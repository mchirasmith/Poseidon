"""One evaluation harness for climatology, gbm and lite on the test split; writes report.json/.md."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.services.derived import d20, d26, mld
from eval import metrics as M
from model.dataset import Store
from model.infer import load_gbm, load_lite, predict_climatology, predict_gbm, predict_lite
from pipeline.sources import DEPTHS_M, SPLIT_TEST

BASINS = ["overall", "arabian_sea", "bay_of_bengal"]
SEASONS = ["all", "DJF", "MAM", "JJAS", "ON"]
THERMOCLINE_MIN_M, THERMOCLINE_MAX_M = 50.0, 200.0
DEPTH_100M_IDX = int(np.where(DEPTHS_M == 100.0)[0][0])
MAX_ARGO_ROWS = 20000


def _depth_metric(fn, pred, true, mask, basin_mask2d, season_mask1d):
    """[15] list applying `fn(pred[:,d],true[:,d],combined_mask)` per depth."""
    out = []
    for d in range(pred.shape[1]):
        m = mask[:, d] & basin_mask2d[None] & season_mask1d[:, None, None]
        out.append(fn(pred[:, d], true[:, d], m))
    return out


def evaluate(data_dir: str, art_dir: str, models: list[str], device: str = "cpu") -> dict:
    data_dir, art_dir = Path(data_dir), Path(art_dir)
    store = Store.open(data_dir / "poseidon.zarr")

    test_days = np.where(store.split == SPLIT_TEST)[0]
    lat2d = np.broadcast_to(store.lat[:, None], (store.H, store.W))
    lon2d = np.broadcast_to(store.lon[None, :], (store.H, store.W))
    as_mask2d = M.basin_mask(lon2d, "arabian_sea")
    bob_mask2d = M.basin_mask(lon2d, "bay_of_bengal")

    gbm = load_gbm(art_dir) if "gbm" in models else None
    lite = load_lite(art_dir, device) if "lite" in models else None
    window = int(lite["session"].get_inputs()[0].shape[1]) if lite is not None else 0

    true_stack, clim_stack, mask_stack, season_labels = [], [], [], []
    pred_stack = {m: [] for m in models}
    sigma_stack = []
    day_cache: dict[int, dict] = {}

    for t in test_days:
        y_true = store.y_raw_day(int(t))
        _, mask = store.day_target(int(t))
        clim = predict_climatology(store, int(t))
        true_stack.append(y_true)
        clim_stack.append(clim)
        mask_stack.append(mask)
        month = pd.Timestamp(store.time[t]).month
        season_labels.append(M.season_of(month))

        preds_here = {}
        if "climatology" in models:
            preds_here["climatology"] = clim
            pred_stack["climatology"].append(clim)
        if "gbm" in models:
            p, _ = predict_gbm(store, gbm, int(t))
            preds_here["gbm"] = p
            pred_stack["gbm"].append(p)
        if "lite" in models:
            p, sig, _, _ = predict_lite(store, lite, int(t), window)
            preds_here["lite"] = p
            pred_stack["lite"].append(p)
            sigma_stack.append(sig)
        day_cache[int(t)] = preds_here

    true_a = np.stack(true_stack)
    clim_a = np.stack(clim_stack)
    mask_a = np.stack(mask_stack).astype(bool)
    season_a = np.asarray(season_labels)

    by_depth: dict = {}
    tables: dict = {}
    for model in models:
        pred_a = np.stack(pred_stack[model])
        by_depth[model] = {"rmse": {}, "mae": {}, "bias": {}, "r": {}, "anomaly_correlation": {}, "skill_score": {}}
        tables[model] = {"thermocline_rmse": {}, "d20_rmse": {}, "d26_rmse": {}, "mld_rmse": {}, "vgrad_rmse": {}, "spatial_power_ratio_100m": {}}

        clim_pred_a = np.stack(pred_stack["climatology"]) if "climatology" in models else clim_a

        for basin in BASINS:
            b2d = np.ones_like(as_mask2d) if basin == "overall" else (as_mask2d if basin == "arabian_sea" else bob_mask2d)
            for season in SEASONS:
                s1d = np.ones(len(test_days), dtype=bool) if season == "all" else season_a == season

                by_depth[model]["rmse"].setdefault(basin, {})[season] = _depth_metric(M.rmse, pred_a, true_a, mask_a, b2d, s1d)
                by_depth[model]["mae"].setdefault(basin, {})[season] = _depth_metric(M.mae, pred_a, true_a, mask_a, b2d, s1d)
                by_depth[model]["bias"].setdefault(basin, {})[season] = _depth_metric(M.bias, pred_a, true_a, mask_a, b2d, s1d)
                by_depth[model]["r"].setdefault(basin, {})[season] = _depth_metric(M.pearson_r, pred_a, true_a, mask_a, b2d, s1d)
                by_depth[model]["anomaly_correlation"].setdefault(basin, {})[season] = [
                    M.anomaly_correlation(pred_a[:, d], true_a[:, d], clim_a[:, d], mask_a[:, d] & b2d[None] & s1d[:, None, None])
                    for d in range(len(DEPTHS_M))
                ]
                skills = []
                for d in range(len(DEPTHS_M)):
                    dm = mask_a[:, d] & b2d[None] & s1d[:, None, None]
                    mse_model = M.rmse(pred_a[:, d], true_a[:, d], dm) ** 2
                    mse_clim = M.rmse(clim_pred_a[:, d], true_a[:, d], dm) ** 2
                    skills.append(M.skill_score(mse_model, mse_clim))
                by_depth[model]["skill_score"].setdefault(basin, {})[season] = skills

                therm_band = (DEPTHS_M >= THERMOCLINE_MIN_M) & (DEPTHS_M <= THERMOCLINE_MAX_M)
                tables[model]["thermocline_rmse"].setdefault(basin, {})[season] = M.rmse(pred_a[:, therm_band], true_a[:, therm_band], mask_a[:, therm_band] & b2d[None, None] & s1d[:, None, None, None])
                tables[model]["vgrad_rmse"].setdefault(basin, {})[season] = M.vgrad_rmse(
                    pred_a, true_a, mask_a & b2d[None, None] & s1d[:, None, None, None], depth_axis=1
                )

                pred_d20 = np.stack([d20(DEPTHS_M, pred_a[i]) for i in range(pred_a.shape[0])])
                true_d20 = np.stack([d20(DEPTHS_M, true_a[i]) for i in range(true_a.shape[0])])
                pred_d26 = np.stack([d26(DEPTHS_M, pred_a[i]) for i in range(pred_a.shape[0])])
                true_d26 = np.stack([d26(DEPTHS_M, true_a[i]) for i in range(true_a.shape[0])])
                pred_mld = np.stack([mld(DEPTHS_M, pred_a[i]) for i in range(pred_a.shape[0])])
                true_mld = np.stack([mld(DEPTHS_M, true_a[i]) for i in range(true_a.shape[0])])
                surf_mask = mask_a[:, 0] & b2d[None] & s1d[:, None, None]
                tables[model]["d20_rmse"].setdefault(basin, {})[season] = M.rmse(pred_d20, true_d20, surf_mask & np.isfinite(true_d20) & np.isfinite(pred_d20))
                tables[model]["d26_rmse"].setdefault(basin, {})[season] = M.rmse(pred_d26, true_d26, surf_mask & np.isfinite(true_d26) & np.isfinite(pred_d26))
                tables[model]["mld_rmse"].setdefault(basin, {})[season] = M.rmse(pred_mld, true_mld, surf_mask & np.isfinite(true_mld) & np.isfinite(pred_mld))

                ratios = [
                    M.spatial_power_ratio(pred_a[i, DEPTH_100M_IDX], true_a[i, DEPTH_100M_IDX], 0.25, 0.25)
                    for i in range(pred_a.shape[0])
                    if s1d[i] and mask_a[i, DEPTH_100M_IDX].any()
                ]
                tables[model]["spatial_power_ratio_100m"].setdefault(basin, {})[season] = float(np.nanmean(ratios)) if ratios else float("nan")

    calibration = {}
    if "lite" in models:
        sigma_a = np.stack(sigma_stack)
        pred_a = np.stack(pred_stack["lite"])
        calibration = {
            "nll": M.gaussian_nll(pred_a, sigma_a, true_a, mask_a),
            "crps": M.gaussian_crps(pred_a, sigma_a, true_a, mask_a),
            "coverage": {str(lvl): M.coverage(pred_a, sigma_a, true_a, mask_a, lvl) for lvl in (0.5, 0.8, 0.9, 0.95)},
            "mean_interval_width_90": M.mean_interval_width(sigma_a, mask_a, 0.9),
        }

    argo_scatter = _evaluate_argo(store, data_dir, day_cache, models)

    learning_curve = []
    curve_path = art_dir / "lite" / "learning_curve.json"
    if curve_path.exists():
        learning_curve = json.loads(curve_path.read_text())

    report = {
        "headline": {m: {"thermocline_rmse": tables[m]["thermocline_rmse"]["overall"]["all"]} for m in models},
        "by_depth": by_depth,
        "tables": tables,
        "argo_scatter": argo_scatter,
        "calibration": calibration,
        "learning_curve": learning_curve,
        "maps": {},
    }
    return report


def _evaluate_argo(store: Store, data_dir: Path, day_cache: dict, models: list[str]) -> dict:
    parquet_path = data_dir / "argo_matchups.parquet"
    if not parquet_path.exists():
        return {}
    df = pd.read_parquet(parquet_path)
    if len(df) > MAX_ARGO_ROWS:
        df = df.sample(n=MAX_ARGO_ROWS, random_state=0)
    time_to_idx = {np.datetime64(t, "D"): i for i, t in enumerate(store.time)}
    depth_cols = [f"t_{int(d)}" for d in DEPTHS_M]

    series = {name: {"pred": [], "obs": []} for name in [*models, "glorys"]}
    for _, row in df.iterrows():
        t = time_to_idx.get(np.datetime64(pd.Timestamp(row["date"]).date(), "D"))
        if t is None or t not in day_cache:
            continue
        i, j = int(row["cell_i"]), int(row["cell_j"])
        obs = np.asarray([row[c] for c in depth_cols], dtype=np.float32)
        valid = np.isfinite(obs)
        if not valid.any():
            continue
        glorys = store.y_raw_day(t)[:, i, j]
        series["glorys"]["pred"].append(glorys[valid])
        series["glorys"]["obs"].append(obs[valid])
        for model in models:
            pred = day_cache[t][model][:, i, j]
            series[model]["pred"].append(pred[valid])
            series[model]["obs"].append(obs[valid])

    out = {}
    for name, d in series.items():
        if not d["pred"]:
            out[name] = {"rmse": float("nan"), "bias": float("nan"), "r": float("nan"), "n": 0}
            continue
        pred = np.concatenate(d["pred"])
        obs = np.concatenate(d["obs"])
        mask = np.ones_like(pred, dtype=bool)
        out[name] = {"rmse": M.rmse(pred, obs, mask), "bias": M.bias(pred, obs, mask), "r": M.pearson_r(pred, obs, mask), "n": int(pred.size)}
    return out


def _nan_to_null(obj):
    if isinstance(obj, float):
        return None if np.isnan(obj) else obj
    if isinstance(obj, dict):
        return {k: _nan_to_null(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nan_to_null(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if np.isnan(v) else v
    return obj


def write_report(report: dict, data_dir: str) -> None:
    """Write report.json and report.md into `data_dir` (the pipeline's data directory)."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    clean = _nan_to_null(report)
    (data_dir / "report.json").write_text(json.dumps(clean, indent=2))

    lines = ["# Poseidon evaluation report", "", "| model | thermocline RMSE (overall) |", "|---|---|"]
    for model, headline in report["headline"].items():
        val = headline["thermocline_rmse"]
        lines.append(f"| {model} | {val if val is not None else 'N/A'} |")
    (data_dir / "report.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="data")
    p.add_argument("--art-dir", default="artifacts")
    p.add_argument("--models", default="climatology,gbm,lite")
    p.add_argument("--device", default="cpu")
    args = p.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    report = evaluate(args.data_dir, args.art_dir, models, args.device)
    write_report(report, args.data_dir)


if __name__ == "__main__":
    main()
