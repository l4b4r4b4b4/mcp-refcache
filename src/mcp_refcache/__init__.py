"""mcp-refcache: Reference-based caching for FastMCP servers.

This library provides context-aware caching with:
- Namespace isolation (public, session, user, custom)
- Access control (separate permissions for users and agents)
- Identity-aware actors (users, agents, system)
- Private computation (EXECUTE permission for blind compute)
- Context limiting (token/char-based with truncate/paginate/sample strategies)
- Context-scoped caching (dynamic namespace/owner from FastMCP context)
"""

from mcp_refcache.access.actor import (
    Actor,
    ActorLike,
    ActorType,
    DefaultActor,
    resolve_actor,
)
from mcp_refcache.access.checker import (
    DefaultPermissionChecker,
    PermissionChecker,
    PermissionDenied,
)
from mcp_refcache.access.namespace import (
    DefaultNamespaceResolver,
    NamespaceInfo,
    NamespaceResolver,
)
from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.backends.sqlite import SQLiteBackend
from mcp_refcache.cache import RefCache
from mcp_refcache.context import (
    CharacterFallback,
    CharacterMeasurer,
    HuggingFaceAdapter,
    SizeMeasurer,
    TiktokenAdapter,
    Tokenizer,
    TokenMeasurer,
    get_default_measurer,
    get_default_tokenizer,
)
from mcp_refcache.context_integration import (
    DEFAULT_FALLBACKS,
    build_context_scoped_policy,
    derive_actor_from_context,
    expand_template,
    get_context_values,
    try_get_fastmcp_context,
)
from mcp_refcache.models import (
    AsyncTaskResponse,
    CacheReference,
    CacheResponse,
    PaginatedResponse,
    PreviewConfig,
    PreviewStrategy,
    RetryInfo,
    SizeMode,
    TaskInfo,
    TaskProgress,
    TaskStatus,
)
from mcp_refcache.permissions import (
    POLICY_EXECUTE_ONLY,
    POLICY_PUBLIC,
    POLICY_READ_ONLY,
    POLICY_USER_ONLY,
    AccessPolicy,
    Permission,
)
from mcp_refcache.preview import (
    PaginateGenerator,
    PreviewGenerator,
    PreviewResult,
    SampleGenerator,
    TruncateGenerator,
    get_default_generator,
)
from mcp_refcache.resolution import (
    CircularReferenceError,
    RefResolver,
    ResolutionResult,
    is_ref_id,
    resolve_args_and_kwargs,
    resolve_kwargs,
    resolve_refs,
)

# RedisBackend is optional - only available if redis package is installed
try:
    from mcp_refcache.backends.redis import RedisBackend as RedisBackend

    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_FALLBACKS",
    "POLICY_EXECUTE_ONLY",
    "POLICY_PUBLIC",
    "POLICY_READ_ONLY",
    "POLICY_USER_ONLY",
    "AccessPolicy",
    "Actor",
    "ActorLike",
    "ActorType",
    "AsyncTaskResponse",
    "CacheBackend",
    "CacheEntry",
    "CacheReference",
    "CacheResponse",
    "CharacterFallback",
    "CharacterMeasurer",
    "CircularReferenceError",
    "DefaultActor",
    "DefaultNamespaceResolver",
    "DefaultPermissionChecker",
    "HuggingFaceAdapter",
    "MemoryBackend",
    "NamespaceInfo",
    "NamespaceResolver",
    "PaginateGenerator",
    "PaginatedResponse",
    "Permission",
    "PermissionChecker",
    "PermissionDenied",
    "PreviewConfig",
    "PreviewGenerator",
    "PreviewResult",
    "PreviewStrategy",
    "RefCache",
    "RefResolver",
    "ResolutionResult",
    "RetryInfo",
    "SQLiteBackend",
    "SampleGenerator",
    "SizeMeasurer",
    "SizeMode",
    "TaskInfo",
    "TaskProgress",
    "TaskStatus",
    "TiktokenAdapter",
    "TokenMeasurer",
    "Tokenizer",
    "TruncateGenerator",
    "__version__",
    "build_context_scoped_policy",
    "derive_actor_from_context",
    "expand_template",
    "get_context_values",
    "get_default_generator",
    "get_default_measurer",
    "get_default_tokenizer",
    "is_ref_id",
    "resolve_actor",
    "resolve_args_and_kwargs",
    "resolve_kwargs",
    "resolve_refs",
    "try_get_fastmcp_context",
]

if _REDIS_AVAILABLE:
    __all__.append("RedisBackend")
