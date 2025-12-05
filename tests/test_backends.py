"""Tests for cache backends.

Tests the CacheEntry dataclass and MemoryBackend implementation.
"""

import time

import pytest

from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.permissions import AccessPolicy


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_required_fields(self) -> None:
        """Test CacheEntry with required fields only."""
        entry = CacheEntry(
            value={"key": "value"},
            namespace="public",
            policy=AccessPolicy(),
            created_at=1234567890.0,
        )
        assert entry.value == {"key": "value"}
        assert entry.namespace == "public"
        assert entry.created_at == 1234567890.0
        assert entry.expires_at is None
        assert entry.metadata == {}

    def test_cache_entry_with_expiration(self) -> None:
        """Test CacheEntry with expiration time."""
        entry = CacheEntry(
            value="test",
            namespace="session:abc",
            policy=AccessPolicy(),
            created_at=1000.0,
            expires_at=2000.0,
        )
        assert entry.expires_at == 2000.0

    def test_cache_entry_with_metadata(self) -> None:
        """Test CacheEntry with custom metadata."""
        entry = CacheEntry(
            value=[1, 2, 3],
            namespace="public",
            policy=AccessPolicy(),
            created_at=1000.0,
            metadata={"tool_name": "my_tool", "total_items": 100},
        )
        assert entry.metadata["tool_name"] == "my_tool"
        assert entry.metadata["total_items"] == 100

    def test_is_expired_when_no_expiration(self) -> None:
        """Test is_expired returns False when expires_at is None."""
        entry = CacheEntry(
            value="test",
            namespace="public",
            policy=AccessPolicy(),
            created_at=1000.0,
            expires_at=None,
        )
        assert entry.is_expired(current_time=9999999.0) is False

    def test_is_expired_when_not_expired(self) -> None:
        """Test is_expired returns False before expiration time."""
        entry = CacheEntry(
            value="test",
            namespace="public",
            policy=AccessPolicy(),
            created_at=1000.0,
            expires_at=2000.0,
        )
        assert entry.is_expired(current_time=1500.0) is False

    def test_is_expired_when_expired(self) -> None:
        """Test is_expired returns True after expiration time."""
        entry = CacheEntry(
            value="test",
            namespace="public",
            policy=AccessPolicy(),
            created_at=1000.0,
            expires_at=2000.0,
        )
        assert entry.is_expired(current_time=2000.0) is True
        assert entry.is_expired(current_time=2500.0) is True


class TestMemoryBackendProtocolCompliance:
    """Test that MemoryBackend implements the CacheBackend protocol."""

    def test_memory_backend_is_cache_backend(self) -> None:
        """Test that MemoryBackend satisfies the CacheBackend protocol."""
        backend = MemoryBackend()
        assert isinstance(backend, CacheBackend)

    def test_memory_backend_has_required_methods(self) -> None:
        """Test that MemoryBackend has all required protocol methods."""
        backend = MemoryBackend()
        assert hasattr(backend, "get")
        assert hasattr(backend, "set")
        assert hasattr(backend, "delete")
        assert hasattr(backend, "exists")
        assert hasattr(backend, "clear")
        assert hasattr(backend, "keys")


class TestMemoryBackendBasicOperations:
    """Tests for basic MemoryBackend operations."""

    @pytest.fixture
    def backend(self) -> MemoryBackend:
        """Create a fresh MemoryBackend for each test."""
        return MemoryBackend()

    @pytest.fixture
    def sample_entry(self) -> CacheEntry:
        """Create a sample cache entry for testing."""
        return CacheEntry(
            value={"id": 1, "name": "Test"},
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )

    def test_set_and_get(
        self, backend: MemoryBackend, sample_entry: CacheEntry
    ) -> None:
        """Test storing and retrieving an entry."""
        backend.set("key1", sample_entry)
        result = backend.get("key1")

        assert result is not None
        assert result.value == sample_entry.value
        assert result.namespace == sample_entry.namespace

    def test_get_nonexistent_key(self, backend: MemoryBackend) -> None:
        """Test getting a key that doesn't exist returns None."""
        result = backend.get("nonexistent")
        assert result is None

    def test_overwrite_existing_key(self, backend: MemoryBackend) -> None:
        """Test that setting an existing key overwrites the value."""
        entry1 = CacheEntry(
            value="first",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        entry2 = CacheEntry(
            value="second",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )

        backend.set("key1", entry1)
        backend.set("key1", entry2)

        result = backend.get("key1")
        assert result is not None
        assert result.value == "second"

    def test_delete_existing_key(
        self, backend: MemoryBackend, sample_entry: CacheEntry
    ) -> None:
        """Test deleting an existing key returns True."""
        backend.set("key1", sample_entry)
        result = backend.delete("key1")

        assert result is True
        assert backend.get("key1") is None

    def test_delete_nonexistent_key(self, backend: MemoryBackend) -> None:
        """Test deleting a nonexistent key returns False."""
        result = backend.delete("nonexistent")
        assert result is False

    def test_exists_for_existing_key(
        self, backend: MemoryBackend, sample_entry: CacheEntry
    ) -> None:
        """Test exists returns True for existing key."""
        backend.set("key1", sample_entry)
        assert backend.exists("key1") is True

    def test_exists_for_nonexistent_key(self, backend: MemoryBackend) -> None:
        """Test exists returns False for nonexistent key."""
        assert backend.exists("nonexistent") is False


class TestMemoryBackendExpiration:
    """Tests for TTL/expiration handling in MemoryBackend."""

    @pytest.fixture
    def backend(self) -> MemoryBackend:
        """Create a fresh MemoryBackend for each test."""
        return MemoryBackend()

    def test_get_expired_entry_returns_none(self, backend: MemoryBackend) -> None:
        """Test that getting an expired entry returns None."""
        expired_entry = CacheEntry(
            value="expired",
            namespace="public",
            policy=AccessPolicy(),
            created_at=1000.0,
            expires_at=1000.0,  # Already expired
        )
        backend.set("expired_key", expired_entry)

        result = backend.get("expired_key")
        assert result is None

    def test_get_expired_entry_cleans_up(self, backend: MemoryBackend) -> None:
        """Test that getting an expired entry removes it from storage."""
        expired_entry = CacheEntry(
            value="expired",
            namespace="public",
            policy=AccessPolicy(),
            created_at=1000.0,
            expires_at=1000.0,
        )
        backend.set("expired_key", expired_entry)

        # First get should return None and clean up
        backend.get("expired_key")

        # Key should no longer exist in storage
        keys = backend.keys()
        assert "expired_key" not in keys

    def test_exists_returns_false_for_expired(self, backend: MemoryBackend) -> None:
        """Test that exists returns False for expired entries."""
        expired_entry = CacheEntry(
            value="expired",
            namespace="public",
            policy=AccessPolicy(),
            created_at=1000.0,
            expires_at=1000.0,
        )
        backend.set("expired_key", expired_entry)

        assert backend.exists("expired_key") is False

    def test_non_expired_entry_accessible(self, backend: MemoryBackend) -> None:
        """Test that non-expired entries are still accessible."""
        future_time = time.time() + 3600  # 1 hour from now
        entry = CacheEntry(
            value="valid",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
            expires_at=future_time,
        )
        backend.set("valid_key", entry)

        result = backend.get("valid_key")
        assert result is not None
        assert result.value == "valid"


class TestMemoryBackendClear:
    """Tests for clear operations in MemoryBackend."""

    @pytest.fixture
    def backend(self) -> MemoryBackend:
        """Create a fresh MemoryBackend for each test."""
        return MemoryBackend()

    def test_clear_all(self, backend: MemoryBackend) -> None:
        """Test clearing all entries."""
        for index in range(5):
            entry = CacheEntry(
                value=f"value{index}",
                namespace="public",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"key{index}", entry)

        cleared = backend.clear()

        assert cleared == 5
        assert len(backend.keys()) == 0

    def test_clear_by_namespace(self, backend: MemoryBackend) -> None:
        """Test clearing only entries in a specific namespace."""
        # Add entries in different namespaces
        for index in range(3):
            entry = CacheEntry(
                value=f"public{index}",
                namespace="public",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"public_key{index}", entry)

        for index in range(2):
            entry = CacheEntry(
                value=f"session{index}",
                namespace="session:abc",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"session_key{index}", entry)

        # Clear only session namespace
        cleared = backend.clear(namespace="session:abc")

        assert cleared == 2
        assert len(backend.keys()) == 3
        assert len(backend.keys(namespace="public")) == 3
        assert len(backend.keys(namespace="session:abc")) == 0

    def test_clear_empty_cache(self, backend: MemoryBackend) -> None:
        """Test clearing an empty cache returns 0."""
        cleared = backend.clear()
        assert cleared == 0


class TestMemoryBackendKeys:
    """Tests for key listing in MemoryBackend."""

    @pytest.fixture
    def backend(self) -> MemoryBackend:
        """Create a fresh MemoryBackend for each test."""
        return MemoryBackend()

    def test_keys_empty_cache(self, backend: MemoryBackend) -> None:
        """Test keys returns empty list for empty cache."""
        assert backend.keys() == []

    def test_keys_all(self, backend: MemoryBackend) -> None:
        """Test keys returns all keys when no namespace filter."""
        for index in range(3):
            entry = CacheEntry(
                value=f"value{index}",
                namespace="public",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"key{index}", entry)

        keys = backend.keys()
        assert len(keys) == 3
        assert set(keys) == {"key0", "key1", "key2"}

    def test_keys_by_namespace(self, backend: MemoryBackend) -> None:
        """Test keys filters by namespace."""
        namespaces = ["public", "session:abc", "user:123"]
        for namespace_index, namespace in enumerate(namespaces):
            entry = CacheEntry(
                value=f"value{namespace_index}",
                namespace=namespace,
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"key{namespace_index}", entry)

        public_keys = backend.keys(namespace="public")
        session_keys = backend.keys(namespace="session:abc")
        user_keys = backend.keys(namespace="user:123")

        assert len(public_keys) == 1
        assert len(session_keys) == 1
        assert len(user_keys) == 1

    def test_keys_excludes_expired(self, backend: MemoryBackend) -> None:
        """Test that keys excludes expired entries."""
        # Add valid entry
        valid_entry = CacheEntry(
            value="valid",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )
        backend.set("valid_key", valid_entry)

        # Add expired entry
        expired_entry = CacheEntry(
            value="expired",
            namespace="public",
            policy=AccessPolicy(),
            created_at=1000.0,
            expires_at=1000.0,
        )
        backend.set("expired_key", expired_entry)

        keys = backend.keys()
        assert "valid_key" in keys
        assert "expired_key" not in keys


class TestMemoryBackendThreadSafety:
    """Tests for thread safety in MemoryBackend."""

    def test_concurrent_set_and_get(self) -> None:
        """Test that concurrent set and get operations don't corrupt data."""
        import threading

        backend = MemoryBackend()
        errors: list[Exception] = []

        def writer(thread_index: int) -> None:
            try:
                for iteration in range(100):
                    entry = CacheEntry(
                        value=f"thread{thread_index}_iter{iteration}",
                        namespace="public",
                        policy=AccessPolicy(),
                        created_at=time.time(),
                    )
                    backend.set(f"key_{thread_index}_{iteration}", entry)
            except Exception as exception:
                errors.append(exception)

        def reader() -> None:
            try:
                for _ in range(100):
                    backend.keys()
                    backend.get("key_0_0")
            except Exception as exception:
                errors.append(exception)

        threads = []
        for thread_index in range(5):
            writer_thread = threading.Thread(target=writer, args=(thread_index,))
            reader_thread = threading.Thread(target=reader)
            threads.extend([writer_thread, reader_thread])

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        # Should have 500 keys (5 writers * 100 iterations)
        assert len(backend.keys()) == 500
