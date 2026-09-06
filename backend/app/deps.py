"""Backend protocol routers depend on, plus the fixture-backed implementation."""
from __future__ import annotations

import json
import time
from datetime import date as date_cls
from pathlib import Path
from typing import Protocol

from fastapi import Depends, HTTPException, Request

from app.config import Settings
from app.schemas.day import Day
from app.schemas.health import Health
from app.schemas.meta import Meta
from app.schemas.profile import Profile
from app.schemas.run import RunStart, RunStatus
from app.schemas.section import Section
from app.services.jobs import JobRegistry


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


def build_live_backend(settings: Settings) -> Backend:
    raise NotImplementedError(
        "the live backend is not implemented yet; run with a FixtureBackend "
        "(see backend/mock.py) until the inference services land"
    )


def get_backend(request: Request) -> Backend:
    return request.app.state.backend


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def require_model(model: str | None = None, settings: Settings = Depends(get_settings)) -> str:
    return resolve_model(model, settings)
