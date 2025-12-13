"""Tests for cache backends.

Tests the CacheEntry dataclass, MemoryBackend, and SQLiteBackend implementations.
Both backends are tested through parametrized fixtures to ensure consistent behavior.
"""

import threading
import time
from pathlib import Path

import pytest

from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.backends.sqlite import SQLiteBackend
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


class TestBackendProtocolCompliance:
    """Test that both backends implement the CacheBackend protocol."""

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

    def test_sqlite_backend_is_cache_backend(self) -> None:
        """Test that SQLiteBackend satisfies the CacheBackend protocol."""
        backend = SQLiteBackend(":memory:")
        assert isinstance(backend, CacheBackend)
        backend.close()

    def test_sqlite_backend_has_required_methods(self) -> None:
        """Test that SQLiteBackend has all required protocol methods."""
        backend = SQLiteBackend(":memory:")
        assert hasattr(backend, "get")
        assert hasattr(backend, "set")
        assert hasattr(backend, "delete")
        assert hasattr(backend, "exists")
        assert hasattr(backend, "clear")
        assert hasattr(backend, "keys")
        backend.close()


# Parametrized fixtures for testing both backends with same tests


@pytest.fixture(params=["memory", "sqlite_memory", "sqlite_file"])
def backend(request: pytest.FixtureRequest, tmp_path: Path) -> CacheBackend:
    """Create a backend for testing.

    Parametrized to test MemoryBackend, SQLiteBackend with :memory:,
    and SQLiteBackend with a file-based database.
    """
    if request.param == "memory":
        yield MemoryBackend()
    elif request.param == "sqlite_memory":
        sqlite_backend = SQLiteBackend(":memory:")
        yield sqlite_backend
        sqlite_backend.close()
    elif request.param == "sqlite_file":
        database_path = tmp_path / "test_cache.db"
        sqlite_backend = SQLiteBackend(database_path)
        yield sqlite_backend
        sqlite_backend.close()


@pytest.fixture()
def sample_entry() -> CacheEntry:
    """Create a sample cache entry for testing."""
    return CacheEntry(
        value={"id": 1, "name": "Test"},
        namespace="public",
        policy=AccessPolicy(),
        created_at=time.time(),
    )


class TestBackendBasicOperations:
    """Tests for basic backend operations (parametrized for both backends)."""

    def test_set_and_get(self, backend: CacheBackend, sample_entry: CacheEntry) -> None:
        """Test storing and retrieving an entry."""
        backend.set("key1", sample_entry)
        result = backend.get("key1")

        assert result is not None
        assert result.value == sample_entry.value
        assert result.namespace == sample_entry.namespace

    def test_get_nonexistent_key(self, backend: CacheBackend) -> None:
        """Test getting a key that doesn't exist returns None."""
        result = backend.get("nonexistent")
        assert result is None

    def test_overwrite_existing_key(self, backend: CacheBackend) -> None:
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
        self, backend: CacheBackend, sample_entry: CacheEntry
    ) -> None:
        """Test deleting an existing key returns True."""
        backend.set("key1", sample_entry)
        result = backend.delete("key1")

        assert result is True
        assert backend.get("key1") is None

    def test_delete_nonexistent_key(self, backend: CacheBackend) -> None:
        """Test deleting a nonexistent key returns False."""
        result = backend.delete("nonexistent")
        assert result is False

    def test_exists_for_existing_key(
        self, backend: CacheBackend, sample_entry: CacheEntry
    ) -> None:
        """Test exists returns True for existing key."""
        backend.set("key1", sample_entry)
        assert backend.exists("key1") is True

    def test_exists_for_nonexistent_key(self, backend: CacheBackend) -> None:
        """Test exists returns False for nonexistent key."""
        assert backend.exists("nonexistent") is False

    def test_stores_complex_values(self, backend: CacheBackend) -> None:
        """Test storing and retrieving complex nested values."""
        complex_value = {
            "list": [1, 2, 3, {"nested": True}],
            "dict": {"a": 1, "b": {"c": 2}},
            "string": "hello",
            "number": 42.5,
            "boolean": True,
            "null": None,
        }
        entry = CacheEntry(
            value=complex_value,
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )

        backend.set("complex_key", entry)
        result = backend.get("complex_key")

        assert result is not None
        assert result.value == complex_value

    def test_stores_list_values(self, backend: CacheBackend) -> None:
        """Test storing and retrieving list values."""
        list_value = [1, 2, 3, "four", {"five": 5}]
        entry = CacheEntry(
            value=list_value,
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )

        backend.set("list_key", entry)
        result = backend.get("list_key")

        assert result is not None
        assert result.value == list_value

    def test_preserves_policy(self, backend: CacheBackend) -> None:
        """Test that AccessPolicy is preserved through storage."""
        policy = AccessPolicy(
            owner="user:alice",
            allowed_actors=frozenset({"user:bob", "user:charlie"}),
        )
        entry = CacheEntry(
            value="test",
            namespace="private",
            policy=policy,
            created_at=time.time(),
        )

        backend.set("policy_key", entry)
        result = backend.get("policy_key")

        assert result is not None
        assert result.policy.owner == "user:alice"
        assert result.policy.allowed_actors == frozenset({"user:bob", "user:charlie"})

    def test_preserves_metadata(self, backend: CacheBackend) -> None:
        """Test that metadata is preserved through storage."""
        metadata = {
            "tool_name": "my_tool",
            "total_items": 100,
            "extra": {"nested": True},
        }
        entry = CacheEntry(
            value="test",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
            metadata=metadata,
        )

        backend.set("metadata_key", entry)
        result = backend.get("metadata_key")

        assert result is not None
        assert result.metadata == metadata


class TestBackendExpiration:
    """Tests for TTL/expiration handling (parametrized for both backends)."""

    def test_get_expired_entry_returns_none(self, backend: CacheBackend) -> None:
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

    def test_get_expired_entry_cleans_up(self, backend: CacheBackend) -> None:
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

    def test_exists_returns_false_for_expired(self, backend: CacheBackend) -> None:
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

    def test_non_expired_entry_accessible(self, backend: CacheBackend) -> None:
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


class TestBackendClear:
    """Tests for clear operations (parametrized for both backends)."""

    def test_clear_all(self, backend: CacheBackend) -> None:
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

    def test_clear_by_namespace(self, backend: CacheBackend) -> None:
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

    def test_clear_empty_cache(self, backend: CacheBackend) -> None:
        """Test clearing an empty cache returns 0."""
        cleared = backend.clear()
        assert cleared == 0


class TestBackendKeys:
    """Tests for key listing (parametrized for both backends)."""

    def test_keys_empty_cache(self, backend: CacheBackend) -> None:
        """Test keys returns empty list for empty cache."""
        assert backend.keys() == []

    def test_keys_all(self, backend: CacheBackend) -> None:
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

    def test_keys_by_namespace(self, backend: CacheBackend) -> None:
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

    def test_keys_excludes_expired(self, backend: CacheBackend) -> None:
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


class TestBackendThreadSafety:
    """Tests for thread safety (parametrized for both backends)."""

    def test_concurrent_set_and_get(self, backend: CacheBackend) -> None:
        """Test that concurrent set and get operations don't corrupt data."""
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


# SQLite-specific tests


class TestSQLiteBackendSpecific:
    """Tests specific to SQLiteBackend functionality."""

    def test_database_path_property(self, tmp_path: Path) -> None:
        """Test that database_path property returns the correct path."""
        database_path = tmp_path / "test.db"
        backend = SQLiteBackend(database_path)

        assert backend.database_path == database_path
        backend.close()

    def test_memory_database_path(self) -> None:
        """Test that :memory: database path is preserved."""
        backend = SQLiteBackend(":memory:")

        assert backend.database_path == ":memory:"
        backend.close()

    def test_creates_directory_if_not_exists(self, tmp_path: Path) -> None:
        """Test that SQLiteBackend creates parent directories."""
        database_path = tmp_path / "nested" / "deep" / "cache.db"
        backend = SQLiteBackend(database_path)

        assert database_path.parent.exists()
        backend.close()

    def test_persistence_across_connections(self, tmp_path: Path) -> None:
        """Test that data persists when reopening the database."""
        database_path = tmp_path / "persistent.db"

        # Write with first connection
        backend1 = SQLiteBackend(database_path)
        entry = CacheEntry(
            value="persistent_value",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        backend1.set("persistent_key", entry)
        backend1.close()

        # Read with second connection
        backend2 = SQLiteBackend(database_path)
        result = backend2.get("persistent_key")

        assert result is not None
        assert result.value == "persistent_value"
        backend2.close()

    def test_close_and_reopen(self, tmp_path: Path) -> None:
        """Test closing and reopening the backend."""
        database_path = tmp_path / "reopen.db"

        backend = SQLiteBackend(database_path)
        entry = CacheEntry(
            value="test",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        backend.set("key1", entry)
        backend.close()

        # Reopen and verify
        backend = SQLiteBackend(database_path)
        result = backend.get("key1")
        assert result is not None
        assert result.value == "test"
        backend.close()

    def test_memory_database_not_shared(self) -> None:
        """Test that :memory: databases are isolated per backend instance."""
        backend1 = SQLiteBackend(":memory:")
        backend2 = SQLiteBackend(":memory:")

        entry = CacheEntry(
            value="test",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        backend1.set("key1", entry)

        # backend2 should not see backend1's data
        assert backend2.get("key1") is None

        backend1.close()
        backend2.close()

    def test_environment_variable_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that MCP_REFCACHE_DB_PATH environment variable is respected."""
        env_path = tmp_path / "env_cache.db"
        monkeypatch.setenv("MCP_REFCACHE_DB_PATH", str(env_path))

        backend = SQLiteBackend()

        assert backend.database_path == env_path
        backend.close()

    def test_environment_variable_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that MCP_REFCACHE_DB_PATH can be set to :memory:."""
        monkeypatch.setenv("MCP_REFCACHE_DB_PATH", ":memory:")

        backend = SQLiteBackend()

        assert backend.database_path == ":memory:"
        backend.close()

    def test_xdg_cache_home_respected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that XDG_CACHE_HOME is respected for default path."""
        cache_home = tmp_path / "custom_cache"
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))
        monkeypatch.delenv("MCP_REFCACHE_DB_PATH", raising=False)

        backend = SQLiteBackend()

        expected_path = cache_home / "mcp-refcache" / "cache.db"
        assert backend.database_path == expected_path
        backend.close()


class TestSQLiteBackendConcurrentProcesses:
    """Tests for concurrent access from multiple processes (simulated with threads)."""

    def test_concurrent_writers_different_keys(self, tmp_path: Path) -> None:
        """Test multiple writers writing to different keys concurrently."""
        database_path = tmp_path / "concurrent.db"
        errors: list[Exception] = []

        def writer(backend: SQLiteBackend, writer_id: int) -> None:
            try:
                for iteration in range(50):
                    entry = CacheEntry(
                        value=f"writer{writer_id}_iter{iteration}",
                        namespace="public",
                        policy=AccessPolicy(),
                        created_at=time.time(),
                    )
                    backend.set(f"key_{writer_id}_{iteration}", entry)
            except Exception as exception:
                errors.append(exception)

        # Create multiple backends pointing to same file (simulates multiple processes)
        backends = [SQLiteBackend(database_path) for _ in range(3)]

        threads = [
            threading.Thread(target=writer, args=(backends[index], index))
            for index in range(3)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        for backend in backends:
            backend.close()

        # Verify all data was written
        verify_backend = SQLiteBackend(database_path)
        keys = verify_backend.keys()
        assert len(keys) == 150  # 3 writers * 50 iterations
        verify_backend.close()

        assert len(errors) == 0, f"Concurrent write errors: {errors}"

    def test_concurrent_read_write(self, tmp_path: Path) -> None:
        """Test concurrent reads and writes don't interfere."""
        database_path = tmp_path / "read_write.db"

        # Pre-populate with some data
        setup_backend = SQLiteBackend(database_path)
        for index in range(10):
            entry = CacheEntry(
                value=f"initial_{index}",
                namespace="public",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            setup_backend.set(f"initial_key_{index}", entry)
        setup_backend.close()

        errors: list[Exception] = []
        read_results: list[int] = []

        def reader(backend: SQLiteBackend, reader_id: int) -> None:
            try:
                count = 0
                for _ in range(100):
                    keys = backend.keys()
                    count += len(keys)
                read_results.append(count)
            except Exception as exception:
                errors.append(exception)

        def writer(backend: SQLiteBackend, writer_id: int) -> None:
            try:
                for iteration in range(20):
                    entry = CacheEntry(
                        value=f"writer{writer_id}_iter{iteration}",
                        namespace="public",
                        policy=AccessPolicy(),
                        created_at=time.time(),
                    )
                    backend.set(f"new_key_{writer_id}_{iteration}", entry)
            except Exception as exception:
                errors.append(exception)

        backends = [SQLiteBackend(database_path) for _ in range(4)]

        threads = [
            threading.Thread(target=reader, args=(backends[0], 0)),
            threading.Thread(target=reader, args=(backends[1], 1)),
            threading.Thread(target=writer, args=(backends[2], 0)),
            threading.Thread(target=writer, args=(backends[3], 1)),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        for backend in backends:
            backend.close()

        assert len(errors) == 0, f"Concurrent read/write errors: {errors}"
        # Readers should have seen some data
        assert all(count > 0 for count in read_results)
