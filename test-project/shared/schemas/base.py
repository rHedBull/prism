"""Pydantic base schemas for API responses and shared data structures.

All service APIs should inherit from these base schemas to maintain
consistent response envelopes across the platform.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class TenantContext(BaseModel):
    """Tenant identity and context injected by auth middleware.

    Attributes:
        tenant_id: Unique tenant identifier (UUID).
        tenant_slug: URL-safe tenant slug for routing.
        plan: Subscription plan tier.
        features: Feature flags enabled for this tenant.
    """

    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    tenant_slug: str = ""
    plan: str = "free"
    features: list[str] = Field(default_factory=list)

    @property
    def is_paid(self) -> bool:
        """Return True if the tenant is on a paid plan."""
        return self.plan not in ("free", "trial")


class ErrorDetail(BaseModel):
    """A single validation or business-logic error."""

    field: str | None = None
    message: str
    code: str = "validation_error"


class ErrorResponse(BaseModel):
    """Standard error response envelope.

    Attributes:
        error: Machine-readable error code.
        detail: Human-readable error description.
        errors: Optional list of field-level error details.
        request_id: Request ID for support and debugging.
        timestamp: UTC timestamp of the error.
    """

    error: str
    detail: str
    errors: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BaseResponse(BaseModel, Generic[T]):
    """Standard successful response envelope.

    Wraps any response data in a consistent structure with metadata.

    Attributes:
        data: The response payload.
        meta: Optional metadata dict (timing, version, etc.).
        request_id: Request ID echoed from the middleware.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    data: T
    meta: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata included in paginated responses."""

    page: int = Field(ge=1, description="Current page number (1-indexed).")
    page_size: int = Field(ge=1, le=200, description="Items per page.")
    total_items: int = Field(ge=0, description="Total number of items across all pages.")
    total_pages: int = Field(ge=0, description="Total number of pages.")
    has_next: bool = False
    has_previous: bool = False

    @field_validator("total_pages", mode="before")
    @classmethod
    def _compute_total_pages(cls, v: int, info: Any) -> int:
        """Auto-compute total_pages if not explicitly set."""
        if v is not None and v >= 0:
            return v
        data = info.data if hasattr(info, "data") else {}
        total = data.get("total_items", 0)
        size = data.get("page_size", 20)
        return max(1, -(-total // size))  # Ceiling division


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response envelope for list endpoints.

    Attributes:
        data: List of items for the current page.
        pagination: Pagination metadata.
        meta: Optional extra metadata.
        request_id: Request ID echoed from the middleware.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    data: list[T]
    pagination: PaginationMeta
    meta: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None

    @classmethod
    def create(
        cls,
        items: list[T],
        total_items: int,
        page: int,
        page_size: int,
        **meta: Any,
    ) -> PaginatedResponse[T]:
        """Factory method for building a paginated response.

        Args:
            items: Items for the current page.
            total_items: Total item count across all pages.
            page: Current page number (1-indexed).
            page_size: Number of items per page.
            **meta: Additional metadata key-value pairs.

        Returns:
            A fully populated :class:`PaginatedResponse`.
        """
        total_pages = max(1, -(-total_items // page_size))

        return cls(
            data=items,
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_previous=page > 1,
            ),
            meta=meta,
        )


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = "ok"
    service: str
    version: str
    uptime_seconds: float
    checks: dict[str, bool] = Field(default_factory=dict)


class BulkOperationResult(BaseModel):
    """Result summary for bulk create/update/delete operations."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[ErrorDetail] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Return the success rate as a float between 0.0 and 1.0."""
        if self.total == 0:
            return 1.0
        return self.succeeded / self.total
