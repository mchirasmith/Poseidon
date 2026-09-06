"""Nearest Argo matchup to a query point, within the configured distance/time tolerance."""
from __future__ import annotations

from datetime import date as date_cls
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.sources import DEPTHS_M

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


class ArgoIndex:
    """Loads argo_matchups.parquet once; nearest() scans rows within the day tolerance."""

    def __init__(self, parquet_path: str | Path | None):
        self.df = pd.read_parquet(parquet_path) if parquet_path and Path(parquet_path).exists() else None
        self.depth_cols = [f"t_{int(d)}" for d in DEPTHS_M]
        if self.df is not None:
            self.df["_ord"] = pd.to_datetime(self.df["date"]).values.astype("datetime64[D]").astype(np.int64)

    def day_window(self, date: str, max_days: float) -> pd.DataFrame | None:
        """Matchup rows within `max_days` of `date`; filter once and reuse across many points."""
        if self.df is None or len(self.df) == 0:
            return None
        target_ord = np.datetime64(date_cls.fromisoformat(date), "D").astype(np.int64)
        window = self.df[np.abs(self.df["_ord"] - target_ord) <= max_days].copy()
        if window.empty:
            return None
        window["_target_ord"] = target_ord
        return window

    def nearest_in_window(self, window: pd.DataFrame | None, lat: float, lon: float, max_km: float) -> dict | None:
        if window is None:
            return None
        dist = _haversine_km(lat, lon, window["lat"].to_numpy(), window["lon"].to_numpy())
        idx = np.argmin(dist)
        if dist[idx] > max_km:
            return None
        row = window.iloc[idx]
        temps = [None if pd.isna(row[c]) else float(row[c]) for c in self.depth_cols]
        return {
            "wmo": str(row["wmo"]),
            "distance_km": float(dist[idx]),
            "day_offset": int(row["_ord"] - row["_target_ord"]),
            "depths_m": [float(d) for d in DEPTHS_M],
            "temp": temps,
        }

    def nearest(self, date: str, lat: float, lon: float, max_km: float, max_days: float) -> dict | None:
        return self.nearest_in_window(self.day_window(date, max_days), lat, lon, max_km)
