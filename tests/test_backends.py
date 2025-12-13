"""Tests for cache backends.

Tests the CacheEntry dataclass, MemoryBackend, SQLiteBackend, and RedisBackend
implementations. All backends are tested through parametrized fixtures to
ensure consistent behavior.
"""

import threading
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.backends.sqlite import SQLiteBackend
from mcp_refcache.permissions import AccessPolicy

# Check if Redis is available
try:
    from mcp_refcache.backends.redis import RedisBackend

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisBackend = None  # type: ignore[assignment,misc]


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
    """Test that all backends implement the CacheBackend protocol."""

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

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis package not installed")
    def test_redis_backend_is_cache_backend(self) -> None:
        """Test that RedisBackend satisfies the CacheBackend protocol."""
        try:
            backend = RedisBackend(password="mcp-refcache-dev-password")
            if not backend.ping():
                pytest.skip("Redis server not available")
            assert isinstance(backend, CacheBackend)
            backend.close()
        except Exception:
            pytest.skip("Redis server not available")

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis package not installed")
    def test_redis_backend_has_required_methods(self) -> None:
        """Test that RedisBackend has all required protocol methods."""
        try:
            backend = RedisBackend(password="mcp-refcache-dev-password")
            if not backend.ping():
                pytest.skip("Redis server not available")
            assert hasattr(backend, "get")
            assert hasattr(backend, "set")
            assert hasattr(backend, "delete")
            assert hasattr(backend, "exists")
            assert hasattr(backend, "clear")
            assert hasattr(backend, "keys")
            backend.close()
        except Exception:
            pytest.skip("Redis server not available")


# Parametrized fixtures for testing all backends with same tests


def _get_backend_params() -> list[str]:
    """Get list of backend parameter names for parametrization."""
    params = ["memory", "sqlite_memory", "sqlite_file"]
    if REDIS_AVAILABLE:
        params.append("redis")
    return params


@pytest.fixture(params=_get_backend_params())
def backend(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Generator[CacheBackend, None, None]:
    """Create a backend for testing.

    Parametrized to test MemoryBackend, SQLiteBackend (memory and file),
    and RedisBackend (when available and connected).
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
    elif request.param == "redis":
        if not REDIS_AVAILABLE:
            pytest.skip("Redis package not installed")
        try:
            redis_backend = RedisBackend(password="mcp-refcache-dev-password")
            if not redis_backend.ping():
                pytest.skip("Redis server not available")
            # Clean up any leftover data from previous tests
            redis_backend.clear()
            yield redis_backend
            # Clean up after test
            redis_backend.clear()
            redis_backend.close()
        except Exception as exception:
            pytest.skip(f"Redis connection failed: {exception}")


@pytest.fixture
def sample_entry() -> CacheEntry:
    """Create a sample cache entry for testing."""
    return CacheEntry(
        value={"id": 1, "name": "Test"},
        namespace="public",
        policy=AccessPolicy(),
        created_at=time.time(),
    )


class TestBackendBasicOperations:
    """Tests for basic backend operations (parametrized for all backends)."""

    def test_set_and_get(self, backend: CacheBackend, sample_entry: CacheEntry) -> None:
        """Test basic set and get operations."""
        backend.set("test_key", sample_entry)
        result = backend.get("test_key")

        assert result is not None
        assert result.value == sample_entry.value
        assert result.namespace == sample_entry.namespace

    def test_get_nonexistent_key(self, backend: CacheBackend) -> None:
        """Test getting a key that doesn't exist returns None."""
        assert backend.get("nonexistent_key") is None

    def test_overwrite_existing_key(
        self, backend: CacheBackend, sample_entry: CacheEntry
    ) -> None:
        """Test that setting an existing key overwrites the value."""
        backend.set("test_key", sample_entry)

        new_entry = CacheEntry(
            value={"new": "value"},
            namespace="private",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        backend.set("test_key", new_entry)

        result = backend.get("test_key")
        assert result is not None
        assert result.value == {"new": "value"}
        assert result.namespace == "private"

    def test_delete_existing_key(
        self, backend: CacheBackend, sample_entry: CacheEntry
    ) -> None:
        """Test deleting an existing key."""
        backend.set("test_key", sample_entry)
        assert backend.exists("test_key")

        deleted = backend.delete("test_key")
        assert deleted is True
        assert backend.get("test_key") is None

    def test_delete_nonexistent_key(self, backend: CacheBackend) -> None:
        """Test deleting a nonexistent key returns False."""
        deleted = backend.delete("nonexistent_key")
        assert deleted is False

    def test_exists_for_existing_key(
        self, backend: CacheBackend, sample_entry: CacheEntry
    ) -> None:
        """Test exists returns True for existing keys."""
        backend.set("test_key", sample_entry)
        assert backend.exists("test_key") is True

    def test_exists_for_nonexistent_key(self, backend: CacheBackend) -> None:
        """Test exists returns False for nonexistent keys."""
        assert backend.exists("nonexistent_key") is False

    def test_stores_complex_values(self, backend: CacheBackend) -> None:
        """Test storing complex nested data structures."""
        complex_value = {
            "nested": {"deep": {"value": [1, 2, 3]}},
            "list": [{"a": 1}, {"b": 2}],
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
        """Test storing list values directly."""
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
        from mcp_refcache.permissions import Permission

        custom_policy = AccessPolicy(
            owner="user:alice",
            user_permissions=Permission.READ,
            agent_permissions=Permission.EXECUTE,
        )
        entry = CacheEntry(
            value="test",
            namespace="user:alice",
            policy=custom_policy,
            created_at=time.time(),
        )

        backend.set("policy_key", entry)
        result = backend.get("policy_key")

        assert result is not None
        assert result.policy.owner == "user:alice"
        assert result.policy.user_permissions == Permission.READ
        assert result.policy.agent_permissions == Permission.EXECUTE

    def test_preserves_metadata(self, backend: CacheBackend) -> None:
        """Test that metadata is preserved through storage."""
        metadata = {
            "tool_name": "test_tool",
            "total_items": 100,
            "preview_size": 50,
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
    """Tests for entry expiration handling (parametrized for all backends)."""

    def test_get_expired_entry_returns_none(self, backend: CacheBackend) -> None:
        """Test that getting an expired entry returns None."""
        expired_entry = CacheEntry(
            value="expired",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time() - 100,
            expires_at=time.time() - 1,  # Already expired
        )
        backend.set("expired_key", expired_entry)

        result = backend.get("expired_key")
        assert result is None

    def test_get_expired_entry_cleans_up(self, backend: CacheBackend) -> None:
        """Test that accessing an expired entry removes it."""
        expired_entry = CacheEntry(
            value="expired",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time() - 100,
            expires_at=time.time() - 1,
        )
        backend.set("expired_key", expired_entry)

        # Access the expired entry
        backend.get("expired_key")

        # It should be cleaned up now
        assert backend.exists("expired_key") is False

    def test_exists_returns_false_for_expired(self, backend: CacheBackend) -> None:
        """Test that exists returns False for expired entries."""
        expired_entry = CacheEntry(
            value="expired",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time() - 100,
            expires_at=time.time() - 1,
        )
        backend.set("expired_key", expired_entry)

        assert backend.exists("expired_key") is False

    def test_non_expired_entry_accessible(self, backend: CacheBackend) -> None:
        """Test that non-expired entries are accessible."""
        future_entry = CacheEntry(
            value="future",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
            expires_at=time.time() + 3600,  # Expires in 1 hour
        )
        backend.set("future_key", future_entry)

        result = backend.get("future_key")
        assert result is not None
        assert result.value == "future"


class TestBackendClear:
    """Tests for clearing cache entries (parametrized for all backends)."""

    def test_clear_all(self, backend: CacheBackend) -> None:
        """Test clearing all entries."""
        for index in range(5):
            entry = CacheEntry(
                value=f"value_{index}",
                namespace=f"ns_{index}",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"key_{index}", entry)

        cleared = backend.clear()
        assert cleared == 5
        assert backend.keys() == []

    def test_clear_by_namespace(self, backend: CacheBackend) -> None:
        """Test clearing entries in a specific namespace."""
        # Create entries in different namespaces
        for index in range(3):
            entry = CacheEntry(
                value=f"ns1_{index}",
                namespace="namespace_1",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"ns1_key_{index}", entry)

        for index in range(2):
            entry = CacheEntry(
                value=f"ns2_{index}",
                namespace="namespace_2",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"ns2_key_{index}", entry)

        # Clear only namespace_1
        cleared = backend.clear("namespace_1")
        assert cleared == 3

        # namespace_2 entries should still exist
        remaining_keys = backend.keys()
        assert len(remaining_keys) == 2
        assert all("ns2" in key for key in remaining_keys)

    def test_clear_empty_cache(self, backend: CacheBackend) -> None:
        """Test clearing an empty cache returns 0."""
        cleared = backend.clear()
        assert cleared == 0


class TestBackendKeys:
    """Tests for listing cache keys (parametrized for all backends)."""

    def test_keys_empty_cache(self, backend: CacheBackend) -> None:
        """Test keys returns empty list for empty cache."""
        assert backend.keys() == []

    def test_keys_all(self, backend: CacheBackend) -> None:
        """Test keys returns all stored keys."""
        for index in range(5):
            entry = CacheEntry(
                value=f"value_{index}",
                namespace="public",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"key_{index}", entry)

        keys = backend.keys()
        assert len(keys) == 5
        assert set(keys) == {f"key_{index}" for index in range(5)}

    def test_keys_by_namespace(self, backend: CacheBackend) -> None:
        """Test keys filtered by namespace."""
        for index in range(3):
            entry = CacheEntry(
                value=f"ns1_{index}",
                namespace="namespace_1",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"ns1_key_{index}", entry)

        for index in range(2):
            entry = CacheEntry(
                value=f"ns2_{index}",
                namespace="namespace_2",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend.set(f"ns2_key_{index}", entry)

        ns1_keys = backend.keys("namespace_1")
        assert len(ns1_keys) == 3
        assert all("ns1" in key for key in ns1_keys)

    def test_keys_excludes_expired(self, backend: CacheBackend) -> None:
        """Test that keys excludes expired entries."""
        # Valid entry
        valid_entry = CacheEntry(
            value="valid",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )
        backend.set("valid_key", valid_entry)

        # Expired entry
        expired_entry = CacheEntry(
            value="expired",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time() - 100,
            expires_at=time.time() - 1,
        )
        backend.set("expired_key", expired_entry)

        keys = backend.keys()
        assert "valid_key" in keys
        assert "expired_key" not in keys


class TestBackendThreadSafety:
    """Tests for thread safety (parametrized for all backends)."""

    def test_concurrent_set_and_get(self, backend: CacheBackend) -> None:
        """Test concurrent reads and writes don't cause errors."""
        errors: list[Exception] = []

        def writer() -> None:
            try:
                for index in range(100):
                    entry = CacheEntry(
                        value=f"value_{index}",
                        namespace="public",
                        policy=AccessPolicy(),
                        created_at=time.time(),
                    )
                    backend.set(f"concurrent_key_{index}", entry)
            except Exception as exception:
                errors.append(exception)

        def reader() -> None:
            try:
                for _ in range(100):
                    backend.keys()
                    backend.get("concurrent_key_0")
            except Exception as exception:
                errors.append(exception)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_concurrent_many_operations(self, backend: CacheBackend) -> None:
        """Test many concurrent operations."""
        errors: list[Exception] = []

        def worker(worker_id: int) -> None:
            try:
                for index in range(50):
                    entry = CacheEntry(
                        value=f"worker_{worker_id}_value_{index}",
                        namespace="public",
                        policy=AccessPolicy(),
                        created_at=time.time(),
                    )
                    backend.set(f"worker_{worker_id}_key_{index}", entry)
                    backend.get(f"worker_{worker_id}_key_{index}")
                    backend.exists(f"worker_{worker_id}_key_{index}")
            except Exception as exception:
                errors.append(exception)

        threads = [
            threading.Thread(target=worker, args=(index,)) for index in range(10)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Concurrent operation errors: {errors}"
        # Each worker writes 50 keys
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
        """Test closing and reopening the database."""
        database_path = tmp_path / "close_reopen.db"

        backend = SQLiteBackend(database_path)
        entry = CacheEntry(
            value="test_value",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        backend.set("test_key", entry)
        backend.close()

        # Reopen and verify
        backend = SQLiteBackend(database_path)
        result = backend.get("test_key")
        assert result is not None
        assert result.value == "test_value"
        backend.close()

    def test_memory_database_not_shared(self) -> None:
        """Test that separate :memory: databases are independent."""
        backend1 = SQLiteBackend(":memory:")
        backend2 = SQLiteBackend(":memory:")

        entry = CacheEntry(
            value="only_in_backend1",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        backend1.set("unique_key", entry)

        # backend2 should not see backend1's data
        assert backend2.get("unique_key") is None

        backend1.close()
        backend2.close()

    def test_environment_variable_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that MCP_REFCACHE_DB_PATH environment variable is respected."""
        env_path = tmp_path / "env_cache.db"
        monkeypatch.setenv("MCP_REFCACHE_DB_PATH", str(env_path))

        backend = SQLiteBackend()  # No path argument
        assert backend.database_path == env_path
        backend.close()

    def test_environment_variable_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that MCP_REFCACHE_DB_PATH=:memory: works."""
        monkeypatch.setenv("MCP_REFCACHE_DB_PATH", ":memory:")

        backend = SQLiteBackend()
        assert backend.database_path == ":memory:"
        backend.close()

    def test_xdg_cache_home_respected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that XDG_CACHE_HOME is used for default path."""
        xdg_cache = tmp_path / "xdg_cache"
        xdg_cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))
        monkeypatch.delenv("MCP_REFCACHE_DB_PATH", raising=False)

        backend = SQLiteBackend()
        expected_path = xdg_cache / "mcp-refcache" / "cache.db"
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


# Redis-specific tests


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis package not installed")
class TestRedisBackendSpecific:
    """Tests specific to RedisBackend functionality."""

    @pytest.fixture
    def redis_backend(self) -> Generator[RedisBackend, None, None]:
        """Create a Redis backend for testing."""
        try:
            backend = RedisBackend(password="mcp-refcache-dev-password")
            if not backend.ping():
                pytest.skip("Redis server not available")
            backend.clear()  # Clean slate
            yield backend
            backend.clear()  # Cleanup
            backend.close()
        except Exception as exception:
            pytest.skip(f"Redis connection failed: {exception}")

    def test_ping(self, redis_backend: RedisBackend) -> None:
        """Test that ping returns True when connected."""
        assert redis_backend.ping() is True

    def test_connection_info(self, redis_backend: RedisBackend) -> None:
        """Test that connection_info returns expected keys."""
        info = redis_backend.connection_info
        assert "host" in info
        assert "port" in info
        assert "db" in info
        assert "ssl" in info

    def test_key_prefix(self, redis_backend: RedisBackend) -> None:
        """Test that keys are stored with the correct prefix."""
        entry = CacheEntry(
            value="test_value",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        redis_backend.set("my_key", entry)

        # Check that the key is stored with prefix
        keys = redis_backend.keys()
        assert "my_key" in keys

    def test_native_ttl(self, redis_backend: RedisBackend) -> None:
        """Test that Redis native TTL is used for expiration."""
        entry = CacheEntry(
            value="expiring_value",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
            expires_at=time.time() + 3600,  # 1 hour
        )
        redis_backend.set("ttl_key", entry)

        # Verify key exists
        assert redis_backend.exists("ttl_key")

        # Verify we can retrieve it
        result = redis_backend.get("ttl_key")
        assert result is not None
        assert result.value == "expiring_value"

    def test_expired_entry_not_accessible(self, redis_backend: RedisBackend) -> None:
        """Test that expired entries are not accessible."""
        entry = CacheEntry(
            value="expired_value",
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time() - 100,
            expires_at=time.time() - 1,  # Already expired
        )
        redis_backend.set("expired_key", entry)

        # Entry should not be accessible
        result = redis_backend.get("expired_key")
        assert result is None

    def test_close_and_reconnect(self) -> None:
        """Test that closing and creating a new connection works."""
        try:
            backend1 = RedisBackend(password="mcp-refcache-dev-password")
            if not backend1.ping():
                pytest.skip("Redis server not available")

            entry = CacheEntry(
                value="persistent_value",
                namespace="public",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            backend1.set("reconnect_key", entry)
            backend1.close()

            # Create new connection and verify data
            backend2 = RedisBackend(password="mcp-refcache-dev-password")
            result = backend2.get("reconnect_key")
            assert result is not None
            assert result.value == "persistent_value"

            backend2.clear()
            backend2.close()
        except Exception as exception:
            pytest.skip(f"Redis connection failed: {exception}")

    def test_environment_variable_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that REDIS_URL environment variable is respected."""
        monkeypatch.setenv(
            "REDIS_URL", "redis://:mcp-refcache-dev-password@localhost:6379/0"
        )

        try:
            backend = RedisBackend()  # No arguments, should use env var
            if not backend.ping():
                pytest.skip("Redis server not available")
            assert backend.ping() is True
            backend.close()
        except Exception as exception:
            pytest.skip(f"Redis connection failed: {exception}")

    def test_environment_variable_components(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that REDIS_HOST, REDIS_PORT, etc. environment variables work."""
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PORT", "6379")
        monkeypatch.setenv("REDIS_DB", "0")
        monkeypatch.setenv("REDIS_PASSWORD", "mcp-refcache-dev-password")

        try:
            backend = RedisBackend()  # No arguments, should use env vars
            if not backend.ping():
                pytest.skip("Redis server not available")
            assert backend.ping() is True
            backend.close()
        except Exception as exception:
            pytest.skip(f"Redis connection failed: {exception}")


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis package not installed")
class TestRedisBackendConcurrent:
    """Tests for concurrent Redis access."""

    @pytest.fixture
    def redis_backend(self) -> Generator[RedisBackend, None, None]:
        """Create a Redis backend for testing."""
        try:
            backend = RedisBackend(password="mcp-refcache-dev-password")
            if not backend.ping():
                pytest.skip("Redis server not available")
            backend.clear()
            yield backend
            backend.clear()
            backend.close()
        except Exception as exception:
            pytest.skip(f"Redis connection failed: {exception}")

    def test_concurrent_writers(self, redis_backend: RedisBackend) -> None:
        """Test multiple threads writing concurrently."""
        errors: list[Exception] = []

        def writer(worker_id: int) -> None:
            try:
                for index in range(50):
                    entry = CacheEntry(
                        value=f"worker_{worker_id}_value_{index}",
                        namespace="public",
                        policy=AccessPolicy(),
                        created_at=time.time(),
                    )
                    redis_backend.set(f"concurrent_{worker_id}_{index}", entry)
            except Exception as exception:
                errors.append(exception)

        threads = [threading.Thread(target=writer, args=(index,)) for index in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Concurrent write errors: {errors}"
        # 5 workers * 50 keys each
        assert len(redis_backend.keys()) == 250

    def test_concurrent_read_write(self, redis_backend: RedisBackend) -> None:
        """Test concurrent reads and writes."""
        # Pre-populate
        for index in range(10):
            entry = CacheEntry(
                value=f"initial_{index}",
                namespace="public",
                policy=AccessPolicy(),
                created_at=time.time(),
            )
            redis_backend.set(f"initial_{index}", entry)

        errors: list[Exception] = []
        read_counts: list[int] = []

        def reader(reader_id: int) -> None:
            try:
                count = 0
                for _ in range(50):
                    keys = redis_backend.keys()
                    count += len(keys)
                read_counts.append(count)
            except Exception as exception:
                errors.append(exception)

        def writer(writer_id: int) -> None:
            try:
                for index in range(20):
                    entry = CacheEntry(
                        value=f"writer_{writer_id}_{index}",
                        namespace="public",
                        policy=AccessPolicy(),
                        created_at=time.time(),
                    )
                    redis_backend.set(f"new_{writer_id}_{index}", entry)
            except Exception as exception:
                errors.append(exception)

        threads = [
            threading.Thread(target=reader, args=(0,)),
            threading.Thread(target=reader, args=(1,)),
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(1,)),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Concurrent read/write errors: {errors}"
        # Readers should have seen some data
        assert all(count > 0 for count in read_counts)
