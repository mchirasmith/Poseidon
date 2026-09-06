"""CF-1.10 NetCDF-4 writer for one reconstructed day, per the technical spec's variable table."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from netCDF4 import Dataset

ZLIB_LEVEL = 4
STATUS_VALID, STATUS_LAND, STATUS_BELOW_SEAFLOOR = 0, 1, 2


def _prediction_status(wet: np.ndarray, bottom: np.ndarray) -> np.ndarray:
    """(D, H, W) uint8: 0 valid, 1 land, 2 below seafloor."""
    status = np.full(bottom.shape, STATUS_VALID, dtype=np.uint8)
    status[:, wet == 0] = STATUS_LAND
    status[(bottom == 0) & (wet[None] == 1)] = STATUS_BELOW_SEAFLOOR
    return status


def write(
    path: str | Path,
    date: str,
    lat: np.ndarray,
    lon: np.ndarray,
    depths_m: np.ndarray,
    wet: np.ndarray,
    bottom: np.ndarray,
    mean: np.ndarray,
    sigma: np.ndarray | None,
    p10: np.ndarray | None,
    p90: np.ndarray | None,
    anomaly: np.ndarray,
    attrs: dict,
) -> Path:
    """Writes thetao(+ std/p10/p90 if sigma given), thetao_anomaly and prediction_status."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    H, W = len(lat), len(lon)
    D = len(depths_m)
    chunks = (1, D, H, W)

    ds = Dataset(str(path), "w", format="NETCDF4")
    try:
        ds.createDimension("time", 1)
        ds.createDimension("depth", D)
        ds.createDimension("latitude", H)
        ds.createDimension("longitude", W)

        time_var = ds.createVariable("time", "f8", ("time",))
        time_var.standard_name = "time"
        time_var.units = "days since 1970-01-01"
        time_var.calendar = "gregorian"
        time_var[:] = [(np.datetime64(date, "D") - np.datetime64("1970-01-01", "D")).astype(np.int64)]

        depth_var = ds.createVariable("depth", "f4", ("depth",))
        depth_var.standard_name = "depth"
        depth_var.positive = "down"
        depth_var.units = "m"
        depth_var.axis = "Z"
        depth_var[:] = depths_m

        lat_var = ds.createVariable("latitude", "f4", ("latitude",))
        lat_var.standard_name = "latitude"
        lat_var.units = "degrees_north"
        lat_var.axis = "Y"
        lat_var[:] = lat

        lon_var = ds.createVariable("longitude", "f4", ("longitude",))
        lon_var.standard_name = "longitude"
        lon_var.units = "degrees_east"
        lon_var.axis = "X"
        lon_var[:] = lon

        def _field_var(name, long_name, values, units="degC", **extra):
            var = ds.createVariable(
                name, "f4", ("time", "depth", "latitude", "longitude"),
                zlib=True, complevel=ZLIB_LEVEL, chunksizes=chunks, fill_value=np.nan,
            )
            var.long_name = long_name
            var.units = units
            for k, v in extra.items():
                setattr(var, k, v)
            var[0] = values
            return var

        thetao = _field_var("thetao", "sea water potential temperature", mean)
        thetao.standard_name = "sea_water_potential_temperature"
        thetao.cell_methods = "time: mean"

        if sigma is not None:
            _field_var("thetao_std", "predictive standard deviation", sigma)
            _field_var("thetao_p10", "10th percentile predictive temperature", p10)
            _field_var("thetao_p90", "90th percentile predictive temperature", p90)

        _field_var("thetao_anomaly", "anomaly relative to 1993-2016 harmonic climatology", anomaly)

        status_var = ds.createVariable(
            "prediction_status", "u1", ("depth", "latitude", "longitude"),
            zlib=True, complevel=ZLIB_LEVEL, chunksizes=(D, H, W),
        )
        status_var.long_name = "prediction status"
        status_var.flag_values = np.array([STATUS_VALID, STATUS_LAND, STATUS_BELOW_SEAFLOOR], dtype=np.uint8)
        status_var.flag_meanings = "valid land below_seafloor"
        status_var[:] = _prediction_status(wet, bottom)

        ds.Conventions = "CF-1.10"
        for key, value in attrs.items():
            setattr(ds, key, value)
    finally:
        ds.close()
    return path
