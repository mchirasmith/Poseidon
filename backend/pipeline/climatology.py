"""Harmonic (annual + semi-annual) climatology fit on training days only, vectorised over cells."""
from __future__ import annotations

import numpy as np

from pipeline.sources import HARMONIC_ORDERS, HARMONIC_PERIOD_DAYS

N_COEFFS = 2 * HARMONIC_ORDERS + 1
MIN_TRAIN_POINTS = N_COEFFS
MONTHS_PER_YEAR = 12
RIDGE_EPS = 1e-3  # relative to each cell's normal-equation diagonal scale
RIDGE_ABS_FLOOR = 1e-8  # keeps AtA invertible for cells with zero training data
LAT_CHUNK = 20


def harmonic_design(doy: np.ndarray) -> np.ndarray:
    """Design matrix columns: 1, cos(2pi doy/T), sin(...), cos(4pi doy/T), sin(...)."""
    doy = np.asarray(doy, dtype=np.float64)
    cols = [np.ones_like(doy)]
    for k in range(1, HARMONIC_ORDERS + 1):
        angle = 2 * np.pi * k * doy / HARMONIC_PERIOD_DAYS
        cols.append(np.cos(angle))
        cols.append(np.sin(angle))
    return np.stack(cols, axis=1)


def fit_evaluate(values: np.ndarray, mask: np.ndarray, doy_train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit per-cell harmonic on (T, H, W) train data, return (coeffs (H,W,5), clim (366, H, W)).

    A cell is fit only if its valid train days span all 12 calendar months and meet
    MIN_TRAIN_POINTS; otherwise its coefficients and climatology are NaN.
    """
    T, H, W = values.shape
    A = harmonic_design(doy_train)
    doy_eval = np.arange(1, 367)
    A_eval = harmonic_design(doy_eval)

    month_bin = ((np.asarray(doy_train) - 1) * MONTHS_PER_YEAR // 366).astype(np.int64)
    month_onehot = np.zeros((T, MONTHS_PER_YEAR))
    month_onehot[np.arange(T), month_bin] = 1.0

    coeffs = np.full((H, W, N_COEFFS), np.nan, dtype=np.float64)
    clim = np.full((366, H, W), np.nan, dtype=np.float32)

    for lat0 in range(0, H, LAT_CHUNK):
        lat1 = min(lat0 + LAT_CHUNK, H)
        y = values[:, lat0:lat1, :].reshape(T, -1)
        m = mask[:, lat0:lat1, :].reshape(T, -1).astype(np.float64)
        y_filled = np.nan_to_num(y, nan=0.0)

        AtA = np.einsum("tc,ti,tj->cij", m, A, A)
        Atb = np.einsum("tc,ti->ci", m * y_filled, A)
        diag_scale = np.diagonal(AtA, axis1=1, axis2=2).mean(axis=1)
        ridge = RIDGE_EPS * diag_scale + RIDGE_ABS_FLOOR
        AtA += np.eye(N_COEFFS)[None, :, :] * ridge[:, None, None]

        c = np.linalg.solve(AtA, Atb)  # (c, 5)
        counts = m.sum(axis=0)
        month_counts = month_onehot.T @ m  # (12, c)
        full_coverage = (month_counts > 0).all(axis=0)
        c[(counts < MIN_TRAIN_POINTS) | ~full_coverage] = np.nan

        clim_chunk = A_eval @ c.T  # (366, c)
        n = lat1 - lat0
        coeffs[lat0:lat1, :, :] = c.reshape(n, W, N_COEFFS)
        clim[:, lat0:lat1, :] = clim_chunk.reshape(366, n, W)

    return coeffs.astype(np.float32), clim


def init_accumulator(n_cells: int) -> dict:
    """State for streaming the normal-equation sums fit_evaluate computes over a full (T, H, W) array."""
    return {
        "AtA": np.zeros((n_cells, N_COEFFS, N_COEFFS)),
        "Atb": np.zeros((n_cells, N_COEFFS)),
        "counts": np.zeros(n_cells),
        "month_counts": np.zeros((MONTHS_PER_YEAR, n_cells)),
    }


def accumulate(acc: dict, values: np.ndarray, mask: np.ndarray, doy_chunk: np.ndarray) -> None:
    """Add one (Tc, H, W) time chunk's contribution to the running normal-equation sums, in place."""
    Tc = len(doy_chunk)
    A = harmonic_design(doy_chunk)
    m = mask.reshape(Tc, -1).astype(np.float64)
    y = np.nan_to_num(values.reshape(Tc, -1), nan=0.0)
    acc["AtA"] += np.einsum("tc,ti,tj->cij", m, A, A)
    acc["Atb"] += np.einsum("tc,ti->ci", m * y, A)
    acc["counts"] += m.sum(axis=0)
    month_bin = ((np.asarray(doy_chunk) - 1) * MONTHS_PER_YEAR // 366).astype(np.int64)
    onehot = np.zeros((Tc, MONTHS_PER_YEAR))
    onehot[np.arange(Tc), month_bin] = 1.0
    acc["month_counts"] += onehot.T @ m


def solve(acc: dict, H: int, W: int) -> tuple[np.ndarray, np.ndarray]:
    """Ridge-solve the accumulated normal equations, same result as fit_evaluate on the full record."""
    AtA, Atb, counts, month_counts = acc["AtA"], acc["Atb"], acc["counts"], acc["month_counts"]
    diag_scale = np.diagonal(AtA, axis1=1, axis2=2).mean(axis=1)
    ridge = RIDGE_EPS * diag_scale + RIDGE_ABS_FLOOR
    AtA = AtA + np.eye(N_COEFFS)[None, :, :] * ridge[:, None, None]
    c = np.linalg.solve(AtA, Atb)
    full_coverage = (month_counts > 0).all(axis=0)
    c[(counts < MIN_TRAIN_POINTS) | ~full_coverage] = np.nan

    doy_eval = np.arange(1, 367)
    A_eval = harmonic_design(doy_eval)
    clim = (A_eval @ c.T).reshape(366, H, W)
    return c.reshape(H, W, N_COEFFS).astype(np.float32), clim.astype(np.float32)
