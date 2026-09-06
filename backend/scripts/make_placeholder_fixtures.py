"""Generates small deterministic placeholder fixtures for the mock server."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import STANDARD_DEPTHS_M
from app.services import derived, tiles

RNG = np.random.default_rng(7)

NY, NX = 20, 24
LAT_MIN, LON_MIN, STEP = 5.125, 45.125, 0.25
DATES = ["2020-05-18", "2020-01-15"]
CURATED_LABEL = {"2020-05-18": "Cyclone Amphan"}
INPUT_VARS = ("sst", "sss", "sla", "cur", "wind")
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def smooth_field(base: float, spread: float, seed_offset: int) -> np.ndarray:
    """Cheap smooth random field: low-res noise upsampled by repetition + blur-ish average."""
    rng = np.random.default_rng(7 + seed_offset)
    coarse = rng.normal(base, spread, size=(5, 6))
    field = np.kron(coarse, np.ones((NY // 5, NX // 6)))
    field = field[:NY, :NX]
    return field.astype(np.float64)


def make_wet_mask() -> np.ndarray:
    wet = np.ones((NY, NX), dtype=np.uint8)
    wet[0, :] = 0  # southern border land strip
    wet[:, 0] = 0  # western border land strip
    return wet


def make_bottom(wet: np.ndarray) -> np.ndarray:
    """All 15 depths above seafloor except a shallow shelf near the western edge."""
    bottom = np.ones((15, NY, NX), dtype=np.uint8)
    bottom[8:, :, 1:4] = 0  # depths >= 125 m are below seafloor on the shelf
    return bottom


def write_png(path: Path, array2d: np.ndarray, mode: str, scales: dict, wet: np.ndarray, bottom=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tiles.render(array2d, mode, scales, wet, bottom))


def build_profile(seed: int) -> tuple[list[float], list[float]]:
    rng = np.random.default_rng(seed)
    surf = 29.0 + rng.normal(0, 0.5)
    depths = np.array(STANDARD_DEPTHS_M, dtype=np.float64)
    mean = surf - 0.02 * depths - 8.0 * (1 / (1 + np.exp(-(depths - 120) / 30)))
    mean = mean + rng.normal(0, 0.05, size=depths.shape)
    return depths.tolist(), mean.tolist()


def main() -> None:
    scales = json.loads((FIXTURES_DIR.parent / "scales.json").read_text())
    wet = make_wet_mask()
    bottom = make_bottom(wet)

    (FIXTURES_DIR / "download").mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / "wet_mask.json").write_text(json.dumps(wet.tolist()))

    grid = {
        "lat_min": LAT_MIN,
        "lat_max": LAT_MIN + (NY - 1) * STEP,
        "lon_min": LON_MIN,
        "lon_max": LON_MIN + (NX - 1) * STEP,
        "step": STEP,
        "ny": NY,
        "nx": NX,
    }

    meta = {
        "model_version": "0.1.0-placeholder",
        "checkpoint": "placeholder",
        "test_range": ["2019-01-01", "2020-12-31"],
        "depths_m": STANDARD_DEPTHS_M,
        "grid": grid,
        "curated_days": [{"date": d, "label": CURATED_LABEL.get(d, d)} for d in DATES],
        "cached_days": DATES,
        "models_available": ["lite", "gbm"],
        "fixture_kind": "placeholder",
    }
    (FIXTURES_DIR / "meta.json").write_text(json.dumps(meta))

    report = {
        "headline": {"lite": {"rmse": 0.42}, "gbm": {"rmse": 0.55}, "fixture_kind": "placeholder"},
        "by_depth": {},
        "maps": {},
        "argo_scatter": [],
        "calibration": {},
        "tables": {},
        "learning_curve": {},
    }
    (FIXTURES_DIR / "report.json").write_text(json.dumps(report))

    for di, date in enumerate(DATES):
        day_dir = FIXTURES_DIR / "days" / date
        tile_dir = FIXTURES_DIR / "tiles" / date

        inputs = {}
        for vi, var in enumerate(INPUT_VARS):
            base = {"sst": 28, "sss": 34, "sla": 0.0, "cur": 0.3, "wind": 6.0}[var]
            spread = {"sst": 1.5, "sss": 0.5, "sla": 0.1, "cur": 0.2, "wind": 2.0}[var]
            field = smooth_field(base, spread, seed_offset=di * 10 + vi)
            history = []
            for t in range(-8, 1):
                png_path = tile_dir / "in" / f"{var}_t{t}.png"
                write_png(png_path, field + t * 0.02, var, scales, wet)
                history.append(f"/tiles/{date}/in/{var}_t{t}.png")
            inputs[var] = {
                "tile": history[-1],
                "range": [float(field.min()), float(field.max())],
                "missing_fraction": 0.0,
                "history": history,
            }

        layers = {}
        per_depth_scales = {}
        for mi, mode in enumerate(("mean", "sigma", "anom", "error")):
            urls = []
            ranges = []
            for zi, depth_m in enumerate(STANDARD_DEPTHS_M):
                base = {"mean": 28 - 0.02 * depth_m, "sigma": 0.3, "anom": 0.0, "error": 0.0}[mode]
                spread = {"mean": 1.0, "sigma": 0.1, "anom": 0.5, "error": 0.4}[mode]
                field = smooth_field(base, spread, seed_offset=di * 100 + zi + mi * 20)
                png_path = tile_dir / mode / f"z{zi:02d}.png"
                write_png(png_path, field, mode, scales, wet, bottom[zi])
                urls.append(f"/tiles/{date}/{mode}/z{zi:02d}.png")
                ranges.append([float(field.min()), float(field.max())])
            layers[mode] = urls
            per_depth_scales[mode] = ranges

        nc_path = FIXTURES_DIR / "download" / f"poseidon_lite_{date}.nc"
        nc_path.write_bytes(b"placeholder netcdf fixture, not a real CF file\n")

        day_payload = {
            "date": date,
            "cached_at": "2026-01-01T00:00:00Z",
            "runtime_ms": 1200,
            "inputs": inputs,
            "layers": layers,
            "scales": {m: [scales[m]["vmin"], scales[m]["vmax"]] for m in ("mean", "sigma", "anom", "error")},
            "per_depth_scales": per_depth_scales,
            "netcdf_url": f"/download/poseidon_lite_{date}.nc",
        }
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "day.json").write_text(json.dumps(day_payload))

        depths_m, mean_t = build_profile(seed=100 + di)
        p10 = [round(t - 0.4, 3) for t in mean_t]
        p90 = [round(t + 0.4, 3) for t in mean_t]
        glorys = [round(t + 0.05, 3) for t in mean_t]
        d20 = derived.d20(np.array(depths_m), np.array(mean_t))
        d26 = derived.d26(np.array(depths_m), np.array(mean_t))
        mld = derived.mld(np.array(depths_m), np.array(mean_t))

        lat = LAT_MIN + (NY // 2) * STEP
        lon = LON_MIN + (NX // 2) * STEP
        profile_payload = {
            "lat": lat,
            "lon": lon,
            "depths_m": depths_m,
            "poseidon_mean": mean_t,
            "poseidon_p10": p10,
            "poseidon_p90": p90,
            "glorys": glorys,
            "gbm": None,
            "argo": (
                {
                    "wmo": "2902123",
                    "distance_km": 31.0,
                    "day_offset": -1,
                    "depths_m": depths_m,
                    "temp": glorys,
                }
                if di == 0
                else None
            ),
            "scalars": {
                "d20_m": None if np.isnan(d20) else float(d20),
                "d26_m": None if np.isnan(d26) else float(d26),
                "mld_m": None if np.isnan(mld) else float(mld),
                "rmse_glorys": 0.31,
                "rmse_argo": 0.44,
            },
        }
        (day_dir / "profile.json").write_text(json.dumps(profile_payload))

        n_points = 10
        a_lat, a_lon = LAT_MIN + 2 * STEP, LON_MIN + 2 * STEP
        b_lat, b_lon = LAT_MIN + (NY - 2) * STEP, LON_MIN + (NX - 2) * STEP
        lats = np.linspace(a_lat, b_lat, n_points).tolist()
        lons = np.linspace(a_lon, b_lon, n_points).tolist()
        distances = (np.linspace(0, 1, n_points) * 300).tolist()
        section_payload = {
            "distances_km": distances,
            "lats": lats,
            "lons": lons,
            "depths_m": depths_m,
            "poseidon": [mean_t for _ in range(n_points)],
            "glorys": [glorys for _ in range(n_points)],
            "sigma": [p10 for _ in range(n_points)],
            "d20_m": [None if np.isnan(d20) else float(d20)] * n_points,
            "mld_m": [None if np.isnan(mld) else float(mld)] * n_points,
            "argo_markers": [{"distance_km": 150.0, "wmo": "2902123"}] if di == 0 else [],
        }
        (day_dir / "section.json").write_text(json.dumps(section_payload))

    print(f"wrote fixtures to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
