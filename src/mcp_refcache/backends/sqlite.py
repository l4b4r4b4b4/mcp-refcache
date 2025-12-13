"""SQLite cache backend implementation.

Provides a persistent, file-based storage backend with support for
concurrent access from multiple processes. This enables cross-tool
reference sharing when multiple MCP servers share the same database.
"""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from mcp_refcache.backends.base import CacheEntry
from mcp_refcache.permissions import AccessPolicy


class SQLiteBackend:
    """SQLite-based persistent cache backend.

    Uses SQLite with WAL mode for concurrent access. Supports sharing
    cached references across multiple MCP servers on the same machine.

    Features:
        - Persistent storage survives process restarts
        - Cross-process sharing via file-based database
        - WAL mode for concurrent readers + one writer
        - Thread-safe with thread-local connections
        - Lazy expiration cleanup on read

    Example:
        ```python
        # Use default location (~/.cache/mcp-refcache/cache.db)
        backend = SQLiteBackend()

        # Or specify custom path
        backend = SQLiteBackend("/path/to/cache.db")

        # For testing (in-memory, no file)
        backend = SQLiteBackend(":memory:")

        entry = CacheEntry(
            value={"data": "example"},
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        backend.set("my_key", entry)
        result = backend.get("my_key")
        ```
    """

    # SQL statements
    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS cache_entries (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            namespace TEXT NOT NULL,
            policy_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL,
            metadata_json TEXT NOT NULL
        )
    """

    _CREATE_NAMESPACE_INDEX_SQL = """
        CREATE INDEX IF NOT EXISTS idx_namespace
        ON cache_entries(namespace)
    """

    _CREATE_EXPIRES_INDEX_SQL = """
        CREATE INDEX IF NOT EXISTS idx_expires_at
        ON cache_entries(expires_at)
    """

    def __init__(self, database_path: Path | str | None = None) -> None:
        """Initialize the SQLite backend.

        Args:
            database_path: Path to the SQLite database file.
                - None: Use default (~/.cache/mcp-refcache/cache.db)
                - ":memory:": Use in-memory database (for testing)
                - Path/str: Use specified file path
        """
        self._database_path = self._resolve_path(database_path)
        self._is_memory = str(self._database_path) == ":memory:"
        self._local = threading.local()
        self._lock = threading.RLock()

        # For :memory: databases, we need a shared connection
        # because each connection to :memory: creates a separate database
        if self._is_memory:
            self._shared_connection: sqlite3.Connection | None = (
                self._create_connection()
            )
            self._initialize_database(self._shared_connection)
        else:
            self._shared_connection = None
            self._ensure_directory()
            self._initialize_database(self._get_connection())

    def _resolve_path(self, path: Path | str | None) -> Path | str:
        """Resolve database path with sensible defaults.

        Args:
            path: User-provided path or None for default.

        Returns:
            Resolved path as Path object, or ":memory:" string.
        """
        if path is not None:
            if str(path) == ":memory:":
                return ":memory:"
            return Path(path)

        # Check environment variable
        env_path = os.environ.get("MCP_REFCACHE_DB_PATH")
        if env_path:
            if env_path == ":memory:":
                return ":memory:"
            return Path(env_path)

        # XDG-compliant default
        cache_home = os.environ.get("XDG_CACHE_HOME")
        base_path = Path(cache_home) if cache_home else Path.home() / ".cache"

        return base_path / "mcp-refcache" / "cache.db"

    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        if not self._is_memory and isinstance(self._database_path, Path):
            self._database_path.parent.mkdir(parents=True, exist_ok=True)

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with proper settings."""
        connection = sqlite3.connect(
            str(self._database_path),
            check_same_thread=False,
            timeout=30.0,  # Wait up to 30 seconds for locks
        )
        connection.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent access (file-based only)
        if not self._is_memory:
            connection.execute("PRAGMA journal_mode=WAL")

        # Enable foreign keys and other optimizations
        connection.execute("PRAGMA foreign_keys=ON")

        return connection

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection.

        For :memory: databases, returns the shared connection.
        For file-based databases, returns a thread-local connection.

        Returns:
            SQLite connection for the current thread.
        """
        if self._is_memory:
            assert self._shared_connection is not None
            return self._shared_connection

        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = self._create_connection()

        return self._local.connection

    def _initialize_database(self, connection: sqlite3.Connection) -> None:
        """Create tables and indexes if they don't exist.

        Args:
            connection: Database connection to use for initialization.
        """
        with self._lock:
            cursor = connection.cursor()
            cursor.execute(self._CREATE_TABLE_SQL)
            cursor.execute(self._CREATE_NAMESPACE_INDEX_SQL)
            cursor.execute(self._CREATE_EXPIRES_INDEX_SQL)
            connection.commit()

    def _serialize_entry(self, entry: CacheEntry) -> dict[str, Any]:
        """Convert CacheEntry to storable dict.

        Args:
            entry: The CacheEntry to serialize.

        Returns:
            Dictionary with JSON-serialized fields.
        """
        return {
            "value_json": json.dumps(entry.value, default=str),
            "namespace": entry.namespace,
            # Use mode='json' to convert Permission enums to integers
            "policy_json": json.dumps(entry.policy.model_dump(mode="json")),
            "created_at": entry.created_at,
            "expires_at": entry.expires_at,
            "metadata_json": json.dumps(entry.metadata, default=str),
        }

    def _deserialize_entry(self, row: sqlite3.Row) -> CacheEntry:
        """Convert database row to CacheEntry.

        Args:
            row: SQLite row with cache entry data.

        Returns:
            Reconstructed CacheEntry object.
        """
        return CacheEntry(
            value=json.loads(row["value_json"]),
            namespace=row["namespace"],
            policy=AccessPolicy(**json.loads(row["policy_json"])),
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve an entry by key.

        If the entry exists but is expired, it will be deleted and None returned.

        Args:
            key: The cache key to look up.

        Returns:
            The CacheEntry if found and not expired, None otherwise.
        """
        connection = self._get_connection()
        current_time = time.time()

        with self._lock:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT * FROM cache_entries WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            entry = self._deserialize_entry(row)

            # Check expiration and clean up if expired
            if entry.is_expired(current_time):
                cursor.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                connection.commit()
                return None

            return entry

    def set(self, key: str, entry: CacheEntry) -> None:
        """Store an entry.

        Args:
            key: The cache key to store under.
            entry: The CacheEntry to store.
        """
        connection = self._get_connection()
        serialized = self._serialize_entry(entry)

        with self._lock:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (key, value_json, namespace, policy_json, created_at, expires_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    serialized["value_json"],
                    serialized["namespace"],
                    serialized["policy_json"],
                    serialized["created_at"],
                    serialized["expires_at"],
                    serialized["metadata_json"],
                ),
            )
            connection.commit()

    def delete(self, key: str) -> bool:
        """Delete an entry by key.

        Args:
            key: The cache key to delete.

        Returns:
            True if the entry was deleted, False if it didn't exist.
        """
        connection = self._get_connection()

        with self._lock:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            connection.commit()
            return cursor.rowcount > 0

    def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired.

        Args:
            key: The cache key to check.

        Returns:
            True if the key exists and is not expired, False otherwise.
        """
        connection = self._get_connection()
        current_time = time.time()

        with self._lock:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT expires_at FROM cache_entries WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()

            if row is None:
                return False

            expires_at = row["expires_at"]

            # Check expiration
            if expires_at is not None and current_time >= expires_at:
                # Clean up expired entry
                cursor.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                connection.commit()
                return False

            return True

    def clear(self, namespace: str | None = None) -> int:
        """Clear entries from the cache.

        Args:
            namespace: If provided, only clear entries in this namespace.
                      If None, clear all entries.

        Returns:
            The number of entries that were cleared.
        """
        connection = self._get_connection()

        with self._lock:
            cursor = connection.cursor()

            if namespace is None:
                cursor.execute("DELETE FROM cache_entries")
            else:
                cursor.execute(
                    "DELETE FROM cache_entries WHERE namespace = ?",
                    (namespace,),
                )

            connection.commit()
            return cursor.rowcount

    def keys(self, namespace: str | None = None) -> list[str]:
        """List all keys in the cache.

        Expired entries are excluded from the result and cleaned up.

        Args:
            namespace: If provided, only return keys in this namespace.
                      If None, return all keys.

        Returns:
            List of cache keys.
        """
        connection = self._get_connection()
        current_time = time.time()

        with self._lock:
            cursor = connection.cursor()

            # First, clean up expired entries
            cursor.execute(
                "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (current_time,),
            )
            connection.commit()

            # Then fetch keys
            if namespace is None:
                cursor.execute("SELECT key FROM cache_entries")
            else:
                cursor.execute(
                    "SELECT key FROM cache_entries WHERE namespace = ?",
                    (namespace,),
                )

            return [row["key"] for row in cursor.fetchall()]

    def close(self) -> None:
        """Close all database connections.

        This should be called when the backend is no longer needed.
        """
        with self._lock:
            if self._is_memory and self._shared_connection is not None:
                self._shared_connection.close()
                self._shared_connection = None

            if (
                hasattr(self._local, "connection")
                and self._local.connection is not None
            ):
                self._local.connection.close()
                self._local.connection = None

    @property
    def database_path(self) -> Path | str:
        """Get the database path.

        Returns:
            The path to the database file, or ":memory:" for in-memory databases.
        """
        return self._database_path
