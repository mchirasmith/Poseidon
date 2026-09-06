"""Serves the frozen evaluation report; gzip applied by the app-level middleware."""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.deps import Backend, get_backend

router = APIRouter()


@router.get("/api/report")
def get_report(backend: Backend = Depends(get_backend)) -> FileResponse:
    return FileResponse(backend.report_path(), media_type="application/json")
