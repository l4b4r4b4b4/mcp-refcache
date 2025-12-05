"""Pytest configuration and fixtures for mcp-refcache tests."""

from typing import Any

import pytest

from mcp_refcache import AccessPolicy, Permission, PreviewConfig
from mcp_refcache.models import PreviewStrategy, SizeMode


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


@pytest.fixture
def default_preview_config() -> PreviewConfig:
    """Default preview configuration."""
    return PreviewConfig()


@pytest.fixture
def character_preview_config() -> PreviewConfig:
    """Character-based preview configuration."""
    return PreviewConfig(
        size_mode=SizeMode.CHARACTER,
        max_size=2000,
        default_strategy=PreviewStrategy.TRUNCATE,
    )


@pytest.fixture
def public_policy() -> AccessPolicy:
    """Public access policy - full access for everyone."""
    return AccessPolicy(
        user_permissions=Permission.FULL,
        agent_permissions=Permission.FULL,
    )


@pytest.fixture
def restricted_policy() -> AccessPolicy:
    """Restricted policy - agent can execute but not read."""
    return AccessPolicy(
        user_permissions=Permission.FULL,
        agent_permissions=Permission.EXECUTE,
    )


@pytest.fixture
def read_only_policy() -> AccessPolicy:
    """Read-only access policy for both user and agent."""
    return AccessPolicy(
        user_permissions=Permission.READ,
        agent_permissions=Permission.READ,
    )
