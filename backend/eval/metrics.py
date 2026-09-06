"""Metric primitives shared by the evaluation harness: error stats, skill, calibration, spectra."""
from __future__ import annotations

import math

import numpy as np
from scipy import fft as spfft

AS_LON_MAX_DEG = 77.5  # Arabian Sea: lon < this; Bay of Bengal: lon >= this
SEASON_MONTHS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJAS": (6, 7, 8, 9), "ON": (10, 11)}
Z_QUANTILE = {0.5: 0.6744897501960817, 0.8: 1.2815515655446004, 0.9: 1.6448536269514722, 0.95: 1.959963984540054}
POWER_WAVELEN_MIN_DEG, POWER_WAVELEN_MAX_DEG = 1.0, 3.0
POWER_MIN_GRID = 8
INV_SQRT_PI = 1.0 / math.sqrt(math.pi)


def _flat(*arrays, mask):
    m = mask.astype(bool)
    return tuple(a[m] for a in arrays)


def rmse(pred, true, mask) -> float:
    p, t = _flat(pred, true, mask=mask)
    return float(np.sqrt(np.mean((p - t) ** 2))) if p.size else float("nan")


def mae(pred, true, mask) -> float:
    p, t = _flat(pred, true, mask=mask)
    return float(np.mean(np.abs(p - t))) if p.size else float("nan")


def bias(pred, true, mask) -> float:
    p, t = _flat(pred, true, mask=mask)
    return float(np.mean(p - t)) if p.size else float("nan")


def pearson_r(pred, true, mask) -> float:
    p, t = _flat(pred, true, mask=mask)
    if p.size < 2 or np.std(p) == 0 or np.std(t) == 0:
        return float("nan")
    return float(np.corrcoef(p, t)[0, 1])


def anomaly_correlation(pred, true, clim, mask) -> float:
    return pearson_r(pred - clim, true - clim, mask)


def skill_score(mse_model: float, mse_clim: float) -> float:
    if not mse_clim or np.isnan(mse_clim) or mse_clim == 0:
        return float("nan")
    return float(1.0 - mse_model / mse_clim)


def vgrad_rmse(pred, true, mask, depth_axis: int = 0) -> float:
    """RMSE of adjacent-depth differences dT/dz, pooled over the depth axis."""
    d_pred = np.diff(pred, axis=depth_axis)
    d_true = np.diff(true, axis=depth_axis)
    pair_mask = np.take(mask, range(mask.shape[depth_axis] - 1), axis=depth_axis) & np.take(
        mask, range(1, mask.shape[depth_axis]), axis=depth_axis
    )
    return rmse(d_pred, d_true, pair_mask)


def coverage(mean, sigma, true, mask, level: float) -> float:
    z = Z_QUANTILE[level]
    half = z * sigma
    inside = (true >= mean - half) & (true <= mean + half) & mask.astype(bool)
    denom = mask.astype(bool).sum()
    return float(inside.sum() / denom) if denom else float("nan")


def mean_interval_width(sigma, mask, level: float = 0.9) -> float:
    z = Z_QUANTILE[level]
    s, = _flat(sigma, mask=mask)
    return float(np.mean(2 * z * s)) if s.size else float("nan")


def gaussian_nll(mean, sigma, true, mask) -> float:
    m, s, t = _flat(mean, sigma, true, mask=mask)
    if not m.size:
        return float("nan")
    nll = 0.5 * np.log(2 * np.pi) + np.log(s) + 0.5 * ((t - m) / s) ** 2
    return float(np.mean(nll))


def _std_normal_cdf(z):
    return 0.5 * (1.0 + np.vectorize(math.erf)(z / math.sqrt(2.0)))


def _std_normal_pdf(z):
    return np.exp(-0.5 * z**2) / math.sqrt(2 * math.pi)


def gaussian_crps(mean, sigma, true, mask) -> float:
    """Closed-form CRPS for a Gaussian predictive distribution, masked mean."""
    m, s, t = _flat(mean, sigma, true, mask=mask)
    if not m.size:
        return float("nan")
    z = (t - m) / s
    crps = s * (z * (2 * _std_normal_cdf(z) - 1) + 2 * _std_normal_pdf(z) - INV_SQRT_PI)
    return float(np.mean(crps))


def spatial_power_ratio(pred_field: np.ndarray, true_field: np.ndarray, lat_step_deg: float, lon_step_deg: float) -> float:
    """Ratio of predicted to true 2D FFT power summed over the 1-3 deg wavelength band; NaN if the grid is too small."""
    h, w = pred_field.shape
    if h < POWER_MIN_GRID or w < POWER_MIN_GRID:
        return float("nan")
    pred = np.nan_to_num(pred_field, nan=0.0)
    true = np.nan_to_num(true_field, nan=0.0)
    fy = spfft.fftfreq(h, d=lat_step_deg)
    fx = spfft.fftfreq(w, d=lon_step_deg)
    fmag = np.sqrt(fy[:, None] ** 2 + fx[None, :] ** 2)
    band = (fmag >= 1.0 / POWER_WAVELEN_MAX_DEG) & (fmag <= 1.0 / POWER_WAVELEN_MIN_DEG)
    if not band.any():
        return float("nan")
    pred_power = np.abs(spfft.fft2(pred)) ** 2
    true_power = np.abs(spfft.fft2(true)) ** 2
    denom = true_power[band].sum()
    return float(pred_power[band].sum() / denom) if denom > 0 else float("nan")


def basin_mask(lon2d: np.ndarray, basin: str) -> np.ndarray:
    return lon2d < AS_LON_MAX_DEG if basin == "arabian_sea" else lon2d >= AS_LON_MAX_DEG


def season_of(month: int) -> str:
    for name, months in SEASON_MONTHS.items():
        if month in months:
            return name
    raise ValueError(f"unmapped month {month}")
