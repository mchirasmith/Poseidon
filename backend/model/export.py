"""ONNX export for poseidon-lite (opset 17, dynamic H/W) and artifact validation for poseidon-gbm."""
from __future__ import annotations

# torch and lightgbm each bundle a conflicting OpenMP runtime on macOS, so each model's export
# path imports only the library it needs, and the two paths never run in the same process.
import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from model.dataset import Store, full_domain_batch
from pipeline.sources import DEPTHS_M

ONNX_OPSET = 17
PARITY_MAX_ABS_DIFF = 1e-4
PARITY_MAX_ABS_DIFF_FULL_DOMAIN = 5e-4  # real (non-random) inputs accumulate more float32 rounding
PARITY_N_TILES = 10
PARITY_SIZES = [(16, 24), (40, 56)]  # multiples of 8, neither a multiple of the other


def _make_export_wrapper(torch, nn):
    """Build the ExportWrapper class bound to a torch/nn imported by the caller."""

    class ExportWrapper(nn.Module):
        """Lite forward with calibration alphas baked into the sigma output."""

        def __init__(self, lite: nn.Module, alphas: list[float]):
            super().__init__()
            self.lite = lite
            self.register_buffer("alpha", torch.tensor(alphas, dtype=torch.float32).view(1, -1, 1, 1))

        def forward(self, x, static):
            mean, logsigma, embedding = self.lite(x, static)
            sigma = self.alpha * torch.exp(logsigma.clamp(-6.0, 6.0))
            return mean, sigma, embedding

    return ExportWrapper


def _example_inputs(store: Store, window: int, torch):
    t = int(np.where(store.split == 0)[0][-1])
    x, s, h, w = full_domain_batch(store, t, window)
    return torch.as_tensor(x, dtype=torch.float32), torch.as_tensor(s, dtype=torch.float32)


def export_lite(cfg_path: str, data_dir: str, art_dir: str) -> Path:
    import torch
    import torch.nn as nn

    from model.calibrate import _load_lite

    ExportWrapper = _make_export_wrapper(torch, nn)

    cfg = yaml.safe_load(Path(cfg_path).read_text())
    art_dir = Path(art_dir)
    store = Store.open(Path(data_dir) / "poseidon.zarr")
    device = "cpu"
    model = _load_lite(cfg, art_dir, device)

    card_path = art_dir / "lite" / "model_card.json"
    card = json.loads(card_path.read_text()) if card_path.exists() else {}
    alphas = card.get("calibration_alphas", [1.0] * len(DEPTHS_M))
    wrapper = ExportWrapper(model, alphas).eval()

    x_ex, s_ex = _example_inputs(store, cfg["window"], torch)
    onnx_path = art_dir / "lite" / "poseidon-lite.onnx"
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        wrapper,
        (x_ex, s_ex),
        str(onnx_path),
        input_names=["x", "static"],
        output_names=["mean", "sigma", "embedding"],
        opset_version=ONNX_OPSET,
        dynamic_axes={
            "x": {3: "H", 4: "W"},
            "static": {2: "H", 3: "W"},
            "mean": {2: "H", 3: "W"},
            "sigma": {2: "H", 3: "W"},
            "embedding": {2: "H", 3: "W"},
        },
        dynamo=False,
    )

    # verify against a freshly built module: the legacy tracer leaves hooks on `wrapper`
    # that make a reused instance unsafe to call again in the same process
    fresh = ExportWrapper(_load_lite(cfg, art_dir, device), alphas).eval()
    max_diff = verify_parity(fresh, onnx_path, cfg["window"], store)
    card["onnx_path"] = str(onnx_path)
    card["opset"] = ONNX_OPSET
    card["parity_max_abs_diff"] = max_diff
    card_path.write_text(json.dumps(card, indent=2))
    return onnx_path


def _max_abs_diff(wrapper, sess, x: np.ndarray, s: np.ndarray) -> float:
    import torch

    with torch.no_grad():
        t_mean, t_sigma, t_emb = wrapper(torch.as_tensor(x), torch.as_tensor(s))
    o_mean, o_sigma, o_emb = sess.run(None, {"x": x, "static": s})
    return max(
        float(np.max(np.abs(t_mean.numpy() - o_mean))),
        float(np.max(np.abs(t_sigma.numpy() - o_sigma))),
        float(np.max(np.abs(t_emb.numpy() - o_emb))),
    )


def verify_parity(wrapper, onnx_path: Path, window: int, store: Store | None = None) -> float:
    """Max abs diff between PyTorch and ONNX Runtime over PARITY_N_TILES tiles at two sizes; raises if too large.

    Also checks a full-domain padded run (real, non-random inputs) against a looser tolerance.
    """
    import onnxruntime as ort

    sess = ort.InferenceSession(str(onnx_path))
    rng = np.random.default_rng(1)
    worst = 0.0
    for h, w in PARITY_SIZES:
        h_p, w_p = -(-h // 8) * 8, -(-w // 8) * 8
        for _ in range(PARITY_N_TILES):
            x = rng.normal(size=(1, window, 12, h_p, w_p)).astype(np.float32)
            s = rng.normal(size=(1, 3, h_p, w_p)).astype(np.float32)
            worst = max(worst, _max_abs_diff(wrapper, sess, x, s))
    if worst >= PARITY_MAX_ABS_DIFF:
        raise RuntimeError(f"ONNX parity failed: max abs diff {worst} >= {PARITY_MAX_ABS_DIFF}")

    if store is not None:
        t = int(np.where(store.split == 0)[0][-1])
        x, s, _, _ = full_domain_batch(store, t, window)
        full_diff = _max_abs_diff(wrapper, sess, x.astype(np.float32), s.astype(np.float32))
        if full_diff >= PARITY_MAX_ABS_DIFF_FULL_DOMAIN:
            raise RuntimeError(f"ONNX full-domain parity failed: max abs diff {full_diff} >= {PARITY_MAX_ABS_DIFF_FULL_DOMAIN}")

    return worst


def export_gbm(cfg_path: str, data_dir: str, art_dir: str) -> Path:
    import lightgbm as lgb

    out_dir = Path(art_dir) / "gbm"
    spec = json.loads((out_dir / "feature_spec.json").read_text())
    for depth in spec["depths_m"]:
        booster = lgb.Booster(model_file=str(out_dir / f"depth_{int(depth):02d}.txt"))
        assert booster.num_trees() > 0, f"booster for depth {depth} has no trees"
    card_path = out_dir / "model_card.json"
    card = json.loads(card_path.read_text()) if card_path.exists() else {}
    card["validated"] = True
    card_path.write_text(json.dumps(card, indent=2))
    return out_dir


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=["lite", "gbm"], default="lite")
    p.add_argument("--cfg", default="configs/lite.yaml")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--art-dir", default="artifacts")
    args = p.parse_args()
    if args.model == "lite":
        export_lite(args.cfg, args.data_dir, args.art_dir)
    else:
        export_gbm(args.cfg, args.data_dir, args.art_dir)


if __name__ == "__main__":
    main()
