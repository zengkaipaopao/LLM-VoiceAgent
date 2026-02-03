"""
Common dependencies for FastAPI endpoints.
"""
from typing import Generator
from sqlalchemy.orm import Session
from app.core.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.
    
    Yields:
        Database session
        
    Example:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
