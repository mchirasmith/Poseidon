"""Cached-day payload: input tiles, output layers, colour scales."""
from pydantic import BaseModel


class InputVar(BaseModel):
    tile: str
    range: tuple[float, float]
    missing_fraction: float
    history: list[str]


class Day(BaseModel):
    date: str
    model: str
    cached_at: str
    runtime_ms: int
    inputs: dict[str, InputVar]
    layers: dict[str, list[str]]
    scales: dict[str, tuple[float, float]]
    per_depth_scales: dict[str, list[tuple[float, float]]]
    netcdf_url: str
