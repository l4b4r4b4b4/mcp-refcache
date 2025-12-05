"""mcp-refcache: Reference-based caching for FastMCP servers.

This library provides context-aware caching with:
- Namespace isolation (public, session, user, custom)
- Access control (separate permissions for users and agents)
- Private computation (EXECUTE permission for blind compute)
- Context limiting (token/char-based with truncate/paginate/sample strategies)
"""

from mcp_refcache.models import (
    CacheReference,
    CacheResponse,
    PaginatedResponse,
    PreviewConfig,
)
from mcp_refcache.permissions import (
    AccessPolicy,
    Permission,
)

__version__ = "0.0.1"

__all__ = [
    "AccessPolicy",
    "CacheReference",
    "CacheResponse",
    "PaginatedResponse",
    "Permission",
    "PreviewConfig",
    "__version__",
]
