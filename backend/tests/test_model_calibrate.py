"""fit_alpha coverage-matching behaviour, including the empty-mask edge case."""
import numpy as np

from model.calibrate import fit_alpha


def test_fit_alpha_empty_mask_returns_one():
    mean = np.zeros((5, 4, 4), dtype=np.float32)
    sigma = np.ones((5, 4, 4), dtype=np.float32)
    target = np.zeros((5, 4, 4), dtype=np.float32)
    mask = np.zeros((5, 4, 4), dtype=bool)
    assert fit_alpha(mean, sigma, target, mask) == 1.0


def test_fit_alpha_matches_nominal_coverage_on_well_calibrated_data():
    rng = np.random.default_rng(0)
    mean = np.zeros((200, 8, 8), dtype=np.float32)
    sigma = np.ones((200, 8, 8), dtype=np.float32)
    target = rng.normal(size=mean.shape).astype(np.float32)
    mask = np.ones(mean.shape, dtype=bool)
    alpha = fit_alpha(mean, sigma, target, mask)
    assert 0.5 < alpha < 2.0
