"""Pytest configuration and fixtures for mcp-refcache tests."""

import asyncio
from collections.abc import Generator
from typing import Any

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_value() -> dict[str, Any]:
    """Sample cacheable value for testing."""
    return {
        "id": 123,
        "name": "Test User",
        "email": "test@example.com",
        "metadata": {
            "created_at": "2024-01-01T00:00:00Z",
            "tags": ["test", "sample"],
        },
    }


@pytest.fixture
def large_value() -> dict[str, Any]:
    """Large value that should trigger preview generation."""
    return {
        "items": [{"id": i, "name": f"Item {i}"} for i in range(1000)],
        "total": 1000,
    }


@pytest.fixture
def sample_namespace() -> str:
    """Sample namespace for testing."""
    return "test:unit"


@pytest.fixture
def session_namespace() -> str:
    """Session-scoped namespace for testing."""
    return "session:test-session-123"


@pytest.fixture
def user_namespace() -> str:
    """User-scoped namespace for testing."""
    return "user:test-user-456"


# TODO: Add these fixtures once core classes are implemented
#
# @pytest.fixture
# def cache() -> Generator[RefCache, None, None]:
#     """Create a fresh in-memory cache for each test."""
#     cache = RefCache(
#         name="test-cache",
#         backend="memory",
#         default_namespace="test:unit",
#     )
#     yield cache
#     cache.clear()
#
#
# @pytest.fixture
# async def async_cache() -> AsyncGenerator[RefCache, None]:
#     """Create an async-compatible cache for each test."""
#     cache = RefCache(
#         name="test-async-cache",
#         backend="memory",
#         default_namespace="test:unit",
#     )
#     yield cache
#     await cache.async_clear()
#
#
# @pytest.fixture
# def cache_with_namespaces() -> Generator[RefCache, None, None]:
#     """Cache with multiple namespaces configured."""
#     cache = RefCache(
#         name="test-ns-cache",
#         namespaces=[
#             Namespace.PUBLIC,
#             Namespace.session("test-session"),
#             Namespace.user("test-user"),
#             Namespace.custom("project:test"),
#         ],
#     )
#     yield cache
#     cache.clear()
#
#
# @pytest.fixture
# def restricted_policy() -> AccessPolicy:
#     """Access policy where agent can execute but not read."""
#     return AccessPolicy(
#         user_permissions=Permission.FULL,
#         agent_permissions=Permission.EXECUTE,
#     )
#
#
# @pytest.fixture
# def read_only_policy() -> AccessPolicy:
#     """Read-only access policy for both user and agent."""
#     return AccessPolicy(
#         user_permissions=Permission.READ,
#         agent_permissions=Permission.READ,
#     )
