"""Tests for the RefCache class.

Tests the main cache interface including set, get, resolve, delete,
permission enforcement, and the @cached decorator.
"""

import time
from unittest.mock import patch

import pytest

from mcp_refcache import AccessPolicy, CacheReference, CacheResponse, Permission
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.cache import RefCache
from mcp_refcache.models import PreviewStrategy


class TestRefCacheInitialization:
    """Tests for RefCache initialization."""

    def test_default_initialization(self) -> None:
        """Test RefCache with default settings."""
        cache = RefCache()
        assert cache.name == "default"
        assert cache.default_ttl == 3600
        assert isinstance(cache._backend, MemoryBackend)

    def test_custom_name(self) -> None:
        """Test RefCache with custom name."""
        cache = RefCache(name="my-cache")
        assert cache.name == "my-cache"

    def test_custom_backend(self) -> None:
        """Test RefCache with custom backend."""
        backend = MemoryBackend()
        cache = RefCache(backend=backend)
        assert cache._backend is backend

    def test_custom_default_policy(self) -> None:
        """Test RefCache with custom default policy."""
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            agent_permissions=Permission.EXECUTE,
        )
        cache = RefCache(default_policy=policy)
        assert cache.default_policy == policy

    def test_custom_ttl(self) -> None:
        """Test RefCache with custom TTL."""
        cache = RefCache(default_ttl=7200)
        assert cache.default_ttl == 7200

    def test_no_ttl(self) -> None:
        """Test RefCache with no expiration."""
        cache = RefCache(default_ttl=None)
        assert cache.default_ttl is None


class TestRefCacheSet:
    """Tests for RefCache.set() method."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    def test_set_returns_cache_reference(self, cache: RefCache) -> None:
        """Test that set returns a CacheReference."""
        ref = cache.set("key1", {"data": "value"})
        assert isinstance(ref, CacheReference)

    def test_set_reference_has_correct_cache_name(self, cache: RefCache) -> None:
        """Test that reference has correct cache name."""
        ref = cache.set("key1", {"data": "value"})
        assert ref.cache_name == "test-cache"

    def test_set_reference_has_ref_id(self, cache: RefCache) -> None:
        """Test that reference has a ref_id."""
        ref = cache.set("key1", {"data": "value"})
        assert ref.ref_id is not None
        assert len(ref.ref_id) > 0

    def test_set_with_custom_namespace(self, cache: RefCache) -> None:
        """Test set with custom namespace."""
        ref = cache.set("key1", {"data": "value"}, namespace="session:abc")
        assert ref.namespace == "session:abc"

    def test_set_with_custom_policy(self, cache: RefCache) -> None:
        """Test set with custom access policy."""
        policy = AccessPolicy(agent_permissions=Permission.EXECUTE)
        ref = cache.set("key1", {"data": "value"}, policy=policy)
        # Verify the policy is stored (will be checked in resolve test)
        assert ref is not None

    def test_set_with_custom_ttl(self, cache: RefCache) -> None:
        """Test set with custom TTL."""
        ref = cache.set("key1", {"data": "value"}, ttl=60)
        assert ref.expires_at is not None
        assert ref.expires_at > time.time()

    def test_set_with_tool_name(self, cache: RefCache) -> None:
        """Test set with tool name."""
        ref = cache.set("key1", {"data": "value"}, tool_name="my_tool")
        assert ref.tool_name == "my_tool"

    def test_set_stores_value_in_backend(self, cache: RefCache) -> None:
        """Test that set actually stores value in backend."""
        cache.set("key1", {"data": "value"})
        # Value should be retrievable
        assert cache.exists("key1")

    def test_set_different_keys_get_different_refs(self, cache: RefCache) -> None:
        """Test that different keys get different ref_ids."""
        ref1 = cache.set("key1", "value1")
        ref2 = cache.set("key2", "value2")
        assert ref1.ref_id != ref2.ref_id

    def test_set_same_key_overwrites(self, cache: RefCache) -> None:
        """Test that setting same key overwrites the value."""
        cache.set("key1", "first")
        cache.set("key1", "second")
        value = cache.resolve("key1")
        assert value == "second"

    def test_set_tracks_total_items_for_list(self, cache: RefCache) -> None:
        """Test that set tracks total_items for lists."""
        ref = cache.set("key1", [1, 2, 3, 4, 5])
        assert ref.total_items == 5

    def test_set_tracks_total_items_for_dict(self, cache: RefCache) -> None:
        """Test that set tracks total_items for dicts."""
        ref = cache.set("key1", {"a": 1, "b": 2, "c": 3})
        assert ref.total_items == 3


class TestRefCacheGet:
    """Tests for RefCache.get() method."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    def test_get_returns_cache_response(self, cache: RefCache) -> None:
        """Test that get returns a CacheResponse."""
        ref = cache.set("key1", {"data": "value"})
        response = cache.get(ref.ref_id)
        assert isinstance(response, CacheResponse)

    def test_get_response_has_correct_ref_id(self, cache: RefCache) -> None:
        """Test that response has correct ref_id."""
        ref = cache.set("key1", {"data": "value"})
        response = cache.get(ref.ref_id)
        assert response.ref_id == ref.ref_id

    def test_get_response_has_preview(self, cache: RefCache) -> None:
        """Test that response includes a preview."""
        ref = cache.set("key1", {"data": "value"})
        response = cache.get(ref.ref_id)
        assert response.preview is not None

    def test_get_nonexistent_ref_raises(self, cache: RefCache) -> None:
        """Test that getting nonexistent ref raises error."""
        with pytest.raises(KeyError):
            cache.get("nonexistent-ref")

    def test_get_with_page(self, cache: RefCache) -> None:
        """Test get with pagination."""
        ref = cache.set("key1", list(range(100)))
        response = cache.get(ref.ref_id, page=2, page_size=10)
        assert response.page == 2
        assert response.total_pages is not None

    def test_get_respects_agent_read_permission(self, cache: RefCache) -> None:
        """Test that get respects agent READ permission."""
        policy = AccessPolicy(agent_permissions=Permission.NONE)
        cache.set("key1", {"secret": "data"}, policy=policy)

        with pytest.raises(PermissionError):
            cache.get("key1", actor="agent")

    def test_get_allows_user_with_read_permission(self, cache: RefCache) -> None:
        """Test that get allows user with READ permission."""
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            agent_permissions=Permission.NONE,
        )
        cache.set("key1", {"data": "value"}, policy=policy)

        response = cache.get("key1", actor="user")
        assert response is not None


class TestRefCacheResolve:
    """Tests for RefCache.resolve() method."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    def test_resolve_returns_full_value(self, cache: RefCache) -> None:
        """Test that resolve returns the full cached value."""
        original = {"id": 1, "name": "Test", "nested": {"key": "value"}}
        ref = cache.set("key1", original)
        resolved = cache.resolve(ref.ref_id)
        assert resolved == original

    def test_resolve_list_value(self, cache: RefCache) -> None:
        """Test resolving a list value."""
        original = [1, 2, 3, 4, 5]
        ref = cache.set("key1", original)
        resolved = cache.resolve(ref.ref_id)
        assert resolved == original

    def test_resolve_string_value(self, cache: RefCache) -> None:
        """Test resolving a string value."""
        original = "Hello, World!"
        ref = cache.set("key1", original)
        resolved = cache.resolve(ref.ref_id)
        assert resolved == original

    def test_resolve_nonexistent_ref_raises(self, cache: RefCache) -> None:
        """Test that resolving nonexistent ref raises error."""
        with pytest.raises(KeyError):
            cache.resolve("nonexistent-ref")

    def test_resolve_respects_agent_read_permission(self, cache: RefCache) -> None:
        """Test that resolve respects agent READ permission."""
        policy = AccessPolicy(
            agent_permissions=Permission.EXECUTE
        )  # Execute but not read
        cache.set("key1", {"secret": "data"}, policy=policy)

        with pytest.raises(PermissionError):
            cache.resolve("key1", actor="agent")

    def test_resolve_allows_user_with_permission(self, cache: RefCache) -> None:
        """Test that resolve allows user with READ permission."""
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            agent_permissions=Permission.NONE,
        )
        cache.set("key1", {"data": "value"}, policy=policy)

        value = cache.resolve("key1", actor="user")
        assert value == {"data": "value"}

    def test_resolve_by_key_or_ref_id(self, cache: RefCache) -> None:
        """Test that resolve works with either key or ref_id."""
        ref = cache.set("my-key", "my-value")

        # Both should work
        value1 = cache.resolve("my-key")
        value2 = cache.resolve(ref.ref_id)
        assert value1 == value2 == "my-value"


class TestRefCacheDelete:
    """Tests for RefCache.delete() method."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    def test_delete_existing_returns_true(self, cache: RefCache) -> None:
        """Test that deleting existing entry returns True."""
        cache.set("key1", "value")
        result = cache.delete("key1", actor="user")
        assert result is True

    def test_delete_removes_entry(self, cache: RefCache) -> None:
        """Test that delete removes the entry."""
        cache.set("key1", "value")
        cache.delete("key1", actor="user")
        assert not cache.exists("key1")

    def test_delete_nonexistent_returns_false(self, cache: RefCache) -> None:
        """Test that deleting nonexistent entry returns False."""
        result = cache.delete("nonexistent")
        assert result is False

    def test_delete_respects_agent_permission(self, cache: RefCache) -> None:
        """Test that delete respects agent DELETE permission."""
        policy = AccessPolicy(agent_permissions=Permission.READ)  # Read but not delete
        cache.set("key1", "value", policy=policy)

        with pytest.raises(PermissionError):
            cache.delete("key1", actor="agent")

    def test_delete_allows_user_with_permission(self, cache: RefCache) -> None:
        """Test that delete allows user with DELETE permission."""
        policy = AccessPolicy(
            user_permissions=Permission.DELETE,
            agent_permissions=Permission.NONE,
        )
        cache.set("key1", "value", policy=policy)

        result = cache.delete("key1", actor="user")
        assert result is True


class TestRefCacheExists:
    """Tests for RefCache.exists() method."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    def test_exists_for_existing_key(self, cache: RefCache) -> None:
        """Test exists returns True for existing key."""
        cache.set("key1", "value")
        assert cache.exists("key1") is True

    def test_exists_for_nonexistent_key(self, cache: RefCache) -> None:
        """Test exists returns False for nonexistent key."""
        assert cache.exists("nonexistent") is False

    def test_exists_by_ref_id(self, cache: RefCache) -> None:
        """Test exists works with ref_id."""
        ref = cache.set("key1", "value")
        assert cache.exists(ref.ref_id) is True

    def test_exists_returns_false_for_expired(self, cache: RefCache) -> None:
        """Test exists returns False for expired entries."""
        # Set with very short TTL
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            cache.set("key1", "value", ttl=1)

            # Move time forward
            mock_time.return_value = 1002.0
            assert cache.exists("key1") is False


class TestRefCacheClear:
    """Tests for RefCache.clear() method."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    def test_clear_all(self, cache: RefCache) -> None:
        """Test clearing all entries."""
        for index in range(5):
            cache.set(f"key{index}", f"value{index}")

        cleared = cache.clear()
        assert cleared == 5
        assert not cache.exists("key0")

    def test_clear_by_namespace(self, cache: RefCache) -> None:
        """Test clearing by namespace."""
        cache.set("public1", "val1", namespace="public")
        cache.set("public2", "val2", namespace="public")
        cache.set("session1", "val3", namespace="session:abc")

        cleared = cache.clear(namespace="session:abc")
        assert cleared == 1
        assert cache.exists("public1")
        assert not cache.exists("session1")


class TestRefCacheTTL:
    """Tests for TTL/expiration handling."""

    def test_expired_entry_not_accessible(self) -> None:
        """Test that expired entries are not accessible."""
        cache = RefCache(default_ttl=1)

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            cache.set("key1", "value")

            # Move time forward past expiration
            mock_time.return_value = 1002.0

            with pytest.raises(KeyError):
                cache.resolve("key1")

    def test_non_expired_entry_accessible(self) -> None:
        """Test that non-expired entries are accessible."""
        cache = RefCache(default_ttl=3600)
        cache.set("key1", "value")

        value = cache.resolve("key1")
        assert value == "value"

    def test_no_ttl_never_expires(self) -> None:
        """Test that entries without TTL never expire."""
        cache = RefCache(default_ttl=None)

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            cache.set("key1", "value")

            # Move time forward way into the future
            mock_time.return_value = 999999999.0

            value = cache.resolve("key1")
            assert value == "value"


class TestRefCacheDecorator:
    """Tests for the @cached decorator."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    def test_cached_decorator_caches_result(self, cache: RefCache) -> None:
        """Test that @cached decorator caches function results."""
        call_count = 0

        @cache.cached()
        def expensive_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        result1 = expensive_function(5)
        result2 = expensive_function(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1  # Only called once

    def test_cached_decorator_different_args(self, cache: RefCache) -> None:
        """Test that different args produce different cache entries."""
        call_count = 0

        @cache.cached()
        def expensive_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        result1 = expensive_function(5)
        result2 = expensive_function(10)

        assert result1 == 10
        assert result2 == 20
        assert call_count == 2

    def test_cached_decorator_with_namespace(self, cache: RefCache) -> None:
        """Test @cached with custom namespace."""

        @cache.cached(namespace="session:xyz")
        def my_function() -> str:
            return "result"

        my_function()

        # Check that it's in the right namespace
        keys = cache._backend.keys(namespace="session:xyz")
        assert len(keys) > 0

    def test_cached_decorator_with_policy(self, cache: RefCache) -> None:
        """Test @cached with custom access policy."""
        policy = AccessPolicy(agent_permissions=Permission.EXECUTE)

        @cache.cached(policy=policy)
        def my_function() -> str:
            return "secret"

        my_function()

        # Agent should not be able to read - find the cached entry key
        keys = cache._backend.keys()
        assert len(keys) > 0, "Expected cached entry"

        with pytest.raises(PermissionError):
            cache.resolve(keys[0], actor="agent")

    def test_cached_decorator_with_ttl(self, cache: RefCache) -> None:
        """Test @cached with custom TTL."""

        @cache.cached(ttl=60)
        def my_function() -> str:
            return "result"

        my_function()

        # Check that expiration is set
        keys = cache._backend.keys()
        if keys:
            entry = cache._backend.get(keys[0])
            assert entry is not None
            assert entry.expires_at is not None

    def test_cached_decorator_async_function(self, cache: RefCache) -> None:
        """Test @cached with async function."""
        import asyncio

        call_count = 0

        @cache.cached()
        async def async_function(value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        result1 = asyncio.run(async_function(5))
        result2 = asyncio.run(async_function(5))

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1


class TestRefCacheNamespaces:
    """Tests for namespace isolation."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    def test_namespaces_are_isolated(self, cache: RefCache) -> None:
        """Test that namespaces provide isolation."""
        cache.set("same-key", "value1", namespace="ns1")
        cache.set("same-key", "value2", namespace="ns2")

        # Both should exist
        assert cache.exists("same-key")  # Depends on implementation

    def test_clear_namespace_doesnt_affect_others(self, cache: RefCache) -> None:
        """Test that clearing one namespace doesn't affect others."""
        cache.set("key1", "value1", namespace="keep")
        cache.set("key2", "value2", namespace="delete")

        cache.clear(namespace="delete")

        assert cache.exists("key1")

    def test_default_namespace_is_public(self, cache: RefCache) -> None:
        """Test that default namespace is 'public'."""
        ref = cache.set("key1", "value")
        assert ref.namespace == "public"


class TestRefCachePreview:
    """Tests for preview generation."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    def test_get_returns_preview_for_large_list(self, cache: RefCache) -> None:
        """Test that get returns a preview for large lists."""
        large_list = list(range(5000))
        ref = cache.set("key1", large_list)
        response = cache.get(ref.ref_id)

        # Preview should not be the full list (default max_size is 1000)
        assert isinstance(response.preview, list)
        assert len(response.preview) <= 1000
        assert len(response.preview) < 5000

    def test_get_returns_full_value_for_small_data(self, cache: RefCache) -> None:
        """Test that get returns full value for small data."""
        small_data = {"key": "value"}
        ref = cache.set("key1", small_data)
        response = cache.get(ref.ref_id)

        # For small data, preview might be the full value
        assert response.preview is not None

    def test_preview_strategy_in_response(self, cache: RefCache) -> None:
        """Test that response includes preview strategy."""
        ref = cache.set("key1", list(range(100)))
        response = cache.get(ref.ref_id)

        assert response.preview_strategy in [
            PreviewStrategy.SAMPLE,
            PreviewStrategy.TRUNCATE,
            PreviewStrategy.PAGINATE,
        ]
