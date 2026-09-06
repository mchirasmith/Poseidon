"""Liveness and version check."""
from fastapi import APIRouter, Depends

from app.deps import Backend, get_backend
from app.schemas.health import Health

router = APIRouter()


@router.get("/healthz", response_model=Health)
def healthz(backend: Backend = Depends(get_backend)) -> Health:
    return backend.health()
