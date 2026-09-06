"""No-network synthetic dataset generator, schema-identical to the real pipeline output.

Exercises split.py / climatology.py / normalise.py / zarr_writer.py exactly as the real run does,
so the synthetic path is a real test of those stages, not a stand-in. Everything time-shaped is
streamed in ZARR_TIME_CHUNK-day chunks through a scratch zarr store so peak memory stays flat
regardless of how many days are requested.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import zarr
from scipy.ndimage import gaussian_filter

from pipeline import climatology, masks, normalise, zarr_writer
from pipeline.argo_matchups import DEPTHS_M, build_matchup_row
from pipeline.sources import (
    GRID_LAT_MIN,
    GRID_LON_MIN,
    GRID_STEP_DEG,
    SPLIT_TRAIN,
    X_MASK_VARS,
    X_VARS,
    ZARR_TIME_CHUNK,
    Grid,
)
from pipeline.split import split_codes

AR1_PHI = 0.9  # AR(1) persistence of the daily anomaly field
SPATIAL_SMOOTH_SIGMA = 1.5  # cells, low-pass on the raw noise before the AR(1) recursion
ANOMALY_DEPTH_DECAY_M = 200.0
SURFACE_SEASONAL_AMP_C = 2.0
THERMOCLINE_CENTER_M = 100.0
THERMOCLINE_WIDTH_M = 30.0
SURFACE_TEMP_EQUATOR_C = 29.0
DEEP_TEMP_C = 4.0
LAT_COOLING_PER_DEG = 0.12
COAST_MIN_DEPTH_M = 30.0
OFFSHORE_MAX_DEPTH_M = 4000.0
MISSING_DAY_PROB = 0.03
ARGO_SAMPLE_NOISE_C = 0.2
N_ARGO_SAMPLES_PER_YEAR = 200

VAR_TO_MASK_IDX = {"sst": 0, "sss": 1, "sla": 2, "cur_u": 3, "cur_v": 3, "wnd_u": 4, "wnd_v": 4}


def _grid(ny: int, nx: int) -> tuple[np.ndarray, np.ndarray]:
    lat = GRID_LAT_MIN + GRID_STEP_DEG / 2 + np.arange(ny) * GRID_STEP_DEG
    lon = GRID_LON_MIN + GRID_STEP_DEG / 2 + np.arange(nx) * GRID_STEP_DEG
    return lat.astype(np.float32), lon.astype(np.float32)


def _land_mask(ny: int, nx: int) -> np.ndarray:
    """1 = ocean. A coastline strip on the west edge plus one island."""
    wet = np.ones((ny, nx), dtype=bool)
    coast_width = max(1, nx // 12)
    wet[:, :coast_width] = False
    isl_i, isl_j = ny // 2, nx // 2
    isl_r = max(1, min(ny, nx) // 10)
    ii, jj = np.mgrid[0:ny, 0:nx]
    wet[(ii - isl_i) ** 2 + (jj - isl_j) ** 2 <= isl_r**2] = False
    return wet


def _seafloor_depth(ny: int, nx: int, wet: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Sloping seafloor: shallow near the west coast, deep offshore, with mild noise."""
    j = np.arange(nx)
    slope = COAST_MIN_DEPTH_M + (OFFSHORE_MAX_DEPTH_M - COAST_MIN_DEPTH_M) * (j / max(nx - 1, 1))
    depth = np.tile(slope, (ny, 1)).astype(np.float64)
    depth *= 1.0 + rng.normal(0, 0.05, depth.shape)
    depth = np.clip(depth, COAST_MIN_DEPTH_M, OFFSHORE_MAX_DEPTH_M)
    depth[~wet] = 0.0
    return depth


def _mean_temp_profile(lat: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """(H, D): latitude-dependent surface warmth with a logistic thermocline."""
    surface = SURFACE_TEMP_EQUATOR_C - LAT_COOLING_PER_DEG * np.abs(lat - lat.mean())
    shape = 1.0 / (1.0 + np.exp((depth[None, :] - THERMOCLINE_CENTER_M) / THERMOCLINE_WIDTH_M))
    return DEEP_TEMP_C + (surface[:, None] - DEEP_TEMP_C) * shape


def _ar1_chunks(T: int, ny: int, nx: int, ar1_seed, std: float | None = None):
    """Yield (t0, t1, anomaly_chunk) sequentially from a dedicated, replayable RNG stream.

    Rerunning with the same ar1_seed reproduces the same raw sequence, so the global std
    needed to rescale the field can be computed on a first, storage-free pass and applied on a second.
    """
    rng = np.random.default_rng(ar1_seed)
    prev = gaussian_filter(rng.normal(0, 1, (ny, nx)), SPATIAL_SMOOTH_SIGMA)
    t = 0
    while t < T:
        t1 = min(t + ZARR_TIME_CHUNK, T)
        chunk = np.empty((t1 - t, ny, nx), dtype=np.float64)
        for i in range(t1 - t):
            eta = gaussian_filter(rng.normal(0, 1, (ny, nx)), SPATIAL_SMOOTH_SIGMA)
            prev = AR1_PHI * prev + np.sqrt(1 - AR1_PHI**2) * eta
            chunk[i] = prev
        yield t, t1, (chunk if std is None else chunk / std)
        t = t1


def _ar1_std(T: int, ny: int, nx: int, ar1_seed) -> float:
    """Population std of the whole AR(1) record, from running sums over the chunked pass."""
    n, s, ss = 0, 0.0, 0.0
    for _, _, chunk in _ar1_chunks(T, ny, nx, ar1_seed):
        n += chunk.size
        s += chunk.sum()
        ss += np.square(chunk).sum()
    mean = s / n
    return float(np.sqrt(max(ss / n - mean**2, 0.0)) + 1e-9)


def _create_scratch(path: Path, T: int, ny: int, nx: int) -> zarr.Group:
    """Unnormalised x/y_raw/x_mask/split for one generation run; deleted once the real store is done."""
    root = zarr.open_group(str(path), mode="w")
    tchunk = min(ZARR_TIME_CHUNK, T)
    # chunked one channel/depth at a time: avoids decompressing every channel to read just one
    root.create_dataset("x_raw", shape=(T, len(X_VARS), ny, nx), dtype="float32",
                         chunks=(tchunk, 1, ny, nx), fill_value=np.nan)
    root.create_dataset("x_mask", shape=(T, len(X_MASK_VARS), ny, nx), dtype="uint8",
                         chunks=(tchunk, len(X_MASK_VARS), ny, nx), fill_value=0)
    root.create_dataset("y_raw", shape=(T, len(DEPTHS_M), ny, nx), dtype="float32",
                         chunks=(tchunk, 1, ny, nx), fill_value=np.nan)
    root.create_dataset("split", shape=(T,), dtype="uint8", chunks=(tchunk,), fill_value=255)
    return root


def _stream_fit(get_chunk, doy: np.ndarray, train_bool: np.ndarray, T: int, H: int, W: int) -> tuple[np.ndarray, float, float]:
    """One channel's climatology and anomaly mean/std, streamed over the train-day span of the scratch store."""
    train_days = np.where(train_bool)[0]
    lo, hi = (int(train_days.min()), int(train_days.max()) + 1) if train_days.size else (0, 0)

    acc = climatology.init_accumulator(H * W)
    for t0 in range(lo, hi, ZARR_TIME_CHUNK):
        t1 = min(t0 + ZARR_TIME_CHUNK, hi)
        vals = get_chunk(t0, t1)
        mask = np.isfinite(vals) & train_bool[t0:t1, None, None]
        climatology.accumulate(acc, vals, mask, doy[t0:t1])
    _, clim = climatology.solve(acc, H, W)

    stats = normalise.init_stats()
    for t0 in range(lo, hi, ZARR_TIME_CHUNK):
        t1 = min(t0 + ZARR_TIME_CHUNK, hi)
        vals = get_chunk(t0, t1)
        anom = vals - clim[(doy[t0:t1] - 1) % 366]
        mask = np.isfinite(vals) & np.isfinite(anom) & train_bool[t0:t1, None, None]
        normalise.accumulate_stats(stats, anom, mask)
    mean, std = normalise.solve_stats(stats)
    return clim.astype(np.float16), mean, std


def generate(out_dir: str | Path, start: str, end: str, ny: int, nx: int, seed: int = 0) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    ar1_seed = np.random.SeedSequence(seed).spawn(1)[0]

    time = pd.date_range(start, end, freq="D")
    T = len(time)
    doy = np.asarray(time.dayofyear)
    lat, lon = _grid(ny, nx)
    wet = _land_mask(ny, nx)
    depth_bottom = _seafloor_depth(ny, nx, wet, rng)
    bottom = (DEPTHS_M[:, None, None] <= depth_bottom[None, :, :]) & wet[None, :, :]
    bottom = bottom.astype(np.uint8)

    depth_decay = np.exp(-DEPTHS_M / ANOMALY_DEPTH_DECAY_M).astype(np.float32)
    mean_profile = _mean_temp_profile(lat, DEPTHS_M)  # (H, D)
    seasonal = SURFACE_SEASONAL_AMP_C * np.cos(2 * np.pi * (doy - 15) / 365.25)  # peaks in Jan
    monsoon_u = np.sin(2 * np.pi * (doy - 150) / 365.25)
    monsoon_v = np.cos(2 * np.pi * doy / 365.25)

    split = split_codes(pd.DatetimeIndex(time))
    train_bool = split == SPLIT_TRAIN

    coast_dist = masks.coast_distance(wet)
    static = np.stack(
        [wet.astype(np.float32), (depth_bottom / OFFSHORE_MAX_DEPTH_M).astype(np.float32), coast_dist], axis=0
    )

    scratch_path = out_dir / "_synthetic_scratch.zarr"
    scratch = _create_scratch(scratch_path, T, ny, nx)
    ar1_std = _ar1_std(T, ny, nx, ar1_seed)

    try:
        # pass 0: generate the raw fields sequentially, one AR(1) chunk at a time, into the scratch store
        for t0, t1, anomaly in _ar1_chunks(T, ny, nx, ar1_seed, std=ar1_std):
            anomaly = anomaly.astype(np.float32, copy=False)  # halves every downstream per-chunk temporary
            Tc = t1 - t0
            y_raw_c = np.empty((Tc, len(DEPTHS_M), ny, nx), dtype=np.float32)
            for d in range(len(DEPTHS_M)):
                base = mean_profile[:, d][None, :, None]
                seasonal_d = seasonal[t0:t1, None, None] * depth_decay[d]
                anom_d = anomaly * depth_decay[d] * 1.5
                y_raw_c[:, d] = base + seasonal_d + anom_d
                y_raw_c[:, d][:, bottom[d] == 0] = np.nan  # covers land too: bottom already requires wet

            def noise(sigma: float) -> np.ndarray:
                return rng.normal(0, sigma, (Tc, ny, nx)).astype(np.float32)

            sst = y_raw_c[:, 0].copy()
            sss = 35.0 + 0.6 * anomaly + noise(0.05)
            sla = 0.05 * anomaly + noise(0.01)
            wnd_u = (4.0 * monsoon_u[t0:t1, None, None] * np.ones((1, ny, nx), dtype=np.float32) + noise(0.5)).astype(np.float32)
            wnd_v = (2.0 * monsoon_v[t0:t1, None, None] * np.ones((1, ny, nx), dtype=np.float32) + noise(0.5)).astype(np.float32)
            grad_lon = (np.gradient(sla, axis=2) / GRID_STEP_DEG).astype(np.float32)
            grad_lat = (np.gradient(sla, axis=1) / GRID_STEP_DEG).astype(np.float32)
            cur_u = -grad_lat * 5.0 + noise(0.02)
            cur_v = grad_lon * 5.0 + noise(0.02)

            x_raw = {"sst": sst, "sss": sss, "sla": sla, "cur_u": cur_u, "cur_v": cur_v, "wnd_u": wnd_u, "wnd_v": wnd_v}
            for arr in x_raw.values():
                arr[:, ~wet] = np.nan

            x_mask_raw = np.ones((Tc, len(X_MASK_VARS), ny, nx), dtype=np.uint8)
            for m in range(len(X_MASK_VARS)):
                missing_days = rng.random(Tc) < MISSING_DAY_PROB
                x_mask_raw[missing_days, m] = 0
            x_mask_c = masks.modality_masks(x_mask_raw, wet.astype(np.uint8))

            x_stack = np.stack([x_raw[v] for v in X_VARS], axis=1)
            for k, v in enumerate(X_VARS):
                gone = x_mask_c[:, VAR_TO_MASK_IDX[v]] == 0
                x_stack[:, k][gone] = np.nan

            scratch["x_raw"][t0:t1] = x_stack
            scratch["x_mask"][t0:t1] = x_mask_c
            scratch["y_raw"][t0:t1] = y_raw_c
            scratch["split"][t0:t1] = split[t0:t1]

        # pass 1: streaming climatology + normalisation stats over the scratch store, train days only
        H, W = ny, nx
        clim_x = np.empty((366, len(X_VARS), H, W), dtype=np.float16)
        norm: dict[str, dict] = {}
        for k, v in enumerate(X_VARS):
            clim_x[:, k], mean, std = _stream_fit(lambda t0, t1, k=k: scratch["x_raw"][t0:t1, k], doy, train_bool, T, H, W)
            norm[v] = {"mean": mean, "std": std}

        clim_y = np.empty((366, len(DEPTHS_M), H, W), dtype=np.float16)
        for d in range(len(DEPTHS_M)):
            clim_y[:, d], mean, std = _stream_fit(lambda t0, t1, d=d: scratch["y_raw"][t0:t1, d], doy, train_bool, T, H, W)
            norm[f"y_depth_{int(DEPTHS_M[d])}"] = {"mean": mean, "std": std}

        data_hash = hashlib.sha256(f"{seed}:{start}:{end}:{ny}:{nx}".encode()).hexdigest()
        root = zarr_writer.create_store_custom(
            out_dir / "poseidon.zarr", time.values, lat, lon, static, wet.astype(np.uint8), bottom, norm, data_hash
        )
        zarr_writer.write_climatology(root, clim_x, clim_y)

        # pass 2: apply climatology + normalisation and write the final chunks
        for t0 in range(0, T, ZARR_TIME_CHUNK):
            t1 = min(t0 + ZARR_TIME_CHUNK, T)
            doy_c = doy[t0:t1]
            x_stack_c = scratch["x_raw"][t0:t1]
            x_mask_c = scratch["x_mask"][t0:t1]
            y_raw_c = scratch["y_raw"][t0:t1]

            x_norm_c = np.empty((t1 - t0, len(X_VARS), H, W), dtype=np.float16)
            for k, v in enumerate(X_VARS):
                clim_full = clim_x[:, k][(doy_c - 1) % 366]
                mean, std = norm[v]["mean"], norm[v]["std"]
                x_norm_c[:, k] = normalise.apply_normalise(x_stack_c[:, k] - clim_full, mean, std)
            # store invariant (see zarr_writer.py header): x is 0, never NaN, wherever x_mask is 0
            for k, v in enumerate(X_VARS):
                x_norm_c[:, k][x_mask_c[:, VAR_TO_MASK_IDX[v]] == 0] = 0.0

            y_norm_c = np.empty((t1 - t0, len(DEPTHS_M), H, W), dtype=np.float16)
            for d in range(len(DEPTHS_M)):
                clim_full = clim_y[:, d][(doy_c - 1) % 366]
                mean, std = norm[f"y_depth_{int(DEPTHS_M[d])}"]["mean"], norm[f"y_depth_{int(DEPTHS_M[d])}"]["std"]
                y_norm_c[:, d] = normalise.apply_normalise(y_raw_c[:, d] - clim_full, mean, std)

            zarr_writer.write_time_chunk(root, t0, t1, x_norm_c, x_mask_c, y_norm_c, y_raw_c.astype(np.float16), split[t0:t1])

        zarr_writer.finalize(out_dir / "poseidon.zarr")
    finally:
        shutil.rmtree(scratch_path, ignore_errors=True)

    argo = _synthetic_argo_matchups(root, time, lat, lon, wet, rng)
    argo.to_parquet(out_dir / "argo_matchups.parquet")
    return out_dir / "poseidon.zarr"


def _synthetic_argo_matchups(root: zarr.Group, time, lat, lon, wet, rng) -> pd.DataFrame:
    """Fake profiles sampled at the standard depths, routed through the real QC/interp/matching path.

    Reads one y_raw day at a time from the store (grouped by date), never the whole record.
    """
    grid = Grid(lat, lon)
    ocean_cells = np.column_stack(np.where(wet))
    n_years = max(1, (time[-1] - time[0]).days // 365)
    n_samples = N_ARGO_SAMPLES_PER_YEAR * n_years

    t_idx = rng.integers(0, len(time), n_samples)
    cell_idx = rng.integers(0, len(ocean_cells), n_samples)
    noise = rng.normal(0, ARGO_SAMPLE_NOISE_C, (n_samples, len(DEPTHS_M)))

    rows = []
    last_t, day = None, None
    for k in np.argsort(t_idx):
        t = int(t_idx[k])
        if t != last_t:
            day = np.asarray(root["y_raw"][t], dtype=np.float64)
            last_t = t
        i, j = (int(v) for v in ocean_cells[cell_idx[k]])
        profile = day[:, i, j] + noise[k]
        valid = np.isfinite(profile)
        if not valid.any():
            continue
        pres = DEPTHS_M[valid].astype(np.float64)
        temp = profile[valid].astype(np.float64)
        qc = ["1"] * len(pres)
        row = build_matchup_row(
            date=pd.Timestamp(time[t]),
            wmo=900000 + (int(k) % 50),
            lat=float(lat[i]),
            lon=float(lon[j]),
            pres=pres,
            temp=temp,
            temp_adj=temp,
            temp_qc=qc,
            temp_adj_qc=qc,
            data_mode="D",
            grid=grid,
        )
        rows.append(row)
    return pd.DataFrame(rows)
