"""Base response schemas."""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


DataT = TypeVar("DataT")


class ApiError(BaseModel):
    """Standardized API error payload."""

    code: str
    message: str
    details: Any | None = None


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class PaginatedMetaWrapper(BaseModel):
    pagination: PaginationMeta


class ResponseMeta(BaseModel):
    request_id: str | None = None


class ResponseBase(BaseModel, Generic[DataT]):
    """Base response model for all API responses."""

    success: bool = True
    data: DataT | None = None
    meta: ResponseMeta | dict[str, Any] | None = None
    error: ApiError | None = None
    # Backward compatible field; prefer error.message for failures.
    message: str | None = Field(default="Success")


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Paginated response model."""

    success: bool = True
    message: str = "Success"
    data: list[DataT]
    meta: PaginatedMetaWrapper
