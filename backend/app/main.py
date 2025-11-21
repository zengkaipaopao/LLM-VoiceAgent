from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)

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
