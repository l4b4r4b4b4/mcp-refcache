"""Cache backend implementations.

This module provides the backend protocol and implementations for
storing cached values. The default backend is MemoryBackend.

Exports:
    CacheBackend: Protocol defining the backend interface.
    CacheEntry: Dataclass for internal storage format.
    MemoryBackend: Thread-safe in-memory backend implementation.
    SQLiteBackend: Persistent SQLite-based backend implementation.
    RedisBackend: Distributed Redis-based backend (requires redis package).
"""

from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.backends.sqlite import SQLiteBackend

# RedisBackend is optional - only available if redis package is installed
try:
    from mcp_refcache.backends.redis import RedisBackend as RedisBackend

    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

__all__ = [
    "CacheBackend",
    "CacheEntry",
    "MemoryBackend",
    "SQLiteBackend",
]

if _REDIS_AVAILABLE:
    __all__.append("RedisBackend")
