"""Permission model for access control.

Provides fine-grained permissions for both users and agents,
including the EXECUTE permission for private/blind computation.
"""

from enum import Flag, auto

from pydantic import BaseModel, Field


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

    Example:
        ```python
        # Agent can use but not see the value
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            agent_permissions=Permission.EXECUTE,
        )
        ```
    """

    user_permissions: Permission = Field(
        default=Permission.FULL,
        description="Permissions granted to human users.",
    )
    agent_permissions: Permission = Field(
        default=Permission.READ | Permission.EXECUTE,
        description="Permissions granted to AI agents.",
    )

    model_config = {"arbitrary_types_allowed": True}

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
