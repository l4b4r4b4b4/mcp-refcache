"""Context integration for FastMCP servers.

Provides utilities for expanding templates with values from FastMCP's Context
object, enabling dynamic namespace and owner assignment based on authenticated
session context.

Key Features:
- Template expansion with {placeholder} syntax
- Safe FastMCP context access (graceful when not installed)
- Sensible fallbacks for missing values
- Actor derivation from context

Security Note:
    Template values come from authenticated session context (set by middleware),
    NOT from function arguments. This ensures agents cannot control their own
    scoping or spoof identity.

Example:
    ```python
    from mcp_refcache.context_integration import (
        expand_template,
        get_context_values,
        try_get_fastmcp_context,
    )

    # In a decorator or tool:
    ctx = try_get_fastmcp_context()
    if ctx:
        values = get_context_values(ctx)
        namespace = expand_template("org:{org_id}:user:{user_id}", values)
        # namespace = "org:acme:user:alice"
    ```
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp_refcache.access.actor import Actor, ActorLike

# Default fallback values for known context keys
# Used when a template placeholder cannot be resolved from context
DEFAULT_FALLBACKS: dict[str, str] = {
    "user_id": "anonymous",
    "org_id": "default",
    "tenant_id": "default",
    "session_id": "nosession",
    "client_id": "unknown",
    "request_id": "unknown",
    "agent_id": "anonymous",
}

# Regex pattern for matching {placeholder} in templates
_PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def expand_template(
    template: str,
    context_values: dict[str, str],
    fallbacks: dict[str, str] | None = None,
) -> str:
    """Expand a template string by replacing {placeholders} with values.

    Args:
        template: Template string with {placeholder} syntax.
            Example: "org:{org_id}:user:{user_id}"
        context_values: Dictionary of placeholder names to values.
        fallbacks: Optional custom fallbacks. Merged with DEFAULT_FALLBACKS.

    Returns:
        Expanded string with all placeholders replaced.

    Example:
        ```python
        values = {"org_id": "acme", "user_id": "alice"}
        result = expand_template("org:{org_id}:user:{user_id}", values)
        # result = "org:acme:user:alice"

        # With missing values (uses fallbacks):
        result = expand_template("user:{user_id}", {})
        # result = "user:anonymous"
        ```
    """
    if not template:
        return template

    effective_fallbacks = {**DEFAULT_FALLBACKS}
    if fallbacks:
        effective_fallbacks.update(fallbacks)

    def replace_placeholder(match: re.Match[str]) -> str:
        key = match.group(1)
        # Try context_values first, then fallbacks, then generic "unknown"
        if key in context_values:
            return context_values[key]
        if key in effective_fallbacks:
            return effective_fallbacks[key]
        return "unknown"

    return _PLACEHOLDER_PATTERN.sub(replace_placeholder, template)


def get_context_values(context: Any) -> dict[str, str]:
    """Extract template values from a FastMCP Context object.

    Extracts values from multiple sources in priority order:
    1. ctx.get_state(key) - Values set by middleware
    2. Built-in Context attributes (session_id, client_id, request_id)

    Args:
        context: FastMCP Context object (or any object with compatible API).

    Returns:
        Dictionary of key-value pairs suitable for template expansion.

    Example:
        ```python
        ctx = get_context()  # FastMCP context
        values = get_context_values(ctx)
        # values = {"user_id": "alice", "org_id": "acme", "session_id": "sess-123"}
        ```
    """
    values: dict[str, str] = {}

    if context is None:
        return values

    # Extract built-in Context attributes
    builtin_attrs = ["session_id", "client_id", "request_id"]
    for attr in builtin_attrs:
        try:
            value = getattr(context, attr, None)
            if value is not None:
                values[attr] = str(value)
        except Exception:  # nosec B110
            # Ignore any attribute access errors - context may have varying implementations
            pass

    # Extract state values set by middleware
    # Common keys that middleware might set
    state_keys = [
        "user_id",
        "org_id",
        "tenant_id",
        "agent_id",
        "role",
        "scopes",
    ]

    # Try to get state values
    if hasattr(context, "get_state"):
        for key in state_keys:
            try:
                value = context.get_state(key)
                if value is not None:
                    values[key] = str(value)
            except Exception:  # nosec B110
                # Ignore missing keys or errors - state may not be set
                pass

    return values


def try_get_fastmcp_context() -> Any | None:
    """Safely attempt to get the current FastMCP Context.

    This function handles the case where FastMCP is not installed or
    the context is not available (e.g., called outside of a tool handler).

    Returns:
        FastMCP Context object if available, None otherwise.

    Example:
        ```python
        ctx = try_get_fastmcp_context()
        if ctx:
            # We're in a FastMCP tool handler
            values = get_context_values(ctx)
        else:
            # FastMCP not available, use fallbacks
            values = {}
        ```
    """
    try:
        from fastmcp.server.dependencies import get_context

        return get_context()
    except ImportError:
        # FastMCP not installed
        return None
    except RuntimeError:
        # No active context (called outside tool handler)
        return None
    except Exception:
        # Any other error - fail gracefully
        return None


def derive_actor_from_context(
    context_values: dict[str, str],
    default_actor: ActorLike = "agent",
) -> Actor:
    """Derive an Actor from context values.

    Creates an appropriate Actor based on identity information in the context:
    - If user_id present → User actor with that identity
    - If agent_id present → Agent actor with specific identity
    - Otherwise → Use default_actor string

    Args:
        context_values: Values extracted from FastMCP Context.
        default_actor: Fallback actor string if no identity in context.

    Returns:
        Actor object for permission checks.

    Example:
        ```python
        values = {"user_id": "alice", "session_id": "sess-123"}
        actor = derive_actor_from_context(values)
        # Returns DefaultActor.user("alice", session_id="sess-123")

        values = {"agent_id": "claude-instance-1"}
        actor = derive_actor_from_context(values)
        # Returns DefaultActor.agent("claude-instance-1")
        ```
    """
    from mcp_refcache.access.actor import DefaultActor, resolve_actor

    session_id = context_values.get("session_id")

    # Priority 1: User identity
    user_id = context_values.get("user_id")
    if user_id and user_id != "anonymous":
        return DefaultActor.user(user_id, session_id=session_id)

    # Priority 2: Agent identity (specific agent, not generic)
    agent_id = context_values.get("agent_id")
    if agent_id and agent_id != "anonymous":
        return DefaultActor.agent(agent_id, session_id=session_id)

    # Priority 3: Fall back to default_actor string
    return resolve_actor(default_actor)


def build_context_scoped_policy(
    base_policy: Any | None,
    context_values: dict[str, str],
    owner_template: str | None = None,
    session_scoped: bool = False,
) -> Any:
    """Build an AccessPolicy with context-derived owner and session binding.

    Creates a new policy (or modifies existing) with:
    - owner: Expanded from owner_template using context values
    - bound_session: Set to session_id if session_scoped=True

    Args:
        base_policy: Existing AccessPolicy to modify, or None for defaults.
        context_values: Values extracted from FastMCP Context.
        owner_template: Template for owner (e.g., "user:{user_id}").
        session_scoped: If True, bind to current session.

    Returns:
        New AccessPolicy with context-derived values.

    Example:
        ```python
        values = {"user_id": "alice", "session_id": "sess-123"}
        policy = build_context_scoped_policy(
            base_policy=None,
            context_values=values,
            owner_template="user:{user_id}",
            session_scoped=True,
        )
        # policy.owner = "user:alice"
        # policy.bound_session = "sess-123"
        ```
    """
    from mcp_refcache.permissions import AccessPolicy

    # Start with base policy or defaults
    policy_dict = base_policy.model_dump() if base_policy is not None else {}

    # Set owner from template if provided
    if owner_template:
        owner = expand_template(owner_template, context_values)
        policy_dict["owner"] = owner

    # Bind to session if requested
    if session_scoped:
        session_id = context_values.get("session_id")
        if session_id and session_id != "nosession":
            policy_dict["bound_session"] = session_id

    return AccessPolicy(**policy_dict)


__all__ = [
    "DEFAULT_FALLBACKS",
    "build_context_scoped_policy",
    "derive_actor_from_context",
    "expand_template",
    "get_context_values",
    "try_get_fastmcp_context",
]
