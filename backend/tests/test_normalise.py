"""Normalisation statistics come from train days only; train anomalies land near mean 0, std 1."""
import numpy as np

from pipeline.normalise import fit_normalise


def test_stats_from_train_days_only():
    rng = np.random.default_rng(0)
    T = 500
    train_idx = np.arange(0, 400)
    anomaly = rng.normal(5.0, 2.0, T)
    anomaly[400:] = rng.normal(-50.0, 10.0, T - 400)  # dev/test look very different
    mask = np.ones(T)

    mean, std, normed = fit_normalise(anomaly, mask, train_idx)
    assert abs(mean - 5.0) < 0.5
    assert abs(std - 2.0) < 0.5


def test_train_anomaly_mean_zero_std_one():
    rng = np.random.default_rng(1)
    T = 2000
    train_idx = np.arange(T)
    anomaly = rng.normal(3.0, 1.5, T)
    mask = np.ones(T)

    mean, std, normed = fit_normalise(anomaly, mask, train_idx)
    normed32 = normed.astype(np.float32)
    assert abs(float(normed32.mean())) < 0.05
    assert abs(float(normed32.std()) - 1.0) < 0.05
