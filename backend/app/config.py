"""Environment-driven settings for the Poseidon API."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

STANDARD_DEPTHS_M = [0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000]


def _split_comma(value: Any) -> Any:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def _split_dates(value: Any) -> Any:
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        return (date.fromisoformat(parts[0]), date.fromisoformat(parts[1]))
    return value


CommaSeparated = Annotated[list[str], NoDecode, BeforeValidator(_split_comma)]
DateRange = Annotated[tuple[date, date], NoDecode, BeforeValidator(_split_dates)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSEIDON_")

    data_dir: str = "./data"
    art_dir: str = "./artifacts"
    model: str = "lite"
    enable_gbm: bool = True
    device: str = "cpu"
    cors_origins: CommaSeparated = ["*"]
    test_range: DateRange = (date(2019, 1, 1), date(2020, 12, 31))
    max_jobs: int = 2

    # job registry
    job_ttl_seconds: int = 600
    poll_interval_ms: int = 300

    # argo matchup tolerances
    argo_max_km: float = 55.0
    argo_max_days: float = 2.0

    # mock server
    mock_stage_delay_ms: int = 250

    @property
    def models_available(self) -> list[str]:
        models = [self.model]
        if self.enable_gbm:
            models.append("gbm")
        return models
