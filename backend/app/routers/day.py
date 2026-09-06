"""Cached-day reconstruction payload."""
from fastapi import APIRouter, Depends, HTTPException

from app.deps import Backend, OutOfRangeError, get_backend, require_model
from app.routers.run import DATE_RE
from app.schemas.day import Day

router = APIRouter()


@router.get("/api/day/{date}", response_model=Day)
def get_day(
    date: str,
    model: str = Depends(require_model),
    backend: Backend = Depends(get_backend),
) -> Day:
    if not DATE_RE.match(date):
        raise HTTPException(400, "bad date")
    try:
        return backend.day(date, model)
    except OutOfRangeError:
        raise HTTPException(422, "date outside test range")
    except FileNotFoundError:
        raise HTTPException(404, "day not cached")
