"""Permission checking for access control.

This module provides the permission checking abstraction for the access control
system. Permission checkers evaluate whether an actor has the required permissions
to perform an operation on a cached value.

The permission resolution algorithm:
1. DENY if actor is in denied_actors (explicit deny)
2. DENY if bound_session is set and actor's session doesn't match
3. DENY if namespace ownership rules are violated
4. ALLOW if actor is in allowed_actors (explicit allow, bypass role check)
5. ALLOW with owner_permissions if actor matches the owner
6. ALLOW/DENY based on role permissions (user_permissions/agent_permissions)

Example:
    ```python
    checker = DefaultPermissionChecker()

    policy = AccessPolicy(
        user_permissions=Permission.FULL,
        agent_permissions=Permission.READ | Permission.EXECUTE,
        owner="user:alice",
        owner_permissions=Permission.FULL,
    )

    alice = DefaultActor.user(id="alice")
    bob = DefaultActor.user(id="bob")
    agent = DefaultActor.agent()

    # Alice is owner - has full permissions
    checker.check(policy, Permission.DELETE, alice, "public")  # OK

    # Bob uses role-based permissions
    checker.check(policy, Permission.READ, bob, "public")  # OK

    # Agent has limited permissions
    checker.check(policy, Permission.DELETE, agent, "public")  # PermissionError
    ```
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from mcp_refcache.access.actor import Actor, ActorType
from mcp_refcache.access.namespace import DefaultNamespaceResolver, NamespaceResolver
from mcp_refcache.permissions import Permission

if TYPE_CHECKING:
    from mcp_refcache.permissions import AccessPolicy


class PermissionDenied(PermissionError):
    """Raised when an actor lacks the required permission.

    This exception provides detailed information about why permission
    was denied, useful for debugging and audit logging.

    Attributes:
        actor: The actor that was denied.
        required: The permission that was required.
        reason: Human-readable explanation of the denial.
        namespace: The namespace involved (if applicable).
        policy: The policy that was evaluated (if applicable).
    """

    def __init__(
        self,
        message: str,
        *,
        actor: Actor | None = None,
        required: Permission | None = None,
        reason: str | None = None,
        namespace: str | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: The error message.
            actor: The actor that was denied.
            required: The permission that was required.
            reason: Human-readable explanation.
            namespace: The namespace involved.
        """
        super().__init__(message)
        self.actor = actor
        self.required = required
        self.reason = reason
        self.namespace = namespace


@runtime_checkable
class PermissionChecker(Protocol):
    """Protocol for permission checking strategies.

    Implementations of this protocol evaluate access control policies
    and determine whether an actor has the required permissions.

    The protocol requires:
    - check(): Raise PermissionDenied if permission is denied
    - has_permission(): Return bool instead of raising
    - get_effective_permissions(): Return all permissions for an actor
    """

    def check(
        self,
        policy: AccessPolicy,
        required: Permission,
        actor: Actor,
        namespace: str,
    ) -> None:
        """Check if an actor has the required permission.

        Args:
            policy: The access policy to evaluate.
            required: The permission required for the operation.
            actor: The actor attempting the operation.
            namespace: The namespace of the resource.

        Raises:
            PermissionDenied: If the actor lacks the required permission.
        """
        ...

    def has_permission(
        self,
        policy: AccessPolicy,
        required: Permission,
        actor: Actor,
        namespace: str,
    ) -> bool:
        """Check if an actor has the required permission.

        This is a non-throwing version of check().

        Args:
            policy: The access policy to evaluate.
            required: The permission required for the operation.
            actor: The actor attempting the operation.
            namespace: The namespace of the resource.

        Returns:
            True if the actor has the required permission.
        """
        ...

    def get_effective_permissions(
        self,
        policy: AccessPolicy,
        actor: Actor,
        namespace: str,
    ) -> Permission:
        """Get the effective permissions for an actor.

        This returns all permissions the actor has under the given
        policy and namespace, useful for introspection.

        Args:
            policy: The access policy to evaluate.
            actor: The actor to get permissions for.
            namespace: The namespace context.

        Returns:
            Combined Permission flags for all granted permissions.
        """
        ...


class DefaultPermissionChecker:
    """Default implementation of the PermissionChecker protocol.

    Implements the standard permission resolution algorithm:
    1. Explicit deny (denied_actors)
    2. Session binding check (bound_session)
    3. Namespace ownership check (via NamespaceResolver)
    4. Explicit allow (allowed_actors)
    5. Owner permissions (owner + owner_permissions)
    6. Role-based permissions (user_permissions / agent_permissions)

    Example:
        ```python
        checker = DefaultPermissionChecker()

        # With custom namespace resolver
        resolver = CustomNamespaceResolver()
        checker = DefaultPermissionChecker(namespace_resolver=resolver)
        ```
    """

    def __init__(
        self,
        namespace_resolver: NamespaceResolver | None = None,
    ) -> None:
        """Initialize the permission checker.

        Args:
            namespace_resolver: Optional namespace resolver for ownership checks.
                              Defaults to DefaultNamespaceResolver.
        """
        self._namespace_resolver = (
            namespace_resolver
            if namespace_resolver is not None
            else DefaultNamespaceResolver()
        )

    def check(
        self,
        policy: AccessPolicy,
        required: Permission,
        actor: Actor,
        namespace: str,
    ) -> None:
        """Check if an actor has the required permission.

        Applies the permission resolution algorithm in order:
        1. Check explicit deny list
        2. Check session binding
        3. Check namespace ownership
        4. Check explicit allow list
        5. Check owner permissions
        6. Check role-based permissions

        Args:
            policy: The access policy to evaluate.
            required: The permission required for the operation.
            actor: The actor attempting the operation.
            namespace: The namespace of the resource.

        Raises:
            PermissionDenied: If the actor lacks the required permission.
        """
        actor_string = actor.to_string()

        # 1. Explicit deny always wins
        if self._is_explicitly_denied(policy, actor):
            raise PermissionDenied(
                f"Actor {actor_string} is explicitly denied",
                actor=actor,
                required=required,
                reason="explicit_deny",
                namespace=namespace,
            )

        # 2. Session binding check
        if not self._check_session_binding(policy, actor):
            raise PermissionDenied(
                f"Actor {actor_string} session does not match bound session",
                actor=actor,
                required=required,
                reason="session_mismatch",
                namespace=namespace,
            )

        # 3. Namespace ownership check
        if not self._namespace_resolver.validate_access(namespace, actor):
            raise PermissionDenied(
                f"Actor {actor_string} cannot access namespace {namespace}",
                actor=actor,
                required=required,
                reason="namespace_ownership",
                namespace=namespace,
            )

        # 4. Explicit allow bypasses role check
        if self._is_explicitly_allowed(policy, actor):
            return  # Allowed

        # 5. Owner gets owner permissions
        if self._is_owner(policy, actor):
            owner_perms = self._get_owner_permissions(policy)
            if required in owner_perms:
                return  # Allowed
            raise PermissionDenied(
                f"Owner {actor_string} lacks {required.name} permission",
                actor=actor,
                required=required,
                reason="owner_insufficient",
                namespace=namespace,
            )

        # 6. Fall back to role-based permissions
        role_perms = self._get_role_permissions(policy, actor)
        if required in role_perms:
            return  # Allowed

        raise PermissionDenied(
            f"{actor.type.value.capitalize()} lacks {required.name} permission",
            actor=actor,
            required=required,
            reason="role_insufficient",
            namespace=namespace,
        )

    def has_permission(
        self,
        policy: AccessPolicy,
        required: Permission,
        actor: Actor,
        namespace: str,
    ) -> bool:
        """Check if an actor has the required permission.

        Non-throwing version of check().

        Args:
            policy: The access policy to evaluate.
            required: The permission required for the operation.
            actor: The actor attempting the operation.
            namespace: The namespace of the resource.

        Returns:
            True if the actor has the required permission.
        """
        try:
            self.check(policy, required, actor, namespace)
            return True
        except PermissionDenied:
            return False

    def get_effective_permissions(
        self,
        policy: AccessPolicy,
        actor: Actor,
        namespace: str,
    ) -> Permission:
        """Get the effective permissions for an actor.

        Evaluates the policy to determine all permissions the actor
        has, considering all resolution steps.

        Args:
            policy: The access policy to evaluate.
            actor: The actor to get permissions for.
            namespace: The namespace context.

        Returns:
            Combined Permission flags for all granted permissions.
        """
        # If explicitly denied, no permissions
        if self._is_explicitly_denied(policy, actor):
            return Permission.NONE

        # If session doesn't match, no permissions
        if not self._check_session_binding(policy, actor):
            return Permission.NONE

        # If namespace access denied, no permissions
        if not self._namespace_resolver.validate_access(namespace, actor):
            return Permission.NONE

        # If explicitly allowed, check what permissions we'd get
        # (explicit allow just bypasses the check, doesn't grant extra perms)
        # So we still need to determine which permissions apply

        # Owner permissions
        if self._is_owner(policy, actor):
            return self._get_owner_permissions(policy)

        # Role-based permissions
        return self._get_role_permissions(policy, actor)

    def _is_explicitly_denied(self, policy: AccessPolicy, actor: Actor) -> bool:
        """Check if actor is in the explicit deny list."""
        denied = getattr(policy, "denied_actors", None)
        if denied is None:
            return False

        actor_string = actor.to_string()
        for pattern in denied:
            if actor.matches(pattern):
                return True
            # Also check exact match
            if actor_string == pattern:
                return True
        return False

    def _is_explicitly_allowed(self, policy: AccessPolicy, actor: Actor) -> bool:
        """Check if actor is in the explicit allow list."""
        allowed = getattr(policy, "allowed_actors", None)
        if allowed is None:
            return False

        actor_string = actor.to_string()
        for pattern in allowed:
            if actor.matches(pattern):
                return True
            if actor_string == pattern:
                return True
        return False

    def _check_session_binding(self, policy: AccessPolicy, actor: Actor) -> bool:
        """Check if actor's session matches the bound session."""
        bound_session = getattr(policy, "bound_session", None)
        if bound_session is None:
            return True  # No binding, always OK

        return actor.session_id == bound_session

    def _is_owner(self, policy: AccessPolicy, actor: Actor) -> bool:
        """Check if actor is the owner of the resource."""
        owner = getattr(policy, "owner", None)
        if owner is None:
            return False

        return actor.to_string() == owner

    def _get_owner_permissions(self, policy: AccessPolicy) -> Permission:
        """Get the permissions granted to the owner."""
        return getattr(policy, "owner_permissions", Permission.FULL)

    def _get_role_permissions(self, policy: AccessPolicy, actor: Actor) -> Permission:
        """Get the role-based permissions for an actor."""
        if actor.type == ActorType.SYSTEM:
            # System actors get full permissions
            return Permission.FULL
        elif actor.type == ActorType.USER:
            return policy.user_permissions
        elif actor.type == ActorType.AGENT:
            return policy.agent_permissions
        else:
            return Permission.NONE
