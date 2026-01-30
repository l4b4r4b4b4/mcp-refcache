"""Permission model for access control.

Provides fine-grained permissions for both users and agents,
including the EXECUTE permission for private/blind computation.
"""

from enum import Flag, auto

from pydantic import BaseModel, Field, field_validator


class Permission(Flag):
    """Permission flags for cache access control.

    Permissions can be combined using bitwise operators:
        Permission.READ | Permission.WRITE  # Read and write
        Permission.CRUD  # All CRUD operations
        Permission.FULL  # Everything including EXECUTE
    """

    NONE = 0
    READ = auto()  # Resolve reference to see the value
    WRITE = auto()  # Create new references
    UPDATE = auto()  # Modify existing cached values
    DELETE = auto()  # Remove/invalidate references
    EXECUTE = auto()  # Use value in computation WITHOUT seeing it

    # Convenience combinations
    CRUD = READ | WRITE | UPDATE | DELETE
    FULL = CRUD | EXECUTE


class AccessPolicy(BaseModel):
    """Access policy defining separate permissions for users and agents.

    This separation enables private computation where agents can use
    values (EXECUTE) without being able to read them (READ).

    The policy supports multiple layers of access control:
    - Role-based: user_permissions and agent_permissions (default behavior)
    - Ownership: owner and owner_permissions for resource owners
    - ACL: allowed_actors and denied_actors for explicit allow/deny lists
    - Session binding: bound_session for session-scoped access

    Example:
        ```python
        # Agent can use but not see the value
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            agent_permissions=Permission.EXECUTE,
        )

        # With ownership
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            owner="user:alice",
            owner_permissions=Permission.FULL,
        )

        # With explicit deny list
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            denied_actors=frozenset({"user:untrusted"}),
        )
        ```
    """

    # === Role-based permissions (existing) ===
    user_permissions: Permission = Field(
        default=Permission.FULL,
        description="Permissions granted to human users.",
    )
    agent_permissions: Permission = Field(
        default=Permission.READ | Permission.EXECUTE,
        description="Permissions granted to AI agents.",
    )

    # === Ownership ===
    owner: str | None = Field(
        default=None,
        description="Owner identity string (e.g., 'user:alice', 'agent:claude-1').",
    )
    owner_permissions: Permission = Field(
        default=Permission.FULL,
        description="Permissions granted to the owner.",
    )

    # === ACL (Access Control Lists) ===
    allowed_actors: frozenset[str] | None = Field(
        default=None,
        description="Explicit allow list of actor patterns (e.g., {'user:alice', 'agent:*'}).",
    )
    denied_actors: frozenset[str] | None = Field(
        default=None,
        description="Explicit deny list of actor patterns. Deny takes precedence over allow.",
    )

    # === Session binding ===
    bound_session: str | None = Field(
        default=None,
        description="If set, only actors with this session_id can access.",
    )

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("allowed_actors", "denied_actors", mode="before")
    @classmethod
    def convert_set_to_frozenset(
        cls, value: set[str] | frozenset[str] | None
    ) -> frozenset[str] | None:
        """Convert set to frozenset for immutability."""
        if value is None:
            return None
        if isinstance(value, frozenset):
            return value
        return frozenset(value)

    def user_can(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return bool(self.user_permissions & permission)

    def agent_can(self, permission: Permission) -> bool:
        """Check if agent has a specific permission."""
        return bool(self.agent_permissions & permission)


# Common policy presets
POLICY_PUBLIC = AccessPolicy(
    user_permissions=Permission.FULL,
    agent_permissions=Permission.FULL,
)

POLICY_USER_ONLY = AccessPolicy(
    user_permissions=Permission.FULL,
    agent_permissions=Permission.NONE,
)

POLICY_EXECUTE_ONLY = AccessPolicy(
    user_permissions=Permission.FULL,
    agent_permissions=Permission.EXECUTE,
)

POLICY_READ_ONLY = AccessPolicy(
    user_permissions=Permission.READ,
    agent_permissions=Permission.READ,
)
