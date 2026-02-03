"""
Database configuration and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,      # Enable connection health checks
    pool_size=5,              # Connection pool size
    max_overflow=10,          # Maximum overflow connections
    pool_recycle=3600,        # Recycle connections after 1 hour
    echo=settings.debug       # Log SQL queries in debug mode
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create base class for models
Base = declarative_base()


# Dependency for FastAPI
def get_db():
    """
    Database session dependency for FastAPI.
    
    Yields:
        Session: SQLAlchemy database session
        
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
