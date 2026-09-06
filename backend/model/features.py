"""24-column tabular feature table for one day, shared by gbm training and serving."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter

from model.dataset import Store
from pipeline.sources import GRID_STEP_DEG, X_MASK_VARS, X_VARS

FEATURE_COLUMNS = [
    *X_VARS,
    *[f"mask_{m}" for m in X_MASK_VARS],
    "nbr_mean_sla",
    "nbr_mean_sst",
    "sla_grad_mag",
    "sst_grad_mag",
    "wind_curl",
    "wind_speed",
    "lat",
    "lon",
    "sin_doy",
    "cos_doy",
    "water_depth",
    "coast_distance",
]


def _nanmean_3x3(a: np.ndarray) -> np.ndarray:
    valid = np.isfinite(a).astype(np.float32)
    filled = np.nan_to_num(a, nan=0.0).astype(np.float32)
    s = uniform_filter(filled, size=3, mode="nearest") * 9
    c = uniform_filter(valid, size=3, mode="nearest") * 9
    return np.where(c > 0, s / np.maximum(c, 1), np.nan)


def _grad_mag(a: np.ndarray) -> np.ndarray:
    filled = np.nan_to_num(a, nan=0.0)
    gy, gx = np.gradient(filled, GRID_STEP_DEG)
    return np.sqrt(gx**2 + gy**2)


def build_features(store: Store, t: int) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray]]:
    """(N_cells, 24) float32 feature table and (ii, jj) ocean-cell index for day t."""
    x, m = store.field_day(t)
    var_idx = {v: i for i, v in enumerate(X_VARS)}
    sla, sst = x[var_idx["sla"]], x[var_idx["sst"]]
    wnd_u, wnd_v = x[var_idx["wnd_u"]], x[var_idx["wnd_v"]]

    nbr_sla = _nanmean_3x3(sla)
    nbr_sst = _nanmean_3x3(sst)
    sla_grad = _grad_mag(sla)
    sst_grad = _grad_mag(sst)

    du_dy, _ = np.gradient(np.nan_to_num(wnd_u, nan=0.0), GRID_STEP_DEG)
    _, dv_dx = np.gradient(np.nan_to_num(wnd_v, nan=0.0), GRID_STEP_DEG)
    wind_curl = dv_dx - du_dy
    wind_speed = np.sqrt(np.nan_to_num(wnd_u, nan=0.0) ** 2 + np.nan_to_num(wnd_v, nan=0.0) ** 2)

    lat2d = np.broadcast_to(store.lat[:, None], (store.H, store.W)).astype(np.float32)
    lon2d = np.broadcast_to(store.lon[None, :], (store.H, store.W)).astype(np.float32)
    doy = float(store.doy[t]) if 0 <= t < store.T else 1.0
    sin_doy = np.full((store.H, store.W), np.sin(2 * np.pi * doy / 365.25), dtype=np.float32)
    cos_doy = np.full((store.H, store.W), np.cos(2 * np.pi * doy / 365.25), dtype=np.float32)
    water_depth = store.static[1]
    coast_distance = store.static[2]

    ii, jj = np.where(store.wet == 1)
    layers = [x[k] for k in range(x.shape[0])]
    layers += [m[k].astype(np.float32) for k in range(m.shape[0])]
    layers += [nbr_sla, nbr_sst, sla_grad, sst_grad, wind_curl, wind_speed]
    layers += [lat2d, lon2d, sin_doy, cos_doy, water_depth, coast_distance]

    cols = [np.nan_to_num(layer[ii, jj], nan=0.0).astype(np.float32) for layer in layers]
    feats = np.stack(cols, axis=1)
    return feats, (ii, jj)
