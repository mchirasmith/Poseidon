"""End-to-end: `scripts/run_all.py --synthetic` on a tiny grid, then the live API over its cache."""
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.deps import LiveBackend
from app.main import create_app

REPO_BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def e2e_dirs(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e")
    data_dir, art_dir = root / "data", root / "art"
    fixtures_dir, fallback_dir = root / "fixtures", root / "fallback"

    cmd = [
        sys.executable, "scripts/run_all.py", "--synthetic",
        "--cfg", "configs/tiny.yaml", "--gbm-cfg", "configs/gbm.yaml",
        "--data-dir", str(data_dir), "--art-dir", str(art_dir),
        "--start", "2015-01-01", "--end", "2019-03-31",
        "--ny", "12", "--nx", "16", "--seed", "3",
        "--fixtures-dir", str(fixtures_dir), "--fallback-dir", str(fallback_dir),
    ]
    result = subprocess.run(cmd, cwd=REPO_BACKEND, capture_output=True, text=True, timeout=110)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    return data_dir, art_dir, fixtures_dir, fallback_dir


@pytest.fixture(scope="session")
def e2e_client(e2e_dirs):
    data_dir, art_dir, _fixtures_dir, _fallback_dir = e2e_dirs
    # a single model in the live process avoids ever importing lightgbm alongside
    # torch already imported by other test modules in this pytest session
    settings = Settings(data_dir=str(data_dir), art_dir=str(art_dir), enable_gbm=False, max_jobs=2)
    backend = LiveBackend(str(data_dir), str(art_dir), settings)
    app = create_app(backend=backend, settings=settings)
    with TestClient(app) as c:
        yield c, backend


def _first_test_date(backend: LiveBackend) -> str:
    days = backend.meta().cached_days
    assert days, "precompute must have cached at least one day"
    return sorted(days)[0]


def test_fixtures_and_fallback_written(e2e_dirs):
    _data_dir, _art_dir, fixtures_dir, fallback_dir = e2e_dirs
    assert (fixtures_dir / "meta.json").exists()
    assert json_kind(fixtures_dir) == "synthetic"
    assert (fallback_dir / "meta.json").exists()
    assert (fallback_dir / "report.json").exists()


def json_kind(fixtures_dir: Path) -> str:
    import json

    return json.loads((fixtures_dir / "meta.json").read_text())["fixture_kind"]


def test_gbm_cache_exists_on_disk(e2e_dirs):
    data_dir, _art_dir, _fixtures_dir, _fallback_dir = e2e_dirs
    cache_root = data_dir / "cache"
    gbm_days = list(cache_root.glob("*/gbm/meta.json"))
    assert gbm_days, "precompute should have cached at least one day for gbm"


def test_healthz(e2e_client):
    client, _backend = e2e_client
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_meta_lists_cached_days(e2e_client):
    client, backend = e2e_client
    r = client.get("/api/meta")
    assert r.status_code == 200
    assert len(r.json()["cached_days"]) > 0


def test_run_cached_then_forced(e2e_client):
    client, backend = e2e_client
    date = _first_test_date(backend)

    r = client.post("/api/run", json={"date": date})
    assert r.status_code == 200
    assert r.json()["cached"] is True

    r = client.post("/api/run", json={"date": date, "force": True})
    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is False
    job_id = body["job_id"]

    import time

    for _ in range(200):
        s = client.get(f"/api/run/{job_id}")
        assert s.status_code == 200
        if s.json()["state"] == "done":
            break
        time.sleep(0.1)
    else:
        raise AssertionError("job never finished")


def test_day_shape_and_tiles_reachable(e2e_client):
    client, backend = e2e_client
    date = _first_test_date(backend)
    r = client.get(f"/api/day/{date}")
    assert r.status_code == 200
    body = r.json()
    for mode in ("mean", "sigma", "anom", "error"):
        assert len(body["layers"][mode]) == 15
    tile_url = body["layers"]["mean"][0]
    tile_resp = client.get(tile_url)
    assert tile_resp.status_code == 200
    assert tile_resp.headers["content-type"] == "image/png"

    for var, entry in body["inputs"].items():
        assert len(entry["history"]) == 9
        history_resp = client.get(entry["history"][0])
        assert history_resp.status_code == 200


def test_profile_ocean_cell(e2e_client):
    client, backend = e2e_client
    date = _first_test_date(backend)
    store = backend.engine.store
    ii, jj = (store.wet == 1).nonzero()
    lat, lon = float(store.lat[ii[len(ii) // 2]]), float(store.lon[jj[len(jj) // 2]])
    r = client.get("/api/profile", params={"d": date, "lat": lat, "lon": lon})
    assert r.status_code == 200
    body = r.json()
    assert "scalars" in body
    assert len(body["poseidon_mean"]) == 15


def test_profile_land_cell_422(e2e_client):
    client, backend = e2e_client
    date = _first_test_date(backend)
    store = backend.engine.store
    jj, ii = (store.wet == 0).nonzero()
    if len(jj) == 0:
        pytest.skip("synthetic grid has no land cell")
    lat, lon = float(store.lat[jj[0]]), float(store.lon[ii[0]])
    r = client.get("/api/profile", params={"d": date, "lat": lat, "lon": lon})
    assert r.status_code == 422


def test_section_preset(e2e_client):
    client, backend = e2e_client
    date = _first_test_date(backend)
    store = backend.engine.store
    lat_lo, lat_hi = float(store.lat.min()), float(store.lat.max())
    lon_lo, lon_hi = float(store.lon.min()), float(store.lon.max())
    a = f"{lat_lo + 0.25},{lon_lo + 0.25}"
    b = f"{lat_hi - 0.25},{lon_hi - 0.25}"
    r = client.get("/api/section", params={"d": date, "a": a, "b": b, "n": 20})
    assert r.status_code == 200
    body = r.json()
    assert len(body["distances_km"]) == 20
    assert len(body["poseidon"]) == 20


def test_download_netcdf(e2e_client):
    client, backend = e2e_client
    date = _first_test_date(backend)
    day = client.get(f"/api/day/{date}").json()
    r = client.get(day["netcdf_url"])
    assert r.status_code == 200
    assert r.content[:3] == b"CDF" or r.content[:4] == b"\x89HDF"
