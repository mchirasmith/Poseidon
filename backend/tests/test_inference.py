"""Engine.run determinism and parity with a direct ONNX call. lite only: gbm needs a subprocess
(lightgbm cannot share a process with torch, already imported by other test modules)."""
from pathlib import Path

import numpy as np
import pytest

from app.config import Settings
from app.services.inference import Engine, _physical_x_field
from model.dataset import Store, full_domain_batch
from pipeline.sources import DEPTHS_M


@pytest.fixture(scope="module")
def engine(synthetic_trained_lite) -> Engine:
    data_dir, art_dir = synthetic_trained_lite
    settings = Settings(data_dir=str(data_dir), art_dir=str(art_dir), enable_gbm=False)
    scales_path = Path(__file__).resolve().parent.parent / "scales.json"
    return Engine(data_dir, art_dir, scales_path, settings)


def _a_test_date(engine: Engine) -> str:
    from pipeline.sources import SPLIT_TEST

    idx = np.where(engine.store.split == SPLIT_TEST)[0]
    assert len(idx) > 0
    return str(np.datetime_as_string(engine.store.time[idx[0]], unit="D"))


def test_run_is_deterministic(engine: Engine):
    date = _a_test_date(engine)
    r1 = engine.run(date, "lite", lambda s: None)
    r2 = engine.run(date, "lite", lambda s: None)
    np.testing.assert_array_equal(np.nan_to_num(r1["mean"]), np.nan_to_num(r2["mean"]))
    np.testing.assert_array_equal(np.nan_to_num(r1["sigma"]), np.nan_to_num(r2["sigma"]))


def test_matches_direct_onnx_call(engine: Engine):
    date = _a_test_date(engine)
    result = engine.run(date, "lite", lambda s: None)

    t = engine._time_index(date)
    x, s, h, w = full_domain_batch(engine.store, t, engine.window)
    mean_n, sigma_n, _emb = engine.session.run(None, {"x": x.astype(np.float32), "static": s.astype(np.float32)})
    mean_n, sigma_n = mean_n[0, :, :h, :w], sigma_n[0, :, :h, :w]

    clim = engine.store.clim_y[(engine.store.doy[t] - 1) % 366]
    for d in range(mean_n.shape[0]):
        entry = engine.store.norm.get(f"y_depth_{int(DEPTHS_M[d])}", {"mean": 0.0, "std": 1.0})
        expected_mean = mean_n[d] * entry["std"] + entry["mean"] + clim[d]
        got = result["mean"][d]
        diff = np.nan_to_num(got - expected_mean, nan=0.0)
        assert np.max(np.abs(diff)) < 1e-4


def test_missing_fraction_is_over_wet_cells_only(synthetic_store):
    from app.services.inference import build_input_history

    store = Store.open(synthetic_store / "poseidon.zarr")
    t = 10
    _, frac = build_input_history(store, t)

    x, m = store.field_day(t)
    doy_idx = (store.doy[t] - 1) % 366
    physical = _physical_x_field(store, x, m, doy_idx)
    wet = store.wet.astype(bool)
    all_cells_frac = 1.0 - np.isfinite(physical["sst"]).sum() / physical["sst"].size
    wet_only_frac = 1.0 - np.isfinite(physical["sst"])[wet].sum() / wet.sum()

    assert frac["sst"] == pytest.approx(wet_only_frac)
    assert frac["sst"] != pytest.approx(all_cells_frac)


def test_masks_land_and_below_seafloor(engine: Engine):
    date = _a_test_date(engine)
    result = engine.run(date, "lite", lambda s: None)
    wet = result["wet"].astype(bool)
    assert np.isnan(result["mean"][:, ~wet]).all()
    below = result["bottom"] == 0
    assert np.isnan(result["mean"][below]).all()
