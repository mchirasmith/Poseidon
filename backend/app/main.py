"""App factory: CORS, gzip, static mounts, routers and error shaping."""
from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings
from app.deps import Backend, build_live_backend
from app.routers import day, health, meta, profile, report, run, section
from app.schemas.errors import ErrorBody

logger = logging.getLogger("poseidon")


def create_app(backend: Backend | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    backend = backend or build_live_backend(settings)

    app = FastAPI(title="Poseidon API")
    app.state.settings = settings
    app.state.backend = backend

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    tiles_root = backend.tiles_root()
    tiles_root.mkdir(parents=True, exist_ok=True)
    app.mount("/tiles", StaticFiles(directory=tiles_root), name="tiles")

    download_root = backend.download_root()
    download_root.mkdir(parents=True, exist_ok=True)
    app.mount("/download", StaticFiles(directory=download_root), name="download")

    for module in (health, meta, report, run, day, profile, section):
        app.include_router(module.router)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        body = ErrorBody(error=str(exc.detail), detail=None)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        body = ErrorBody(error="invalid request", detail=str(exc))
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error: %s", traceback.format_exc())
        body = ErrorBody(error="inference failed", detail=None)
        return JSONResponse(status_code=500, content=body.model_dump())

    return app
