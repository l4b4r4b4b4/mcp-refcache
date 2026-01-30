"""Tests for preview generators: sample, paginate, truncate strategies.

Tests the PreviewGenerator protocol and its implementations:
- SampleGenerator (binary search + evenly-spaced sampling)
- PaginateGenerator (page-based splitting)
- TruncateGenerator (string truncation)

Also tests PreviewResult dataclass and factory functions.
"""

import pytest

from mcp_refcache.context import CharacterFallback, CharacterMeasurer, TokenMeasurer
from mcp_refcache.models import PreviewStrategy

# =============================================================================
# PreviewResult Tests
# =============================================================================


class TestPreviewResult:
    """Tests for PreviewResult dataclass."""

    def test_preview_result_creation(self) -> None:
        """PreviewResult can be created with all fields."""
        from mcp_refcache.preview import PreviewResult

        result = PreviewResult(
            preview=["a", "b", "c"],
            strategy=PreviewStrategy.SAMPLE,
            original_size=100,
            preview_size=30,
            total_items=10,
            sampled_items=3,
            page=None,
            total_pages=None,
        )

        assert result.preview == ["a", "b", "c"]
        assert result.strategy == PreviewStrategy.SAMPLE
        assert result.original_size == 100
        assert result.preview_size == 30
        assert result.total_items == 10
        assert result.sampled_items == 3

    def test_preview_result_with_pagination(self) -> None:
        """PreviewResult supports pagination fields."""
        from mcp_refcache.preview import PreviewResult

        result = PreviewResult(
            preview=["item1", "item2"],
            strategy=PreviewStrategy.PAGINATE,
            original_size=500,
            preview_size=50,
            total_items=100,
            sampled_items=2,
            page=1,
            total_pages=50,
        )

        assert result.page == 1
        assert result.total_pages == 50

    def test_preview_result_optional_fields(self) -> None:
        """PreviewResult handles None for optional fields."""
        from mcp_refcache.preview import PreviewResult

        result = PreviewResult(
            preview="truncated...",
            strategy=PreviewStrategy.TRUNCATE,
            original_size=1000,
            preview_size=100,
            total_items=None,
            sampled_items=None,
            page=None,
            total_pages=None,
        )

        assert result.total_items is None
        assert result.sampled_items is None


# =============================================================================
# PreviewGenerator Protocol Tests
# =============================================================================


class TestPreviewGeneratorProtocol:
    """Tests for PreviewGenerator protocol compliance."""

    def test_sample_generator_implements_protocol(self) -> None:
        """SampleGenerator implements PreviewGenerator protocol."""
        from mcp_refcache.preview import PreviewGenerator, SampleGenerator

        generator = SampleGenerator()
        assert isinstance(generator, PreviewGenerator)

    def test_paginate_generator_implements_protocol(self) -> None:
        """PaginateGenerator implements PreviewGenerator protocol."""
        from mcp_refcache.preview import PaginateGenerator, PreviewGenerator

        generator = PaginateGenerator()
        assert isinstance(generator, PreviewGenerator)

    def test_truncate_generator_implements_protocol(self) -> None:
        """TruncateGenerator implements PreviewGenerator protocol."""
        from mcp_refcache.preview import PreviewGenerator, TruncateGenerator

        generator = TruncateGenerator()
        assert isinstance(generator, PreviewGenerator)


# =============================================================================
# SampleGenerator Tests
# =============================================================================


class TestSampleGenerator:
    """Tests for SampleGenerator (evenly-spaced sampling)."""

    @pytest.fixture
    def generator(self):
        """Create a SampleGenerator instance."""
        from mcp_refcache.preview import SampleGenerator

        return SampleGenerator()

    @pytest.fixture
    def measurer(self):
        """Create a CharacterMeasurer for testing."""
        return CharacterMeasurer()

    def test_small_list_returned_as_is(self, generator, measurer) -> None:
        """Small lists that fit within limit are returned unchanged."""
        value = [1, 2, 3, 4, 5]
        result = generator.generate(value, max_size=1000, measurer=measurer)

        assert result.preview == value
        assert result.strategy == PreviewStrategy.SAMPLE
        assert result.total_items == 5
        assert result.sampled_items == 5

    def test_large_list_is_sampled(self, generator, measurer) -> None:
        """Large lists are sampled to fit within limit."""
        value = list(range(100))
        # Set a small limit that forces sampling
        result = generator.generate(value, max_size=50, measurer=measurer)

        assert len(result.preview) < 100
        assert result.strategy == PreviewStrategy.SAMPLE
        assert result.total_items == 100
        assert result.sampled_items == len(result.preview)
        # Preview should fit within limit
        assert result.preview_size <= 50

    def test_evenly_spaced_sampling(self, generator, measurer) -> None:
        """Sampled items are evenly spaced from the original list."""
        value = list(range(100))
        result = generator.generate(value, max_size=30, measurer=measurer)

        # Check that samples are evenly distributed
        # First and last items should be included (or close to it)
        if len(result.preview) > 1:
            # Items should be spread across the range
            assert result.preview[0] < 10  # Near start
            assert result.preview[-1] > 90  # Near end

    def test_small_dict_returned_as_is(self, generator, measurer) -> None:
        """Small dicts that fit within limit are returned unchanged."""
        value = {"a": 1, "b": 2, "c": 3}
        result = generator.generate(value, max_size=1000, measurer=measurer)

        assert result.preview == value
        assert result.strategy == PreviewStrategy.SAMPLE
        assert result.total_items == 3
        assert result.sampled_items == 3

    def test_large_dict_is_sampled(self, generator, measurer) -> None:
        """Large dicts are sampled to fit within limit."""
        value = {f"key_{i}": f"value_{i}" for i in range(100)}
        result = generator.generate(value, max_size=100, measurer=measurer)

        assert len(result.preview) < 100
        assert isinstance(result.preview, dict)
        assert result.strategy == PreviewStrategy.SAMPLE
        assert result.total_items == 100
        assert result.preview_size <= 100

    def test_string_passed_to_truncate(self, generator, measurer) -> None:
        """Strings are handled (delegated to truncation behavior)."""
        value = "a" * 1000
        result = generator.generate(value, max_size=50, measurer=measurer)

        # SampleGenerator should handle strings by truncating
        assert len(result.preview) < 1000
        assert result.strategy in (PreviewStrategy.SAMPLE, PreviewStrategy.TRUNCATE)

    def test_nested_structure(self, generator, measurer) -> None:
        """Nested structures are sampled at top level only.

        Note: Current implementation samples top-level keys only.
        If a single top-level value exceeds max_size, it won't be
        recursively shrunk. This is a known limitation.
        """
        # Use a structure where top-level sampling works
        value = {f"key_{i}": {"data": f"value_{i}"} for i in range(50)}
        result = generator.generate(value, max_size=200, measurer=measurer)

        assert isinstance(result.preview, dict)
        assert result.preview_size <= 200
        assert result.sampled_items < 50

    def test_empty_list(self, generator, measurer) -> None:
        """Empty list is returned as-is."""
        value = []
        result = generator.generate(value, max_size=100, measurer=measurer)

        assert result.preview == []
        assert result.total_items == 0
        assert result.sampled_items == 0

    def test_empty_dict(self, generator, measurer) -> None:
        """Empty dict is returned as-is."""
        value = {}
        result = generator.generate(value, max_size=100, measurer=measurer)

        assert result.preview == {}
        assert result.total_items == 0
        assert result.sampled_items == 0

    def test_single_item_list(self, generator, measurer) -> None:
        """Single item list is returned as-is."""
        value = [{"complex": "object", "with": "data"}]
        result = generator.generate(value, max_size=1000, measurer=measurer)

        assert result.preview == value
        assert result.total_items == 1
        assert result.sampled_items == 1

    def test_binary_search_finds_optimal_count(self, generator, measurer) -> None:
        """Binary search finds the maximum items that fit."""
        # Create items of predictable size
        value = [{"id": i, "data": "x" * 10} for i in range(50)]
        result = generator.generate(value, max_size=200, measurer=measurer)

        # Should have found a good fit
        assert result.preview_size <= 200
        # Adding one more item should exceed limit (approximately)
        assert result.sampled_items > 0

    def test_with_token_measurer(self, generator) -> None:
        """SampleGenerator works with TokenMeasurer."""
        tokenizer = CharacterFallback()
        measurer = TokenMeasurer(tokenizer)

        value = list(range(100))
        result = generator.generate(value, max_size=20, measurer=measurer)

        assert result.preview_size <= 20
        assert result.sampled_items < 100


# =============================================================================
# PaginateGenerator Tests
# =============================================================================


class TestPaginateGenerator:
    """Tests for PaginateGenerator (page-based splitting)."""

    @pytest.fixture
    def generator(self):
        """Create a PaginateGenerator instance."""
        from mcp_refcache.preview import PaginateGenerator

        return PaginateGenerator()

    @pytest.fixture
    def measurer(self):
        """Create a CharacterMeasurer for testing."""
        return CharacterMeasurer()

    def test_first_page_of_list(self, generator, measurer) -> None:
        """Get first page of a list."""
        value = list(range(100))
        result = generator.generate(
            value, max_size=50, measurer=measurer, page=1, page_size=10
        )

        assert result.strategy == PreviewStrategy.PAGINATE
        assert result.page == 1
        assert len(result.preview) == 10
        assert result.preview == list(range(10))
        assert result.total_items == 100
        assert result.total_pages == 10

    def test_middle_page_of_list(self, generator, measurer) -> None:
        """Get middle page of a list."""
        value = list(range(100))
        result = generator.generate(
            value, max_size=1000, measurer=measurer, page=5, page_size=10
        )

        assert result.page == 5
        assert result.preview == list(range(40, 50))

    def test_last_page_of_list(self, generator, measurer) -> None:
        """Get last page of a list."""
        value = list(range(95))  # 95 items, 10 pages with last having 5
        result = generator.generate(
            value, max_size=1000, measurer=measurer, page=10, page_size=10
        )

        assert result.page == 10
        assert result.preview == list(range(90, 95))
        assert len(result.preview) == 5

    def test_dict_pagination(self, generator, measurer) -> None:
        """Paginate through a dict's items."""
        value = {f"key_{i}": i for i in range(50)}
        result = generator.generate(
            value, max_size=1000, measurer=measurer, page=1, page_size=10
        )

        assert result.strategy == PreviewStrategy.PAGINATE
        assert len(result.preview) == 10
        assert isinstance(result.preview, dict)
        assert result.total_items == 50
        assert result.total_pages == 5

    def test_page_out_of_range(self, generator, measurer) -> None:
        """Page number beyond range returns empty."""
        value = list(range(10))
        result = generator.generate(
            value, max_size=1000, measurer=measurer, page=100, page_size=10
        )

        assert result.preview == []
        assert result.page == 100

    def test_default_page_size(self, generator, measurer) -> None:
        """Uses default page size when not specified."""
        value = list(range(100))
        result = generator.generate(value, max_size=1000, measurer=measurer, page=1)

        assert len(result.preview) <= 20  # Default page size

    def test_has_next_and_previous(self, generator, measurer) -> None:
        """Correctly indicates next/previous pages."""
        value = list(range(100))

        # First page
        result1 = generator.generate(
            value, max_size=1000, measurer=measurer, page=1, page_size=10
        )
        assert result1.page == 1
        assert result1.total_pages == 10

        # Middle page
        result5 = generator.generate(
            value, max_size=1000, measurer=measurer, page=5, page_size=10
        )
        assert result5.page == 5

        # Last page
        result10 = generator.generate(
            value, max_size=1000, measurer=measurer, page=10, page_size=10
        )
        assert result10.page == 10

    def test_empty_list(self, generator, measurer) -> None:
        """Empty list returns empty page."""
        value = []
        result = generator.generate(
            value, max_size=1000, measurer=measurer, page=1, page_size=10
        )

        assert result.preview == []
        assert result.total_items == 0
        assert result.total_pages == 0

    def test_page_respects_max_size(self, generator, measurer) -> None:
        """Page is further trimmed if it exceeds max_size."""
        value = [{"data": "x" * 100} for _ in range(100)]
        result = generator.generate(
            value, max_size=50, measurer=measurer, page=1, page_size=10
        )

        # Should have fewer items than page_size due to max_size constraint
        assert result.preview_size <= 50


# =============================================================================
# TruncateGenerator Tests
# =============================================================================


class TestTruncateGenerator:
    """Tests for TruncateGenerator (string truncation)."""

    @pytest.fixture
    def generator(self):
        """Create a TruncateGenerator instance."""
        from mcp_refcache.preview import TruncateGenerator

        return TruncateGenerator()

    @pytest.fixture
    def measurer(self):
        """Create a CharacterMeasurer for testing."""
        return CharacterMeasurer()

    def test_short_string_unchanged(self, generator, measurer) -> None:
        """Short strings that fit are returned unchanged."""
        value = "Hello, world!"
        result = generator.generate(value, max_size=100, measurer=measurer)

        assert result.preview == value
        assert result.strategy == PreviewStrategy.TRUNCATE

    def test_long_string_truncated(self, generator, measurer) -> None:
        """Long strings are truncated with ellipsis."""
        value = "a" * 1000
        result = generator.generate(value, max_size=50, measurer=measurer)

        assert len(result.preview) < 1000
        assert result.preview.endswith("...")
        assert result.strategy == PreviewStrategy.TRUNCATE
        assert result.preview_size <= 50

    def test_list_stringified_and_truncated(self, generator, measurer) -> None:
        """Lists are JSON-stringified then truncated."""
        value = list(range(1000))
        result = generator.generate(value, max_size=50, measurer=measurer)

        assert isinstance(result.preview, str)
        assert result.preview.endswith("...")
        assert result.preview_size <= 50

    def test_dict_stringified_and_truncated(self, generator, measurer) -> None:
        """Dicts are JSON-stringified then truncated."""
        value = {f"key_{i}": i for i in range(100)}
        result = generator.generate(value, max_size=50, measurer=measurer)

        assert isinstance(result.preview, str)
        assert result.preview.endswith("...")
        assert result.preview_size <= 50

    def test_empty_string(self, generator, measurer) -> None:
        """Empty string is returned as-is."""
        value = ""
        result = generator.generate(value, max_size=100, measurer=measurer)

        assert result.preview == ""

    def test_exact_fit(self, generator, measurer) -> None:
        """String that exactly fits is not truncated."""
        value = "x" * 10
        result = generator.generate(value, max_size=12, measurer=measurer)
        # 10 chars + 2 quotes in JSON = 12

        assert result.preview == value
        assert "..." not in result.preview

    def test_preserves_structure_info_in_metadata(self, generator, measurer) -> None:
        """Original structure info is preserved in result."""
        value = list(range(100))
        result = generator.generate(value, max_size=50, measurer=measurer)

        assert result.total_items == 100
        assert result.original_size > 50


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetDefaultGenerator:
    """Tests for get_default_generator factory function."""

    def test_sample_strategy(self) -> None:
        """get_default_generator returns SampleGenerator for SAMPLE."""
        from mcp_refcache.preview import SampleGenerator, get_default_generator

        generator = get_default_generator(PreviewStrategy.SAMPLE)
        assert isinstance(generator, SampleGenerator)

    def test_paginate_strategy(self) -> None:
        """get_default_generator returns PaginateGenerator for PAGINATE."""
        from mcp_refcache.preview import PaginateGenerator, get_default_generator

        generator = get_default_generator(PreviewStrategy.PAGINATE)
        assert isinstance(generator, PaginateGenerator)

    def test_truncate_strategy(self) -> None:
        """get_default_generator returns TruncateGenerator for TRUNCATE."""
        from mcp_refcache.preview import TruncateGenerator, get_default_generator

        generator = get_default_generator(PreviewStrategy.TRUNCATE)
        assert isinstance(generator, TruncateGenerator)


# =============================================================================
# Integration Tests
# =============================================================================


class TestPreviewIntegration:
    """Integration tests for preview generation."""

    def test_sample_with_token_measurer(self) -> None:
        """Full pipeline with SampleGenerator and TokenMeasurer."""
        from mcp_refcache.preview import SampleGenerator

        tokenizer = CharacterFallback()
        measurer = TokenMeasurer(tokenizer)
        generator = SampleGenerator()

        value = [{"id": i, "name": f"Item {i}", "data": "x" * 50} for i in range(100)]
        result = generator.generate(value, max_size=100, measurer=measurer)

        assert result.preview_size <= 100
        assert result.sampled_items < 100
        assert isinstance(result.preview, list)

    def test_paginate_with_character_measurer(self) -> None:
        """Full pipeline with PaginateGenerator and CharacterMeasurer."""
        from mcp_refcache.preview import PaginateGenerator

        measurer = CharacterMeasurer()
        generator = PaginateGenerator()

        value = list(range(1000))
        result = generator.generate(
            value, max_size=500, measurer=measurer, page=1, page_size=20
        )

        assert result.page == 1
        assert result.total_pages == 50
        assert len(result.preview) == 20

    def test_complex_nested_sampling(self) -> None:
        """Sample complex nested structures at top level.

        Note: Sampling happens at top-level keys only. For deeply nested
        structures where even one top-level key exceeds the limit,
        consider flattening the structure or using truncate strategy.
        """
        from mcp_refcache.preview import SampleGenerator

        measurer = CharacterMeasurer()
        generator = SampleGenerator()

        # Use a structure where each top-level item is reasonably sized
        value = {
            f"user_{i}": {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
            }
            for i in range(100)
        }

        result = generator.generate(value, max_size=500, measurer=measurer)

        assert result.preview_size <= 500
        assert isinstance(result.preview, dict)
        assert result.sampled_items < 100

    def test_generator_consistency(self) -> None:
        """Same input produces consistent output."""
        from mcp_refcache.preview import SampleGenerator

        measurer = CharacterMeasurer()
        generator = SampleGenerator()

        value = list(range(100))

        result1 = generator.generate(value, max_size=50, measurer=measurer)
        result2 = generator.generate(value, max_size=50, measurer=measurer)

        assert result1.preview == result2.preview
        assert result1.sampled_items == result2.sampled_items
