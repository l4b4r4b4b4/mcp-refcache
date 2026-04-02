"""Targeted unit tests for FastMCP admin helper utilities.

These tests focus on:
- `_check_admin` (sync/async checker behavior and error paths)
- `_format_reference_info` (formatting branches for metadata/policy/value previews)
- `PermissionDeniedError` (message handling and inheritance)
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from mcp_refcache.fastmcp.admin_tools import (
    AdminToolError,
    PermissionDeniedError,
    _check_admin,
    _format_reference_info,
)

# =============================================================================
# _check_admin
# =============================================================================


@pytest.mark.asyncio
async def test_check_admin_no_checker_raises() -> None:
    """None admin_check should deny access with a specific message."""
    with pytest.raises(PermissionDeniedError, match="No admin check configured"):
        await _check_admin(ctx=object(), admin_check=None)


@pytest.mark.asyncio
async def test_check_admin_no_context_raises() -> None:
    """None context should deny access before checker invocation."""
    checker = lambda _ctx: True  # noqa: E731

    with pytest.raises(
        PermissionDeniedError,
        match="Context required for admin verification",
    ):
        await _check_admin(ctx=None, admin_check=checker)


@pytest.mark.asyncio
async def test_check_admin_sync_returns_false() -> None:
    """Sync checker returning False should raise PermissionDeniedError."""
    checker = lambda _ctx: False  # noqa: E731

    with pytest.raises(PermissionDeniedError, match="Admin access required"):
        await _check_admin(ctx=object(), admin_check=checker)


@pytest.mark.asyncio
async def test_check_admin_sync_returns_true() -> None:
    """Sync checker returning True should allow access."""
    checker = lambda _ctx: True  # noqa: E731

    await _check_admin(ctx=object(), admin_check=checker)


@pytest.mark.asyncio
async def test_check_admin_async_returns_true() -> None:
    """Async checker returning True should allow access."""

    async def checker(_ctx: object) -> bool:
        return True

    await _check_admin(ctx=object(), admin_check=checker)


@pytest.mark.asyncio
async def test_check_admin_async_returns_false() -> None:
    """Async checker returning False should deny access."""

    async def checker(_ctx: object) -> bool:
        return False

    with pytest.raises(PermissionDeniedError, match="Admin access required"):
        await _check_admin(ctx=object(), admin_check=checker)


# =============================================================================
# _format_reference_info
# =============================================================================


def test_format_basic_entry() -> None:
    """Basic entry should include core metadata fields and ISO datetimes."""
    created_at = datetime(2024, 1, 1, 12, 30, tzinfo=timezone.utc)
    expires_at = datetime(2024, 1, 2, 12, 30, tzinfo=timezone.utc)
    entry = SimpleNamespace(
        namespace="public",
        created_at=created_at,
        expires_at=expires_at,
        tool_name="example_tool",
        owner="user:alice",
    )

    info = _format_reference_info("ref-123", entry)

    assert info["ref_id"] == "ref-123"
    assert info["namespace"] == "public"
    assert info["created_at"] == created_at.isoformat()
    assert info["expires_at"] == expires_at.isoformat()
    assert info["tool_name"] == "example_tool"
    assert info["owner"] == "user:alice"
    assert "policy" not in info
    assert "value_type" not in info
    assert "preview" not in info


def test_format_entry_no_optional_attrs() -> None:
    """Entry with no optional attrs should use safe defaults."""
    entry = SimpleNamespace()

    info = _format_reference_info("ref-min", entry)

    assert info["ref_id"] == "ref-min"
    assert info["namespace"] == "unknown"
    assert info["created_at"] is None
    assert info["expires_at"] is None
    assert info["tool_name"] is None
    assert info["owner"] is None
    assert "policy" not in info
    assert "value_type" not in info
    assert "preview" not in info


def test_format_entry_with_policy() -> None:
    """Policy details should be stringified and included when present."""
    policy = SimpleNamespace(
        user_permissions="READ",
        agent_permissions="EXECUTE",
        owner_permissions="FULL",
        session_bound=True,
    )
    entry = SimpleNamespace(policy=policy)

    info = _format_reference_info("ref-pol", entry)

    assert "policy" in info
    assert info["policy"] == {
        "user_permissions": "READ",
        "agent_permissions": "EXECUTE",
        "owner_permissions": "FULL",
        "session_bound": True,
    }


def test_format_entry_with_list_value_no_preview() -> None:
    """List value should include type/size without preview when disabled."""
    entry = SimpleNamespace(value=[1, 2, 3])

    info = _format_reference_info("ref-list", entry, include_preview=False)

    assert info["value_type"] == "list"
    assert info["value_size"] == 3
    assert "preview" not in info


def test_format_entry_with_list_value_preview() -> None:
    """Long list preview should include first 5 values and ellipsis marker."""
    entry = SimpleNamespace(value=[1, 2, 3, 4, 5, 6, 7])

    info = _format_reference_info("ref-list-preview", entry, include_preview=True)

    assert info["value_type"] == "list"
    assert info["value_size"] == 7
    assert info["preview"] == [1, 2, 3, 4, 5, "..."]


def test_format_entry_with_short_list_preview() -> None:
    """Short list preview should include full list without ellipsis."""
    entry = SimpleNamespace(value=[1, 2])

    info = _format_reference_info("ref-short-list", entry, include_preview=True)

    assert info["preview"] == [1, 2]


def test_format_entry_with_dict_value_preview() -> None:
    """Large dict preview should include first 5 keys and '...' sentinel key."""
    entry = SimpleNamespace(
        value={"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7}
    )

    info = _format_reference_info("ref-dict", entry, include_preview=True)

    assert info["value_type"] == "dict"
    assert info["value_size"] == 7
    assert info["preview"] == {
        "a": "...",
        "b": "...",
        "c": "...",
        "d": "...",
        "e": "...",
        "...": "...",
    }


def test_format_entry_with_small_dict_preview() -> None:
    """Small dict preview should include only existing keys."""
    entry = SimpleNamespace(value={"a": 1})

    info = _format_reference_info("ref-small-dict", entry, include_preview=True)

    assert info["value_type"] == "dict"
    assert info["value_size"] == 1
    assert info["preview"] == {"a": "..."}
    assert "..." not in [k for k in info["preview"] if k != "a"]


def test_format_entry_with_string_value_preview() -> None:
    """Short string preview should not be truncated."""
    entry = SimpleNamespace(value="hello world")

    info = _format_reference_info("ref-str", entry, include_preview=True)

    assert info["value_type"] == "str"
    assert info["value_size"] == 11
    assert info["preview"] == "hello world"


def test_format_entry_with_long_string_preview() -> None:
    """Long string preview should be truncated to 100 chars plus ellipsis."""
    long_text = "x" * 200
    entry = SimpleNamespace(value=long_text)

    info = _format_reference_info("ref-long-str", entry, include_preview=True)

    assert info["value_type"] == "str"
    assert info["value_size"] == 200
    assert info["preview"] == ("x" * 100) + "..."
    assert len(info["preview"]) == 103


def test_format_entry_with_numeric_value_preview() -> None:
    """Non-sized scalar preview should be stringified and omit value_size."""
    entry = SimpleNamespace(value=42)

    info = _format_reference_info("ref-num", entry, include_preview=True)

    assert info["value_type"] == "int"
    assert "value_size" not in info
    assert info["preview"] == "42"


# =============================================================================
# PermissionDeniedError
# =============================================================================


def test_permission_denied_default_message() -> None:
    """Default constructor message should be preserved on exception."""
    error = PermissionDeniedError()
    assert error.message == "Admin access required"
    assert str(error) == "Admin access required"


def test_permission_denied_custom_message() -> None:
    """Custom constructor message should be preserved on exception."""
    error = PermissionDeniedError("No admin check configured")
    assert error.message == "No admin check configured"
    assert str(error) == "No admin check configured"


def test_permission_denied_is_admin_tool_error() -> None:
    """PermissionDeniedError should inherit from AdminToolError."""
    error = PermissionDeniedError()
    assert isinstance(error, AdminToolError)
