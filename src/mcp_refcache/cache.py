"""RefCache: Main cache interface for mcp-refcache.

Provides the primary API for caching values and managing references
with namespace isolation and permission-based access control.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import hashlib
import inspect
import json
import logging
import time
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from mcp_refcache.access.actor import Actor, ActorLike, resolve_actor
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
from mcp_refcache.context_integration import (
    build_context_scoped_policy,
    derive_actor_from_context,
    expand_template,
    get_context_values,
    try_get_fastmcp_context,
)
from mcp_refcache.models import (
    AsyncResponseFormat,
    AsyncTaskResponse,
    CacheReference,
    CacheResponse,
    ExpectedSchema,
    PreviewConfig,
    TaskInfo,
    TaskStatus,
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

if TYPE_CHECKING:
    from collections.abc import Callable

    from mcp_refcache.backends.task_base import TaskBackend

# Module-level logger
logger = logging.getLogger(__name__)

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
        task_backend: TaskBackend | None = None,
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
            task_backend: Task backend for async execution. If provided, enables
                async_timeout parameter on @cache.cached() decorator. When a cached
                function exceeds the timeout, execution continues in background and
                an AsyncTaskResponse is returned immediately for polling.

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

        # Task backend for async execution (optional)
        self._task_backend = task_backend

        # Track active async tasks: task_id -> TaskInfo
        self._active_tasks: dict[str, TaskInfo] = {}

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
    ) -> CacheResponse | AsyncTaskResponse:
        """Get a preview of a cached value or status of an in-flight task.

        If the ref_id corresponds to an active async task, returns AsyncTaskResponse
        with current status and progress. If it's a completed/cached entry, returns
        CacheResponse with preview.

        Args:
            ref_id: Reference ID or key to look up.
            page: Page number for pagination (1-indexed).
            page_size: Number of items per page.
            max_size: Maximum preview size (tokens/chars). Overrides server default.
                Use smaller values for quick summaries, larger for more context.
            actor: Who is requesting. Can be an Actor object or literal "user"/"agent".

        Returns:
            AsyncTaskResponse if the task is in-flight (PENDING/PROCESSING/FAILED).
            CacheResponse if the result is cached or task is complete.

        Raises:
            KeyError: If the reference is not found.
            PermissionDenied: If the actor lacks READ permission or namespace access.

        Example:
            ```python
            response = cache.get(ref.ref_id)

            # For cached results
            if isinstance(response, CacheResponse):
                print(response.preview)

            # For in-flight tasks
            elif isinstance(response, AsyncTaskResponse):
                print(f"Status: {response.status}, Progress: {response.progress}")

            # With Actor object
            from mcp_refcache import DefaultActor
            actor = DefaultActor.user(id="alice")
            response = cache.get(ref.ref_id, actor=actor)
            ```
        """
        # Check if this is an active async task first
        task_info = self.get_task_status(ref_id)
        if task_info is not None:
            # Task is still being tracked
            if task_info.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
                # Still in progress - return task status
                return self._build_async_task_response(task_info)
            elif task_info.status == TaskStatus.FAILED:
                # Failed - return error info
                return self._build_async_task_response(task_info)
            # COMPLETE or CANCELLED - fall through to cache lookup
            # Clean up tracking for completed tasks
            if task_info.status == TaskStatus.COMPLETE and ref_id in self._active_tasks:
                del self._active_tasks[ref_id]

        # Normal cache lookup for completed/cached entries
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
        actor: ActorLike = "agent",
        # Context-scoped parameters
        namespace_template: str | None = None,
        owner_template: str | None = None,
        session_scoped: bool = False,
        # Async execution parameters
        async_timeout: float | None = None,
        async_response_format: AsyncResponseFormat | str = AsyncResponseFormat.STANDARD,
    ) -> Callable[[Callable[P, R]], Callable[P, dict[str, Any]]]:
        """Decorator to cache function results and return structured responses.

        This decorator provides full MCP tool integration:
        1. **Pre-execution**: Resolves any ref_ids in inputs (deep recursive)
        2. **Post-execution**: Caches result and returns structured response

        The response is ALWAYS a structured dict containing:
        - Small results: Full value + ref_id + metadata (is_complete=True)
        - Large results: Preview + ref_id + pagination info (is_complete=False)

        Context-Scoped Caching:
            When used with FastMCP, namespace and owner can be dynamically
            derived from the authenticated session context. This ensures
            agents cannot control their own scoping - identity comes from
            middleware-set values, not function parameters.

        Async Timeout Execution:
            When async_timeout is set and a task_backend is configured on the
            RefCache, long-running computations that exceed the timeout will
            continue executing in the background. The decorator returns an
            AsyncTaskResponse immediately, allowing clients to poll for completion.

        Args:
            namespace: Static namespace for cached results.
            policy: Access policy for cached results.
            ttl: TTL for cached results.
            max_size: Maximum size (tokens/chars) before auto-preview.
                If None, uses cache's preview_config.max_size.
            resolve_refs: If True (default), resolve ref_ids in inputs before
                executing the function. Any parameter value matching the ref_id
                pattern will be hot-swapped with the cached value.
            actor: Actor identity for permission checks when resolving refs.
            namespace_template: Dynamic namespace template with {placeholders}.
                Placeholders are filled from FastMCP Context (e.g.,
                "org:{org_id}:user:{user_id}"). Takes priority over namespace.
            owner_template: Dynamic owner template with {placeholders}.
                Sets AccessPolicy.owner from context (e.g., "user:{user_id}").
            session_scoped: If True, binds cached value to the current session.
                Only the session that created the cache entry can access it.
            async_timeout: Timeout in seconds before returning an async response.
                If the function doesn't complete within this time, execution
                continues in background via task_backend, and an AsyncTaskResponse
                is returned immediately. Requires task_backend to be configured.
            async_response_format: Detail level for async responses. Can be:
                - "minimal": Just ref_id, status, is_async (for simple polling)
                - "standard" (default): Above + started_at, progress, message
                - "full": Above + expected_schema, eta_seconds, retry_info
                Agents can override at call time with `_async_response_format` param.

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

            # Context-scoped caching (with FastMCP):
            @mcp.tool
            @cache.cached(
                namespace_template="org:{org_id}:user:{user_id}",
                owner_template="user:{user_id}",
                session_scoped=True,
            )
            async def get_account_balance(account_id: str) -> dict:
                # Namespace becomes "org:acme:user:alice" from context
                # Owner is automatically set to "user:alice"
                # Only this session can access the cached result
                ...

            # Async timeout execution:
            @mcp.tool
            @cache.cached(namespace="jobs", async_timeout=5.0)
            async def process_large_document(doc_id: str) -> dict:
                # If processing takes >5s, returns immediately with:
                # {"ref_id": "...", "status": "processing", ...}
                # Client polls get_cached_result(ref_id) for completion
                ...

            # Full async response with schema preview:
            @mcp.tool
            @cache.cached(
                namespace="jobs",
                async_timeout=5.0,
                async_response_format="full",
            )
            async def analyze_document(doc_id: str) -> AnalysisResult:
                # Returns schema info so agent knows what to expect:
                # {"ref_id": "...", "status": "processing",
                #  "expected_schema": {"return_type": "AnalysisResult", ...}}
                ...

            # Agent can also override at call time:
            result = await analyze_document(doc_id, _async_response_format="minimal")
            ```
        """
        effective_max_size = max_size or self.preview_config.max_size
        use_context_scoping = (
            namespace_template is not None
            or owner_template is not None
            or session_scoped
        )
        use_async_timeout = async_timeout is not None and self._task_backend is not None

        # Normalize async_response_format to enum
        if isinstance(async_response_format, str):
            default_response_format = AsyncResponseFormat(async_response_format)
        else:
            default_response_format = async_response_format

        if async_timeout is not None and self._task_backend is None:
            logger.warning(
                "async_timeout specified but no task_backend configured. "
                "Async timeout will be ignored."
            )

        def decorator(func: Callable[P, Any]) -> Callable[P, dict[str, Any]]:
            # Extract return type annotation for schema generation
            return_annotation = inspect.signature(func).return_annotation
            expected_schema = self._extract_expected_schema(func, return_annotation)
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

            def _get_context_scoped_values() -> tuple[
                str, AccessPolicy | None, Actor | None
            ]:
                """Get namespace, policy, and actor from FastMCP context.

                Returns:
                    Tuple of (effective_namespace, effective_policy, effective_actor)
                """
                if not use_context_scoping:
                    return namespace, policy, None

                # Try to get FastMCP context
                ctx = try_get_fastmcp_context()
                if ctx is None:
                    # No context available - use static values with fallbacks
                    context_values: dict[str, str] = {}
                else:
                    context_values = get_context_values(ctx)

                # Expand namespace template or use static namespace
                if namespace_template is not None:
                    effective_namespace = expand_template(
                        namespace_template, context_values
                    )
                else:
                    effective_namespace = namespace

                # Build policy with owner and session binding
                effective_policy = build_context_scoped_policy(
                    base_policy=policy,
                    context_values=context_values,
                    owner_template=owner_template,
                    session_scoped=session_scoped,
                )

                # Derive actor from context
                effective_actor = derive_actor_from_context(
                    context_values, default_actor=actor
                )

                return effective_namespace, effective_policy, effective_actor

            def _resolve_inputs(
                args: tuple[Any, ...],
                kwargs: dict[str, Any],
                effective_actor: Actor | None,
            ) -> tuple[tuple[Any, ...], dict[str, Any]]:
                """Resolve any ref_ids in args and kwargs."""
                if not resolve_refs:
                    return args, kwargs

                # Use context-derived actor if available, default to "agent"
                actor_for_resolution: ActorLike = (
                    effective_actor if effective_actor is not None else actor
                )

                args_result, kwargs_result = resolve_args_and_kwargs(
                    self,
                    args,
                    kwargs,
                    actor=actor_for_resolution,
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
                        "is_async": False,
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
                        "is_async": False,
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

            def _build_async_response(
                task_info: TaskInfo,
                response_format: AsyncResponseFormat | None = None,
            ) -> dict[str, Any]:
                """Build response for async in-flight task."""
                effective_format = response_format or default_response_format
                response = AsyncTaskResponse.from_task_info(
                    task_info,
                    expected_schema=expected_schema
                    if effective_format == AsyncResponseFormat.FULL
                    else None,
                    response_format=effective_format,
                )
                return response.to_dict(response_format=effective_format)

            def _get_response_format_override(
                kwargs: dict[str, Any],
            ) -> tuple[AsyncResponseFormat | None, dict[str, Any]]:
                """Extract _async_response_format from kwargs if present."""
                if "_async_response_format" not in kwargs:
                    return None, kwargs

                # Make a copy to avoid mutating the original
                kwargs_copy = dict(kwargs)
                format_value = kwargs_copy.pop("_async_response_format")
                if isinstance(format_value, str):
                    return AsyncResponseFormat(format_value), kwargs_copy
                elif isinstance(format_value, AsyncResponseFormat):
                    return format_value, kwargs_copy
                else:
                    logger.warning(
                        "Invalid _async_response_format value: %s, using default",
                        format_value,
                    )
                    return None, kwargs_copy

            def _check_existing_task(
                ref_id: str,
                response_format: AsyncResponseFormat | None = None,
            ) -> dict[str, Any] | None:
                """Check if there's an in-flight task for this ref_id."""
                if ref_id in self._active_tasks:
                    task_info = self._active_tasks[ref_id]
                    if not task_info.is_terminal:
                        return _build_async_response(task_info, response_format)
                    # Task completed - check if result is cached
                    if task_info.status == TaskStatus.COMPLETE:
                        # Clean up tracking
                        del self._active_tasks[ref_id]
                return None

            if is_async:

                @functools.wraps(func)
                async def async_wrapper(
                    *args: P.args, **kwargs: P.kwargs
                ) -> dict[str, Any]:
                    # Step 0a: Extract _async_response_format override if present
                    response_format_override, clean_kwargs = (
                        _get_response_format_override(dict(kwargs))
                    )

                    # Step 0b: Get context-scoped values (namespace, policy, actor)
                    (
                        effective_namespace,
                        effective_policy,
                        effective_actor,
                    ) = _get_context_scoped_values()

                    # Step 1: Resolve any ref_ids in inputs
                    resolved_args, resolved_kwargs = _resolve_inputs(
                        args, clean_kwargs, effective_actor
                    )

                    # Step 2: Generate cache key from RESOLVED inputs
                    cache_key = self._make_cache_key(
                        func, resolved_args, resolved_kwargs
                    )

                    # Step 3: Check if already cached or in-flight
                    namespaced_key = self._make_namespaced_key(
                        cache_key, effective_namespace
                    )
                    if namespaced_key in self._key_to_ref:
                        ref_id = self._key_to_ref[namespaced_key]

                        # Check for in-flight task first
                        async_response = _check_existing_task(
                            ref_id, response_format_override
                        )
                        if async_response is not None:
                            return async_response

                        if self._backend.exists(ref_id):
                            entry = self._backend.get(ref_id)
                            if entry is not None:
                                return _build_response(ref_id, entry.value)

                    # Step 4: Execute function with resolved inputs
                    # If async_timeout is configured, use timeout-based execution
                    if use_async_timeout and async_timeout is not None:
                        timeout_result = await self._execute_with_async_timeout(
                            func=func,
                            args=resolved_args,
                            kwargs=resolved_kwargs,
                            timeout=async_timeout,
                            cache_key=cache_key,
                            namespace=effective_namespace,
                            policy=effective_policy,
                            ttl_value=ttl,
                            tool_name=func.__name__,
                            is_async_func=True,
                            response_format=response_format_override
                            or default_response_format,
                            expected_schema=expected_schema,
                        )
                        if isinstance(timeout_result, dict) and timeout_result.get(
                            "is_async"
                        ):
                            return timeout_result
                        # Function completed within timeout
                        actual_result = timeout_result
                    else:
                        actual_result = await func(*resolved_args, **resolved_kwargs)

                    # Step 5: Cache the result
                    ref = self.set(
                        cache_key,
                        actual_result,
                        namespace=effective_namespace,
                        policy=effective_policy,
                        ttl=ttl,
                        tool_name=func.__name__,
                    )

                    # Step 6: Return structured response
                    return _build_response(ref.ref_id, actual_result)

                # Update return annotation for FastMCP schema generation
                # Both __annotations__ AND __signature__ must be updated because
                # functools.wraps copies the original signature, and inspect.signature()
                # uses __wrapped__ to return the original signature, ignoring __annotations__
                async_wrapper.__annotations__ = {
                    **func.__annotations__,
                    "return": dict[str, Any],
                }
                # Update __signature__ so inspect.signature() returns correct type
                original_sig = inspect.signature(func)
                async_wrapper.__signature__ = original_sig.replace(  # type: ignore[attr-defined]
                    return_annotation=dict[str, Any]
                )
                return async_wrapper  # type: ignore[return-value]
            else:

                @functools.wraps(func)
                def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
                    # Step 0a: Extract _async_response_format override if present
                    response_format_override, clean_kwargs = (
                        _get_response_format_override(dict(kwargs))
                    )

                    # Step 0b: Get context-scoped values (namespace, policy, actor)
                    (
                        effective_namespace,
                        effective_policy,
                        effective_actor,
                    ) = _get_context_scoped_values()

                    # Step 1: Resolve any ref_ids in inputs
                    resolved_args, resolved_kwargs = _resolve_inputs(
                        args, clean_kwargs, effective_actor
                    )

                    # Step 2: Generate cache key from RESOLVED inputs
                    cache_key = self._make_cache_key(
                        func, resolved_args, resolved_kwargs
                    )

                    # Step 3: Check if already cached or in-flight
                    namespaced_key = self._make_namespaced_key(
                        cache_key, effective_namespace
                    )
                    if namespaced_key in self._key_to_ref:
                        ref_id = self._key_to_ref[namespaced_key]

                        # Check for in-flight task first
                        async_response = _check_existing_task(
                            ref_id, response_format_override
                        )
                        if async_response is not None:
                            return async_response

                        if self._backend.exists(ref_id):
                            entry = self._backend.get(ref_id)
                            if entry is not None:
                                return _build_response(ref_id, entry.value)

                    # Step 4: Execute function with resolved inputs
                    # If async_timeout is configured, use timeout-based execution
                    if use_async_timeout and async_timeout is not None:
                        timeout_result = self._execute_sync_with_async_timeout(
                            func=func,
                            args=resolved_args,
                            kwargs=resolved_kwargs,
                            timeout=async_timeout,
                            cache_key=cache_key,
                            namespace=effective_namespace,
                            policy=effective_policy,
                            ttl_value=ttl,
                            tool_name=func.__name__,
                            response_format=response_format_override
                            or default_response_format,
                            expected_schema=expected_schema,
                        )
                        if isinstance(timeout_result, dict) and timeout_result.get(
                            "is_async"
                        ):
                            return timeout_result
                        # Function completed within timeout
                        actual_result = timeout_result
                    else:
                        actual_result = func(*resolved_args, **resolved_kwargs)

                    # Step 5: Cache the result
                    ref = self.set(
                        cache_key,
                        actual_result,
                        namespace=effective_namespace,
                        policy=effective_policy,
                        ttl=ttl,
                        tool_name=func.__name__,
                    )

                    # Step 6: Return structured response
                    return _build_response(ref.ref_id, actual_result)

                # Update return annotation for FastMCP schema generation
                # Both __annotations__ AND __signature__ must be updated because
                # functools.wraps copies the original signature, and inspect.signature()
                # uses __wrapped__ to return the original signature, ignoring __annotations__
                sync_wrapper.__annotations__ = {
                    **func.__annotations__,
                    "return": dict[str, Any],
                }
                # Update __signature__ so inspect.signature() returns correct type
                original_sig = inspect.signature(func)
                sync_wrapper.__signature__ = original_sig.replace(  # type: ignore[attr-defined]
                    return_annotation=dict[str, Any]
                )
                return sync_wrapper

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

    def _make_cache_key(
        self, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> str:
        """Create a cache key from function and arguments."""
        # Create a deterministic key from function name and arguments
        key_parts = [func.__module__, func.__qualname__]

        for arg in args:
            key_parts.append(repr(arg))

        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v!r}")

        composite = ":".join(key_parts)
        return hashlib.sha256(composite.encode()).hexdigest()[:32]

    def _extract_expected_schema(
        self,
        func: Callable[..., Any],
        return_annotation: Any,
    ) -> ExpectedSchema | None:
        """Extract schema information from function's return type annotation.

        Args:
            func: The function to extract schema from.
            return_annotation: The return type annotation.

        Returns:
            ExpectedSchema if extractable, None otherwise.
        """
        if return_annotation is inspect.Parameter.empty:
            return None

        try:
            # Get string representation of return type
            if hasattr(return_annotation, "__name__"):
                return_type_str = return_annotation.__name__
            elif hasattr(return_annotation, "__origin__"):
                # Handle generics like dict[str, Any], list[int], etc.
                origin = return_annotation.__origin__
                args = getattr(return_annotation, "__args__", ())
                if args:
                    args_str = ", ".join(getattr(a, "__name__", str(a)) for a in args)
                    return_type_str = f"{origin.__name__}[{args_str}]"
                else:
                    return_type_str = origin.__name__
            else:
                return_type_str = str(return_annotation)

            # Try to extract fields from Pydantic models
            fields: dict[str, str] | None = None
            description: str | None = None

            # Check if it's a Pydantic model
            if hasattr(return_annotation, "model_fields"):
                fields = {}
                for field_name, field_info in return_annotation.model_fields.items():
                    field_type = field_info.annotation
                    if hasattr(field_type, "__name__"):
                        fields[field_name] = field_type.__name__
                    else:
                        fields[field_name] = str(field_type)

                # Try to get description from docstring
                if return_annotation.__doc__:
                    description = return_annotation.__doc__.strip().split("\n")[0]

            # Check if it's a TypedDict
            elif hasattr(return_annotation, "__annotations__"):
                annotations = return_annotation.__annotations__
                if annotations:
                    fields = {}
                    for field_name, field_type in annotations.items():
                        if hasattr(field_type, "__name__"):
                            fields[field_name] = field_type.__name__
                        else:
                            fields[field_name] = str(field_type)

            return ExpectedSchema(
                return_type=return_type_str,
                fields=fields,
                example=None,
                description=description,
            )

        except Exception as exc:
            logger.debug("Failed to extract schema from %s: %s", func.__name__, exc)
            return None

    async def _execute_with_async_timeout(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        timeout: float,
        cache_key: str,
        namespace: str,
        policy: AccessPolicy | None,
        ttl_value: float | None,
        tool_name: str,
        is_async_func: bool,
        response_format: AsyncResponseFormat = AsyncResponseFormat.STANDARD,
        expected_schema: ExpectedSchema | None = None,
    ) -> Any | dict[str, Any]:
        """Execute a function with async timeout handling.

        If the function completes within the timeout, returns the result.
        If it times out, submits to task_backend and returns AsyncTaskResponse.
        """
        assert self._task_backend is not None

        # Generate task_id that will also be the ref_id
        task_id = self._generate_ref_id(cache_key, namespace)

        # For async functions, try to complete within timeout
        if is_async_func:
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout,
                )
                return result
            except asyncio.TimeoutError:
                logger.info(
                    "Function %s exceeded timeout of %ss, submitting to background",
                    tool_name,
                    timeout,
                )
        else:
            # For sync functions called from async context, run in executor with timeout
            loop = asyncio.get_event_loop()
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                    timeout=timeout,
                )
                return result
            except asyncio.TimeoutError:
                logger.info(
                    "Function %s exceeded timeout of %ss, submitting to background",
                    tool_name,
                    timeout,
                )

        # Timeout occurred - submit to task backend for background execution
        # Create a wrapper that caches the result when complete
        def background_task_wrapper() -> Any:
            return self._execute_and_cache_background_task(
                func=func,
                args=args,
                kwargs=kwargs,
                task_id=task_id,
                cache_key=cache_key,
                namespace=namespace,
                policy=policy,
                ttl_value=ttl_value,
                tool_name=tool_name,
                is_async_func=is_async_func,
            )

        # Submit to task backend
        task_info = self._task_backend.submit(
            task_id=task_id,
            func=background_task_wrapper,
            args=(),
            kwargs={},
        )

        # Track the active task
        self._active_tasks[task_id] = task_info

        # Also register the ref_id mapping so polling works
        namespaced_key = self._make_namespaced_key(cache_key, namespace)
        self._key_to_ref[namespaced_key] = task_id
        self._ref_to_key[task_id] = cache_key

        # Return async response
        response = AsyncTaskResponse.from_task_info(
            task_info,
            expected_schema=expected_schema
            if response_format == AsyncResponseFormat.FULL
            else None,
            response_format=response_format,
        )
        return response.to_dict(response_format=response_format)

    def _execute_sync_with_async_timeout(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        timeout: float,
        cache_key: str,
        namespace: str,
        policy: AccessPolicy | None,
        ttl_value: float | None,
        tool_name: str,
        response_format: AsyncResponseFormat = AsyncResponseFormat.STANDARD,
        expected_schema: ExpectedSchema | None = None,
    ) -> Any | dict[str, Any]:
        """Execute a sync function with timeout handling.

        Uses ThreadPoolExecutor to run with timeout. If timeout occurs,
        submits to task_backend for background completion.
        """
        assert self._task_backend is not None

        # Generate task_id that will also be the ref_id
        task_id = self._generate_ref_id(cache_key, namespace)

        # Try to execute within timeout using a thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            try:
                result = future.result(timeout=timeout)
                return result
            except concurrent.futures.TimeoutError:
                logger.info(
                    "Function %s exceeded timeout of %ss, submitting to background",
                    tool_name,
                    timeout,
                )
                # Note: The future is still running! We'll let task_backend handle it
                # by starting a fresh execution. The original will be orphaned.
                # This is a known limitation - we can't "continue" the same execution.

        # Timeout occurred - submit to task backend for background execution
        def background_task_wrapper() -> Any:
            return self._execute_and_cache_background_task(
                func=func,
                args=args,
                kwargs=kwargs,
                task_id=task_id,
                cache_key=cache_key,
                namespace=namespace,
                policy=policy,
                ttl_value=ttl_value,
                tool_name=tool_name,
                is_async_func=False,
            )

        # Submit to task backend
        task_info = self._task_backend.submit(
            task_id=task_id,
            func=background_task_wrapper,
            args=(),
            kwargs={},
        )

        # Track the active task
        self._active_tasks[task_id] = task_info

        # Also register the ref_id mapping so polling works
        namespaced_key = self._make_namespaced_key(cache_key, namespace)
        self._key_to_ref[namespaced_key] = task_id
        self._ref_to_key[task_id] = cache_key

        # Return async response
        response = AsyncTaskResponse.from_task_info(
            task_info,
            expected_schema=expected_schema
            if response_format == AsyncResponseFormat.FULL
            else None,
            response_format=response_format,
        )
        return response.to_dict(response_format=response_format)

    def _execute_and_cache_background_task(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        task_id: str,
        cache_key: str,
        namespace: str,
        policy: AccessPolicy | None,
        ttl_value: float | None,
        tool_name: str,
        is_async_func: bool,
    ) -> Any:
        """Execute a function and cache its result (called by task_backend).

        This runs in the background thread/worker. When complete, it stores
        the result in the cache so polling via get_cached_result works.
        """
        try:
            # Execute the function
            if is_async_func:
                # Run async function in a new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(func(*args, **kwargs))
                finally:
                    loop.close()
            else:
                result = func(*args, **kwargs)

            # Cache the result using the pre-generated task_id as ref_id
            # We need to store directly to backend since set() generates new ref_id
            created_at = time.time()
            expires_at = created_at + ttl_value if ttl_value is not None else None

            entry = CacheEntry(
                value=result,
                namespace=namespace,
                policy=policy if policy is not None else self.default_policy,
                created_at=created_at,
                expires_at=expires_at,
                metadata={
                    "tool_name": tool_name,
                    "total_items": self._count_items(result),
                    "total_size": self._estimate_size(result),
                    "async_completed": True,
                },
            )

            self._backend.set(task_id, entry)
            logger.info("Background task %s completed and cached", task_id)

            # Update task info if we're tracking it
            if task_id in self._active_tasks:
                self._active_tasks[task_id].status = TaskStatus.COMPLETE
                self._active_tasks[task_id].completed_at = time.time()

            return result

        except Exception as exc:
            logger.error("Background task %s failed: %s", task_id, exc)
            # Update task info
            if task_id in self._active_tasks:
                self._active_tasks[task_id].status = TaskStatus.FAILED
                self._active_tasks[task_id].error = str(exc)
                self._active_tasks[task_id].completed_at = time.time()
            raise

    def get_task_status(self, ref_id: str) -> TaskInfo | None:
        """Get the status of an async task by ref_id.

        Args:
            ref_id: The reference ID (which is also the task_id for async tasks).

        Returns:
            TaskInfo if the task exists, None otherwise.
        """
        # Check our local tracking first
        if ref_id in self._active_tasks:
            task_info = self._active_tasks[ref_id]
            # If we have a task backend, get fresh status
            if self._task_backend is not None:
                backend_status = self._task_backend.get_status(ref_id)
                if backend_status is not None:
                    self._active_tasks[ref_id] = backend_status
                    return backend_status
            return task_info

        # Try the task backend directly
        if self._task_backend is not None:
            return self._task_backend.get_status(ref_id)

        return None

    def _build_async_task_response(
        self,
        task_info: TaskInfo,
        response_format: AsyncResponseFormat = AsyncResponseFormat.STANDARD,
    ) -> AsyncTaskResponse:
        """Build an AsyncTaskResponse for an in-flight or failed task.

        Args:
            task_info: Internal task tracking information.
            response_format: Detail level for the response (default: STANDARD).

        Returns:
            AsyncTaskResponse with status, progress, and ETA.
        """
        # Calculate ETA if progress is available
        eta_seconds = self._calculate_eta(task_info)

        # Note: expected_schema is not stored in TaskInfo, it's stored separately
        # during task creation. For polling responses, we don't include it.
        # It's only included in the initial async response from the decorator.
        return AsyncTaskResponse.from_task_info(
            task_info=task_info,
            eta_seconds=eta_seconds,
            expected_schema=None,
            response_format=response_format,
        )

    def _calculate_eta(self, task_info: TaskInfo) -> float | None:
        """Estimate time remaining based on progress rate.

        Args:
            task_info: Task tracking information with progress.

        Returns:
            Estimated seconds until completion, or None if ETA cannot be calculated.
        """
        if task_info.progress is None:
            return None
        if task_info.progress.current is None or task_info.progress.total is None:
            return None
        if task_info.progress.current == 0:
            return None

        elapsed = time.time() - task_info.started_at
        rate = task_info.progress.current / elapsed
        remaining = task_info.progress.total - task_info.progress.current

        return remaining / rate if rate > 0 else None

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
        if isinstance(value, list | tuple | set | frozenset):
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
