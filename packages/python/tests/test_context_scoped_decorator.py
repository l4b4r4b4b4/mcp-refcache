"""Tests for context-scoped caching in the @cache.cached() decorator.

Tests the new parameters:
- namespace_template: Dynamic namespace with {placeholders}
- owner_template: Dynamic owner with {placeholders}
- session_scoped: Bind to current session
"""

from typing import Any
from unittest.mock import patch

import pytest

from mcp_refcache import AccessPolicy, Permission, RefCache


class MockFastMCPContext:
    """Mock FastMCP Context for testing."""

    def __init__(
        self,
        session_id: str | None = None,
        client_id: str | None = None,
        request_id: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> None:
        self.session_id = session_id
        self.client_id = client_id
        self.request_id = request_id
        self._state = state or {}

    def get_state(self, key: str) -> Any:
        return self._state.get(key)


@pytest.fixture
def cache() -> RefCache:
    """Create a fresh RefCache for each test."""
    return RefCache(name="test-context")


class TestNamespaceTemplate:
    """Tests for namespace_template parameter."""

    def test_namespace_template_expands_user_id(self, cache: RefCache) -> None:
        """Test namespace template expands {user_id} from context."""
        mock_ctx = MockFastMCPContext(
            session_id="sess-123",
            state={"user_id": "alice"},
        )

        @cache.cached(namespace_template="user:{user_id}")
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        assert "ref_id" in result
        # The ref should be in the "user:alice" namespace
        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.namespace == "user:alice"

    def test_namespace_template_expands_multiple_placeholders(
        self, cache: RefCache
    ) -> None:
        """Test namespace template with multiple placeholders."""
        mock_ctx = MockFastMCPContext(
            state={"org_id": "acme", "user_id": "bob"},
        )

        @cache.cached(namespace_template="org:{org_id}:user:{user_id}")
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.namespace == "org:acme:user:bob"

    def test_namespace_template_uses_fallback_for_missing_values(
        self, cache: RefCache
    ) -> None:
        """Test namespace template uses fallbacks for missing context values."""
        mock_ctx = MockFastMCPContext(
            state={},  # No user_id or org_id
        )

        @cache.cached(namespace_template="org:{org_id}:user:{user_id}")
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        # Should use fallback values
        assert entry.namespace == "org:default:user:anonymous"

    def test_namespace_template_without_context_uses_fallbacks(
        self, cache: RefCache
    ) -> None:
        """Test namespace template works when FastMCP context is not available."""

        @cache.cached(namespace_template="user:{user_id}")
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=None,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.namespace == "user:anonymous"

    def test_namespace_template_takes_priority_over_static_namespace(
        self, cache: RefCache
    ) -> None:
        """Test that namespace_template takes priority over namespace."""
        mock_ctx = MockFastMCPContext(
            state={"user_id": "charlie"},
        )

        # Both namespace and namespace_template provided
        @cache.cached(namespace="static:namespace", namespace_template="user:{user_id}")
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        # Template should win
        assert entry.namespace == "user:charlie"


class TestOwnerTemplate:
    """Tests for owner_template parameter."""

    def test_owner_template_sets_policy_owner(self, cache: RefCache) -> None:
        """Test owner template sets AccessPolicy.owner."""
        mock_ctx = MockFastMCPContext(
            state={"user_id": "alice"},
        )

        @cache.cached(owner_template="user:{user_id}")
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.policy.owner == "user:alice"

    def test_owner_template_with_org_and_user(self, cache: RefCache) -> None:
        """Test owner template with multiple placeholders."""
        mock_ctx = MockFastMCPContext(
            state={"org_id": "acme", "user_id": "bob"},
        )

        @cache.cached(owner_template="org:{org_id}:user:{user_id}")
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.policy.owner == "org:acme:user:bob"

    def test_owner_template_preserves_base_policy_permissions(
        self, cache: RefCache
    ) -> None:
        """Test that owner_template preserves other policy settings."""
        mock_ctx = MockFastMCPContext(
            state={"user_id": "alice"},
        )

        base_policy = AccessPolicy(
            user_permissions=Permission.READ,
            agent_permissions=Permission.EXECUTE,
        )

        @cache.cached(policy=base_policy, owner_template="user:{user_id}")
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        # Owner should be set
        assert entry.policy.owner == "user:alice"
        # Permissions should be preserved
        assert entry.policy.user_permissions == Permission.READ
        assert entry.policy.agent_permissions == Permission.EXECUTE


class TestSessionScoped:
    """Tests for session_scoped parameter."""

    def test_session_scoped_binds_to_session(self, cache: RefCache) -> None:
        """Test session_scoped=True sets bound_session in policy."""
        mock_ctx = MockFastMCPContext(
            session_id="sess-abc-123",
        )

        @cache.cached(session_scoped=True)
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.policy.bound_session == "sess-abc-123"

    def test_session_scoped_without_session_id_is_none(self, cache: RefCache) -> None:
        """Test session_scoped with no session_id doesn't set bound_session."""
        mock_ctx = MockFastMCPContext(
            session_id=None,  # No session
        )

        @cache.cached(session_scoped=True)
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        # bound_session should be None when no session available
        assert entry.policy.bound_session is None

    def test_session_scoped_with_owner_template(self, cache: RefCache) -> None:
        """Test combining session_scoped with owner_template."""
        mock_ctx = MockFastMCPContext(
            session_id="sess-xyz",
            state={"user_id": "alice"},
        )

        @cache.cached(
            owner_template="user:{user_id}",
            session_scoped=True,
        )
        def get_data() -> dict[str, str]:
            return {"data": "value"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.policy.owner == "user:alice"
        assert entry.policy.bound_session == "sess-xyz"


class TestCombinedContextScoping:
    """Tests for combining namespace_template, owner_template, and session_scoped."""

    def test_full_context_scoping(self, cache: RefCache) -> None:
        """Test using all context-scoped parameters together."""
        mock_ctx = MockFastMCPContext(
            session_id="sess-full-test",
            state={"org_id": "acme", "user_id": "alice"},
        )

        @cache.cached(
            namespace_template="org:{org_id}:user:{user_id}",
            owner_template="user:{user_id}",
            session_scoped=True,
        )
        def get_data() -> dict[str, str]:
            return {"important": "data"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.namespace == "org:acme:user:alice"
        assert entry.policy.owner == "user:alice"
        assert entry.policy.bound_session == "sess-full-test"

    def test_different_users_get_different_namespaces(self, cache: RefCache) -> None:
        """Test that different users get isolated cache entries."""

        @cache.cached(namespace_template="user:{user_id}")
        def get_data() -> dict[str, str]:
            return {"shared": "function"}

        # User Alice
        mock_ctx_alice = MockFastMCPContext(
            state={"user_id": "alice"},
        )
        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx_alice,
        ):
            result_alice = get_data()

        # User Bob
        mock_ctx_bob = MockFastMCPContext(
            state={"user_id": "bob"},
        )
        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx_bob,
        ):
            result_bob = get_data()

        # Should have different ref_ids (different namespaces)
        assert result_alice["ref_id"] != result_bob["ref_id"]

        # Verify namespaces
        entry_alice = cache._backend.get(result_alice["ref_id"])
        entry_bob = cache._backend.get(result_bob["ref_id"])
        assert entry_alice is not None
        assert entry_bob is not None
        assert entry_alice.namespace == "user:alice"
        assert entry_bob.namespace == "user:bob"


class TestAsyncContextScoping:
    """Tests for context-scoped caching with async functions."""

    @pytest.mark.asyncio
    async def test_async_namespace_template(self, cache: RefCache) -> None:
        """Test namespace_template works with async functions."""
        mock_ctx = MockFastMCPContext(
            state={"user_id": "async_user"},
        )

        @cache.cached(namespace_template="user:{user_id}")
        async def get_async_data() -> dict[str, str]:
            return {"async": "data"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = await get_async_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.namespace == "user:async_user"

    @pytest.mark.asyncio
    async def test_async_full_context_scoping(self, cache: RefCache) -> None:
        """Test all context-scoped parameters with async function."""
        mock_ctx = MockFastMCPContext(
            session_id="async-sess-123",
            state={"org_id": "async_org", "user_id": "async_user"},
        )

        @cache.cached(
            namespace_template="org:{org_id}:user:{user_id}",
            owner_template="user:{user_id}",
            session_scoped=True,
        )
        async def get_async_data() -> dict[str, str]:
            return {"async": "data"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = await get_async_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.namespace == "org:async_org:user:async_user"
        assert entry.policy.owner == "user:async_user"
        assert entry.policy.bound_session == "async-sess-123"


class TestActorDerivation:
    """Tests for automatic actor derivation from context."""

    def test_actor_derived_from_user_id(self, cache: RefCache) -> None:
        """Test that actor is derived from user_id in context."""
        mock_ctx = MockFastMCPContext(
            session_id="sess-actor-test",
            state={"user_id": "alice"},
        )

        # We need to test that ref resolution uses the derived actor
        # First, create a ref with owner policy
        ref = cache.set(
            "test-key",
            [1, 2, 3],
            namespace="public",
            policy=AccessPolicy(
                owner="user:alice",
                owner_permissions=Permission.FULL,
                agent_permissions=Permission.NONE,  # Deny agents
            ),
        )

        @cache.cached(namespace_template="user:{user_id}")
        def process_data(data: list[int]) -> int:
            return sum(data)

        # When context has user_id=alice, should be able to resolve the ref
        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            # The actor derived from context should match the owner
            result = process_data(data=ref.ref_id)

        assert "ref_id" in result
        assert result["value"] == 6  # sum([1, 2, 3])

    def test_actor_derived_from_agent_id(self, cache: RefCache) -> None:
        """Test that actor is derived from agent_id when user_id not present."""
        mock_ctx = MockFastMCPContext(
            session_id="sess-agent",
            state={"agent_id": "claude-instance-1"},
        )

        @cache.cached(namespace_template="agent:{agent_id}")
        def get_data() -> dict[str, str]:
            return {"agent": "data"}

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        assert entry.namespace == "agent:claude-instance-1"


class TestNoContextScoping:
    """Tests for decorator behavior when context scoping is not used."""

    def test_static_namespace_without_context_params(self, cache: RefCache) -> None:
        """Test that static namespace works when no context params are used."""

        @cache.cached(namespace="static:namespace")
        def get_data() -> dict[str, str]:
            return {"static": "data"}

        # Even with context available, should use static namespace
        mock_ctx = MockFastMCPContext(
            state={"user_id": "should_be_ignored"},
        )
        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result = get_data()

        ref_id = result["ref_id"]
        entry = cache._backend.get(ref_id)
        assert entry is not None
        # Should use static namespace, not template
        assert entry.namespace == "static:namespace"

    def test_no_context_access_when_not_needed(self, cache: RefCache) -> None:
        """Test that try_get_fastmcp_context is not called unnecessarily."""

        @cache.cached(namespace="public")
        def get_data() -> dict[str, str]:
            return {"public": "data"}

        with patch("mcp_refcache.cache.try_get_fastmcp_context") as mock_get_ctx:
            result = get_data()

        # Should not have called try_get_fastmcp_context
        mock_get_ctx.assert_not_called()
        assert "ref_id" in result


class TestCacheHitWithContextScoping:
    """Tests for cache hits with context-scoped caching."""

    def test_cache_hit_same_user_same_args(self, cache: RefCache) -> None:
        """Test cache hit when same user calls with same args."""
        call_count = 0

        @cache.cached(namespace_template="user:{user_id}")
        def expensive_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        mock_ctx = MockFastMCPContext(
            state={"user_id": "alice"},
        )

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx,
        ):
            result1 = expensive_function(10)
            result2 = expensive_function(10)

        # Same ref_id for cache hit
        assert result1["ref_id"] == result2["ref_id"]
        # Function only called once
        assert call_count == 1

    def test_cache_miss_different_users(self, cache: RefCache) -> None:
        """Test cache miss when different users call with same args."""
        call_count = 0

        @cache.cached(namespace_template="user:{user_id}")
        def expensive_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        mock_ctx_alice = MockFastMCPContext(state={"user_id": "alice"})
        mock_ctx_bob = MockFastMCPContext(state={"user_id": "bob"})

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx_alice,
        ):
            result_alice = expensive_function(10)

        with patch(
            "mcp_refcache.cache.try_get_fastmcp_context",
            return_value=mock_ctx_bob,
        ):
            result_bob = expensive_function(10)

        # Different ref_ids (different namespaces)
        assert result_alice["ref_id"] != result_bob["ref_id"]
        # Function called twice (once per user)
        assert call_count == 2
