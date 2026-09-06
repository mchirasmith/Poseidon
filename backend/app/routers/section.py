"""Vertical section along a lat/lon line."""
from fastapi import APIRouter, Depends, HTTPException

from app.deps import Backend, LandCellError, OutOfRangeError, get_backend, require_model
from app.routers.run import DATE_RE
from app.schemas.section import Section

router = APIRouter()


def _parse_point(raw: str) -> tuple[float, float]:
    lat_s, lon_s = raw.split(",")
    return float(lat_s), float(lon_s)


@router.get("/api/section", response_model=Section)
def get_section(
    d: str,
    a: str,
    b: str,
    n: int = 200,
    model: str = Depends(require_model),
    backend: Backend = Depends(get_backend),
) -> Section:
    if not DATE_RE.match(d):
        raise HTTPException(400, "bad date")
    try:
        a_pt = _parse_point(a)
        b_pt = _parse_point(b)
    except ValueError:
        raise HTTPException(400, "bad point")
    try:
        return backend.section(d, a_pt, b_pt, n, model)
    except OutOfRangeError:
        raise HTTPException(422, "date outside test range")
    except LandCellError:
        raise HTTPException(422, "land cell")
    except FileNotFoundError:
        raise HTTPException(404, "day not cached")
