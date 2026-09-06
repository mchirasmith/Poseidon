"""Raw month -> interim regridded product files, and lazy per-chunk readers for assembly."""
from __future__ import annotations

from pathlib import Path

import xarray as xr

from pipeline import align, qc, regrid
from pipeline.sources import DEFAULT_GRID, PRODUCTS, SLA_MAX_ERR_M, SST_MAX_ANALYSIS_ERROR_C, Grid

_DIM_RENAME = {"latitude": "lat", "longitude": "lon"}


def _std_dims(ds: xr.Dataset) -> xr.Dataset:
    rename = {k: v for k, v in _DIM_RENAME.items() if k in ds.dims}
    return ds.rename(rename) if rename else ds


def _load_sst(ds: xr.Dataset) -> xr.DataArray:
    sst = qc.kelvin_to_celsius(ds["analysed_sst"])
    if "mask" in ds:
        sst = qc.apply_flag_mask(sst, ds["mask"], valid_value=1.0)
    if "analysis_error" in ds:
        sst = qc.apply_error_threshold(sst, ds["analysis_error"], SST_MAX_ANALYSIS_ERROR_C)
    return qc.range_check(sst, "sst").rename("sst")


def _load_sss(ds: xr.Dataset) -> xr.DataArray:
    sos = ds["sos"]
    if "depth" in sos.dims:  # the Copernicus surface salinity keeps a size-1 depth axis at 0 m
        sos = sos.squeeze("depth", drop=True)
    return qc.range_check(sos, "sss").rename("sss")


def _load_sla(ds: xr.Dataset) -> xr.DataArray:
    sla = ds["sla"]
    if "err_sla" in ds:
        sla = qc.apply_error_threshold(sla, ds["err_sla"], SLA_MAX_ERR_M)
    return qc.range_check(sla, "sla").rename("sla")


def _load_glorys(ds: xr.Dataset) -> xr.DataArray:
    return qc.range_check(ds["thetao_glor"], "thetao").rename("thetao")


def _load_cur(ds: xr.Dataset) -> xr.Dataset:
    u = qc.range_check(ds["u"], "cur_u").rename("cur_u")
    v = qc.range_check(ds["v"], "cur_v").rename("cur_v")
    return xr.merge([u, v])


def _load_wnd(ds: xr.Dataset) -> xr.Dataset:
    u = align.to_daily_mean(qc.range_check(ds["uwnd"], "wnd_u")).rename("wnd_u")
    v = align.to_daily_mean(qc.range_check(ds["vwnd"], "wnd_v")).rename("wnd_v")
    return xr.merge([u, v])


_SCALAR_LOADERS = {"sst": _load_sst, "sss": _load_sss, "sla": _load_sla, "glorys": _load_glorys}
_VECTOR_LOADERS = {"cur": _load_cur, "wnd": _load_wnd}


def regrid_month(name: str, raw_path: Path, interim_dir: Path, month_key: str, grid: Grid = DEFAULT_GRID) -> Path:
    """QC + regrid one raw month to the target grid, write interim/<name>/<month>.nc."""
    product = PRODUCTS[name]
    out_dir = interim_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{month_key}.nc"

    with xr.open_dataset(raw_path) as raw:
        ds = _std_dims(raw.load())
        if isinstance(ds.indexes.get("time"), xr.CFTimeIndex):  # OSCAR currents use a Julian calendar
            ds = ds.assign_coords(time=ds.indexes["time"].to_datetimeindex())
        if name in _SCALAR_LOADERS:
            da = _SCALAR_LOADERS[name](ds)
            out = regrid.to_grid(da, product.source_step_deg, grid.lat, grid.lon).to_dataset()
        else:
            merged = _VECTOR_LOADERS[name](ds)
            out = xr.merge(
                regrid.to_grid(merged[v], product.source_step_deg, grid.lat, grid.lon) for v in merged.data_vars
            )
    out.to_netcdf(out_path)
    return out_path


class ProductReader:
    """Interim monthly file paths for one product, opened only for the months a slice needs."""

    def __init__(self, name: str, year0: int, year1: int, interim_dir: Path):
        self.name = name
        self._paths: dict[str, Path] = {}
        for year in range(year0, year1 + 1):
            for month in range(1, 13):
                month_key = f"{year:04d}-{month:02d}"
                path = interim_dir / name / f"{month_key}.nc"
                if path.exists():
                    self._paths[month_key] = path

    def slice(self, calendar_chunk):
        """Open only the months `calendar_chunk` overlaps, reindex, and load that slice into memory."""
        months = sorted({f"{t.year:04d}-{t.month:02d}" for t in calendar_chunk})
        paths = [self._paths[m] for m in months if m in self._paths]
        if not paths:
            return None
        with xr.open_mfdataset(paths, combine="by_coords", chunks={"time": len(calendar_chunk)}) as combined:
            return align.reindex_to_calendar(combined, calendar_chunk).load()

    def close(self) -> None:
        pass  # files are opened and closed within each slice() call
