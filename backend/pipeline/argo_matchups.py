"""Argo profiles -> QC'd temperature at standard depths, matched to the nearest grid cell."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from pipeline.sources import (
    ARGO_ADJUSTED_MODES,
    ARGO_DEPTH_TOL_M,
    ARGO_GOOD_QC_FLAGS,
    DEFAULT_GRID,
    DEPTHS_M,
    Grid,
)

EARTH_RADIUS_KM = 6371.0


def select_good_temp(temp, temp_adjusted, temp_qc, adjusted_qc, data_mode: str) -> np.ndarray:
    """TEMP_ADJUSTED when the profile is adjusted/delayed-mode, else TEMP; keep QC flags 1 and 2."""
    use_adjusted = data_mode in ARGO_ADJUSTED_MODES
    values = np.array(temp_adjusted if use_adjusted else temp, dtype=np.float64)
    qc = np.asarray(adjusted_qc if use_adjusted else temp_qc)
    good = np.array([str(q) in ARGO_GOOD_QC_FLAGS for q in qc])
    return np.where(good, values, np.nan)


def interp_to_standard_depths(pres: np.ndarray, temp: np.ndarray) -> np.ndarray:
    """Linear interpolation to the 15 standard depths; NaN unless bracketed within ARGO_DEPTH_TOL_M."""
    pres = np.asarray(pres, dtype=np.float64)
    temp = np.asarray(temp, dtype=np.float64)
    valid = np.isfinite(pres) & np.isfinite(temp)
    pres, temp = pres[valid], temp[valid]
    out = np.full(len(DEPTHS_M), np.nan, dtype=np.float32)
    if pres.size < 2:
        return out
    order = np.argsort(pres)
    pres, temp = pres[order], temp[order]
    for i, d in enumerate(DEPTHS_M):
        below = pres[pres <= d]
        above = pres[pres >= d]
        if below.size == 0:
            # no bracket above: the shallowest sample stands in if it's close enough
            if above.size and (above.min() - d) <= ARGO_DEPTH_TOL_M:
                out[i] = temp[0]
            continue
        if above.size == 0:
            continue
        if (d - below.max()) > ARGO_DEPTH_TOL_M or (above.min() - d) > ARGO_DEPTH_TOL_M:
            continue
        out[i] = np.interp(d, pres, temp)
    return out


@lru_cache(maxsize=4)
def _tree_for(lat_key: tuple, lon_key: tuple) -> cKDTree:
    lon_grid, lat_grid = np.meshgrid(np.array(lon_key), np.array(lat_key))
    points = np.column_stack([lat_grid.ravel(), lon_grid.ravel()])
    return cKDTree(points)


def nearest_cell(lat: float, lon: float, grid: Grid = DEFAULT_GRID) -> tuple[int, int, float]:
    """Nearest grid cell (i, j) via a KD-tree over cell centres, plus great-circle distance in km."""
    tree = _tree_for(tuple(grid.lat), tuple(grid.lon))
    _, idx = tree.query([lat, lon])
    i = idx // len(grid.lon)
    j = idx % len(grid.lon)
    dist_km = _haversine_km(lat, lon, grid.lat[i], grid.lon[j])
    return int(i), int(j), dist_km


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return float(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a)))


def build_matchup_row(
    date, wmo, lat: float, lon: float, pres, temp, temp_adj, temp_qc, temp_adj_qc, data_mode: str, grid: Grid = DEFAULT_GRID
) -> dict:
    good = select_good_temp(temp, temp_adj, temp_qc, temp_adj_qc, data_mode)
    depths_t = interp_to_standard_depths(pres, good)
    i, j, dist_km = nearest_cell(lat, lon, grid)
    row = {
        "date": pd.Timestamp(date),
        "wmo": wmo,
        "lat": lat,
        "lon": lon,
        "cell_i": i,
        "cell_j": j,
        "dist_km": dist_km,
    }
    for d, t in zip(DEPTHS_M, depths_t):
        row[f"t_{int(d)}"] = t
    return row


def build_matchups(profiles: list[dict], grid: Grid = DEFAULT_GRID) -> pd.DataFrame:
    rows = [build_matchup_row(**p, grid=grid) for p in profiles]
    return pd.DataFrame(rows)
