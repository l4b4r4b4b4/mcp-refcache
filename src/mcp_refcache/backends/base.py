"""Base types for cache backends.

Defines the CacheEntry dataclass for internal storage and the
CacheBackend protocol that all storage implementations must follow.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from mcp_refcache.permissions import AccessPolicy


@dataclass
class CacheEntry:
    """Internal storage format for cached values.

    This is what backends store. It contains the value plus all
    metadata needed for access control, expiration, and retrieval.

    Attributes:
        value: The cached value (any JSON-serializable data).
        namespace: Isolation namespace for this entry.
        policy: Access control policy for users and agents.
        created_at: Unix timestamp when the entry was created.
        expires_at: Unix timestamp when the entry expires (None = never).
        metadata: Additional metadata (tool_name, total_items, etc.).
    """

    value: Any
    namespace: str
    policy: AccessPolicy
    created_at: float
    expires_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, current_time: float) -> bool:
        """Check if this entry has expired.

        Args:
            current_time: Current Unix timestamp to compare against.

        Returns:
            True if the entry has expired, False otherwise.
        """
        if self.expires_at is None:
            return False
        return current_time >= self.expires_at


@runtime_checkable
class CacheBackend(Protocol):
    """Protocol defining the interface for cache storage backends.

    All cache backends (memory, Redis, etc.) must implement this interface.
    The protocol uses duck typing - any class with these methods will work.

    Example:
        ```python
        class MyBackend:
            def get(self, key: str) -> CacheEntry | None:
                # Implementation
                ...

            # ... implement other methods

        # Works because it has all required methods
        backend: CacheBackend = MyBackend()
        ```
    """

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve an entry by key.

        Args:
            key: The cache key to look up.

        Returns:
            The CacheEntry if found and not expired, None otherwise.
        """
        ...

    def set(self, key: str, entry: CacheEntry) -> None:
        """Store an entry.

        Args:
            key: The cache key to store under.
            entry: The CacheEntry to store.
        """
        ...

    def delete(self, key: str) -> bool:
        """Delete an entry by key.

        Args:
            key: The cache key to delete.

        Returns:
            True if the entry was deleted, False if it didn't exist.
        """
        ...

    def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired.

        Args:
            key: The cache key to check.

        Returns:
            True if the key exists and is not expired, False otherwise.
        """
        ...

    def clear(self, namespace: str | None = None) -> int:
        """Clear entries from the cache.

        Args:
            namespace: If provided, only clear entries in this namespace.
                      If None, clear all entries.

        Returns:
            The number of entries that were cleared.
        """
        ...

    def keys(self, namespace: str | None = None) -> list[str]:
        """List all keys in the cache.

        Args:
            namespace: If provided, only return keys in this namespace.
                      If None, return all keys.

        Returns:
            List of cache keys.
        """
        ...
