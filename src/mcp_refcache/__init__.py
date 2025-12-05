"""mcp-refcache: Reference-based caching for FastMCP servers.

This library provides context-aware caching with:
- Namespace isolation (public, session, user, custom)
- Access control (separate permissions for users and agents)
- Private computation (EXECUTE permission for blind compute)
- Context limiting (token/char-based with truncate/paginate/sample strategies)
"""

from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.cache import RefCache
from mcp_refcache.models import (
    CacheReference,
    CacheResponse,
    PaginatedResponse,
    PreviewConfig,
    PreviewStrategy,
    SizeMode,
)
from mcp_refcache.permissions import (
    POLICY_EXECUTE_ONLY,
    POLICY_PUBLIC,
    POLICY_READ_ONLY,
    POLICY_USER_ONLY,
    AccessPolicy,
    Permission,
)

__version__ = "0.0.1"

__all__ = [
    "POLICY_EXECUTE_ONLY",
    "POLICY_PUBLIC",
    "POLICY_READ_ONLY",
    "POLICY_USER_ONLY",
    "AccessPolicy",
    "CacheBackend",
    "CacheEntry",
    "CacheReference",
    "CacheResponse",
    "MemoryBackend",
    "PaginatedResponse",
    "Permission",
    "PreviewConfig",
    "PreviewStrategy",
    "RefCache",
    "SizeMode",
    "__version__",
]
