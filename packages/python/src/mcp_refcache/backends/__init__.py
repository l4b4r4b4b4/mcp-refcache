"""Cache and task backend implementations.

This module provides the backend protocols and implementations for
storing cached values and executing async tasks.

Cache Backends:
    CacheBackend: Protocol defining the cache storage interface.
    CacheEntry: Dataclass for internal storage format.
    MemoryBackend: Thread-safe in-memory cache implementation.
    SQLiteBackend: Persistent SQLite-based cache implementation.
    RedisBackend: Distributed Redis-based cache (requires redis package).

Task Backends:
    TaskBackend: Protocol defining the async task execution interface.
    MemoryTaskBackend: In-memory task execution using ThreadPoolExecutor.
"""

from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.backends.sqlite import SQLiteBackend
from mcp_refcache.backends.task_base import ProgressCallback, TaskBackend
from mcp_refcache.backends.task_memory import MemoryTaskBackend

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
    "MemoryTaskBackend",
    "ProgressCallback",
    "SQLiteBackend",
    "TaskBackend",
]

if _REDIS_AVAILABLE:
    __all__.append("RedisBackend")
