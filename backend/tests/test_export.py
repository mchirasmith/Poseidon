"""ONNX export parity, onnxruntime full-domain run, and GBM artifact validation."""
import json

import numpy as np
import onnxruntime as ort
import torch
import yaml

from model.calibrate import _load_lite
from model.dataset import Store, full_domain_batch
from model.export import PARITY_MAX_ABS_DIFF
from tests.test_model_train import full_artifacts  # noqa: F401  (shared session fixture)

TINY_CFG = yaml.safe_load(open("configs/tiny.yaml"))


def test_export_writes_onnx_and_card(full_artifacts):
    onnx_path = full_artifacts / "lite" / "poseidon-lite.onnx"
    assert onnx_path.exists()
    card = json.loads((full_artifacts / "lite" / "model_card.json").read_text())
    assert card["opset"] == 17
    assert card["parity_max_abs_diff"] < PARITY_MAX_ABS_DIFF
    assert len(card["calibration_alphas"]) == 15


def test_gbm_export_validates_boosters(full_artifacts):
    card = json.loads((full_artifacts / "gbm" / "model_card.json").read_text())
    assert card["validated"] is True


def test_onnxruntime_full_domain_run(full_artifacts, synthetic_store):
    store = Store.open(synthetic_store / "poseidon.zarr")
    sess = ort.InferenceSession(str(full_artifacts / "lite" / "poseidon-lite.onnx"))
    x, s, h, w = full_domain_batch(store, 100, TINY_CFG["window"])
    mean, sigma, emb = sess.run(None, {"x": x.astype(np.float32), "static": s.astype(np.float32)})
    assert mean.shape[2:] == x.shape[-2:]
    assert np.isfinite(mean[:, :, :h, :w]).all()
    assert (sigma[:, :, :h, :w] > 0).all()


def test_onnx_parity_on_non_multiple_of_tile(full_artifacts):
    """Export must run cleanly on a domain size that is not a multiple of the training tile."""
    sess = ort.InferenceSession(str(full_artifacts / "lite" / "poseidon-lite.onnx"))
    rng = np.random.default_rng(3)
    h, w = 24, 40  # not a multiple of tiny.yaml's tile=16
    x = rng.normal(size=(1, TINY_CFG["window"], 12, h, w)).astype(np.float32)
    s = rng.normal(size=(1, 3, h, w)).astype(np.float32)
    mean, sigma, emb = sess.run(None, {"x": x, "static": s})
    assert mean.shape == (1, 15, h, w)


def test_onnx_sigma_equals_alpha_scaled_pytorch_sigma(full_artifacts, synthetic_store):
    store = Store.open(synthetic_store / "poseidon.zarr")
    card = json.loads((full_artifacts / "lite" / "model_card.json").read_text())
    alphas = np.asarray(card["calibration_alphas"], dtype=np.float32)
    model = _load_lite(TINY_CFG, full_artifacts, "cpu")

    x, s, h, w = full_domain_batch(store, 100, TINY_CFG["window"])
    with torch.no_grad():
        _, logsigma, _ = model(torch.as_tensor(x, dtype=torch.float32), torch.as_tensor(s, dtype=torch.float32))
    expected_sigma = alphas[None, :, None, None] * torch.exp(logsigma.clamp(-6.0, 6.0)).numpy()

    sess = ort.InferenceSession(str(full_artifacts / "lite" / "poseidon-lite.onnx"))
    _, onnx_sigma, _ = sess.run(None, {"x": x.astype(np.float32), "static": s.astype(np.float32)})
    # sigma = alpha * exp(logsigma) can be large, amplifying float32 rounding: use a relative tolerance
    np.testing.assert_allclose(expected_sigma, onnx_sigma, rtol=1e-4, atol=1e-4)
