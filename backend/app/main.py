import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from fastapi.exceptions import RequestValidationError
from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.exceptions import AppException
from app.api.errors import (
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
)

setup_logging()
app = FastAPI(title=settings.app_name)
logger = logging.getLogger("app.request")

allowed_origins = settings.cors_origin_list
if settings.environment != "local":
    if not allowed_origins:
        raise RuntimeError("CORS origins must be configured in non-local environments.")
    if "*" in allowed_origins:
        raise RuntimeError("Wildcard CORS origin is not allowed in non-local environments.")

# Register Exception Handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"]
    if settings.environment == "local"
    else ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"]
    if settings.environment == "local"
    else [
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-API-Key",
        "X-CSRF-Token",
    ],
    allow_credentials=True,
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    request.state.request_id = request_id
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/")
async def read_root():
    return {"service": settings.app_name, "status": "ok"}
