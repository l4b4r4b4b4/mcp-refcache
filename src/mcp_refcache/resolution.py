"""Ref_id resolution utilities for mcp-refcache.

This module provides utilities for detecting and resolving ref_ids
anywhere in input structures, enabling transparent reference passing
between MCP tools.

Key features:
- Pattern matching for ref_id strings (e.g., "cachename:hexhash")
- Deep recursive resolution through nested dicts, lists, and tuples
- Cycle detection to prevent infinite loops
- Error handling for missing/expired references
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp_refcache.cache import RefCache

# Pattern for ref_id: cachename:hexhash (e.g., "finquant:2780226d27c57e49")
# Cache name: alphanumeric, hyphens, underscores
# Hash: hexadecimal characters
REF_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*:[a-f0-9]{8,}$")


class CircularReferenceError(Exception):
    """Raised when a circular reference is detected during resolution."""

    def __init__(self, ref_id: str, chain: list[str]) -> None:
        self.ref_id = ref_id
        self.chain = chain
        chain_str = " -> ".join([*chain, ref_id])
        super().__init__(f"Circular reference detected: {chain_str}")


def is_ref_id(value: Any) -> bool:
    """Check if a value is a ref_id string.

    Args:
        value: Any value to check.

    Returns:
        True if the value matches the ref_id pattern.

    Example:
        ```python
        is_ref_id("finquant:2780226d27c57e49")  # True
        is_ref_id("just a string")              # False
        is_ref_id(12345)                        # False
        is_ref_id({"key": "value"})             # False
        ```
    """
    if not isinstance(value, str):
        return False
    return REF_ID_PATTERN.match(value) is not None


@dataclass
class ResolutionResult:
    """Result of resolving ref_ids in an input structure.

    Attributes:
        value: The resolved value with all ref_ids replaced.
        resolved_count: Number of ref_ids that were resolved.
        resolved_refs: List of ref_ids that were resolved.
        errors: Dict mapping ref_ids to error messages for failed resolutions.
    """

    value: Any
    resolved_count: int = 0
    resolved_refs: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        """Check if any resolution errors occurred."""
        return len(self.errors) > 0

    @property
    def success(self) -> bool:
        """Check if all resolutions succeeded."""
        return not self.has_errors


class RefResolver:
    """Resolves ref_ids in input structures.

    Recursively walks through input structures (dicts, lists, tuples)
    and resolves any ref_id strings to their cached values.

    Example:
        ```python
        cache = RefCache(name="myapp")
        resolver = RefResolver(cache)

        # Store some values
        ref1 = cache.set("prices", [100, 101, 102])
        ref2 = cache.set("multiplier", 2.0)

        # Resolve refs in nested structure
        result = resolver.resolve({
            "data": ref1.ref_id,
            "factor": ref2.ref_id,
            "options": {"nested": [1, 2, ref1.ref_id]}
        })

        # result.value contains fully resolved structure
        # {
        #     "data": [100, 101, 102],
        #     "factor": 2.0,
        #     "options": {"nested": [1, 2, [100, 101, 102]]}
        # }
        ```
    """

    def __init__(
        self,
        cache: RefCache,
        *,
        actor: str = "agent",
        fail_on_missing: bool = True,
    ) -> None:
        """Initialize the resolver.

        Args:
            cache: The RefCache instance to resolve refs from.
            actor: Actor identity for permission checks (default: "agent").
            fail_on_missing: If True, raise KeyError for missing refs.
                If False, collect errors and continue.
        """
        self._cache = cache
        self._actor = actor
        self._fail_on_missing = fail_on_missing

    def resolve(
        self, value: Any, *, _visiting: set[str] | None = None
    ) -> ResolutionResult:
        """Resolve all ref_ids in a value structure.

        Recursively walks through the input, resolving any ref_id strings
        to their cached values.

        Args:
            value: Any value that may contain ref_ids (nested or not).

        Returns:
            ResolutionResult containing the resolved value and metadata.

        Raises:
            KeyError: If fail_on_missing is True and a ref_id is not found.
            PermissionError: If the actor lacks permission to resolve a ref.
            CircularReferenceError: If a circular reference is detected.
        """
        resolved_refs: list[str] = []
        errors: dict[str, str] = {}
        visiting = _visiting if _visiting is not None else set()

        resolved_value = self._resolve_recursive(value, resolved_refs, errors, visiting)

        return ResolutionResult(
            value=resolved_value,
            resolved_count=len(resolved_refs),
            resolved_refs=resolved_refs,
            errors=errors,
        )

    def _resolve_recursive(
        self,
        value: Any,
        resolved_refs: list[str],
        errors: dict[str, str],
        visiting: set[str],
    ) -> Any:
        """Recursively resolve ref_ids in a value.

        Args:
            value: The value to resolve.
            resolved_refs: List to track resolved ref_ids.
            errors: Dict to track resolution errors.
            visiting: Set of ref_ids currently being resolved (for cycle detection).

        Returns:
            The resolved value.
        """
        # Check if this is a ref_id string
        if is_ref_id(value):
            return self._resolve_ref(value, resolved_refs, errors, visiting)

        # Recursively handle containers
        if isinstance(value, dict):
            return {
                k: self._resolve_recursive(v, resolved_refs, errors, visiting)
                for k, v in value.items()
            }

        if isinstance(value, list):
            return [
                self._resolve_recursive(item, resolved_refs, errors, visiting)
                for item in value
            ]

        if isinstance(value, tuple):
            return tuple(
                self._resolve_recursive(item, resolved_refs, errors, visiting)
                for item in value
            )

        # Non-container, non-ref value - return as-is
        return value

    def _resolve_ref(
        self,
        ref_id: str,
        resolved_refs: list[str],
        errors: dict[str, str],
        visiting: set[str],
    ) -> Any:
        """Resolve a single ref_id.

        Args:
            ref_id: The ref_id string to resolve.
            resolved_refs: List to track resolved ref_ids.
            errors: Dict to track resolution errors.
            visiting: Set of ref_ids currently being resolved (for cycle detection).

        Returns:
            The resolved value, or the original ref_id if resolution failed
            and fail_on_missing is False.

        Raises:
            CircularReferenceError: If this ref_id is already being resolved.
        """
        # Check for circular reference
        if ref_id in visiting:
            raise CircularReferenceError(ref_id, list(visiting))

        try:
            # Mark as visiting before resolving
            visiting.add(ref_id)

            resolved_value = self._cache.resolve(ref_id, actor=self._actor)
            resolved_refs.append(ref_id)

            # If resolved value contains more ref_ids, resolve them too
            # (with cycle detection still active)
            if self._contains_ref_ids(resolved_value):
                resolved_value = self._resolve_recursive(
                    resolved_value, resolved_refs, errors, visiting
                )

            return resolved_value
        except KeyError:
            if self._fail_on_missing:
                # Raise opaque error that doesn't leak existence info
                raise KeyError(f"Invalid or inaccessible reference: {ref_id}") from None
            errors[ref_id] = "Invalid or inaccessible reference"
            return ref_id  # Return original ref_id on failure
        except PermissionError:
            if self._fail_on_missing:
                # Raise same opaque error as KeyError (security: don't leak existence)
                raise KeyError(f"Invalid or inaccessible reference: {ref_id}") from None
            errors[ref_id] = "Invalid or inaccessible reference"
            return ref_id
        finally:
            # Remove from visiting set when done (whether success or failure)
            visiting.discard(ref_id)

    def _contains_ref_ids(self, value: Any) -> bool:
        """Check if a value contains any ref_ids (for nested resolution)."""
        if is_ref_id(value):
            return True
        if isinstance(value, dict):
            return any(self._contains_ref_ids(v) for v in value.values())
        if isinstance(value, (list, tuple)):
            return any(self._contains_ref_ids(item) for item in value)
        return False


def resolve_refs(
    cache: RefCache,
    value: Any,
    *,
    actor: str = "agent",
    fail_on_missing: bool = True,
) -> ResolutionResult:
    """Convenience function to resolve all ref_ids in a value.

    Args:
        cache: The RefCache instance to resolve refs from.
        value: Any value that may contain ref_ids.
        actor: Actor identity for permission checks (default: "agent").
        fail_on_missing: If True, raise on missing refs. If False, collect errors.

    Returns:
        ResolutionResult containing the resolved value and metadata.

    Example:
        ```python
        result = resolve_refs(cache, {
            "prices": "finquant:abc123",
            "config": {"factor": "finquant:def456"}
        })

        if result.success:
            print(f"Resolved {result.resolved_count} refs")
            use_data(result.value)
        else:
            print(f"Errors: {result.errors}")
        ```
    """
    resolver = RefResolver(cache, actor=actor, fail_on_missing=fail_on_missing)
    return resolver.resolve(value)


def resolve_kwargs(
    cache: RefCache,
    kwargs: dict[str, Any],
    *,
    actor: str = "agent",
    fail_on_missing: bool = True,
) -> ResolutionResult:
    """Resolve all ref_ids in function kwargs.

    Convenience wrapper for resolving refs in tool function arguments.

    Args:
        cache: The RefCache instance to resolve refs from.
        kwargs: Keyword arguments dict that may contain ref_ids.
        actor: Actor identity for permission checks.
        fail_on_missing: If True, raise on missing refs.

    Returns:
        ResolutionResult with resolved kwargs as the value.

    Example:
        ```python
        # In decorator wrapper:
        result = resolve_kwargs(cache, kwargs)
        if not result.success:
            return {"error": "Failed to resolve refs", "details": result.errors}
        resolved_kwargs = result.value
        return func(*args, **resolved_kwargs)
        ```
    """
    return resolve_refs(
        cache,
        kwargs,
        actor=actor,
        fail_on_missing=fail_on_missing,
    )


def resolve_args_and_kwargs(
    cache: RefCache,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    actor: str = "agent",
    fail_on_missing: bool = True,
) -> tuple[ResolutionResult, ResolutionResult]:
    """Resolve all ref_ids in both args and kwargs.

    Args:
        cache: The RefCache instance to resolve refs from.
        args: Positional arguments tuple.
        kwargs: Keyword arguments dict.
        actor: Actor identity for permission checks.
        fail_on_missing: If True, raise on missing refs.

    Returns:
        Tuple of (args_result, kwargs_result).

    Example:
        ```python
        args_result, kwargs_result = resolve_args_and_kwargs(cache, args, kwargs)

        if args_result.success and kwargs_result.success:
            return func(*args_result.value, **kwargs_result.value)
        ```
    """
    resolver = RefResolver(cache, actor=actor, fail_on_missing=fail_on_missing)

    args_result = resolver.resolve(args)
    kwargs_result = resolver.resolve(kwargs)

    return args_result, kwargs_result
