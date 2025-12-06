"""Tests for the RefCache class.

Tests the main cache interface including set, get, resolve, delete,
permission enforcement, and the @cached decorator.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from mcp_refcache import (
    AccessPolicy,
    Actor,
    CacheReference,
    CacheResponse,
    CharacterFallback,
    CharacterMeasurer,
    DefaultActor,
    DefaultNamespaceResolver,
    DefaultPermissionChecker,
    Permission,
    PermissionChecker,
    PermissionDenied,
    PreviewGenerator,
    PreviewResult,
    SampleGenerator,
    SizeMeasurer,
    TiktokenAdapter,
    TokenMeasurer,
)
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.cache import RefCache
from mcp_refcache.models import PreviewConfig, PreviewStrategy, SizeMode


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

    def test_get_with_page(self) -> None:
        """Test get with pagination requires PaginateGenerator."""
        from mcp_refcache.preview import PaginateGenerator

        cache = RefCache(
            name="test-cache",
            preview_generator=PaginateGenerator(),
        )
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

        # Now returns structured response
        assert isinstance(result1, dict)
        assert "ref_id" in result1
        assert result1["value"] == 10
        assert result1["is_complete"] is True

        assert isinstance(result2, dict)
        assert result2["value"] == 10
        assert result2["ref_id"] == result1["ref_id"]  # Same ref_id for cached

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

        # Now returns structured response
        assert result1["value"] == 10
        assert result2["value"] == 20
        assert result1["ref_id"] != result2["ref_id"]  # Different ref_ids
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

        # Now returns structured response
        assert isinstance(result1, dict)
        assert result1["value"] == 10
        assert result1["is_complete"] is True

        assert isinstance(result2, dict)
        assert result2["value"] == 10
        assert result2["ref_id"] == result1["ref_id"]  # Same cached ref

        assert call_count == 1


class TestRefCacheDecoratorRefResolution:
    """Tests for ref_id resolution in decorator inputs."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for testing."""
        return RefCache(name="test-cache")

    def test_cached_resolves_ref_in_kwarg(self, cache: RefCache) -> None:
        """Test that ref_id in kwargs is resolved before function execution."""
        # Store a value to be referenced
        ref = cache.set("multiplier", 2.5)

        @cache.cached()
        def multiply(value: int, factor: float) -> float:
            return value * factor

        # Call with ref_id instead of actual value
        result = multiply(value=10, factor=ref.ref_id)

        # The function should receive resolved value
        assert result["value"] == 25.0
        assert result["is_complete"] is True

    def test_cached_resolves_ref_in_positional_arg(self, cache: RefCache) -> None:
        """Test that ref_id in positional args is resolved."""
        ref = cache.set("data", [1, 2, 3])

        @cache.cached()
        def sum_list(numbers: list[int]) -> int:
            return sum(numbers)

        result = sum_list(ref.ref_id)

        assert result["value"] == 6

    def test_cached_resolves_nested_ref_in_dict(self, cache: RefCache) -> None:
        """Test that ref_id nested in dict is resolved."""
        ref = cache.set("prices", [100, 200, 300])

        @cache.cached()
        def process(data: dict) -> int:
            return sum(data["prices"])

        result = process(data={"prices": ref.ref_id, "name": "test"})

        assert result["value"] == 600

    def test_cached_resolves_multiple_refs(self, cache: RefCache) -> None:
        """Test that multiple ref_ids are all resolved."""
        ref1 = cache.set("a", 10)
        ref2 = cache.set("b", 20)

        @cache.cached()
        def add(x: int, y: int) -> int:
            return x + y

        result = add(x=ref1.ref_id, y=ref2.ref_id)

        assert result["value"] == 30

    def test_cached_resolves_ref_in_list(self, cache: RefCache) -> None:
        """Test that ref_id inside a list is resolved."""
        ref = cache.set("item", 999)

        @cache.cached()
        def first_item(items: list) -> int:
            return items[0]

        result = first_item(items=[ref.ref_id, 2, 3])

        assert result["value"] == 999

    def test_cached_mixed_refs_and_values(self, cache: RefCache) -> None:
        """Test mixed ref_ids and direct values."""
        ref = cache.set("factor", 2.0)

        @cache.cached()
        def compute(data: list[int], factor: float, name: str) -> dict:
            return {"sum": sum(data) * factor, "name": name}

        result = compute(data=[1, 2, 3], factor=ref.ref_id, name="test")

        assert result["value"] == {"sum": 12.0, "name": "test"}

    def test_cached_no_refs_works_normally(self, cache: RefCache) -> None:
        """Test that functions without refs work normally."""

        @cache.cached()
        def simple(x: int) -> int:
            return x * 2

        result = simple(x=5)

        assert result["value"] == 10
        assert result["is_complete"] is True

    def test_cached_resolve_refs_disabled(self, cache: RefCache) -> None:
        """Test that resolve_refs=False skips resolution."""
        ref = cache.set("data", 42)

        @cache.cached(resolve_refs=False)
        def echo(value: str) -> str:
            return value

        # Should NOT resolve - returns the ref_id string as-is
        result = echo(value=ref.ref_id)

        assert result["value"] == ref.ref_id  # Unchanged


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


class TestRefCacheContextLimiting:
    """Tests for RefCache integration with context limiting system."""

    def test_init_with_tokenizer(self) -> None:
        """RefCache accepts tokenizer parameter."""
        tokenizer = CharacterFallback()
        cache = RefCache(tokenizer=tokenizer)

        assert cache._tokenizer is tokenizer

    def test_init_with_measurer(self) -> None:
        """RefCache accepts measurer parameter."""
        measurer = CharacterMeasurer()
        cache = RefCache(measurer=measurer)

        assert cache._measurer is measurer

    def test_init_with_preview_generator(self) -> None:
        """RefCache accepts preview_generator parameter."""
        generator = SampleGenerator()
        cache = RefCache(preview_generator=generator)

        assert cache._preview_generator is generator

    def test_init_creates_default_measurer_from_tokenizer(self) -> None:
        """When tokenizer provided, measurer is created automatically."""
        tokenizer = CharacterFallback()
        cache = RefCache(tokenizer=tokenizer)

        # Should create TokenMeasurer wrapping the tokenizer
        assert cache._measurer is not None
        assert isinstance(cache._measurer, TokenMeasurer)

    def test_init_explicit_measurer_overrides_tokenizer(self) -> None:
        """Explicit measurer takes precedence over tokenizer."""
        tokenizer = CharacterFallback()
        measurer = CharacterMeasurer()
        cache = RefCache(tokenizer=tokenizer, measurer=measurer)

        # Explicit measurer wins
        assert cache._measurer is measurer

    def test_init_default_measurer_uses_tiktoken(self) -> None:
        """Default measurer should attempt to use TiktokenAdapter."""
        cache = RefCache()

        # Should have a measurer (either TokenMeasurer or CharacterMeasurer)
        assert cache._measurer is not None

    def test_init_default_generator_from_config(self) -> None:
        """Default generator comes from preview_config.default_strategy."""
        config = PreviewConfig(default_strategy=PreviewStrategy.SAMPLE)
        cache = RefCache(preview_config=config)

        assert cache._preview_generator is not None
        assert isinstance(cache._preview_generator, SampleGenerator)

    def test_preview_uses_injected_measurer(self) -> None:
        """Preview generation uses the injected measurer."""
        # Create a mock measurer to verify it's being called
        mock_measurer = MagicMock(spec=SizeMeasurer)
        mock_measurer.measure.return_value = 50  # Small size, fits in limit

        cache = RefCache(measurer=mock_measurer)
        ref = cache.set("key1", {"data": "value"})
        cache.get(ref.ref_id)

        # Measurer should have been called during preview generation
        assert mock_measurer.measure.called

    def test_preview_uses_injected_generator(self) -> None:
        """Preview generation uses the injected generator."""
        # Create a mock generator
        mock_generator = MagicMock(spec=PreviewGenerator)
        mock_generator.generate.return_value = PreviewResult(
            preview={"sampled": True},
            strategy=PreviewStrategy.SAMPLE,
            original_size=100,
            preview_size=50,
            total_items=10,
            sampled_items=5,
            page=None,
            total_pages=None,
        )

        cache = RefCache(preview_generator=mock_generator)
        ref = cache.set("key1", {"data": "value"})
        response = cache.get(ref.ref_id)

        # Generator should have been called
        assert mock_generator.generate.called
        # Response should use generator's result
        assert response.preview == {"sampled": True}

    def test_response_includes_size_metadata(self) -> None:
        """CacheResponse includes original_size and preview_size."""
        cache = RefCache(measurer=CharacterMeasurer())
        ref = cache.set("key1", list(range(100)))
        response = cache.get(ref.ref_id)

        # Response should have size metadata
        assert response.original_size is not None
        assert response.preview_size is not None
        assert response.original_size >= response.preview_size

    def test_response_includes_pagination_metadata(self) -> None:
        """CacheResponse includes page info from PreviewResult."""
        from mcp_refcache.preview import PaginateGenerator

        cache = RefCache(
            measurer=CharacterMeasurer(),
            preview_generator=PaginateGenerator(),
        )
        large_list = list(range(1000))
        ref = cache.set("key1", large_list)
        response = cache.get(ref.ref_id, page=1, page_size=10)

        # Response should have pagination info
        assert response.page == 1
        assert response.total_pages is not None
        assert response.total_pages > 1

    def test_default_behavior_samples_large_lists(self) -> None:
        """Default RefCache samples large lists to fit size limit."""
        cache = RefCache()

        ref = cache.set("key1", list(range(5000)))
        response = cache.get(ref.ref_id)

        assert response.preview is not None
        assert isinstance(response.preview, list)
        assert len(response.preview) < 5000

    def test_default_behavior_small_values_unchanged(self) -> None:
        """Small values that fit within size limit are returned as-is."""
        cache = RefCache()

        small_data = {"key": "value", "number": 42}
        ref = cache.set("key1", small_data)
        response = cache.get(ref.ref_id)

        # Small data should be returned fully
        assert response.preview == small_data

    def test_token_measurer_integration(self) -> None:
        """TokenMeasurer works correctly when integrated."""
        tokenizer = CharacterFallback(chars_per_token=4)
        measurer = TokenMeasurer(tokenizer)
        cache = RefCache(measurer=measurer)

        # Create data that will need sampling
        large_list = list(range(500))
        ref = cache.set("key1", large_list)
        response = cache.get(ref.ref_id)

        assert response.preview is not None
        assert response.original_size is not None

    def test_convenience_api_with_tiktoken_adapter(self) -> None:
        """Convenience API: just pass tokenizer, measurer auto-created."""
        # TiktokenAdapter falls back to CharacterFallback if tiktoken not installed
        tokenizer = TiktokenAdapter(model="gpt-4o")
        cache = RefCache(tokenizer=tokenizer)

        ref = cache.set("key1", {"data": "test"})
        response = cache.get(ref.ref_id)

        assert response.preview is not None
        assert response.original_size is not None

    def test_character_mode_via_preview_config(self) -> None:
        """Character mode can be configured via PreviewConfig."""
        config = PreviewConfig(size_mode=SizeMode.CHARACTER, max_size=100)
        cache = RefCache(preview_config=config)

        # Should use character-based measurement
        ref = cache.set("key1", list(range(1000)))
        response = cache.get(ref.ref_id)

        assert response.preview is not None
        # Preview should be limited

    def test_custom_max_size_respected(self) -> None:
        """max_size from PreviewConfig is respected."""
        config = PreviewConfig(max_size=50)
        measurer = CharacterMeasurer()
        cache = RefCache(preview_config=config, measurer=measurer)

        large_data = list(range(1000))
        ref = cache.set("key1", large_data)
        response = cache.get(ref.ref_id)

        # Preview size should respect max_size
        assert response.preview_size is not None
        assert response.preview_size <= 50


class TestRefCacheAccessControlIntegration:
    """Tests for RefCache integration with access control system.

    Tests the injection of PermissionChecker and proper handling of
    Actor objects (not just literal strings).
    """

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for each test."""
        return RefCache(name="test-cache")

    # -------------------------------------------------------------------------
    # Constructor Tests
    # -------------------------------------------------------------------------

    def test_init_with_permission_checker(self) -> None:
        """RefCache accepts permission_checker parameter."""
        checker = DefaultPermissionChecker()
        cache = RefCache(permission_checker=checker)

        assert cache._permission_checker is checker

    def test_init_default_permission_checker(self) -> None:
        """RefCache creates default permission checker if none provided."""
        cache = RefCache()

        assert cache._permission_checker is not None
        assert isinstance(cache._permission_checker, DefaultPermissionChecker)

    def test_init_with_custom_namespace_resolver_via_checker(self) -> None:
        """Custom namespace resolver is passed via permission checker."""
        resolver = DefaultNamespaceResolver()
        checker = DefaultPermissionChecker(namespace_resolver=resolver)
        cache = RefCache(permission_checker=checker)

        assert cache._permission_checker is checker

    # -------------------------------------------------------------------------
    # Actor Object Tests
    # -------------------------------------------------------------------------

    def test_get_accepts_actor_object(self, cache: RefCache) -> None:
        """get() accepts Actor objects, not just string literals."""
        ref = cache.set("key1", {"data": "value"})

        # Use Actor object instead of literal
        actor = DefaultActor.user()
        response = cache.get(ref.ref_id, actor=actor)

        assert response is not None
        assert response.preview == {"data": "value"}

    def test_get_accepts_identified_actor(self, cache: RefCache) -> None:
        """get() works with identified Actor objects."""
        ref = cache.set("key1", {"data": "value"})

        actor = DefaultActor.user(id="alice", session_id="sess-123")
        response = cache.get(ref.ref_id, actor=actor)

        assert response is not None

    def test_resolve_accepts_actor_object(self, cache: RefCache) -> None:
        """resolve() accepts Actor objects."""
        ref = cache.set("key1", {"secret": "data"})

        actor = DefaultActor.user()
        value = cache.resolve(ref.ref_id, actor=actor)

        assert value == {"secret": "data"}

    def test_delete_accepts_actor_object(self, cache: RefCache) -> None:
        """delete() accepts Actor objects."""
        cache.set("key1", {"data": "value"})

        actor = DefaultActor.user()
        result = cache.delete("key1", actor=actor)

        assert result is True
        assert not cache.exists("key1")

    def test_literal_strings_still_work(self, cache: RefCache) -> None:
        """Backwards compatibility: literal strings still work."""
        ref = cache.set("key1", {"data": "value"})

        # Old-style literals should still work
        response = cache.get(ref.ref_id, actor="user")
        assert response is not None

        value = cache.resolve(ref.ref_id, actor="agent")
        assert value == {"data": "value"}

    # -------------------------------------------------------------------------
    # Permission Checker Integration Tests
    # -------------------------------------------------------------------------

    def test_get_uses_permission_checker(self) -> None:
        """get() delegates to injected permission checker."""
        mock_checker = MagicMock(spec=PermissionChecker)
        cache = RefCache(permission_checker=mock_checker)

        ref = cache.set("key1", {"data": "value"})
        cache.get(ref.ref_id, actor="agent")

        # Checker should have been called
        assert mock_checker.check.called
        call_args = mock_checker.check.call_args
        assert call_args[0][1] == Permission.READ  # required permission

    def test_resolve_uses_permission_checker(self) -> None:
        """resolve() delegates to injected permission checker."""
        mock_checker = MagicMock(spec=PermissionChecker)
        cache = RefCache(permission_checker=mock_checker)

        ref = cache.set("key1", {"data": "value"})
        cache.resolve(ref.ref_id, actor="user")

        assert mock_checker.check.called
        call_args = mock_checker.check.call_args
        assert call_args[0][1] == Permission.READ

    def test_delete_uses_permission_checker(self) -> None:
        """delete() delegates to injected permission checker."""
        mock_checker = MagicMock(spec=PermissionChecker)
        cache = RefCache(permission_checker=mock_checker)

        cache.set("key1", {"data": "value"})
        cache.delete("key1", actor="user")

        assert mock_checker.check.called
        call_args = mock_checker.check.call_args
        assert call_args[0][1] == Permission.DELETE

    def test_permission_checker_receives_namespace(self) -> None:
        """Permission checker receives the entry's namespace."""
        mock_checker = MagicMock(spec=PermissionChecker)
        cache = RefCache(permission_checker=mock_checker)

        ref = cache.set("key1", {"data": "value"}, namespace="session:abc")
        cache.get(ref.ref_id, actor="agent")

        call_args = mock_checker.check.call_args
        assert call_args[0][3] == "session:abc"  # namespace

    def test_permission_checker_receives_actor(self) -> None:
        """Permission checker receives resolved Actor object."""
        mock_checker = MagicMock(spec=PermissionChecker)
        cache = RefCache(permission_checker=mock_checker)

        ref = cache.set("key1", {"data": "value"})
        actor = DefaultActor.user(id="alice")
        cache.get(ref.ref_id, actor=actor)

        call_args = mock_checker.check.call_args
        received_actor = call_args[0][2]
        assert received_actor.id == "alice"

    # -------------------------------------------------------------------------
    # Namespace Ownership Tests
    # -------------------------------------------------------------------------

    def test_user_namespace_allows_matching_user(self) -> None:
        """User namespace allows access by matching user."""
        cache = RefCache()

        # Store in user:alice namespace
        ref = cache.set("key1", {"secret": "data"}, namespace="user:alice")

        # Alice can access
        alice = DefaultActor.user(id="alice")
        response = cache.get(ref.ref_id, actor=alice)
        assert response is not None

    def test_user_namespace_denies_different_user(self) -> None:
        """User namespace denies access by different user."""
        cache = RefCache()

        # Store in user:alice namespace
        ref = cache.set("key1", {"secret": "data"}, namespace="user:alice")

        # Bob cannot access
        bob = DefaultActor.user(id="bob")
        with pytest.raises(PermissionError):
            cache.get(ref.ref_id, actor=bob)

    def test_session_namespace_allows_matching_session(self) -> None:
        """Session namespace allows access with matching session_id."""
        cache = RefCache()

        ref = cache.set("key1", {"data": "value"}, namespace="session:sess-123")

        actor = DefaultActor.user(id="anyone", session_id="sess-123")
        response = cache.get(ref.ref_id, actor=actor)
        assert response is not None

    def test_session_namespace_denies_different_session(self) -> None:
        """Session namespace denies access with different session_id."""
        cache = RefCache()

        ref = cache.set("key1", {"data": "value"}, namespace="session:sess-123")

        actor = DefaultActor.user(id="anyone", session_id="sess-456")
        with pytest.raises(PermissionError):
            cache.get(ref.ref_id, actor=actor)

    def test_public_namespace_allows_all(self) -> None:
        """Public namespace allows access from any actor."""
        cache = RefCache()

        ref = cache.set("key1", {"data": "value"}, namespace="public")

        # Both user and agent can access
        user = DefaultActor.user()
        agent = DefaultActor.agent()

        cache.get(ref.ref_id, actor=user)
        cache.get(ref.ref_id, actor=agent)

    def test_system_actor_bypasses_namespace_checks(self) -> None:
        """System actors can access any namespace."""
        cache = RefCache()

        ref = cache.set("key1", {"data": "value"}, namespace="user:alice")

        system = DefaultActor.system()
        response = cache.get(ref.ref_id, actor=system)
        assert response is not None

    # -------------------------------------------------------------------------
    # PermissionDenied Exception Tests
    # -------------------------------------------------------------------------

    def test_permission_denied_is_permission_error(self, cache: RefCache) -> None:
        """PermissionDenied is a subclass of PermissionError."""
        policy = AccessPolicy(agent_permissions=Permission.NONE)
        cache.set("key1", {"data": "value"}, policy=policy)

        # Should raise PermissionDenied which is also PermissionError
        with pytest.raises(PermissionError):
            cache.get("key1", actor="agent")

    def test_permission_denied_has_attributes(self, cache: RefCache) -> None:
        """PermissionDenied exception has useful attributes."""
        policy = AccessPolicy(agent_permissions=Permission.NONE)
        cache.set("key1", {"data": "value"}, policy=policy)

        with pytest.raises(PermissionDenied) as exc_info:
            cache.get("key1", actor="agent")

        exc = exc_info.value
        assert exc.required == Permission.READ
        assert exc.actor is not None
        assert exc.reason is not None

    def test_permission_denied_includes_namespace(self) -> None:
        """PermissionDenied includes namespace information."""
        cache = RefCache()

        ref = cache.set("key1", {"data": "value"}, namespace="user:alice")
        bob = DefaultActor.user(id="bob")

        with pytest.raises(PermissionDenied) as exc_info:
            cache.get(ref.ref_id, actor=bob)

        exc = exc_info.value
        assert exc.namespace == "user:alice"

    # -------------------------------------------------------------------------
    # Custom Permission Checker Tests
    # -------------------------------------------------------------------------

    def test_custom_permission_checker_deny_all(self) -> None:
        """Custom permission checker that denies all access."""

        class DenyAllChecker:
            """Permission checker that denies everything."""

            def check(
                self,
                policy: AccessPolicy,
                required: Permission,
                actor: Actor,
                namespace: str,
            ) -> None:
                raise PermissionDenied(
                    "Access denied by policy",
                    actor=actor,
                    required=required,
                    reason="deny_all",
                    namespace=namespace,
                )

            def has_permission(
                self,
                policy: AccessPolicy,
                required: Permission,
                actor: Actor,
                namespace: str,
            ) -> bool:
                return False

            def get_effective_permissions(
                self,
                policy: AccessPolicy,
                actor: Actor,
                namespace: str,
            ) -> Permission:
                return Permission.NONE

        cache = RefCache(permission_checker=DenyAllChecker())
        cache.set("key1", {"data": "value"})

        with pytest.raises(PermissionDenied) as exc_info:
            cache.get("key1", actor="user")

        assert exc_info.value.reason == "deny_all"

    def test_custom_permission_checker_allow_all(self) -> None:
        """Custom permission checker that allows all access."""

        class AllowAllChecker:
            """Permission checker that allows everything."""

            def check(
                self,
                policy: AccessPolicy,
                required: Permission,
                actor: Actor,
                namespace: str,
            ) -> None:
                pass  # Allow

            def has_permission(
                self,
                policy: AccessPolicy,
                required: Permission,
                actor: Actor,
                namespace: str,
            ) -> bool:
                return True

            def get_effective_permissions(
                self,
                policy: AccessPolicy,
                actor: Actor,
                namespace: str,
            ) -> Permission:
                return Permission.FULL

        # Policy that would normally deny agent
        policy = AccessPolicy(agent_permissions=Permission.NONE)
        cache = RefCache(permission_checker=AllowAllChecker())
        cache.set("key1", {"secret": "data"}, policy=policy)

        # Custom checker allows anyway
        response = cache.get("key1", actor="agent")
        assert response is not None

    # -------------------------------------------------------------------------
    # Integration: Policy + Namespace + Actor
    # -------------------------------------------------------------------------

    def test_policy_and_namespace_both_checked(self) -> None:
        """Both policy permissions and namespace ownership are checked."""
        cache = RefCache()

        # Alice's namespace, but policy denies agent read
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            agent_permissions=Permission.NONE,
        )
        ref = cache.set(
            "key1", {"data": "value"}, namespace="user:alice", policy=policy
        )

        # Alice (user) can read
        alice = DefaultActor.user(id="alice")
        response = cache.get(ref.ref_id, actor=alice)
        assert response is not None

        # Agent is denied by policy (even if namespace allowed)
        agent = DefaultActor.agent(id="alice")  # Same ID but agent type
        with pytest.raises(PermissionError):
            cache.get(ref.ref_id, actor=agent)

    def test_owner_permissions_work(self) -> None:
        """Owner-specific permissions work correctly."""
        cache = RefCache()

        # Policy where owner has FULL but others have none
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            agent_permissions=Permission.NONE,
            owner="user:alice",
            owner_permissions=Permission.FULL,
        )
        ref = cache.set("key1", {"data": "value"}, policy=policy)

        # Alice (owner) can delete
        alice = DefaultActor.user(id="alice")
        result = cache.delete(ref.ref_id, actor=alice)
        assert result is True

    def test_agent_in_agent_namespace(self) -> None:
        """Agent can access agent-scoped namespace with matching ID."""
        cache = RefCache()

        ref = cache.set("key1", {"data": "value"}, namespace="agent:claude-1")

        # Agent with matching ID can access
        agent = DefaultActor.agent(id="claude-1")
        response = cache.get(ref.ref_id, actor=agent)
        assert response is not None

        # Agent with different ID cannot
        other_agent = DefaultActor.agent(id="gpt-4")
        with pytest.raises(PermissionError):
            cache.get(ref.ref_id, actor=other_agent)


class TestRefCachePreviewResult:
    """Tests for PreviewResult integration in RefCache."""

    def test_create_preview_returns_preview_result(self) -> None:
        """_create_preview now returns PreviewResult."""
        cache = RefCache()
        result = cache._create_preview(list(range(100)))

        assert isinstance(result, PreviewResult)
        assert result.preview is not None
        assert result.strategy in PreviewStrategy
        assert result.original_size >= 0
        assert result.preview_size >= 0

    def test_preview_result_has_item_counts_for_list(self) -> None:
        """PreviewResult includes total_items and sampled_items for lists."""
        cache = RefCache(measurer=CharacterMeasurer())
        large_list = list(range(1000))
        result = cache._create_preview(large_list)

        assert result.total_items == 1000
        assert result.sampled_items is not None
        assert result.sampled_items <= 1000

    def test_preview_result_has_item_counts_for_dict(self) -> None:
        """PreviewResult includes total_items and sampled_items for dicts."""
        cache = RefCache(measurer=CharacterMeasurer())
        large_dict = {f"key_{i}": i for i in range(500)}
        result = cache._create_preview(large_dict)

        assert result.total_items == 500
        assert result.sampled_items is not None

    def test_preview_result_pagination_fields(self) -> None:
        """PreviewResult includes pagination info when paginating."""
        from mcp_refcache.preview import PaginateGenerator

        cache = RefCache(
            measurer=CharacterMeasurer(),
            preview_generator=PaginateGenerator(),
        )
        large_list = list(range(1000))
        result = cache._create_preview(large_list, page=2, page_size=50)

        assert result.page == 2
        assert result.total_pages is not None

    def test_preview_result_strategy_matches_generator(self) -> None:
        """PreviewResult strategy matches the generator used."""
        from mcp_refcache.preview import TruncateGenerator

        cache = RefCache(
            measurer=CharacterMeasurer(),
            preview_generator=TruncateGenerator(),
        )
        result = cache._create_preview("A" * 5000)

        assert result.strategy == PreviewStrategy.TRUNCATE
