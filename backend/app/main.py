from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.exceptions import RequestValidationError
from app.api.routes import api_router
from app.core.config import settings
from app.exceptions import AppException
from app.api.errors import (
    app_exception_handler,
    validation_exception_handler,
    general_exception_handler
)

app = FastAPI(title=settings.app_name)

# Register Exception Handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"]
    if settings.environment == "local"
    else ["GET", "POST", "PUT", "PATCH"],
    allow_headers=["*"]
    if settings.environment == "local"
    else ["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
async def read_root():
    return {"service": settings.app_name, "status": "ok"}
