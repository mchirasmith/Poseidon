"""Request/response shapes for starting and polling a reconstruction job."""
from pydantic import BaseModel


class RunRequest(BaseModel):
    date: str
    force: bool = False
    model: str | None = None


class RunStart(BaseModel):
    job_id: str
    cached: bool


class RunStatus(BaseModel):
    state: str
    stage: str | None
    elapsed_ms: int
    message: str | None = None
