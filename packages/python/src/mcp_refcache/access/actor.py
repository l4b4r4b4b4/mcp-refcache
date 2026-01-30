"""Actor types and identity model for access control.

This module provides the core identity abstraction for the access control
system. Actors represent entities (users, agents, or system processes)
that can perform operations on cached values.

Example:
    ```python
    # Create an anonymous user actor
    actor = DefaultActor.user()

    # Create an identified user with session
    actor = DefaultActor.user(id="alice", session_id="sess-123")

    # Create an agent actor
    actor = DefaultActor.agent(id="claude-instance-1")

    # Check if actor matches a pattern
    actor.matches("user:alice")  # True
    actor.matches("user:*")      # True (wildcard)
    actor.matches("agent:*")     # False (wrong type)
    ```
"""

from __future__ import annotations

import fnmatch
from enum import Enum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ActorType(str, Enum):
    """Type of actor performing an operation.

    Actors are categorized into three types:
    - USER: Human users interacting with the system
    - AGENT: AI agents (LLMs, assistants) operating on behalf of users
    - SYSTEM: Internal system processes with elevated privileges
    """

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


@runtime_checkable
class Actor(Protocol):
    """Protocol defining the interface for identity-aware actors.

    Actors encapsulate identity information used for access control decisions.
    Any class implementing this protocol can be used with the permission system.

    The protocol requires:
    - type: The category of actor (user, agent, or system)
    - id: Optional unique identifier within the actor type
    - session_id: Optional session context for session-scoped access
    - matches(): Pattern matching for ACL checks
    - to_string(): Canonical string representation
    """

    @property
    def type(self) -> ActorType:
        """The type of this actor."""
        ...

    @property
    def id(self) -> str | None:
        """Unique identifier for this actor within its type.

        Returns None for anonymous actors.
        """
        ...

    @property
    def session_id(self) -> str | None:
        """Session identifier for session-scoped access control.

        Returns None if the actor is not associated with a session.
        """
        ...

    def matches(self, pattern: str) -> bool:
        """Check if this actor matches an ACL pattern.

        Patterns follow the format `type:id` where:
        - type: "user", "agent", or "system"
        - id: specific ID, "*" for any, or glob pattern

        Args:
            pattern: Pattern to match against (e.g., "user:alice", "agent:*")

        Returns:
            True if the actor matches the pattern.

        Example:
            ```python
            actor = DefaultActor.user(id="alice")
            actor.matches("user:alice")  # True
            actor.matches("user:*")      # True
            actor.matches("user:bob")    # False
            actor.matches("agent:*")     # False
            ```
        """
        ...

    def to_string(self) -> str:
        """Return canonical string representation.

        Format: `type:id` or `type:*` for anonymous actors.

        Returns:
            String representation suitable for storage and ACL matching.
        """
        ...


class DefaultActor(BaseModel):
    """Default implementation of the Actor protocol.

    Provides a Pydantic-based actor with factory methods for common patterns.

    Example:
        ```python
        # Anonymous actors (backwards compatible with old system)
        user = DefaultActor.user()
        agent = DefaultActor.agent()

        # Identified actors
        alice = DefaultActor.user(id="alice", session_id="sess-123")
        claude = DefaultActor.agent(id="claude-instance-1")

        # System actor for internal operations
        system = DefaultActor.system()
        ```
    """

    actor_type: ActorType = Field(
        description="The type of this actor (user, agent, or system).",
    )
    actor_id: str | None = Field(
        default=None,
        description="Unique identifier for this actor. None for anonymous actors.",
    )
    actor_session_id: str | None = Field(
        default=None,
        description="Session ID for session-scoped access control.",
    )

    model_config = {"frozen": True}

    @property
    def type(self) -> ActorType:
        """The type of this actor."""
        return self.actor_type

    @property
    def id(self) -> str | None:
        """Unique identifier for this actor within its type."""
        return self.actor_id

    @property
    def session_id(self) -> str | None:
        """Session identifier for session-scoped access control."""
        return self.actor_session_id

    def matches(self, pattern: str) -> bool:
        """Check if this actor matches an ACL pattern.

        Supports glob patterns using fnmatch semantics:
        - "*" matches any sequence of characters
        - "?" matches any single character
        - "[seq]" matches any character in seq

        Args:
            pattern: Pattern in format "type:id" or "type:*"

        Returns:
            True if the actor matches the pattern.
        """
        if ":" not in pattern:
            return False

        pattern_type, pattern_id = pattern.split(":", 1)

        # Type must match exactly
        if pattern_type != self.actor_type.value:
            return False

        # Wildcard matches everything
        if pattern_id == "*":
            return True

        # For anonymous actors, only wildcard matches
        if self.actor_id is None:
            return False

        # Use fnmatch for glob-style matching
        return fnmatch.fnmatch(self.actor_id, pattern_id)

    def to_string(self) -> str:
        """Return canonical string representation.

        Returns:
            String in format "type:id" or "type:*" for anonymous actors.
        """
        actor_id = self.actor_id if self.actor_id is not None else "*"
        return f"{self.actor_type.value}:{actor_id}"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return self.to_string()

    def __repr__(self) -> str:
        """Debug representation."""
        parts = [f"type={self.actor_type.value!r}"]
        if self.actor_id is not None:
            parts.append(f"id={self.actor_id!r}")
        if self.actor_session_id is not None:
            parts.append(f"session_id={self.actor_session_id!r}")
        return f"DefaultActor({', '.join(parts)})"

    @classmethod
    def user(
        cls,
        id: str | None = None,
        session_id: str | None = None,
    ) -> DefaultActor:
        """Create a user actor.

        Args:
            id: Optional user identifier (e.g., "alice", "user-123").
            session_id: Optional session identifier.

        Returns:
            A DefaultActor instance with type USER.

        Example:
            ```python
            anonymous_user = DefaultActor.user()
            identified_user = DefaultActor.user(id="alice")
            session_user = DefaultActor.user(id="alice", session_id="sess-123")
            ```
        """
        return cls(
            actor_type=ActorType.USER,
            actor_id=id,
            actor_session_id=session_id,
        )

    @classmethod
    def agent(
        cls,
        id: str | None = None,
        session_id: str | None = None,
    ) -> DefaultActor:
        """Create an agent actor.

        Args:
            id: Optional agent identifier (e.g., "claude-instance-1").
            session_id: Optional session identifier.

        Returns:
            A DefaultActor instance with type AGENT.

        Example:
            ```python
            anonymous_agent = DefaultActor.agent()
            identified_agent = DefaultActor.agent(id="claude-instance-1")
            ```
        """
        return cls(
            actor_type=ActorType.AGENT,
            actor_id=id,
            actor_session_id=session_id,
        )

    @classmethod
    def system(cls) -> DefaultActor:
        """Create a system actor for internal operations.

        System actors typically have elevated privileges and are used
        for administrative or internal operations.

        Returns:
            A DefaultActor instance with type SYSTEM.

        Example:
            ```python
            system = DefaultActor.system()
            ```
        """
        return cls(
            actor_type=ActorType.SYSTEM,
            actor_id="internal",
            actor_session_id=None,
        )

    @classmethod
    def from_literal(
        cls,
        actor: Literal["user", "agent"],
        session_id: str | None = None,
    ) -> DefaultActor:
        """Create an actor from a literal string (backwards compatibility).

        This method provides backwards compatibility with the old
        `actor: Literal["user", "agent"]` parameter pattern.

        Args:
            actor: Either "user" or "agent".
            session_id: Optional session identifier.

        Returns:
            A DefaultActor instance with the appropriate type.

        Example:
            ```python
            # Old code path
            actor = DefaultActor.from_literal("user")
            actor = DefaultActor.from_literal("agent")
            ```
        """
        actor_type = ActorType.USER if actor == "user" else ActorType.AGENT
        return cls(
            actor_type=actor_type,
            actor_id=None,
            actor_session_id=session_id,
        )


# Type alias for accepting both old and new actor formats
ActorLike = Actor | Literal["user", "agent"]


def resolve_actor(actor: ActorLike, session_id: str | None = None) -> Actor:
    """Resolve an ActorLike to a concrete Actor instance.

    This function handles backwards compatibility by accepting either
    the new Actor protocol or the old literal strings.

    Args:
        actor: Either an Actor instance or a literal "user"/"agent".
        session_id: Optional session ID to attach (only used for literal actors).

    Returns:
        An Actor instance.

    Example:
        ```python
        # New style (returned as-is)
        actor = resolve_actor(DefaultActor.user(id="alice"))

        # Old style (converted to DefaultActor)
        actor = resolve_actor("user")
        actor = resolve_actor("agent", session_id="sess-123")
        ```
    """
    if isinstance(actor, str):
        return DefaultActor.from_literal(actor, session_id=session_id)
    return actor
