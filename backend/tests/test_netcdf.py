"""CF-1.10 variable/attribute coverage for app.services.netcdf.write."""
import numpy as np
from netCDF4 import Dataset

from app.services.netcdf import write

D, H, W = 3, 4, 5


def _arrays():
    lat = np.linspace(5.0, 10.0, H).astype(np.float32)
    lon = np.linspace(45.0, 50.0, W).astype(np.float32)
    depths = np.array([0.0, 10.0, 20.0], dtype=np.float32)
    wet = np.ones((H, W), dtype=np.uint8)
    wet[0, 0] = 0
    bottom = np.ones((D, H, W), dtype=np.uint8)
    bottom[2, 1, 1] = 0
    rng = np.random.default_rng(0)
    mean = rng.normal(20, 2, (D, H, W)).astype(np.float32)
    sigma = np.abs(rng.normal(0.5, 0.1, (D, H, W))).astype(np.float32)
    # the writer stores whatever it is given; masking land/below-seafloor is the caller's job
    mean[:, wet == 0] = np.nan
    sigma[:, wet == 0] = np.nan
    return lat, lon, depths, wet, bottom, mean, sigma


def test_lite_writes_all_variables(tmp_path):
    lat, lon, depths, wet, bottom, mean, sigma = _arrays()
    p10, p90 = mean - sigma, mean + sigma
    anomaly = mean - 20.0
    attrs = {
        "title": "t", "institution": "i", "model_name": "poseidon-lite",
        "calibration_alphas": "[1.0, 1.05, 1.2]", "data_hash": "deadbeef",
    }
    path = write(
        tmp_path / "out.nc", "2020-01-15", lat, lon, depths, wet, bottom,
        mean, sigma, p10, p90, anomaly,
        attrs=attrs,
    )
    with Dataset(path) as ds:
        ds.set_auto_mask(False)
        assert ds.Conventions == "CF-1.10"
        assert ds.title == "t"
        assert ds.calibration_alphas == attrs["calibration_alphas"]
        assert ds.data_hash == attrs["data_hash"]
        for name in ("thetao", "thetao_std", "thetao_p10", "thetao_p90", "thetao_anomaly", "prediction_status"):
            assert name in ds.variables
        assert ds["thetao"].dimensions == ("time", "depth", "latitude", "longitude")
        assert ds["thetao"].standard_name == "sea_water_potential_temperature"
        assert ds["thetao"]._FillValue is not None and np.isnan(ds["thetao"]._FillValue)
        assert np.isnan(ds["thetao"][0, :, 0, 0]).all()  # land cell
        assert ds["thetao"].filters()["zlib"] is True
        assert ds["thetao"].filters()["complevel"] == 4
        assert ds["thetao"].chunking() == [1, D, H, W]
        assert ds["prediction_status"].filters()["zlib"] is True
        assert ds["prediction_status"].chunking() == [D, H, W]
        status = ds["prediction_status"][:]
        assert status[0, 0, 0] == 1  # land
        assert status[2, 1, 1] == 2  # below seafloor
        assert list(ds["prediction_status"].flag_values) == [0, 1, 2]
        assert ds["depth"].positive == "down"
        assert ds["depth"].axis == "Z"
        assert ds["latitude"].standard_name == "latitude"


def test_gbm_omits_uncertainty_variables(tmp_path):
    lat, lon, depths, wet, bottom, mean, _sigma = _arrays()
    anomaly = mean - 20.0
    path = write(
        tmp_path / "gbm.nc", "2020-01-15", lat, lon, depths, wet, bottom,
        mean, None, None, None, anomaly, attrs={},
    )
    with Dataset(path) as ds:
        assert "thetao" in ds.variables
        for name in ("thetao_std", "thetao_p10", "thetao_p90"):
            assert name not in ds.variables
