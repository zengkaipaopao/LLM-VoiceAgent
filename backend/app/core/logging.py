"""
Logging configuration.
"""
import logging
import sys

from app.core.config import settings


def setup_logging():
    """
    Configure application logging.
    
    Sets up:
    - Console handler for stdout
    - JSON formatting for production
    - Debug level for development
    """
    # Create logger
    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    
    # Formatter
    if settings.environment == "production":
        # JSON format for production (CloudWatch friendly)
        formatter = logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}'
        )
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Create application logger
logger = setup_logging()
