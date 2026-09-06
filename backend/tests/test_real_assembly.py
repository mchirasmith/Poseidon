"""Real-path assembly on fake raw files: no network, exercises download -> zarr end to end."""
from __future__ import annotations

import json
from pathlib import Path

import earthaccess
import numpy as np
import pandas as pd
import pytest
import xarray as xr
import zarr

from pipeline import align, climatology, download, interim, normalise, run
from pipeline import split as split_stage
from pipeline.sources import DEPTHS_M, SPLIT_TRAIN, Grid

GRID = Grid(
    lat=np.round(np.arange(10.125, 11.5, 0.25), 3),
    lon=np.round(np.arange(60.125, 62.0, 0.25), 3),
)
YEAR = 2014
MISSING_MONTH = {"sss": 6}  # exercises the has_data=False download path for one product/month
NATIVE_DEPTHS = np.array([0.0, 5, 15, 30, 60, 100, 150, 200, 300, 500, 800, 1100], dtype=np.float32)


def _raw_axis(step: float, margin_cells: int = 2) -> tuple[np.ndarray, np.ndarray]:
    lat = np.arange(GRID.lat[0] - margin_cells * 0.25, GRID.lat[-1] + margin_cells * 0.25 + 1e-6, step)
    lon = np.arange(GRID.lon[0] - margin_cells * 0.25, GRID.lon[-1] + margin_cells * 0.25 + 1e-6, step)
    return lat, lon


def _month_time(year: int, month: int, freq: str = "1D") -> pd.DatetimeIndex:
    start = pd.Timestamp(year, month, 1)
    end = start + pd.offsets.MonthEnd(0)
    return pd.date_range(start, end, freq=freq)


def _sst_ds(year: int, month: int, has_data: bool) -> xr.Dataset:
    lat, lon = _raw_axis(0.05)
    time = _month_time(year, month)
    shape = (len(time), len(lat), len(lon))
    if has_data:
        base = 300.0 + 2.0 * np.sin(np.radians(lat))[None, :, None]
        sst_k = np.broadcast_to(base, shape).astype(np.float32) + 0.05 * np.arange(len(time))[:, None, None]
    else:
        sst_k = np.full(shape, np.nan, dtype=np.float32)
    mask = np.ones((len(lat), len(lon)), dtype=np.int8)
    return xr.Dataset(
        {
            "analysed_sst": (("time", "latitude", "longitude"), sst_k),
            "analysis_error": (("time", "latitude", "longitude"), np.full(shape, 0.2, dtype=np.float32)),
            "mask": (("latitude", "longitude"), mask),
        },
        coords={"time": time, "latitude": lat, "longitude": lon},
    )


def _sss_ds(year: int, month: int, has_data: bool) -> xr.Dataset:
    lat, lon = _raw_axis(0.125)
    time = _month_time(year, month)
    shape = (len(time), len(lat), len(lon))
    sos = (34.5 + 0.1 * np.cos(np.radians(lon))[None, None, :]) if has_data else np.nan
    sos = np.broadcast_to(sos, shape).astype(np.float32) if has_data else np.full(shape, np.nan, dtype=np.float32)
    return xr.Dataset({"sos": (("time", "latitude", "longitude"), sos)}, coords={"time": time, "latitude": lat, "longitude": lon})


def _sla_ds(year: int, month: int, has_data: bool) -> xr.Dataset:
    lat, lon = _raw_axis(0.125)
    time = _month_time(year, month)
    shape = (len(time), len(lat), len(lon))
    if has_data:
        sla = 0.05 * np.sin(np.arange(len(time)))[:, None, None] * np.ones(shape[1:])[None]
        sla = sla.astype(np.float32)
    else:
        sla = np.full(shape, np.nan, dtype=np.float32)
    return xr.Dataset(
        {"sla": (("time", "latitude", "longitude"), sla), "err_sla": (("time", "latitude", "longitude"), np.full(shape, 0.01, dtype=np.float32))},
        coords={"time": time, "latitude": lat, "longitude": lon},
    )


def _glorys_ds(year: int, month: int, has_data: bool) -> xr.Dataset:
    # The 0.25 deg ensemble member has cell centres on whole quarter degrees, offset from the target x.125 grid.
    lat, lon = _raw_axis(0.25)
    lat, lon = lat - 0.125, lon - 0.125
    time = _month_time(year, month)
    shape = (len(time), len(NATIVE_DEPTHS), len(lat), len(lon))
    if has_data:
        profile = (28.0 - 0.02 * NATIVE_DEPTHS)[None, :, None, None]
        thetao = np.broadcast_to(profile, shape).astype(np.float32).copy()
        thetao += 0.02 * np.arange(len(time))[:, None, None, None]
        thetao[:, :, :, lon < GRID.lon[0] + 0.125] = np.nan  # dry column: becomes land/wet=0 after regrid
    else:
        thetao = np.full(shape, np.nan, dtype=np.float32)
    return xr.Dataset(
        {"thetao_glor": (("time", "depth", "latitude", "longitude"), thetao)},
        coords={"time": time, "depth": NATIVE_DEPTHS, "latitude": lat, "longitude": lon},
    )


_COPERNICUS_BUILDERS = {"sst": _sst_ds, "sss": _sss_ds, "sla": _sla_ds, "glorys": _glorys_ds}


def _fake_download_month(product, year: int, month: int, raw_dir: Path) -> Path:
    name = product.name
    month_key = f"{year:04d}-{month:02d}"
    out_dir = raw_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{month_key}.nc"
    if download.is_done(raw_dir, name, month_key):
        return out_path
    has_data = month != MISSING_MONTH.get(name)
    ds = _COPERNICUS_BUILDERS[name](year, month, has_data)
    ds.to_netcdf(out_path)
    download.mark_done(raw_dir, name, month_key)
    return out_path


# --- PO.DAAC path: no monkeypatch of download_podaac_month, only of earthaccess itself.
# Global-extent files with each product's real dim naming, so the real crop/rename/sort logic runs.

_PODAAC_STEP_DEG = 0.25


def _global_cur_ds(year: int, month: int) -> xr.Dataset:
    """OSCAR-style file: latitude/longitude dims, descending latitude, uncropped extent."""
    lat = np.arange(35.0, -0.001, -_PODAAC_STEP_DEG)
    lon = np.arange(40.0, 110.001, _PODAAC_STEP_DEG)
    time = _month_time(year, month)
    shape = (len(time), len(lat), len(lon))
    return xr.Dataset(
        {
            "u": (("time", "latitude", "longitude"), 0.1 * np.ones(shape, dtype=np.float32)),
            "v": (("time", "latitude", "longitude"), -0.05 * np.ones(shape, dtype=np.float32)),
        },
        coords={"time": time, "latitude": lat, "longitude": lon},
    )


def _global_wnd_ds(year: int, month: int) -> xr.Dataset:
    """CCMP-style file: lat/lon dims, ascending latitude, 0..360 longitude convention, uncropped extent."""
    lat = np.arange(0.0, 35.001, _PODAAC_STEP_DEG)
    lon = np.arange(40.0, 110.001, _PODAAC_STEP_DEG)
    time = _month_time(year, month, freq="6h")
    shape = (len(time), len(lat), len(lon))
    return xr.Dataset(
        {
            "uwnd": (("time", "lat", "lon"), 3.0 * np.ones(shape, dtype=np.float32)),
            "vwnd": (("time", "lat", "lon"), 1.0 * np.ones(shape, dtype=np.float32)),
        },
        coords={"time": time, "lat": lat, "lon": lon},
    )


_GLOBAL_BUILDERS = {"cur": _global_cur_ds, "wnd": _global_wnd_ds}
_SHORT_NAME_TO_PRODUCT = {"OSCAR_L4_OC_FINAL_V2.0": "cur", "CCMP_WINDS_10M6HR_L4_V3.1": "wnd"}


class _FakeAuth:
    authenticated = True


def _fake_login(strategy, **kwargs):
    return _FakeAuth()


def _fake_search_data(short_name, temporal, bounding_box, count):
    start = pd.Timestamp(temporal[0])
    return [{"product": _SHORT_NAME_TO_PRODUCT[short_name], "year": start.year, "month": start.month}]


def _fake_earthaccess_download(granules, local_path):
    paths = []
    for g in granules:
        ds = _GLOBAL_BUILDERS[g["product"]](g["year"], g["month"])
        out = Path(local_path) / f"{g['product']}_{g['year']:04d}{g['month']:02d}.nc"
        ds.to_netcdf(out)
        paths.append(str(out))
    return paths


def _char_array(values: list[str], width: int) -> np.ndarray:
    return np.array([list(v.ljust(width).encode("ascii")[:width]) for v in values], dtype="S1")


def _write_argo_profile(path: Path, lat: float, lon: float, wmo: str, day: pd.Timestamp) -> None:
    pres = np.array([[0.0, 10.0, 20.0, 50.0, 100.0, 200.0, 400.0, 800.0]], dtype=np.float32)
    temp = (28.0 - 0.02 * pres).astype(np.float32)
    ds = xr.Dataset(
        {
            "PRES": (("N_PROF", "N_LEVELS"), pres),
            "TEMP": (("N_PROF", "N_LEVELS"), temp),
            "TEMP_ADJUSTED": (("N_PROF", "N_LEVELS"), temp),
            "TEMP_QC": (("N_PROF", "N_LEVELS"), np.full(pres.shape, b"1", dtype="S1")),
            "TEMP_ADJUSTED_QC": (("N_PROF", "N_LEVELS"), np.full(pres.shape, b"1", dtype="S1")),
            "DATA_MODE": (("N_PROF",), np.array([b"D"], dtype="S1")),
            "PLATFORM_NUMBER": (("N_PROF", "STRING8"), _char_array([wmo], 8)),
            "JULD": (("N_PROF",), np.array([day], dtype="datetime64[ns]")),
            "LATITUDE": (("N_PROF",), np.array([lat], dtype=np.float64)),
            "LONGITUDE": (("N_PROF",), np.array([lon], dtype=np.float64)),
        }
    )
    ds.to_netcdf(path)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / "data"
    monkeypatch.setattr(download, "credentials_status", lambda: {"copernicus": True, "podaac": True})
    monkeypatch.setattr(download, "download_copernicus_month", _fake_download_month)
    monkeypatch.setattr(earthaccess, "login", _fake_login)
    monkeypatch.setattr(earthaccess, "search_data", _fake_search_data)
    monkeypatch.setattr(earthaccess, "download", _fake_earthaccess_download)
    monkeypatch.setattr(download, "download_argo_index", lambda: pd.DataFrame())
    monkeypatch.setattr(download, "filter_argo_index", lambda df, start, end: df)

    argo_dir = d / "raw" / "argo"
    argo_dir.mkdir(parents=True)
    profiles = []
    for i, (lat, lon) in enumerate([(10.6, 61.0), (10.9, 61.4), (10.3, 60.4)]):
        p = argo_dir / f"profile_{i}.nc"
        _write_argo_profile(p, lat, lon, f"19000{i}", pd.Timestamp(2014, 1, 15 + i))
        profiles.append(p)
    monkeypatch.setattr(download, "download_argo_profiles", lambda index, raw_dir: profiles)
    return d


PRODUCTS = ["sst", "sss", "sla", "glorys", "cur", "wnd"]


def test_real_assembly_produces_valid_schema(data_dir: Path):
    zarr_path = run.assemble_real(data_dir, PRODUCTS, YEAR, YEAR, GRID)
    g = zarr.open_consolidated(str(zarr_path))

    H, W = len(GRID.lat), len(GRID.lon)
    D = len(DEPTHS_M)
    assert g["x"].shape == (365, 7, H, W) and str(g["x"].dtype) == "float16"
    assert g["x_mask"].shape == (365, 5, H, W) and str(g["x_mask"].dtype) == "uint8"
    assert g["y"].shape == (365, D, H, W) and str(g["y"].dtype) == "float16"
    assert g["y_raw"].shape == (365, D, H, W) and str(g["y_raw"].dtype) == "float16"
    assert g["wet"].shape == (H, W)
    assert g["bottom"].shape == (D, H, W)
    assert g["static"].shape == (3, H, W)
    assert g["clim_x"].shape == (366, 7, H, W)
    assert g["clim_y"].shape == (366, D, H, W)
    for name in ["x", "x_mask", "y", "y_raw", "split"]:
        assert g[name].chunks[0] == 32

    wet = g["wet"][:]
    assert wet.sum() > 0 and wet.sum() < wet.size  # the dry column is masked out, the rest is wet

    sst_k = 0
    sst = g["x"][:, sst_k].astype(np.float32)
    valid_sst = sst[np.isfinite(sst)]
    assert valid_sst.size > 0
    assert np.abs(valid_sst).max() < 50  # normalised anomaly, not raw Kelvin

    y_raw = g["y_raw"][:].astype(np.float32)
    wet_cells = wet.astype(bool)
    surface_wet = y_raw[:, 0][:, wet_cells]
    assert np.isfinite(surface_wet).any()
    assert np.nanmax(surface_wet) < 40 and np.nanmin(surface_wet) > -2  # degC, sane range

    y_anom = g["y"][:].astype(np.float32)
    finite = y_anom[np.isfinite(y_anom)]
    assert finite.size > 0 and np.isfinite(finite).all()

    bottom = g["bottom"][:]
    assert bottom[:, ~wet_cells].sum() == 0  # dry column never above seafloor

    # static[1] is a normalised seafloor depth: 0 on the dry column, > 0 on wet cells with a full profile
    static = g["static"][:]
    assert (static[1][~wet_cells] == 0).all()
    assert (static[1][wet_cells] > 0).any()

    assert not (data_dir / "raw" / "glorys" / "2014-01.nc").exists()
    assert not (data_dir / "raw" / "glorys" / "2014-02.nc").exists()

    df = pd.read_parquet(data_dir / "argo_matchups.parquet")
    expected_cols = {"date", "wmo", "lat", "lon", "cell_i", "cell_j", "dist_km"} | {f"t_{int(d)}" for d in DEPTHS_M}
    assert expected_cols.issubset(df.columns)
    assert len(df) == 3


def test_real_assembly_resumes_without_reassembling(data_dir: Path, monkeypatch):
    run.assemble_real(data_dir, PRODUCTS, YEAR, YEAR, GRID)

    def _boom(*a, **k):
        raise AssertionError("assembly should have been skipped on resume")

    import pipeline.run as run_module

    orig_assemble, orig_argo = run_module._assemble, run_module._build_argo_matchups
    run_module._assemble = _boom
    run_module._build_argo_matchups = _boom
    monkeypatch.setattr(interim, "regrid_month", _boom)
    try:
        run.assemble_real(data_dir, PRODUCTS, YEAR, YEAR, GRID)
    finally:
        run_module._assemble = orig_assemble
        run_module._build_argo_matchups = orig_argo


def test_pass1_streaming_matches_in_memory_fit(data_dir: Path):
    """run._fit_stats_streaming's chunked climatology/stats match a single-shot in-memory fit."""
    zarr_path = run.assemble_real(data_dir, ["sst"], YEAR, YEAR, GRID)
    g = zarr.open_consolidated(str(zarr_path))

    calendar = align.master_calendar(f"{YEAR}-01-01", f"{YEAR}-12-31")
    doy = np.asarray(calendar.dayofyear)
    train_idx = np.where(split_stage.split_codes(calendar) == SPLIT_TRAIN)[0]
    train_cal, train_doy = calendar[train_idx], doy[train_idx]

    reader = interim.ProductReader("sst", YEAR, YEAR, data_dir / "interim")
    vals = reader.slice(train_cal)["sst"].transpose("time", "lat", "lon").values.astype(np.float32)
    mask = np.isfinite(vals).astype(np.float64)
    _, clim_ref = climatology.fit_evaluate(vals, mask, train_doy)
    anom = vals - clim_ref[(train_doy - 1) % 366]
    mean_ref, std_ref, _ = normalise.fit_normalise(anom, mask, np.arange(len(train_idx)))

    clim_streamed = g["clim_x"][:, 0].astype(np.float32)
    finite = np.isfinite(clim_ref) & np.isfinite(clim_streamed)
    assert finite.sum() > 0
    np.testing.assert_allclose(clim_streamed[finite], clim_ref[finite], rtol=1e-2, atol=1e-2)

    norm = json.loads(g.attrs["norm"])
    assert abs(norm["sst"]["mean"] - mean_ref) < 1e-2
    assert abs(norm["sst"]["std"] - std_ref) < 1e-2
