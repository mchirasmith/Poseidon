"""D20/D26/MLD on hand-built profiles, including no-crossing edge cases."""
import numpy as np

from app.services import derived

DEPTHS = np.array([0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000], dtype=float)


def test_isotherm_crossing_interpolates():
    temps = np.full(DEPTHS.shape, 30.0)
    temps[DEPTHS >= 100] = 18.0
    temps[(DEPTHS >= 75) & (DEPTHS < 100)] = 24.0  # crosses 20 between 75 and 100
    d = derived.d20(DEPTHS, temps)
    assert 75 < d < 100


def test_no_crossing_is_nan():
    temps = np.full(DEPTHS.shape, 5.0)  # never reaches 20 C
    d = derived.d20(DEPTHS, temps)
    assert np.isnan(d)


def test_surface_colder_than_isotherm_is_nan():
    temps = np.full(DEPTHS.shape, 15.0)
    temps[0] = 10.0
    d = derived.d20(DEPTHS, temps)
    assert np.isnan(d)


def test_mld_threshold():
    temps = np.full(DEPTHS.shape, 28.0)
    ref = 28.0
    temps[DEPTHS == 30] = ref - 0.3  # first drop below 0.2 C threshold at 30 m
    m = derived.mld(DEPTHS, temps)
    assert 20 < m <= 30


def test_mld_no_drop_is_nan():
    temps = np.full(DEPTHS.shape, 28.0)
    m = derived.mld(DEPTHS, temps)
    assert np.isnan(m)


def test_mld_interpolates_across_nan_gap():
    temps = np.full(DEPTHS.shape, 28.0)
    temps[DEPTHS == 20] = np.nan  # gap right before the crossing
    temps[DEPTHS == 30] = 27.5  # crosses the 0.2 C threshold here
    m = derived.mld(DEPTHS, temps)
    assert 10 <= m <= 30


def test_vectorised_matches_scalar():
    rng = np.random.default_rng(0)
    profiles = 30 - 0.01 * DEPTHS[:, None] - rng.normal(0, 0.1, size=(len(DEPTHS), 4))
    vect = derived.d20(DEPTHS, profiles)
    for j in range(4):
        scalar = derived.d20(DEPTHS, profiles[:, j])
        assert np.isnan(scalar) == np.isnan(vect[j])
        if not np.isnan(scalar):
            assert abs(scalar - vect[j]) < 1e-9
