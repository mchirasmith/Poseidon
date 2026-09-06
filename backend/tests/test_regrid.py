"""Block mean of a finer field, coastal non-contamination, passthrough of an already-0.25deg grid."""
import numpy as np
import xarray as xr

from pipeline.regrid import to_grid


def _fine_field(factor: int, target_lat, target_lon, land_block=True):
    step = 0.25 / factor
    src_lat = np.round(
        np.concatenate([np.arange(t - 0.125, t + 0.125, step) + step / 2 for t in target_lat]), 5
    )
    src_lon = np.round(
        np.concatenate([np.arange(t - 0.125, t + 0.125, step) + step / 2 for t in target_lon]), 5
    )
    data = np.full((len(src_lat), len(src_lon)), 15.0)
    if land_block:
        data[:factor, :factor] = np.nan
    return xr.DataArray(data, dims=["lat", "lon"], coords={"lat": src_lat, "lon": src_lon})


def test_block_mean_reproduces_known_values_and_no_land_contamination():
    target_lat = np.array([10.125, 10.375])
    target_lon = np.array([50.125, 50.375])
    da = _fine_field(5, target_lat, target_lon)

    out = to_grid(da, 0.05, target_lat, target_lon)
    assert np.isnan(out.values[0, 0])  # fully-land cell
    assert np.isclose(out.values[0, 1], 15.0)  # neighbouring ocean cell untouched
    assert np.isclose(out.values[1, 0], 15.0)
    assert np.isclose(out.values[1, 1], 15.0)


def test_source_at_025_with_centre_offset_passes_through_unchanged():
    target_lat = np.array([10.125, 10.375, 10.625])
    target_lon = np.array([50.125, 50.375, 50.625])
    data = np.arange(9.0).reshape(3, 3)
    da = xr.DataArray(data, dims=["lat", "lon"], coords={"lat": target_lat, "lon": target_lon})

    out = to_grid(da, 0.25, target_lat, target_lon)
    assert np.allclose(out.values, data)


def test_lon_0_360_is_handled():
    # target sits west of the prime meridian; the source only makes sense once wrapped from 0..360
    target_lat = np.array([10.125, 10.375])
    target_lon = np.array([-109.875, -109.625])
    lon_360 = np.array([250.125, 250.375])
    lat = np.array([10.125, 10.375])
    data = np.array([[7.0, 8.0], [9.0, 10.0]])
    da = xr.DataArray(data, dims=["lat", "lon"], coords={"lat": lat, "lon": lon_360})
    out = to_grid(da, 0.25, target_lat, target_lon)
    assert np.allclose(out.values, data)
