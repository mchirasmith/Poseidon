"""Backend protocol routers depend on, plus the fixture-backed and live implementations."""
from __future__ import annotations

import json
import time
from datetime import date as date_cls, datetime, timezone
from pathlib import Path
from typing import Protocol

import numpy as np
from fastapi import Depends, HTTPException, Request

from app.config import Settings
from app.schemas.day import Day, InputVar
from app.schemas.health import Health
from app.schemas.meta import CuratedDay, Grid, Meta
from app.schemas.profile import ArgoProfile, Profile, ProfileScalars
from app.schemas.run import RunStart, RunStatus
from app.schemas.section import ArgoMarker, Section
from app.services import cache, derived, tiles
from app.services.argo import ArgoIndex
from app.services.inference import INPUT_VARS, Engine
from app.services.jobs import JobRegistry
from app.services.netcdf import write as write_netcdf
from app.services.section import build as build_section
from app.services.section import nearest_cell
from pipeline.sources import DEPTHS_M, GRID_STEP_DEG


class LandCellError(Exception):
    """Query point falls on a land cell."""


class OutOfRangeError(Exception):
    """Date falls outside the served test range."""


def resolve_model(model: str | None, settings: Settings) -> str:
    """Fill in the default model and reject one not in settings.models_available."""
    model = model or settings.model
    if model not in settings.models_available:
        raise HTTPException(422, "unknown model")
    return model


class Backend(Protocol):
    def meta(self) -> Meta: ...
    def report_path(self) -> Path: ...
    def tiles_root(self) -> Path: ...
    def download_root(self) -> Path: ...
    def is_cached(self, date: str, model: str) -> bool: ...
    async def start_run(self, date: str, model: str, force: bool) -> RunStart: ...
    def run_status(self, job_id: str) -> RunStatus | None: ...
    def day(self, date: str, model: str) -> Day: ...
    def profile(self, date: str, lat: float, lon: float, model: str) -> Profile: ...
    def section(self, date: str, a: tuple[float, float], b: tuple[float, float], n: int, model: str) -> Section: ...
    def health(self) -> Health: ...


class FixtureBackend:
    """Serves canned JSON/PNG fixtures and simulates job progress with delays."""

    STAGES = ("load", "encode", "embed", "decode", "render")

    def __init__(self, fixtures_dir: Path, settings: Settings):
        self.dir = Path(fixtures_dir)
        self.settings = settings
        self._meta_json = json.loads((self.dir / "meta.json").read_text())
        self._wet = json.loads((self.dir / "wet_mask.json").read_text())
        self.jobs = JobRegistry(settings.max_jobs, settings.job_ttl_seconds)

    def meta(self) -> Meta:
        return Meta.model_validate(self._meta_json)

    def report_path(self) -> Path:
        return self.dir / "report.json"

    def tiles_root(self) -> Path:
        return self.dir / "tiles"

    def download_root(self) -> Path:
        return self.dir / "download"

    def _day_dir(self, date: str) -> Path:
        return self.dir / "days" / date

    def is_cached(self, date: str, model: str) -> bool:
        return (self._day_dir(date) / "day.json").exists()

    def _check_range(self, date: str) -> None:
        lo, hi = self._meta_json["test_range"]
        d = date_cls.fromisoformat(date)
        if not (date_cls.fromisoformat(lo) <= d <= date_cls.fromisoformat(hi)):
            raise OutOfRangeError(date)

    async def start_run(self, date: str, model: str, force: bool) -> RunStart:
        self._check_range(date)
        if self.is_cached(date, model) and not force:
            return RunStart(job_id="", cached=True)

        delay_s = self.settings.mock_stage_delay_ms / 1000

        def run(set_stage) -> None:
            for stage in self.STAGES:
                set_stage(stage)
                time.sleep(delay_s)

        job = await self.jobs.start(run)
        return RunStart(job_id=job.id, cached=False)

    def run_status(self, job_id: str) -> RunStatus | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        return RunStatus(
            state=job.state,
            stage=job.stage,
            elapsed_ms=job.elapsed_ms,
            message=job.message,
        )

    def day(self, date: str, model: str) -> Day:
        self._check_range(date)
        path = self._day_dir(date) / "day.json"
        if not path.exists():
            raise FileNotFoundError(date)
        payload = json.loads(path.read_text())
        payload["model"] = model
        return Day.model_validate(payload)

    def _nearest_cell(self, lat: float, lon: float) -> tuple[int, int]:
        grid = self._meta_json["grid"]
        j = round((lat - grid["lat_min"]) / grid["step"])
        i = round((lon - grid["lon_min"]) / grid["step"])
        j = max(0, min(grid["ny"] - 1, j))
        i = max(0, min(grid["nx"] - 1, i))
        return j, i

    def _assert_wet(self, lat: float, lon: float) -> None:
        j, i = self._nearest_cell(lat, lon)
        if not self._wet[j][i]:
            raise LandCellError((lat, lon))

    def profile(self, date: str, lat: float, lon: float, model: str) -> Profile:
        self._check_range(date)
        self._assert_wet(lat, lon)
        path = self._day_dir(date) / "profile.json"
        if not path.exists():
            raise FileNotFoundError(date)
        payload = json.loads(path.read_text())
        payload["lat"] = lat
        payload["lon"] = lon
        return Profile.model_validate(payload)

    def section(self, date: str, a: tuple[float, float], b: tuple[float, float], n: int, model: str) -> Section:
        self._check_range(date)
        self._assert_wet(*a)
        self._assert_wet(*b)
        path = self._day_dir(date) / "section.json"
        if not path.exists():
            raise FileNotFoundError(date)
        payload = json.loads(path.read_text())
        return Section.model_validate(payload)

    def health(self) -> Health:
        return Health(
            status="ok",
            model_version=self._meta_json["model_version"],
            test_range=tuple(self._meta_json["test_range"]),
        )


SCALES_PATH = Path(__file__).resolve().parent.parent / "scales.json"
CURATED_DAYS_FILENAME = "curated_days.json"


class LiveBackend:
    """Backend running the real Engine, caching every reconstruction to disk."""

    STAGES = ("load", "encode", "embed", "decode", "render")

    def __init__(self, data_dir: str | Path, art_dir: str | Path, settings: Settings, scales_path: Path = SCALES_PATH):
        self.settings = settings
        self.data_dir = Path(data_dir)
        self.art_dir = Path(art_dir)
        self.cache_root = self.data_dir / "cache"
        self.engine = Engine(self.data_dir, self.art_dir, scales_path, settings)
        self.jobs = JobRegistry(settings.max_jobs, settings.job_ttl_seconds)
        self.argo_index = ArgoIndex(self.data_dir / "argo_matchups.parquet")

    # -- meta / health --------------------------------------------------

    def meta(self) -> Meta:
        store = self.engine.store
        step = float(np.round(np.median(np.diff(store.lat)), 6)) if len(store.lat) > 1 else GRID_STEP_DEG
        grid = Grid(
            lat_min=float(store.lat.min()), lat_max=float(store.lat.max()),
            lon_min=float(store.lon.min()), lon_max=float(store.lon.max()),
            step=step, ny=store.H, nx=store.W,
        )
        curated_path = self.data_dir / CURATED_DAYS_FILENAME
        curated = json.loads(curated_path.read_text()) if curated_path.exists() else []
        card = self.engine.lite_card
        return Meta(
            model_version=card.get("git_sha", "") or "dev",
            checkpoint=str(self.art_dir / "lite" / "best.pt"),
            test_range=(str(self.settings.test_range[0]), str(self.settings.test_range[1])),
            depths_m=[float(d) for d in DEPTHS_M],
            grid=grid,
            curated_days=[CuratedDay(**c) for c in curated],
            cached_days=cache.list_cached_days(self.cache_root, self.settings.model),
            models_available=self.settings.models_available,
        )

    def health(self) -> Health:
        card = self.engine.lite_card
        return Health(
            status="ok",
            model_version=card.get("git_sha", "") or "dev",
            test_range=(str(self.settings.test_range[0]), str(self.settings.test_range[1])),
        )

    def report_path(self) -> Path:
        return self.data_dir / "report.json"

    def tiles_root(self) -> Path:
        return self.cache_root

    def download_root(self) -> Path:
        return self.cache_root

    def is_cached(self, date: str, model: str) -> bool:
        return cache.exists(self.cache_root, date, model)

    def _check_range(self, date: str) -> None:
        lo, hi = self.settings.test_range
        d = date_cls.fromisoformat(date)
        if not (lo <= d <= hi):
            raise OutOfRangeError(date)

    def _nearest_cell(self, lat: float, lon: float) -> tuple[int, int]:
        return nearest_cell(lat, lon, self.engine.store.lat, self.engine.store.lon)

    def _assert_wet(self, lat: float, lon: float) -> None:
        j, i = self._nearest_cell(lat, lon)
        if not self.engine.store.wet[j, i]:
            raise LandCellError((lat, lon))

    # -- run / cache write ------------------------------------------------

    async def start_run(self, date: str, model: str, force: bool) -> RunStart:
        self._check_range(date)
        if self.is_cached(date, model) and not force:
            return RunStart(job_id="", cached=True)

        def runner(set_stage) -> None:
            t0 = time.monotonic()
            result = self.engine.run(date, model, set_stage)
            set_stage("render")
            self._write_cache(date, model, result, int((time.monotonic() - t0) * 1000))

        job = await self.jobs.start(runner)
        return RunStart(job_id=job.id, cached=False)

    def run_sync(self, date: str, model: str) -> None:
        """Run and cache one day without the job registry; used by precompute and the runner."""
        t0 = time.monotonic()
        result = self.engine.run(date, model, lambda stage: None)
        self._write_cache(date, model, result, int((time.monotonic() - t0) * 1000))

    def run_status(self, job_id: str) -> RunStatus | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        return RunStatus(state=job.state, stage=job.stage, elapsed_ms=job.elapsed_ms, message=job.message)

    def _write_cache(self, date: str, model: str, result: dict, runtime_ms: int) -> None:
        store = self.engine.store
        wet, bottom = result["wet"].astype(bool), result["bottom"]
        scales = self.engine.scales

        layers: dict[str, list[str]] = {}
        per_depth_scales: dict[str, list[tuple[float, float]]] = {}
        for mode, arr in (("mean", result["mean"]), ("sigma", result["sigma"]), ("anom", result["anomaly"]), ("error", result["error"])):
            if arr is None:
                continue
            urls, ranges = [], []
            for zi in range(arr.shape[0]):
                path = cache.tile_path(self.cache_root, date, model, mode, zi)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(tiles.render(arr[zi], mode, scales, wet, bottom[zi].astype(bool)))
                urls.append(f"/tiles/{date}/{model}/{mode}/z{zi:02d}.png")
                finite = arr[zi][np.isfinite(arr[zi])]
                ranges.append([float(finite.min()), float(finite.max())] if finite.size else [0.0, 0.0])
            layers[mode] = urls
            per_depth_scales[mode] = ranges

        inputs: dict[str, dict] = {}
        for var in INPUT_VARS:
            history_arr = result["inputs"][var]
            history_urls = []
            for k, t_off in enumerate(range(-(len(history_arr) - 1), 1)):
                path = cache.input_tile_path(self.cache_root, date, var, t_off)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(tiles.render(history_arr[k], mode_for_input(var), scales, wet))
                history_urls.append(f"/tiles/{date}/in/{var}_t{t_off}.png")
            finite = history_arr[-1][np.isfinite(history_arr[-1])]
            inputs[var] = InputVar(
                tile=history_urls[-1],
                range=[float(finite.min()), float(finite.max())] if finite.size else [0.0, 0.0],
                missing_fraction=result["input_missing"][var],
                history=history_urls,
            ).model_dump()

        fields_path = cache.fields_path(self.cache_root, date, model)
        fields_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            fields_path,
            mean=result["mean"], anom=result["anomaly"], error=result["error"],
            sigma=result["sigma"] if result["sigma"] is not None else np.array([]),
            p10=result["p10"] if result["p10"] is not None else np.array([]),
            p90=result["p90"] if result["p90"] is not None else np.array([]),
            glorys=result["y_raw"],
        )

        card = self.engine.lite_card if model != "gbm" else self.engine.gbm_card
        nc_path = cache.netcdf_path(self.cache_root, date, model)
        write_netcdf(
            nc_path, date, store.lat, store.lon, DEPTHS_M, wet.astype(np.uint8), bottom,
            result["mean"], result["sigma"], result["p10"], result["p90"], result["anomaly"],
            attrs=self._netcdf_attrs(model, card),
        )

        meta = {
            "date": date,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "runtime_ms": runtime_ms,
            "inputs": inputs,
            "layers": layers,
            "scales": {m: [scales[m]["vmin"], scales[m]["vmax"]] for m in layers},
            "per_depth_scales": per_depth_scales,
            "netcdf_url": f"/download/{date}/{model}/{nc_path.name}",
        }
        cache.write_meta(self.cache_root, date, model, meta)

    def _netcdf_attrs(self, model: str, card: dict) -> dict:
        store = self.engine.store
        lo, hi = self.settings.test_range
        return {
            "title": "Poseidon subsurface temperature reconstruction",
            "institution": "Poseidon",
            "source": "OSTIA, DUACS, GLORYS, OSCAR, CCMP",
            "model_name": f"poseidon-{model}",
            "model_version": card.get("git_sha", "") or "dev",
            "git_sha": card.get("git_sha", ""),
            "config_hash": card.get("config_hash", ""),
            "data_hash": card.get("data_hash", store.root.attrs.get("data_hash", "")),
            "calibration_alphas": str(card.get("calibration_alphas", [])),
            "training_period": str(card.get("train_years", [])),
            "test_period": f"{lo}/{hi}",
            "history": f"created {datetime.now(timezone.utc).isoformat()} by poseidon backend",
            "references": "https://marine.copernicus.eu",
            "geospatial_lat_min": float(store.lat.min()), "geospatial_lat_max": float(store.lat.max()),
            "geospatial_lon_min": float(store.lon.min()), "geospatial_lon_max": float(store.lon.max()),
            "time_coverage_start": str(lo), "time_coverage_end": str(hi),
        }

    # -- reads -----------------------------------------------------------

    def day(self, date: str, model: str) -> Day:
        self._check_range(date)
        if not self.is_cached(date, model):
            raise FileNotFoundError(date)
        payload = cache.read_meta(self.cache_root, date, model)
        payload["model"] = model
        return Day.model_validate(payload)

    def profile(self, date: str, lat: float, lon: float, model: str) -> Profile:
        self._check_range(date)
        self._assert_wet(lat, lon)
        if not self.is_cached(date, model):
            raise FileNotFoundError(date)
        j, i = self._nearest_cell(lat, lon)
        fields = np.load(cache.fields_path(self.cache_root, date, model))
        depths = [float(d) for d in DEPTHS_M]

        def col(name: str) -> list[float | None]:
            arr = fields[name]
            if arr.size == 0:
                return [None] * len(depths)
            return [None if np.isnan(v) else float(v) for v in arr[:, j, i]]

        mean_col = col("mean")
        glorys_col = col("glorys")
        rmse_glorys = _rmse(mean_col, glorys_col)

        gbm_col = None
        if self.settings.enable_gbm and model != "gbm" and self.is_cached(date, "gbm"):
            gbm_fields = np.load(cache.fields_path(self.cache_root, date, "gbm"))
            gbm_col = [None if np.isnan(v) else float(v) for v in gbm_fields["mean"][:, j, i]]

        argo = self.argo_index.nearest(date, lat, lon, self.settings.argo_max_km, self.settings.argo_max_days)
        rmse_argo = None
        if argo is not None:
            rmse_argo = _rmse(mean_col, argo["temp"])

        mean_arr = np.array([np.nan if v is None else v for v in mean_col])
        depths_arr = np.array(depths)
        d20 = derived.d20(depths_arr, mean_arr)
        d26 = derived.d26(depths_arr, mean_arr)
        mld = derived.mld(depths_arr, mean_arr)

        return Profile(
            lat=lat, lon=lon, depths_m=depths,
            poseidon_mean=mean_col, poseidon_p10=col("p10"), poseidon_p90=col("p90"),
            glorys=glorys_col, gbm=gbm_col,
            argo=ArgoProfile(**argo) if argo is not None else None,
            scalars=ProfileScalars(
                d20_m=None if np.isnan(d20) else float(d20),
                d26_m=None if np.isnan(d26) else float(d26),
                mld_m=None if np.isnan(mld) else float(mld),
                rmse_glorys=rmse_glorys, rmse_argo=rmse_argo,
            ),
        )

    def section(self, date: str, a: tuple[float, float], b: tuple[float, float], n: int, model: str) -> Section:
        self._check_range(date)
        self._assert_wet(*a)
        self._assert_wet(*b)
        if not self.is_cached(date, model):
            raise FileNotFoundError(date)
        fields = np.load(cache.fields_path(self.cache_root, date, model))
        sigma = fields["sigma"] if fields["sigma"].size else None
        payload = build_section(
            a, b, n, self.engine.store.lat, self.engine.store.lon, DEPTHS_M,
            fields["mean"], sigma, fields["glorys"],
            self.argo_index, date, self.settings.argo_max_km, self.settings.argo_max_days,
        )
        return Section(argo_markers=[ArgoMarker(**m) for m in payload.pop("argo_markers")], **payload)


def mode_for_input(var: str) -> str:
    """Input tiles reuse the physical-quantity colour scales, keyed by display var name."""
    return {"cur": "cur", "wind": "wind"}.get(var, var)


def _rmse(pred: list[float | None], true: list[float | None]) -> float | None:
    pairs = [(p, t) for p, t in zip(pred, true) if p is not None and t is not None]
    if not pairs:
        return None
    diffs = np.array([p - t for p, t in pairs])
    return float(np.sqrt(np.mean(diffs**2)))


def build_live_backend(settings: Settings) -> Backend:
    return LiveBackend(settings.data_dir, settings.art_dir, settings)


def get_backend(request: Request) -> Backend:
    return request.app.state.backend


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def require_model(model: str | None = None, settings: Settings = Depends(get_settings)) -> str:
    return resolve_model(model, settings)
