"""In-memory cache backend implementation.

Provides a thread-safe, dictionary-based storage backend with TTL support.
This is the default backend for RefCache when no other backend is specified.
"""

import threading
import time

from mcp_refcache.backends.base import CacheEntry


class MemoryBackend:
    """Thread-safe in-memory cache backend.

    Uses a dictionary for storage and an RLock for thread safety.
    Expired entries are cleaned up lazily on access.

    Example:
        ```python
        backend = MemoryBackend()
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

    def __init__(self) -> None:
        """Initialize the memory backend with empty storage."""
        self._storage: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve an entry by key.

        If the entry exists but is expired, it will be deleted and None returned.

        Args:
            key: The cache key to look up.

        Returns:
            The CacheEntry if found and not expired, None otherwise.
        """
        with self._lock:
            entry = self._storage.get(key)
            if entry is None:
                return None

            if entry.is_expired(time.time()):
                del self._storage[key]
                return None

            return entry

    def set(self, key: str, entry: CacheEntry) -> None:
        """Store an entry.

        Args:
            key: The cache key to store under.
            entry: The CacheEntry to store.
        """
        with self._lock:
            self._storage[key] = entry

    def delete(self, key: str) -> bool:
        """Delete an entry by key.

        Args:
            key: The cache key to delete.

        Returns:
            True if the entry was deleted, False if it didn't exist.
        """
        with self._lock:
            if key in self._storage:
                del self._storage[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired.

        Args:
            key: The cache key to check.

        Returns:
            True if the key exists and is not expired, False otherwise.
        """
        with self._lock:
            entry = self._storage.get(key)
            if entry is None:
                return False

            if entry.is_expired(time.time()):
                del self._storage[key]
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
        with self._lock:
            if namespace is None:
                count = len(self._storage)
                self._storage.clear()
                return count

            keys_to_delete = [
                key
                for key, entry in self._storage.items()
                if entry.namespace == namespace
            ]
            for key in keys_to_delete:
                del self._storage[key]
            return len(keys_to_delete)

    def keys(self, namespace: str | None = None) -> list[str]:
        """List all keys in the cache.

        Expired entries are excluded from the result but not automatically
        cleaned up (to avoid modifying storage during iteration).

        Args:
            namespace: If provided, only return keys in this namespace.
                      If None, return all keys.

        Returns:
            List of cache keys.
        """
        current_time = time.time()
        with self._lock:
            result = []
            expired_keys = []

            for key, entry in self._storage.items():
                if entry.is_expired(current_time):
                    expired_keys.append(key)
                elif namespace is None or entry.namespace == namespace:
                    result.append(key)

            # Clean up expired entries
            for key in expired_keys:
                del self._storage[key]

            return result
