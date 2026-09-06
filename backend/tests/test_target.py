"""Depth interpolation onto the standard depths; shallow clamp at 0 m; NaN below the seafloor."""
import numpy as np

from pipeline.sources import DEPTHS_M
from pipeline.target import to_standard_depths

# GLORYS-like native levels: shallowest sample is not at 0 m
SOURCE_DEPTHS = np.array([0.494, 5.078, 15.81, 29.44, 60.11, 100.5, 155.9, 208.7, 302.6, 500.9, 803.3, 1100.0])


def test_linear_interpolation_on_synthetic_profile():
    profile = 30.0 - 0.01 * SOURCE_DEPTHS
    out = to_standard_depths(profile[None, :], SOURCE_DEPTHS)[0]
    expected = 30.0 - 0.01 * DEPTHS_M
    within_grid = DEPTHS_M >= SOURCE_DEPTHS[0]
    assert np.allclose(out[within_grid], expected[within_grid], atol=1e-6)


def test_0m_clamps_to_shallowest_sample_within_tolerance():
    profile = 30.0 - 0.01 * SOURCE_DEPTHS
    out = to_standard_depths(profile[None, :], SOURCE_DEPTHS)[0]
    assert np.isclose(out[0], profile[0])  # DEPTHS_M[0] == 0, within 1 m of the 0.494 m sample


def test_nan_below_seafloor():
    source_depths = np.array([0.494, 25.0, 50.0, 100.0])  # seafloor at 100 m
    profile = 30.0 - 0.01 * source_depths
    out = to_standard_depths(profile[None, :], source_depths)[0]
    shallow = (DEPTHS_M <= 100.0) & (DEPTHS_M >= source_depths[0])
    assert np.isfinite(out[shallow]).all()
    assert np.isnan(out[DEPTHS_M > 100.0]).all()
