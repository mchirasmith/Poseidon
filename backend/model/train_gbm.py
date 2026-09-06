"""LightGBM baseline: 15 per-depth regressors on normalised anomaly, trained on tabular rows."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import lightgbm as lgb
import numpy as np
import yaml

from model.dataset import Store
from model.features import FEATURE_COLUMNS, build_features
from pipeline.sources import DEPTHS_M

GBM_OBJECTIVE = "regression"
GBM_MIN_DATA_IN_LEAF = 20


def _year_train_days(store: Store, y0: int, y1: int) -> np.ndarray:
    years = store.time.astype("datetime64[Y]").astype(int) + 1970
    return np.where((store.split == 0) & (years >= y0) & (years <= y1))[0]


def collect_rows(store: Store, days: np.ndarray, rows_budget: int, rng: np.random.Generator):
    """Sample (day, cell) pairs first, then build features only for the days actually sampled.

    The wet-cell set is the same every day, so total rows = len(days) * n_wet_cells and a flat
    row index can be sampled directly without ever building features for the full day range.
    """
    n_cells = int((store.wet == 1).sum())
    total = len(days) * n_cells
    if total == 0:
        empty = np.empty((0, len(FEATURE_COLUMNS)), dtype=np.float32)
        return empty, np.empty((0, len(DEPTHS_M)), dtype=np.float32), np.empty((0, len(DEPTHS_M)), dtype=np.uint8)

    n_rows = min(rows_budget, total)
    flat_idx = rng.choice(total, size=n_rows, replace=False)
    day_pos, cell_pos = flat_idx // n_cells, flat_idx % n_cells

    feat_chunks, y_chunks, mask_chunks = [], [], []
    for dp in np.unique(day_pos):
        t = int(days[dp])
        sel = cell_pos[day_pos == dp]
        feats, (ii, jj) = build_features(store, t)
        y, mask = store.day_target(t)
        feat_chunks.append(feats[sel])
        y_chunks.append(y[:, ii[sel], jj[sel]].T)
        mask_chunks.append(mask[:, ii[sel], jj[sel]].T)
    return np.concatenate(feat_chunks, axis=0), np.concatenate(y_chunks, axis=0), np.concatenate(mask_chunks, axis=0)


def train_depth(feats: np.ndarray, y: np.ndarray, mask: np.ndarray, cfg: dict) -> lgb.Booster:
    """One LightGBM regressor for one depth, rows restricted to its valid mask."""
    valid = mask.astype(bool)
    ds = lgb.Dataset(feats[valid], label=y[valid], feature_name=FEATURE_COLUMNS, free_raw_data=True)
    params = {
        "objective": GBM_OBJECTIVE,
        "num_leaves": cfg["num_leaves"],
        "learning_rate": cfg["learning_rate"],
        "min_data_in_leaf": min(GBM_MIN_DATA_IN_LEAF, max(1, valid.sum() // 4)),
        "verbose": -1,
    }
    return lgb.train(params, ds, num_boost_round=cfg["num_trees"])


def train(cfg_path: str, rows_key: str, data_dir: str, art_dir: str) -> Path:
    all_cfg = yaml.safe_load(Path(cfg_path).read_text())
    cfg = all_cfg[rows_key]
    store = Store.open(Path(data_dir) / "poseidon.zarr")
    rng = np.random.default_rng(0)

    y0, y1 = cfg["years_train"]
    days = _year_train_days(store, y0, y1)
    feats, y_all, mask_all = collect_rows(store, days, cfg["rows"], rng)

    out_dir = Path(art_dir) / "gbm"
    out_dir.mkdir(parents=True, exist_ok=True)

    dev_days = np.where(store.split == 1)[0]
    dev_rmse = []
    for d in range(len(DEPTHS_M)):
        booster = train_depth(feats, y_all[:, d], mask_all[:, d], cfg)
        booster.save_model(str(out_dir / f"depth_{int(DEPTHS_M[d]):02d}.txt"))
        if len(dev_days) > 0:
            dev_feats, dev_y, dev_mask = collect_rows(store, dev_days[:1], 5000, rng)
            valid = dev_mask[:, d].astype(bool)
            if valid.any():
                pred = booster.predict(dev_feats[valid])
                dev_rmse.append(float(np.sqrt(np.mean((pred - dev_y[valid, d]) ** 2))))

    (out_dir / "feature_spec.json").write_text(
        json.dumps({"columns": FEATURE_COLUMNS, "depths_m": DEPTHS_M.tolist()}, indent=2)
    )
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent).stdout.strip()
    card = {
        "name": "poseidon-gbm",
        "git_sha": sha,
        "config_hash": hashlib.sha256(Path(cfg_path).read_bytes()).hexdigest()[:12],
        "data_hash": store.root.attrs.get("data_hash", ""),
        "train_years": [y0, y1],
        "rows": int(feats.shape[0]),
        "dev_metrics": {"rmse_mean": float(np.mean(dev_rmse))} if dev_rmse else {},
    }
    (out_dir / "model_card.json").write_text(json.dumps(card, indent=2))
    return out_dir


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cfg", default="configs/gbm.yaml")
    p.add_argument("--rows", default="lite")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--art-dir", default="artifacts")
    args = p.parse_args()
    train(args.cfg, args.rows, args.data_dir, args.art_dir)


if __name__ == "__main__":
    main()
