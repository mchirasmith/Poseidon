"""Start and poll a reconstruction job."""
import re

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings
from app.deps import Backend, OutOfRangeError, get_backend, get_settings, resolve_model
from app.schemas.run import RunRequest, RunStart, RunStatus
from app.services.jobs import Busy

router = APIRouter()
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@router.post("/api/run", response_model=RunStart)
async def start_run(
    body: RunRequest,
    backend: Backend = Depends(get_backend),
    settings: Settings = Depends(get_settings),
) -> RunStart:
    if not DATE_RE.match(body.date):
        raise HTTPException(400, "bad date")
    model = resolve_model(body.model, settings)
    try:
        return await backend.start_run(body.date, model, body.force)
    except OutOfRangeError:
        raise HTTPException(422, "date outside test range")
    except Busy:
        raise HTTPException(429, "too many concurrent runs")


@router.get("/api/run/{job_id}", response_model=RunStatus)
def run_status(job_id: str, backend: Backend = Depends(get_backend)) -> RunStatus:
    status = backend.run_status(job_id)
    if status is None:
        raise HTTPException(404, "unknown job")
    return status
