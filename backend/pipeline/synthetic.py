"""No-network synthetic dataset generator, schema-identical to the real pipeline output.

Exercises split.py / climatology.py / normalise.py / zarr_writer.py exactly as the real run does,
so the synthetic path is a real test of those stages, not a stand-in.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter

from pipeline import climatology, masks, normalise, zarr_writer
from pipeline.argo_matchups import DEPTHS_M, build_matchup_row
from pipeline.sources import GRID_LAT_MIN, GRID_LON_MIN, GRID_STEP_DEG, SPLIT_TRAIN, X_MASK_VARS, X_VARS, Grid
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


def _ar1_anomaly_field(T: int, ny: int, nx: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth, slowly-evolving anomaly: spatial low-pass noise driven through an AR(1) in time."""
    field = np.zeros((T, ny, nx), dtype=np.float64)
    prev = gaussian_filter(rng.normal(0, 1, (ny, nx)), SPATIAL_SMOOTH_SIGMA)
    for t in range(T):
        eta = gaussian_filter(rng.normal(0, 1, (ny, nx)), SPATIAL_SMOOTH_SIGMA)
        prev = AR1_PHI * prev + np.sqrt(1 - AR1_PHI**2) * eta
        field[t] = prev
    field /= field.std() + 1e-9
    return field


def _mean_temp_profile(lat: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """(H, D): latitude-dependent surface warmth with a logistic thermocline."""
    surface = SURFACE_TEMP_EQUATOR_C - LAT_COOLING_PER_DEG * np.abs(lat - lat.mean())
    shape = 1.0 / (1.0 + np.exp((depth[None, :] - THERMOCLINE_CENTER_M) / THERMOCLINE_WIDTH_M))
    return DEEP_TEMP_C + (surface[:, None] - DEEP_TEMP_C) * shape


def generate(out_dir: str | Path, start: str, end: str, ny: int, nx: int, seed: int = 0) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    time = pd.date_range(start, end, freq="D")
    T = len(time)
    doy = np.asarray(time.dayofyear)
    lat, lon = _grid(ny, nx)
    wet = _land_mask(ny, nx)
    depth_bottom = _seafloor_depth(ny, nx, wet, rng)
    bottom = (DEPTHS_M[:, None, None] <= depth_bottom[None, :, :]) & wet[None, :, :]
    bottom = bottom.astype(np.uint8)

    anomaly = _ar1_anomaly_field(T, ny, nx, rng)
    depth_decay = np.exp(-DEPTHS_M / ANOMALY_DEPTH_DECAY_M).astype(np.float32)

    mean_profile = _mean_temp_profile(lat, DEPTHS_M)  # (H, D)
    seasonal = SURFACE_SEASONAL_AMP_C * np.cos(2 * np.pi * (doy - 15) / 365.25)  # peaks in Jan

    y_raw = np.empty((T, len(DEPTHS_M), ny, nx), dtype=np.float32)
    for d in range(len(DEPTHS_M)):
        base = mean_profile[:, d][None, :, None]  # (1, H, 1)
        seasonal_d = (seasonal[:, None, None] * depth_decay[d])
        anom_d = anomaly * depth_decay[d] * 1.5
        y_raw[:, d] = base + seasonal_d + anom_d
    y_raw[:, :, ~wet] = np.nan
    y_raw = np.where(bottom[None, :, :, :] == 0, np.nan, y_raw).astype(np.float32)

    sst = y_raw[:, 0].copy()
    sss = 35.0 + 0.6 * anomaly + rng.normal(0, 0.05, (T, ny, nx))
    sla = 0.05 * anomaly + rng.normal(0, 0.01, (T, ny, nx))
    monsoon = np.sin(2 * np.pi * (doy - 150) / 365.25)
    wnd_u = 4.0 * monsoon[:, None, None] * np.ones((1, ny, nx)) + rng.normal(0, 0.5, (T, ny, nx))
    wnd_v = 2.0 * np.cos(2 * np.pi * doy / 365.25)[:, None, None] * np.ones((1, ny, nx)) + rng.normal(0, 0.5, (T, ny, nx))
    grad_lon = np.gradient(sla, axis=2) / GRID_STEP_DEG
    grad_lat = np.gradient(sla, axis=1) / GRID_STEP_DEG
    cur_u = -grad_lat * 5.0 + rng.normal(0, 0.02, (T, ny, nx))
    cur_v = grad_lon * 5.0 + rng.normal(0, 0.02, (T, ny, nx))

    x_raw = {"sst": sst, "sss": sss, "sla": sla, "cur_u": cur_u, "cur_v": cur_v, "wnd_u": wnd_u, "wnd_v": wnd_v}
    for arr in x_raw.values():
        arr[:, ~wet] = np.nan

    x_mask_raw = np.ones((T, len(X_MASK_VARS), ny, nx), dtype=np.uint8)
    for m, name in enumerate(X_MASK_VARS):
        missing_days = rng.random(T) < MISSING_DAY_PROB
        x_mask_raw[missing_days, m] = 0
    x_mask = masks.modality_masks(x_mask_raw, wet.astype(np.uint8))

    var_to_mask = {"sst": 0, "sss": 1, "sla": 2, "cur_u": 3, "cur_v": 3, "wnd_u": 4, "wnd_v": 4}
    x_stack = np.stack([x_raw[v] for v in X_VARS], axis=1)
    for k, v in enumerate(X_VARS):
        gone = x_mask[:, var_to_mask[v]] == 0
        x_stack[:, k][gone] = np.nan

    split = split_codes(pd.DatetimeIndex(time))
    train_idx = np.where(split == SPLIT_TRAIN)[0]
    train_doy = doy[train_idx]

    x_norm = np.empty((T, len(X_VARS), ny, nx), dtype=np.float16)
    clim_x = np.empty((366, len(X_VARS), ny, nx), dtype=np.float16)
    norm: dict[str, dict] = {}
    for k, v in enumerate(X_VARS):
        train_mask = np.isfinite(x_stack[train_idx, k]).astype(np.float64)
        _, clim = climatology.fit_evaluate(x_stack[train_idx, k], train_mask, train_doy)
        clim_full = clim[(doy - 1) % 366]
        anom = x_stack[:, k] - clim_full
        mask_all = np.isfinite(x_stack[:, k]).astype(np.float64)
        mean, std, normed = normalise.fit_normalise(anom, mask_all, train_idx)
        x_norm[:, k] = normed
        clim_x[:, k] = clim.astype(np.float16)
        norm[v] = {"mean": mean, "std": std}

    y_norm = np.empty((T, len(DEPTHS_M), ny, nx), dtype=np.float16)
    clim_y = np.empty((366, len(DEPTHS_M), ny, nx), dtype=np.float16)
    for d in range(len(DEPTHS_M)):
        train_mask = np.isfinite(y_raw[train_idx, d]).astype(np.float64)
        _, clim = climatology.fit_evaluate(y_raw[train_idx, d], train_mask, train_doy)
        clim_full = clim[(doy - 1) % 366]
        anom = y_raw[:, d] - clim_full
        mask_all = np.isfinite(y_raw[:, d]).astype(np.float64)
        mean, std, normed = normalise.fit_normalise(anom, mask_all, train_idx)
        y_norm[:, d] = normed
        clim_y[:, d] = clim.astype(np.float16)
        norm[f"y_depth_{int(DEPTHS_M[d])}"] = {"mean": mean, "std": std}

    coast_dist = masks.coast_distance(wet)
    static = np.stack(
        [wet.astype(np.float32), (depth_bottom / OFFSHORE_MAX_DEPTH_M).astype(np.float32), coast_dist], axis=0
    )

    # store invariant (see zarr_writer.py header): x is 0, never NaN, wherever x_mask is 0
    for k, v in enumerate(X_VARS):
        x_norm[:, k][x_mask[:, var_to_mask[v]] == 0] = 0.0

    data_hash = hashlib.sha256(f"{seed}:{start}:{end}:{ny}:{nx}".encode()).hexdigest()
    root = zarr_writer.create_store_custom(
        out_dir / "poseidon.zarr", time.values, lat, lon, static, wet.astype(np.uint8), bottom, norm, data_hash
    )
    zarr_writer.write_time_chunk(root, 0, T, x_norm, x_mask, y_norm, y_raw.astype(np.float16), split)
    zarr_writer.write_climatology(root, clim_x, clim_y)
    zarr_writer.finalize(out_dir / "poseidon.zarr")

    argo = _synthetic_argo_matchups(time, lat, lon, y_raw, wet, rng)
    argo.to_parquet(out_dir / "argo_matchups.parquet")
    return out_dir / "poseidon.zarr"


def _synthetic_argo_matchups(time, lat, lon, y_raw, wet, rng) -> pd.DataFrame:
    """Fake profiles sampled at the standard depths, routed through the real QC/interp/matching path."""
    ny, nx = wet.shape
    grid = Grid(lat, lon)
    ocean_cells = np.column_stack(np.where(wet))
    n_years = max(1, (time[-1] - time[0]).days // 365)
    n_samples = N_ARGO_SAMPLES_PER_YEAR * n_years
    rows = []
    for k in range(n_samples):
        t = rng.integers(0, len(time))
        cell = ocean_cells[rng.integers(0, len(ocean_cells))]
        i, j = int(cell[0]), int(cell[1])
        profile = y_raw[t, :, i, j] + rng.normal(0, ARGO_SAMPLE_NOISE_C, len(DEPTHS_M))
        valid = np.isfinite(profile)
        if not valid.any():
            continue
        pres = DEPTHS_M[valid].astype(np.float64)
        temp = profile[valid].astype(np.float64)
        qc = ["1"] * len(pres)
        row = build_matchup_row(
            date=pd.Timestamp(time[t]),
            wmo=900000 + (k % 50),
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
