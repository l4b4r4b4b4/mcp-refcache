"""Context limiting: tokenizer adapters and size measurers.

This module provides exact token counting for LLM context window management.

Tokenizer Adapters:
    - TiktokenAdapter: OpenAI models (gpt-4o, gpt-4, gpt-3.5-turbo)
    - HuggingFaceAdapter: HF models (Llama, Mistral, Qwen, etc.)
    - CharacterFallback: ~4 chars per token approximation (no dependencies)

Size Measurers:
    - TokenMeasurer: Uses injected Tokenizer for accurate token counts
    - CharacterMeasurer: Simple JSON character length

Example:
    ```python
    from mcp_refcache.context import (
        TiktokenAdapter,
        TokenMeasurer,
        get_default_measurer,
    )
    from mcp_refcache.models import SizeMode

    # With tiktoken (OpenAI models)
    tokenizer = TiktokenAdapter(model="gpt-4o")
    measurer = TokenMeasurer(tokenizer)
    size = measurer.measure({"key": "value"})

    # With factory function
    measurer = get_default_measurer(SizeMode.TOKEN, tokenizer=tokenizer)
    ```
"""

from __future__ import annotations

import json
import math
from typing import Any, Protocol, runtime_checkable

from mcp_refcache.models import SizeMode

# =============================================================================
# Tokenizer Protocol
# =============================================================================


@runtime_checkable
class Tokenizer(Protocol):
    """Protocol for tokenizer adapters.

    Implementations provide exact token counting for different LLM families.
    All implementations must support lazy loading for fast initialization.
    """

    @property
    def model_name(self) -> str:
        """The model this tokenizer is for.

        Returns:
            Model identifier string (e.g., "gpt-4o", "meta-llama/Llama-3.1-8B").
        """
        ...

    def encode(self, text: str) -> list[int]:
        """Encode text to token IDs.

        Args:
            text: The text to encode.

        Returns:
            List of integer token IDs.
        """
        ...

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        This may be more efficient than len(encode(text)) for some implementations.

        Args:
            text: The text to count tokens for.

        Returns:
            Number of tokens in the text.
        """
        ...


# =============================================================================
# CharacterFallback Tokenizer
# =============================================================================


class CharacterFallback:
    """Fallback tokenizer using character count approximation.

    Estimates tokens as approximately 4 characters per token.
    This is a rough approximation that works when no tokenizer library is available.

    Args:
        chars_per_token: Characters per token ratio (default: 4).

    Example:
        ```python
        tokenizer = CharacterFallback()
        tokens = tokenizer.count_tokens("Hello, world!")  # ~4 tokens
        ```
    """

    def __init__(self, chars_per_token: int = 4) -> None:
        """Initialize CharacterFallback.

        Args:
            chars_per_token: Characters per token ratio for approximation.
        """
        self._chars_per_token = chars_per_token

    @property
    def model_name(self) -> str:
        """Return descriptive model name."""
        return "character-fallback"

    def encode(self, text: str) -> list[int]:
        """Return pseudo token IDs based on character count.

        Args:
            text: The text to encode.

        Returns:
            List of pseudo token IDs (just incrementing integers).
        """
        token_count = self.count_tokens(text)
        return list(range(token_count))

    def count_tokens(self, text: str) -> int:
        """Estimate token count from character length.

        Args:
            text: The text to count tokens for.

        Returns:
            Estimated token count (rounded up).
        """
        if not text:
            return 0
        return math.ceil(len(text) / self._chars_per_token)


# =============================================================================
# TiktokenAdapter
# =============================================================================


class TiktokenAdapter:
    """Adapter for OpenAI's tiktoken library.

    Provides exact token counting for OpenAI models (gpt-4o, gpt-4, gpt-3.5-turbo).
    The tiktoken encoding is lazily loaded on first use.

    Args:
        model: OpenAI model name (default: "gpt-4o").
        fallback: Fallback tokenizer if tiktoken is not available.

    Example:
        ```python
        tokenizer = TiktokenAdapter(model="gpt-4o")
        tokens = tokenizer.count_tokens("Hello, world!")
        ```
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        fallback: Tokenizer | None = None,
    ) -> None:
        """Initialize TiktokenAdapter.

        Args:
            model: OpenAI model name for encoding selection.
            fallback: Fallback tokenizer if tiktoken is unavailable.
        """
        self._model = model
        self._fallback = fallback or CharacterFallback()
        self._encoding: Any = None
        self._tiktoken_available: bool | None = None

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    def _get_encoding(self) -> Any:
        """Get or create the tiktoken encoding.

        Returns:
            tiktoken.Encoding instance, or None if unavailable.
        """
        if self._encoding is not None:
            return self._encoding

        if self._tiktoken_available is False:
            return None

        try:
            import tiktoken

            self._encoding = tiktoken.encoding_for_model(self._model)
            self._tiktoken_available = True
            return self._encoding
        except ImportError:
            self._tiktoken_available = False
            return None
        except KeyError:
            # Model not found, try cl100k_base as fallback encoding
            try:
                import tiktoken

                self._encoding = tiktoken.get_encoding("cl100k_base")
                self._tiktoken_available = True
                return self._encoding
            except ImportError:
                self._tiktoken_available = False
                return None

    def encode(self, text: str) -> list[int]:
        """Encode text to token IDs using tiktoken.

        Args:
            text: The text to encode.

        Returns:
            List of token IDs.
        """
        encoding = self._get_encoding()
        if encoding is not None:
            return encoding.encode(text)
        return self._fallback.encode(text)

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken.

        Args:
            text: The text to count tokens for.

        Returns:
            Number of tokens.
        """
        encoding = self._get_encoding()
        if encoding is not None:
            return len(encoding.encode(text))
        return self._fallback.count_tokens(text)


# =============================================================================
# HuggingFaceAdapter
# =============================================================================


class HuggingFaceAdapter:
    """Adapter for HuggingFace transformers tokenizers.

    Provides exact token counting for HuggingFace models (Llama, Mistral, Qwen, etc.).
    The tokenizer is lazily loaded on first use and cached by HuggingFace
    in ~/.cache/huggingface/hub/.

    Args:
        model: HuggingFace model name (default: "gpt2" for testing).
        fallback: Fallback tokenizer if transformers is not available.

    Example:
        ```python
        tokenizer = HuggingFaceAdapter(model="meta-llama/Llama-3.1-8B")
        tokens = tokenizer.count_tokens("Hello, world!")
        ```
    """

    def __init__(
        self,
        model: str = "gpt2",
        fallback: Tokenizer | None = None,
    ) -> None:
        """Initialize HuggingFaceAdapter.

        Args:
            model: HuggingFace model name or path.
            fallback: Fallback tokenizer if transformers is unavailable.
        """
        self._model = model
        self._fallback = fallback or CharacterFallback()
        self._tokenizer: Any = None
        self._transformers_available: bool | None = None

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    def _get_tokenizer(self) -> Any:
        """Get or create the HuggingFace tokenizer.

        Returns:
            PreTrainedTokenizer instance, or None if unavailable.
        """
        if self._tokenizer is not None:
            return self._tokenizer

        if self._transformers_available is False:
            return None

        try:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self._model)
            self._transformers_available = True
            return self._tokenizer
        except ImportError:
            self._transformers_available = False
            return None
        except Exception:
            # Model not found or other error
            self._transformers_available = False
            return None

    def encode(self, text: str) -> list[int]:
        """Encode text to token IDs using HuggingFace tokenizer.

        Args:
            text: The text to encode.

        Returns:
            List of token IDs.
        """
        tokenizer = self._get_tokenizer()
        if tokenizer is not None:
            return tokenizer.encode(text)
        return self._fallback.encode(text)

    def count_tokens(self, text: str) -> int:
        """Count tokens using HuggingFace tokenizer.

        Args:
            text: The text to count tokens for.

        Returns:
            Number of tokens.
        """
        tokenizer = self._get_tokenizer()
        if tokenizer is not None:
            return len(tokenizer.encode(text))
        return self._fallback.count_tokens(text)


# =============================================================================
# SizeMeasurer Protocol
# =============================================================================


@runtime_checkable
class SizeMeasurer(Protocol):
    """Protocol for measuring value size.

    Implementations measure the size of Python values for context limiting.
    Size can be measured in tokens or characters depending on implementation.
    """

    def measure(self, value: Any) -> int:
        """Measure size of a value.

        Args:
            value: The value to measure (dict, list, string, etc.).

        Returns:
            Size in tokens or characters.
        """
        ...


# =============================================================================
# CharacterMeasurer
# =============================================================================


class CharacterMeasurer:
    """Measure size by JSON character count.

    Simple and fast measurement using JSON serialization length.
    Good for quick estimates when exact token counts aren't needed.

    Example:
        ```python
        measurer = CharacterMeasurer()
        size = measurer.measure({"key": "value"})  # Returns JSON length
        ```
    """

    def measure(self, value: Any) -> int:
        """Measure value size as JSON string length.

        Args:
            value: The value to measure.

        Returns:
            Length of JSON-serialized value.
        """
        return len(json.dumps(value, default=str))


# =============================================================================
# TokenMeasurer
# =============================================================================


class TokenMeasurer:
    """Measure size by token count using injected Tokenizer.

    Provides accurate token counts for LLM context window management.
    The tokenizer is injected for flexibility and testability.

    Args:
        tokenizer: Tokenizer implementation to use for counting.

    Example:
        ```python
        tokenizer = TiktokenAdapter(model="gpt-4o")
        measurer = TokenMeasurer(tokenizer)
        size = measurer.measure({"key": "value"})
        ```
    """

    def __init__(self, tokenizer: Tokenizer) -> None:
        """Initialize TokenMeasurer.

        Args:
            tokenizer: Tokenizer to use for token counting.
        """
        self._tokenizer = tokenizer

    def measure(self, value: Any) -> int:
        """Measure value size in tokens.

        Args:
            value: The value to measure.

        Returns:
            Token count of JSON-serialized value.
        """
        text = json.dumps(value, default=str)
        return self._tokenizer.count_tokens(text)


# =============================================================================
# Factory Functions
# =============================================================================


def get_default_tokenizer(model: str | None = None) -> Tokenizer:
    """Get a default tokenizer, preferring tiktoken if available.

    Tries tokenizers in order:
    1. TiktokenAdapter (if tiktoken installed and model is OpenAI-like)
    2. HuggingFaceAdapter (if transformers installed)
    3. CharacterFallback (always available)

    Args:
        model: Optional model name. If not provided, defaults to "gpt-4o".

    Returns:
        A Tokenizer implementation.

    Example:
        ```python
        tokenizer = get_default_tokenizer()  # Auto-detect best available
        tokenizer = get_default_tokenizer("gpt-4o")  # Prefer tiktoken
        tokenizer = get_default_tokenizer("meta-llama/Llama-3.1-8B")  # Prefer HF
        ```
    """
    model = model or "gpt-4o"

    # Try tiktoken first for OpenAI-like models
    tiktoken_adapter = TiktokenAdapter(model=model)
    if tiktoken_adapter._get_encoding() is not None:
        return tiktoken_adapter

    # Try HuggingFace for other models
    hf_adapter = HuggingFaceAdapter(model=model)
    if hf_adapter._get_tokenizer() is not None:
        return hf_adapter

    # Fall back to character approximation
    return CharacterFallback()


def get_default_measurer(
    size_mode: SizeMode,
    tokenizer: Tokenizer | None = None,
) -> SizeMeasurer:
    """Get a default SizeMeasurer for the given mode.

    Args:
        size_mode: How to measure size (TOKEN or CHARACTER).
        tokenizer: Optional tokenizer for TOKEN mode. If not provided,
            a default tokenizer will be created.

    Returns:
        A SizeMeasurer implementation.

    Example:
        ```python
        # Character-based (fast)
        measurer = get_default_measurer(SizeMode.CHARACTER)

        # Token-based with explicit tokenizer
        tokenizer = TiktokenAdapter(model="gpt-4o")
        measurer = get_default_measurer(SizeMode.TOKEN, tokenizer=tokenizer)

        # Token-based with auto-detected tokenizer
        measurer = get_default_measurer(SizeMode.TOKEN)
        ```
    """
    if size_mode == SizeMode.CHARACTER:
        return CharacterMeasurer()

    # TOKEN mode
    if tokenizer is None:
        tokenizer = get_default_tokenizer()
    return TokenMeasurer(tokenizer)


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "CharacterFallback",
    "CharacterMeasurer",
    "HuggingFaceAdapter",
    "SizeMeasurer",
    "TiktokenAdapter",
    "TokenMeasurer",
    "Tokenizer",
    "get_default_measurer",
    "get_default_tokenizer",
]
