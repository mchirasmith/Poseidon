"""Env-var parsing for Settings: dates, comma lists, defaults."""
from datetime import date

from app.config import Settings


def test_defaults():
    s = Settings()
    assert s.model == "lite"
    assert s.enable_gbm is True
    assert s.max_jobs == 2
    assert s.test_range == (date(2019, 1, 1), date(2020, 12, 31))
    assert s.cors_origins == ["*"]


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("POSEIDON_MODEL", "gbm")
    monkeypatch.setenv("POSEIDON_CORS_ORIGINS", "https://a.com, https://b.com")
    monkeypatch.setenv("POSEIDON_TEST_RANGE", "2015-01-01,2016-06-30")
    monkeypatch.setenv("POSEIDON_MAX_JOBS", "5")
    s = Settings()
    assert s.model == "gbm"
    assert s.cors_origins == ["https://a.com", "https://b.com"]
    assert s.test_range == (date(2015, 1, 1), date(2016, 6, 30))
    assert s.max_jobs == 5


def test_models_available():
    s = Settings(model="lite", enable_gbm=True)
    assert s.models_available == ["lite", "gbm"]
    s2 = Settings(model="lite", enable_gbm=False)
    assert s2.models_available == ["lite"]
