"""Core Pydantic models for mcp-refcache.

Defines the data structures for cache references, responses,
and configuration options.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SizeMode(str, Enum):
    """How to measure size for context limiting."""

    TOKEN = "token"  # Count tokens (accurate for LLM context)
    CHARACTER = "character"  # Count characters (faster)


class PreviewStrategy(str, Enum):
    """Strategy for generating previews of large values."""

    TRUNCATE = "truncate"  # Stringify and cut at limit
    PAGINATE = "paginate"  # Split into pages, each respects limit
    SAMPLE = "sample"  # Pick evenly-spaced items, output respects limit


class PreviewConfig(BaseModel):
    """Configuration for context limiting behavior."""

    size_mode: SizeMode = Field(
        default=SizeMode.TOKEN,
        description="How to measure size (tokens or characters).",
    )
    max_size: int = Field(
        default=1000,
        description="Maximum size in tokens or characters.",
        gt=0,
    )
    default_strategy: PreviewStrategy = Field(
        default=PreviewStrategy.SAMPLE,
        description="Default strategy for generating previews.",
    )


class CacheReference(BaseModel):
    """Reference to a cached value.

    This is what gets returned to agents instead of the full value.
    The agent can use this reference to:
    - Paginate through the data
    - Pass to another tool (server resolves it)
    - Request the full value (if permitted)
    """

    ref_id: str = Field(
        description="Unique identifier for this cached value.",
    )
    cache_name: str = Field(
        description="Name of the cache containing this value.",
    )
    namespace: str = Field(
        default="public",
        description="Namespace for isolation and access control.",
    )
    tool_name: str | None = Field(
        default=None,
        description="Name of the tool that created this reference.",
    )
    created_at: float = Field(
        description="Unix timestamp when the reference was created.",
    )
    expires_at: float | None = Field(
        default=None,
        description="Unix timestamp when the reference expires (None = never).",
    )

    # Metadata about the cached value
    total_items: int | None = Field(
        default=None,
        description="Total number of items if value is a collection.",
    )
    total_size: int | None = Field(
        default=None,
        description="Total size in bytes of the cached value.",
    )
    total_tokens: int | None = Field(
        default=None,
        description="Estimated token count of the full value.",
    )


class PaginatedResponse(BaseModel):
    """Response containing a page of data with navigation info."""

    items: list[Any] = Field(
        description="Items in the current page.",
    )
    page: int = Field(
        description="Current page number (1-indexed).",
        ge=1,
    )
    page_size: int = Field(
        description="Number of items per page.",
        ge=1,
    )
    total_items: int = Field(
        description="Total number of items across all pages.",
        ge=0,
    )
    total_pages: int = Field(
        description="Total number of pages.",
        ge=0,
    )
    has_next: bool = Field(
        description="Whether there are more pages after this one.",
    )
    has_previous: bool = Field(
        description="Whether there are pages before this one.",
    )

    @classmethod
    def from_list(
        cls,
        items: list[Any],
        page: int = 1,
        page_size: int = 20,
    ) -> "PaginatedResponse":
        """Create a paginated response from a list."""
        total_items = len(items)
        total_pages = (
            (total_items + page_size - 1) // page_size if total_items > 0 else 0
        )
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = items[start_idx:end_idx]

        return cls(
            items=page_items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )


class CacheResponse(BaseModel):
    """Standard response format for cached values.

    Combines reference metadata with preview/value data.
    This is what MCP tools should return for large responses.
    """

    # Reference info (always present)
    ref_id: str = Field(
        description="Reference ID for accessing the cached value.",
    )
    cache_name: str = Field(
        description="Name of the cache containing this value.",
    )
    namespace: str = Field(
        default="public",
        description="Namespace for isolation.",
    )

    # Metadata about the full value
    total_items: int | None = Field(
        default=None,
        description="Total number of items if value is a collection.",
    )
    total_tokens: int | None = Field(
        default=None,
        description="Estimated token count of the full value.",
    )

    # Size metadata from PreviewResult
    original_size: int | None = Field(
        default=None,
        description="Size of the original value (in tokens or characters).",
    )
    preview_size: int | None = Field(
        default=None,
        description="Size of the preview (in tokens or characters).",
    )

    # The preview (structured, not stringified!)
    preview: Any = Field(
        description="Preview of the value (structured data, respects size limit).",
    )
    preview_strategy: PreviewStrategy = Field(
        description="Strategy used to generate the preview.",
    )

    # Pagination info (if applicable)
    page: int | None = Field(
        default=None,
        description="Current page number (if paginated).",
    )
    total_pages: int | None = Field(
        default=None,
        description="Total pages available (if paginated).",
    )

    # What can the agent do next?
    available_actions: list[str] = Field(
        default_factory=lambda: ["get_page", "resolve_full", "pass_to_tool"],
        description="Actions available to the agent.",
    )
