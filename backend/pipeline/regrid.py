"""Regrid a source field onto the 0.25 deg target grid without mixing land into ocean cells."""
from __future__ import annotations

import numpy as np
import xarray as xr

from pipeline.sources import GRID_STEP_DEG, REGRID_MIN_VALID_FRACTION

_GRID_TOL = 1e-6


def _normalise_lon(da: xr.DataArray) -> xr.DataArray:
    """Wrap the longitude coordinate to -180..180 and sort both lat and lon ascending."""
    lon = ((da["lon"] + 180) % 360) - 180
    da = da.assign_coords(lon=lon)
    return da.sortby(["lat", "lon"])


def _cell_edges(centres: np.ndarray, step: float) -> np.ndarray:
    return np.concatenate([centres - step / 2, centres[-1:] + step / 2])


def _reduce_2d(da: xr.DataArray, lat_edges: np.ndarray, lon_edges: np.ndarray, target_lat, target_lon) -> xr.DataArray:
    """Sum over lon then lat bins, collapsing both source dims into the target grid."""
    out = da.groupby_bins("lon", lon_edges, labels=target_lon).sum("lon", skipna=True)
    out = out.groupby_bins("lat", lat_edges, labels=target_lat).sum("lat", skipna=True)
    return out.rename({"lat_bins": "lat", "lon_bins": "lon"})


def _block_mean(da: xr.DataArray, target_lat: np.ndarray, target_lon: np.ndarray) -> xr.DataArray:
    """NaN-aware block mean: a target cell needs REGRID_MIN_VALID_FRACTION of its source pixels valid."""
    lat_edges = _cell_edges(target_lat, GRID_STEP_DEG)
    lon_edges = _cell_edges(target_lon, GRID_STEP_DEG)
    valid = da.notnull()
    ones = xr.ones_like(da, dtype="float32")

    sums = _reduce_2d(da.fillna(0.0), lat_edges, lon_edges, target_lat, target_lon)
    counts = _reduce_2d(valid.astype("float32"), lat_edges, lon_edges, target_lat, target_lon)
    total = _reduce_2d(ones, lat_edges, lon_edges, target_lat, target_lon)

    mean = sums / counts.where(counts > 0)
    mean = mean.where(counts >= REGRID_MIN_VALID_FRACTION * total)
    return mean


def _passthrough_or_bilinear(da: xr.DataArray, target_lat: np.ndarray, target_lon: np.ndarray) -> xr.DataArray:
    lat0 = float(da["lat"].values[0])
    lon0 = float(da["lon"].values[0])
    aligned = (
        abs((lat0 - target_lat[0]) % GRID_STEP_DEG) < _GRID_TOL
        or abs((lat0 - target_lat[0]) % GRID_STEP_DEG - GRID_STEP_DEG) < _GRID_TOL
    ) and (
        abs((lon0 - target_lon[0]) % GRID_STEP_DEG) < _GRID_TOL
        or abs((lon0 - target_lon[0]) % GRID_STEP_DEG - GRID_STEP_DEG) < _GRID_TOL
    )
    if aligned:
        return da.sel(lat=target_lat, lon=target_lon, method="nearest", tolerance=_GRID_TOL * 10)
    return da.interp(lat=target_lat, lon=target_lon, method="linear")


def to_grid(
    da: xr.DataArray,
    source_step_deg: float,
    target_lat: np.ndarray,
    target_lon: np.ndarray,
) -> xr.DataArray:
    """Regrid onto the target lat/lon: masked block mean when finer, else passthrough/bilinear."""
    da = _normalise_lon(da)
    factor = GRID_STEP_DEG / source_step_deg
    if factor > 1.0 + 1e-6:
        return _block_mean(da, target_lat, target_lon)
    return _passthrough_or_bilinear(da, target_lat, target_lon)
