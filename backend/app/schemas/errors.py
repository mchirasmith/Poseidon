"""Shape of every error response the API returns."""
from pydantic import BaseModel


class ErrorBody(BaseModel):
    error: str
    detail: str | None = None
