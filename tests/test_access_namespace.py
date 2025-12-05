"""Tests for NamespaceResolver protocol and DefaultNamespaceResolver implementation.

Tests cover:
- NamespaceInfo dataclass behavior
- DefaultNamespaceResolver.parse() for various namespace patterns
- DefaultNamespaceResolver.validate_access() for ownership rules
- DefaultNamespaceResolver.get_owner() extraction
- DefaultNamespaceResolver.get_required_session() extraction
- NamespaceResolver protocol compliance
- Edge cases and custom namespaces
"""

from mcp_refcache.access.actor import DefaultActor
from mcp_refcache.access.namespace import (
    DefaultNamespaceResolver,
    NamespaceInfo,
    NamespaceResolver,
)


class TestNamespaceInfo:
    """Tests for the NamespaceInfo dataclass."""

    def test_namespace_info_basic_creation(self) -> None:
        """NamespaceInfo can be created with required fields."""
        info = NamespaceInfo(raw="public", prefix="public")
        assert info.raw == "public"
        assert info.prefix == "public"
        assert info.identifier is None
        assert info.is_public is False
        assert info.is_session_scoped is False
        assert info.is_user_scoped is False
        assert info.is_agent_scoped is False
        assert info.implied_owner is None

    def test_namespace_info_with_all_fields(self) -> None:
        """NamespaceInfo can be created with all fields."""
        info = NamespaceInfo(
            raw="user:alice",
            prefix="user",
            identifier="alice",
            is_public=False,
            is_session_scoped=False,
            is_user_scoped=True,
            is_agent_scoped=False,
            implied_owner="user:alice",
        )
        assert info.raw == "user:alice"
        assert info.prefix == "user"
        assert info.identifier == "alice"
        assert info.is_user_scoped is True
        assert info.implied_owner == "user:alice"

    def test_namespace_info_repr(self) -> None:
        """NamespaceInfo has useful repr."""
        info = NamespaceInfo(raw="session:abc", prefix="session", identifier="abc")
        repr_str = repr(info)
        assert "NamespaceInfo" in repr_str
        assert "session:abc" in repr_str
        assert "session" in repr_str
        assert "abc" in repr_str

    def test_namespace_info_equality(self) -> None:
        """NamespaceInfo equality is based on raw value."""
        info1 = NamespaceInfo(raw="public", prefix="public")
        info2 = NamespaceInfo(raw="public", prefix="public")
        info3 = NamespaceInfo(raw="private", prefix="private")

        assert info1 == info2
        assert info1 != info3

    def test_namespace_info_equality_with_non_namespace_info(self) -> None:
        """NamespaceInfo equality returns NotImplemented for other types."""
        info = NamespaceInfo(raw="public", prefix="public")
        assert info.__eq__("public") is NotImplemented
        assert info.__eq__(42) is NotImplemented


class TestDefaultNamespaceResolverParse:
    """Tests for DefaultNamespaceResolver.parse()."""

    def test_parse_public_namespace(self) -> None:
        """Parses 'public' as public namespace."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("public")

        assert info.raw == "public"
        assert info.prefix == "public"
        assert info.identifier is None
        assert info.is_public is True
        assert info.is_session_scoped is False
        assert info.is_user_scoped is False
        assert info.is_agent_scoped is False
        assert info.implied_owner is None

    def test_parse_session_namespace(self) -> None:
        """Parses 'session:<id>' as session-scoped namespace."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("session:abc123")

        assert info.raw == "session:abc123"
        assert info.prefix == "session"
        assert info.identifier == "abc123"
        assert info.is_public is False
        assert info.is_session_scoped is True
        assert info.is_user_scoped is False
        assert info.is_agent_scoped is False
        assert info.implied_owner is None

    def test_parse_user_namespace(self) -> None:
        """Parses 'user:<id>' as user-scoped namespace."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("user:alice")

        assert info.raw == "user:alice"
        assert info.prefix == "user"
        assert info.identifier == "alice"
        assert info.is_public is False
        assert info.is_session_scoped is False
        assert info.is_user_scoped is True
        assert info.is_agent_scoped is False
        assert info.implied_owner == "user:alice"

    def test_parse_agent_namespace(self) -> None:
        """Parses 'agent:<id>' as agent-scoped namespace."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("agent:claude-1")

        assert info.raw == "agent:claude-1"
        assert info.prefix == "agent"
        assert info.identifier == "claude-1"
        assert info.is_public is False
        assert info.is_session_scoped is False
        assert info.is_user_scoped is False
        assert info.is_agent_scoped is True
        assert info.implied_owner == "agent:claude-1"

    def test_parse_shared_namespace(self) -> None:
        """Parses 'shared:<group>' as shared namespace."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("shared:team-alpha")

        assert info.raw == "shared:team-alpha"
        assert info.prefix == "shared"
        assert info.identifier == "team-alpha"
        assert info.is_public is False
        assert info.is_session_scoped is False
        assert info.is_user_scoped is False
        assert info.is_agent_scoped is False
        assert info.implied_owner is None

    def test_parse_custom_namespace_without_colon(self) -> None:
        """Parses custom namespace without colon."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("custom")

        assert info.raw == "custom"
        assert info.prefix == "custom"
        assert info.identifier is None
        assert info.is_public is False
        assert info.is_session_scoped is False
        assert info.is_user_scoped is False
        assert info.is_agent_scoped is False

    def test_parse_custom_namespace_with_colon(self) -> None:
        """Parses custom namespace with colon."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("custom:my-namespace")

        assert info.raw == "custom:my-namespace"
        assert info.prefix == "custom"
        assert info.identifier == "my-namespace"
        assert info.is_public is False

    def test_parse_namespace_with_multiple_colons(self) -> None:
        """Parses namespace with multiple colons correctly (splits on first)."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("user:alice:extra:stuff")

        assert info.raw == "user:alice:extra:stuff"
        assert info.prefix == "user"
        assert info.identifier == "alice:extra:stuff"
        assert info.is_user_scoped is True
        assert info.implied_owner == "user:alice:extra:stuff"

    def test_parse_empty_identifier(self) -> None:
        """Parses namespace with empty identifier after colon."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("session:")

        assert info.raw == "session:"
        assert info.prefix == "session"
        assert info.identifier == ""
        assert info.is_session_scoped is True


class TestDefaultNamespaceResolverValidateAccess:
    """Tests for DefaultNamespaceResolver.validate_access()."""

    def test_validate_access_public_allows_all(self) -> None:
        """Public namespace allows all actors."""
        resolver = DefaultNamespaceResolver()

        # Anonymous user
        assert resolver.validate_access("public", DefaultActor.user()) is True

        # Identified user
        assert resolver.validate_access("public", DefaultActor.user(id="alice")) is True

        # Anonymous agent
        assert resolver.validate_access("public", DefaultActor.agent()) is True

        # Identified agent
        assert (
            resolver.validate_access("public", DefaultActor.agent(id="claude-1"))
            is True
        )

    def test_validate_access_session_matching(self) -> None:
        """Session namespace requires matching session_id."""
        resolver = DefaultNamespaceResolver()

        # Matching session
        actor = DefaultActor.user(session_id="sess-123")
        assert resolver.validate_access("session:sess-123", actor) is True

        # Non-matching session
        actor_wrong = DefaultActor.user(session_id="sess-456")
        assert resolver.validate_access("session:sess-123", actor_wrong) is False

        # No session
        actor_no_session = DefaultActor.user()
        assert resolver.validate_access("session:sess-123", actor_no_session) is False

    def test_validate_access_session_works_for_agents(self) -> None:
        """Session namespace works for agent actors too."""
        resolver = DefaultNamespaceResolver()

        agent = DefaultActor.agent(session_id="sess-123")
        assert resolver.validate_access("session:sess-123", agent) is True

        agent_wrong = DefaultActor.agent(session_id="sess-456")
        assert resolver.validate_access("session:sess-123", agent_wrong) is False

    def test_validate_access_user_namespace_matching(self) -> None:
        """User namespace requires matching user id."""
        resolver = DefaultNamespaceResolver()

        # Matching user
        alice = DefaultActor.user(id="alice")
        assert resolver.validate_access("user:alice", alice) is True

        # Non-matching user
        bob = DefaultActor.user(id="bob")
        assert resolver.validate_access("user:alice", bob) is False

        # Anonymous user
        anon = DefaultActor.user()
        assert resolver.validate_access("user:alice", anon) is False

    def test_validate_access_user_namespace_rejects_agents(self) -> None:
        """User namespace rejects agent actors."""
        resolver = DefaultNamespaceResolver()

        # Agent with same id as namespace
        agent = DefaultActor.agent(id="alice")
        assert resolver.validate_access("user:alice", agent) is False

    def test_validate_access_agent_namespace_matching(self) -> None:
        """Agent namespace requires matching agent id."""
        resolver = DefaultNamespaceResolver()

        # Matching agent
        claude = DefaultActor.agent(id="claude-1")
        assert resolver.validate_access("agent:claude-1", claude) is True

        # Non-matching agent
        other = DefaultActor.agent(id="other-agent")
        assert resolver.validate_access("agent:claude-1", other) is False

        # Anonymous agent
        anon = DefaultActor.agent()
        assert resolver.validate_access("agent:claude-1", anon) is False

    def test_validate_access_agent_namespace_rejects_users(self) -> None:
        """Agent namespace rejects user actors."""
        resolver = DefaultNamespaceResolver()

        # User with same id as namespace
        user = DefaultActor.user(id="claude-1")
        assert resolver.validate_access("agent:claude-1", user) is False

    def test_validate_access_shared_namespace_allows_all(self) -> None:
        """Shared namespace currently allows all (group membership TBD)."""
        resolver = DefaultNamespaceResolver()

        assert (
            resolver.validate_access("shared:team-alpha", DefaultActor.user()) is True
        )
        assert (
            resolver.validate_access("shared:team-alpha", DefaultActor.agent()) is True
        )
        assert (
            resolver.validate_access("shared:team-alpha", DefaultActor.user(id="alice"))
            is True
        )

    def test_validate_access_custom_namespace_allows_all(self) -> None:
        """Custom namespaces have no implicit restrictions."""
        resolver = DefaultNamespaceResolver()

        assert resolver.validate_access("custom", DefaultActor.user()) is True
        assert resolver.validate_access("custom:value", DefaultActor.agent()) is True
        assert (
            resolver.validate_access("myapp:data", DefaultActor.user(id="alice"))
            is True
        )

    def test_validate_access_system_actor_bypasses_all(self) -> None:
        """System actors bypass all namespace restrictions."""
        resolver = DefaultNamespaceResolver()
        system = DefaultActor.system()

        # Can access session namespace without session_id
        assert resolver.validate_access("session:abc123", system) is True

        # Can access user namespace without matching id
        assert resolver.validate_access("user:alice", system) is True

        # Can access agent namespace
        assert resolver.validate_access("agent:claude-1", system) is True

        # Can access public
        assert resolver.validate_access("public", system) is True


class TestDefaultNamespaceResolverGetOwner:
    """Tests for DefaultNamespaceResolver.get_owner()."""

    def test_get_owner_public_returns_none(self) -> None:
        """Public namespace has no owner."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_owner("public") is None

    def test_get_owner_session_returns_none(self) -> None:
        """Session namespace has no owner (session binding != ownership)."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_owner("session:abc123") is None

    def test_get_owner_user_namespace(self) -> None:
        """User namespace returns user:<id> as owner."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_owner("user:alice") == "user:alice"
        assert resolver.get_owner("user:bob") == "user:bob"

    def test_get_owner_agent_namespace(self) -> None:
        """Agent namespace returns agent:<id> as owner."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_owner("agent:claude-1") == "agent:claude-1"
        assert resolver.get_owner("agent:gpt-4") == "agent:gpt-4"

    def test_get_owner_shared_returns_none(self) -> None:
        """Shared namespace has no single owner."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_owner("shared:team-alpha") is None

    def test_get_owner_custom_returns_none(self) -> None:
        """Custom namespaces have no implied owner."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_owner("custom") is None
        assert resolver.get_owner("custom:value") is None
        assert resolver.get_owner("myapp:data") is None


class TestDefaultNamespaceResolverGetRequiredSession:
    """Tests for DefaultNamespaceResolver.get_required_session()."""

    def test_get_required_session_for_session_namespace(self) -> None:
        """Session namespace returns required session id."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_required_session("session:abc123") == "abc123"
        assert resolver.get_required_session("session:sess-456") == "sess-456"

    def test_get_required_session_for_public(self) -> None:
        """Public namespace has no required session."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_required_session("public") is None

    def test_get_required_session_for_user(self) -> None:
        """User namespace has no required session."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_required_session("user:alice") is None

    def test_get_required_session_for_agent(self) -> None:
        """Agent namespace has no required session."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_required_session("agent:claude-1") is None

    def test_get_required_session_for_custom(self) -> None:
        """Custom namespaces have no required session."""
        resolver = DefaultNamespaceResolver()
        assert resolver.get_required_session("custom") is None
        assert resolver.get_required_session("custom:value") is None


class TestDefaultNamespaceResolverProtocolCompliance:
    """Tests for NamespaceResolver protocol compliance."""

    def test_is_protocol_instance(self) -> None:
        """DefaultNamespaceResolver satisfies NamespaceResolver protocol."""
        resolver = DefaultNamespaceResolver()
        assert isinstance(resolver, NamespaceResolver)

    def test_has_validate_access_method(self) -> None:
        """Has validate_access method."""
        resolver = DefaultNamespaceResolver()
        assert hasattr(resolver, "validate_access")
        assert callable(resolver.validate_access)

    def test_has_get_owner_method(self) -> None:
        """Has get_owner method."""
        resolver = DefaultNamespaceResolver()
        assert hasattr(resolver, "get_owner")
        assert callable(resolver.get_owner)

    def test_has_get_required_session_method(self) -> None:
        """Has get_required_session method."""
        resolver = DefaultNamespaceResolver()
        assert hasattr(resolver, "get_required_session")
        assert callable(resolver.get_required_session)

    def test_has_parse_method(self) -> None:
        """Has parse method."""
        resolver = DefaultNamespaceResolver()
        assert hasattr(resolver, "parse")
        assert callable(resolver.parse)


class TestNamespaceEdgeCases:
    """Edge case tests for namespace handling."""

    def test_empty_namespace(self) -> None:
        """Empty namespace is treated as custom."""
        resolver = DefaultNamespaceResolver()
        info = resolver.parse("")

        assert info.raw == ""
        assert info.prefix == ""
        assert info.identifier is None
        assert info.is_public is False

        # Empty namespace allows access (custom namespace)
        assert resolver.validate_access("", DefaultActor.user()) is True

    def test_namespace_case_sensitivity(self) -> None:
        """Namespace prefixes are case-sensitive."""
        resolver = DefaultNamespaceResolver()

        # Uppercase is not recognized as standard prefix
        info_upper = resolver.parse("PUBLIC")
        assert info_upper.is_public is False

        info_session = resolver.parse("SESSION:abc")
        assert info_session.is_session_scoped is False

        info_user = resolver.parse("USER:alice")
        assert info_user.is_user_scoped is False

    def test_namespace_with_special_characters(self) -> None:
        """Namespaces can contain special characters in identifier."""
        resolver = DefaultNamespaceResolver()

        info = resolver.parse("user:alice@example.com")
        assert info.prefix == "user"
        assert info.identifier == "alice@example.com"
        assert info.is_user_scoped is True
        assert info.implied_owner == "user:alice@example.com"

    def test_namespace_with_uuid(self) -> None:
        """Namespaces work with UUID identifiers."""
        resolver = DefaultNamespaceResolver()

        uuid = "550e8400-e29b-41d4-a716-446655440000"
        info = resolver.parse(f"session:{uuid}")

        assert info.prefix == "session"
        assert info.identifier == uuid
        assert info.is_session_scoped is True

        # Actor with matching session can access
        actor = DefaultActor.user(session_id=uuid)
        assert resolver.validate_access(f"session:{uuid}", actor) is True

    def test_namespace_with_path_like_identifier(self) -> None:
        """Namespaces work with path-like identifiers."""
        resolver = DefaultNamespaceResolver()

        info = resolver.parse("custom:org/repo/branch")
        assert info.prefix == "custom"
        assert info.identifier == "org/repo/branch"
