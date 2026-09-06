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


def skill_score(mse_model: float, mse_clim: float) -> float:
    if not mse_clim or np.isnan(mse_clim) or mse_clim == 0:
        return float("nan")
    return float(1.0 - mse_model / mse_clim)


def coverage(mean, sigma, true, mask, level: float) -> float:
    z = Z_QUANTILE[level]
    half = z * sigma
    inside = (true >= mean - half) & (true <= mean + half) & mask.astype(bool)
    denom = mask.astype(bool).sum()
    return float(inside.sum() / denom) if denom else float("nan")


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


def init_calibration_acc() -> dict:
    """Zeroed running NLL/CRPS/coverage/width sums for streaming Gaussian calibration over days."""
    return {"n": 0, "nll": 0.0, "crps": 0.0, "width90": 0.0, "coverage": {lvl: 0 for lvl in Z_QUANTILE}}


def accumulate_calibration(acc: dict, mean, sigma, true, mask) -> None:
    """Add one day's masked NLL/CRPS/coverage/width-90 contributions to the running sums, in place."""
    m = mask.astype(bool)
    if not m.any():
        return
    mm, s, t = mean[m], sigma[m], true[m]
    nll = 0.5 * np.log(2 * np.pi) + np.log(s) + 0.5 * ((t - mm) / s) ** 2
    z = (t - mm) / s
    crps = s * (z * (2 * _std_normal_cdf(z) - 1) + 2 * _std_normal_pdf(z) - INV_SQRT_PI)
    acc["n"] += int(mm.size)
    acc["nll"] += float(nll.sum())
    acc["crps"] += float(crps.sum())
    acc["width90"] += float(np.sum(2 * Z_QUANTILE[0.9] * s))
    for lvl, zq in Z_QUANTILE.items():
        half = zq * s
        acc["coverage"][lvl] += int(((t >= mm - half) & (t <= mm + half)).sum())


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


def init_sum_acc(shape) -> dict:
    """Zeroed running sums for RMSE/MAE/bias/Pearson r on raw and anomaly values, streamed over days."""
    keys = ("n", "sum_err", "sum_err2", "sum_abs_err", "sum_p", "sum_t", "sum_p2", "sum_t2", "sum_pt",
            "sum_pa", "sum_ta", "sum_pa2", "sum_ta2", "sum_pat")
    return {k: np.zeros(shape) for k in keys}


def accumulate_sums(acc: dict, pred, true, clim, mask, axis) -> None:
    """Add one day's masked pred/true/clim to the running sums, reducing over `axis`, in place."""
    m = mask.astype(bool)
    p = np.where(m, pred, 0.0).astype(np.float64)
    t = np.where(m, true, 0.0).astype(np.float64)
    c = np.where(m, clim, 0.0).astype(np.float64)
    err, pa, ta = p - t, p - c, t - c
    acc["n"] += m.sum(axis=axis)
    acc["sum_err"] += err.sum(axis=axis)
    acc["sum_err2"] += np.square(err).sum(axis=axis)
    acc["sum_abs_err"] += np.abs(err).sum(axis=axis)
    acc["sum_p"] += p.sum(axis=axis)
    acc["sum_t"] += t.sum(axis=axis)
    acc["sum_p2"] += np.square(p).sum(axis=axis)
    acc["sum_t2"] += np.square(t).sum(axis=axis)
    acc["sum_pt"] += (p * t).sum(axis=axis)
    acc["sum_pa"] += pa.sum(axis=axis)
    acc["sum_ta"] += ta.sum(axis=axis)
    acc["sum_pa2"] += np.square(pa).sum(axis=axis)
    acc["sum_ta2"] += np.square(ta).sum(axis=axis)
    acc["sum_pat"] += (pa * ta).sum(axis=axis)


def _safe_div(num, denom):
    out = np.full(np.shape(num), np.nan, dtype=np.float64)
    return np.divide(num, denom, out=out, where=np.asarray(denom) > 0)


def _pearson_from_sums(n, sp, st, sp2, st2, spt):
    num = n * spt - sp * st
    den = np.sqrt(np.clip(n * sp2 - sp**2, 0, None) * np.clip(n * st2 - st**2, 0, None))
    r = _safe_div(num, den)
    return np.where(n < 2, np.nan, r)


def rmse_from_sums(acc) -> np.ndarray:
    return np.sqrt(_safe_div(acc["sum_err2"], acc["n"]))


def mae_from_sums(acc) -> np.ndarray:
    return _safe_div(acc["sum_abs_err"], acc["n"])


def bias_from_sums(acc) -> np.ndarray:
    return _safe_div(acc["sum_err"], acc["n"])


def r_from_sums(acc) -> np.ndarray:
    return _pearson_from_sums(acc["n"], acc["sum_p"], acc["sum_t"], acc["sum_p2"], acc["sum_t2"], acc["sum_pt"])


def anomaly_correlation_from_sums(acc) -> np.ndarray:
    return _pearson_from_sums(acc["n"], acc["sum_pa"], acc["sum_ta"], acc["sum_pa2"], acc["sum_ta2"], acc["sum_pat"])


def skill_score_from_sums(acc_model: dict, acc_clim: dict) -> np.ndarray:
    mse_model = _safe_div(acc_model["sum_err2"], acc_model["n"])
    mse_clim = _safe_div(acc_clim["sum_err2"], acc_clim["n"])
    return np.where((mse_clim == 0) | np.isnan(mse_clim), np.nan, 1.0 - mse_model / mse_clim)


def init_sqerr_acc() -> dict:
    """Zeroed running (n, sum squared error) for a pooled RMSE, e.g. thermocline band or D20/D26/MLD."""
    return {"n": 0.0, "sum_err2": 0.0}


def accumulate_sqerr(acc: dict, pred, true, mask) -> None:
    """Add one day's masked pred/true squared error to the running pooled sums, in place."""
    m = mask.astype(bool)
    err = (pred[m] - true[m]).astype(np.float64)
    acc["n"] += err.size
    acc["sum_err2"] += float(np.square(err).sum())


def rmse_from_sqerr(acc: dict) -> float:
    return float(np.sqrt(acc["sum_err2"] / acc["n"])) if acc["n"] > 0 else float("nan")


def basin_mask(lon2d: np.ndarray, basin: str) -> np.ndarray:
    return lon2d < AS_LON_MAX_DEG if basin == "arabian_sea" else lon2d >= AS_LON_MAX_DEG


def season_of(month: int) -> str:
    for name, months in SEASON_MONTHS.items():
        if month in months:
            return name
    raise ValueError(f"unmapped month {month}")
