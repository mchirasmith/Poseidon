"""One evaluation harness for climatology, gbm and lite on the test split; writes report.json/.md.

Streams over test days: accumulates sums per (model, depth, basin, season) instead of stacking
every day's fields, so peak memory stays flat regardless of how long the test split is.
"""
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
THERM_BAND = (DEPTHS_M >= THERMOCLINE_MIN_M) & (DEPTHS_M <= THERMOCLINE_MAX_M)
DEPTH_100M_IDX = int(np.where(DEPTHS_M == 100.0)[0][0])
SPATIAL_POWER_GRID_STEP_DEG = 0.25
MAX_ARGO_ROWS = 20000
N_DEPTHS = len(DEPTHS_M)


def _tree(models, factory):
    """model -> basin -> season -> factory(), the shape every per-day accumulator is stored in."""
    return {m: {b: {s: factory() for s in SEASONS} for b in BASINS} for m in models}


def evaluate(data_dir: str, art_dir: str, models: list[str], device: str = "cpu") -> dict:
    data_dir, art_dir = Path(data_dir), Path(art_dir)
    store = Store.open(data_dir / "poseidon.zarr")

    test_days = np.where(store.split == SPLIT_TEST)[0]
    lon2d = np.broadcast_to(store.lon[None, :], (store.H, store.W))
    basin2d = {
        "overall": np.ones((store.H, store.W), dtype=bool),
        "arabian_sea": M.basin_mask(lon2d, "arabian_sea"),
        "bay_of_bengal": M.basin_mask(lon2d, "bay_of_bengal"),
    }

    gbm = load_gbm(art_dir) if "gbm" in models else None
    lite = load_lite(art_dir, device) if "lite" in models else None
    window = int(lite["session"].get_inputs()[0].shape[1]) if lite is not None else 0

    # "climatology" is always tracked, since skill_score needs it as a baseline even when unrequested
    compute_models = list(dict.fromkeys([*models, "climatology"]))

    depth_acc = _tree(compute_models, lambda: M.init_sum_acc(N_DEPTHS))
    therm_acc = _tree(compute_models, M.init_sqerr_acc)
    vgrad_acc = _tree(compute_models, M.init_sqerr_acc)
    d20_acc = _tree(compute_models, M.init_sqerr_acc)
    d26_acc = _tree(compute_models, M.init_sqerr_acc)
    mld_acc = _tree(compute_models, M.init_sqerr_acc)
    power_acc = {m: {s: {"sum": 0.0, "n": 0} for s in SEASONS} for m in compute_models}
    calib_acc = M.init_calibration_acc()

    argo_index = _argo_day_index(store, data_dir)
    argo_series = {name: {"pred": [], "obs": []} for name in [*models, "glorys"]}

    for t in test_days:
        y_true = store.y_raw_day(int(t))
        _, mask = store.day_target(int(t))
        mask = mask.astype(bool)
        clim = predict_climatology(store, int(t))
        month = pd.Timestamp(store.time[t]).month
        season_names = ("all", M.season_of(month))

        preds, sigmas = {}, {}
        for model in compute_models:
            if model == "climatology":
                preds[model] = clim
            elif model == "gbm":
                preds[model], _ = predict_gbm(store, gbm, int(t))
            elif model == "lite":
                preds[model], sigmas[model], _, _ = predict_lite(store, lite, int(t), window)

        for i, j, obs in argo_index.get(int(t), []):
            valid = np.isfinite(obs)
            argo_series["glorys"]["pred"].append(y_true[:, i, j][valid])
            argo_series["glorys"]["obs"].append(obs[valid])
            for model in models:
                argo_series[model]["pred"].append(preds[model][:, i, j][valid])
                argo_series[model]["obs"].append(obs[valid])

        if "lite" in preds:
            M.accumulate_calibration(calib_acc, preds["lite"], sigmas["lite"], y_true, mask)

        true_d20, true_d26, true_mld = d20(DEPTHS_M, y_true), d26(DEPTHS_M, y_true), mld(DEPTHS_M, y_true)

        for model in compute_models:
            pred = preds[model]
            pred_d20, pred_d26, pred_mld = d20(DEPTHS_M, pred), d26(DEPTHS_M, pred), mld(DEPTHS_M, pred)
            surf_mask_base = mask[0] & np.isfinite(pred_d20) & np.isfinite(true_d20)
            d26_mask_base = mask[0] & np.isfinite(pred_d26) & np.isfinite(true_d26)
            mld_mask_base = mask[0] & np.isfinite(pred_mld) & np.isfinite(true_mld)

            ratio_valid = mask[DEPTH_100M_IDX].any()
            ratio = M.spatial_power_ratio(pred[DEPTH_100M_IDX], y_true[DEPTH_100M_IDX],
                                           SPATIAL_POWER_GRID_STEP_DEG, SPATIAL_POWER_GRID_STEP_DEG) if ratio_valid else float("nan")

            for basin, b2d in basin2d.items():
                mask3 = mask & b2d[None]
                for season_name in season_names:
                    M.accumulate_sums(depth_acc[model][basin][season_name], pred, y_true, clim, mask3, axis=(1, 2))
                    M.accumulate_sqerr(therm_acc[model][basin][season_name], pred[THERM_BAND], y_true[THERM_BAND], mask3[THERM_BAND])

                    d_pred, d_true = np.diff(pred, axis=0), np.diff(y_true, axis=0)
                    pair_mask = mask3[:-1] & mask3[1:]
                    M.accumulate_sqerr(vgrad_acc[model][basin][season_name], d_pred, d_true, pair_mask)

                    M.accumulate_sqerr(d20_acc[model][basin][season_name], pred_d20, true_d20, surf_mask_base & b2d)
                    M.accumulate_sqerr(d26_acc[model][basin][season_name], pred_d26, true_d26, d26_mask_base & b2d)
                    M.accumulate_sqerr(mld_acc[model][basin][season_name], pred_mld, true_mld, mld_mask_base & b2d)

            # whole-grid metric, tracked once per day regardless of basin
            if ratio_valid and np.isfinite(ratio):
                for season_name in season_names:
                    p = power_acc[model][season_name]
                    p["sum"] += ratio
                    p["n"] += 1

    by_depth: dict = {}
    tables: dict = {}
    for model in models:
        by_depth[model] = {"rmse": {}, "mae": {}, "bias": {}, "r": {}, "anomaly_correlation": {}, "skill_score": {}}
        tables[model] = {"thermocline_rmse": {}, "d20_rmse": {}, "d26_rmse": {}, "mld_rmse": {}, "vgrad_rmse": {}, "spatial_power_ratio_100m": {}}
        for basin in BASINS:
            for season in SEASONS:
                acc = depth_acc[model][basin][season]
                by_depth[model]["rmse"].setdefault(basin, {})[season] = [float(v) for v in M.rmse_from_sums(acc)]
                by_depth[model]["mae"].setdefault(basin, {})[season] = [float(v) for v in M.mae_from_sums(acc)]
                by_depth[model]["bias"].setdefault(basin, {})[season] = [float(v) for v in M.bias_from_sums(acc)]
                by_depth[model]["r"].setdefault(basin, {})[season] = [float(v) for v in M.r_from_sums(acc)]
                by_depth[model]["anomaly_correlation"].setdefault(basin, {})[season] = [float(v) for v in M.anomaly_correlation_from_sums(acc)]
                by_depth[model]["skill_score"].setdefault(basin, {})[season] = [
                    float(v) for v in M.skill_score_from_sums(acc, depth_acc["climatology"][basin][season])
                ]

                tables[model]["thermocline_rmse"].setdefault(basin, {})[season] = M.rmse_from_sqerr(therm_acc[model][basin][season])
                tables[model]["vgrad_rmse"].setdefault(basin, {})[season] = M.rmse_from_sqerr(vgrad_acc[model][basin][season])
                tables[model]["d20_rmse"].setdefault(basin, {})[season] = M.rmse_from_sqerr(d20_acc[model][basin][season])
                tables[model]["d26_rmse"].setdefault(basin, {})[season] = M.rmse_from_sqerr(d26_acc[model][basin][season])
                tables[model]["mld_rmse"].setdefault(basin, {})[season] = M.rmse_from_sqerr(mld_acc[model][basin][season])

        # spatial_power_ratio_100m has no basin breakdown: it's a mean of per-day whole-grid ratios
        for season in SEASONS:
            p = power_acc[model][season]
            tables[model]["spatial_power_ratio_100m"][season] = (p["sum"] / p["n"]) if p["n"] else float("nan")

    calibration = {}
    if "lite" in models:
        n = calib_acc["n"]
        calibration = {
            "nll": calib_acc["nll"] / n if n else float("nan"),
            "crps": calib_acc["crps"] / n if n else float("nan"),
            "coverage": {str(lvl): (calib_acc["coverage"][lvl] / n if n else float("nan")) for lvl in (0.5, 0.8, 0.9, 0.95)},
            "mean_interval_width_90": calib_acc["width90"] / n if n else float("nan"),
        }

    argo_scatter = _finalize_argo(argo_series)

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


def _argo_day_index(store: Store, data_dir: Path) -> dict[int, list[tuple[int, int, np.ndarray]]]:
    """test-day index -> [(cell_i, cell_j, obs_by_depth), ...], read once before the day loop."""
    parquet_path = data_dir / "argo_matchups.parquet"
    if not parquet_path.exists():
        return {}
    df = pd.read_parquet(parquet_path)
    if len(df) > MAX_ARGO_ROWS:
        df = df.sample(n=MAX_ARGO_ROWS, random_state=0)
    time_to_idx = {np.datetime64(t, "D"): i for i, t in enumerate(store.time)}
    depth_cols = [f"t_{int(d)}" for d in DEPTHS_M]

    index: dict[int, list[tuple[int, int, np.ndarray]]] = {}
    for _, row in df.iterrows():
        t = time_to_idx.get(np.datetime64(pd.Timestamp(row["date"]).date(), "D"))
        if t is None:
            continue
        obs = np.asarray([row[c] for c in depth_cols], dtype=np.float32)
        if not np.isfinite(obs).any():
            continue
        index.setdefault(t, []).append((int(row["cell_i"]), int(row["cell_j"]), obs))
    return index


def _finalize_argo(series: dict) -> dict:
    """Concatenate the per-day matchup arrays gathered during the day loop into RMSE/bias/r."""
    out = {}
    for name, d in series.items():
        if not d["pred"]:
            out[name] = {"rmse": float("nan"), "bias": float("nan"), "r": float("nan"), "n": 0}
            continue
        pred = np.concatenate(d["pred"])
        obs = np.concatenate(d["obs"])
        mask = np.isfinite(pred) & np.isfinite(obs)  # a float over a cell that is dry at depth has no prediction there
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
