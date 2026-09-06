"""CLI entry: `python -m pipeline.run --years 2014-2020` or `--synthetic ...`."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import zarr

from pipeline import align, climatology, download, interim, masks, normalise, synthetic, target, zarr_writer
from pipeline import argo_matchups
from pipeline import split as split_stage
from pipeline.sources import (
    DEFAULT_GRID,
    DEPTHS_M,
    PRODUCTS,
    SPLIT_TRAIN,
    X_MASK_VARS,
    X_VARS,
    ZARR_TIME_CHUNK,
    Grid,
    required_services,
)

_VAR_PRODUCT = {
    "sst": "sst", "sss": "sss", "sla": "sla",
    "cur_u": "cur", "cur_v": "cur", "wnd_u": "wnd", "wnd_v": "wnd",
}


def _parse_years(spec: str) -> tuple[int, int]:
    a, b = spec.split("-")
    return int(a), int(b)


def run_synthetic(args: argparse.Namespace) -> None:
    out = synthetic.generate(args.data_dir, args.start, args.end, args.ny, args.nx, args.seed)
    print(f"synthetic store written: {out}")


def _check_credentials(products: list[str]) -> None:
    needed = required_services(products)
    status = download.credentials_status()
    missing = {s for s in needed if not status.get(s, False)}
    if missing:
        print(download.credentials_instructions(missing))
        sys.exit(1)


def _download_and_regrid(products: list[str], year0: int, year1: int, raw_dir: Path, interim_dir: Path, grid: Grid) -> None:
    for name in products:
        product = PRODUCTS[name]
        for year in range(year0, year1 + 1):
            for month in range(1, 13):
                month_key = f"{year:04d}-{month:02d}"
                if download.is_done(interim_dir, name, month_key):
                    continue
                if product.kind == "copernicus":
                    raw_path = download.download_copernicus_month(product, year, month, raw_dir)
                else:
                    raw_path = download.download_podaac_month(product, year, month, raw_dir)
                interim.regrid_month(name, raw_path, interim_dir, month_key, grid)
                download.mark_done(interim_dir, name, month_key)
                if name == "glorys":
                    Path(raw_path).unlink(missing_ok=True)


def _glorys_std_depths(sliced) -> np.ndarray:
    """(t, depth, H, W) native GLORYS -> (t, 15, H, W) on the standard depths."""
    thetao = sliced["thetao"].transpose("time", "depth", "lat", "lon").values
    src_depths = sliced["depth"].values
    profile = np.moveaxis(thetao, 1, -1)  # (t, H, W, depth)
    return np.moveaxis(target.to_standard_depths(profile, src_depths), -1, 1).astype(np.float32)


def _wet_and_bottom(glorys_reader, calendar, grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    """Streaming valid-day fraction from GLORYS, chunked so the full record is never held in RAM."""
    H, W = len(grid.lat), len(grid.lon)
    valid_surface = np.zeros((H, W), dtype=np.int64)
    valid_depth = np.zeros((len(DEPTHS_M), H, W), dtype=np.int64)
    n_total = 0
    T = len(calendar)
    for t0 in range(0, T, ZARR_TIME_CHUNK):
        t1 = min(t0 + ZARR_TIME_CHUNK, T)
        n_total += t1 - t0
        if glorys_reader is None:
            continue
        sliced = glorys_reader.slice(calendar[t0:t1])
        if sliced is None:
            continue
        valid_surface += np.isfinite(sliced["thetao"].transpose("time", "depth", "lat", "lon").values[:, 0]).sum(axis=0)
        y_std = _glorys_std_depths(sliced)
        valid_depth += np.isfinite(y_std).sum(axis=0)
    n_total = max(n_total, 1)
    wet = masks.fraction_mask(valid_surface / n_total)
    bottom = masks.fraction_mask(valid_depth / n_total)
    return wet, bottom


def _fit_stats_streaming(extract, train_cal, train_doy: np.ndarray, H: int, W: int) -> tuple[np.ndarray, float, float]:
    """One channel's climatology and anomaly mean/std, streamed in ZARR_TIME_CHUNK-day slices.

    `extract(chunk_cal)` returns that chunk's (Tc, H, W) values; never more than one chunk is held.
    """
    acc = climatology.init_accumulator(H * W)
    n = len(train_cal)
    for t0 in range(0, n, ZARR_TIME_CHUNK):
        t1 = min(t0 + ZARR_TIME_CHUNK, n)
        vals = extract(train_cal[t0:t1])
        climatology.accumulate(acc, vals, np.isfinite(vals), train_doy[t0:t1])
    _, clim = climatology.solve(acc, H, W)

    stats = normalise.init_stats()
    for t0 in range(0, n, ZARR_TIME_CHUNK):
        t1 = min(t0 + ZARR_TIME_CHUNK, n)
        vals = extract(train_cal[t0:t1])
        anom = vals - clim[(train_doy[t0:t1] - 1) % 366]
        normalise.accumulate_stats(stats, anom, np.isfinite(vals))
    mean, std = normalise.solve_stats(stats)
    return clim.astype(np.float16), mean, std


def _assembly_done(zarr_path: Path, data_hash: str) -> bool:
    if not zarr_path.exists():
        return False
    try:
        root = zarr.open_consolidated(str(zarr_path))
        return bool(root.attrs.get("complete")) and root.attrs.get("data_hash") == data_hash
    except Exception:
        return False


def _assemble(interim_dir: Path, zarr_path: Path, products: list[str], year0: int, year1: int, grid: Grid, data_hash: str) -> None:
    calendar = align.master_calendar(f"{year0}-01-01", f"{year1}-12-31")
    H, W = len(grid.lat), len(grid.lon)
    T = len(calendar)
    doy = np.asarray(calendar.dayofyear)
    split_arr = split_stage.split_codes(calendar)
    train_idx = np.where(split_arr == SPLIT_TRAIN)[0]
    if train_idx.size == 0:
        raise ValueError(f"no training days between {year0} and {year1}: check the split-year boundaries")

    surface_products = [p for p in ("sst", "sss", "sla", "cur", "wnd") if p in products]
    readers = {name: interim.ProductReader(name, year0, year1, interim_dir) for name in surface_products}
    glorys_reader = interim.ProductReader("glorys", year0, year1, interim_dir) if "glorys" in products else None

    wet, bottom = _wet_and_bottom(glorys_reader, calendar, grid)
    coast_dist = masks.coast_distance(wet.astype(bool))
    static = np.stack([wet.astype(np.float32), masks.bottom_depth_norm(bottom), coast_dist])

    train_cal = calendar[train_idx]
    train_doy = doy[train_idx]

    def _extract_x(v: str):
        reader = readers.get(_VAR_PRODUCT[v])

        def extract(chunk_cal):
            sliced = reader.slice(chunk_cal) if reader is not None else None
            if sliced is not None and v in sliced:
                return sliced[v].transpose("time", "lat", "lon").values.astype(np.float32)
            return np.full((len(chunk_cal), H, W), np.nan, dtype=np.float32)

        return extract

    def _extract_y(d: int):
        def extract(chunk_cal):
            sliced = glorys_reader.slice(chunk_cal) if glorys_reader is not None else None
            if sliced is not None:
                return _glorys_std_depths(sliced)[:, d]
            return np.full((len(chunk_cal), H, W), np.nan, dtype=np.float32)

        return extract

    clim_x = np.empty((366, len(X_VARS), H, W), dtype=np.float16)
    x_stats: dict[str, tuple[float, float]] = {}
    for k, v in enumerate(X_VARS):
        clim_x[:, k], mean, std = _fit_stats_streaming(_extract_x(v), train_cal, train_doy, H, W)
        x_stats[v] = (mean, std)

    clim_y = np.empty((366, len(DEPTHS_M), H, W), dtype=np.float16)
    y_stats: list[tuple[float, float]] = []
    for d in range(len(DEPTHS_M)):
        clim_y[:, d], mean, std = _fit_stats_streaming(_extract_y(d), train_cal, train_doy, H, W)
        y_stats.append((mean, std))

    norm = {v: {"mean": m, "std": s} for v, (m, s) in x_stats.items()}
    norm.update({f"y_depth_{int(DEPTHS_M[d])}": {"mean": m, "std": s} for d, (m, s) in enumerate(y_stats)})

    root = zarr_writer.create_store_custom(zarr_path, calendar.values, grid.lat, grid.lon, static, wet, bottom, norm, data_hash)
    zarr_writer.write_climatology(root, clim_x, clim_y)

    for t0 in range(0, T, ZARR_TIME_CHUNK):
        t1 = min(t0 + ZARR_TIME_CHUNK, T)
        chunk_cal, chunk_doy, Tc = calendar[t0:t1], doy[t0:t1], t1 - t0

        x_chunk = np.full((Tc, len(X_VARS), H, W), np.nan, dtype=np.float32)
        x_mask_raw = np.zeros((Tc, len(X_MASK_VARS), H, W), dtype=np.uint8)
        for m, product_name in enumerate(X_MASK_VARS):
            reader = readers.get(product_name)
            sliced = reader.slice(chunk_cal) if reader is not None else None
            var_names = [v for v in X_VARS if _VAR_PRODUCT[v] == product_name]
            valid = np.ones((Tc, H, W), dtype=bool)
            for v in var_names:
                k = X_VARS.index(v)
                if sliced is not None and v in sliced:
                    arr = sliced[v].transpose("time", "lat", "lon").values.astype(np.float32)
                    x_chunk[:, k] = arr
                    valid &= np.isfinite(arr)
                else:
                    valid &= False
            x_mask_raw[:, m] = valid.astype(np.uint8)
        x_mask_chunk = masks.modality_masks(x_mask_raw, wet)
        for k, v in enumerate(X_VARS):
            m = X_MASK_VARS.index(_VAR_PRODUCT[v])
            x_chunk[:, k][x_mask_chunk[:, m] == 0] = np.nan

        if glorys_reader is not None:
            sliced = glorys_reader.slice(chunk_cal)
            y_raw_chunk = _glorys_std_depths(sliced) if sliced is not None else np.full((Tc, len(DEPTHS_M), H, W), np.nan, dtype=np.float32)
        else:
            y_raw_chunk = np.full((Tc, len(DEPTHS_M), H, W), np.nan, dtype=np.float32)
        y_raw_chunk = np.where(bottom[None] == 0, np.nan, y_raw_chunk).astype(np.float32)

        x_norm_chunk = np.empty((Tc, len(X_VARS), H, W), dtype=np.float16)
        for k, v in enumerate(X_VARS):
            clim_full = clim_x[:, k][(chunk_doy - 1) % 366]
            mean, std = x_stats[v]
            x_norm_chunk[:, k] = normalise.apply_normalise(x_chunk[:, k] - clim_full, mean, std)

        y_norm_chunk = np.empty((Tc, len(DEPTHS_M), H, W), dtype=np.float16)
        for d in range(len(DEPTHS_M)):
            clim_full = clim_y[:, d][(chunk_doy - 1) % 366]
            mean, std = y_stats[d]
            y_norm_chunk[:, d] = normalise.apply_normalise(y_raw_chunk[:, d] - clim_full, mean, std)

        # store invariant (see zarr_writer.py header): x is 0, never NaN, wherever x_mask is 0
        for k, v in enumerate(X_VARS):
            m = X_MASK_VARS.index(_VAR_PRODUCT[v])
            x_norm_chunk[:, k][x_mask_chunk[:, m] == 0] = 0.0

        zarr_writer.write_time_chunk(root, t0, t1, x_norm_chunk, x_mask_chunk, y_norm_chunk, y_raw_chunk.astype(np.float16), split_arr[t0:t1])

    root.attrs["complete"] = True
    zarr_writer.finalize(zarr_path)
    for reader in list(readers.values()) + ([glorys_reader] if glorys_reader else []):
        reader.close()


def _decode_chars(raw) -> str:
    """Argo char arrays / byte strings -> a plain str."""
    if isinstance(raw, (bytes, np.bytes_)):
        return raw.decode("utf-8", "ignore").strip()
    if isinstance(raw, np.ndarray):
        return b"".join(x if isinstance(x, (bytes, np.bytes_)) else str(x).encode() for x in raw.ravel()).decode("utf-8", "ignore").strip()
    return str(raw).strip()


def _read_argo_profile(path: Path) -> dict | None:
    """One GDAC profile NetCDF -> the kwargs for argo_matchups.build_matchup_row."""
    import pandas as pd
    import xarray as xr

    with xr.open_dataset(path) as ds:
        if "PRES" not in ds or "TEMP" not in ds:
            return None
        pres = np.asarray(ds["PRES"].values[0], dtype=np.float64)
        temp = np.asarray(ds["TEMP"].values[0], dtype=np.float64)
        n = len(temp)
        temp_adj = np.asarray(ds["TEMP_ADJUSTED"].values[0], dtype=np.float64) if "TEMP_ADJUSTED" in ds else np.full(n, np.nan)
        temp_qc = list(_decode_chars(ds["TEMP_QC"].values[0])) if "TEMP_QC" in ds else ["9"] * n
        temp_adj_qc = list(_decode_chars(ds["TEMP_ADJUSTED_QC"].values[0])) if "TEMP_ADJUSTED_QC" in ds else ["9"] * n
        data_mode = _decode_chars(ds["DATA_MODE"].values[0]) if "DATA_MODE" in ds else "R"
        return dict(
            date=pd.Timestamp(ds["JULD"].values[0]),
            wmo=_decode_chars(ds["PLATFORM_NUMBER"].values[0]),
            lat=float(ds["LATITUDE"].values[0]),
            lon=float(ds["LONGITUDE"].values[0]),
            pres=pres, temp=temp, temp_adj=temp_adj,
            temp_qc=temp_qc, temp_adj_qc=temp_adj_qc, data_mode=data_mode,
        )


def _build_argo_matchups(raw_dir: Path, year0: int, year1: int, grid: Grid, out_path: Path) -> None:
    index = download.download_argo_index()
    filtered = download.filter_argo_index(index, f"{year0}-01-01", f"{year1}-12-31")
    paths = download.download_argo_profiles(filtered, raw_dir)
    profiles = [p for p in (_read_argo_profile(f) for f in paths) if p is not None]
    df = argo_matchups.build_matchups(profiles, grid)
    df.to_parquet(out_path)


def assemble_real(data_dir: str | Path, products: list[str], year0: int, year1: int, grid: Grid = DEFAULT_GRID) -> Path:
    """Download, regrid, align, mask, target, split, climatology, normalise, write zarr, then Argo matchups."""
    data_dir = Path(data_dir)
    raw_dir, interim_dir = data_dir / "raw", data_dir / "interim"
    raw_dir.mkdir(parents=True, exist_ok=True)
    interim_dir.mkdir(parents=True, exist_ok=True)

    _check_credentials(products)
    _download_and_regrid(products, year0, year1, raw_dir, interim_dir, grid)

    zarr_path = data_dir / "poseidon.zarr"
    data_hash = hashlib.sha256(f"{sorted(products)}:{year0}:{year1}:{len(grid.lat)}x{len(grid.lon)}".encode()).hexdigest()
    if _assembly_done(zarr_path, data_hash):
        print(f"assembly already complete: {zarr_path}")
    else:
        _assemble(interim_dir, zarr_path, products, year0, year1, grid, data_hash)

    argo_path = data_dir / "argo_matchups.parquet"
    if argo_path.exists():
        print(f"argo matchups already complete: {argo_path}")
    else:
        _build_argo_matchups(raw_dir, year0, year1, grid, argo_path)
    return zarr_path


def run_real(args: argparse.Namespace) -> None:
    year0, year1 = _parse_years(args.years)
    products = args.products or list(PRODUCTS)
    assemble_real(args.data_dir, products, year0, year1)
    print("real pipeline complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Poseidon data pipeline")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--years", default="2014-2020")
    parser.add_argument("--products", nargs="*")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--start", default="2014-01-01")
    parser.add_argument("--end", default="2020-12-31")
    parser.add_argument("--ny", type=int, default=100)
    parser.add_argument("--nx", type=int, default=240)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if args.synthetic:
        run_synthetic(args)
    else:
        run_real(args)


if __name__ == "__main__":
    main()
