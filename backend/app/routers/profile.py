"""Single-point vertical profile."""
from fastapi import APIRouter, Depends, HTTPException

from app.deps import Backend, LandCellError, OutOfRangeError, get_backend, require_model
from app.routers.run import DATE_RE
from app.schemas.profile import Profile

router = APIRouter()


@router.get("/api/profile", response_model=Profile)
def get_profile(
    d: str,
    lat: float,
    lon: float,
    model: str = Depends(require_model),
    backend: Backend = Depends(get_backend),
) -> Profile:
    if not DATE_RE.match(d):
        raise HTTPException(400, "bad date")
    try:
        return backend.profile(d, lat, lon, model)
    except OutOfRangeError:
        raise HTTPException(422, "date outside test range")
    except LandCellError:
        raise HTTPException(422, "land cell")
    except FileNotFoundError:
        raise HTTPException(404, "day not cached")
