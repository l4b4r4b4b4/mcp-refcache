"""Cache backend implementations.

This module provides the backend protocol and implementations for
storing cached values. The default backend is MemoryBackend.

Exports:
    CacheBackend: Protocol defining the backend interface.
    CacheEntry: Dataclass for internal storage format.
    MemoryBackend: Thread-safe in-memory backend implementation.
    SQLiteBackend: Persistent SQLite-based backend implementation.
"""

from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.backends.sqlite import SQLiteBackend

__all__ = [
    "CacheBackend",
    "CacheEntry",
    "MemoryBackend",
    "SQLiteBackend",
]
