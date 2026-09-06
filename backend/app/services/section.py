"""Vertical section along the straight lat/lon line between two points."""
from __future__ import annotations

import numpy as np

from app.services import derived

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return float(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a)))


def nearest_cell(lat: float, lon: float, lat_axis: np.ndarray, lon_axis: np.ndarray) -> tuple[int, int]:
    j = int(np.argmin(np.abs(lat_axis - lat)))
    i = int(np.argmin(np.abs(lon_axis - lon)))
    return j, i


def _clean(values: np.ndarray) -> list[float | None]:
    return [None if np.isnan(v) else float(v) for v in values]


def build(
    a: tuple[float, float],
    b: tuple[float, float],
    n: int,
    lat_axis: np.ndarray,
    lon_axis: np.ndarray,
    depths_m: np.ndarray,
    mean: np.ndarray,
    sigma: np.ndarray | None,
    glorys: np.ndarray | None,
    argo_index,
    date: str,
    max_km: float,
    max_days: float,
) -> dict:
    """(mean, sigma, glorys) are each (15, H, W); returns the Section payload as a dict."""
    lats = np.linspace(a[0], b[0], n)
    lons = np.linspace(a[1], b[1], n)
    distances = [0.0]
    for k in range(1, n):
        distances.append(distances[-1] + _haversine_km(lats[k - 1], lons[k - 1], lats[k], lons[k]))

    poseidon, glorys_out, sigma_out, d20s, mlds = [], [], [], [], []
    argo_window = argo_index.day_window(date, max_days) if argo_index is not None else None
    closest_hit_by_wmo: dict[str, tuple[float, dict]] = {}
    for k in range(n):
        j, i = nearest_cell(float(lats[k]), float(lons[k]), lat_axis, lon_axis)
        prof_mean = mean[:, j, i]
        prof_sigma = sigma[:, j, i] if sigma is not None else np.full(len(depths_m), np.nan)
        prof_glorys = glorys[:, j, i] if glorys is not None else np.full(len(depths_m), np.nan)

        poseidon.append(_clean(prof_mean))
        glorys_out.append(_clean(prof_glorys))
        sigma_out.append(_clean(prof_sigma))
        d20 = derived.d20(depths_m, prof_mean)
        mld = derived.mld(depths_m, prof_mean)
        d20s.append(None if np.isnan(d20) else float(d20))
        mlds.append(None if np.isnan(mld) else float(mld))

        if argo_window is not None:
            m = argo_index.nearest_in_window(argo_window, float(lats[k]), float(lons[k]), max_km)
            if m is not None:
                prev = closest_hit_by_wmo.get(m["wmo"])
                if prev is None or m["distance_km"] < prev[0]:
                    closest_hit_by_wmo[m["wmo"]] = (m["distance_km"], {"distance_km": distances[k], "wmo": m["wmo"]})
    argo_markers = [marker for _, marker in closest_hit_by_wmo.values()]

    return {
        "distances_km": distances,
        "lats": lats.tolist(),
        "lons": lons.tolist(),
        "depths_m": [float(d) for d in depths_m],
        "poseidon": poseidon,
        "glorys": glorys_out,
        "sigma": sigma_out,
        "d20_m": d20s,
        "mld_m": mlds,
        "argo_markers": argo_markers,
    }
