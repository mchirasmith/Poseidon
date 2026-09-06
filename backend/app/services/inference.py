"""Live inference engine: loads the store and models once, runs one day end to end.

Never imports torch: serving uses onnxruntime (lite) and lightgbm (gbm) only.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from model.dataset import Store
from model.infer import load_gbm, make_session, predict_gbm, predict_lite
from pipeline.sources import SPLIT_PURGED

Z90_ONE_SIDED = 1.2816
INPUT_HISTORY_DAYS = 9
INPUT_VARS = ("sst", "sss", "sla", "cur", "wind")
STAGES = ("load", "encode", "embed", "decode")


def _mask_land_seafloor(arr: np.ndarray, wet: np.ndarray, bottom: np.ndarray) -> np.ndarray:
    """(D, H, W) arr -> NaN on land and below the seafloor."""
    out = arr.copy()
    out[:, wet == 0] = np.nan
    out[bottom == 0] = np.nan
    return out


def _physical_x_field(store: Store, x: np.ndarray, m: np.ndarray, doy_idx: int) -> dict[str, np.ndarray]:
    """One day's (H, W) x/x_mask -> physical values for the five display variables."""
    from pipeline.sources import X_MASK_VARS, X_VARS

    physical = {}
    for k, v in enumerate(X_VARS):
        entry = store.norm.get(v, {"mean": 0.0, "std": 1.0})
        clim = store.clim_x[doy_idx, k]
        valid = m[X_MASK_VARS.index(_var_mask(v))] == 1
        physical[v] = np.where(valid, x[k] * entry["std"] + entry["mean"] + clim, np.nan)
    return {
        "sst": physical["sst"],
        "sss": physical["sss"],
        "sla": physical["sla"],
        "cur": np.hypot(physical["cur_u"], physical["cur_v"]),
        "wind": np.hypot(physical["wnd_u"], physical["wnd_v"]),
    }


def build_input_history(store: Store, t: int) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    """(var -> (INPUT_HISTORY_DAYS, H, W) physical) and each var's missing fraction on the latest day."""
    days = range(t - INPUT_HISTORY_DAYS + 1, t + 1)
    per_day = []
    for dt in days:
        if 0 <= dt < store.T:
            x, m = store.field_day(dt)
            doy_idx = (store.doy[dt] - 1) % 366
        else:
            x = np.full((store.n_x, store.H, store.W), np.nan, dtype=np.float32)
            m = np.zeros((store.n_mask, store.H, store.W), dtype=np.uint8)
            doy_idx = 0
        per_day.append(_physical_x_field(store, x, m, doy_idx))
    history = {v: np.stack([day[v] for day in per_day]) for v in INPUT_VARS}
    latest = per_day[-1]
    wet = store.wet.astype(bool)
    n_wet = int(wet.sum())
    frac = {v: float(1.0 - np.isfinite(latest[v])[wet].sum() / n_wet) if n_wet else 0.0 for v in INPUT_VARS}
    return history, frac


def _var_mask(v: str) -> str:
    return {"sst": "sst", "sss": "sss", "sla": "sla", "cur_u": "cur", "cur_v": "cur", "wnd_u": "wnd", "wnd_v": "wnd"}[v]


class Engine:
    """Holds the store, model card(s), ONNX session and gbm boosters, loaded once."""

    def __init__(self, data_dir: str | Path, art_dir: str | Path, scales_path: str | Path, settings):
        self.settings = settings
        self.store = Store.open(Path(data_dir) / "poseidon.zarr")
        self.scales = json.loads(Path(scales_path).read_text())
        self.art_dir = Path(art_dir)

        card_path = self.art_dir / "lite" / "model_card.json"
        self.lite_card = json.loads(card_path.read_text()) if card_path.exists() else {}
        onnx_path = self.art_dir / "lite" / "poseidon-lite.onnx"
        self.session = make_session(onnx_path, settings.device) if onnx_path.exists() else None
        self.window = int(self.session.get_inputs()[0].shape[1]) if self.session is not None else 3

        self.gbm = None
        self.gbm_card = {}
        if settings.enable_gbm:
            gbm_card_path = self.art_dir / "gbm" / "model_card.json"
            self.gbm_card = json.loads(gbm_card_path.read_text()) if gbm_card_path.exists() else {}
            spec_path = self.art_dir / "gbm" / "feature_spec.json"
            if spec_path.exists():
                self.gbm = load_gbm(self.art_dir)

    def warm_up(self) -> None:
        if self.session is None:
            return
        h, w = 8, 8
        x = np.zeros((1, self.window, 12, h, w), dtype=np.float32)
        s = np.zeros((1, 3, h, w), dtype=np.float32)
        self.session.run(None, {"x": x, "static": s})

    def _time_index(self, date: str) -> int:
        target = np.datetime64(date, "D")
        idx = np.where(self.store.time == target)[0]
        if len(idx) == 0 or self.store.split[idx[0]] == SPLIT_PURGED:
            raise ValueError(f"{date} not in store")
        return int(idx[0])

    def run(self, date: str, model: str, set_stage) -> dict:
        set_stage("load")
        t = self._time_index(date)
        wet = self.store.wet.astype(np.uint8)
        bottom = self.store.bottom.astype(np.uint8)
        y_raw = self.store.y_raw_day(t)
        inputs, input_missing = build_input_history(self.store, t)

        set_stage("encode")
        if model == "gbm":
            mean, anomaly = predict_gbm(self.store, self.gbm, t)
            sigma = p10 = p90 = None
            embedding = None
        else:
            mean, sigma, anomaly, embedding = predict_lite(self.store, {"session": self.session}, t, self.window)
            p10 = mean - Z90_ONE_SIDED * sigma
            p90 = mean + Z90_ONE_SIDED * sigma
        set_stage("embed")
        set_stage("decode")

        mean = _mask_land_seafloor(mean, wet, bottom)
        anomaly = _mask_land_seafloor(anomaly, wet, bottom)
        if sigma is not None:
            sigma = _mask_land_seafloor(sigma, wet, bottom)
            p10 = _mask_land_seafloor(p10, wet, bottom)
            p90 = _mask_land_seafloor(p90, wet, bottom)
        error = _mask_land_seafloor(mean - y_raw, wet, bottom)

        return {
            "t": t,
            "mean": mean,
            "sigma": sigma,
            "p10": p10,
            "p90": p90,
            "anomaly": anomaly,
            "error": error,
            "embedding": embedding,
            "y_raw": y_raw,
            "wet": wet,
            "bottom": bottom,
            "inputs": inputs,
            "input_missing": input_missing,
        }
