"""Shared fixtures: a FixtureBackend app instance for route tests."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.deps import FixtureBackend
from app.main import create_app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def settings() -> Settings:
    return Settings(max_jobs=2, mock_stage_delay_ms=5, job_ttl_seconds=600)


@pytest.fixture
def backend(settings: Settings) -> FixtureBackend:
    return FixtureBackend(FIXTURES_DIR, settings)


@pytest.fixture
def client(backend: FixtureBackend, settings: Settings) -> TestClient:
    app = create_app(backend=backend, settings=settings)
    with TestClient(app) as c:
        yield c
