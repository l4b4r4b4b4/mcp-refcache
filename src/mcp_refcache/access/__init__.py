"""Access control system for mcp-refcache.

This module provides identity-aware access control with:
- Actor types and identity (users, agents, system)
- Namespace ownership and session binding
- Permission checking with configurable policies
- Backwards compatibility with literal "user"/"agent" actors

Core Components:
    - Actor: Protocol for identity-aware actors
    - DefaultActor: Pydantic implementation with factory methods
    - NamespaceResolver: Protocol for namespace ownership rules
    - DefaultNamespaceResolver: Standard namespace pattern handling
    - PermissionChecker: Protocol for permission evaluation
    - DefaultPermissionChecker: Standard permission resolution algorithm

Example:
    ```python
    from mcp_refcache.access import (
        DefaultActor,
        DefaultPermissionChecker,
        DefaultNamespaceResolver,
        ActorType,
        PermissionDenied,
    )
    from mcp_refcache.permissions import Permission, AccessPolicy

    # Create actors
    alice = DefaultActor.user(id="alice", session_id="sess-123")
    agent = DefaultActor.agent(id="claude-1")

    # Create checker
    checker = DefaultPermissionChecker()

    # Create policy with ownership
    policy = AccessPolicy(
        user_permissions=Permission.FULL,
        agent_permissions=Permission.READ | Permission.EXECUTE,
    )

    # Check permissions
    try:
        checker.check(policy, Permission.READ, alice, "public")
    except PermissionDenied as e:
        print(f"Access denied: {e.reason}")
    ```
"""

from mcp_refcache.access.actor import (
    Actor,
    ActorLike,
    ActorType,
    DefaultActor,
    resolve_actor,
)
from mcp_refcache.access.checker import (
    DefaultPermissionChecker,
    PermissionChecker,
    PermissionDenied,
)
from mcp_refcache.access.namespace import (
    DefaultNamespaceResolver,
    NamespaceInfo,
    NamespaceResolver,
)

__all__ = [
    "Actor",
    "ActorLike",
    "ActorType",
    "DefaultActor",
    "DefaultNamespaceResolver",
    "DefaultPermissionChecker",
    "NamespaceInfo",
    "NamespaceResolver",
    "PermissionChecker",
    "PermissionDenied",
    "resolve_actor",
]
