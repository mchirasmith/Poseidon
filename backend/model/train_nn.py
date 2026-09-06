"""Plain PyTorch training loop for poseidon-lite: AdamW, cosine schedule, EMA, dev eval."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from model.dataset import Sampler, Store, Tiler
from model.lite import Lite
from model.losses import lite_loss
from pipeline.sources import DEPTHS_M

DEPTH_100M_IDX = int(np.where(DEPTHS_M == 100.0)[0][0])


def resolve_device(name: str) -> str:
    if name == "mps" and not torch.backends.mps.is_available():
        return "cpu"
    if name == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return name


class EMA:
    def __init__(self, model: torch.nn.Module, decay: float):
        self.decay = decay
        self.shadow = {k: v.detach().clone() for k, v in model.state_dict().items()}

    def update(self, model: torch.nn.Module) -> None:
        for k, v in model.state_dict().items():
            if v.dtype.is_floating_point:
                self.shadow[k].mul_(self.decay).add_(v.detach(), alpha=1 - self.decay)
            else:
                self.shadow[k] = v.detach().clone()

    def apply_to(self, model: torch.nn.Module) -> None:
        model.load_state_dict(self.shadow, strict=True)


def _train_day_range(store: Store, y0: int, y1: int) -> np.ndarray:
    years = store.time.astype("datetime64[Y]").astype(int) + 1970
    return np.where((store.split == 0) & (years >= y0) & (years <= y1))[0]


def _make_batch(store: Store, tiler: Tiler, samples, window: int, device: str):
    xs, ys, masks, cores, statics = [], [], [], [], []
    core_cache: dict[tuple[int, int], np.ndarray] = {}
    for t, oh, ow in samples:
        w = store.window(t, window)
        x_tile, _ = tiler.extract(w, oh, ow)
        y, m = store.day_target(t)
        y_tile, valid = tiler.extract(y, oh, ow)
        m_tile, _ = tiler.extract(m, oh, ow)
        s_tile, _ = tiler.extract(store.static, oh, ow)
        if (oh, ow) not in core_cache:
            core_cache[(oh, ow)] = tiler.core_mask(oh, ow) & valid
        xs.append(x_tile)
        ys.append(y_tile)
        masks.append(m_tile & valid[None])
        cores.append(core_cache[(oh, ow)])
        statics.append(s_tile)
    to = lambda a, dt=torch.float32: torch.as_tensor(np.stack(a), dtype=dt, device=device)
    return (
        to(xs),
        to(statics),
        to(ys),
        to(masks, torch.float32),
        to(cores, torch.float32),
    )


def _dev_eval(store, tiler, dev_days, model, device, window, n_tiles, rng):
    if len(dev_days) == 0:
        return float("nan"), float("nan")
    origins = tiler.tiles
    samples = [(int(rng.choice(dev_days)), *origins[rng.integers(len(origins))]) for _ in range(n_tiles)]
    x, s, y, mask, core = _make_batch(store, tiler, samples, window, device)
    model.eval()
    with torch.no_grad():
        mean, logsigma, _ = model(x, s)
        full_mask = mask * core.unsqueeze(1)
        sigma = torch.exp(logsigma.clamp(-6, 6))
        nll = 0.5 * np.log(2 * np.pi) + logsigma.clamp(-6, 6) + 0.5 * ((y - mean) / sigma) ** 2
        denom = full_mask.sum().clamp(min=1.0)
        dev_nll = float((nll * full_mask).sum() / denom)
        m100 = full_mask[:, DEPTH_100M_IDX]
        se = (mean[:, DEPTH_100M_IDX] - y[:, DEPTH_100M_IDX]) ** 2
        d100 = m100.sum().clamp(min=1.0)
        dev_rmse_100m = float(((se * m100).sum() / d100).sqrt())
    model.train()
    return dev_nll, dev_rmse_100m


def train(cfg_path: str, data_dir: str, art_dir: str) -> Path:
    cfg = yaml.safe_load(Path(cfg_path).read_text())
    store = Store.open(Path(data_dir) / "poseidon.zarr")

    y0, y1 = cfg["years_train"]
    train_days = _train_day_range(store, y0, y1)
    dev_days = np.where(store.split == 1)[0]

    if cfg.get("in_ram", True) and len(train_days):
        # widen by window-1 so the earliest sampled day still has a full lookback window in RAM
        store.load_in_ram(int(train_days.min()) - (cfg["window"] - 1), int(train_days.max()) + 1)

    tiler = Tiler(store.H, store.W, cfg["tile"], cfg["core"])
    rng = np.random.default_rng(0)
    sampler = Sampler(store, tiler, train_days, cfg["min_wet_frac"], rng)

    device = resolve_device(cfg["device"])
    model = Lite(
        cfg["window"], 12, cfg["width"], cfg["decoder_width"], cfg["emb_dim"], cfg["attn_heads"], cfg["depth_tokens"]
    ).to(device)
    ema = EMA(model, cfg["ema_decay"])
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["lr"]), weight_decay=float(cfg["weight_decay"]))
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg["steps"])

    out_dir = Path(art_dir) / "lite"
    ckpt_dir = out_dir / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    curve = []
    best_nll = float("inf")
    t_last = time.time()
    for step in range(1, cfg["steps"] + 1):
        samples = sampler.sample(cfg["batch"])
        x, s, y, mask, core = _make_batch(store, tiler, samples, cfg["window"], device)

        opt.zero_grad()
        mean, logsigma, _ = model(x, s)
        loss, parts = lite_loss(mean, logsigma, y, mask, core, cfg["loss"])
        loss.backward()
        opt.step()
        sched.step()
        ema.update(model)

        if step % 100 == 0 or step == 1:
            dt = time.time() - t_last
            t_last = time.time()
            print(f"step {step} loss {float(loss.detach()):.4f} nll {parts['nll']:.4f} vgrad {parts['vgrad']:.4f} s/step {dt/max(step % 100, 1):.3f}")

        if step % cfg["eval_every"] == 0 or step == cfg["steps"]:
            eval_model = Lite(
                cfg["window"], 12, cfg["width"], cfg["decoder_width"], cfg["emb_dim"], cfg["attn_heads"], cfg["depth_tokens"]
            ).to(device)
            ema.apply_to(eval_model)
            n_tiles = min(cfg["eval_tiles"], len(dev_days) * 4 or 1)
            dev_nll, dev_rmse_100m = _dev_eval(store, tiler, dev_days, eval_model, device, cfg["window"], n_tiles, rng)
            curve.append({"step": step, "dev_nll": dev_nll, "dev_rmse_100m": dev_rmse_100m})
            ckpt = {"step": step, "model": model.state_dict(), "ema": ema.shadow, "cfg": cfg}
            torch.save(ckpt, ckpt_dir / f"step_{step:04d}.pt")
            if dev_nll < best_nll:
                best_nll = dev_nll
                torch.save(ckpt, out_dir / "best.pt")

    (out_dir / "learning_curve.json").write_text(json.dumps(curve, indent=2))

    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent).stdout.strip()
    card = {
        "name": "poseidon-lite",
        "git_sha": sha,
        "config_hash": hashlib.sha256(Path(cfg_path).read_bytes()).hexdigest()[:12],
        "data_hash": store.root.attrs.get("data_hash", ""),
        "train_years": [y0, y1],
        "steps": cfg["steps"],
        "dev_metrics": curve[-1] if curve else {},
    }
    (out_dir / "model_card.json").write_text(json.dumps(card, indent=2))
    return out_dir


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cfg", default="configs/lite.yaml")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--art-dir", default="artifacts")
    args = p.parse_args()
    train(args.cfg, args.data_dir, args.art_dir)


if __name__ == "__main__":
    main()
