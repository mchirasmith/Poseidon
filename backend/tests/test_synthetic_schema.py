"""The synthetic store conforms to the zarr schema table and the argo parquet columns."""
import json
from pathlib import Path

import numpy as np
import zarr

from pipeline.sources import DEPTHS_M, X_MASK_VARS, X_VARS

_VAR_TO_MASK = {"sst": "sst", "sss": "sss", "sla": "sla", "cur_u": "cur", "cur_v": "cur", "wnd_u": "wnd", "wnd_v": "wnd"}

EXPECTED_ARRAYS = {
    "time": ((None,), "datetime64[ns]"),
    "lat": ((None,), "float32"),
    "lon": ((None,), "float32"),
    "depth": ((15,), "float32"),
    "x": ((None, 7, None, None), "float16"),
    "x_mask": ((None, 5, None, None), "uint8"),
    "y": ((None, 15, None, None), "float16"),
    "y_raw": ((None, 15, None, None), "float16"),
    "wet": ((None, None), "uint8"),
    "bottom": ((15, None, None), "uint8"),
    "static": ((3, None, None), "float32"),
    "split": ((None,), "uint8"),
    "clim_x": ((366, 7, None, None), "float16"),
    "clim_y": ((366, 15, None, None), "float16"),
}


def _shape_matches(actual, expected) -> bool:
    return len(actual) == len(expected) and all(e is None or e == a for a, e in zip(actual, expected))


def test_arrays_present_with_expected_shape_and_dtype(synthetic_store: Path):
    g = zarr.open_consolidated(str(synthetic_store / "poseidon.zarr"))
    for name, (shape, dtype) in EXPECTED_ARRAYS.items():
        assert name in g, f"missing array {name}"
        assert _shape_matches(g[name].shape, shape), f"{name} shape {g[name].shape} != {shape}"
        assert str(g[name].dtype) == dtype, f"{name} dtype {g[name].dtype} != {dtype}"
    assert len(g["depth"]) == len(DEPTHS_M)


def test_time_chunking_is_32(synthetic_store: Path):
    g = zarr.open_consolidated(str(synthetic_store / "poseidon.zarr"))
    for name in ["x", "x_mask", "y", "y_raw", "split"]:
        assert g[name].chunks[0] == 32


def test_norm_and_data_hash_attrs(synthetic_store: Path):
    g = zarr.open_consolidated(str(synthetic_store / "poseidon.zarr"))
    norm = json.loads(g.attrs["norm"])
    assert "sst" in norm and "mean" in norm["sst"] and "std" in norm["sst"]
    assert isinstance(g.attrs["data_hash"], str) and len(g.attrs["data_hash"]) == 64


def test_x_is_finite_and_zero_where_masked(synthetic_store: Path):
    g = zarr.open_consolidated(str(synthetic_store / "poseidon.zarr"))
    x = g["x"][:].astype(np.float32)
    x_mask = g["x_mask"][:]
    assert np.isfinite(x).all()
    for k, v in enumerate(X_VARS):
        m = X_MASK_VARS.index(_VAR_TO_MASK[v])
        assert (x[:, k][x_mask[:, m] == 0] == 0.0).all()


def test_split_contains_purged_days(synthetic_store: Path):
    g = zarr.open_consolidated(str(synthetic_store / "poseidon.zarr"))
    assert (g["split"][:] == 255).any()


def test_y_is_nan_on_land_and_below_bottom(synthetic_store: Path):
    g = zarr.open_consolidated(str(synthetic_store / "poseidon.zarr"))
    wet = g["wet"][:].astype(bool)
    bottom = g["bottom"][:]
    y = g["y"][:]
    y_raw = g["y_raw"][:]
    assert np.isnan(y[:, :, ~wet]).all()
    assert np.isnan(y_raw[:, :, ~wet]).all()
    below_bottom = np.broadcast_to(bottom[None] == 0, y_raw.shape)
    assert np.isnan(y_raw[below_bottom]).all()
    assert np.isnan(y[below_bottom]).all()


def test_climatology_finite_on_wet_cells(synthetic_store: Path):
    g = zarr.open_consolidated(str(synthetic_store / "poseidon.zarr"))
    wet = g["wet"][:].astype(bool)
    clim_y_surface = g["clim_y"][:, 0]
    assert np.isfinite(clim_y_surface[:, wet]).any()


def test_static_depth_channel_varies(synthetic_store: Path):
    g = zarr.open_consolidated(str(synthetic_store / "poseidon.zarr"))
    static = g["static"][:]
    assert static[1].std() > 0


def test_argo_parquet_columns(synthetic_store: Path):
    import pandas as pd

    df = pd.read_parquet(synthetic_store / "argo_matchups.parquet")
    expected = {"date", "wmo", "lat", "lon", "cell_i", "cell_j", "dist_km"}
    expected |= {f"t_{int(d)}" for d in DEPTHS_M}
    assert expected.issubset(set(df.columns))
    assert len(df) > 0
