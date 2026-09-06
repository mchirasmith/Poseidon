"""Per-depth sigma calibration: scale poseidon-lite uncertainty to match nominal 90% coverage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import yaml

from model.dataset import Store, full_domain_batch
from model.lite import Lite
from model.train_nn import resolve_device
from pipeline.sources import DEPTHS_M, SPLIT_CAL

NOMINAL_COVERAGE = 0.90
Z_90 = 1.6448536269514722  # standard normal quantile for a two-sided 90% interval
ALPHA_LO, ALPHA_HI, ALPHA_ITERS = 0.05, 20.0, 40


def _load_lite(cfg: dict, art_dir: Path, device: str) -> Lite:
    model = Lite(
        cfg["window"], 12, cfg["width"], cfg["decoder_width"], cfg["emb_dim"], cfg["attn_heads"], cfg["depth_tokens"]
    ).to(device)
    ckpt = torch.load(art_dir / "lite" / "best.pt", map_location=device)
    model.load_state_dict(ckpt["ema"])
    model.eval()
    return model


def _coverage(alpha: float, mean, sigma, target, mask) -> float:
    half_width = alpha * Z_90 * sigma
    inside = (target >= mean - half_width) & (target <= mean + half_width) & mask
    denom = mask.sum()
    return float(inside.sum() / denom) if denom else 0.0


def fit_alpha(mean, sigma, target, mask) -> float:
    """Bisection on alpha so empirical coverage of the alpha-scaled 90% interval matches nominal."""
    if not np.any(mask):
        return 1.0
    lo, hi = ALPHA_LO, ALPHA_HI
    if _coverage(hi, mean, sigma, target, mask) < NOMINAL_COVERAGE:
        return hi
    for _ in range(ALPHA_ITERS):
        mid = 0.5 * (lo + hi)
        if _coverage(mid, mean, sigma, target, mask) < NOMINAL_COVERAGE:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def calibrate(cfg_path: str, data_dir: str, art_dir: str) -> list[float]:
    cfg = yaml.safe_load(Path(cfg_path).read_text())
    art_dir = Path(art_dir)
    store = Store.open(Path(data_dir) / "poseidon.zarr")
    device = resolve_device(cfg["device"])
    model = _load_lite(cfg, art_dir, device)

    cal_days = np.where(store.split == SPLIT_CAL)[0]
    if len(cal_days) > cfg["cal_days"]:
        cal_days = np.random.default_rng(0).choice(cal_days, cfg["cal_days"], replace=False)

    means, sigmas, targets, masks = [], [], [], []
    for t in cal_days:
        x, s, h, w = full_domain_batch(store, int(t), cfg["window"])
        y, mask = store.day_target(int(t))
        with torch.no_grad():
            mean, logsigma, _ = model(torch.as_tensor(x, dtype=torch.float32, device=device), torch.as_tensor(s, dtype=torch.float32, device=device))
        means.append(mean[0, :, :h, :w].cpu().numpy())
        sigmas.append(torch.exp(logsigma[0, :, :h, :w].clamp(-6, 6)).cpu().numpy())
        targets.append(y)
        masks.append(mask)

    alphas = []
    if means:
        mean_a = np.stack(means)
        sigma_a = np.stack(sigmas)
        target_a = np.stack(targets)
        mask_a = np.stack(masks)
        for d in range(len(DEPTHS_M)):
            alphas.append(fit_alpha(mean_a[:, d], sigma_a[:, d], target_a[:, d], mask_a[:, d]))
    else:
        alphas = [1.0] * len(DEPTHS_M)

    card_path = art_dir / "lite" / "model_card.json"
    card = json.loads(card_path.read_text()) if card_path.exists() else {}
    card["calibration_alphas"] = alphas
    card_path.write_text(json.dumps(card, indent=2))
    return alphas


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cfg", default="configs/lite.yaml")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--art-dir", default="artifacts")
    args = p.parse_args()
    calibrate(args.cfg, args.data_dir, args.art_dir)


if __name__ == "__main__":
    main()
