"""Tests for Actor protocol and DefaultActor implementation.

Tests cover:
- ActorType enum values
- DefaultActor creation via factory methods
- Actor protocol compliance
- Pattern matching with matches()
- String representation with to_string()
- Backwards compatibility with from_literal()
- resolve_actor() helper function
"""

import pytest

from mcp_refcache.access.actor import (
    Actor,
    ActorLike,
    ActorType,
    DefaultActor,
    resolve_actor,
)


class TestActorType:
    """Tests for the ActorType enum."""

    def test_actor_type_values(self) -> None:
        """ActorType has expected string values."""
        assert ActorType.USER.value == "user"
        assert ActorType.AGENT.value == "agent"
        assert ActorType.SYSTEM.value == "system"

    def test_actor_type_is_string_enum(self) -> None:
        """ActorType values can be used as strings."""
        assert ActorType.USER == "user"
        assert ActorType.AGENT == "agent"
        assert ActorType.SYSTEM == "system"


class TestDefaultActorCreation:
    """Tests for DefaultActor factory methods."""

    def test_user_factory_anonymous(self) -> None:
        """DefaultActor.user() creates anonymous user actor."""
        actor = DefaultActor.user()
        assert actor.type == ActorType.USER
        assert actor.id is None
        assert actor.session_id is None

    def test_user_factory_with_id(self) -> None:
        """DefaultActor.user() accepts id parameter."""
        actor = DefaultActor.user(id="alice")
        assert actor.type == ActorType.USER
        assert actor.id == "alice"
        assert actor.session_id is None

    def test_user_factory_with_session_id(self) -> None:
        """DefaultActor.user() accepts session_id parameter."""
        actor = DefaultActor.user(session_id="sess-123")
        assert actor.type == ActorType.USER
        assert actor.id is None
        assert actor.session_id == "sess-123"

    def test_user_factory_with_both_ids(self) -> None:
        """DefaultActor.user() accepts both id and session_id."""
        actor = DefaultActor.user(id="alice", session_id="sess-123")
        assert actor.type == ActorType.USER
        assert actor.id == "alice"
        assert actor.session_id == "sess-123"

    def test_agent_factory_anonymous(self) -> None:
        """DefaultActor.agent() creates anonymous agent actor."""
        actor = DefaultActor.agent()
        assert actor.type == ActorType.AGENT
        assert actor.id is None
        assert actor.session_id is None

    def test_agent_factory_with_id(self) -> None:
        """DefaultActor.agent() accepts id parameter."""
        actor = DefaultActor.agent(id="claude-instance-1")
        assert actor.type == ActorType.AGENT
        assert actor.id == "claude-instance-1"
        assert actor.session_id is None

    def test_agent_factory_with_session_id(self) -> None:
        """DefaultActor.agent() accepts session_id parameter."""
        actor = DefaultActor.agent(session_id="sess-456")
        assert actor.type == ActorType.AGENT
        assert actor.id is None
        assert actor.session_id == "sess-456"

    def test_system_factory(self) -> None:
        """DefaultActor.system() creates system actor with internal id."""
        actor = DefaultActor.system()
        assert actor.type == ActorType.SYSTEM
        assert actor.id == "internal"
        assert actor.session_id is None


class TestDefaultActorProtocolCompliance:
    """Tests for Actor protocol compliance."""

    def test_default_actor_is_actor_protocol(self) -> None:
        """DefaultActor satisfies Actor protocol at runtime."""
        actor = DefaultActor.user()
        assert isinstance(actor, Actor)

    def test_default_actor_has_type_property(self) -> None:
        """DefaultActor has type property."""
        actor = DefaultActor.user()
        assert hasattr(actor, "type")
        assert actor.type == ActorType.USER

    def test_default_actor_has_id_property(self) -> None:
        """DefaultActor has id property."""
        actor = DefaultActor.user(id="test")
        assert hasattr(actor, "id")
        assert actor.id == "test"

    def test_default_actor_has_session_id_property(self) -> None:
        """DefaultActor has session_id property."""
        actor = DefaultActor.user(session_id="sess-test")
        assert hasattr(actor, "session_id")
        assert actor.session_id == "sess-test"

    def test_default_actor_has_matches_method(self) -> None:
        """DefaultActor has matches method."""
        actor = DefaultActor.user()
        assert hasattr(actor, "matches")
        assert callable(actor.matches)

    def test_default_actor_has_to_string_method(self) -> None:
        """DefaultActor has to_string method."""
        actor = DefaultActor.user()
        assert hasattr(actor, "to_string")
        assert callable(actor.to_string)


class TestDefaultActorPatternMatching:
    """Tests for DefaultActor.matches() pattern matching."""

    def test_matches_exact_user_pattern(self) -> None:
        """Matches exact user:id pattern."""
        actor = DefaultActor.user(id="alice")
        assert actor.matches("user:alice") is True
        assert actor.matches("user:bob") is False

    def test_matches_exact_agent_pattern(self) -> None:
        """Matches exact agent:id pattern."""
        actor = DefaultActor.agent(id="claude-1")
        assert actor.matches("agent:claude-1") is True
        assert actor.matches("agent:claude-2") is False

    def test_matches_wildcard_pattern(self) -> None:
        """Wildcard * matches any id."""
        user = DefaultActor.user(id="alice")
        agent = DefaultActor.agent(id="claude-1")

        assert user.matches("user:*") is True
        assert user.matches("agent:*") is False
        assert agent.matches("agent:*") is True
        assert agent.matches("user:*") is False

    def test_matches_wildcard_for_anonymous_actor(self) -> None:
        """Wildcard matches anonymous actors too."""
        actor = DefaultActor.user()
        assert actor.matches("user:*") is True
        assert actor.matches("agent:*") is False

    def test_anonymous_actor_does_not_match_specific_pattern(self) -> None:
        """Anonymous actors don't match specific id patterns."""
        actor = DefaultActor.user()
        assert actor.matches("user:alice") is False
        assert actor.matches("user:*") is True

    def test_matches_type_must_match(self) -> None:
        """Type portion of pattern must match exactly."""
        user = DefaultActor.user(id="alice")
        agent = DefaultActor.agent(id="alice")

        assert user.matches("user:alice") is True
        assert user.matches("agent:alice") is False
        assert agent.matches("agent:alice") is True
        assert agent.matches("user:alice") is False

    def test_matches_glob_pattern(self) -> None:
        """Supports fnmatch glob patterns."""
        actor = DefaultActor.user(id="alice-admin")

        assert actor.matches("user:alice-*") is True
        assert actor.matches("user:*-admin") is True
        assert actor.matches("user:alice-???in") is True
        assert actor.matches("user:bob-*") is False

    def test_matches_invalid_pattern_no_colon(self) -> None:
        """Returns False for patterns without colon."""
        actor = DefaultActor.user(id="alice")
        assert actor.matches("useralice") is False
        assert actor.matches("alice") is False
        assert actor.matches("") is False

    def test_matches_system_actor(self) -> None:
        """System actors match system patterns."""
        actor = DefaultActor.system()
        assert actor.matches("system:internal") is True
        assert actor.matches("system:*") is True
        assert actor.matches("user:internal") is False


class TestDefaultActorStringRepresentation:
    """Tests for DefaultActor.to_string() and __str__."""

    def test_to_string_identified_user(self) -> None:
        """to_string returns type:id format for identified actors."""
        actor = DefaultActor.user(id="alice")
        assert actor.to_string() == "user:alice"

    def test_to_string_anonymous_user(self) -> None:
        """to_string returns type:* for anonymous actors."""
        actor = DefaultActor.user()
        assert actor.to_string() == "user:*"

    def test_to_string_identified_agent(self) -> None:
        """to_string works for agent actors."""
        actor = DefaultActor.agent(id="claude-1")
        assert actor.to_string() == "agent:claude-1"

    def test_to_string_anonymous_agent(self) -> None:
        """to_string returns agent:* for anonymous agents."""
        actor = DefaultActor.agent()
        assert actor.to_string() == "agent:*"

    def test_to_string_system(self) -> None:
        """to_string works for system actors."""
        actor = DefaultActor.system()
        assert actor.to_string() == "system:internal"

    def test_str_equals_to_string(self) -> None:
        """__str__ returns same as to_string()."""
        actor = DefaultActor.user(id="alice")
        assert str(actor) == actor.to_string()

    def test_repr_format(self) -> None:
        """__repr__ includes all set attributes."""
        actor = DefaultActor.user(id="alice", session_id="sess-123")
        repr_str = repr(actor)
        assert "DefaultActor" in repr_str
        assert "type='user'" in repr_str
        assert "id='alice'" in repr_str
        assert "session_id='sess-123'" in repr_str

    def test_repr_omits_none_values(self) -> None:
        """__repr__ omits None values."""
        actor = DefaultActor.user()
        repr_str = repr(actor)
        assert "id=" not in repr_str
        assert "session_id=" not in repr_str


class TestDefaultActorFromLiteral:
    """Tests for backwards compatibility with literal actors."""

    def test_from_literal_user(self) -> None:
        """from_literal('user') creates anonymous user."""
        actor = DefaultActor.from_literal("user")
        assert actor.type == ActorType.USER
        assert actor.id is None
        assert actor.session_id is None

    def test_from_literal_agent(self) -> None:
        """from_literal('agent') creates anonymous agent."""
        actor = DefaultActor.from_literal("agent")
        assert actor.type == ActorType.AGENT
        assert actor.id is None
        assert actor.session_id is None

    def test_from_literal_with_session_id(self) -> None:
        """from_literal accepts session_id parameter."""
        actor = DefaultActor.from_literal("user", session_id="sess-123")
        assert actor.type == ActorType.USER
        assert actor.id is None
        assert actor.session_id == "sess-123"


class TestResolveActor:
    """Tests for resolve_actor() helper function."""

    def test_resolve_actor_passes_through_actor(self) -> None:
        """resolve_actor returns Actor instances unchanged."""
        original = DefaultActor.user(id="alice")
        resolved = resolve_actor(original)
        assert resolved is original

    def test_resolve_actor_converts_user_literal(self) -> None:
        """resolve_actor converts 'user' to DefaultActor."""
        resolved = resolve_actor("user")
        assert isinstance(resolved, Actor)
        assert resolved.type == ActorType.USER
        assert resolved.id is None

    def test_resolve_actor_converts_agent_literal(self) -> None:
        """resolve_actor converts 'agent' to DefaultActor."""
        resolved = resolve_actor("agent")
        assert isinstance(resolved, Actor)
        assert resolved.type == ActorType.AGENT
        assert resolved.id is None

    def test_resolve_actor_with_session_id(self) -> None:
        """resolve_actor attaches session_id to literal actors."""
        resolved = resolve_actor("user", session_id="sess-123")
        assert resolved.type == ActorType.USER
        assert resolved.session_id == "sess-123"

    def test_resolve_actor_ignores_session_for_actor_objects(self) -> None:
        """session_id parameter is ignored for Actor objects."""
        original = DefaultActor.user(id="alice", session_id="original")
        resolved = resolve_actor(original, session_id="different")
        assert resolved.session_id == "original"


class TestDefaultActorImmutability:
    """Tests for DefaultActor immutability (frozen model)."""

    def test_actor_is_frozen(self) -> None:
        """DefaultActor is immutable."""
        from pydantic import ValidationError

        actor = DefaultActor.user(id="alice")
        with pytest.raises(ValidationError, match="frozen"):
            actor.actor_id = "bob"  # type: ignore[misc]

    def test_actor_is_hashable(self) -> None:
        """DefaultActor can be used in sets and as dict keys."""
        actor1 = DefaultActor.user(id="alice")
        actor2 = DefaultActor.user(id="alice")
        actor3 = DefaultActor.user(id="bob")

        # Same parameters create equal actors
        assert actor1 == actor2
        assert hash(actor1) == hash(actor2)

        # Different parameters create different actors
        assert actor1 != actor3

        # Can be used in sets
        actor_set = {actor1, actor2, actor3}
        assert len(actor_set) == 2  # actor1 and actor2 are duplicates

    def test_actor_as_dict_key(self) -> None:
        """DefaultActor can be used as dict key."""
        actor = DefaultActor.user(id="alice")
        permissions_map = {actor: "admin"}
        assert permissions_map[actor] == "admin"


class TestActorLikeTypeAlias:
    """Tests for ActorLike type alias usage."""

    def test_actor_like_accepts_actor(self) -> None:
        """ActorLike accepts Actor instances."""
        actor: ActorLike = DefaultActor.user(id="alice")
        assert isinstance(actor, Actor)

    def test_actor_like_accepts_literal_user(self) -> None:
        """ActorLike accepts literal 'user'."""
        actor: ActorLike = "user"
        assert actor == "user"

    def test_actor_like_accepts_literal_agent(self) -> None:
        """ActorLike accepts literal 'agent'."""
        actor: ActorLike = "agent"
        assert actor == "agent"
