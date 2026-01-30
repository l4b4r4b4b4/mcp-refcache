"""Tests for context limiting: tokenizer adapters and size measurers.

Tests the Tokenizer protocol and its implementations:
- TiktokenAdapter (OpenAI models)
- HuggingFaceAdapter (HF models)
- CharacterFallback (no dependencies)

Also tests SizeMeasurer protocol and implementations:
- TokenMeasurer (uses injected Tokenizer)
- CharacterMeasurer (simple JSON length)
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from mcp_refcache.models import SizeMode

# =============================================================================
# Helper Functions
# =============================================================================


def _tiktoken_available() -> bool:
    """Check if tiktoken is installed."""
    try:
        import tiktoken  # noqa: F401

        return True
    except ImportError:
        return False


def _transformers_available() -> bool:
    """Check if transformers is installed."""
    try:
        import transformers  # noqa: F401

        return True
    except ImportError:
        return False


# =============================================================================
# Tokenizer Protocol Tests
# =============================================================================


class TestTokenizerProtocol:
    """Tests for Tokenizer protocol compliance."""

    def test_tokenizer_has_model_name_property(self) -> None:
        """Tokenizer must have model_name property."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback()
        assert hasattr(tokenizer, "model_name")
        assert isinstance(tokenizer.model_name, str)

    def test_tokenizer_has_encode_method(self) -> None:
        """Tokenizer must have encode method returning list[int]."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback()
        result = tokenizer.encode("hello world")
        assert isinstance(result, list)
        assert all(isinstance(t, int) for t in result)

    def test_tokenizer_has_count_tokens_method(self) -> None:
        """Tokenizer must have count_tokens method returning int."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback()
        result = tokenizer.count_tokens("hello world")
        assert isinstance(result, int)
        assert result > 0


# =============================================================================
# CharacterFallback Tests
# =============================================================================


class TestCharacterFallback:
    """Tests for CharacterFallback tokenizer (no dependencies)."""

    def test_model_name(self) -> None:
        """CharacterFallback has descriptive model name."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback()
        assert tokenizer.model_name == "character-fallback"

    def test_count_tokens_approximation(self) -> None:
        """CharacterFallback estimates ~4 chars per token."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback()
        # 20 characters should be ~5 tokens
        text = "a" * 20
        tokens = tokenizer.count_tokens(text)
        assert tokens == 5

    def test_count_tokens_rounds_up(self) -> None:
        """CharacterFallback rounds up partial tokens."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback()
        # 5 characters should round up to 2 tokens (5/4 = 1.25 -> 2)
        text = "a" * 5
        tokens = tokenizer.count_tokens(text)
        assert tokens == 2

    def test_count_tokens_minimum_one(self) -> None:
        """CharacterFallback returns at least 1 for non-empty text."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback()
        tokens = tokenizer.count_tokens("a")
        assert tokens == 1

    def test_count_tokens_empty_string(self) -> None:
        """CharacterFallback returns 0 for empty string."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback()
        tokens = tokenizer.count_tokens("")
        assert tokens == 0

    def test_encode_returns_pseudo_tokens(self) -> None:
        """CharacterFallback encode returns pseudo token IDs."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback()
        text = "hello world"
        tokens = tokenizer.encode(text)
        # Should return list of integers
        assert isinstance(tokens, list)
        assert all(isinstance(t, int) for t in tokens)
        # Length should match count_tokens
        assert len(tokens) == tokenizer.count_tokens(text)

    def test_custom_chars_per_token(self) -> None:
        """CharacterFallback supports custom chars_per_token ratio."""
        from mcp_refcache.context import CharacterFallback

        tokenizer = CharacterFallback(chars_per_token=2)
        text = "a" * 10
        tokens = tokenizer.count_tokens(text)
        assert tokens == 5  # 10 chars / 2 chars per token


# =============================================================================
# TiktokenAdapter Tests
# =============================================================================


class TestTiktokenAdapter:
    """Tests for TiktokenAdapter (OpenAI models)."""

    def test_model_name(self) -> None:
        """TiktokenAdapter stores model name."""
        from mcp_refcache.context import TiktokenAdapter

        adapter = TiktokenAdapter(model="gpt-4o")
        assert adapter.model_name == "gpt-4o"

    def test_default_model(self) -> None:
        """TiktokenAdapter defaults to gpt-4o."""
        from mcp_refcache.context import TiktokenAdapter

        adapter = TiktokenAdapter()
        assert adapter.model_name == "gpt-4o"

    def test_lazy_loading(self) -> None:
        """TiktokenAdapter doesn't load encoding until first use."""
        from mcp_refcache.context import TiktokenAdapter

        adapter = TiktokenAdapter()
        # Should not have loaded encoding yet
        assert adapter._encoding is None

    @pytest.mark.skipif(
        not _tiktoken_available(),
        reason="tiktoken not installed",
    )
    def test_count_tokens_with_tiktoken(self) -> None:
        """TiktokenAdapter counts tokens accurately with tiktoken."""
        from mcp_refcache.context import TiktokenAdapter

        adapter = TiktokenAdapter(model="gpt-4o")
        # "hello world" is typically 2 tokens
        tokens = adapter.count_tokens("hello world")
        assert isinstance(tokens, int)
        assert tokens > 0

    @pytest.mark.skipif(
        not _tiktoken_available(),
        reason="tiktoken not installed",
    )
    def test_encode_with_tiktoken(self) -> None:
        """TiktokenAdapter encodes text to token IDs."""
        from mcp_refcache.context import TiktokenAdapter

        adapter = TiktokenAdapter(model="gpt-4o")
        tokens = adapter.encode("hello world")
        assert isinstance(tokens, list)
        assert all(isinstance(t, int) for t in tokens)
        assert len(tokens) == adapter.count_tokens("hello world")

    @pytest.mark.skipif(
        not _tiktoken_available(),
        reason="tiktoken not installed",
    )
    def test_encoding_cached(self) -> None:
        """TiktokenAdapter caches encoding after first use."""
        from mcp_refcache.context import TiktokenAdapter

        adapter = TiktokenAdapter(model="gpt-4o")
        adapter.count_tokens("test")
        encoding1 = adapter._encoding
        adapter.count_tokens("another test")
        encoding2 = adapter._encoding
        assert encoding1 is encoding2

    def test_fallback_when_tiktoken_unavailable(self) -> None:
        """TiktokenAdapter uses fallback when tiktoken not available."""
        from mcp_refcache.context import CharacterFallback, TiktokenAdapter

        fallback = CharacterFallback()
        adapter = TiktokenAdapter(fallback=fallback)

        # Mock tiktoken import failure
        with patch.dict("sys.modules", {"tiktoken": None}):
            # Force reload of encoding
            adapter._encoding = None
            adapter._tiktoken_available = False

            tokens = adapter.count_tokens("hello world")
            # Should use fallback (11 chars / 4 = 3 tokens)
            assert tokens == fallback.count_tokens("hello world")


# =============================================================================
# HuggingFaceAdapter Tests
# =============================================================================


class TestHuggingFaceAdapter:
    """Tests for HuggingFaceAdapter (HF models)."""

    def test_model_name(self) -> None:
        """HuggingFaceAdapter stores model name."""
        from mcp_refcache.context import HuggingFaceAdapter

        adapter = HuggingFaceAdapter(model="gpt2")
        assert adapter.model_name == "gpt2"

    def test_default_model(self) -> None:
        """HuggingFaceAdapter defaults to gpt2 (small, always available)."""
        from mcp_refcache.context import HuggingFaceAdapter

        adapter = HuggingFaceAdapter()
        assert adapter.model_name == "gpt2"

    def test_lazy_loading(self) -> None:
        """HuggingFaceAdapter doesn't load tokenizer until first use."""
        from mcp_refcache.context import HuggingFaceAdapter

        adapter = HuggingFaceAdapter()
        assert adapter._tokenizer is None

    @pytest.mark.skipif(
        not _transformers_available(),
        reason="transformers not installed",
    )
    def test_count_tokens_with_transformers(self) -> None:
        """HuggingFaceAdapter counts tokens accurately."""
        from mcp_refcache.context import HuggingFaceAdapter

        adapter = HuggingFaceAdapter(model="gpt2")
        tokens = adapter.count_tokens("hello world")
        assert isinstance(tokens, int)
        assert tokens > 0

    @pytest.mark.skipif(
        not _transformers_available(),
        reason="transformers not installed",
    )
    def test_encode_with_transformers(self) -> None:
        """HuggingFaceAdapter encodes text to token IDs."""
        from mcp_refcache.context import HuggingFaceAdapter

        adapter = HuggingFaceAdapter(model="gpt2")
        tokens = adapter.encode("hello world")
        assert isinstance(tokens, list)
        assert all(isinstance(t, int) for t in tokens)
        assert len(tokens) == adapter.count_tokens("hello world")

    @pytest.mark.skipif(
        not _transformers_available(),
        reason="transformers not installed",
    )
    def test_tokenizer_cached(self) -> None:
        """HuggingFaceAdapter caches tokenizer after first use."""
        from mcp_refcache.context import HuggingFaceAdapter

        adapter = HuggingFaceAdapter(model="gpt2")
        adapter.count_tokens("test")
        tokenizer1 = adapter._tokenizer
        adapter.count_tokens("another test")
        tokenizer2 = adapter._tokenizer
        assert tokenizer1 is tokenizer2

    def test_fallback_when_transformers_unavailable(self) -> None:
        """HuggingFaceAdapter uses fallback when transformers not available."""
        from mcp_refcache.context import CharacterFallback, HuggingFaceAdapter

        fallback = CharacterFallback()
        adapter = HuggingFaceAdapter(fallback=fallback)

        # Mock transformers import failure
        adapter._tokenizer = None
        adapter._transformers_available = False

        tokens = adapter.count_tokens("hello world")
        assert tokens == fallback.count_tokens("hello world")


# =============================================================================
# SizeMeasurer Protocol Tests
# =============================================================================


class TestSizeMeasurerProtocol:
    """Tests for SizeMeasurer protocol compliance."""

    def test_measurer_has_measure_method(self) -> None:
        """SizeMeasurer must have measure method returning int."""
        from mcp_refcache.context import CharacterMeasurer

        measurer = CharacterMeasurer()
        result = measurer.measure({"key": "value"})
        assert isinstance(result, int)
        assert result > 0


# =============================================================================
# CharacterMeasurer Tests
# =============================================================================


class TestCharacterMeasurer:
    """Tests for CharacterMeasurer (JSON string length)."""

    def test_measure_dict(self) -> None:
        """CharacterMeasurer measures dict as JSON length."""
        from mcp_refcache.context import CharacterMeasurer

        measurer = CharacterMeasurer()
        value = {"key": "value"}
        size = measurer.measure(value)
        expected = len(json.dumps(value))
        assert size == expected

    def test_measure_list(self) -> None:
        """CharacterMeasurer measures list as JSON length."""
        from mcp_refcache.context import CharacterMeasurer

        measurer = CharacterMeasurer()
        value = [1, 2, 3, 4, 5]
        size = measurer.measure(value)
        expected = len(json.dumps(value))
        assert size == expected

    def test_measure_string(self) -> None:
        """CharacterMeasurer measures string as JSON length (includes quotes)."""
        from mcp_refcache.context import CharacterMeasurer

        measurer = CharacterMeasurer()
        value = "hello world"
        size = measurer.measure(value)
        expected = len(json.dumps(value))  # Includes quotes
        assert size == expected

    def test_measure_nested_structure(self) -> None:
        """CharacterMeasurer handles nested structures."""
        from mcp_refcache.context import CharacterMeasurer

        measurer = CharacterMeasurer()
        value = {"users": [{"name": "Alice"}, {"name": "Bob"}]}
        size = measurer.measure(value)
        expected = len(json.dumps(value))
        assert size == expected

    def test_measure_non_serializable(self) -> None:
        """CharacterMeasurer handles non-JSON-serializable objects via default=str."""
        from mcp_refcache.context import CharacterMeasurer

        measurer = CharacterMeasurer()

        class CustomObject:
            def __str__(self) -> str:
                return "custom"

        value = {"obj": CustomObject()}
        # Should not raise, uses default=str
        size = measurer.measure(value)
        assert size > 0


# =============================================================================
# TokenMeasurer Tests
# =============================================================================


class TestTokenMeasurer:
    """Tests for TokenMeasurer (uses injected Tokenizer)."""

    def test_measure_uses_tokenizer(self) -> None:
        """TokenMeasurer delegates to injected tokenizer."""
        from mcp_refcache.context import CharacterFallback, TokenMeasurer

        tokenizer = CharacterFallback()
        measurer = TokenMeasurer(tokenizer)

        value = {"key": "value"}
        size = measurer.measure(value)

        # Should be tokens, not characters
        json_str = json.dumps(value)
        expected = tokenizer.count_tokens(json_str)
        assert size == expected

    def test_measure_dict(self) -> None:
        """TokenMeasurer measures dict in tokens."""
        from mcp_refcache.context import CharacterFallback, TokenMeasurer

        tokenizer = CharacterFallback()
        measurer = TokenMeasurer(tokenizer)

        value = {"key": "value"}
        size = measurer.measure(value)
        assert isinstance(size, int)
        assert size > 0

    def test_measure_list(self) -> None:
        """TokenMeasurer measures list in tokens."""
        from mcp_refcache.context import CharacterFallback, TokenMeasurer

        tokenizer = CharacterFallback()
        measurer = TokenMeasurer(tokenizer)

        value = [1, 2, 3, 4, 5]
        size = measurer.measure(value)
        assert isinstance(size, int)
        assert size > 0

    def test_measure_with_mock_tokenizer(self) -> None:
        """TokenMeasurer works with any Tokenizer implementation."""
        from mcp_refcache.context import TokenMeasurer

        # Create mock tokenizer
        mock_tokenizer = MagicMock()
        mock_tokenizer.count_tokens.return_value = 42

        measurer = TokenMeasurer(mock_tokenizer)
        value = {"test": "data"}
        size = measurer.measure(value)

        assert size == 42
        mock_tokenizer.count_tokens.assert_called_once()

    @pytest.mark.skipif(
        not _tiktoken_available(),
        reason="tiktoken not installed",
    )
    def test_measure_with_tiktoken(self) -> None:
        """TokenMeasurer works with TiktokenAdapter."""
        from mcp_refcache.context import TiktokenAdapter, TokenMeasurer

        tokenizer = TiktokenAdapter(model="gpt-4o")
        measurer = TokenMeasurer(tokenizer)

        value = {"message": "Hello, world!"}
        size = measurer.measure(value)
        assert isinstance(size, int)
        assert size > 0


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetDefaultMeasurer:
    """Tests for get_default_measurer factory function."""

    def test_character_mode_returns_character_measurer(self) -> None:
        """get_default_measurer returns CharacterMeasurer for CHARACTER mode."""
        from mcp_refcache.context import CharacterMeasurer, get_default_measurer

        measurer = get_default_measurer(SizeMode.CHARACTER)
        assert isinstance(measurer, CharacterMeasurer)

    def test_token_mode_with_tokenizer_returns_token_measurer(self) -> None:
        """get_default_measurer returns TokenMeasurer for TOKEN mode with tokenizer."""
        from mcp_refcache.context import (
            CharacterFallback,
            TokenMeasurer,
            get_default_measurer,
        )

        tokenizer = CharacterFallback()
        measurer = get_default_measurer(SizeMode.TOKEN, tokenizer=tokenizer)
        assert isinstance(measurer, TokenMeasurer)

    def test_token_mode_without_tokenizer_creates_fallback(self) -> None:
        """get_default_measurer creates CharacterFallback if no tokenizer provided."""
        from mcp_refcache.context import TokenMeasurer, get_default_measurer

        measurer = get_default_measurer(SizeMode.TOKEN)
        assert isinstance(measurer, TokenMeasurer)
        # Should have created a fallback tokenizer internally


class TestGetDefaultTokenizer:
    """Tests for get_default_tokenizer factory function."""

    def test_returns_tiktoken_if_available(self) -> None:
        """get_default_tokenizer prefers TiktokenAdapter if tiktoken installed."""
        from mcp_refcache.context import get_default_tokenizer

        tokenizer = get_default_tokenizer()
        # Should return some tokenizer (type depends on what's installed)
        assert hasattr(tokenizer, "count_tokens")
        assert hasattr(tokenizer, "encode")
        assert hasattr(tokenizer, "model_name")

    def test_with_explicit_model(self) -> None:
        """get_default_tokenizer accepts explicit model name."""
        from mcp_refcache.context import get_default_tokenizer

        tokenizer = get_default_tokenizer(model="gpt-4")
        assert tokenizer.model_name in ["gpt-4", "character-fallback"]

    def test_always_returns_valid_tokenizer(self) -> None:
        """get_default_tokenizer always returns a working tokenizer."""
        from mcp_refcache.context import get_default_tokenizer

        tokenizer = get_default_tokenizer()
        # Should work without raising
        tokens = tokenizer.count_tokens("test text")
        assert isinstance(tokens, int)
        assert tokens > 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestContextIntegration:
    """Integration tests for context limiting components."""

    def test_full_pipeline_with_fallback(self) -> None:
        """Test complete pipeline with CharacterFallback."""
        from mcp_refcache.context import CharacterFallback, TokenMeasurer

        tokenizer = CharacterFallback()
        measurer = TokenMeasurer(tokenizer)

        # Measure a complex value
        value = {
            "users": [
                {"id": 1, "name": "Alice", "email": "alice@example.com"},
                {"id": 2, "name": "Bob", "email": "bob@example.com"},
            ],
            "total": 2,
        }

        size = measurer.measure(value)
        assert size > 0

        # Verify consistency
        json_str = json.dumps(value)
        expected_tokens = tokenizer.count_tokens(json_str)
        assert size == expected_tokens

    @pytest.mark.skipif(
        not _tiktoken_available(),
        reason="tiktoken not installed",
    )
    def test_full_pipeline_with_tiktoken(self) -> None:
        """Test complete pipeline with TiktokenAdapter."""
        from mcp_refcache.context import TiktokenAdapter, TokenMeasurer

        tokenizer = TiktokenAdapter(model="gpt-4o")
        measurer = TokenMeasurer(tokenizer)

        value = {"message": "Hello, world!", "count": 42}
        size = measurer.measure(value)

        assert size > 0
        # Tiktoken should give different (more accurate) count than character-based
        # Token count might differ significantly from character estimate
        assert isinstance(size, int)
