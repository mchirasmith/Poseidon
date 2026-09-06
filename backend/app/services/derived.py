"""Derived vertical-profile quantities: isotherm depths and mixed-layer depth."""
from __future__ import annotations

import numpy as np

MLD_DELTA_C = 0.2
MLD_REF_DEPTH_M = 10.0


def _interp_crossing(depths: np.ndarray, temps: np.ndarray, iso: float) -> np.ndarray:
    """First depth (top-down) where temps crosses below iso, linearly interpolated."""
    depths = np.asarray(depths, dtype=np.float64)
    temps = np.asarray(temps, dtype=np.float64)
    shape = temps.shape[1:]
    flat = temps.reshape(temps.shape[0], -1)
    out = np.full(flat.shape[1], np.nan)

    below = flat < iso
    above_surface = flat[0] < iso
    for j in range(flat.shape[1]):
        if above_surface[j] or np.all(np.isnan(flat[:, j])):
            continue
        col = flat[:, j]
        crossed = below[:, j]
        idx = np.argmax(crossed) if crossed.any() else -1
        if idx <= 0:
            continue
        t0, t1 = col[idx - 1], col[idx]
        if np.isnan(t0) or np.isnan(t1):
            continue
        d0, d1 = depths[idx - 1], depths[idx]
        frac = (iso - t0) / (t1 - t0) if t1 != t0 else 0.0
        out[j] = d0 + frac * (d1 - d0)
    return out.reshape(shape) if shape else out.item()


def isotherm_depth(depths: np.ndarray, temps: np.ndarray, iso: float) -> np.ndarray:
    """Depth where the profile first crosses below `iso`, going down."""
    return _interp_crossing(depths, temps, iso)


def d20(depths: np.ndarray, temps: np.ndarray) -> np.ndarray:
    return isotherm_depth(depths, temps, 20.0)


def d26(depths: np.ndarray, temps: np.ndarray) -> np.ndarray:
    return isotherm_depth(depths, temps, 26.0)


def mld(depths: np.ndarray, temps: np.ndarray) -> np.ndarray:
    """Depth where T drops MLD_DELTA_C below the value at MLD_REF_DEPTH_M."""
    depths = np.asarray(depths, dtype=np.float64)
    temps = np.asarray(temps, dtype=np.float64)
    shape = temps.shape[1:]
    flat = temps.reshape(temps.shape[0], -1)
    out = np.full(flat.shape[1], np.nan)

    ref_idx = int(np.argmin(np.abs(depths - MLD_REF_DEPTH_M)))

    for j in range(flat.shape[1]):
        col = flat[:, j]
        if np.isnan(col[ref_idx]):
            continue
        ref_t = col[ref_idx]
        threshold = ref_t - MLD_DELTA_C
        found = None
        last_valid = (depths[ref_idx], ref_t)
        for i in range(ref_idx + 1, len(depths)):
            if np.isnan(col[i]):
                continue
            d0, t0 = last_valid
            d1, t1 = depths[i], col[i]
            if t1 <= threshold:
                frac = (threshold - t0) / (t1 - t0) if t1 != t0 else 0.0
                frac = min(1.0, max(0.0, frac))
                found = d0 + frac * (d1 - d0)
                break
            last_valid = (d1, t1)
        if found is not None:
            out[j] = found
    return out.reshape(shape) if shape else out.item()
