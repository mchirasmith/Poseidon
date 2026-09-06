"""Route shapes and status codes against the FixtureBackend."""
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.deps import FixtureBackend
from app.main import create_app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
DATE = "2020-05-18"


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_meta(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert "lite" in body["models_available"]
    assert body["grid"]["ny"] > 0


def test_report(client):
    r = client.get("/api/report")
    assert r.status_code == 200
    assert "headline" in r.json()


def test_run_bad_date(client):
    r = client.post("/api/run", json={"date": "not-a-date"})
    assert r.status_code == 400
    assert set(r.json().keys()) == {"error", "detail"}


def test_run_out_of_range(client):
    r = client.post("/api/run", json={"date": "2000-01-01"})
    assert r.status_code == 422


def test_run_cached_and_poll_to_done(client):
    r = client.post("/api/run", json={"date": DATE, "force": True})
    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is False
    job_id = body["job_id"]

    for _ in range(100):
        s = client.get(f"/api/run/{job_id}")
        assert s.status_code == 200
        if s.json()["state"] == "done":
            break
        time.sleep(0.02)
    else:
        raise AssertionError("job never finished")


def test_run_cached_without_force(client):
    r = client.post("/api/run", json={"date": DATE, "force": False})
    assert r.status_code == 200
    assert r.json()["cached"] is True


def test_run_unknown_job(client):
    r = client.get("/api/run/does-not-exist")
    assert r.status_code == 404


def test_run_busy():
    settings = Settings(max_jobs=1, mock_stage_delay_ms=500, job_ttl_seconds=600)
    backend = FixtureBackend(FIXTURES_DIR, settings)
    app = create_app(backend=backend, settings=settings)
    with TestClient(app) as busy_client:
        r1 = busy_client.post("/api/run", json={"date": DATE, "force": True})
        r2 = busy_client.post("/api/run", json={"date": "2020-01-15", "force": True})
    assert r1.status_code == 200
    assert r2.status_code == 429
    assert r2.json() == {"error": "too many concurrent runs", "detail": None}


def test_day_bad_date(client):
    r = client.get("/api/day/nope")
    assert r.status_code == 400


def test_day_uncached(client):
    r = client.get("/api/day/2019-03-03")
    assert r.status_code == 404


def test_day_out_of_range(client):
    r = client.get("/api/day/2010-01-01")
    assert r.status_code == 422


def test_day_ok(client):
    r = client.get(f"/api/day/{DATE}")
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "lite"
    assert "wind" in body["inputs"]
    assert len(body["layers"]["mean"]) == 15


def test_profile_ok(client, backend):
    grid = backend.meta().grid
    lat = grid.lat_min + (grid.ny // 2) * grid.step
    lon = grid.lon_min + (grid.nx // 2) * grid.step
    r = client.get("/api/profile", params={"d": DATE, "lat": lat, "lon": lon})
    assert r.status_code == 200
    body = r.json()
    assert "poseidon_mean" in body
    assert "poseidon_p10" in body
    assert "poseidon_p90" in body


def test_profile_land_cell(client, backend):
    grid = backend.meta().grid
    r = client.get("/api/profile", params={"d": DATE, "lat": grid.lat_min, "lon": grid.lon_min})
    assert r.status_code == 422


def test_section_ok(client, backend):
    grid = backend.meta().grid
    a = f"{grid.lat_min + 2 * grid.step},{grid.lon_min + 2 * grid.step}"
    b = f"{grid.lat_max - 2 * grid.step},{grid.lon_max - 2 * grid.step}"
    r = client.get("/api/section", params={"d": DATE, "a": a, "b": b, "n": 10})
    assert r.status_code == 200
    body = r.json()
    assert len(body["poseidon"]) == len(body["distances_km"])


def test_error_body_shape(client):
    r = client.get("/api/day/bad")
    assert r.status_code == 400
    body = r.json()
    assert set(body.keys()) == {"error", "detail"}
    assert isinstance(body["error"], str)


def test_missing_tiles_path_returns_error_body(client):
    r = client.get("/tiles/does-not-exist.png")
    assert r.status_code == 404
    assert set(r.json().keys()) == {"error", "detail"}


def test_day_unknown_model(client):
    r = client.get(f"/api/day/{DATE}", params={"model": "not-a-model"})
    assert r.status_code == 422
    assert set(r.json().keys()) == {"error", "detail"}


def test_profile_uncached_day(client, backend):
    grid = backend.meta().grid
    lat = grid.lat_min + (grid.ny // 2) * grid.step
    lon = grid.lon_min + (grid.nx // 2) * grid.step
    r = client.get("/api/profile", params={"d": "2019-03-03", "lat": lat, "lon": lon})
    assert r.status_code == 404
    assert r.json()["error"] == "day not cached"


def test_section_uncached_day(client, backend):
    grid = backend.meta().grid
    a = f"{grid.lat_min + 2 * grid.step},{grid.lon_min + 2 * grid.step}"
    b = f"{grid.lat_max - 2 * grid.step},{grid.lon_max - 2 * grid.step}"
    r = client.get("/api/section", params={"d": "2019-03-03", "a": a, "b": b, "n": 10})
    assert r.status_code == 404
    assert r.json()["error"] == "day not cached"
