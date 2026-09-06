"""Per-channel anomaly normalisation using training-day statistics only."""
from __future__ import annotations

import numpy as np

MIN_STD = 1e-6
CLIP_SIGMA = 10.0  # normalised anomalies are clipped to +/- this before the float16 cast, avoids inf


def fit_normalise(anomaly: np.ndarray, mask: np.ndarray, train_idx: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Mean/std of one channel's anomaly over train days, and the normalised float16 anomaly for all days."""
    train_vals = anomaly[train_idx][mask[train_idx] > 0]
    mean = float(np.nanmean(train_vals)) if train_vals.size else 0.0
    std = float(np.nanstd(train_vals)) if train_vals.size else 1.0
    std = max(std, MIN_STD)
    normed = np.clip((anomaly - mean) / std, -CLIP_SIGMA, CLIP_SIGMA).astype(np.float16)
    return mean, std, normed


def apply_normalise(anomaly: np.ndarray, mean: float, std: float) -> np.ndarray:
    """Apply already-fitted mean/std to a chunk of days, for the two-pass real pipeline."""
    return np.clip((anomaly - mean) / std, -CLIP_SIGMA, CLIP_SIGMA).astype(np.float16)


def init_stats() -> dict:
    """State for streaming mean/std as sufficient statistics (count, sum, sum of squares)."""
    return {"count": 0.0, "sum": 0.0, "sumsq": 0.0}


def accumulate_stats(stats: dict, anomaly: np.ndarray, mask: np.ndarray) -> None:
    """Add one chunk's valid anomaly values to the running sufficient statistics, in place."""
    vals = anomaly[mask > 0].astype(np.float64)
    stats["count"] += vals.size
    stats["sum"] += float(vals.sum())
    stats["sumsq"] += float(np.square(vals).sum())


def solve_stats(stats: dict) -> tuple[float, float]:
    """Mean/std from accumulated sufficient statistics."""
    if stats["count"] == 0:
        return 0.0, 1.0
    mean = stats["sum"] / stats["count"]
    var = max(stats["sumsq"] / stats["count"] - mean**2, 0.0)
    return mean, max(var**0.5, MIN_STD)
