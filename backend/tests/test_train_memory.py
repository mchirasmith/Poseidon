"""MPS driver memory must plateau, not grow, over a training run."""
import sys
from pathlib import Path

import pytest
import torch
import yaml

from model import train_nn

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or not torch.backends.mps.is_available(), reason="requires MPS, unix only"
)

TINY_CFG = Path(__file__).resolve().parent.parent / "configs" / "tiny.yaml"
PROBE_STEPS = (50, 200)


def test_driver_memory_plateaus_over_200_steps(synthetic_store, tmp_path):
    cfg = yaml.safe_load(TINY_CFG.read_text())
    cfg["device"] = "mps"
    cfg["steps"] = 200
    cfg_path = tmp_path / "tiny_mps.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))

    readings = {}

    def on_step(step: int) -> None:
        if step in PROBE_STEPS:
            readings[step] = torch.mps.driver_allocated_memory()

    train_nn.train(str(cfg_path), str(synthetic_store), str(tmp_path), on_step=on_step)

    early, late = readings[PROBE_STEPS[0]], readings[PROBE_STEPS[1]]
    growth = late - early
    assert growth < 0.10 * max(early, 1.0)
    assert growth < 1e9


LITE_CFG = Path(__file__).resolve().parent.parent / "configs" / "lite.yaml"
LITE_STEP_MAX_BYTES = 4 * 2**30


def test_lite_step_at_batch_32_fits_memory_budget():
    from model.lite import Lite
    from model.losses import masked_gaussian_nll

    cfg = yaml.safe_load(LITE_CFG.read_text())
    model = Lite(
        cfg["window"], 12, cfg["width"], cfg["decoder_width"], cfg["emb_dim"], cfg["attn_heads"], cfg["depth_tokens"],
        head_chunk=cfg["head_chunk"],
    ).to("mps")
    tile = cfg["tile"]
    x = torch.randn(cfg["batch"], cfg["window"], 12, tile, tile, device="mps")
    static = torch.randn(cfg["batch"], 3, tile, tile, device="mps")
    target = torch.randn(cfg["batch"], 15, tile, tile, device="mps")
    mask = torch.ones_like(target, dtype=torch.bool)
    torch.mps.empty_cache()
    mean, logsigma, _ = model(x, static)
    masked_gaussian_nll(mean, logsigma, target, mask).backward()
    torch.mps.synchronize()
    assert torch.mps.driver_allocated_memory() < LITE_STEP_MAX_BYTES
