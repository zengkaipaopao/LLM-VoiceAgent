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


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int

class PaginatedMetaWrapper(BaseModel):
    pagination: PaginationMeta

class PaginatedResponse(BaseModel, Generic[DataT]):
    """
    Paginated response model.
    """
    success: bool = True
    message: str = "Success"
    data: list[DataT]
    meta: PaginatedMetaWrapper
