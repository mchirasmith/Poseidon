"""24-column feature table shape, names and the NaN-aware neighbourhood mean."""
import numpy as np
import pytest

from model.dataset import Store
from model.features import FEATURE_COLUMNS, _nanmean_3x3, build_features


@pytest.fixture(scope="module")
def store(synthetic_store):
    return Store.open(synthetic_store / "poseidon.zarr")


def test_24_columns_with_expected_names(store):
    feats, (ii, jj) = build_features(store, 100)
    assert feats.shape == (len(ii), 24)
    assert len(FEATURE_COLUMNS) == 24
    assert feats.shape[1] == len(FEATURE_COLUMNS)


def test_rows_are_ocean_cells(store):
    _, (ii, jj) = build_features(store, 100)
    assert store.wet[ii, jj].all()


def test_features_are_finite(store):
    feats, _ = build_features(store, 100)
    assert np.isfinite(feats).all()


def test_nanmean_3x3_ignores_nan_neighbours():
    a = np.array(
        [
            [1.0, 1.0, 1.0],
            [1.0, np.nan, 1.0],
            [1.0, 1.0, 1.0],
        ]
    )
    out = _nanmean_3x3(a)
    assert out[1, 1] == pytest.approx(1.0)


def test_nanmean_3x3_all_nan_gives_nan():
    a = np.full((3, 3), np.nan)
    out = _nanmean_3x3(a)
    assert np.isnan(out[1, 1])
