"""CLI entry: `python -m pipeline.run --years 2014-2020` or `--synthetic ...`."""
from __future__ import annotations

import argparse
import hashlib
import os
import time
import sys
from concurrent.futures import ProcessPoolExecutor
from itertools import repeat
from pathlib import Path

import numpy as np
import zarr

from pipeline import align, climatology, download, interim, masks, normalise, synthetic, target, zarr_writer
from pipeline import argo_matchups
from pipeline import split as split_stage
from pipeline.sources import (
    DEFAULT_GRID,
    DOWNLOAD_RETRIES,
    DOWNLOAD_RETRY_WAIT_S,
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


def _download_with_retry(product, year: int, month: int, raw_dir: Path) -> Path:
    fetch = download.download_copernicus_month if product.kind == "copernicus" else download.download_podaac_month
    for attempt in range(DOWNLOAD_RETRIES):
        try:
            return fetch(product, year, month, raw_dir)
        except Exception as exc:  # network errors are transient; the last attempt re-raises
            if attempt == DOWNLOAD_RETRIES - 1:
                raise
            print(f"{product.name} {year}-{month:02d}: {exc.__class__.__name__}, retry in {DOWNLOAD_RETRY_WAIT_S * (attempt + 1)} s")
            time.sleep(DOWNLOAD_RETRY_WAIT_S * (attempt + 1))


def _download_and_regrid_product(name: str, year0: int, year1: int, raw_dir: Path, interim_dir: Path, grid: Grid) -> str:
    """One product's full download+regrid loop; the unit of work for a download worker."""
    product = PRODUCTS[name]
    for year in range(year0, year1 + 1):
        for month in range(1, 13):
            month_key = f"{year:04d}-{month:02d}"
            if download.is_done(interim_dir, name, month_key):
                continue
            raw_path = _download_with_retry(product, year, month, raw_dir)
            interim.regrid_month(name, raw_path, interim_dir, month_key, grid)
            download.mark_done(interim_dir, name, month_key)
            if name == "glorys":
                Path(raw_path).unlink(missing_ok=True)
            print(f"{name} {month_key}: regridded")
    return name


def _download_and_regrid(
    products: list[str], year0: int, year1: int, raw_dir: Path, interim_dir: Path, grid: Grid, workers: int = 1, initializer=None
) -> None:
    """Sequential when workers <= 1 (or a single product); otherwise one spawned process per product."""
    if workers <= 1 or len(products) <= 1:
        for name in products:
            _download_and_regrid_product(name, year0, year1, raw_dir, interim_dir, grid)
        return

    from concurrent.futures import as_completed

    with ProcessPoolExecutor(max_workers=min(workers, len(products)), initializer=initializer) as pool:
        futures = [pool.submit(_download_and_regrid_product, name, year0, year1, raw_dir, interim_dir, grid) for name in products]
        for future in as_completed(futures):
            future.result()


def _glorys_std_depths(sliced) -> np.ndarray:
    """(t, depth, H, W) native GLORYS -> (t, 15, H, W) on the standard depths."""
    thetao = sliced["thetao"].transpose("time", "depth", "lat", "lon").values
    src_depths = sliced["depth"].values
    profile = np.moveaxis(thetao, 1, -1)  # (t, H, W, depth)
    return np.moveaxis(target.to_standard_depths(profile, src_depths), -1, 1).astype(np.float32)


ASSEMBLY_WORKER_RAM_BYTES = 2 * 1024**3  # one 32-day native-depth GLORYS chunk plus its float64 interpolation temporaries


def _available_ram_bytes() -> int | None:
    """Physical memory currently free, or None where the platform does not say (macOS)."""
    if sys.platform == "win32":
        import ctypes

        class _MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        return int(status.ullAvailPhys) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None
    try:
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        return None


def _assembly_workers(requested: int | None) -> int:
    """Worker processes for the assembly passes: all cores but three, capped by free RAM, unless overridden."""
    if requested is not None:
        return max(1, requested)
    workers = max(1, (os.cpu_count() or 4) - 3)
    available = _available_ram_bytes()
    if available is not None:
        workers = min(workers, max(1, available // ASSEMBLY_WORKER_RAM_BYTES))
    return workers


def _chunk_ranges(n: int) -> list[tuple[int, int]]:
    return [(t0, min(t0 + ZARR_TIME_CHUNK, n)) for t0 in range(0, n, ZARR_TIME_CHUNK)]


def _split_groups(items: list, n_groups: int) -> list[list]:
    """Round-robin partition into at most n_groups non-empty lists, one per worker."""
    n_groups = max(1, min(n_groups, len(items)))
    return [items[i::n_groups] for i in range(n_groups)]


class _ChunkSource:
    """Per-worker interim readers; every pass reads calendar slices through the same two methods."""

    def __init__(self, interim_dir: Path, products: list[str], year0: int, year1: int, H: int, W: int):
        surface = [p for p in ("sst", "sss", "sla", "cur", "wnd") if p in products]
        self.readers = {name: interim.ProductReader(name, year0, year1, interim_dir) for name in surface}
        self.glorys = interim.ProductReader("glorys", year0, year1, interim_dir) if "glorys" in products else None
        self.H, self.W = H, W

    def x(self, chunk_cal) -> tuple[np.ndarray, np.ndarray]:
        """(Tc, NX, H, W) float32 raw values (NaN where absent) and (Tc, NXMASK, H, W) uint8 per-product validity."""
        Tc, H, W = len(chunk_cal), self.H, self.W
        x = np.full((Tc, len(X_VARS), H, W), np.nan, dtype=np.float32)
        valid = np.zeros((Tc, len(X_MASK_VARS), H, W), dtype=np.uint8)
        for m, product_name in enumerate(X_MASK_VARS):
            reader = self.readers.get(product_name)
            sliced = reader.slice(chunk_cal) if reader is not None else None
            ok = np.ones((Tc, H, W), dtype=bool)
            for v in (v for v in X_VARS if _VAR_PRODUCT[v] == product_name):
                k = X_VARS.index(v)
                if sliced is not None and v in sliced:
                    arr = sliced[v].transpose("time", "lat", "lon").values.astype(np.float32)
                    x[:, k] = arr
                    ok &= np.isfinite(arr)
                else:
                    ok &= False
            valid[:, m] = ok
        return x, valid

    def glorys_native(self, chunk_cal):
        """The native-depth GLORYS slice, or None when no month overlaps the chunk."""
        return self.glorys.slice(chunk_cal) if self.glorys is not None else None

    def y(self, chunk_cal) -> np.ndarray:
        """(Tc, D, H, W) float32 on the standard depths, NaN where GLORYS is absent."""
        sliced = self.glorys_native(chunk_cal)
        if sliced is None:
            return np.full((len(chunk_cal), len(DEPTHS_M), self.H, self.W), np.nan, dtype=np.float32)
        return _glorys_std_depths(sliced)

    def channels(self, chunk_cal) -> np.ndarray:
        """(Tc, NX + D, H, W) float32: every x variable followed by every target depth."""
        x, _ = self.x(chunk_cal)
        return np.concatenate([x, self.y(chunk_cal)], axis=1)


def _worker_masks(spec: dict, ranges: list[tuple[int, int]]):
    """Valid-day counts at the surface (native depth 0) and on the standard depths for these chunks."""
    src = _ChunkSource(spec["interim_dir"], spec["products"], spec["year0"], spec["year1"], spec["H"], spec["W"])
    calendar = spec["calendar"]
    valid_surface = np.zeros((src.H, src.W), dtype=np.int64)
    valid_depth = np.zeros((len(DEPTHS_M), src.H, src.W), dtype=np.int64)
    n_total = 0
    for t0, t1 in ranges:
        n_total += t1 - t0
        sliced = src.glorys_native(calendar[t0:t1])
        if sliced is None:
            continue
        valid_surface += np.isfinite(sliced["thetao"].transpose("time", "depth", "lat", "lon").values[:, 0]).sum(axis=0)
        valid_depth += np.isfinite(_glorys_std_depths(sliced)).sum(axis=0)
    return valid_surface, valid_depth, n_total


def _worker_clim(spec: dict, ranges: list[tuple[int, int]]):
    """Harmonic normal-equation sums for every channel over these train-day slices."""
    src = _ChunkSource(spec["interim_dir"], spec["products"], spec["year0"], spec["year1"], spec["H"], spec["W"])
    calendar, doy, train_idx = spec["calendar"], spec["doy"], spec["train_idx"]
    n_channels = len(X_VARS) + len(DEPTHS_M)
    accs = [climatology.init_accumulator(src.H * src.W) for _ in range(n_channels)]
    for a, b in ranges:
        idx = train_idx[a:b]
        vals = src.channels(calendar[idx])
        for c in range(n_channels):
            climatology.accumulate(accs[c], vals[:, c], np.isfinite(vals[:, c]), doy[idx])
    return accs


def _worker_stats(spec: dict, ranges: list[tuple[int, int]], clim_path: Path):
    """Anomaly sufficient statistics for every channel over these train-day slices."""
    src = _ChunkSource(spec["interim_dir"], spec["products"], spec["year0"], spec["year1"], spec["H"], spec["W"])
    calendar, doy, train_idx = spec["calendar"], spec["doy"], spec["train_idx"]
    clim = np.load(clim_path, mmap_mode="r")
    n_channels = len(X_VARS) + len(DEPTHS_M)
    stats = [normalise.init_stats() for _ in range(n_channels)]
    for a, b in ranges:
        idx = train_idx[a:b]
        vals = src.channels(calendar[idx])
        anom = vals - clim[(doy[idx] - 1) % 366]
        for c in range(n_channels):
            normalise.accumulate_stats(stats[c], anom[:, c], np.isfinite(vals[:, c]) & np.isfinite(anom[:, c]))
    return stats


def _worker_write(spec: dict, ranges: list[tuple[int, int]], clim_path: Path, zarr_path: Path, norm_stats: list, wet, bottom, split_arr):
    """Mask, normalise and write these calendar chunks into the (already created) store."""
    src = _ChunkSource(spec["interim_dir"], spec["products"], spec["year0"], spec["year1"], spec["H"], spec["W"])
    calendar, doy = spec["calendar"], spec["doy"]
    clim = np.load(clim_path, mmap_mode="r")
    root = zarr.open_group(str(zarr_path), mode="r+")
    NX, D = len(X_VARS), len(DEPTHS_M)
    for t0, t1 in ranges:
        chunk_cal = calendar[t0:t1]
        x_chunk, x_mask_raw = src.x(chunk_cal)
        x_mask_chunk = masks.modality_masks(x_mask_raw, wet)
        for k, v in enumerate(X_VARS):
            m = X_MASK_VARS.index(_VAR_PRODUCT[v])
            x_chunk[:, k][x_mask_chunk[:, m] == 0] = np.nan
        y_raw_chunk = np.where(bottom[None] == 0, np.nan, src.y(chunk_cal)).astype(np.float32)

        clim_chunk = clim[(doy[t0:t1] - 1) % 366]
        x_norm_chunk = np.empty((t1 - t0, NX, src.H, src.W), dtype=np.float16)
        for k in range(NX):
            mean, std = norm_stats[k]
            x_norm_chunk[:, k] = normalise.apply_normalise(x_chunk[:, k] - clim_chunk[:, k], mean, std)
        y_norm_chunk = np.empty((t1 - t0, D, src.H, src.W), dtype=np.float16)
        for d in range(D):
            mean, std = norm_stats[NX + d]
            y_norm_chunk[:, d] = normalise.apply_normalise(y_raw_chunk[:, d] - clim_chunk[:, NX + d], mean, std)

        # store invariant (see zarr_writer.py header): x is 0, never NaN, wherever x_mask is 0
        for k, v in enumerate(X_VARS):
            m = X_MASK_VARS.index(_VAR_PRODUCT[v])
            x_norm_chunk[:, k][x_mask_chunk[:, m] == 0] = 0.0

        zarr_writer.write_time_chunk(root, t0, t1, x_norm_chunk, x_mask_chunk, y_norm_chunk, y_raw_chunk.astype(np.float16), split_arr[t0:t1])
    return ranges


def _assembly_done(zarr_path: Path, data_hash: str) -> bool:
    if not zarr_path.exists():
        return False
    try:
        root = zarr.open_consolidated(str(zarr_path))
        return bool(root.attrs.get("complete")) and root.attrs.get("data_hash") == data_hash
    except Exception:
        return False


def _assemble(
    interim_dir: Path, zarr_path: Path, products: list[str], year0: int, year1: int, grid: Grid, data_hash: str, workers: int | None = None
) -> None:
    """Four parallel passes over 32-day chunks: valid-day masks, climatology fit, anomaly stats, store write."""
    calendar = align.master_calendar(f"{year0}-01-01", f"{year1}-12-31")
    H, W = len(grid.lat), len(grid.lon)
    T = len(calendar)
    doy = np.asarray(calendar.dayofyear)
    split_arr = split_stage.split_codes(calendar)
    train_idx = np.where(split_arr == SPLIT_TRAIN)[0]
    if train_idx.size == 0:
        raise ValueError(f"no training days between {year0} and {year1}: check the split-year boundaries")

    NX, D = len(X_VARS), len(DEPTHS_M)
    n_workers = _assembly_workers(workers)
    spec = dict(interim_dir=interim_dir, products=products, year0=year0, year1=year1, H=H, W=W, calendar=calendar, doy=doy, train_idx=train_idx)
    all_groups = _split_groups(_chunk_ranges(T), n_workers)
    train_groups = _split_groups(_chunk_ranges(len(train_idx)), n_workers)
    clim_path = zarr_path.with_name(zarr_path.name + ".clim.npy")
    t_start = time.time()

    def _log(msg: str) -> None:
        print(f"assemble [{time.time() - t_start:6.0f}s] {msg}", flush=True)

    _log(f"{n_workers} workers, {T} days in {len(_chunk_ranges(T))} chunks, {len(train_idx)} train days")
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        valid_surface = np.zeros((H, W), dtype=np.int64)
        valid_depth = np.zeros((D, H, W), dtype=np.int64)
        n_total = 0
        for vs, vd, n in pool.map(_worker_masks, repeat(spec), all_groups):
            valid_surface += vs
            valid_depth += vd
            n_total += n
        n_total = max(n_total, 1)
        wet = masks.fraction_mask(valid_surface / n_total)
        bottom = masks.fraction_mask(valid_depth / n_total)
        coast_dist = masks.coast_distance(wet.astype(bool))
        static = np.stack([wet.astype(np.float32), masks.bottom_depth_norm(bottom), coast_dist])
        _log(f"masks done, {int(wet.sum())} wet cells")

        accs = [climatology.init_accumulator(H * W) for _ in range(NX + D)]
        for part in pool.map(_worker_clim, repeat(spec), train_groups):
            for acc, contribution in zip(accs, part):
                for key in acc:
                    acc[key] += contribution[key]
        clim = np.empty((366, NX + D, H, W), dtype=np.float32)
        for c, acc in enumerate(accs):
            _, clim[:, c] = climatology.solve(acc, H, W)
        np.save(clim_path, clim)
        _log("climatology fitted")

        stats = [normalise.init_stats() for _ in range(NX + D)]
        for part in pool.map(_worker_stats, repeat(spec), train_groups, repeat(clim_path)):
            for st, contribution in zip(stats, part):
                for key in st:
                    st[key] += contribution[key]
        norm_stats = [normalise.solve_stats(st) for st in stats]
        norm = {v: {"mean": m, "std": s} for v, (m, s) in zip(X_VARS, norm_stats[:NX])}
        norm.update({f"y_depth_{int(DEPTHS_M[d])}": {"mean": m, "std": s} for d, (m, s) in enumerate(norm_stats[NX:])})
        _log("normalisation stats fitted")

        root = zarr_writer.create_store_custom(zarr_path, calendar.values, grid.lat, grid.lon, static, wet, bottom, norm, data_hash)
        zarr_writer.write_climatology(root, clim[:, :NX].astype(np.float16), clim[:, NX:].astype(np.float16))
        written = 0
        for ranges in pool.map(
            _worker_write, repeat(spec), all_groups, repeat(clim_path), repeat(zarr_path), repeat(norm_stats), repeat(wet), repeat(bottom), repeat(split_arr)
        ):
            written += sum(t1 - t0 for t0, t1 in ranges)
            _log(f"wrote {written}/{T} days")

    root.attrs["complete"] = True
    zarr_writer.finalize(zarr_path)
    clim_path.unlink(missing_ok=True)


def _decode_chars(raw) -> str:
    """Argo char arrays / byte strings -> a plain str."""
    if isinstance(raw, (bytes, np.bytes_)):
        return raw.decode("utf-8", "ignore").strip()
    if isinstance(raw, np.ndarray):
        return b"".join(x if isinstance(x, (bytes, np.bytes_)) else str(x).encode() for x in raw.ravel()).decode("utf-8", "ignore").strip()
    return str(raw).strip()


def _decode_qc(raw, n: int) -> list[str]:
    """Per-level QC flags, one per pressure level: never stripped (a blank flag is fill), padded with 9 (missing)."""
    if isinstance(raw, np.ndarray):
        text = "".join(x.decode("utf-8", "ignore") if isinstance(x, (bytes, np.bytes_)) else str(x) for x in raw.ravel())
    elif isinstance(raw, (bytes, np.bytes_)):
        text = raw.decode("utf-8", "ignore")
    else:
        text = str(raw)
    flags = list(text[:n])
    return flags + ["9"] * (n - len(flags))


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
        temp_qc = _decode_qc(ds["TEMP_QC"].values[0], n) if "TEMP_QC" in ds else ["9"] * n
        temp_adj_qc = _decode_qc(ds["TEMP_ADJUSTED_QC"].values[0], n) if "TEMP_ADJUSTED_QC" in ds else ["9"] * n
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
    with ProcessPoolExecutor(max_workers=_assembly_workers(None)) as pool:
        profiles = [p for p in pool.map(_read_argo_profile, paths, chunksize=64) if p is not None]
    df = argo_matchups.build_matchups(profiles, grid)
    df.to_parquet(out_path)


def assemble_real(
    data_dir: str | Path,
    products: list[str],
    year0: int,
    year1: int,
    grid: Grid = DEFAULT_GRID,
    download_workers: int | None = None,
    assemble_workers: int | None = None,
) -> Path:
    """Download, regrid, align, mask, target, split, climatology, normalise, write zarr, then Argo matchups."""
    data_dir = Path(data_dir)
    raw_dir, interim_dir = data_dir / "raw", data_dir / "interim"
    raw_dir.mkdir(parents=True, exist_ok=True)
    interim_dir.mkdir(parents=True, exist_ok=True)

    workers = len(products) if download_workers is None else download_workers
    _check_credentials(products)
    _download_and_regrid(products, year0, year1, raw_dir, interim_dir, grid, workers)

    zarr_path = data_dir / "poseidon.zarr"
    data_hash = hashlib.sha256(f"{sorted(products)}:{year0}:{year1}:{len(grid.lat)}x{len(grid.lon)}".encode()).hexdigest()
    if _assembly_done(zarr_path, data_hash):
        print(f"assembly already complete: {zarr_path}")
    else:
        _assemble(interim_dir, zarr_path, products, year0, year1, grid, data_hash, workers=assemble_workers)

    argo_path = data_dir / "argo_matchups.parquet"
    if argo_path.exists():
        print(f"argo matchups already complete: {argo_path}")
    else:
        _build_argo_matchups(raw_dir, year0, year1, grid, argo_path)
    return zarr_path


def run_real(args: argparse.Namespace) -> None:
    year0, year1 = _parse_years(args.years)
    products = args.products or list(PRODUCTS)
    assemble_real(args.data_dir, products, year0, year1, download_workers=args.workers, assemble_workers=args.assemble_workers)
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
    parser.add_argument("--workers", type=int, default=None, help="parallel download workers; default = number of products, 1 = sequential")
    parser.add_argument("--assemble-workers", type=int, default=None, help="assembly worker processes; default = all cores but three")
    args = parser.parse_args()

    if args.synthetic:
        run_synthetic(args)
    else:
        run_real(args)


if __name__ == "__main__":
    main()
