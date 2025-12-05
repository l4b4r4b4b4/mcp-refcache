"""RefCache: Main cache interface for mcp-refcache.

Provides the primary API for caching values and managing references
with namespace isolation and permission-based access control.
"""

import functools
import hashlib
import inspect
import time
from collections.abc import Callable
from typing import Any, Literal, ParamSpec, TypeVar

from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.models import (
    CacheReference,
    CacheResponse,
    PreviewConfig,
    PreviewStrategy,
)
from mcp_refcache.permissions import AccessPolicy, Permission

# Type variables for decorator
P = ParamSpec("P")
R = TypeVar("R")


class RefCache:
    """Main cache interface for storing values and managing references.

    RefCache provides a reference-based caching system with:
    - Namespace isolation for multi-tenant scenarios
    - Separate permissions for users and agents
    - TTL-based expiration
    - Preview generation for large values
    - Decorator support for caching function results

    Example:
        ```python
        cache = RefCache(name="my-cache")

        # Store a value and get a reference
        ref = cache.set("user_data", {"name": "Alice", "items": [1, 2, 3]})

        # Get a preview of the value
        response = cache.get(ref.ref_id)
        print(response.preview)

        # Resolve to get the full value
        value = cache.resolve(ref.ref_id)
        ```
    """

    def __init__(
        self,
        name: str = "default",
        backend: CacheBackend | None = None,
        default_policy: AccessPolicy | None = None,
        default_ttl: float | None = 3600,
        preview_config: PreviewConfig | None = None,
    ) -> None:
        """Initialize the cache.

        Args:
            name: Name of this cache instance.
            backend: Storage backend. Defaults to MemoryBackend.
            default_policy: Default access policy for new entries.
            default_ttl: Default TTL in seconds. None means no expiration.
            preview_config: Configuration for preview generation.
        """
        self.name = name
        self._backend = backend if backend is not None else MemoryBackend()
        self.default_policy = (
            default_policy if default_policy is not None else AccessPolicy()
        )
        self.default_ttl = default_ttl
        self.preview_config = (
            preview_config if preview_config is not None else PreviewConfig()
        )

        # Mapping from key to ref_id for lookups
        self._key_to_ref: dict[str, str] = {}
        # Mapping from ref_id to key for reverse lookups
        self._ref_to_key: dict[str, str] = {}

    def set(
        self,
        key: str,
        value: Any,
        namespace: str = "public",
        policy: AccessPolicy | None = None,
        ttl: float | None = None,
        tool_name: str | None = None,
    ) -> CacheReference:
        """Store a value in the cache and return a reference.

        Args:
            key: Unique identifier for this value within the namespace.
            value: The value to cache. Should be JSON-serializable.
            namespace: Isolation namespace (default: "public").
            policy: Access control policy. Defaults to cache's default policy.
            ttl: Time-to-live in seconds. None uses cache default.
            tool_name: Name of the tool that created this reference.

        Returns:
            A CacheReference that can be used to retrieve the value.

        Example:
            ```python
            ref = cache.set("user_123", {"name": "Alice"})
            print(ref.ref_id)  # Use this to retrieve later
            ```
        """
        if policy is None:
            policy = self.default_policy

        effective_ttl = ttl if ttl is not None else self.default_ttl

        created_at = time.time()
        expires_at = created_at + effective_ttl if effective_ttl is not None else None

        # Generate a unique ref_id
        ref_id = self._generate_ref_id(key, namespace)

        # Calculate metadata
        total_items = self._count_items(value)
        total_size = self._estimate_size(value)

        metadata = {
            "tool_name": tool_name,
            "total_items": total_items,
            "total_size": total_size,
        }

        # Create the cache entry
        entry = CacheEntry(
            value=value,
            namespace=namespace,
            policy=policy,
            created_at=created_at,
            expires_at=expires_at,
            metadata=metadata,
        )

        # Store in backend using ref_id as the key
        self._backend.set(ref_id, entry)

        # Update mappings
        self._key_to_ref[self._make_namespaced_key(key, namespace)] = ref_id
        self._ref_to_key[ref_id] = key

        # Create and return the reference
        return CacheReference(
            ref_id=ref_id,
            cache_name=self.name,
            namespace=namespace,
            tool_name=tool_name,
            created_at=created_at,
            expires_at=expires_at,
            total_items=total_items,
            total_size=total_size,
        )

    def get(
        self,
        ref_id: str,
        *,
        page: int | None = None,
        page_size: int | None = None,
        actor: Literal["user", "agent"] = "agent",
    ) -> CacheResponse:
        """Get a preview of a cached value.

        Args:
            ref_id: Reference ID or key to look up.
            page: Page number for pagination (1-indexed).
            page_size: Number of items per page.
            actor: Who is requesting ("user" or "agent").

        Returns:
            A CacheResponse with preview and metadata.

        Raises:
            KeyError: If the reference is not found.
            PermissionError: If the actor lacks READ permission.

        Example:
            ```python
            response = cache.get(ref.ref_id)
            print(response.preview)  # Sampled preview
            print(response.total_items)  # Total count
            ```
        """
        entry = self._get_entry(ref_id)

        # Check permissions
        self._check_permission(entry.policy, Permission.READ, actor)

        # Generate preview
        preview, strategy = self._create_preview(
            entry.value,
            page=page,
            page_size=page_size,
        )

        # Calculate pagination info
        total_items = entry.metadata.get("total_items")
        total_pages = None
        if page is not None and page_size is not None and total_items is not None:
            total_pages = (
                (total_items + page_size - 1) // page_size if total_items > 0 else 0
            )

        return CacheResponse(
            ref_id=ref_id,
            cache_name=self.name,
            namespace=entry.namespace,
            total_items=total_items,
            preview=preview,
            preview_strategy=strategy,
            page=page,
            total_pages=total_pages,
        )

    def resolve(
        self,
        ref_id: str,
        *,
        actor: Literal["user", "agent"] = "agent",
    ) -> Any:
        """Resolve a reference to get the full cached value.

        Args:
            ref_id: Reference ID or key to look up.
            actor: Who is requesting ("user" or "agent").

        Returns:
            The full cached value.

        Raises:
            KeyError: If the reference is not found.
            PermissionError: If the actor lacks READ permission.

        Example:
            ```python
            value = cache.resolve(ref.ref_id)
            print(value)  # Full value
            ```
        """
        entry = self._get_entry(ref_id)

        # Check permissions
        self._check_permission(entry.policy, Permission.READ, actor)

        return entry.value

    def delete(
        self,
        ref_id: str,
        *,
        actor: Literal["user", "agent"] = "agent",
    ) -> bool:
        """Delete a cached entry.

        Args:
            ref_id: Reference ID or key to delete.
            actor: Who is requesting ("user" or "agent").

        Returns:
            True if deleted, False if not found.

        Raises:
            PermissionError: If the actor lacks DELETE permission.
        """
        # Try to get the entry to check permissions
        try:
            entry = self._get_entry(ref_id)
            self._check_permission(entry.policy, Permission.DELETE, actor)
        except KeyError:
            return False

        # Get the actual backend key
        backend_key = self._resolve_to_backend_key(ref_id)
        if backend_key is None:
            return False

        # Clean up mappings
        if backend_key in self._ref_to_key:
            original_key = self._ref_to_key[backend_key]
            namespaced_key = self._make_namespaced_key(original_key, entry.namespace)
            if namespaced_key in self._key_to_ref:
                del self._key_to_ref[namespaced_key]
            del self._ref_to_key[backend_key]

        return self._backend.delete(backend_key)

    def exists(self, ref_id: str) -> bool:
        """Check if a reference exists and is not expired.

        Args:
            ref_id: Reference ID or key to check.

        Returns:
            True if exists and not expired, False otherwise.
        """
        backend_key = self._resolve_to_backend_key(ref_id)
        if backend_key is None:
            return False
        return self._backend.exists(backend_key)

    def clear(self, namespace: str | None = None) -> int:
        """Clear entries from the cache.

        Args:
            namespace: If provided, only clear entries in this namespace.

        Returns:
            Number of entries cleared.
        """
        # Clear from backend
        cleared = self._backend.clear(namespace)

        # Clear mappings (simplified - clear all if namespace is None)
        if namespace is None:
            self._key_to_ref.clear()
            self._ref_to_key.clear()
        else:
            # Remove mappings for cleared keys
            keys_to_remove = []
            for namespaced_key, ref_id in self._key_to_ref.items():
                if namespaced_key.startswith(f"{namespace}:"):
                    keys_to_remove.append((namespaced_key, ref_id))

            for namespaced_key, ref_id in keys_to_remove:
                del self._key_to_ref[namespaced_key]
                if ref_id in self._ref_to_key:
                    del self._ref_to_key[ref_id]

        return cleared

    def cached(
        self,
        namespace: str = "public",
        policy: AccessPolicy | None = None,
        ttl: float | None = None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Decorator to cache function results.

        Args:
            namespace: Namespace for cached results.
            policy: Access policy for cached results.
            ttl: TTL for cached results.

        Returns:
            A decorator that caches function results.

        Example:
            ```python
            @cache.cached(namespace="session:abc")
            def expensive_computation(x: int) -> int:
                return x * 2

            result = expensive_computation(5)  # Computed
            result = expensive_computation(5)  # From cache
            ```
        """

        def decorator(func: Callable[P, R]) -> Callable[P, R]:
            is_async = inspect.iscoroutinefunction(func)

            if is_async:

                @functools.wraps(func)
                async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                    cache_key = self._make_cache_key(func, args, kwargs)

                    # Check if already cached
                    namespaced_key = self._make_namespaced_key(cache_key, namespace)
                    if namespaced_key in self._key_to_ref:
                        ref_id = self._key_to_ref[namespaced_key]
                        if self._backend.exists(ref_id):
                            entry = self._backend.get(ref_id)
                            if entry is not None:
                                return entry.value

                    # Execute and cache
                    result = await func(*args, **kwargs)
                    self.set(
                        cache_key,
                        result,
                        namespace=namespace,
                        policy=policy,
                        ttl=ttl,
                        tool_name=func.__name__,
                    )
                    return result

                return async_wrapper  # type: ignore
            else:

                @functools.wraps(func)
                def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                    cache_key = self._make_cache_key(func, args, kwargs)

                    # Check if already cached
                    namespaced_key = self._make_namespaced_key(cache_key, namespace)
                    if namespaced_key in self._key_to_ref:
                        ref_id = self._key_to_ref[namespaced_key]
                        if self._backend.exists(ref_id):
                            entry = self._backend.get(ref_id)
                            if entry is not None:
                                return entry.value

                    # Execute and cache
                    result = func(*args, **kwargs)
                    self.set(
                        cache_key,
                        result,
                        namespace=namespace,
                        policy=policy,
                        ttl=ttl,
                        tool_name=func.__name__,
                    )
                    return result

                return sync_wrapper  # type: ignore

        return decorator

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _generate_ref_id(self, key: str, namespace: str) -> str:
        """Generate a unique reference ID."""
        composite = f"{self.name}:{namespace}:{key}:{time.time()}"
        hash_value = hashlib.sha256(composite.encode()).hexdigest()[:16]
        return f"{self.name}:{hash_value}"

    def _make_namespaced_key(self, key: str, namespace: str) -> str:
        """Create a namespaced key for internal lookups."""
        return f"{namespace}:{key}"

    def _make_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """Create a cache key from function and arguments."""
        # Create a deterministic key from function name and arguments
        key_parts = [func.__module__, func.__qualname__]

        for arg in args:
            key_parts.append(repr(arg))

        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v!r}")

        composite = ":".join(key_parts)
        return hashlib.sha256(composite.encode()).hexdigest()[:32]

    def _resolve_to_backend_key(self, ref_id: str) -> str | None:
        """Resolve a ref_id or key to the backend storage key."""
        # Direct ref_id lookup
        if self._backend.exists(ref_id):
            return ref_id

        # Try as a key in each namespace
        for namespaced_key, stored_ref_id in self._key_to_ref.items():
            # Check if ref_id matches the key part and entry exists
            if namespaced_key.endswith(f":{ref_id}") and self._backend.exists(
                stored_ref_id
            ):
                return stored_ref_id

        return None

    def _get_entry(self, ref_id: str) -> CacheEntry:
        """Get a cache entry by ref_id or key."""
        backend_key = self._resolve_to_backend_key(ref_id)
        if backend_key is None:
            raise KeyError(f"Reference '{ref_id}' not found")

        entry = self._backend.get(backend_key)
        if entry is None:
            raise KeyError(f"Reference '{ref_id}' not found or expired")

        return entry

    def _check_permission(
        self,
        policy: AccessPolicy,
        required: Permission,
        actor: Literal["user", "agent"],
    ) -> None:
        """Check if an actor has the required permission."""
        if actor == "user":
            if not policy.user_can(required):
                raise PermissionError(
                    f"User lacks {required.name} permission for this reference"
                )
        else:
            if not policy.agent_can(required):
                raise PermissionError(
                    f"Agent lacks {required.name} permission for this reference"
                )

    def _count_items(self, value: Any) -> int | None:
        """Count items in a collection."""
        if isinstance(value, (list, tuple, set, frozenset)):
            return len(value)
        if isinstance(value, dict):
            return len(value)
        return None

    def _estimate_size(self, value: Any) -> int | None:
        """Estimate size of a value in bytes."""
        try:
            import json

            return len(json.dumps(value, default=str).encode())
        except Exception:
            return None

    def _create_preview(
        self,
        value: Any,
        page: int | None = None,
        page_size: int | None = None,
    ) -> tuple[Any, PreviewStrategy]:
        """Create a preview of a value.

        Returns a tuple of (preview, strategy).
        """
        max_items = self.preview_config.max_size

        # Handle pagination
        if page is not None and page_size is not None:
            if isinstance(value, (list, tuple)):
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                return list(value)[start_idx:end_idx], PreviewStrategy.PAGINATE
            elif isinstance(value, dict):
                keys = list(value.keys())
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                page_keys = keys[start_idx:end_idx]
                return {k: value[k] for k in page_keys}, PreviewStrategy.PAGINATE

        # Sample strategy for large collections
        if isinstance(value, (list, tuple)):
            if len(value) <= max_items:
                return list(value), PreviewStrategy.SAMPLE
            # Sample evenly spaced items
            step = len(value) / max_items
            sampled = [value[int(i * step)] for i in range(max_items)]
            return sampled, PreviewStrategy.SAMPLE

        elif isinstance(value, dict):
            if len(value) <= max_items:
                return dict(value), PreviewStrategy.SAMPLE
            # Sample evenly spaced keys
            keys = list(value.keys())
            step = len(keys) / max_items
            sampled_keys = [keys[int(i * step)] for i in range(max_items)]
            return {k: value[k] for k in sampled_keys}, PreviewStrategy.SAMPLE

        elif isinstance(value, str):
            if len(value) <= max_items:
                return value, PreviewStrategy.TRUNCATE
            return value[:max_items] + "...", PreviewStrategy.TRUNCATE

        # For other types, return as-is
        return value, PreviewStrategy.SAMPLE
