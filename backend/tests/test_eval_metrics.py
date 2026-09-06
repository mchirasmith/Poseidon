"""Metric primitives on hand-built arrays with known values."""
import numpy as np
import pytest

from app.services.derived import d20
from eval import metrics as M


def test_rmse_mae_bias_known_values():
    pred = np.array([1.0, 2.0, 3.0, 4.0])
    true = np.array([1.0, 2.0, 3.0, 6.0])
    mask = np.ones(4, dtype=bool)
    assert M.rmse(pred, true, mask) == np.sqrt(4.0 / 4.0)
    assert M.mae(pred, true, mask) == 0.5
    assert M.bias(pred, true, mask) == -0.5


def test_pearson_r_perfect_correlation():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    mask = np.ones(4, dtype=bool)
    assert M.pearson_r(x, 2 * x + 1, mask) == pytest.approx(1.0)


def test_skill_score_edge_cases():
    assert M.skill_score(0.0, 1.0) == 1.0
    assert np.isnan(M.skill_score(1.0, 0.0))
    assert M.skill_score(2.0, 1.0) == -1.0


def test_coverage_of_known_gaussian():
    rng = np.random.default_rng(0)
    n = 200_000
    mean = np.zeros(n)
    sigma = np.ones(n)
    true = rng.normal(0, 1, n)
    mask = np.ones(n, dtype=bool)
    cov90 = M.coverage(mean, sigma, true, mask, 0.9)
    assert abs(cov90 - 0.9) < 0.01


def test_crps_matches_numeric_integral():
    mean, sigma, true = 0.0, 1.0, 0.5
    closed = M.gaussian_crps(np.array([mean]), np.array([sigma]), np.array([true]), np.array([True]))

    # numeric CRPS via integral of (F(y) - 1{y>=true})^2 over a wide grid
    from math import erf, sqrt

    grid = np.linspace(-10, 10, 200_001)
    cdf = 0.5 * (1 + np.vectorize(erf)((grid - mean) / (sigma * sqrt(2))))
    indicator = (grid >= true).astype(float)
    numeric = np.trapz((cdf - indicator) ** 2, grid)
    assert abs(closed - numeric) < 1e-3


def test_d20_rmse_zero_for_identical_fields():
    depths = np.array([0, 10, 20, 30, 50], dtype=np.float64)
    profile = np.array([28.0, 26.0, 24.0, 18.0, 12.0])
    field = np.broadcast_to(profile[:, None, None], (5, 3, 3)).copy()
    d20_a = d20(depths, field)
    d20_b = d20(depths, field)
    mask = np.isfinite(d20_a)
    assert M.rmse(d20_a, d20_b, mask) == 0.0


def test_spatial_power_ratio_identity_is_one():
    rng = np.random.default_rng(1)
    field = rng.normal(size=(16, 16))
    ratio = M.spatial_power_ratio(field, field, 0.25, 0.25)
    assert abs(ratio - 1.0) < 1e-9


def test_spatial_power_ratio_skipped_on_small_grid():
    field = np.zeros((4, 4))
    assert np.isnan(M.spatial_power_ratio(field, field, 0.25, 0.25))
