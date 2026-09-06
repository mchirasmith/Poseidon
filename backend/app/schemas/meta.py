"""Static metadata about the model and grid, shown once at load."""
from pydantic import BaseModel


class Grid(BaseModel):
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    step: float
    ny: int
    nx: int


class CuratedDay(BaseModel):
    date: str
    label: str


class Meta(BaseModel):
    model_version: str
    checkpoint: str
    test_range: tuple[str, str]
    depths_m: list[float]
    grid: Grid
    curated_days: list[CuratedDay]
    cached_days: list[str]
    models_available: list[str]
