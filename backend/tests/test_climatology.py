"""Harmonic climatology recovers a planted cycle from train days only; dev/test days don't influence it."""
import numpy as np

from pipeline.climatology import fit_evaluate, harmonic_design


def test_recovers_planted_cycle():
    rng = np.random.default_rng(0)
    T, H, W = 900, 3, 3
    doy = (np.arange(T) % 365) + 1
    true_c = np.array([22.0, 2.5, -1.5, 0.6, 0.3])
    base = harmonic_design(doy) @ true_c
    values = np.tile(base[:, None, None], (1, H, W)) + rng.normal(0, 0.05, (T, H, W))
    mask = np.ones((T, H, W))

    coeffs, clim = fit_evaluate(values, mask, doy)
    assert np.allclose(coeffs[1, 1], true_c, atol=0.05)
    assert clim.shape == (366, H, W)


def test_dev_test_days_do_not_influence_fit():
    """fit_evaluate must ignore masked-out days even when they're present in the arrays it's given."""
    import pandas as pd

    from pipeline.split import split_codes
    from pipeline.sources import SPLIT_TRAIN

    time = pd.date_range("2015-01-01", "2017-12-31")
    T, H, W = len(time), 2, 2
    doy = np.asarray(time.dayofyear)
    true_c = np.array([15.0, 1.0, 0.5, 0.1, -0.1])
    base = harmonic_design(doy) @ true_c
    values = np.tile(base[:, None, None], (1, H, W))

    codes = split_codes(pd.DatetimeIndex(time))
    train_mask = np.broadcast_to((codes == SPLIT_TRAIN).astype(np.float64)[:, None, None], (T, H, W))

    _, clim_a = fit_evaluate(values, train_mask, doy)

    perturbed = values.copy()
    perturbed[codes != SPLIT_TRAIN] += 1000.0  # only touch days the mask excludes
    _, clim_b = fit_evaluate(perturbed, train_mask, doy)

    assert np.allclose(clim_a, clim_b)
