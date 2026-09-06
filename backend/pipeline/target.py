"""Interpolate GLORYS levels to the fifteen standard depths, linear in depth."""
from __future__ import annotations

import numpy as np

from pipeline.sources import DEPTHS_M, TARGET_SHALLOW_CLAMP_TOL_M


def to_standard_depths(profile: np.ndarray, source_depths: np.ndarray) -> np.ndarray:
    """(..., n_source) -> (..., 15), linear in depth.

    NaN below the deepest valid sample. A standard depth up to TARGET_SHALLOW_CLAMP_TOL_M
    shallower than the shallowest valid sample takes that sample's value instead of NaN.
    Assumes valid samples form a contiguous run from the shallowest source depth, true for
    QC'd ocean profiles (missing values only appear below the seafloor).
    """
    flat = profile.reshape(-1, profile.shape[-1]).astype(np.float64)
    n = flat.shape[0]
    order = np.argsort(source_depths)
    src = np.asarray(source_depths, dtype=np.float64)[order]
    vals = flat[:, order]

    valid = np.isfinite(vals)
    has_data = valid.any(axis=1)
    src_bc = np.broadcast_to(src, vals.shape)
    shallowest = np.where(has_data, np.min(np.where(valid, src_bc, np.inf), axis=1), np.nan)
    deepest = np.where(has_data, np.max(np.where(valid, src_bc, -np.inf), axis=1), np.nan)
    vals_filled = np.where(valid, vals, 0.0)

    d = DEPTHS_M.astype(np.float64)
    idx_right = np.clip(np.searchsorted(src, d, side="left"), 1, len(src) - 1)
    idx_left = idx_right - 1
    x0, x1 = src[idx_left], src[idx_right]
    y0, y1 = vals_filled[:, idx_left], vals_filled[:, idx_right]
    frac = np.where(x1 > x0, (d - x0) / (x1 - x0), 0.0)
    interpolated = y0 + frac * (y1 - y0)

    shallow_clamp = (d[None, :] < shallowest[:, None]) & (d[None, :] >= shallowest[:, None] - TARGET_SHALLOW_CLAMP_TOL_M)
    interpolated = np.where(shallow_clamp, vals_filled[:, :1], interpolated)

    too_shallow = d[None, :] < shallowest[:, None] - TARGET_SHALLOW_CLAMP_TOL_M
    too_deep = d[None, :] > deepest[:, None]
    out = np.where(too_shallow | too_deep | ~has_data[:, None], np.nan, interpolated).astype(np.float32)
    return out.reshape(*profile.shape[:-1], len(DEPTHS_M))
