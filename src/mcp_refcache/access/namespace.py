"""Namespace resolution and ownership for access control.

This module provides the namespace abstraction for the access control system.
Namespaces partition cached values and define implicit ownership rules based
on naming patterns.

Namespace Patterns:
    - `public`: No ownership restriction, anyone can access
    - `session:<id>`: Session-scoped, requires matching session_id
    - `user:<id>`: User-scoped, requires matching user actor with id
    - `agent:<id>`: Agent-scoped, requires matching agent actor with id
    - `shared:<group>`: Group-scoped (future: group membership check)
    - Custom namespaces follow no implicit rules

Example:
    ```python
    resolver = DefaultNamespaceResolver()

    # Check if an actor can access a namespace
    alice = DefaultActor.user(id="alice")
    resolver.validate_access("user:alice", alice)  # True
    resolver.validate_access("user:bob", alice)    # False

    # Session-scoped access
    actor = DefaultActor.user(id="alice", session_id="sess-123")
    resolver.validate_access("session:sess-123", actor)  # True
    resolver.validate_access("session:other", actor)     # False

    # Public namespace
    resolver.validate_access("public", DefaultActor.agent())  # True
    ```
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mcp_refcache.access.actor import Actor, ActorType


@runtime_checkable
class NamespaceResolver(Protocol):
    """Protocol for namespace ownership resolution.

    Implementations of this protocol determine access rules based on
    namespace patterns. This enables implicit access control without
    explicit ACLs for common patterns like session-scoped or user-scoped
    namespaces.

    The protocol requires:
    - validate_access(): Check if an actor can access a namespace
    - get_owner(): Extract owner identity from namespace pattern
    - get_required_session(): Extract required session ID from namespace
    - parse(): Parse namespace into components
    """

    def validate_access(self, namespace: str, actor: Actor) -> bool:
        """Check if an actor can access this namespace.

        This method applies implicit ownership rules based on the namespace
        pattern. For example, `session:abc123` requires the actor to have
        a matching session_id.

        Args:
            namespace: The namespace to check access for.
            actor: The actor attempting to access.

        Returns:
            True if the actor is allowed to access the namespace.
        """
        ...

    def get_owner(self, namespace: str) -> str | None:
        """Extract the owner identity from a namespace pattern.

        For ownership-implying namespaces like `user:alice` or `agent:claude-1`,
        this returns the canonical owner string (e.g., "user:alice").

        Args:
            namespace: The namespace to extract owner from.

        Returns:
            The owner identity string, or None if namespace has no implicit owner.
        """
        ...

    def get_required_session(self, namespace: str) -> str | None:
        """Extract the required session ID from a namespace pattern.

        For session-scoped namespaces like `session:abc123`, this returns
        the session ID that actors must have to access.

        Args:
            namespace: The namespace to check.

        Returns:
            The required session ID, or None if namespace is not session-scoped.
        """
        ...

    def parse(self, namespace: str) -> NamespaceInfo:
        """Parse a namespace into its components.

        Args:
            namespace: The namespace string to parse.

        Returns:
            A NamespaceInfo object with parsed components.
        """
        ...


class NamespaceInfo:
    """Parsed namespace information.

    Attributes:
        raw: The original namespace string.
        prefix: The namespace prefix (e.g., "session", "user", "public").
        identifier: The identifier part after the prefix, if any.
        is_public: Whether this is the public namespace.
        is_session_scoped: Whether this namespace is session-scoped.
        is_user_scoped: Whether this namespace is user-scoped.
        is_agent_scoped: Whether this namespace is agent-scoped.
        implied_owner: The implied owner string, if any.
    """

    __slots__ = (
        "identifier",
        "implied_owner",
        "is_agent_scoped",
        "is_public",
        "is_session_scoped",
        "is_user_scoped",
        "prefix",
        "raw",
    )

    def __init__(
        self,
        raw: str,
        prefix: str,
        identifier: str | None = None,
        is_public: bool = False,
        is_session_scoped: bool = False,
        is_user_scoped: bool = False,
        is_agent_scoped: bool = False,
        implied_owner: str | None = None,
    ) -> None:
        """Initialize namespace info.

        Args:
            raw: The original namespace string.
            prefix: The namespace prefix.
            identifier: The identifier part after prefix.
            is_public: Whether this is public namespace.
            is_session_scoped: Whether session-scoped.
            is_user_scoped: Whether user-scoped.
            is_agent_scoped: Whether agent-scoped.
            implied_owner: The implied owner identity.
        """
        self.raw = raw
        self.prefix = prefix
        self.identifier = identifier
        self.is_public = is_public
        self.is_session_scoped = is_session_scoped
        self.is_user_scoped = is_user_scoped
        self.is_agent_scoped = is_agent_scoped
        self.implied_owner = implied_owner

    def __repr__(self) -> str:
        """Debug representation."""
        return (
            f"NamespaceInfo(raw={self.raw!r}, prefix={self.prefix!r}, "
            f"identifier={self.identifier!r})"
        )

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, NamespaceInfo):
            return NotImplemented
        return self.raw == other.raw


class DefaultNamespaceResolver:
    """Default implementation of the NamespaceResolver protocol.

    Implements standard namespace patterns:
    - `public`: No restrictions
    - `session:<id>`: Requires actor.session_id == id
    - `user:<id>`: Requires actor.type == USER and actor.id == id
    - `agent:<id>`: Requires actor.type == AGENT and actor.id == id
    - `shared:<group>`: Currently allows all (group membership TBD)
    - Custom namespaces: No implicit restrictions

    Example:
        ```python
        resolver = DefaultNamespaceResolver()

        # Parse namespace
        info = resolver.parse("session:abc123")
        assert info.is_session_scoped
        assert info.identifier == "abc123"

        # Validate access
        actor = DefaultActor.user(session_id="abc123")
        assert resolver.validate_access("session:abc123", actor)
        ```
    """

    # Known namespace prefixes with special handling
    PREFIX_PUBLIC = "public"
    PREFIX_SESSION = "session"
    PREFIX_USER = "user"
    PREFIX_AGENT = "agent"
    PREFIX_SHARED = "shared"

    def validate_access(self, namespace: str, actor: Actor) -> bool:
        """Check if an actor can access this namespace.

        Applies implicit ownership rules:
        - public: Always allowed
        - session:<id>: Requires matching session_id
        - user:<id>: Requires USER type with matching id
        - agent:<id>: Requires AGENT type with matching id
        - shared:<group>: Currently allows all (TODO: group membership)
        - SYSTEM actors bypass all namespace restrictions
        - Custom namespaces: Always allowed (no implicit rules)

        Args:
            namespace: The namespace to check access for.
            actor: The actor attempting to access.

        Returns:
            True if the actor is allowed to access the namespace.
        """
        # System actors bypass namespace restrictions
        if actor.type == ActorType.SYSTEM:
            return True

        info = self.parse(namespace)

        # Public namespace - always accessible
        if info.is_public:
            return True

        # Session-scoped - require matching session_id
        if info.is_session_scoped:
            if actor.session_id is None:
                return False
            return actor.session_id == info.identifier

        # User-scoped - require USER type with matching id
        if info.is_user_scoped:
            if actor.type != ActorType.USER:
                return False
            if actor.id is None:
                return False
            return actor.id == info.identifier

        # Agent-scoped - require AGENT type with matching id
        if info.is_agent_scoped:
            if actor.type != ActorType.AGENT:
                return False
            if actor.id is None:
                return False
            return actor.id == info.identifier

        # Shared namespace - allow all for now (group membership TBD)
        if info.prefix == self.PREFIX_SHARED:
            return True

        # Custom namespaces - no implicit restrictions
        return True

    def get_owner(self, namespace: str) -> str | None:
        """Extract the owner identity from a namespace pattern.

        Args:
            namespace: The namespace to extract owner from.

        Returns:
            The owner identity string (e.g., "user:alice"), or None.
        """
        info = self.parse(namespace)
        return info.implied_owner

    def get_required_session(self, namespace: str) -> str | None:
        """Extract the required session ID from a namespace pattern.

        Args:
            namespace: The namespace to check.

        Returns:
            The required session ID, or None if not session-scoped.
        """
        info = self.parse(namespace)
        if info.is_session_scoped:
            return info.identifier
        return None

    def parse(self, namespace: str) -> NamespaceInfo:
        """Parse a namespace into its components.

        Handles the following patterns:
        - "public" -> prefix="public", identifier=None
        - "session:abc123" -> prefix="session", identifier="abc123"
        - "user:alice" -> prefix="user", identifier="alice"
        - "custom" -> prefix="custom", identifier=None
        - "custom:value" -> prefix="custom", identifier="value"

        Args:
            namespace: The namespace string to parse.

        Returns:
            A NamespaceInfo object with parsed components.
        """
        # Handle public namespace specially
        if namespace == self.PREFIX_PUBLIC:
            return NamespaceInfo(
                raw=namespace,
                prefix=self.PREFIX_PUBLIC,
                identifier=None,
                is_public=True,
            )

        # Split on first colon
        if ":" in namespace:
            prefix, identifier = namespace.split(":", 1)
        else:
            prefix = namespace
            identifier = None

        # Determine namespace type and implied owner
        is_session_scoped = prefix == self.PREFIX_SESSION
        is_user_scoped = prefix == self.PREFIX_USER
        is_agent_scoped = prefix == self.PREFIX_AGENT

        # Calculate implied owner for user/agent namespaces
        implied_owner: str | None = None
        if is_user_scoped and identifier:
            implied_owner = f"user:{identifier}"
        elif is_agent_scoped and identifier:
            implied_owner = f"agent:{identifier}"

        return NamespaceInfo(
            raw=namespace,
            prefix=prefix,
            identifier=identifier,
            is_public=False,
            is_session_scoped=is_session_scoped,
            is_user_scoped=is_user_scoped,
            is_agent_scoped=is_agent_scoped,
            implied_owner=implied_owner,
        )
