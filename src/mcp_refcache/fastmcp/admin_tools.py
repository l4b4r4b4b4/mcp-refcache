"""Admin tools for cache management in FastMCP servers.

This module provides permission-gated administrative tools for managing
RefCache instances. These tools are intended for elevated users (admins)
and should NEVER be exposed to agents.

The tools include:
- list_references: Browse cached references with filtering
- get_reference_info: Get detailed info about a specific reference
- delete_reference: Remove a specific reference
- clear_namespace: Clear all references in a namespace
- get_cache_stats: Detailed cache statistics

Security Model:
    All tools require an admin check function that verifies the caller
    has elevated permissions. This is enforced at registration time
    and checked on every tool invocation.

Example:
    ```python
    from fastmcp import FastMCP
    from mcp_refcache import RefCache
    from mcp_refcache.fastmcp.admin_tools import register_admin_tools

    mcp = FastMCP(name="MyServer")
    cache = RefCache(name="my-cache")

    # Define admin check - customize for your auth system
    async def is_admin(ctx: Context) -> bool:
        # Example: Check user role from context
        user_id = getattr(ctx, 'user_id', None)
        return user_id in ADMIN_USER_IDS

    # Register admin tools with prefix
    register_admin_tools(mcp, cache, admin_check=is_admin, prefix="admin_")
    ```

Warning:
    These tools can expose sensitive cached data and modify cache state.
    Only register them in trusted environments with proper authentication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from mcp_refcache import RefCache

# Try to import FastMCP types, but don't fail if not available
try:
    from fastmcp import Context
except ImportError:
    Context = Any  # type: ignore[misc, assignment]


# =============================================================================
# Protocols and Types
# =============================================================================


@runtime_checkable
class AdminChecker(Protocol):
    """Protocol for admin check functions.

    Admin checkers can be sync or async functions that take a Context
    and return True if the caller has admin privileges.
    """

    def __call__(self, ctx: Context) -> bool | Coroutine[Any, Any, bool]:
        """Check if the context represents an admin user.

        Args:
            ctx: The FastMCP context for the current request.

        Returns:
            True if the caller is an admin, False otherwise.
        """
        ...


class AdminToolError(Exception):
    """Base exception for admin tool errors."""

    pass


class PermissionDeniedError(AdminToolError):
    """Raised when a non-admin attempts to use admin tools."""

    def __init__(self, message: str = "Admin access required") -> None:
        """Initialize with optional custom message."""
        super().__init__(message)
        self.message = message


# =============================================================================
# Helper Functions
# =============================================================================


async def _check_admin(
    ctx: Context | None,
    admin_check: AdminChecker | None,
) -> None:
    """Verify admin access or raise PermissionDeniedError.

    Args:
        ctx: The FastMCP context (may be None in some cases).
        admin_check: The admin check function.

    Raises:
        PermissionDeniedError: If admin check fails or no check configured.
    """
    if admin_check is None:
        # No admin check configured - deny by default for safety
        raise PermissionDeniedError("No admin check configured")

    if ctx is None:
        # No context available - can't verify admin status
        raise PermissionDeniedError("Context required for admin verification")

    # Call the admin check (may be sync or async)
    import asyncio

    result = admin_check(ctx)
    if asyncio.iscoroutine(result):
        result = await result

    if not result:
        raise PermissionDeniedError("Admin access required")


def _format_reference_info(
    ref_id: str,
    entry: Any,
    include_preview: bool = False,
) -> dict[str, Any]:
    """Format a cache entry for API response.

    Args:
        ref_id: The reference ID.
        entry: The cache entry object.
        include_preview: Whether to include a preview of the value.

    Returns:
        Formatted dictionary with reference information.
    """
    info: dict[str, Any] = {
        "ref_id": ref_id,
        "namespace": getattr(entry, "namespace", "unknown"),
        "created_at": (
            entry.created_at.isoformat()
            if hasattr(entry, "created_at") and entry.created_at
            else None
        ),
        "expires_at": (
            entry.expires_at.isoformat()
            if hasattr(entry, "expires_at") and entry.expires_at
            else None
        ),
        "tool_name": getattr(entry, "tool_name", None),
        "owner": getattr(entry, "owner", None),
    }

    # Add policy info if available
    if hasattr(entry, "policy") and entry.policy:
        policy = entry.policy
        info["policy"] = {
            "user_permissions": str(getattr(policy, "user_permissions", "N/A")),
            "agent_permissions": str(getattr(policy, "agent_permissions", "N/A")),
            "owner_permissions": str(getattr(policy, "owner_permissions", "N/A")),
            "session_bound": getattr(policy, "session_bound", None),
        }

    # Add value type and size info
    if hasattr(entry, "value"):
        value = entry.value
        info["value_type"] = type(value).__name__
        if isinstance(value, (list, dict, str, bytes)):
            info["value_size"] = len(value)

        if include_preview:
            # Generate a safe preview
            if isinstance(value, str):
                info["preview"] = value[:100] + ("..." if len(value) > 100 else "")
            elif isinstance(value, (list, tuple)):
                info["preview"] = list(value[:5]) + (["..."] if len(value) > 5 else [])
            elif isinstance(value, dict):
                keys = list(value.keys())[:5]
                info["preview"] = dict.fromkeys(keys, "...") | (
                    {"...": "..."} if len(value) > 5 else {}
                )
            else:
                info["preview"] = str(value)[:100]

    return info


# =============================================================================
# Admin Tool Factory Functions
# =============================================================================


def create_list_references_tool(
    cache: RefCache,
    admin_check: AdminChecker | None = None,
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    """Create a tool function for listing cached references.

    Args:
        cache: The RefCache instance to query.
        admin_check: Optional admin verification function.

    Returns:
        Async tool function for listing references.
    """

    async def list_references(
        namespace: str | None = None,
        include_expired: bool = False,
        include_preview: bool = False,
        limit: int = 50,
        offset: int = 0,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """List cached references with optional filtering.

        Args:
            namespace: Filter by namespace (e.g., 'public', 'user:alice').
            include_expired: Include expired references in results.
            include_preview: Include value previews in results.
            limit: Maximum number of results (default: 50, max: 100).
            offset: Offset for pagination.
            ctx: FastMCP context for admin verification.

        Returns:
            Dictionary with references list and pagination info.

        Raises:
            PermissionDeniedError: If caller is not an admin.
        """
        await _check_admin(ctx, admin_check)

        # Clamp limit
        limit = min(max(1, limit), 100)
        offset = max(0, offset)

        # Get the backend storage
        backend = cache._backend
        references: list[dict[str, Any]] = []
        total_count = 0

        # Iterate through backend entries
        # Note: This assumes memory backend with _storage attribute
        # For production, backends should implement a list/scan method
        if hasattr(backend, "_storage"):
            all_entries = list(backend._storage.items())

            # Filter by namespace if specified
            if namespace:
                all_entries = [
                    (ref_id, entry)
                    for ref_id, entry in all_entries
                    if getattr(entry, "namespace", "").startswith(namespace)
                ]

            # Filter expired if not included
            if not include_expired:
                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)
                all_entries = [
                    (ref_id, entry)
                    for ref_id, entry in all_entries
                    if not (
                        hasattr(entry, "expires_at")
                        and entry.expires_at
                        and entry.expires_at < now
                    )
                ]

            total_count = len(all_entries)

            # Apply pagination
            paginated = all_entries[offset : offset + limit]

            # Format entries
            for ref_id, entry in paginated:
                references.append(
                    _format_reference_info(ref_id, entry, include_preview)
                )

        return {
            "references": references,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count,
            "namespace_filter": namespace,
        }

    return list_references


def create_get_reference_info_tool(
    cache: RefCache,
    admin_check: AdminChecker | None = None,
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    """Create a tool function for getting detailed reference info.

    Args:
        cache: The RefCache instance to query.
        admin_check: Optional admin verification function.

    Returns:
        Async tool function for getting reference details.
    """

    async def get_reference_info(
        ref_id: str,
        include_value: bool = False,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Get detailed information about a cached reference.

        Args:
            ref_id: The reference ID to look up.
            include_value: Include the full cached value (use with caution).
            ctx: FastMCP context for admin verification.

        Returns:
            Dictionary with detailed reference information.

        Raises:
            PermissionDeniedError: If caller is not an admin.
        """
        await _check_admin(ctx, admin_check)

        backend = cache._backend

        if hasattr(backend, "_storage"):
            entry = backend._storage.get(ref_id)
            if entry is None:
                return {
                    "error": "Not found",
                    "message": f"Reference '{ref_id}' not found",
                    "ref_id": ref_id,
                }

            info = _format_reference_info(ref_id, entry, include_preview=True)

            if include_value and hasattr(entry, "value"):
                info["value"] = entry.value

            return info

        return {
            "error": "Unsupported backend",
            "message": "Backend does not support direct access",
        }

    return get_reference_info


def create_delete_reference_tool(
    cache: RefCache,
    admin_check: AdminChecker | None = None,
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    """Create a tool function for deleting a reference.

    Args:
        cache: The RefCache instance to modify.
        admin_check: Optional admin verification function.

    Returns:
        Async tool function for deleting references.
    """

    async def delete_reference(
        ref_id: str,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Delete a specific cached reference.

        Args:
            ref_id: The reference ID to delete.
            ctx: FastMCP context for admin verification.

        Returns:
            Confirmation of deletion or error.

        Raises:
            PermissionDeniedError: If caller is not an admin.
        """
        await _check_admin(ctx, admin_check)

        backend = cache._backend

        if hasattr(backend, "_storage"):
            if ref_id in backend._storage:
                del backend._storage[ref_id]
                return {
                    "success": True,
                    "message": f"Reference '{ref_id}' deleted",
                    "ref_id": ref_id,
                }
            else:
                return {
                    "success": False,
                    "error": "Not found",
                    "message": f"Reference '{ref_id}' not found",
                    "ref_id": ref_id,
                }

        return {
            "success": False,
            "error": "Unsupported backend",
            "message": "Backend does not support deletion",
        }

    return delete_reference


def create_clear_namespace_tool(
    cache: RefCache,
    admin_check: AdminChecker | None = None,
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    """Create a tool function for clearing a namespace.

    Args:
        cache: The RefCache instance to modify.
        admin_check: Optional admin verification function.

    Returns:
        Async tool function for clearing namespaces.
    """

    async def clear_namespace(
        namespace: str,
        include_children: bool = True,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Clear all references in a namespace.

        Args:
            namespace: The namespace to clear (e.g., 'user:alice').
            include_children: Also clear child namespaces (e.g., 'user:alice:temp').
            ctx: FastMCP context for admin verification.

        Returns:
            Confirmation with count of deleted references.

        Raises:
            PermissionDeniedError: If caller is not an admin.
        """
        await _check_admin(ctx, admin_check)

        if not namespace:
            return {
                "success": False,
                "error": "Invalid namespace",
                "message": "Namespace cannot be empty",
            }

        backend = cache._backend
        deleted_count = 0

        if hasattr(backend, "_storage"):
            # Find matching references
            to_delete = []
            for ref_id, entry in backend._storage.items():
                entry_ns = getattr(entry, "namespace", "")
                if include_children:
                    if entry_ns == namespace or entry_ns.startswith(f"{namespace}:"):
                        to_delete.append(ref_id)
                else:
                    if entry_ns == namespace:
                        to_delete.append(ref_id)

            # Delete them
            for ref_id in to_delete:
                del backend._storage[ref_id]
                deleted_count += 1

            return {
                "success": True,
                "message": f"Cleared {deleted_count} references from namespace '{namespace}'",
                "namespace": namespace,
                "deleted_count": deleted_count,
                "include_children": include_children,
            }

        return {
            "success": False,
            "error": "Unsupported backend",
            "message": "Backend does not support clearing",
        }

    return clear_namespace


def create_get_cache_stats_tool(
    cache: RefCache,
    admin_check: AdminChecker | None = None,
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    """Create a tool function for getting cache statistics.

    Args:
        cache: The RefCache instance to query.
        admin_check: Optional admin verification function.

    Returns:
        Async tool function for getting cache statistics.
    """

    async def get_cache_stats(
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Get detailed cache statistics.

        Args:
            ctx: FastMCP context for admin verification.

        Returns:
            Dictionary with cache statistics.

        Raises:
            PermissionDeniedError: If caller is not an admin.
        """
        await _check_admin(ctx, admin_check)

        backend = cache._backend
        stats: dict[str, Any] = {
            "cache_name": cache.name,
            "default_ttl_seconds": cache.default_ttl,
            "preview_config": {
                "size_mode": cache.preview_config.size_mode.value,
                "max_size": cache.preview_config.max_size,
                "default_strategy": cache.preview_config.default_strategy.value,
            },
            "default_policy": {
                "user_permissions": str(cache.default_policy.user_permissions),
                "agent_permissions": str(cache.default_policy.agent_permissions),
            },
        }

        if hasattr(backend, "_storage"):
            entries = list(backend._storage.values())
            stats["total_references"] = len(entries)

            # Count by namespace
            namespace_counts: dict[str, int] = {}
            for entry in entries:
                ns = getattr(entry, "namespace", "unknown")
                namespace_counts[ns] = namespace_counts.get(ns, 0) + 1
            stats["references_by_namespace"] = namespace_counts

            # Count expired
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            expired_count = sum(
                1
                for entry in entries
                if hasattr(entry, "expires_at")
                and entry.expires_at
                and entry.expires_at < now
            )
            stats["expired_references"] = expired_count
            stats["active_references"] = len(entries) - expired_count

            # Value type breakdown
            type_counts: dict[str, int] = {}
            for entry in entries:
                if hasattr(entry, "value"):
                    type_name = type(entry.value).__name__
                    type_counts[type_name] = type_counts.get(type_name, 0) + 1
            stats["references_by_type"] = type_counts

        return stats

    return get_cache_stats


# =============================================================================
# Registration Function
# =============================================================================


def register_admin_tools(
    mcp: Any,  # FastMCP instance
    cache: RefCache,
    admin_check: AdminChecker | None = None,
    prefix: str = "admin_",
    include_dangerous: bool = False,
) -> list[str]:
    """Register admin tools with a FastMCP server.

    This function creates and registers cache management tools that are
    protected by the provided admin check function.

    Args:
        mcp: The FastMCP server instance.
        cache: The RefCache instance to manage.
        admin_check: Function to verify admin access. If None, tools will
            deny all access (safe default).
        prefix: Prefix for tool names (default: 'admin_').
        include_dangerous: Include tools that can expose full values
            (default: False for safety).

    Returns:
        List of registered tool names.

    Example:
        ```python
        async def is_admin(ctx: Context) -> bool:
            return ctx.user_id in ["admin@example.com"]

        registered = register_admin_tools(
            mcp, cache,
            admin_check=is_admin,
            prefix="cache_admin_",
        )
        print(f"Registered: {registered}")
        ```

    Warning:
        If admin_check is None, all admin tools will deny access.
        This is a safe default but means the tools are not usable
        until a proper admin check is configured.
    """
    registered: list[str] = []

    # List references
    tool_name = f"{prefix}list_references"
    list_refs = create_list_references_tool(cache, admin_check)
    list_refs.__name__ = tool_name
    list_refs.__doc__ = """List cached references with optional filtering.

⚠️ ADMIN ONLY - Requires elevated permissions.

Args:
    namespace: Filter by namespace (e.g., 'public', 'user:alice').
    include_expired: Include expired references in results.
    include_preview: Include value previews in results.
    limit: Maximum number of results (default: 50, max: 100).
    offset: Offset for pagination.

Returns:
    Dictionary with references list and pagination info.
"""
    mcp.tool(list_refs)
    registered.append(tool_name)

    # Get reference info
    tool_name = f"{prefix}get_reference_info"
    get_info = create_get_reference_info_tool(cache, admin_check)
    get_info.__name__ = tool_name

    if include_dangerous:
        get_info.__doc__ = """Get detailed information about a cached reference.

⚠️ ADMIN ONLY - Requires elevated permissions.
⚠️ DANGEROUS - Can expose full cached values.

Args:
    ref_id: The reference ID to look up.
    include_value: Include the full cached value (use with caution).

Returns:
    Dictionary with detailed reference information.
"""
    else:
        # Wrap to disable include_value
        original_get_info = get_info

        async def safe_get_info(
            ref_id: str,
            ctx: Context | None = None,
        ) -> dict[str, Any]:
            return await original_get_info(ref_id, include_value=False, ctx=ctx)

        safe_get_info.__name__ = tool_name
        safe_get_info.__doc__ = """Get detailed information about a cached reference.

⚠️ ADMIN ONLY - Requires elevated permissions.

Args:
    ref_id: The reference ID to look up.

Returns:
    Dictionary with detailed reference information (value not included).
"""
        get_info = safe_get_info

    mcp.tool(get_info)
    registered.append(tool_name)

    # Delete reference
    tool_name = f"{prefix}delete_reference"
    delete_ref = create_delete_reference_tool(cache, admin_check)
    delete_ref.__name__ = tool_name
    delete_ref.__doc__ = """Delete a specific cached reference.

⚠️ ADMIN ONLY - Requires elevated permissions.
⚠️ DESTRUCTIVE - This action cannot be undone.

Args:
    ref_id: The reference ID to delete.

Returns:
    Confirmation of deletion or error.
"""
    mcp.tool(delete_ref)
    registered.append(tool_name)

    # Clear namespace
    tool_name = f"{prefix}clear_namespace"
    clear_ns = create_clear_namespace_tool(cache, admin_check)
    clear_ns.__name__ = tool_name
    clear_ns.__doc__ = """Clear all references in a namespace.

⚠️ ADMIN ONLY - Requires elevated permissions.
⚠️ DESTRUCTIVE - This action cannot be undone.

Args:
    namespace: The namespace to clear (e.g., 'user:alice').
    include_children: Also clear child namespaces (default: True).

Returns:
    Confirmation with count of deleted references.
"""
    mcp.tool(clear_ns)
    registered.append(tool_name)

    # Cache stats
    tool_name = f"{prefix}get_cache_stats"
    get_stats = create_get_cache_stats_tool(cache, admin_check)
    get_stats.__name__ = tool_name
    get_stats.__doc__ = """Get detailed cache statistics.

⚠️ ADMIN ONLY - Requires elevated permissions.

Returns:
    Dictionary with cache statistics including:
    - Total references and counts by namespace
    - Active vs expired reference counts
    - Value type breakdown
    - Cache configuration
"""
    mcp.tool(get_stats)
    registered.append(tool_name)

    return registered


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AdminChecker",
    "AdminToolError",
    "PermissionDeniedError",
    "create_clear_namespace_tool",
    "create_delete_reference_tool",
    "create_get_cache_stats_tool",
    "create_get_reference_info_tool",
    "create_list_references_tool",
    "register_admin_tools",
]
