"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.config import settings
from app.core.exceptions import AppException
from app.db.session import close_db, init_db
from app.services.ocr_service import initialize_ocr, close_ocr
from app.services.startup_seed import run_startup_seed

logger = logging.getLogger("app.http")
logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize and close shared application resources."""
    # Initialize database
    await init_db()
    await run_startup_seed()

    # Initialize OCR engine if enabled
    if settings.ocr_enabled:
        try:
            initialize_ocr()
        except Exception as exc:
            if settings.ocr_required:
                raise
            logger.warning(
                "OCR initialization warning (continuing without OCR): %s",
                exc,
            )
            logger.warning(
                "OCR features will be disabled. This is expected in CPU-only environments."
            )

    yield

    # Shutdown
    await close_db()
    close_ocr()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log HTTP method, path, status and latency for each request."""
    started_at = perf_counter()
    try:
        response = await call_next(request)
        duration_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000
        logger.exception(
            "%s %s -> 500 (%.1fms)",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    """Lightweight liveness probe."""
    return {"status": "ok"}


@app.exception_handler(AppException)
async def handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
    """Map domain exceptions to a consistent API response."""
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code in {"UNAUTHORIZED", "INVALID_TOKEN"}:
        status_code = status.HTTP_401_UNAUTHORIZED
    elif exc.code in {"FORBIDDEN"}:
        status_code = status.HTTP_403_FORBIDDEN
    elif exc.code in {"NOT_FOUND", "USER_NOT_FOUND"}:
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code in {"CONFLICT", "EMAIL_ALREADY_EXISTS"}:
        status_code = status.HTTP_409_CONFLICT

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
            },
        },
    )
