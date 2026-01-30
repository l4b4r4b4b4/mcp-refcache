"""Tests for the FastMCP instructions module.

Tests the instruction generators and documentation helpers that
inform LLM agents about how to work with RefCache.
"""

from mcp_refcache.fastmcp.instructions import (
    COMPACT_INSTRUCTIONS,
    FULL_CACHE_GUIDE,
    cache_guide_prompt,
    cache_instructions,
    cached_tool_description,
    format_response_hint,
    get_full_cache_guide,
    with_cache_docs,
)


class TestCompactInstructions:
    """Tests for the compact instructions content."""

    def test_compact_instructions_mentions_reference_caching(self) -> None:
        """Compact instructions should explain reference-based caching."""
        assert "reference-based caching" in COMPACT_INSTRUCTIONS

    def test_compact_instructions_mentions_ref_id(self) -> None:
        """Compact instructions should mention ref_id."""
        assert "ref_id" in COMPACT_INSTRUCTIONS

    def test_compact_instructions_mentions_pagination(self) -> None:
        """Compact instructions should explain pagination."""
        assert "get_cached_result" in COMPACT_INSTRUCTIONS
        assert "page" in COMPACT_INSTRUCTIONS

    def test_compact_instructions_mentions_preview_size_control(self) -> None:
        """Compact instructions should mention preview size control hierarchy."""
        assert "Preview Size Control" in COMPACT_INSTRUCTIONS
        assert "Per-call override" in COMPACT_INSTRUCTIONS
        assert "max_size" in COMPACT_INSTRUCTIONS


class TestFullCacheGuide:
    """Tests for the full cache guide content."""

    def test_full_guide_has_response_types_section(self) -> None:
        """Full guide should have response types section."""
        assert "Response Types" in FULL_CACHE_GUIDE
        assert "Direct Values" in FULL_CACHE_GUIDE
        assert "Reference Responses" in FULL_CACHE_GUIDE

    def test_full_guide_has_pagination_section(self) -> None:
        """Full guide should have pagination section."""
        assert "Pagination" in FULL_CACHE_GUIDE
        assert "page_size" in FULL_CACHE_GUIDE

    def test_full_guide_has_preview_size_control_section(self) -> None:
        """Full guide should have preview size control section."""
        assert "Preview Size Control" in FULL_CACHE_GUIDE
        assert "Per-call" in FULL_CACHE_GUIDE
        assert "Per-tool" in FULL_CACHE_GUIDE
        assert "Server default" in FULL_CACHE_GUIDE

    def test_full_guide_explains_three_level_priority(self) -> None:
        """Full guide should explain three-level max_size priority."""
        assert "highest priority first" in FULL_CACHE_GUIDE

    def test_full_guide_has_reference_input_section(self) -> None:
        """Full guide should have reference input section."""
        assert "Passing References as Inputs" in FULL_CACHE_GUIDE

    def test_full_guide_has_private_computation_section(self) -> None:
        """Full guide should explain private computation."""
        assert "Private Computation" in FULL_CACHE_GUIDE


class TestCacheInstructionsFunction:
    """Tests for the cache_instructions() function."""

    def test_compact_mode_returns_compact(self) -> None:
        """cache_instructions(compact=True) returns compact instructions."""
        result = cache_instructions(compact=True)
        assert result == COMPACT_INSTRUCTIONS

    def test_full_mode_returns_full_guide(self) -> None:
        """cache_instructions(compact=False) returns full guide."""
        result = cache_instructions(compact=False)
        assert result == FULL_CACHE_GUIDE

    def test_default_is_compact(self) -> None:
        """Default mode is compact."""
        result = cache_instructions()
        assert result == COMPACT_INSTRUCTIONS


class TestGetFullCacheGuide:
    """Tests for the get_full_cache_guide() function."""

    def test_returns_full_guide(self) -> None:
        """get_full_cache_guide() returns the full guide."""
        assert get_full_cache_guide() == FULL_CACHE_GUIDE


class TestCacheGuidePrompt:
    """Tests for the cache_guide_prompt() function."""

    def test_returns_full_guide(self) -> None:
        """cache_guide_prompt() returns the full guide for use in prompts."""
        assert cache_guide_prompt() == FULL_CACHE_GUIDE


class TestCachedToolDescription:
    """Tests for the cached_tool_description() function."""

    def test_base_description_preserved(self) -> None:
        """Base description is preserved in output."""
        result = cached_tool_description("Fetches user data")
        assert "Fetches user data" in result

    def test_returns_reference_adds_doc(self) -> None:
        """returns_reference=True adds reference documentation."""
        result = cached_tool_description("Fetches data", returns_reference=True)
        assert "ref_id" in result
        assert "reference" in result.lower()

    def test_supports_pagination_adds_doc(self) -> None:
        """supports_pagination=True adds pagination documentation."""
        result = cached_tool_description("Fetches data", supports_pagination=True)
        assert "page" in result
        assert "page_size" in result

    def test_accepts_references_adds_doc(self) -> None:
        """accepts_references=True adds reference input documentation."""
        result = cached_tool_description("Processes data", accepts_references=True)
        assert "ref_id" in result
        assert "input" in result.lower()

    def test_private_computation_adds_doc(self) -> None:
        """private_computation=True adds private computation documentation."""
        result = cached_tool_description("Computes value", private_computation=True)
        assert "server-side" in result.lower() or "private" in result.lower()


class TestFormatResponseHint:
    """Tests for the format_response_hint() function."""

    def test_includes_ref_id_when_has_reference(self) -> None:
        """Includes ref_id documentation when has_reference=True."""
        result = format_response_hint(has_reference=True)
        assert "ref_id" in result

    def test_includes_preview_when_has_preview(self) -> None:
        """Includes preview documentation when has_preview=True."""
        result = format_response_hint(has_preview=True)
        assert "preview" in result
        assert "total_items" in result

    def test_includes_pagination_when_has_pagination(self) -> None:
        """Includes pagination documentation when has_pagination=True."""
        result = format_response_hint(has_pagination=True)
        assert "page" in result
        assert "total_pages" in result

    def test_includes_available_actions(self) -> None:
        """Includes available actions when specified."""
        result = format_response_hint(available_actions=["get_page", "pass_to_tool"])
        assert "get_page" in result
        assert "pass_to_tool" in result


class TestWithCacheDocsDecorator:
    """Tests for the with_cache_docs() decorator."""

    def test_preserves_original_docstring(self) -> None:
        """Original docstring is preserved."""

        @with_cache_docs()
        def my_func() -> None:
            """Original documentation."""
            pass

        assert "Original documentation" in my_func.__doc__

    def test_adds_caching_documentation(self) -> None:
        """Adds caching documentation when returns_reference=True."""

        @with_cache_docs(returns_reference=True)
        def my_func() -> None:
            """Original."""
            pass

        assert "Caching" in my_func.__doc__
        assert "reference" in my_func.__doc__.lower()

    def test_adds_pagination_documentation(self) -> None:
        """Adds pagination documentation when supports_pagination=True."""

        @with_cache_docs(supports_pagination=True)
        def my_func() -> None:
            """Original."""
            pass

        assert "Pagination" in my_func.__doc__
        assert "page" in my_func.__doc__

    def test_adds_references_documentation(self) -> None:
        """Adds references documentation when accepts_references=True."""

        @with_cache_docs(accepts_references=True)
        def my_func() -> None:
            """Original."""
            pass

        assert "References" in my_func.__doc__
        assert "ref_id" in my_func.__doc__

    def test_adds_private_compute_documentation(self) -> None:
        """Adds private computation documentation."""

        @with_cache_docs(private_computation=True)
        def my_func() -> None:
            """Original."""
            pass

        assert "Private Compute" in my_func.__doc__

    def test_handles_function_without_docstring(self) -> None:
        """Handles functions without docstrings gracefully."""

        @with_cache_docs(returns_reference=True)
        def my_func() -> None:
            pass

        assert my_func.__doc__ is not None
        assert "Caching" in my_func.__doc__

    def test_multiple_flags_combine(self) -> None:
        """Multiple flags combine in the docstring."""

        @with_cache_docs(
            returns_reference=True,
            supports_pagination=True,
            accepts_references=True,
        )
        def my_func() -> None:
            """Original."""
            pass

        assert "Caching" in my_func.__doc__
        assert "Pagination" in my_func.__doc__
        assert "References" in my_func.__doc__
