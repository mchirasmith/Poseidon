"""Evaluation report payload; served as a static file, schema kept for reference and tests."""
from typing import Any

from pydantic import BaseModel


class Report(BaseModel):
    headline: dict[str, Any]
    by_depth: dict[str, Any]
    maps: dict[str, Any]
    argo_scatter: list[Any] = []
    calibration: dict[str, Any] = {}
    tables: dict[str, Any] = {}
    learning_curve: dict[str, Any] = {}
