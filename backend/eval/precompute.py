"""Caches every test day, fills report.json maps, copies fixtures and the frontend fallback bundle.

Never imports torch: serving-side inference only (onnxruntime + lightgbm).
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from app.config import Settings
from app.deps import LandCellError, LiveBackend
from app.services import cache, tiles
from eval.evaluate import write_report
from pipeline.sources import DEPTHS_M, SPLIT_TEST

SECTION_PRESETS = {
    "bob_north_south": {"a": (20.0, 88.0), "b": (6.0, 88.0)},
    "as_east_west": {"a": (15.0, 50.0), "b": (15.0, 75.0)},
    "equatorial_edge": {"a": (7.0, 60.0), "b": (7.0, 95.0)},
}
N_FALLBACK_DAYS = 5
N_SECTION_POINTS = 60
FALLBACK_FIELDS = ("mean", "sigma", "glorys")  # the (D, H, W) arrays the frontend cuts sections from offline


def _test_dates(store, days_arg: str) -> list[str]:
    idx = np.where(store.split == SPLIT_TEST)[0]
    dates = [np.datetime_as_string(store.time[t], unit="D") for t in idx]
    if days_arg == "all":
        return dates
    return dates[: int(days_arg)]


def _center_ocean_cell(store) -> tuple[float, float]:
    ii, jj = np.where(store.wet == 1)
    mid = len(ii) // 2
    return float(store.lat[ii[mid]]), float(store.lon[jj[mid]])


def _clamp_preset(preset: dict, store) -> tuple[tuple[float, float], tuple[float, float]]:
    """Clamp a preset's lat/lon endpoints into the store's actual grid bounds."""
    lat_lo, lat_hi = float(store.lat.min()), float(store.lat.max())
    lon_lo, lon_hi = float(store.lon.min()), float(store.lon.max())

    def clamp(pt):
        lat, lon = pt
        return max(lat_lo, min(lat_hi, lat)), max(lon_lo, min(lon_hi, lon))

    return clamp(preset["a"]), clamp(preset["b"])


def _compute_maps(backend: LiveBackend, model: str, dates: list[str]) -> tuple[np.ndarray, np.ndarray]:
    store = backend.engine.store
    D, H, W = len(DEPTHS_M), store.H, store.W
    sq_err = np.zeros((D, H, W))
    err = np.zeros((D, H, W))
    n = np.zeros((D, H, W))
    for date in dates:
        fields = np.load(cache.fields_path(backend.cache_root, date, model))
        mean, glorys = fields["mean"], fields["glorys"]
        valid = np.isfinite(mean) & np.isfinite(glorys)
        diff = np.where(valid, mean - glorys, 0.0)
        sq_err += diff**2 * valid
        err += diff * valid
        n += valid
    with np.errstate(invalid="ignore"):
        rmse = np.where(n > 0, np.sqrt(sq_err / np.maximum(n, 1)), np.nan)
        bias = np.where(n > 0, err / np.maximum(n, 1), np.nan)
    return rmse, bias


def _write_report_maps(backend: LiveBackend, rmse: np.ndarray, bias: np.ndarray) -> dict:
    store = backend.engine.store
    scales = backend.engine.scales
    wet = store.wet.astype(bool)
    maps = {}
    for d in range(len(DEPTHS_M)):
        rmse_path = backend.cache_root / "report" / "rmse" / f"z{d:02d}.png"
        bias_path = backend.cache_root / "report" / "bias" / f"z{d:02d}.png"
        rmse_path.parent.mkdir(parents=True, exist_ok=True)
        bias_path.parent.mkdir(parents=True, exist_ok=True)
        rmse_path.write_bytes(tiles.render(rmse[d], "rmse", scales, wet))
        bias_path.write_bytes(tiles.render(bias[d], "bias", scales, wet))
        maps[str(int(DEPTHS_M[d]))] = {
            "rmse": f"/tiles/report/rmse/z{d:02d}.png",
            "bias": f"/tiles/report/bias/z{d:02d}.png",
        }
    return maps


def _curated_dates(backend: LiveBackend, test_dates: list[str]) -> list[str]:
    curated_path = backend.data_dir / "curated_days.json"
    if curated_path.exists():
        curated = json.loads(curated_path.read_text())
        return [c["date"] for c in curated][:N_FALLBACK_DAYS]
    return test_dates[:N_FALLBACK_DAYS]


def _rewrite_urls(obj, prefix: str = "/fallback"):
    if isinstance(obj, str) and obj.startswith(("/tiles/", "/download/")):
        return f"{prefix}{obj}"
    if isinstance(obj, dict):
        return {k: _rewrite_urls(v, prefix) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rewrite_urls(v, prefix) for v in obj]
    return obj


def _copy_tiles_for(backend: LiveBackend, date: str, model: str, out_root: Path) -> None:
    """PNG tiles only: the cached arrays and NetCDFs would multiply the static bundle's size."""
    src = backend.cache_root / date
    for sub in (model, "in"):
        src_dir = src / sub
        if src_dir.exists():
            dst_dir = out_root / "tiles" / date / sub
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            for png in src_dir.rglob("*.png"):
                dst = dst_dir / png.relative_to(src_dir)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(png, dst)


def _write_day_fields(fields, day_dir: Path, store) -> None:
    """fields.bin: little-endian float16 (len(FALLBACK_FIELDS), D, H, W); fields.json describes the axes."""
    D = len(DEPTHS_M)
    arrays = []
    for key in FALLBACK_FIELDS:
        arr = np.asarray(fields[key], dtype=np.float32)
        arrays.append(arr if arr.size else np.full((D, store.H, store.W), np.nan, dtype=np.float32))
    stack = np.stack(arrays)
    (day_dir / "fields.bin").write_bytes(stack.astype("<f2").tobytes())
    (day_dir / "fields.json").write_text(json.dumps({
        "order": list(FALLBACK_FIELDS),
        "dtype": "float16",
        "shape": list(stack.shape),
        "lat": [float(v) for v in store.lat],
        "lon": [float(v) for v in store.lon],
        "depths_m": [float(d) for d in DEPTHS_M],
    }))


def _write_day_argo(backend: LiveBackend, date: str, day_dir: Path) -> None:
    """Argo profiles within the matchup day window, so the frontend can mark floats on any transect."""
    window = backend.argo_index.day_window(date, backend.settings.argo_max_days)
    rows = []
    if window is not None:
        for r in window[["wmo", "lat", "lon", "_ord", "_target_ord"]].to_dict("records"):
            rows.append({"wmo": str(r["wmo"]), "lat": float(r["lat"]), "lon": float(r["lon"]), "day_offset": int(r["_ord"] - r["_target_ord"])})
    (day_dir / "argo.json").write_text(json.dumps(rows))


def _write_fallback(backend: LiveBackend, model: str, test_dates: list[str], fallback_dir: Path) -> None:
    fallback_dir.mkdir(parents=True, exist_ok=True)
    (fallback_dir / "tiles").mkdir(exist_ok=True)
    (fallback_dir / "days").mkdir(exist_ok=True)

    dates = _curated_dates(backend, test_dates)

    report = json.loads(backend.report_path().read_text())
    (fallback_dir / "report.json").write_text(json.dumps(_rewrite_urls(report)))
    report_src = backend.cache_root / "report"
    if report_src.exists():
        report_dst = fallback_dir / "tiles" / "report"
        if report_dst.exists():
            shutil.rmtree(report_dst)
        shutil.copytree(report_src, report_dst)

    meta = backend.meta().model_dump()
    meta["cached_days"] = dates
    (fallback_dir / "meta.json").write_text(json.dumps(_rewrite_urls(meta), default=str))

    lat, lon = _center_ocean_cell(backend.engine.store)
    for date in dates:
        if not backend.is_cached(date, model):
            backend.run_sync(date, model)
        day_dir = fallback_dir / "days" / date
        day_dir.mkdir(parents=True, exist_ok=True)
        day = backend.day(date, model).model_dump()
        day["netcdf_url"] = ""  # NetCDFs are not bundled into the fallback; keep it small
        (day_dir / "day.json").write_text(json.dumps(_rewrite_urls(day)))
        profile = backend.profile(date, lat, lon, model).model_dump()
        (day_dir / "profile.json").write_text(json.dumps(_rewrite_urls(profile)))
        preset = next(iter(SECTION_PRESETS.values()))
        a, b = _clamp_preset(preset, backend.engine.store)
        section = backend.section(date, a, b, N_SECTION_POINTS, model).model_dump()
        (day_dir / "section.json").write_text(json.dumps(_rewrite_urls(section)))
        day_sections = day_dir / "sections"
        day_sections.mkdir(exist_ok=True)
        for name, preset in SECTION_PRESETS.items():
            a, b = _clamp_preset(preset, backend.engine.store)
            try:
                section = backend.section(date, a, b, N_SECTION_POINTS, model).model_dump()
            except LandCellError:  # a preset endpoint can fall on land in a synthetic or cropped grid
                continue
            (day_sections / f"{name}.json").write_text(json.dumps(_rewrite_urls(section)))
        _write_day_fields(np.load(cache.fields_path(backend.cache_root, date, model)), day_dir, backend.engine.store)
        _write_day_argo(backend, date, day_dir)
        _copy_tiles_for(backend, date, model, fallback_dir)

    if dates:
        sections_dir = fallback_dir / "sections"
        sections_dir.mkdir(exist_ok=True)
        for name, preset in SECTION_PRESETS.items():
            a, b = _clamp_preset(preset, backend.engine.store)
            try:
                section = backend.section(dates[0], a, b, N_SECTION_POINTS, model).model_dump()
            except LandCellError:
                continue
            (sections_dir / f"{name}.json").write_text(json.dumps(_rewrite_urls(section)))


def _regenerate_fixtures(backend: LiveBackend, model: str, test_dates: list[str], fixtures_dir: Path) -> None:
    """Flat single-model fixture layout, matching scripts/make_placeholder_fixtures.py exactly."""
    store = backend.engine.store
    dates = _curated_dates(backend, test_dates)[:2] or test_dates[:2]
    if fixtures_dir.exists():
        shutil.rmtree(fixtures_dir)
    (fixtures_dir / "download").mkdir(parents=True, exist_ok=True)
    (fixtures_dir / "days").mkdir(parents=True, exist_ok=True)
    (fixtures_dir / "tiles").mkdir(parents=True, exist_ok=True)

    # the mock server's land check reads this mask directly; force the grid-center cell wet so a
    # caller that queries the literal grid center (as tests/test_routes.py does) always gets ocean,
    # even when the synthetic generator happens to place its island there
    wet_mask = store.wet.astype(int).copy()
    wet_mask[wet_mask.shape[0] // 2, wet_mask.shape[1] // 2] = 1
    (fixtures_dir / "wet_mask.json").write_text(json.dumps(wet_mask.tolist()))

    meta = backend.meta().model_dump()
    meta["cached_days"] = dates
    meta["fixture_kind"] = "synthetic"
    (fixtures_dir / "meta.json").write_text(json.dumps(meta, default=str))

    if backend.report_path().exists():
        shutil.copy(backend.report_path(), fixtures_dir / "report.json")

    lat, lon = _center_ocean_cell(store)
    for date in dates:
        if not backend.is_cached(date, model):
            backend.run_sync(date, model)

        day = backend.day(date, model).model_dump()
        nc_src = cache.netcdf_path(backend.cache_root, date, model)
        nc_dst = fixtures_dir / "download" / f"poseidon_{model}_{date}.nc"
        shutil.copy(nc_src, nc_dst)
        day["netcdf_url"] = f"/download/{nc_dst.name}"

        # flatten tile urls: fixtures have no per-model directory level
        for mode, urls in day["layers"].items():
            day["layers"][mode] = [u.replace(f"/{model}/", "/") for u in urls]

        day_dir = fixtures_dir / "days" / date
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "day.json").write_text(json.dumps(day))

        profile = backend.profile(date, lat, lon, model).model_dump()
        (day_dir / "profile.json").write_text(json.dumps(profile))

        preset = next(iter(SECTION_PRESETS.values()))
        a, b = _clamp_preset(preset, store)
        section = backend.section(date, a, b, 10, model).model_dump()
        (day_dir / "section.json").write_text(json.dumps(section))

        cache_tiles = backend.cache_root / date

        # model tiles: cache_root/<date>/<model>/<mode>/z##.png -> fixtures/tiles/<date>/<mode>/
        model_dir = cache_tiles / model
        if model_dir.exists():
            for mode_dir in model_dir.iterdir():
                dest = fixtures_dir / "tiles" / date / mode_dir.name
                dest.mkdir(parents=True, exist_ok=True)
                for png in mode_dir.glob("*.png"):
                    shutil.copy(png, dest / png.name)

        # input tiles: cache_root/<date>/in/<var>_t<t>.png -> fixtures/tiles/<date>/in/ (flat)
        in_dir = cache_tiles / "in"
        if in_dir.exists():
            dest = fixtures_dir / "tiles" / date / "in"
            dest.mkdir(parents=True, exist_ok=True)
            for png in in_dir.glob("*.png"):
                shutil.copy(png, dest / png.name)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="data")
    p.add_argument("--art-dir", default="artifacts")
    p.add_argument("--models", default="lite,gbm")
    p.add_argument("--days", default="all")
    p.add_argument("--fixtures", action="store_true")
    p.add_argument("--fixtures-dir", default=None, help="override; default backend/fixtures")
    p.add_argument("--fallback-dir", default=None, help="override; default frontend/public/fallback")
    args = p.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    settings = Settings(data_dir=args.data_dir, art_dir=args.art_dir, model="lite" if "lite" in models else models[0])
    backend = LiveBackend(args.data_dir, args.art_dir, settings)
    store = backend.engine.store
    dates = _test_dates(store, args.days)

    for model in models:
        for date in dates:
            if not backend.is_cached(date, model):
                backend.run_sync(date, model)
        print(f"cached {len(dates)} days for {model}")

    primary = "lite" if "lite" in models else models[0]
    rmse, bias = _compute_maps(backend, primary, dates)
    maps = _write_report_maps(backend, rmse, bias)

    data_dir = Path(args.data_dir)
    report_path = data_dir / "report.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {
        "headline": {}, "by_depth": {}, "tables": {}, "argo_scatter": {},
        "calibration": {}, "learning_curve": [], "maps": {},
    }
    report["maps"] = maps
    write_report(report, args.data_dir)

    repo_root = Path(__file__).resolve().parent.parent.parent
    fallback_dir = Path(args.fallback_dir) if args.fallback_dir else repo_root / "frontend" / "public" / "fallback"
    _write_fallback(backend, primary, dates, fallback_dir)
    print(f"fallback bundle written to {fallback_dir}")

    if args.fixtures:
        fixtures_dir = Path(args.fixtures_dir) if args.fixtures_dir else Path(__file__).resolve().parent.parent / "fixtures"
        _regenerate_fixtures(backend, primary, dates, fixtures_dir)
        print(f"fixtures regenerated at {fixtures_dir}")


if __name__ == "__main__":
    main()
