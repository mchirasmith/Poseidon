"""Single-point vertical profile response."""
from pydantic import BaseModel


class ArgoProfile(BaseModel):
    wmo: str
    distance_km: float
    day_offset: int
    depths_m: list[float]
    temp: list[float | None]


class ProfileScalars(BaseModel):
    d20_m: float | None
    d26_m: float | None
    mld_m: float | None
    rmse_glorys: float | None
    rmse_argo: float | None


class Profile(BaseModel):
    lat: float
    lon: float
    depths_m: list[float]
    poseidon_mean: list[float | None]
    poseidon_p10: list[float | None]
    poseidon_p90: list[float | None]
    glorys: list[float | None]
    gbm: list[float | None] | None = None
    argo: ArgoProfile | None = None
    scalars: ProfileScalars
