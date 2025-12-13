#!/usr/bin/env python3
"""MCP Server with Langfuse Observability Integration.

This example demonstrates how to integrate mcp-refcache with Langfuse
for comprehensive observability of cache operations in MCP tools.

Features demonstrated:
- Tracing cache set/get operations with Langfuse spans
- Recording cache hits/misses as events
- Tracking ref_id resolution chains
- **User/session attribution via propagate_attributes()** (Langfuse SDK v3)
- Context extraction from MockContext/FastMCP
- Full context metadata in traces for filtering/aggregation
- Error tracking and debugging

Prerequisites:
    1. Install Langfuse: pip install langfuse
    2. Set environment variables:
        LANGFUSE_PUBLIC_KEY=pk-lf-...
        LANGFUSE_SECRET_KEY=sk-lf-...
        LANGFUSE_HOST=https://cloud.langfuse.com  # or self-hosted URL

Usage:
    # Set Langfuse credentials
    export LANGFUSE_PUBLIC_KEY="pk-lf-..."
    export LANGFUSE_SECRET_KEY="sk-lf-..."

    # Run the server
    python examples/langfuse_integration.py

    # Or with SSE transport for debugging
    python examples/langfuse_integration.py --transport sse --port 8000

Langfuse SDK v3 Best Practices:
    - Use propagate_attributes() to pass user_id, session_id, metadata to ALL child spans
    - Call propagate_attributes() early in the trace for complete coverage
    - Metadata keys must be alphanumeric only (no spaces/special chars)
    - Values must be strings ≤200 characters
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import os
import sys
from collections.abc import Callable
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel, Field
from typing_extensions import ParamSpec

P = ParamSpec("P")
T = TypeVar("T")

# =============================================================================
# Check for dependencies
# =============================================================================

try:
    from fastmcp import FastMCP
except ImportError:
    print(
        "Error: FastMCP is not installed. Install with:\n  pip install fastmcp>=2.0.0",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from langfuse import get_client, observe, propagate_attributes
except ImportError:
    print(
        "Error: Langfuse is not installed. Install with:\n  pip install langfuse",
        file=sys.stderr,
    )
    sys.exit(1)

# Import context integration for dynamic namespace support
import mcp_refcache.context_integration as ctx_integration  # noqa: E402
from mcp_refcache import (  # noqa: E402
    CacheResponse,
    PreviewConfig,
    PreviewStrategy,
    RefCache,
    SQLiteBackend,
)
from mcp_refcache.fastmcp import cache_instructions  # noqa: E402

# =============================================================================
# Initialize Langfuse
# =============================================================================

# Langfuse client is automatically initialized from environment variables
# LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
langfuse = get_client()

# Check if Langfuse is properly configured
_langfuse_enabled = all(
    [
        os.getenv("LANGFUSE_PUBLIC_KEY"),
        os.getenv("LANGFUSE_SECRET_KEY"),
    ]
)

if not _langfuse_enabled:
    print(
        "Warning: Langfuse credentials not set. Tracing will be disabled.\n"
        "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable tracing.",
        file=sys.stderr,
    )


# =============================================================================
# Mock Context for Testing (same pattern as mcp_server.py)
# =============================================================================


class MockContext:
    """Mock FastMCP Context for testing context-scoped caching with Langfuse.

    This class simulates a FastMCP Context object with the minimum API
    needed for context-scoped caching and Langfuse attribution:
    - session_id attribute
    - get_state(key) method for retrieving identity values
    """

    # Class-level state storage (shared across all instances)
    _state: ClassVar[dict[str, str]] = {
        "user_id": "demo_user",
        "org_id": "demo_org",
        "agent_id": "demo_agent",
    }
    _session_id: ClassVar[str] = "demo_session_001"

    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        return MockContext._session_id

    @property
    def client_id(self) -> str:
        """Get the client ID (for compatibility)."""
        return "demo_client"

    @property
    def request_id(self) -> str:
        """Get the request ID (for compatibility)."""
        return "demo_request"

    def get_state(self, key: str) -> str | None:
        """Get a state value by key."""
        return MockContext._state.get(key)

    @classmethod
    def set_state(cls, **kwargs: str) -> None:
        """Update state values."""
        cls._state.update(kwargs)

    @classmethod
    def set_session_id(cls, session_id: str) -> None:
        """Update the session ID."""
        cls._session_id = session_id

    @classmethod
    def get_current_state(cls) -> dict[str, Any]:
        """Get a copy of current state for inspection."""
        return {
            **cls._state,
            "session_id": cls._session_id,
        }

    @classmethod
    def reset(cls) -> None:
        """Reset to default test values."""
        cls._state = {
            "user_id": "demo_user",
            "org_id": "demo_org",
            "agent_id": "demo_agent",
        }
        cls._session_id = "demo_session_001"


# Store original function for restoration
_original_try_get_context = ctx_integration.try_get_fastmcp_context
_test_mode_enabled = False


def _mock_try_get_fastmcp_context() -> MockContext | None:
    """Mock version that returns our test context."""
    if _test_mode_enabled:
        return MockContext()
    return _original_try_get_context()


# Patch the context integration module
ctx_integration.try_get_fastmcp_context = _mock_try_get_fastmcp_context


# =============================================================================
# Langfuse Attribute Extraction from Context
# =============================================================================


def get_langfuse_attributes(
    context: MockContext | None = None,
    cache_namespace: str | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    """Extract Langfuse-compatible attributes from context.

    This function extracts user_id, session_id, and metadata from the
    current context (MockContext or FastMCP) for use with propagate_attributes().

    Langfuse SDK v3 requirements:
    - Values must be strings ≤200 characters
    - Metadata keys: alphanumeric only (no whitespace or special characters)
    - user_id and session_id are native Langfuse fields

    Args:
        context: Optional context object. If None, attempts to get from test mode.
        cache_namespace: Optional cache namespace to include in metadata.
        operation: Optional operation name (e.g., "cache_set", "cache_get").

    Returns:
        Dict with keys: user_id, session_id, metadata, tags, version
        All values are Langfuse-compatible (strings, alphanumeric keys).
    """
    # Try to get context if not provided
    if context is None:
        context = _mock_try_get_fastmcp_context()

    # Default values when no context available
    user_id = "anonymous"
    session_id = "nosession"
    org_id = "default"
    agent_id = "unknown"

    # Extract from context if available
    if context is not None:
        user_id = context.get_state("user_id") or user_id
        session_id = getattr(context, "session_id", None) or session_id
        org_id = context.get_state("org_id") or org_id
        agent_id = context.get_state("agent_id") or agent_id

    # Truncate to ≤200 chars (Langfuse requirement)
    user_id = str(user_id)[:200]
    session_id = str(session_id)[:200]

    # Build metadata dict (alphanumeric keys only)
    metadata: dict[str, str] = {
        "orgid": str(org_id)[:200],  # No underscores for strict alphanumeric
        "agentid": str(agent_id)[:200],
    }

    # Add optional fields
    if cache_namespace:
        metadata["cachenamespace"] = str(cache_namespace)[:200]
    if operation:
        metadata["operation"] = str(operation)[:200]

    # Build tags for filtering
    tags = ["mcprefcache"]
    if operation:
        tags.append(operation.replace("_", ""))  # e.g., "cacheset", "cacheget"
    if _test_mode_enabled:
        tags.append("testmode")

    return {
        "user_id": user_id,
        "session_id": session_id,
        "metadata": metadata,
        "tags": tags,
        "version": "1.0.0",
    }


# =============================================================================
# Initialize FastMCP Server
# =============================================================================

mcp = FastMCP(
    name="Langfuse-Traced Calculator",
    instructions=f"""A calculator with Langfuse observability and context attribution.

All tool calls are traced to Langfuse with:
- User ID and Session ID from context (for filtering/aggregation)
- Full context metadata (org_id, agent_id, cache_namespace)
- Cache operation spans with hit/miss tracking

Enable test mode with enable_test_context() to simulate different users.

{cache_instructions()}
""",
)

# =============================================================================
# Initialize RefCache with SQLite Backend for Cross-Tool Sharing
# =============================================================================

# Use SQLite backend for persistence and cross-tool reference sharing
# Default path: ~/.cache/mcp-refcache/cache.db (shared with data-tools server)
_sqlite_backend = SQLiteBackend()

print(f"SQLite cache path: {_sqlite_backend.database_path}", file=sys.stderr)

# Create the base cache with SQLite backend
_cache = RefCache(
    name="langfuse-calculator",
    backend=_sqlite_backend,
    default_ttl=3600,
    preview_config=PreviewConfig(
        max_size=64,
        default_strategy=PreviewStrategy.SAMPLE,
    ),
)


class TracedRefCache:
    """RefCache wrapper that adds Langfuse tracing with context propagation.

    This wrapper intercepts cache operations and creates Langfuse spans
    for observability. Each operation is traced with:
    - user_id and session_id (native Langfuse fields for aggregation)
    - Full context metadata (org_id, agent_id, cache_namespace)
    - Cache hit/miss status and timing information

    Uses propagate_attributes() to ensure all child spans inherit context.
    """

    def __init__(self, cache: RefCache) -> None:
        """Initialize the traced cache wrapper.

        Args:
            cache: The underlying RefCache instance to wrap.
        """
        self._cache = cache

    @property
    def preview_config(self) -> PreviewConfig:
        """Expose preview config from underlying cache."""
        return self._cache.preview_config

    def set(
        self,
        key: str,
        value: Any,
        namespace: str = "public",
        **kwargs: Any,
    ) -> Any:
        """Set a value in cache with Langfuse tracing and context propagation.

        Creates a span for the cache set operation with:
        - user_id, session_id propagated to all child spans
        - Full context metadata (org_id, agent_id, namespace)
        - Operation result and ref_id
        """
        if not _langfuse_enabled:
            return self._cache.set(key, value, namespace=namespace, **kwargs)

        # Get Langfuse attributes from current context
        attributes = get_langfuse_attributes(
            cache_namespace=namespace,
            operation="cache_set",
        )

        with (
            langfuse.start_as_current_observation(
                as_type="span",
                name="cache.set",
                input={"key": key, "namespace": namespace},
            ) as span,
            propagate_attributes(
                user_id=attributes["user_id"],
                session_id=attributes["session_id"],
                metadata=attributes["metadata"],
                tags=attributes["tags"],
                version=attributes["version"],
            ),
        ):
            try:
                result = self._cache.set(key, value, namespace=namespace, **kwargs)
                span.update(
                    output={
                        "ref_id": result.ref_id
                        if hasattr(result, "ref_id")
                        else str(result),
                        "success": True,
                    },
                    metadata={
                        "cacheoperation": "set",
                        "namespace": namespace,
                        "userid": attributes["user_id"],
                        "sessionid": attributes["session_id"],
                    },
                )
                langfuse.flush()
                return result
            except Exception as e:
                span.update(
                    output={"error": str(e), "success": False},
                    metadata={
                        "cacheoperation": "set",
                        "errortype": type(e).__name__,
                    },
                )
                langfuse.flush()
                raise

    def get(
        self,
        ref_id: str,
        actor: Any = None,
        **kwargs: Any,
    ) -> CacheResponse:
        """Get a value from cache with Langfuse tracing and context propagation.

        Creates a span for the cache get operation with:
        - user_id, session_id propagated to all child spans
        - Cache hit/miss status
        - Pagination and preview information
        """
        if not _langfuse_enabled:
            return self._cache.get(ref_id, actor=actor, **kwargs)

        # Get Langfuse attributes from current context
        attributes = get_langfuse_attributes(
            operation="cache_get",
        )

        with (
            langfuse.start_as_current_observation(
                as_type="span",
                name="cache.get",
                input={"ref_id": ref_id},
            ) as span,
            propagate_attributes(
                user_id=attributes["user_id"],
                session_id=attributes["session_id"],
                metadata=attributes["metadata"],
                tags=attributes["tags"],
                version=attributes["version"],
            ),
        ):
            try:
                result = self._cache.get(ref_id, actor=actor, **kwargs)
                is_hit = result is not None and result.preview is not None

                span.update(
                    output={
                        "cache_hit": is_hit,
                        "preview_strategy": getattr(result, "preview_strategy", None),
                    },
                    metadata={
                        "cacheoperation": "get",
                        "cachehit": str(is_hit).lower(),
                        "refid": ref_id,
                        "userid": attributes["user_id"],
                        "sessionid": attributes["session_id"],
                    },
                )
                langfuse.flush()
                return result
            except Exception as e:
                span.update(
                    output={"error": str(e), "cache_hit": False},
                    metadata={
                        "cacheoperation": "get",
                        "errortype": type(e).__name__,
                    },
                )
                langfuse.flush()
                raise

    def resolve(self, ref_id: str, actor: Any = None) -> Any:
        """Resolve a ref_id to its value with Langfuse tracing.

        Creates a span for ref_id resolution with context propagation.
        """
        if not _langfuse_enabled:
            return self._cache.resolve(ref_id, actor=actor)

        # Get Langfuse attributes from current context
        attributes = get_langfuse_attributes(
            operation="cache_resolve",
        )

        with (
            langfuse.start_as_current_observation(
                as_type="span",
                name="cache.resolve",
                input={"ref_id": ref_id},
            ) as span,
            propagate_attributes(
                user_id=attributes["user_id"],
                session_id=attributes["session_id"],
                metadata=attributes["metadata"],
                tags=attributes["tags"],
                version=attributes["version"],
            ),
        ):
            try:
                result = self._cache.resolve(ref_id, actor=actor)
                span.update(
                    output={
                        "resolved": result is not None,
                        "value_type": type(result).__name__ if result else None,
                    },
                    metadata={
                        "cacheoperation": "resolve",
                        "refid": ref_id,
                        "userid": attributes["user_id"],
                        "sessionid": attributes["session_id"],
                    },
                )
                langfuse.flush()
                return result
            except Exception as e:
                span.update(
                    output={"error": str(e), "resolved": False},
                    metadata={
                        "cacheoperation": "resolve",
                        "errortype": type(e).__name__,
                    },
                )
                langfuse.flush()
                raise

    def cached(
        self,
        namespace: str = "public",
        **decorator_kwargs: Any,
    ) -> Callable[[Callable[P, T]], Callable[P, dict[str, Any]]]:
        """Decorator that caches function results with Langfuse tracing.

        This enhanced decorator wraps the underlying @cache.cached() decorator
        and adds Langfuse spans for cache operations. Each cache operation
        is traced with:
        - user_id and session_id for attribution
        - Cache hit/miss status
        - Namespace and operation metadata

        Args:
            namespace: Cache namespace (supports context templates like "user:{user_id}")
            **decorator_kwargs: Additional arguments passed to underlying cached()

        Returns:
            Decorated function that returns structured cache responses with tracing.

        Example:
            @traced_cache.cached(namespace="user:{user_id}")
            async def get_user_data(user_id: str) -> dict:
                return {"name": "Alice"}
        """
        # Get the underlying decorator
        underlying_decorator = self._cache.cached(
            namespace=namespace, **decorator_kwargs
        )

        def tracing_decorator(
            func: Callable[P, T],
        ) -> Callable[P, dict[str, Any]]:
            """Wrap function with Langfuse tracing for cache operations."""
            # Apply underlying decorator first
            cached_func = underlying_decorator(func)

            if asyncio.iscoroutinefunction(func):

                @functools.wraps(cached_func)
                async def async_traced_wrapper(
                    *args: P.args, **kwargs: P.kwargs
                ) -> dict[str, Any]:
                    if not _langfuse_enabled:
                        return await cached_func(*args, **kwargs)

                    # Get Langfuse attributes from context
                    attributes = get_langfuse_attributes(
                        cache_namespace=namespace,
                        operation="cached_call",
                    )

                    with (
                        langfuse.start_as_current_observation(
                            as_type="span",
                            name=f"cache.{func.__name__}",
                            input={
                                "function": func.__name__,
                                "namespace": namespace,
                                "args_count": len(args),
                            },
                        ) as span,
                        propagate_attributes(
                            user_id=attributes["user_id"],
                            session_id=attributes["session_id"],
                            metadata=attributes["metadata"],
                            tags=attributes["tags"],
                            version=attributes["version"],
                        ),
                    ):
                        try:
                            result = await cached_func(*args, **kwargs)

                            # Determine if this was a cache hit
                            # Cache hits typically return faster and have ref_id
                            is_cached = "ref_id" in result

                            span.update(
                                output={
                                    "ref_id": result.get("ref_id"),
                                    "is_complete": result.get("is_complete"),
                                    "cached": is_cached,
                                },
                                metadata={
                                    "cacheoperation": "cached_call",
                                    "function": func.__name__,
                                    "namespace": namespace,
                                    "userid": attributes["user_id"],
                                    "sessionid": attributes["session_id"],
                                },
                            )
                            langfuse.flush()
                            return result
                        except Exception as e:
                            span.update(
                                output={"error": str(e), "cached": False},
                                metadata={
                                    "cacheoperation": "cached_call",
                                    "errortype": type(e).__name__,
                                },
                            )
                            langfuse.flush()
                            raise

                return async_traced_wrapper  # type: ignore
            else:

                @functools.wraps(cached_func)
                def sync_traced_wrapper(
                    *args: P.args, **kwargs: P.kwargs
                ) -> dict[str, Any]:
                    if not _langfuse_enabled:
                        return cached_func(*args, **kwargs)

                    # Get Langfuse attributes from context
                    attributes = get_langfuse_attributes(
                        cache_namespace=namespace,
                        operation="cached_call",
                    )

                    with (
                        langfuse.start_as_current_observation(
                            as_type="span",
                            name=f"cache.{func.__name__}",
                            input={
                                "function": func.__name__,
                                "namespace": namespace,
                                "args_count": len(args),
                            },
                        ) as span,
                        propagate_attributes(
                            user_id=attributes["user_id"],
                            session_id=attributes["session_id"],
                            metadata=attributes["metadata"],
                            tags=attributes["tags"],
                            version=attributes["version"],
                        ),
                    ):
                        try:
                            result = cached_func(*args, **kwargs)

                            # Determine if this was a cache hit
                            is_cached = "ref_id" in result

                            span.update(
                                output={
                                    "ref_id": result.get("ref_id"),
                                    "is_complete": result.get("is_complete"),
                                    "cached": is_cached,
                                },
                                metadata={
                                    "cacheoperation": "cached_call",
                                    "function": func.__name__,
                                    "namespace": namespace,
                                    "userid": attributes["user_id"],
                                    "sessionid": attributes["session_id"],
                                },
                            )
                            langfuse.flush()
                            return result
                        except Exception as e:
                            span.update(
                                output={"error": str(e), "cached": False},
                                metadata={
                                    "cacheoperation": "cached_call",
                                    "errortype": type(e).__name__,
                                },
                            )
                            langfuse.flush()
                            raise

                return sync_traced_wrapper  # type: ignore

        return tracing_decorator

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to underlying cache."""
        return getattr(self._cache, name)


# Create traced cache wrapper
cache = TracedRefCache(_cache)


# =============================================================================
# Pydantic Models
# =============================================================================


class CalculateInput(BaseModel):
    """Input for calculation."""

    expression: str = Field(
        description="Mathematical expression to evaluate",
        examples=["2 + 2", "sqrt(16)", "sin(3.14159/2)"],
    )


class SequenceInput(BaseModel):
    """Input for sequence generation."""

    count: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Number of elements to generate",
    )


# =============================================================================
# Context Management Tools (Test Mode)
# =============================================================================


@mcp.tool
def enable_test_context(enabled: bool = True) -> dict[str, Any]:
    """Enable or disable test context mode for Langfuse attribution demos.

    When enabled, all traces will include user_id, session_id, and metadata
    from the MockContext. This allows testing Langfuse filtering and
    aggregation without a real FastMCP authentication setup.

    Args:
        enabled: Whether to enable test context mode (default: True).

    Returns:
        Status dict with current test mode state and context values.
    """
    global _test_mode_enabled
    _test_mode_enabled = enabled

    if enabled:
        return {
            "test_mode": True,
            "context": MockContext.get_current_state(),
            "langfuse_enabled": _langfuse_enabled,
            "message": "Test context mode enabled. Traces will include user/session from MockContext.",
        }
    return {
        "test_mode": False,
        "context": None,
        "langfuse_enabled": _langfuse_enabled,
        "message": "Test context mode disabled. Context will come from real FastMCP.",
    }


@mcp.tool
def set_test_context(
    user_id: str | None = None,
    org_id: str | None = None,
    session_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Set test context values for Langfuse attribution demos.

    Changes here affect what user_id, session_id, and metadata are
    sent to Langfuse traces. Use this to test filtering by different
    users or sessions in the Langfuse dashboard.

    Args:
        user_id: User identity (e.g., "alice", "bob").
        org_id: Organization identity (e.g., "acme", "globex").
        session_id: Session identifier for grouping traces.
        agent_id: Agent identity (e.g., "claude", "gpt4").

    Returns:
        Updated context state and example of Langfuse attributes.
    """
    if user_id is not None:
        MockContext.set_state(user_id=user_id)
    if org_id is not None:
        MockContext.set_state(org_id=org_id)
    if agent_id is not None:
        MockContext.set_state(agent_id=agent_id)
    if session_id is not None:
        MockContext.set_session_id(session_id)

    # Show what Langfuse will receive
    attributes = get_langfuse_attributes()

    return {
        "context": MockContext.get_current_state(),
        "langfuse_attributes": {
            "user_id": attributes["user_id"],
            "session_id": attributes["session_id"],
            "metadata": attributes["metadata"],
            "tags": attributes["tags"],
        },
        "message": "Context updated. Next tool calls will use these Langfuse attributes.",
    }


@mcp.tool
def reset_test_context() -> dict[str, Any]:
    """Reset test context to default demo values.

    Returns:
        Reset context state.
    """
    MockContext.reset()
    return {
        "context": MockContext.get_current_state(),
        "message": "Context reset to default demo values.",
    }


# =============================================================================
# Tool Implementations with Langfuse Tracing + Context Propagation
# =============================================================================


@mcp.tool
@observe(name="calculate", capture_input=True, capture_output=True)
def calculate(expression: str) -> dict[str, Any]:
    """Evaluate a mathematical expression with Langfuse tracing.

    All calculations are traced to Langfuse with:
    - user_id, session_id, org_id from context
    - Expression and result
    - Timing and error information

    Note: This is a pure computation tool with no LLM calls, so there are
    no inference costs to track. Langfuse cost tracking is only relevant
    for tools that make actual LLM API calls (OpenAI, Anthropic, etc.).

    Args:
        expression: Mathematical expression to evaluate.

    Returns:
        Dict with result and tracing metadata.
    """
    import math

    # Get Langfuse attributes from context and propagate
    attributes = get_langfuse_attributes(operation="calculate")

    # Propagate attributes early so all child spans get them
    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata=attributes["metadata"],
        tags=attributes["tags"],
        version=attributes["version"],
    ):
        # Safe evaluation context
        safe_context = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            "pi": math.pi,
            "e": math.e,
            "pow": pow,
        }

        try:
            result = eval(expression, {"__builtins__": {}}, safe_context)

            result_dict = {
                "expression": expression,
                "result": result,
                "type": type(result).__name__,
                "traced_user": attributes["user_id"],
                "traced_session": attributes["session_id"],
            }
            langfuse.flush()
            return result_dict
        except Exception as e:
            error_dict = {
                "expression": expression,
                "error": str(e),
                "type": "error",
                "traced_user": attributes["user_id"],
                "traced_session": attributes["session_id"],
            }
            langfuse.flush()
            return error_dict


@mcp.tool
@observe(name="generate_fibonacci")
@cache.cached(namespace="sequences", max_size=50)
async def generate_fibonacci(count: int = 20) -> list[int]:
    """Generate Fibonacci sequence with caching and Langfuse tracing.

    The result is cached and traced with full context propagation.
    Langfuse traces include user_id, session_id, org_id for filtering.

    Note: This is a pure computation with no LLM calls, so there are no
    inference costs to track. The @cache.cached() decorator returns a
    structured response with ref_id and cache metadata.

    Args:
        count: Number of Fibonacci numbers to generate (1-1000).

    Returns:
        Cache response dict with ref_id, value/preview, and pagination info.
    """
    # Get Langfuse attributes and propagate to all child spans
    attributes = get_langfuse_attributes(
        cache_namespace="sequences",
        operation="generate_fibonacci",
    )

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata=attributes["metadata"],
        tags=attributes["tags"],
        version=attributes["version"],
    ):
        if count <= 0:
            return []
        if count == 1:
            return [0]
        if count == 2:
            return [0, 1]

        sequence = [0, 1]
        for _ in range(2, count):
            sequence.append(sequence[-1] + sequence[-2])
        langfuse.flush()
        return sequence


@mcp.tool
@observe(name="generate_primes")
@cache.cached(namespace="sequences", max_size=50)
async def generate_primes(count: int = 20) -> list[int]:
    """Generate prime numbers with caching and Langfuse tracing.

    The result is cached and traced with full context propagation.
    Langfuse traces include user_id, session_id, org_id for filtering.

    Note: This is a pure computation with no LLM calls, so there are no
    inference costs to track. The @cache.cached() decorator returns a
    structured response with ref_id and cache metadata.

    Args:
        count: Number of prime numbers to generate (1-1000).

    Returns:
        Cache response dict with ref_id, value/preview, and pagination info.
    """
    # Get Langfuse attributes and propagate to all child spans
    attributes = get_langfuse_attributes(
        cache_namespace="sequences",
        operation="generate_primes",
    )

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata=attributes["metadata"],
        tags=attributes["tags"],
        version=attributes["version"],
    ):
        if count <= 0:
            return []

        primes = []
        candidate = 2

        while len(primes) < count:
            is_prime = True
            for p in primes:
                if p * p > candidate:
                    break
                if candidate % p == 0:
                    is_prime = False
                    break
            if is_prime:
                primes.append(candidate)
            candidate += 1

        langfuse.flush()
        return primes


@mcp.tool
@observe(name="get_cached_result")
async def get_cached_result(
    ref_id: str,
    page: int | None = None,
    page_size: int | None = None,
    max_size: int | None = None,
) -> dict[str, Any]:
    """Retrieve a cached result by ref_id with Langfuse tracing.

    This operation is traced with full context propagation, showing
    cache hit/miss status and user attribution in Langfuse.

    Args:
        ref_id: Reference ID from a previous tool call.
        page: Page number for pagination (1-indexed).
        page_size: Number of items per page.
        max_size: Maximum preview size (overrides defaults).

    Returns:
        Cached value with metadata and trace information.
    """
    # Get Langfuse attributes and propagate
    attributes = get_langfuse_attributes(operation="get_cached_result")

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata=attributes["metadata"],
        tags=attributes["tags"],
        version=attributes["version"],
    ):
        try:
            response = cache.get(
                ref_id,
                page=page,
                page_size=page_size,
                max_size=max_size,
            )
            if response is None:
                return {
                    "error": f"Reference not found: {ref_id}",
                    "ref_id": ref_id,
                    "traced_user": attributes["user_id"],
                    "traced_session": attributes["session_id"],
                }

            result = response.model_dump()
            result["traced_user"] = attributes["user_id"]
            result["traced_session"] = attributes["session_id"]
            langfuse.flush()
            return result
        except Exception as e:
            error_result = {
                "error": str(e),
                "ref_id": ref_id,
                "traced_user": attributes["user_id"],
                "traced_session": attributes["session_id"],
            }
            langfuse.flush()
            return error_result


# =============================================================================
# Traced Tool Wrapper Example
# =============================================================================


# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def traced_tool(name: str | None = None) -> Callable[[F], F]:
    """Decorator that combines Langfuse tracing with MCP tool registration.

    This is a convenience decorator that applies both @observe and @mcp.tool.
    It also automatically propagates context attributes to child spans.

    Args:
        name: Optional name for the trace span.

    Example:
        @traced_tool("my_tool")
        async def my_tool(arg: str) -> dict:
            return {"result": arg}
    """

    def decorator(func: F) -> F:
        traced = observe(name=name or func.__name__)(func)
        return mcp.tool(traced)  # type: ignore[return-value]

    return decorator


@traced_tool("get_trace_info")
async def get_trace_info() -> dict[str, Any]:
    """Get information about the current Langfuse trace and context.

    Returns metadata about Langfuse tracing status and current
    context values for debugging.

    Returns:
        Dict with Langfuse configuration and current context.
    """
    attributes = get_langfuse_attributes()

    return {
        "langfuse_enabled": _langfuse_enabled,
        "langfuse_host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        "public_key_set": bool(os.getenv("LANGFUSE_PUBLIC_KEY")),
        "secret_key_set": bool(os.getenv("LANGFUSE_SECRET_KEY")),
        "test_mode_enabled": _test_mode_enabled,
        "current_context": MockContext.get_current_state()
        if _test_mode_enabled
        else None,
        "langfuse_attributes": {
            "user_id": attributes["user_id"],
            "session_id": attributes["session_id"],
            "metadata": attributes["metadata"],
            "tags": attributes["tags"],
        },
        "message": (
            "Traces are being sent to Langfuse with user/session attribution"
            if _langfuse_enabled
            else "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable tracing"
        ),
    }


# =============================================================================
# Prompts
# =============================================================================


@mcp.prompt
def langfuse_guide() -> str:
    """Guide for using Langfuse-traced tools with context propagation."""
    return """# Langfuse-Traced Calculator Guide

## Context Propagation (Langfuse SDK v3)

All tool calls automatically propagate context to Langfuse traces:

1. **User Attribution**
   - `user_id`: Tracks which user made the request
   - `session_id`: Groups related requests into sessions
   - `metadata`: Additional context (org_id, agent_id, cache_namespace)

2. **Testing Context**
   Enable test mode to simulate different users:
   ```
   enable_test_context(True)
   set_test_context(user_id="alice", org_id="acme", session_id="chat-001")
   ```

3. **Cache Operations**
   Cache set/get/resolve operations create child spans that inherit
   user_id and session_id for complete attribution.

## Example Workflow

```python
# 1. Enable test mode and set user
enable_test_context(True)
set_test_context(user_id="alice", session_id="demo-session")

# 2. Generate a sequence (traced with user attribution)
result = generate_fibonacci(count=100)

# 3. Retrieve cached result (same user in trace)
cached = get_cached_result(result["ref_id"])

# 4. Check trace info
info = get_trace_info()
```

## Viewing Traces in Langfuse

1. Go to your Langfuse dashboard
2. Navigate to Traces
3. Filter by:
   - **User**: "alice" (or any user_id you set)
   - **Session**: "demo-session"
   - **Tags**: "mcprefcache", "cacheset", "cacheget"
   - **Metadata**: orgid, agentid, cachenamespace

## Best Practices

- Call `propagate_attributes()` early in your trace
- Use meaningful user_id and session_id values
- Keep metadata keys alphanumeric (no spaces/special chars)
- Limit values to 200 characters
"""


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run the Langfuse-traced MCP server."""
    parser = argparse.ArgumentParser(
        description="Langfuse-Traced MCP Server with RefCache and Context Propagation",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)",
    )

    args = parser.parse_args()

    print(f"Langfuse tracing: {'enabled' if _langfuse_enabled else 'disabled'}")
    print("Context propagation: enabled (user_id, session_id, metadata)")
    print("Use enable_test_context() to simulate different users")

    try:
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        else:
            mcp.run(
                transport="sse",
                host=args.host,
                port=args.port,
            )
    finally:
        # Ensure all traces are flushed on exit
        if _langfuse_enabled:
            langfuse.flush()


if __name__ == "__main__":
    main()
