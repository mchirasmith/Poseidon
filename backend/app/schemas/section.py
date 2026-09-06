"""Vertical section along a lat/lon line."""
from pydantic import BaseModel


class ArgoMarker(BaseModel):
    distance_km: float
    wmo: str


class Section(BaseModel):
    distances_km: list[float]
    lats: list[float]
    lons: list[float]
    depths_m: list[float]
    poseidon: list[list[float | None]]
    glorys: list[list[float | None]]
    sigma: list[list[float | None]]
    d20_m: list[float | None]
    mld_m: list[float | None]
    argo_markers: list[ArgoMarker]
