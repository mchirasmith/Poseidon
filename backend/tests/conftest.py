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


@pytest.fixture(scope="session")
def synthetic_store(tmp_path_factory) -> Path:
    """Small, fast synthetic pipeline output shared by the pipeline test suite."""
    from pipeline import synthetic

    out_dir = tmp_path_factory.mktemp("synthetic")
    # 2015-01-01..2016-12-31 gives two full train years, so per-cell climatology has full-month coverage
    synthetic.generate(out_dir, "2015-01-01", "2019-03-31", 12, 24, seed=7)
    return out_dir


@pytest.fixture(scope="session")
def synthetic_trained_lite(tmp_path_factory) -> tuple[Path, Path]:
    """Synthetic store + a tiny trained/exported poseidon-lite, built via subprocess stages.

    Runs as subprocesses (like scripts/run_all.py) so torch never shares this pytest
    process with any other test module that imports it.
    """
    import subprocess
    import sys

    root = tmp_path_factory.mktemp("lite_engine")
    data_dir, art_dir = root / "data", root / "art"
    backend_dir = Path(__file__).resolve().parent.parent
    cmd = [
        sys.executable, "scripts/run_all.py", "--synthetic",
        "--cfg", "configs/tiny.yaml",
        "--data-dir", str(data_dir), "--art-dir", str(art_dir),
        "--start", "2015-01-01", "--end", "2019-03-31",
        "--ny", "12", "--nx", "16", "--seed", "5",
        "--only", "data,nn,calibrate,export_lite",
    ]
    result = subprocess.run(cmd, cwd=backend_dir, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    return data_dir, art_dir
