"""Tests for PermissionChecker protocol and DefaultPermissionChecker implementation.

Tests cover:
- PermissionDenied exception attributes
- DefaultPermissionChecker.check() permission resolution algorithm
- DefaultPermissionChecker.has_permission() boolean variant
- DefaultPermissionChecker.get_effective_permissions() introspection
- Explicit deny/allow lists
- Session binding
- Namespace ownership integration
- Owner permissions
- Role-based fallback
- PermissionChecker protocol compliance
- Edge cases and integration scenarios
"""

import pytest

from mcp_refcache.access.actor import DefaultActor
from mcp_refcache.access.checker import (
    DefaultPermissionChecker,
    PermissionChecker,
    PermissionDenied,
)
from mcp_refcache.permissions import AccessPolicy, Permission


class TestPermissionDenied:
    """Tests for the PermissionDenied exception."""

    def test_permission_denied_basic_message(self) -> None:
        """PermissionDenied can be created with just a message."""
        error = PermissionDenied("Access denied")
        assert str(error) == "Access denied"
        assert error.actor is None
        assert error.required is None
        assert error.reason is None
        assert error.namespace is None

    def test_permission_denied_with_all_attributes(self) -> None:
        """PermissionDenied stores all attributes."""
        actor = DefaultActor.user(id="alice")
        error = PermissionDenied(
            "User lacks READ permission",
            actor=actor,
            required=Permission.READ,
            reason="role_insufficient",
            namespace="public",
        )

        assert str(error) == "User lacks READ permission"
        assert error.actor is actor
        assert error.required == Permission.READ
        assert error.reason == "role_insufficient"
        assert error.namespace == "public"

    def test_permission_denied_is_permission_error(self) -> None:
        """PermissionDenied inherits from PermissionError."""
        error = PermissionDenied("Test")
        assert isinstance(error, PermissionError)

    def test_permission_denied_can_be_caught_as_permission_error(self) -> None:
        """PermissionDenied can be caught as PermissionError."""
        with pytest.raises(PermissionError):
            raise PermissionDenied("Test")


class TestDefaultPermissionCheckerCheck:
    """Tests for DefaultPermissionChecker.check() method."""

    def test_check_allows_user_with_permission(self) -> None:
        """Check passes when user has required permission."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.READ)
        actor = DefaultActor.user()

        # Should not raise
        checker.check(policy, Permission.READ, actor, "public")

    def test_check_denies_user_without_permission(self) -> None:
        """Check raises when user lacks required permission."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.NONE)
        actor = DefaultActor.user()

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, actor, "public")

        assert exc_info.value.reason == "role_insufficient"
        assert exc_info.value.required == Permission.READ

    def test_check_allows_agent_with_permission(self) -> None:
        """Check passes when agent has required permission."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(agent_permissions=Permission.EXECUTE)
        actor = DefaultActor.agent()

        # Should not raise
        checker.check(policy, Permission.EXECUTE, actor, "public")

    def test_check_denies_agent_without_permission(self) -> None:
        """Check raises when agent lacks required permission."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(agent_permissions=Permission.READ)
        actor = DefaultActor.agent()

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.DELETE, actor, "public")

        assert exc_info.value.reason == "role_insufficient"

    def test_check_system_actor_has_full_permissions(self) -> None:
        """System actors always have full permissions."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.NONE,
            agent_permissions=Permission.NONE,
        )
        system = DefaultActor.system()

        # System can do anything
        checker.check(policy, Permission.READ, system, "public")
        checker.check(policy, Permission.WRITE, system, "public")
        checker.check(policy, Permission.DELETE, system, "public")
        checker.check(policy, Permission.EXECUTE, system, "public")


class TestDefaultPermissionCheckerExplicitDeny:
    """Tests for explicit deny list handling."""

    def test_explicit_deny_blocks_actor(self) -> None:
        """Actor in denied_actors is blocked."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            denied_actors=frozenset({"user:alice"}),
        )
        alice = DefaultActor.user(id="alice")

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, alice, "public")

        assert exc_info.value.reason == "explicit_deny"

    def test_explicit_deny_with_wildcard(self) -> None:
        """Wildcard patterns in denied_actors work."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            agent_permissions=Permission.FULL,
            denied_actors=frozenset({"agent:*"}),
        )
        agent = DefaultActor.agent(id="claude-1")

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, agent, "public")

        assert exc_info.value.reason == "explicit_deny"

    def test_explicit_deny_does_not_affect_other_actors(self) -> None:
        """Denying one actor doesn't affect others."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            denied_actors=frozenset({"user:alice"}),
        )
        bob = DefaultActor.user(id="bob")

        # Bob is not denied
        checker.check(policy, Permission.READ, bob, "public")

    def test_explicit_deny_takes_precedence_over_owner(self) -> None:
        """Explicit deny overrides owner permissions."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            owner="user:alice",
            owner_permissions=Permission.FULL,
            denied_actors=frozenset({"user:alice"}),
        )
        alice = DefaultActor.user(id="alice")

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, alice, "public")

        assert exc_info.value.reason == "explicit_deny"


class TestDefaultPermissionCheckerSessionBinding:
    """Tests for session binding handling."""

    def test_session_binding_allows_matching_session(self) -> None:
        """Actor with matching session_id is allowed."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            bound_session="sess-123",
        )
        actor = DefaultActor.user(session_id="sess-123")

        # Should not raise
        checker.check(policy, Permission.READ, actor, "public")

    def test_session_binding_denies_non_matching_session(self) -> None:
        """Actor with non-matching session_id is denied."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            bound_session="sess-123",
        )
        actor = DefaultActor.user(session_id="sess-456")

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, actor, "public")

        assert exc_info.value.reason == "session_mismatch"

    def test_session_binding_denies_actor_without_session(self) -> None:
        """Actor without session_id is denied when binding is set."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            bound_session="sess-123",
        )
        actor = DefaultActor.user()

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, actor, "public")

        assert exc_info.value.reason == "session_mismatch"

    def test_no_session_binding_allows_any_session(self) -> None:
        """Without bound_session, any session is allowed."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.READ)

        # All these should pass
        checker.check(policy, Permission.READ, DefaultActor.user(), "public")
        checker.check(
            policy, Permission.READ, DefaultActor.user(session_id="any"), "public"
        )


class TestDefaultPermissionCheckerNamespaceOwnership:
    """Tests for namespace ownership integration."""

    def test_namespace_ownership_denies_non_owner(self) -> None:
        """Actor cannot access namespace they don't own."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.FULL)
        bob = DefaultActor.user(id="bob")

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, bob, "user:alice")

        assert exc_info.value.reason == "namespace_ownership"

    def test_namespace_ownership_allows_owner(self) -> None:
        """Actor can access namespace they own."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.READ)
        alice = DefaultActor.user(id="alice")

        # Should not raise
        checker.check(policy, Permission.READ, alice, "user:alice")

    def test_session_namespace_requires_session_match(self) -> None:
        """Session namespace requires matching session_id."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.FULL)

        # Wrong session
        actor = DefaultActor.user(session_id="wrong")
        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, actor, "session:correct")

        assert exc_info.value.reason == "namespace_ownership"

    def test_public_namespace_allows_all(self) -> None:
        """Public namespace has no ownership restrictions."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            agent_permissions=Permission.READ,
        )

        checker.check(policy, Permission.READ, DefaultActor.user(), "public")
        checker.check(policy, Permission.READ, DefaultActor.agent(), "public")

    def test_custom_namespace_resolver(self) -> None:
        """Custom namespace resolver can be injected."""

        class AlwaysDenyResolver:
            def validate_access(self, namespace: str, actor) -> bool:
                return False

            def get_owner(self, namespace: str):
                return None

            def get_required_session(self, namespace: str):
                return None

            def parse(self, namespace: str):
                from mcp_refcache.access.namespace import NamespaceInfo

                return NamespaceInfo(raw=namespace, prefix=namespace)

        checker = DefaultPermissionChecker(namespace_resolver=AlwaysDenyResolver())
        policy = AccessPolicy(user_permissions=Permission.FULL)

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, DefaultActor.user(), "any")

        assert exc_info.value.reason == "namespace_ownership"


class TestDefaultPermissionCheckerExplicitAllow:
    """Tests for explicit allow list handling."""

    def test_explicit_allow_grants_access(self) -> None:
        """Actor in allowed_actors bypasses role check."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.NONE,  # Would normally deny
            allowed_actors=frozenset({"user:alice"}),
        )
        alice = DefaultActor.user(id="alice")

        # Should not raise despite NONE permissions
        checker.check(policy, Permission.READ, alice, "public")

    def test_explicit_allow_with_wildcard(self) -> None:
        """Wildcard patterns in allowed_actors work."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            agent_permissions=Permission.NONE,
            allowed_actors=frozenset({"agent:claude-*"}),
        )
        claude = DefaultActor.agent(id="claude-instance-1")

        # Matches wildcard pattern
        checker.check(policy, Permission.READ, claude, "public")

    def test_explicit_allow_does_not_bypass_deny(self) -> None:
        """Explicit deny still takes precedence over allow."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            allowed_actors=frozenset({"user:alice"}),
            denied_actors=frozenset({"user:alice"}),
        )
        alice = DefaultActor.user(id="alice")

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, alice, "public")

        assert exc_info.value.reason == "explicit_deny"


class TestDefaultPermissionCheckerOwnership:
    """Tests for owner permissions handling."""

    def test_owner_gets_owner_permissions(self) -> None:
        """Owner uses owner_permissions instead of role permissions."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.READ,  # Limited
            owner="user:alice",
            owner_permissions=Permission.FULL,  # Full for owner
        )
        alice = DefaultActor.user(id="alice")

        # Alice can delete because she's owner
        checker.check(policy, Permission.DELETE, alice, "public")

    def test_owner_denied_if_owner_permissions_insufficient(self) -> None:
        """Owner is denied if owner_permissions don't include required."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            owner="user:alice",
            owner_permissions=Permission.READ,  # Owner can only read
        )
        alice = DefaultActor.user(id="alice")

        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.DELETE, alice, "public")

        assert exc_info.value.reason == "owner_insufficient"

    def test_non_owner_uses_role_permissions(self) -> None:
        """Non-owners fall back to role-based permissions."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            owner="user:alice",
            owner_permissions=Permission.FULL,
        )
        bob = DefaultActor.user(id="bob")

        # Bob can read (role permission)
        checker.check(policy, Permission.READ, bob, "public")

        # Bob cannot delete (not owner, role only has READ)
        with pytest.raises(PermissionDenied):
            checker.check(policy, Permission.DELETE, bob, "public")


class TestDefaultPermissionCheckerHasPermission:
    """Tests for DefaultPermissionChecker.has_permission() method."""

    def test_has_permission_returns_true_when_allowed(self) -> None:
        """has_permission returns True when actor has permission."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.READ)
        actor = DefaultActor.user()

        assert checker.has_permission(policy, Permission.READ, actor, "public") is True

    def test_has_permission_returns_false_when_denied(self) -> None:
        """has_permission returns False when actor lacks permission."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.NONE)
        actor = DefaultActor.user()

        assert checker.has_permission(policy, Permission.READ, actor, "public") is False

    def test_has_permission_does_not_raise(self) -> None:
        """has_permission never raises PermissionDenied."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.NONE,
            denied_actors=frozenset({"user:*"}),
        )
        actor = DefaultActor.user(id="alice")

        # Should return False, not raise
        result = checker.has_permission(policy, Permission.READ, actor, "public")
        assert result is False


class TestDefaultPermissionCheckerGetEffectivePermissions:
    """Tests for DefaultPermissionChecker.get_effective_permissions() method."""

    def test_effective_permissions_for_user(self) -> None:
        """Returns user permissions for user actors."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.READ | Permission.WRITE,
            agent_permissions=Permission.EXECUTE,
        )
        user = DefaultActor.user()

        perms = checker.get_effective_permissions(policy, user, "public")
        assert perms == Permission.READ | Permission.WRITE

    def test_effective_permissions_for_agent(self) -> None:
        """Returns agent permissions for agent actors."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            agent_permissions=Permission.READ | Permission.EXECUTE,
        )
        agent = DefaultActor.agent()

        perms = checker.get_effective_permissions(policy, agent, "public")
        assert perms == Permission.READ | Permission.EXECUTE

    def test_effective_permissions_for_system(self) -> None:
        """Returns FULL permissions for system actors."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.NONE,
            agent_permissions=Permission.NONE,
        )
        system = DefaultActor.system()

        perms = checker.get_effective_permissions(policy, system, "public")
        assert perms == Permission.FULL

    def test_effective_permissions_for_owner(self) -> None:
        """Returns owner permissions when actor is owner."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            owner="user:alice",
            owner_permissions=Permission.CRUD,
        )
        alice = DefaultActor.user(id="alice")

        perms = checker.get_effective_permissions(policy, alice, "public")
        assert perms == Permission.CRUD

    def test_effective_permissions_denied_returns_none(self) -> None:
        """Returns NONE when actor is explicitly denied."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            denied_actors=frozenset({"user:alice"}),
        )
        alice = DefaultActor.user(id="alice")

        perms = checker.get_effective_permissions(policy, alice, "public")
        assert perms == Permission.NONE

    def test_effective_permissions_session_mismatch_returns_none(self) -> None:
        """Returns NONE when session doesn't match."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            bound_session="sess-123",
        )
        actor = DefaultActor.user(session_id="wrong")

        perms = checker.get_effective_permissions(policy, actor, "public")
        assert perms == Permission.NONE

    def test_effective_permissions_namespace_denied_returns_none(self) -> None:
        """Returns NONE when namespace access is denied."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.FULL)
        bob = DefaultActor.user(id="bob")

        perms = checker.get_effective_permissions(policy, bob, "user:alice")
        assert perms == Permission.NONE


class TestDefaultPermissionCheckerProtocolCompliance:
    """Tests for PermissionChecker protocol compliance."""

    def test_is_protocol_instance(self) -> None:
        """DefaultPermissionChecker satisfies PermissionChecker protocol."""
        checker = DefaultPermissionChecker()
        assert isinstance(checker, PermissionChecker)

    def test_has_check_method(self) -> None:
        """Has check method."""
        checker = DefaultPermissionChecker()
        assert hasattr(checker, "check")
        assert callable(checker.check)

    def test_has_has_permission_method(self) -> None:
        """Has has_permission method."""
        checker = DefaultPermissionChecker()
        assert hasattr(checker, "has_permission")
        assert callable(checker.has_permission)

    def test_has_get_effective_permissions_method(self) -> None:
        """Has get_effective_permissions method."""
        checker = DefaultPermissionChecker()
        assert hasattr(checker, "get_effective_permissions")
        assert callable(checker.get_effective_permissions)


class TestDefaultPermissionCheckerIntegration:
    """Integration tests combining multiple features."""

    def test_full_resolution_order(self) -> None:
        """Tests the full permission resolution algorithm order."""
        checker = DefaultPermissionChecker()

        # Setup policy with multiple features
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            agent_permissions=Permission.EXECUTE,
            owner="user:owner",
            owner_permissions=Permission.CRUD,
            allowed_actors=frozenset({"user:special"}),
            denied_actors=frozenset({"user:banned"}),
            bound_session="valid-session",
        )

        # 1. Explicit deny wins
        banned = DefaultActor.user(id="banned", session_id="valid-session")
        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, banned, "public")
        assert exc_info.value.reason == "explicit_deny"

        # 2. Session binding
        wrong_session = DefaultActor.user(session_id="wrong-session")
        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, wrong_session, "public")
        assert exc_info.value.reason == "session_mismatch"

        # 3. Namespace ownership (via user namespace)
        bob = DefaultActor.user(id="bob", session_id="valid-session")
        with pytest.raises(PermissionDenied) as exc_info:
            checker.check(policy, Permission.READ, bob, "user:alice")
        assert exc_info.value.reason == "namespace_ownership"

        # 4. Explicit allow bypasses role check
        special = DefaultActor.user(id="special", session_id="valid-session")
        checker.check(
            policy, Permission.DELETE, special, "public"
        )  # Would fail role check

        # 5. Owner gets owner permissions
        owner = DefaultActor.user(id="owner", session_id="valid-session")
        checker.check(
            policy, Permission.DELETE, owner, "public"
        )  # CRUD includes DELETE

        # 6. Role-based fallback
        regular = DefaultActor.user(id="regular", session_id="valid-session")
        checker.check(policy, Permission.READ, regular, "public")  # User has READ

    def test_combined_permissions(self) -> None:
        """Test checking combined permissions."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(
            user_permissions=Permission.READ | Permission.WRITE,
        )
        user = DefaultActor.user()

        # Individual permissions work
        checker.check(policy, Permission.READ, user, "public")
        checker.check(policy, Permission.WRITE, user, "public")

        # Permission not in set fails
        with pytest.raises(PermissionDenied):
            checker.check(policy, Permission.DELETE, user, "public")

    def test_crud_convenience_permission(self) -> None:
        """Test CRUD convenience permission constant."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(user_permissions=Permission.CRUD)
        user = DefaultActor.user()

        # All CRUD operations work
        checker.check(policy, Permission.READ, user, "public")
        checker.check(policy, Permission.WRITE, user, "public")
        checker.check(policy, Permission.UPDATE, user, "public")
        checker.check(policy, Permission.DELETE, user, "public")

        # EXECUTE is not included
        with pytest.raises(PermissionDenied):
            checker.check(policy, Permission.EXECUTE, user, "public")

    def test_agent_with_session_in_user_namespace(self) -> None:
        """Agent with session cannot access user namespace."""
        checker = DefaultPermissionChecker()
        policy = AccessPolicy(agent_permissions=Permission.FULL)

        # Agent has session but that doesn't help with user namespace
        agent = DefaultActor.agent(id="claude", session_id="sess-123")
        with pytest.raises(PermissionDenied):
            checker.check(policy, Permission.READ, agent, "user:alice")

    def test_anonymous_actor_patterns(self) -> None:
        """Test anonymous actors in allow/deny lists."""
        checker = DefaultPermissionChecker()

        # Deny all anonymous users
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            denied_actors=frozenset({"user:*"}),
        )
        anon = DefaultActor.user()  # Anonymous user

        # Anonymous user matches user:* and is denied
        with pytest.raises(PermissionDenied):
            checker.check(policy, Permission.READ, anon, "public")
