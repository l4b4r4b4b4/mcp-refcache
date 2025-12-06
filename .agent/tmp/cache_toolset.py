import time
import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
from system_2.cache.cache import (
    CacheReference,
    ToolsetCache,
    CacheDefaultResponse,
)
from system_2.cache.return_types import (
    ReturnOptions,
    ValueReturnType,
    ReferenceReturnType,
    PaginationParams,
)
from system_2.cache.redis_cache import RedisCompatibleCache
from system_2.doc_tools.options import with_tool_options

# Initialize FastMCP server
mcp = FastMCP(
    name="Cache Tools",
    description="Tools for working with cached values and references",
    version="0.0.1",
    dependencies=["pydantic>=2.0.0"],
)

# Setup logging
logger = logging.getLogger("cache_toolset")

ToolsetCache.register_cache_implementation(RedisCompatibleCache)

cache_tools_cache = ToolsetCache.get_cache_for_tool("cache_toolset")


# Define models for structured input/output
class ReferenceInput(BaseModel):
    reference: Union[str, Dict[str, Any], CacheReference] = Field(
        description="A cache reference object, reference ID, or dictionary with ref_id and cache_name"
    )


class CacheNameInput(BaseModel):
    cache_name: str = Field(description="Name of the cache to inspect")


class ReferenceValidityResult(BaseModel):
    valid: bool = Field(
        description="Whether the reference is valid and can be resolved"
    )
    reason: Optional[str] = Field(None, description="Reason if invalid")
    tool_name: Optional[str] = Field(
        None, description="Name of the tool that created the reference"
    )
    created_at: Optional[str] = Field(
        None, description="When the reference was created"
    )
    cache_type: Optional[str] = Field(
        None, description="Type of cache (deterministic or non-deterministic)"
    )
    expires_at: Optional[str] = Field(
        None, description="When the reference expires (for non-deterministic caches)"
    )


class ReferenceInfo(BaseModel):
    ref_id: str = Field(description="Unique identifier for the reference")
    tool_name: str = Field(description="Name of the tool that created the reference")
    preview: Optional[str] = Field(None, description="Preview of the cached value")
    created_at: str = Field(description="When the reference was created")
    valid: bool = Field(description="Whether the reference is currently valid")


# Options parameter for controlling return type
# class ReturnOptions(BaseModel):
#     value_type: ValueReturnType = Field(
#         default=ValueReturnType.DEFAULT,
#         description="Controls how the value is returned: 'default' for smart return (full or preview based on size), 'full' for complete value, 'preview' for a preview, None for no value",
#     )
#     reference_type: ReferenceReturnType = Field(
#         default=ReferenceReturnType.DEFAULT,
#         description="Controls how the reference is returned: 'default' for minimal ID, 'simple' for ID and cache name, 'full' for complete reference, None for no reference",
#     )
#     pagination: Optional[PaginationParams] = Field(
#         default=None,
#         description="Optional pagination parameters for value-returning responses",
#     )


@mcp.tool(description="Retrieve a cached value by its reference ID")
@cache_tools_cache.cached
@with_tool_options()
def get_cached_value(
    input_data: ReferenceInput,
    options: Optional[ReturnOptions] = None,
) -> Union[Any, str, CacheReference, CacheDefaultResponse]:
    """
    Retrieve the actual value from a cache reference.

    This essential tool allows you to access previously computed values
    without having to recalculate them. Use it whenever you need to
    refer to a value you obtained earlier as a reference.

    Parameters:
    - input_data: Configuration with these fields:
      - reference: A reference to the cached value. You can provide:
                - Just the reference ID as a string
                - A dictionary with "ref_id" and "cache_name" keys
                - A complete reference object from a previous result

    Returns:
    A response object containing:
    - value: The actual value (or preview or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)

    Example:
    ```
    # Retrieve a cached value using just a reference ID
    time_data = get_cached_value(input_data={"reference": "abc123def456"})
    ```
    """
    try:
        # Reference should already be resolved by the cache decorator
        # Just return the reference object itself
        return input_data.reference
    except ValueError as e:
        raise ValueError(f"Error retrieving cached value: {str(e)}")


@mcp.tool(description="Check if a cache reference is still valid")
@cache_tools_cache.cached
@with_tool_options()
def check_reference_validity(
    input_data: ReferenceInput,
    options: Optional[ReturnOptions] = None,
) -> Union[ReferenceValidityResult, str, CacheReference, CacheDefaultResponse]:
    """
    Check if a cache reference is still valid and can be resolved.

    This tool helps you determine if a reference you have is still usable
    or if it has expired. It's useful before attempting to use an older reference.

    Parameters:
    - input_data: Configuration with these fields:
      - reference: A reference to check. You can provide:
                - Just the reference ID as a string
                - A dictionary with "ref_id" and "cache_name" keys
                - A complete reference object from a previous result

    Returns:
    A response object containing:
    - value: The validity result (or preview or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)

    Example:
    ```
    # Check if a reference is still valid using just the reference ID
    validity = check_reference_validity(input_data={"reference": "abc123def456"})

    if validity["value"].valid:
        # Use the reference
        value = get_cached_value(input_data={"reference": "abc123def456"})
    else:
        # Handle expired reference
        print(f"Reference expired: {validity['value'].reason}")
    ```
    """
    # Now the cache decorator will have resolved reference automatically
    reference = input_data.reference

    try:
        # Ensure reference is a CacheReference object (it should be after automatic resolution)
        if not isinstance(reference, CacheReference):
            return ReferenceValidityResult(
                valid=False,
                reason=f"Invalid reference format: {reference}",
                tool_name=None,
                created_at=None,
                cache_type=None,
                expires_at=None,
            )

        # Get the cache associated with this reference
        cache = ToolsetCache.get_cache_by_name(reference.cache_name)
        if not cache:
            return ReferenceValidityResult(
                valid=False,
                reason=f"Cache '{reference.cache_name}' not found",
                tool_name=reference.tool_name,
                created_at=time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(reference.created_at)
                ),
                cache_type=None,
                expires_at=None,
            )

        # Find the reference in the registry (no need for partial matching now)
        if reference.ref_id not in cache.reference_registry:
            return ReferenceValidityResult(
                valid=False,
                reason="Reference ID not found in registry",
                tool_name=reference.tool_name,
                created_at=time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(reference.created_at)
                ),
                cache_type=None,
                expires_at=None,
            )

        # Get the cache key associated with the reference
        cache_key = cache.reference_registry[reference.ref_id]

        # Check if the key exists in the cache
        if not cache.contains(cache_key):
            return ReferenceValidityResult(
                valid=False,
                reason="Cache entry not found or expired",
                tool_name=reference.tool_name,
                created_at=time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(reference.created_at)
                ),
                cache_type="deterministic"
                if cache.deterministic
                else "non-deterministic",
                expires_at=None,
            )

        # Get the timestamp
        _, timestamp, *_ = cache.get(cache_key)

        # Check expiration if applicable
        if not cache.deterministic and cache.expiry_seconds is not None:
            if time.time() - timestamp >= cache.expiry_seconds:
                return ReferenceValidityResult(
                    valid=False,
                    reason="Reference expired",
                    tool_name=reference.tool_name,
                    created_at=time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(timestamp)
                    ),
                    expires_at=time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(timestamp + cache.expiry_seconds),
                    ),
                    cache_type="non-deterministic",
                )

        # Reference is valid
        return ReferenceValidityResult(
            valid=True,
            reason=None,
            tool_name=reference.tool_name,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
            cache_type="deterministic" if cache.deterministic else "non-deterministic",
            expires_at=None
            if cache.deterministic or cache.expiry_seconds is None
            else time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(timestamp + cache.expiry_seconds),
            ),
        )

    except Exception as e:
        # Safe extraction of tool_name and created_at
        tool_name = None
        created_at_str = None

        if isinstance(reference, CacheReference):
            tool_name = reference.tool_name
            if hasattr(reference, "created_at"):
                try:
                    created_at_str = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(reference.created_at)
                    )
                except (AttributeError, TypeError, ValueError):
                    pass

        return ReferenceValidityResult(
            valid=False,
            reason=f"Error checking reference: {str(e)}",
            tool_name=tool_name,
            created_at=created_at_str,
            cache_type=None,
            expires_at=None,
        )


@mcp.tool(description="Get a preview of a cached value")
@cache_tools_cache.cached
@with_tool_options()
def get_cache_preview(
    input_data: ReferenceInput,
    options: Optional[ReturnOptions] = None,
) -> Union[str, CacheReference, CacheDefaultResponse]:
    """
    Get a human-readable preview of a cached value without retrieving the full data.

    This tool is useful when you want to see what a reference contains
    without processing the complete object, which could be large.

    Parameters:
    - input_data: Configuration with these fields:
      - reference: A reference to preview. You can provide:
                - Just the reference ID as a string
                - A dictionary with "ref_id" and "cache_name" keys
                - A complete reference object from a previous result

    Returns:
    A response object containing:
    - value: The preview text (or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)

    Example:
    ```
    # Get a preview of what's in a reference
    preview = get_cache_preview(input_data={"reference": "abc123def456"})
    ```
    """
    try:
        reference = input_data.reference

        # The reference should already be resolved by the cache decorator
        if not isinstance(reference, CacheReference):
            return "Error: Invalid reference format"

        # Check if preview is allowed for this reference
        if "preview" not in reference.allowed_response_types:
            return "Preview not allowed for this reference"

        # Get preview from the cache system
        preview = ToolsetCache.get_preview_for_reference(reference)
        if preview:
            return f"Preview ({reference.tool_name}): {preview.preview_text}"

        # If no preview available, try resolving the reference and create a preview
        try:
            value = ToolsetCache.resolve_reference(reference)
            if isinstance(value, (dict, list, tuple)):
                preview_text = (
                    str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                )
            else:
                preview_text = str(value)
            return f"Preview ({reference.tool_name}): {preview_text}"
        except Exception as e:
            return f"Error creating preview: {str(e)}"
    except ValueError as e:
        raise ValueError(f"Error retrieving preview: {str(e)}")


@mcp.tool(description="List all available references in a cache")
@cache_tools_cache.cached
@with_tool_options(pagination=True, interpolation=True)  # Added pagination support
def list_cache_references(
    input_data: CacheNameInput, options: Optional[ReturnOptions] = None
) -> Union[List[ReferenceInfo], str, CacheReference, CacheDefaultResponse]:
    """
    List all available references in a specific cache.

    This tool helps you discover what references are available in a particular cache
    when you need to find previously computed values.

    Parameters:
    - input_data: Configuration with these fields:
      - cache_name: Name of the cache to inspect (e.g., "time_toolset", "math_toolset")

    Returns:
    A response object containing:
    - value: List of references (or preview or None depending on value_type)
    - reference: Reference details (or None depending on reference_type)

    Example:
    ```
    # See what time references are available
    time_refs = list_cache_references(input_data={"cache_name": "time_toolset"})

    # Get the shortest unique prefix for each reference (for easy use)
    for ref in time_refs["value"]:
        print(f"Reference ID: {ref.ref_id[:12]}...")
    ```
    """
    cache = ToolsetCache.get_cache_by_name(input_data.cache_name)
    if not cache:
        raise ValueError(f"Cache '{input_data.cache_name}' not found")

    references = []
    for ref_id, cache_key in cache.reference_registry.items():
        try:
            if cache.contains(cache_key):
                value, timestamp, _ = cache.get(cache_key)

                # Try to create a preview
                try:
                    if isinstance(value, (dict, list, tuple)):
                        preview_text = (
                            str(value)[:50] + "..."
                            if len(str(value)) > 50
                            else str(value)
                        )
                    else:
                        preview_text = str(value)
                except Exception as exc:
                    logger.warning(f"Could not generate preview: {exc}")
                    preview_text = "Preview unavailable"

                # Determine tool name (may not always be available)
                tool_name = "unknown"
                if ":" in cache_key:
                    tool_name = cache_key.split(":")[0]

                # Use the minimal unique reference ID prefix (at least 12 chars)
                min_unique_id = ref_id
                if hasattr(cache, "_get_minimal_unique_ref_id"):
                    min_ref_id = cache._get_minimal_unique_ref_id(ref_id)
                    # Ensure it's at least 12 characters
                    if len(min_ref_id) < 12 and len(ref_id) >= 12:
                        min_unique_id = ref_id[:12]
                    else:
                        min_unique_id = min_ref_id
                elif len(ref_id) > 12:
                    min_unique_id = ref_id[:12]

                references.append(
                    ReferenceInfo(
                        ref_id=min_unique_id,
                        tool_name=tool_name,
                        preview=preview_text,
                        created_at=time.strftime(
                            "%Y-%m-%d %H:%M:%S", time.localtime(timestamp)
                        ),
                        valid=True,
                    )
                )
        except Exception as e:
            # Skip invalid references
            logger.warning(f"Error processing reference {ref_id}: {str(e)}")
            continue

    return references


class ListCachesOptions(BaseModel):
    placeholder: Optional[bool] = Field(
        default=None, description="No specific input needed for this tool"
    )


@mcp.tool(description="List all available caches in the system")
@cache_tools_cache.cached
@with_tool_options(pagination=True, interpolation=True)  # Added pagination support
def list_caches(
    input_data: Optional[ListCachesOptions] = None,
    options: Optional[ReturnOptions] = None,
) -> Union[List[Dict[str, Any]], str, CacheReference, CacheDefaultResponse]:
    """
    List all registered caches in the system.

    This tool helps you understand what caches are available and their characteristics,
    so you can work with the most appropriate cache for your needs.

    Parameters:
    - input_data: No specific input required (optional)

    Returns:
    A response object containing:
    - value: List of caches (or preview or None depending on value_type)
    - reference: Reference details (or None depending on reference_type)

    Example:
    ```
    # Find out what caches are available
    caches = list_caches()
    # Find a deterministic cache for long-term storage
    deterministic_caches = [c for c in caches["value"] if c["deterministic"]]
    ```
    """
    caches = []
    for name, cache in ToolsetCache._cache_registry.items():
        caches.append(
            {
                "name": name,
                "deterministic": cache.deterministic,
                "expiry_seconds": cache.expiry_seconds,
                "max_size": cache.max_size,
                "total_entries": len(cache.cache),
                "total_references": len(cache.reference_registry),
                "cache_dir": cache.cache_dir if cache.deterministic else None,
            }
        )

    return caches


@mcp.tool(description="Get detailed statistics about a specific cache")
@cache_tools_cache.cached
@with_tool_options()
def get_cache_stats(
    input_data: CacheNameInput, options: Optional[ReturnOptions] = None
) -> Union[Dict[str, Any], str, CacheReference, CacheDefaultResponse]:
    """
    Get detailed statistics about a specific cache.

    This tool provides insight into how a particular cache is performing,
    including hit rates and usage patterns.

    Parameters:
    - input_data: Configuration with these fields:
      - cache_name: Name of the cache to inspect

    Returns:
    A response object containing:
    - value: Cache statistics (or preview or None depending on value_type)
    - reference: Reference details (or None depending on reference_type)

    Example:
    ```
    # Get stats for the time cache
    time_stats = get_cache_stats(input_data={"cache_name": "time_toolset"})
    ```
    """
    cache = ToolsetCache.get_cache_by_name(input_data.cache_name)
    if not cache:
        raise ValueError(f"Cache '{input_data.cache_name}' not found")

    return cache.get_stats()


@mcp.prompt()
def cache_toolset_guide() -> str:
    """A comprehensive guide for working with cache references and return types"""
    return """
    # Cache Tools Usage Guide

    This toolset provides utilities for working with cached values and references,
    helping you optimize your workflows and reduce redundant computations.

    ## How to Use References

    The caching system automatically resolves references at any nesting level in the input_data. You can simply use the reference ID directly:

    ```python
    # When you get a result with a reference
    result = some_tool(input_data={"param": "value"})

    # Use the reference ID directly in another tool call
    # Just pass the reference ID string where you would normally put a value
    get_cached_value(input_data={"reference": result["reference"]["ref_id"]})
    ```

    The cache system is smart enough to:

    1. Recognize reference IDs and automatically resolve them
    2. Handle nested references at any level in complex data structures
    3. Work with references from any cache (cross-cache resolution)

    ## Available Return Types

    All tools in this toolset support granular control over how values and references are returned:

    ```python
    options = {
        "value_type": "default",  # Controls how the value is returned
        "reference_type": "default",  # Controls how the reference is returned
        "pagination": {"page": 1, "page_size": 20}  # Optional pagination
    }
    ```

    ### Value Return Types:

    - `"default"`: Smart return - full for small results, preview for large ones (default)
    - `"full"`: Always return the complete value
    - `"preview"`: Always return a preview of the value
    - `None`: Don't return any value (reference only)

    ### Reference Return Types:

    - `"default"`: Return minimal reference ID (default)
    - `"simple"`: Return reference ID and cache name
    - `"full"`: Return complete reference details
    - `None`: Don't return any reference (value only)

    ## Example Workflow

    ```python
    # Get a list of all caches in the system
    caches = list_caches()

    # Find a specific reference
    time_refs = list_cache_references(input_data={"cache_name": "time_toolset"})

    # Check if a reference is still valid
    if time_refs and len(time_refs["value"]) > 0:
        first_ref_id = time_refs["value"][0].ref_id
        validity = check_reference_validity(input_data={"reference": first_ref_id})

        if validity["value"].valid:
            # Retrieve the actual value using just the reference ID
            value = get_cached_value(input_data={"reference": first_ref_id})
            print(f"Retrieved value: {value}")
        else:
            print(f"Reference invalid: {validity['value'].reason}")

    # Get statistics about a cache
    math_stats = get_cache_stats(input_data={"cache_name": "math_toolset"})
    ```

    ## Working with References in Responses

    When you receive a response with a reference, you'll typically see:

    ```
    {
      "value": {...},           # The actual value (if small enough)
      "reference": {            # Reference metadata
        "ref_id": "abc123def456",  # Reference ID (can be used in future calls)
        "cache_name": "math_toolset",
        ...
      }
    }
    ```

    Or with a preview for large values:

    ```
    {
      "value": {
        "type": "cache_preview",
        "preview_text": "Preview of the large value...",
        ...
      },
      "reference": {...}
    }
    ```

    You can use the reference ID directly in subsequent calls:

    ```python
    next_tool(input_data={"reference": response["reference"]["ref_id"]})
    ```

    ## Cache Selection Guidelines

    - **For permanent storage**: Use deterministic caches (e.g., math_toolset)
    - **For temporary values**: Use non-deterministic caches with expiry
    - **For large datasets**: Always use references instead of copying values
    - **For sharing values**: Pass references between different tools/toolsets

    ## Best Practices

    1. Check reference validity before using older references
    2. Use get_cache_preview() to see what's in a reference without retrieving the full data
    3. Monitor cache statistics to understand usage patterns
    4. Use the default return types to automatically handle large values efficiently
    5. You only need to provide at least the first few characters of a reference ID, as long as it's unique
    """


if __name__ == "__main__":
    mcp.run(transport="stdio")
