"""RefCache: Main cache interface for mcp-refcache.

Provides the primary API for caching values and managing references
with namespace isolation and permission-based access control.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
import time
from collections.abc import Callable  # noqa: TC003 - used at runtime in type hints
from typing import Any, ParamSpec, TypeVar

from mcp_refcache.access.actor import ActorLike, resolve_actor
from mcp_refcache.access.checker import (
    DefaultPermissionChecker,
    PermissionChecker,
)
from mcp_refcache.backends.base import CacheBackend, CacheEntry
from mcp_refcache.backends.memory import MemoryBackend
from mcp_refcache.context import (
    SizeMeasurer,
    TiktokenAdapter,
    Tokenizer,
    TokenMeasurer,
    get_default_measurer,
)
from mcp_refcache.models import (
    CacheReference,
    CacheResponse,
    PreviewConfig,
)
from mcp_refcache.permissions import AccessPolicy, Permission
from mcp_refcache.preview import (
    PaginateGenerator,
    PreviewGenerator,
    PreviewResult,
    SampleGenerator,
    get_default_generator,
)
from mcp_refcache.resolution import resolve_args_and_kwargs

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
        tokenizer: Tokenizer | None = None,
        measurer: SizeMeasurer | None = None,
        preview_generator: PreviewGenerator | None = None,
        permission_checker: PermissionChecker | None = None,
    ) -> None:
        """Initialize the cache.

        Args:
            name: Name of this cache instance.
            backend: Storage backend. Defaults to MemoryBackend.
            default_policy: Default access policy for new entries.
            default_ttl: Default TTL in seconds. None means no expiration.
            preview_config: Configuration for preview generation.
            tokenizer: Tokenizer for token counting. If provided without measurer,
                a TokenMeasurer is created automatically.
            measurer: Size measurer for preview generation. Takes precedence over
                tokenizer if both are provided.
            preview_generator: Generator for creating previews. Defaults to
                generator matching preview_config.default_strategy.
            permission_checker: Permission checker for access control. Defaults to
                DefaultPermissionChecker which enforces namespace ownership rules.

        Example:
            ```python
            # Simple usage with tiktoken
            cache = RefCache(tokenizer=TiktokenAdapter("gpt-4o"))

            # Advanced usage with custom measurer and generator
            cache = RefCache(
                measurer=TokenMeasurer(TiktokenAdapter("gpt-4o")),
                preview_generator=SampleGenerator(),
            )

            # Custom permission checker with namespace resolver
            from mcp_refcache import DefaultPermissionChecker, DefaultNamespaceResolver
            checker = DefaultPermissionChecker(namespace_resolver=DefaultNamespaceResolver())
            cache = RefCache(permission_checker=checker)
            ```
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

        # Store tokenizer for reference
        self._tokenizer = tokenizer

        # Determine measurer: explicit > from tokenizer > from config
        if measurer is not None:
            self._measurer = measurer
        elif tokenizer is not None:
            self._measurer = TokenMeasurer(tokenizer)
        else:
            # Default: use TOKEN mode with TiktokenAdapter (falls back to CharacterFallback)
            self._measurer = get_default_measurer(
                self.preview_config.size_mode,
                tokenizer=TiktokenAdapter(),
            )

        # Determine preview generator: explicit > from config
        if preview_generator is not None:
            self._preview_generator = preview_generator
        else:
            self._preview_generator = get_default_generator(
                self.preview_config.default_strategy
            )

        # Permission checker for access control
        self._permission_checker: PermissionChecker = (
            permission_checker
            if permission_checker is not None
            else DefaultPermissionChecker()
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
        max_size: int | None = None,
        actor: ActorLike = "agent",
    ) -> CacheResponse:
        """Get a preview of a cached value.

        Args:
            ref_id: Reference ID or key to look up.
            page: Page number for pagination (1-indexed).
            page_size: Number of items per page.
            max_size: Maximum preview size (tokens/chars). Overrides server default.
                Use smaller values for quick summaries, larger for more context.
            actor: Who is requesting. Can be an Actor object or literal "user"/"agent".

        Returns:
            A CacheResponse with preview and metadata.

        Raises:
            KeyError: If the reference is not found.
            PermissionDenied: If the actor lacks READ permission or namespace access.

        Example:
            ```python
            response = cache.get(ref.ref_id)
            print(response.preview)  # Sampled preview
            print(response.total_items)  # Total count

            # With Actor object
            from mcp_refcache import DefaultActor
            actor = DefaultActor.user(id="alice")
            response = cache.get(ref.ref_id, actor=actor)
            ```
        """
        entry = self._get_entry(ref_id)

        # Check permissions
        self._check_permission(entry.policy, Permission.READ, actor, entry.namespace)

        # Generate preview using the new PreviewResult system
        preview_result = self._create_preview(
            entry.value,
            page=page,
            page_size=page_size,
            max_size=max_size,
        )

        return CacheResponse(
            ref_id=ref_id,
            cache_name=self.name,
            namespace=entry.namespace,
            total_items=preview_result.total_items,
            original_size=preview_result.original_size,
            preview_size=preview_result.preview_size,
            preview=preview_result.preview,
            preview_strategy=preview_result.strategy,
            page=preview_result.page,
            total_pages=preview_result.total_pages,
        )

    def resolve(
        self,
        ref_id: str,
        *,
        actor: ActorLike = "agent",
    ) -> Any:
        """Resolve a reference to get the full cached value.

        Args:
            ref_id: Reference ID or key to look up.
            actor: Who is requesting. Can be an Actor object or literal "user"/"agent".

        Returns:
            The full cached value.

        Raises:
            KeyError: If the reference is not found.
            PermissionDenied: If the actor lacks READ permission or namespace access.

        Example:
            ```python
            value = cache.resolve(ref.ref_id)
            print(value)  # Full value

            # With Actor object
            from mcp_refcache import DefaultActor
            actor = DefaultActor.user(id="alice")
            value = cache.resolve(ref.ref_id, actor=actor)
            ```
        """
        entry = self._get_entry(ref_id)

        # Check permissions
        self._check_permission(entry.policy, Permission.READ, actor, entry.namespace)

        return entry.value

    def delete(
        self,
        ref_id: str,
        *,
        actor: ActorLike = "agent",
    ) -> bool:
        """Delete a cached entry.

        Args:
            ref_id: Reference ID or key to delete.
            actor: Who is requesting. Can be an Actor object or literal "user"/"agent".

        Returns:
            True if deleted, False if not found.

        Raises:
            PermissionDenied: If the actor lacks DELETE permission or namespace access.
        """
        # Try to get the entry to check permissions
        try:
            entry = self._get_entry(ref_id)
            self._check_permission(
                entry.policy, Permission.DELETE, actor, entry.namespace
            )
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
        max_size: int | None = None,
        resolve_refs: bool = True,
        actor: str = "agent",
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Decorator to cache function results and return structured responses.

        This decorator provides full MCP tool integration:
        1. **Pre-execution**: Resolves any ref_ids in inputs (deep recursive)
        2. **Post-execution**: Caches result and returns structured response

        The response is ALWAYS a structured dict containing:
        - Small results: Full value + ref_id + metadata (is_complete=True)
        - Large results: Preview + ref_id + pagination info (is_complete=False)

        Args:
            namespace: Namespace for cached results.
            policy: Access policy for cached results.
            ttl: TTL for cached results.
            max_size: Maximum size (tokens/chars) before auto-preview.
                If None, uses cache's preview_config.max_size.
            resolve_refs: If True (default), resolve ref_ids in inputs before
                executing the function. Any parameter value matching the ref_id
                pattern will be hot-swapped with the cached value.
            actor: Actor identity for permission checks when resolving refs.

        Returns:
            A decorator that wraps functions with caching and structured responses.

        Example:
            ```python
            @mcp.tool
            @cache.cached(namespace="data")
            def generate_data(size: int) -> list[int]:
                return list(range(size))

            # Small result - returns full value:
            # {"ref_id": "...", "value": [0, 1, 2], "is_complete": True, ...}

            # Large result - returns preview:
            # {"ref_id": "...", "preview": [0, 50, 100, ...], "is_complete": False, ...}

            # Ref_id resolution - agent can pass refs from previous tools:
            @mcp.tool
            @cache.cached(namespace="results")
            def process_data(data: list[int], factor: float) -> list[float]:
                return [x * factor for x in data]

            # Agent calls: process_data(data="myapp:abc123", factor=2.0)
            # Decorator resolves "myapp:abc123" to actual list before execution
            ```
        """
        effective_max_size = max_size or self.preview_config.max_size

        def decorator(func: Callable[P, R]) -> Callable[P, dict[str, Any]]:
            is_async = inspect.iscoroutinefunction(func)

            # Inject cache documentation into docstring
            original_doc = func.__doc__ or ""

            # Build max_size documentation
            if max_size is not None:
                max_size_doc = f"max_size={max_size} tokens"
            else:
                max_size_doc = "server default"

            cache_doc = f"""

**Caching Behavior:**
- Any input parameter can accept a ref_id from a previous tool call
- Large results return ref_id + preview; use get_cached_result to paginate
- All responses include ref_id for future reference

**Preview Size:** {max_size_doc}. Override per-call with `get_cached_result(ref_id, max_size=...)`."""
            func.__doc__ = original_doc + cache_doc

            def _resolve_inputs(
                args: tuple[Any, ...], kwargs: dict[str, Any]
            ) -> tuple[tuple[Any, ...], dict[str, Any]]:
                """Resolve any ref_ids in args and kwargs."""
                if not resolve_refs:
                    return args, kwargs

                args_result, kwargs_result = resolve_args_and_kwargs(
                    self,
                    args,
                    kwargs,
                    actor=actor,
                    fail_on_missing=True,
                )

                return args_result.value, kwargs_result.value

            def _measure_size(value: Any) -> int:
                """Measure the size of a value using the cache's measurer."""
                try:
                    serialized = json.dumps(value, default=str)
                    return self._measurer.measure(serialized)
                except (TypeError, ValueError):
                    # Fallback: estimate based on string representation
                    return self._measurer.measure(str(value))

            def _build_response(ref_id: str, value: Any) -> dict[str, Any]:
                """Build structured response based on value size."""
                value_size = _measure_size(value)
                is_complete = value_size <= effective_max_size

                if is_complete:
                    # Small result: include full value
                    return {
                        "ref_id": ref_id,
                        "value": value,
                        "is_complete": True,
                        "size": value_size,
                        "total_items": self._count_items(value),
                    }
                else:
                    # Large result: include preview only
                    response = self.get(ref_id)
                    result: dict[str, Any] = {
                        "ref_id": ref_id,
                        "preview": response.preview,
                        "is_complete": False,
                        "preview_strategy": response.preview_strategy.value,
                        "total_items": response.total_items,
                        "original_size": response.original_size,
                        "preview_size": response.preview_size,
                    }
                    if response.page is not None:
                        result["page"] = response.page
                        result["total_pages"] = response.total_pages
                    result["message"] = (
                        f"Use get_cached_result(ref_id='{ref_id}') to paginate."
                    )
                    return result

            if is_async:

                @functools.wraps(func)
                async def async_wrapper(
                    *args: P.args, **kwargs: P.kwargs
                ) -> dict[str, Any]:
                    # Step 1: Resolve any ref_ids in inputs
                    resolved_args, resolved_kwargs = _resolve_inputs(args, kwargs)

                    # Step 2: Generate cache key from RESOLVED inputs
                    cache_key = self._make_cache_key(
                        func, resolved_args, resolved_kwargs
                    )

                    # Step 3: Check if already cached
                    namespaced_key = self._make_namespaced_key(cache_key, namespace)
                    if namespaced_key in self._key_to_ref:
                        ref_id = self._key_to_ref[namespaced_key]
                        if self._backend.exists(ref_id):
                            entry = self._backend.get(ref_id)
                            if entry is not None:
                                return _build_response(ref_id, entry.value)

                    # Step 4: Execute function with resolved inputs
                    result = await func(*resolved_args, **resolved_kwargs)

                    # Step 5: Cache the result
                    ref = self.set(
                        cache_key,
                        result,
                        namespace=namespace,
                        policy=policy,
                        ttl=ttl,
                        tool_name=func.__name__,
                    )

                    # Step 6: Return structured response
                    return _build_response(ref.ref_id, result)

                # Update return annotation for FastMCP schema generation
                async_wrapper.__annotations__ = {
                    **func.__annotations__,
                    "return": dict[str, Any],
                }
                return async_wrapper  # type: ignore
            else:

                @functools.wraps(func)
                def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
                    # Step 1: Resolve any ref_ids in inputs
                    resolved_args, resolved_kwargs = _resolve_inputs(args, kwargs)

                    # Step 2: Generate cache key from RESOLVED inputs
                    cache_key = self._make_cache_key(
                        func, resolved_args, resolved_kwargs
                    )

                    # Step 3: Check if already cached
                    namespaced_key = self._make_namespaced_key(cache_key, namespace)
                    if namespaced_key in self._key_to_ref:
                        ref_id = self._key_to_ref[namespaced_key]
                        if self._backend.exists(ref_id):
                            entry = self._backend.get(ref_id)
                            if entry is not None:
                                return _build_response(ref_id, entry.value)

                    # Step 4: Execute function with resolved inputs
                    result = func(*resolved_args, **resolved_kwargs)

                    # Step 5: Cache the result
                    ref = self.set(
                        cache_key,
                        result,
                        namespace=namespace,
                        policy=policy,
                        ttl=ttl,
                        tool_name=func.__name__,
                    )

                    # Step 6: Return structured response
                    return _build_response(ref.ref_id, result)

                # Update return annotation for FastMCP schema generation
                sync_wrapper.__annotations__ = {
                    **func.__annotations__,
                    "return": dict[str, Any],
                }
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
        actor: ActorLike,
        namespace: str,
    ) -> None:
        """Check if an actor has the required permission.

        Args:
            policy: The access policy to evaluate.
            required: The permission required for the operation.
            actor: The actor attempting the operation (Actor or literal).
            namespace: The namespace of the resource.

        Raises:
            PermissionDenied: If the actor lacks the required permission.
        """
        resolved_actor = resolve_actor(actor)
        self._permission_checker.check(policy, required, resolved_actor, namespace)

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
        max_size: int | None = None,
    ) -> PreviewResult:
        """Create a preview of a value using the configured generator.

        When a page number is specified and the configured generator is
        SampleGenerator, automatically switches to PaginateGenerator for
        that call. This ensures pagination "just works" regardless of the
        default preview strategy.

        Args:
            value: The value to create a preview of.
            page: Page number for pagination (1-indexed). When specified,
                forces use of PaginateGenerator even if SampleGenerator
                is the default.
            page_size: Number of items per page.
            max_size: Maximum preview size. Overrides server default if provided.

        Returns:
            PreviewResult with preview data and metadata.
        """
        # Use provided max_size or fall back to config default
        effective_max_size = (
            max_size if max_size is not None else self.preview_config.max_size
        )

        # Auto-switch to PaginateGenerator when page is specified
        # This ensures pagination works regardless of default strategy
        generator = self._preview_generator
        if page is not None and isinstance(generator, SampleGenerator):
            generator = PaginateGenerator()

        return generator.generate(
            value=value,
            max_size=effective_max_size,
            measurer=self._measurer,
            page=page,
            page_size=page_size,
        )
