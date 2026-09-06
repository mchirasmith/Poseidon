"""Static model/grid metadata."""
from fastapi import APIRouter, Depends

from app.deps import Backend, get_backend
from app.schemas.meta import Meta

router = APIRouter()


@router.get("/api/meta", response_model=Meta)
def get_meta(backend: Backend = Depends(get_backend)) -> Meta:
    return backend.meta()
