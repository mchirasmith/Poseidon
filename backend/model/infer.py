"""Torch-free prediction helpers shared by eval.evaluate and app.services.inference.

Kept separate from model/dataset.py so the API process and eval/precompute.py never import torch.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort

from model.dataset import Store, full_domain_batch
from model.features import build_features
from pipeline.sources import DEPTHS_M

PROVIDERS_BY_DEVICE = {
    "cpu": ["CPUExecutionProvider"],
    "coreml": ["CoreMLExecutionProvider", "CPUExecutionProvider"],
    "cuda": ["CUDAExecutionProvider", "CPUExecutionProvider"],
}


def y_norm(store: Store, depth_idx: int) -> tuple[float, float]:
    entry = store.norm.get(f"y_depth_{int(DEPTHS_M[depth_idx])}", {"mean": 0.0, "std": 1.0})
    return float(entry["mean"]), float(entry["std"])


def full_field(h: int, w: int, ii: np.ndarray, jj: np.ndarray, values: np.ndarray) -> np.ndarray:
    """(15, H, W) filled with NaN outside the given ocean cells; values is (n_cells, 15)."""
    out = np.full((values.shape[1], h, w), np.nan, dtype=np.float32)
    out[:, ii, jj] = values.T
    return out


def predict_climatology(store: Store, t: int) -> np.ndarray:
    doy_idx = (store.doy[t] - 1) % 366
    return np.asarray(store.clim_y[doy_idx], dtype=np.float32)


def load_gbm(art_dir: str | Path) -> dict:
    """Imports lightgbm lazily: it cannot share a process with an already-imported torch on macOS."""
    import lightgbm as lgb

    out_dir = Path(art_dir) / "gbm"
    spec = json.loads((out_dir / "feature_spec.json").read_text())
    boosters = [lgb.Booster(model_file=str(out_dir / f"depth_{int(d):02d}.txt")) for d in spec["depths_m"]]
    return {"boosters": boosters}


def predict_gbm(store: Store, gbm: dict, t: int) -> tuple[np.ndarray, np.ndarray]:
    """(mean_abs, anomaly), both (15, H, W); gbm has no calibrated uncertainty."""
    feats, (ii, jj) = build_features(store, t)
    clim = predict_climatology(store, t)
    preds = np.stack([b.predict(feats) for b in gbm["boosters"]], axis=1)  # (n_cells, 15)
    for d in range(preds.shape[1]):
        mean, std = y_norm(store, d)
        preds[:, d] = preds[:, d] * std + mean
    anomaly = full_field(store.H, store.W, ii, jj, preds)
    return anomaly + clim, anomaly


def make_session(onnx_path: str | Path, device: str) -> ort.InferenceSession:
    providers = PROVIDERS_BY_DEVICE.get(device, ["CPUExecutionProvider"])
    return ort.InferenceSession(str(onnx_path), providers=providers)


def load_lite(art_dir: str | Path, device: str = "cpu") -> dict:
    onnx_path = Path(art_dir) / "lite" / "poseidon-lite.onnx"
    return {"session": make_session(onnx_path, device)}


def predict_lite(store: Store, lite: dict, t: int, window: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(mean_abs, sigma, anomaly, embedding); mean_abs and anomaly are (15, H, W) in degrees C."""
    x, s, h, w = full_domain_batch(store, t, window)
    mean_n, sigma_n, emb = lite["session"].run(None, {"x": x.astype(np.float32), "static": s.astype(np.float32)})
    mean_n, sigma_n, emb = mean_n[0, :, :h, :w], sigma_n[0, :, :h, :w], emb[0, :, :h, :w]
    clim = predict_climatology(store, t)
    anomaly = np.empty_like(mean_n)
    sigma = np.empty_like(sigma_n)
    for d in range(mean_n.shape[0]):
        _, std = y_norm(store, d)
        anomaly[d] = mean_n[d] * std
        sigma[d] = sigma_n[d] * std
    return anomaly + clim, sigma, anomaly, emb
