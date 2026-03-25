"""
Common dependencies for FastAPI endpoints.
"""
from typing import AsyncGenerator, Generator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.database import AsyncSessionLocal, SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency for API handlers."""
    async with AsyncSessionLocal() as db:
        yield db


def get_sync_db() -> Generator[Session, None, None]:
    """Sync database session dependency for legacy scripts/endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
