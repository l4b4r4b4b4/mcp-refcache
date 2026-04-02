"""Preview generators for context limiting.

This module provides strategies for generating previews of large values
that fit within size constraints (tokens or characters).

Generators:
    - SampleGenerator: Binary search + evenly-spaced sampling for collections
    - PaginateGenerator: Page-based splitting for sequential access
    - TruncateGenerator: String truncation (escape hatch for plain text)

Example:
    ```python
    from mcp_refcache.preview import SampleGenerator, get_default_generator
    from mcp_refcache.context import CharacterMeasurer
    from mcp_refcache.models import PreviewStrategy

    measurer = CharacterMeasurer()
    generator = SampleGenerator()

    # Sample a large list to fit within 100 characters
    result = generator.generate(
        value=list(range(1000)),
        max_size=100,
        measurer=measurer,
    )
    print(result.preview)  # [0, 111, 222, ...]
    print(result.sampled_items)  # ~5 items
    ```
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from mcp_refcache.models import PreviewStrategy

if TYPE_CHECKING:
    from mcp_refcache.context import SizeMeasurer

# =============================================================================
# PreviewResult
# =============================================================================


@dataclass
class PreviewResult:
    """Result of preview generation.

    Contains the preview data along with metadata about the original value
    and how it was transformed.

    Attributes:
        preview: The preview data (structured, not stringified for sample/paginate).
        strategy: The strategy used to generate this preview.
        original_size: Size of the original value (in tokens or characters).
        preview_size: Size of the preview (in tokens or characters).
        total_items: Total items in original collection (None for non-collections).
        sampled_items: Number of items in the preview (None for non-collections).
        page: Current page number for pagination (None if not paginated).
        total_pages: Total pages available (None if not paginated).
    """

    preview: Any
    strategy: PreviewStrategy
    original_size: int
    preview_size: int
    total_items: int | None
    sampled_items: int | None
    page: int | None
    total_pages: int | None


# =============================================================================
# PreviewGenerator Protocol
# =============================================================================


@runtime_checkable
class PreviewGenerator(Protocol):
    """Protocol for preview generation strategies.

    Implementations transform large values into smaller previews that fit
    within size constraints while preserving as much useful information
    as possible.
    """

    def generate(
        self,
        value: Any,
        max_size: int,
        measurer: SizeMeasurer,
        page: int | None = None,
        page_size: int | None = None,
    ) -> PreviewResult:
        """Generate a preview of a value within size constraints.

        Args:
            value: The value to create a preview of.
            max_size: Maximum size in tokens or characters.
            measurer: SizeMeasurer to measure value sizes.
            page: Page number for pagination (1-indexed, optional).
            page_size: Items per page for pagination (optional).

        Returns:
            PreviewResult with the preview and metadata.
        """
        ...


# =============================================================================
# SampleGenerator
# =============================================================================


class SampleGenerator:
    """Sample evenly-spaced items to fit within size limit.

    Uses binary search to find the maximum number of items that fit within
    the size constraint, then samples them at even intervals from the
    original collection.

    For lists: samples evenly-spaced elements.
    For dicts: samples evenly-spaced key-value pairs.
    For strings: truncates with ellipsis.
    For other types: returns as-is if fits, otherwise JSON-truncates.

    Example:
        ```python
        generator = SampleGenerator()
        measurer = CharacterMeasurer()

        # Sample 1000 items down to ~10 that fit in 100 chars
        result = generator.generate(list(range(1000)), max_size=100, measurer=measurer)
        print(result.preview)  # [0, 111, 222, 333, ...]
        ```
    """

    def generate(
        self,
        value: Any,
        max_size: int,
        measurer: SizeMeasurer,
        page: int | None = None,
        page_size: int | None = None,
    ) -> PreviewResult:
        """Generate a sampled preview.

        Args:
            value: The value to sample.
            max_size: Maximum size in tokens or characters.
            measurer: SizeMeasurer to measure value sizes.
            page: Ignored for sample strategy.
            page_size: Ignored for sample strategy.

        Returns:
            PreviewResult with sampled preview.
        """
        original_size = measurer.measure(value)

        # Handle different types
        if isinstance(value, list):
            return self._sample_list(value, max_size, measurer, original_size)
        elif isinstance(value, tuple):
            result = self._sample_list(list(value), max_size, measurer, original_size)
            # Convert back to list for JSON compatibility
            return result
        elif isinstance(value, dict):
            return self._sample_dict(value, max_size, measurer, original_size)
        elif isinstance(value, str):
            return self._truncate_string(value, max_size, measurer, original_size)
        else:
            # For other types, check if it fits
            if original_size <= max_size:
                return PreviewResult(
                    preview=value,
                    strategy=PreviewStrategy.SAMPLE,
                    original_size=original_size,
                    preview_size=original_size,
                    total_items=None,
                    sampled_items=None,
                    page=None,
                    total_pages=None,
                )
            # Try to stringify and truncate
            return self._truncate_string(
                json.dumps(value, default=str), max_size, measurer, original_size
            )

    def _sample_list(
        self,
        items: list[Any],
        max_size: int,
        measurer: SizeMeasurer,
        original_size: int,
    ) -> PreviewResult:
        """Sample a list to fit within max_size."""
        total_items = len(items)

        if total_items == 0:
            return PreviewResult(
                preview=[],
                strategy=PreviewStrategy.SAMPLE,
                original_size=original_size,
                preview_size=measurer.measure([]),
                total_items=0,
                sampled_items=0,
                page=None,
                total_pages=None,
            )

        # Check if full list fits
        if original_size <= max_size:
            return PreviewResult(
                preview=items,
                strategy=PreviewStrategy.SAMPLE,
                original_size=original_size,
                preview_size=original_size,
                total_items=total_items,
                sampled_items=total_items,
                page=None,
                total_pages=None,
            )

        # Binary search for optimal count
        target_count = self._find_target_count(items, max_size, measurer)

        # Sample evenly spaced items
        sampled = self._sample_evenly(items, target_count)
        preview_size = measurer.measure(sampled)

        return PreviewResult(
            preview=sampled,
            strategy=PreviewStrategy.SAMPLE,
            original_size=original_size,
            preview_size=preview_size,
            total_items=total_items,
            sampled_items=len(sampled),
            page=None,
            total_pages=None,
        )

    def _sample_dict(
        self,
        value: dict[Any, Any],
        max_size: int,
        measurer: SizeMeasurer,
        original_size: int,
    ) -> PreviewResult:
        """Sample a dict to fit within max_size."""
        total_items = len(value)

        if total_items == 0:
            return PreviewResult(
                preview={},
                strategy=PreviewStrategy.SAMPLE,
                original_size=original_size,
                preview_size=measurer.measure({}),
                total_items=0,
                sampled_items=0,
                page=None,
                total_pages=None,
            )

        # Check if full dict fits
        if original_size <= max_size:
            return PreviewResult(
                preview=value,
                strategy=PreviewStrategy.SAMPLE,
                original_size=original_size,
                preview_size=original_size,
                total_items=total_items,
                sampled_items=total_items,
                page=None,
                total_pages=None,
            )

        # Convert to list of tuples for sampling
        items = list(value.items())
        target_count = self._find_target_count_dict(value, max_size, measurer)

        # Sample evenly spaced items
        sampled_items = self._sample_evenly(items, target_count)
        sampled = dict(sampled_items)
        preview_size = measurer.measure(sampled)

        return PreviewResult(
            preview=sampled,
            strategy=PreviewStrategy.SAMPLE,
            original_size=original_size,
            preview_size=preview_size,
            total_items=total_items,
            sampled_items=len(sampled),
            page=None,
            total_pages=None,
        )

    def _truncate_string(
        self,
        value: str,
        max_size: int,
        measurer: SizeMeasurer,
        original_size: int,
    ) -> PreviewResult:
        """Truncate a string to fit within max_size."""
        if original_size <= max_size:
            return PreviewResult(
                preview=value,
                strategy=PreviewStrategy.TRUNCATE,
                original_size=original_size,
                preview_size=original_size,
                total_items=len(value),
                sampled_items=len(value),
                page=None,
                total_pages=None,
            )

        # Binary search for optimal length
        low, high = 0, len(value)
        best_length = 0
        ellipsis = "..."

        while low <= high:
            mid = (low + high) // 2
            truncated = value[:mid] + ellipsis
            size = measurer.measure(truncated)

            if size <= max_size:
                best_length = mid
                low = mid + 1
            else:
                high = mid - 1

        truncated = (
            value[:best_length] + ellipsis if best_length < len(value) else value
        )
        preview_size = measurer.measure(truncated)

        return PreviewResult(
            preview=truncated,
            strategy=PreviewStrategy.TRUNCATE,
            original_size=original_size,
            preview_size=preview_size,
            total_items=len(value),
            sampled_items=best_length,
            page=None,
            total_pages=None,
        )

    def _find_target_count(
        self,
        items: list[Any],
        max_size: int,
        measurer: SizeMeasurer,
    ) -> int:
        """Binary search to find how many items fit within max_size."""
        low, high = 1, len(items)
        result = 1

        while low <= high:
            mid = (low + high) // 2
            sampled = self._sample_evenly(items, mid)
            size = measurer.measure(sampled)

            if size <= max_size:
                result = mid
                low = mid + 1
            else:
                high = mid - 1

        return result

    def _find_target_count_dict(
        self,
        value: dict[Any, Any],
        max_size: int,
        measurer: SizeMeasurer,
    ) -> int:
        """Binary search to find how many dict items fit within max_size."""
        items = list(value.items())
        low, high = 1, len(items)
        result = 1

        while low <= high:
            mid = (low + high) // 2
            sampled_items = self._sample_evenly(items, mid)
            sampled = dict(sampled_items)
            size = measurer.measure(sampled)

            if size <= max_size:
                result = mid
                low = mid + 1
            else:
                high = mid - 1

        return result

    def _sample_evenly(self, items: list[Any], count: int) -> list[Any]:
        """Sample count items evenly spaced from the list."""
        if count >= len(items):
            return items
        if count <= 0:
            return []
        if count == 1:
            return [items[0]]

        step = (len(items) - 1) / (count - 1)
        return [items[round(i * step)] for i in range(count)]


# =============================================================================
# PaginateGenerator
# =============================================================================


class PaginateGenerator:
    """Split values into pages for sequential access.

    Each page respects the max_size limit. Good for when users want to
    iterate through data in chunks.

    Example:
        ```python
        generator = PaginateGenerator()
        measurer = CharacterMeasurer()

        result = generator.generate(
            value=list(range(100)),
            max_size=500,
            measurer=measurer,
            page=1,
            page_size=10,
        )
        print(result.preview)  # [0, 1, 2, ..., 9]
        print(result.total_pages)  # 10
        ```
    """

    DEFAULT_PAGE_SIZE = 20

    def generate(
        self,
        value: Any,
        max_size: int,
        measurer: SizeMeasurer,
        page: int | None = None,
        page_size: int | None = None,
    ) -> PreviewResult:
        """Generate a paginated preview.

        Args:
            value: The value to paginate.
            max_size: Maximum size in tokens or characters.
            measurer: SizeMeasurer to measure value sizes.
            page: Page number (1-indexed, defaults to 1).
            page_size: Items per page (defaults to 20).

        Returns:
            PreviewResult with the page and pagination metadata.
        """
        page = page or 1
        page_size = page_size or self.DEFAULT_PAGE_SIZE
        original_size = measurer.measure(value)

        if isinstance(value, list):
            return self._paginate_list(
                value, max_size, measurer, original_size, page, page_size
            )
        elif isinstance(value, tuple):
            return self._paginate_list(
                list(value), max_size, measurer, original_size, page, page_size
            )
        elif isinstance(value, dict):
            return self._paginate_dict(
                value, max_size, measurer, original_size, page, page_size
            )
        else:
            # For non-collection types, treat as single-page
            return PreviewResult(
                preview=value,
                strategy=PreviewStrategy.PAGINATE,
                original_size=original_size,
                preview_size=original_size,
                total_items=1,
                sampled_items=1,
                page=1,
                total_pages=1,
            )

    def _paginate_list(
        self,
        items: list[Any],
        max_size: int,
        measurer: SizeMeasurer,
        original_size: int,
        page: int,
        page_size: int,
    ) -> PreviewResult:
        """Paginate a list."""
        total_items = len(items)
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        # Calculate page slice
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = items[start_idx:end_idx]

        # Trim page if it exceeds max_size
        if page_items:
            page_items = self._trim_to_fit(page_items, max_size, measurer)

        preview_size = measurer.measure(page_items)

        return PreviewResult(
            preview=page_items,
            strategy=PreviewStrategy.PAGINATE,
            original_size=original_size,
            preview_size=preview_size,
            total_items=total_items,
            sampled_items=len(page_items),
            page=page,
            total_pages=total_pages,
        )

    def _paginate_dict(
        self,
        value: dict[Any, Any],
        max_size: int,
        measurer: SizeMeasurer,
        original_size: int,
        page: int,
        page_size: int,
    ) -> PreviewResult:
        """Paginate a dict."""
        items = list(value.items())
        total_items = len(items)
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        # Calculate page slice
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = items[start_idx:end_idx]

        # Convert back to dict
        page_dict = dict(page_items)

        # Trim if exceeds max_size
        if page_dict:
            page_dict = self._trim_dict_to_fit(page_dict, max_size, measurer)

        preview_size = measurer.measure(page_dict)

        return PreviewResult(
            preview=page_dict,
            strategy=PreviewStrategy.PAGINATE,
            original_size=original_size,
            preview_size=preview_size,
            total_items=total_items,
            sampled_items=len(page_dict),
            page=page,
            total_pages=total_pages,
        )

    def _trim_to_fit(
        self,
        items: list[Any],
        max_size: int,
        measurer: SizeMeasurer,
    ) -> list[Any]:
        """Trim list to fit within max_size."""
        if measurer.measure(items) <= max_size:
            return items

        # Binary search for how many items fit
        low, high = 0, len(items)
        result = 0

        while low <= high:
            mid = (low + high) // 2
            trimmed = items[:mid]
            if measurer.measure(trimmed) <= max_size:
                result = mid
                low = mid + 1
            else:
                high = mid - 1

        return items[:result]

    def _trim_dict_to_fit(
        self,
        value: dict[Any, Any],
        max_size: int,
        measurer: SizeMeasurer,
    ) -> dict[Any, Any]:
        """Trim dict to fit within max_size."""
        if measurer.measure(value) <= max_size:
            return value

        items = list(value.items())
        low, high = 0, len(items)
        result = 0

        while low <= high:
            mid = (low + high) // 2
            trimmed = dict(items[:mid])
            if measurer.measure(trimmed) <= max_size:
                result = mid
                low = mid + 1
            else:
                high = mid - 1

        return dict(items[:result])


# =============================================================================
# TruncateGenerator
# =============================================================================


class TruncateGenerator:
    """Truncate values as strings with ellipsis.

    This is the escape hatch for when structured sampling isn't appropriate.
    Values are JSON-serialized and then truncated to fit the limit.

    Example:
        ```python
        generator = TruncateGenerator()
        measurer = CharacterMeasurer()

        result = generator.generate("a" * 1000, max_size=50, measurer=measurer)
        print(result.preview)  # "aaaaaaa..."
        ```
    """

    def generate(
        self,
        value: Any,
        max_size: int,
        measurer: SizeMeasurer,
        page: int | None = None,
        page_size: int | None = None,
    ) -> PreviewResult:
        """Generate a truncated preview.

        Args:
            value: The value to truncate.
            max_size: Maximum size in tokens or characters.
            measurer: SizeMeasurer to measure value sizes.
            page: Ignored for truncate strategy.
            page_size: Ignored for truncate strategy.

        Returns:
            PreviewResult with truncated string preview.
        """
        # Convert to string if not already
        if isinstance(value, str):
            text = value
            total_items = len(value)
        else:
            text = json.dumps(value, default=str)
            total_items = self._count_items(value)

        original_size = measurer.measure(text)

        # Check if it fits
        if original_size <= max_size:
            return PreviewResult(
                preview=value if isinstance(value, str) else text,
                strategy=PreviewStrategy.TRUNCATE,
                original_size=original_size,
                preview_size=original_size,
                total_items=total_items,
                sampled_items=total_items,
                page=None,
                total_pages=None,
            )

        # Binary search for optimal truncation point
        low, high = 0, len(text)
        best_length = 0
        ellipsis = "..."

        while low <= high:
            mid = (low + high) // 2
            truncated = text[:mid] + ellipsis
            size = measurer.measure(truncated)

            if size <= max_size:
                best_length = mid
                low = mid + 1
            else:
                high = mid - 1

        truncated = text[:best_length] + ellipsis
        preview_size = measurer.measure(truncated)

        return PreviewResult(
            preview=truncated,
            strategy=PreviewStrategy.TRUNCATE,
            original_size=original_size,
            preview_size=preview_size,
            total_items=total_items,
            sampled_items=best_length,
            page=None,
            total_pages=None,
        )

    def _count_items(self, value: Any) -> int | None:
        """Count items in a collection."""
        if isinstance(value, (list, tuple, set, frozenset)):
            return len(value)
        if isinstance(value, dict):
            return len(value)
        return None


# =============================================================================
# Factory Function
# =============================================================================


def get_default_generator(strategy: PreviewStrategy) -> PreviewGenerator:
    """Get a default PreviewGenerator for the given strategy.

    Args:
        strategy: The preview strategy to use.

    Returns:
        A PreviewGenerator implementation.

    Example:
        ```python
        generator = get_default_generator(PreviewStrategy.SAMPLE)
        result = generator.generate(value, max_size=100, measurer=measurer)
        ```
    """
    if strategy == PreviewStrategy.SAMPLE:
        return SampleGenerator()
    elif strategy == PreviewStrategy.PAGINATE:
        return PaginateGenerator()
    elif strategy == PreviewStrategy.TRUNCATE:
        return TruncateGenerator()
    else:
        # Default to sample
        return SampleGenerator()


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "PaginateGenerator",
    "PreviewGenerator",
    "PreviewResult",
    "SampleGenerator",
    "TruncateGenerator",
    "get_default_generator",
]
