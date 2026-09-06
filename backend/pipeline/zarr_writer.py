"""Create and incrementally fill data/poseidon.zarr against the fixed schema table.

Invariant: `x` is 0 (never NaN) wherever `x_mask` is 0; `y` and `y_raw` are NaN on land and below the seafloor.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import zarr

from pipeline.sources import DEPTHS_M, GRID_LAT, GRID_LON, X_MASK_VARS, X_VARS, ZARR_TIME_CHUNK

H, W = len(GRID_LAT), len(GRID_LON)
D = len(DEPTHS_M)
NX, NXMASK = len(X_VARS), len(X_MASK_VARS)


def create_store_custom(
    path: str | Path,
    time_values: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    static: np.ndarray,
    wet: np.ndarray,
    bottom: np.ndarray,
    norm: dict,
    data_hash: str,
) -> zarr.Group:
    """Allocate every array at full size for an arbitrary grid; time arrays are written later in chunks."""
    root = zarr.open_group(str(path), mode="w")
    T = len(time_values)
    H, W = len(lat), len(lon)
    tchunk = (min(ZARR_TIME_CHUNK, T),)

    root.create_dataset("time", data=time_values.astype("datetime64[ns]"), chunks=tchunk)
    root.create_dataset("lat", data=np.asarray(lat, dtype="float32"), chunks=(H,))
    root.create_dataset("lon", data=np.asarray(lon, dtype="float32"), chunks=(W,))
    root.create_dataset("depth", data=DEPTHS_M.astype("float32"), chunks=(D,))

    root.create_dataset("x", shape=(T, NX, H, W), dtype="float16", chunks=(ZARR_TIME_CHUNK, NX, H, W), fill_value=np.nan)
    root.create_dataset("x_mask", shape=(T, NXMASK, H, W), dtype="uint8", chunks=(ZARR_TIME_CHUNK, NXMASK, H, W), fill_value=0)
    root.create_dataset("y", shape=(T, D, H, W), dtype="float16", chunks=(ZARR_TIME_CHUNK, D, H, W), fill_value=np.nan)
    root.create_dataset("y_raw", shape=(T, D, H, W), dtype="float16", chunks=(ZARR_TIME_CHUNK, D, H, W), fill_value=np.nan)
    root.create_dataset("split", shape=(T,), dtype="uint8", chunks=tchunk, fill_value=255)

    root.create_dataset("wet", data=wet.astype("uint8"), chunks=(H, W))
    root.create_dataset("bottom", data=bottom.astype("uint8"), chunks=(D, H, W))
    root.create_dataset("static", data=static.astype("float32"), chunks=(3, H, W))

    root.create_dataset("clim_x", shape=(366, NX, H, W), dtype="float16", chunks=(366, NX, H, W), fill_value=np.nan)
    root.create_dataset("clim_y", shape=(366, D, H, W), dtype="float16", chunks=(366, D, H, W), fill_value=np.nan)

    root.attrs["norm"] = json.dumps(norm)
    root.attrs["data_hash"] = data_hash
    root.attrs["x_vars"] = X_VARS
    root.attrs["x_mask_vars"] = X_MASK_VARS
    return root


def write_time_chunk(root: zarr.Group, t0: int, t1: int, x, x_mask, y, y_raw, split) -> None:
    root["x"][t0:t1] = x
    root["x_mask"][t0:t1] = x_mask
    root["y"][t0:t1] = y
    root["y_raw"][t0:t1] = y_raw
    root["split"][t0:t1] = split


def write_climatology(root: zarr.Group, clim_x: np.ndarray, clim_y: np.ndarray) -> None:
    root["clim_x"][:] = clim_x
    root["clim_y"][:] = clim_y


def finalize(path: str | Path) -> None:
    zarr.consolidate_metadata(str(path))
