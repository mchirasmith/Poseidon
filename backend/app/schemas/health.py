"""Health check response."""
from pydantic import BaseModel


class Health(BaseModel):
    status: str
    model_version: str
    test_range: tuple[str, str]
