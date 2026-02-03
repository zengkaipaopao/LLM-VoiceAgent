"""
Error handlers for FastAPI application.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.exceptions import AppException


async def app_exception_handler(request: Request, exc: AppException):
    """
    Handle custom application exceptions.
    
    Args:
        request: FastAPI request
        exc: Application exception
        
    Returns:
        JSON response with error details
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "data": None
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors.
    
    Args:
        request: FastAPI request
        exc: Validation error
        
    Returns:
        JSON response with validation error details
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation error",
            "data": {"errors": exc.errors()}
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle general exceptions.
    
    Args:
        request: FastAPI request
        exc: Exception
        
    Returns:
        JSON response with error message
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "data": None
        }
    )
