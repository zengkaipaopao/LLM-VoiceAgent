"""Error handlers for FastAPI application."""
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions import AppException


def _error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
):
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    content = {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "meta": {"request_id": request_id} if request_id else None,
        "message": message,
    }
    return JSONResponse(status_code=status_code, content=content)


async def app_exception_handler(request: Request, exc: AppException):
    """
    Handle custom application exceptions.
    
    Args:
        request: FastAPI request
        exc: Application exception
        
    Returns:
        JSON response with error details
    """
    return _error_response(
        request=request,
        status_code=exc.status_code,
        code=f"APP_{exc.status_code}",
        message=exc.message,
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
    return _error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Validation error",
        details={"errors": exc.errors()},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Normalize FastAPI HTTPException payload to the common envelope."""
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    details = exc.detail if not isinstance(exc.detail, str) else None
    return _error_response(
        request=request,
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        message=detail,
        details=details,
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
    return _error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="Internal server error",
    )
