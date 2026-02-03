"""
Base schemas for Pydantic models.
"""
from pydantic import BaseModel
from typing import Optional, Any, Generic, TypeVar


DataT = TypeVar('DataT')


class ResponseBase(BaseModel, Generic[DataT]):
    """
    Base response model for all API responses.
    
    Attributes:
        success: Whether the request was successful
        message: Response message
        data: Response data
    """
    success: bool = True
    message: str = "Success"
    data: Optional[DataT] = None


class PaginatedResponse(BaseModel, Generic[DataT]):
    """
    Paginated response model.
    
    Attributes:
        items: List of items
        total: Total number of items
        page: Current page number
        page_size: Number of items per page
        total_pages: Total number of pages
    """
    items: list[DataT]
    total: int
    page: int
    page_size: int
    total_pages: int
