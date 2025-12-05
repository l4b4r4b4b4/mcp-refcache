import functools
import hashlib
import inspect
import json
import logging
import os
import pickle
import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import (
    Any,
    Optional,
    TypeVar,
    Union,
    cast,
)

from pydantic import BaseModel, ConfigDict, Field

from .return_types import (
    InterpolationParams,
    PaginationParams,
    ReferenceReturnType,
    ReturnOptions,
    ValueReturnType,
)

logger = logging.getLogger("mcp_cache")
logger.setLevel(logging.DEBUG)

# Enhanced JSONValue type to better document what's actually JSON-serializable
JSONValue = Union[
    None, bool, int, float, str, list["JSONValue"], dict[str, "JSONValue"]
]

# Then define CachableValue without direct self-reference
CachableValue = Union[
    JSONValue,
    BaseModel,
    tuple[Any, ...],  # Tuples can be converted to lists
    Enum,  # Enums can be converted to their values
    set[Any],  # Sets can be converted to lists
]


def make_json_serializable(value: Any) -> JSONValue:
    """Convert any value to a JSON-serializable form."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    elif isinstance(value, BaseModel):
        return value.model_dump()
    elif isinstance(value, Enum):
        return value.value  # Extract the enum value
    elif isinstance(value, (list, tuple)):
        return [make_json_serializable(item) for item in value]
    elif isinstance(value, dict):
        return {k: make_json_serializable(v) for k, v in value.items()}
    elif isinstance(value, set):
        return [make_json_serializable(item) for item in value]
    else:
        # Try JSON serialization as a test
        try:
            json.dumps(value)
            return cast("JSONValue", value)
        except (TypeError, OverflowError):
            # If it can't be serialized, convert to string
            return str(value)


# Return type for cached functions
ReturnT = TypeVar("ReturnT")


class PaginatedResponse(BaseModel):
    """Standard format for paginated responses"""

    items: Any = Field(description="The current page of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Number of items per page")
    total_pages: int = Field(description="Total number of pages")
    total_items: int = Field(description="Total number of items")
    has_next: bool = Field(description="Whether there are more pages")
    has_prev: bool = Field(description="Whether there are previous pages")

    model_config = ConfigDict(
        frozen=True,  # Make immutable
    )

    def __str__(self) -> str:
        """String representation of the paginated response"""
        return f"Page {self.page}/{self.total_pages} ({self.total_items} items)"

    def model_dump_for_mcp(self) -> dict[str, Any]:
        """Custom serialization method for MCP transport layer"""
        return {
            "type": "paginated_response",
            "items": self.items,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "total_items": self.total_items,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


class CacheDefaultResponse(BaseModel):
    """Default response format combining reference ID with either value or preview
    to prevent context overflow for large responses.
    """

    ref_id: str = Field(description="Reference ID for the cached value")
    cache_name: str = Field(description="Name of the cache where the value is stored")
    tool_name: str = Field(description="Name of the tool that generated the value")
    value: Any | None = Field(
        default=None, description="The actual value if small enough"
    )
    preview: str | None = Field(
        default=None, description="Preview of the value if too large"
    )
    is_preview: bool = Field(
        description="Whether this contains the full value or just a preview"
    )

    model_config = ConfigDict(
        frozen=True,  # Make immutable
    )

    def __str__(self) -> str:
        """String representation of the default response"""
        if self.is_preview:
            return f"Reference({self.ref_id[:8]}) with preview: {self.preview}"
        return f"Reference({self.ref_id[:8]}) with value"

    def model_dump_for_mcp(self) -> dict[str, Any]:
        """Custom serialization method for MCP transport layer"""
        return {
            "type": "cache_default_response",
            "ref_id": self.ref_id,
            "cache_name": self.cache_name,
            "tool_name": self.tool_name,
            "value": self.value if not self.is_preview else None,
            "preview": self.preview if self.is_preview else None,
            "is_preview": self.is_preview,
        }


class CacheReference(BaseModel):
    """Object representing a reference to a cached value without exposing any details.
    """

    cache_name: str = Field(
        description="Name of the cache where the referenced value is stored"
    )
    ref_id: str = Field(description="Unique identifier for this reference in the cache")
    tool_name: str = Field(
        description="Name of the tool that generated the cached value"
    )
    created_at: float = Field(
        default_factory=time.time,
        description="Timestamp when this reference was created",
    )
    allowed_response_types: frozenset[str] = Field(
        default=frozenset({"full", "preview", "reference"}),
        description="Which response types are allowed when using this reference",
    )

    model_config = ConfigDict(
        frozen=True,  # Make references immutable
        extra="forbid",  # Prevent any extra attributes
    )

    def __str__(self) -> str:
        """String representation of the reference for debugging"""
        return f"CacheReference(id={self.ref_id[:8]}, cache={self.cache_name}, tool={self.tool_name})"

    def model_dump_for_mcp(self) -> dict[str, Any]:
        """Custom serialization method for MCP transport layer"""
        return {
            "type": "cache_reference",
            "ref_id": self.ref_id,
            "cache_name": self.cache_name,
            "tool_name": self.tool_name,
            "created_at": self.created_at,
            "allowed_response_types": list(self.allowed_response_types),
        }


class CachePreview(BaseModel):
    """Separate class for previewing cached values without exposing the full reference.

    This provides a safe way to get a glimpse of what's in a cache without exposing
    the full value or reference details.
    """

    preview_text: str = Field(description="Short textual preview of the cached value")
    tool_name: str = Field(
        description="Name of the tool that generated the cached value"
    )

    model_config = ConfigDict(
        frozen=True  # Make previews immutable
    )

    def __str__(self) -> str:
        """String representation of the preview"""
        return f"Preview({self.tool_name}): {self.preview_text}"

    def model_dump_for_mcp(self) -> dict[str, Any]:
        """Custom serialization method for MCP transport layer"""
        return {
            "type": "cache_preview",
            "preview_text": self.preview_text,
            "tool_name": self.tool_name,
        }


class CacheStats(BaseModel):
    """Statistics about cache usage and performance.

    Tracks hits, misses, and other metrics to help optimize cache usage.
    """

    name: str = Field(description="Name of the cache")
    deterministic: bool = Field(description="Whether this cache is deterministic")
    hits: int = Field(default=0, description="Number of cache hits")
    misses: int = Field(default=0, description="Number of cache misses")
    expirations: int = Field(default=0, description="Number of expired entries removed")
    references_used: int = Field(default=0, description="Number of references resolved")
    total_entries: int = Field(
        default=0, description="Current number of entries in cache"
    )
    total_references: int = Field(default=0, description="Current number of references")
    max_size: int | None = Field(description="Maximum cache size (entries)")
    expiry_seconds: float | None = Field(description="Entry expiry time in seconds")

    @property
    def hit_rate(self) -> str:
        """Calculate the hit rate as a percentage string"""
        total = self.hits + self.misses
        if total == 0:
            return "0.00%"
        return f"{(self.hits / total) * 100:.2f}%"

    @property
    def current_usage(self) -> str:
        """Calculate current cache usage as a percentage string"""
        if not self.max_size:
            return "N/A"
        return f"{(self.total_entries / self.max_size) * 100:.2f}%"


class ToolsetCache:
    """Reusable caching mechanism for MCP toolsets with disk persistence for deterministic caches.

    Supports reference-based access, allowing values to be passed between tools without
    exposing the actual data, and different return types (full, preview, reference).
    """

    # Class-level base directory for all caches
    BASE_CACHE_DIR = ".cache"

    # Class-level registry of all cache instances
    _cache_registry: dict[str, "ToolsetCache"] = {}
    _cache_implementation = None

    def __init__(
        self,
        name: str,
        deterministic: bool = False,
        expiry_seconds: int | float | None = 3600,  # Only used for non-deterministic caches
        max_size: int | None = 10000,
        cache_dir: str | None = None,  # Optional
        flush_interval: int | None = 60 * 60,  # 1 hour = 60 minutes = 3600 s
    ):
        """Initialize a cache for a specific toolset.

        Parameters:
        - name: Name of the toolset for logging
        - deterministic: Whether this cache contains deterministic results that can be persisted
        - expiry_seconds: Cache expiry time in seconds (only for non-deterministic caches)
                         Set to None for indefinite caching
        - max_size: Maximum number of items to keep in cache (default: 10000)
                   Set to None for unlimited cache size
        - cache_dir: Directory to store persistent cache files (default: auto-generated from name)
        - flush_interval: How often to flush deterministic caches to disk (in seconds)
                         Set to None to disable periodic flushing
        """
        self.name = name
        self.deterministic = deterministic

        # Register this cache instance globally
        ToolsetCache._cache_registry[name] = self

        # For deterministic caches, override expiry_seconds to None (never expire)
        self.expiry_seconds = None if deterministic else expiry_seconds

        if deterministic and expiry_seconds is not None:
            logger.warning(
                f"Ignoring expiry_seconds for deterministic cache {name}. "
                f"Deterministic caches do not expire."
            )

        self.max_size = max_size
        self.flush_interval = flush_interval

        # Initialize stats
        self.stats = {"hits": 0, "misses": 0, "expirations": 0, "references_used": 0}

        # Main cache storage: {key: (value, timestamp)}
        self.cache: dict[str, tuple[Any, float, str]] = {}

        # Reference registry: {ref_id: cache_key}
        self.reference_registry: dict[str, str] = {}

        # Track access order for LRU eviction policy
        self.access_order: list[str] = []

        # Thread lock for thread safety
        self._cache_lock = threading.RLock()

        # Auto-generate cache directory if not specified
        if cache_dir is None and deterministic:
            # Convert the name to a directory-friendly format
            dir_name = (
                name.replace("/", "_")
                .replace("\\", "_")
                .replace(" ", "_")
                .replace(":", "_")
            )
            # Add any domain or category structure from the name
            if "." in dir_name:
                # Use dots as directory separators (e.g., "api.users" -> "api/users")
                path_parts = dir_name.split(".")
                self.cache_dir = os.path.join(self.BASE_CACHE_DIR, *path_parts)
            else:
                self.cache_dir = os.path.join(self.BASE_CACHE_DIR, dir_name)
        else:
            self.cache_dir = cache_dir

        # Create cache directory if it doesn't exist and this is a deterministic cache
        if self.deterministic and self.cache_dir and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            logger.debug(f"Created cache directory: {self.cache_dir}")

        # Load existing cache from disk if deterministic
        if self.deterministic and self.cache_dir:
            self._load_from_disk()

            # Start periodic flush thread if this is a deterministic cache and flush_interval is set
            if flush_interval is not None:
                self._start_periodic_flush()

        logger.info(
            f"Initialized cache '{name}' "
            f"(deterministic={deterministic}, "
            f"{'' if deterministic else ('expiry=' + (str(expiry_seconds) if expiry_seconds is not None else 'indefinite') + 's, ')}"
            f"max_size={max_size if max_size is not None else 'unlimited'})"
        )

    @classmethod
    def register_cache_implementation(cls, implementation_class):
        """Register a cache implementation class to use for all new caches"""
        cls._cache_implementation = implementation_class
        logger.info(f"Registered cache implementation: {implementation_class.__name__}")

    @classmethod
    def set_base_cache_dir(cls, directory: str) -> None:
        """Set the base directory for all caches"""
        cls.BASE_CACHE_DIR = directory
        logger.info(f"Set base cache directory to: {directory}")

    @classmethod
    def get_cache_by_name(cls, name: str) -> Optional["ToolsetCache"]:
        """Get a cache instance by name"""
        return cls._cache_registry.get(name)

    def _get_cache_key_for_ref(self, ref_id: str) -> str | None:
        """Get the cache key for a reference ID.
        Default implementation for in-memory cache.
        Subclasses may override for different storage backends.
        """
        return self.reference_registry.get(ref_id)

    @classmethod
    def resolve_reference(cls, ref: CacheReference | str | dict[str, Any]) -> Any:
        """Resolve a reference to its cached value.
        Reference can be:
        1. A CacheReference object
        2. A string reference ID
        3. A dict with at least ref_id and cache_name
        """
        with threading.RLock():  # Global lock for reference resolution
            # Convert string ID to CacheReference object if needed
            if isinstance(ref, str):
                # Find the cache that contains this reference
                for cache_name, cache in cls._cache_registry.items():
                    matching_refs = [
                        full_id
                        for full_id in cache.reference_registry.keys()
                        if full_id.startswith(ref)
                    ]
                    if len(matching_refs) == 1:
                        ref = CacheReference(
                            ref_id=matching_refs[0],
                            cache_name=cache_name,
                            tool_name="<auto-resolved>",
                            created_at=time.time(),
                        )
                        break
                else:
                    # No match found in any cache
                    raise ValueError(f"Reference ID '{ref}' not found in any cache")

            # Convert dict to CacheReference object if needed
            elif isinstance(ref, dict) and "ref_id" in ref and "cache_name" in ref:
                ref = CacheReference(
                    ref_id=ref["ref_id"],
                    cache_name=ref["cache_name"],
                    tool_name=ref.get("tool_name", "<auto-resolved>"),
                    created_at=ref.get("created_at", time.time()),
                )

            # Now we should have a proper CacheReference object
            if not isinstance(ref, CacheReference):
                raise ValueError(f"Invalid reference type: {type(ref)}")

            # Get the cache
            cache = cls.get_cache_by_name(ref.cache_name)
            if not cache:
                raise ValueError(f"Cache '{ref.cache_name}' not found")

            # Find the full reference ID if a prefix was provided
            ref_id = ref.ref_id
            if ref_id not in cache.reference_registry:
                matching_refs = [
                    full_id
                    for full_id in cache.reference_registry.keys()
                    if full_id.startswith(ref_id)
                ]
                if len(matching_refs) == 1:
                    ref_id = matching_refs[0]
                else:
                    raise ValueError(
                        f"Reference ID '{ref_id}' not found or ambiguous in cache '{ref.cache_name}'"
                    )

            # Get the cache key
            cache_key = cache.reference_registry.get(ref_id)
            if not cache_key:
                raise ValueError(
                    f"Reference ID '{ref_id}' not found in cache '{ref.cache_name}'"
                )

            # Get the value
            try:
                value, *_ = cache.get(cache_key)

                # Update stats
                if hasattr(cache, "_update_stats_in_redis"):
                    cache._update_stats_in_redis(references_used=1)
                else:
                    # Use the standard stats update if available
                    if hasattr(cache, "stats"):
                        cache.stats["references_used"] += 1

                logger.debug(f"Resolved reference {ref_id} from cache {ref.cache_name}")
                return value
            except KeyError:
                raise ValueError(
                    f"Cache key not found for reference '{ref_id}' in cache '{ref.cache_name}'"
                )

    def _paginate_value(
        self, value: Any, pagination: PaginationParams
    ) -> PaginatedResponse:
        """Paginate any value type, handling different data structures appropriately.
        Returns a PaginatedResponse object.
        """
        # Default values
        page = pagination.page
        page_size = pagination.page_size

        # Handle different types of values
        if isinstance(value, list):
            # For lists, paginate the items directly
            total_items = len(value)
            total_pages = max(1, (total_items + page_size - 1) // page_size)
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_items)
            items = value[start_idx:end_idx]

        elif isinstance(value, dict):
            # For dictionaries, paginate the keys and create a sub-dictionary
            keys = list(value.keys())
            total_items = len(keys)
            total_pages = max(1, (total_items + page_size - 1) // page_size)
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_items)

            # Extract the subset of keys for this page
            page_keys = keys[start_idx:end_idx]
            items = {k: value[k] for k in page_keys}

        elif isinstance(value, tuple):
            # Convert tuple to list and paginate
            total_items = len(value)
            total_pages = max(1, (total_items + page_size - 1) // page_size)
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_items)
            items = list(
                value[start_idx:end_idx]
            )  # Convert to list for JSON serialization

        elif isinstance(value, set):
            # Convert set to list and paginate
            value_list = list(value)
            total_items = len(value_list)
            total_pages = max(1, (total_items + page_size - 1) // page_size)
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_items)
            items = value_list[start_idx:end_idx]

        elif isinstance(value, Enum):
            # For Enums, just return a single item (not paginated)
            total_items = 1
            total_pages = 1
            items = value.value if page == 1 else None

        elif hasattr(value, "__iter__") and not isinstance(
            value, (str, bytes, BaseModel)
        ):
            # For other iterables (not strings or bytes), convert to list first
            try:
                value_list = list(value)
                return self._paginate_value(value_list, pagination)
            except Exception as e:
                # If conversion fails, treat as a single item
                logger.debug(f"Failed to convert value to list: {e}")
                total_items = 1
                total_pages = 1
                items = value if page == 1 else None

        elif isinstance(value, BaseModel):
            # For Pydantic models, paginate the dict representation
            model_dict = value.model_dump()
            paginated_dict = self._paginate_value(model_dict, pagination)
            return paginated_dict

        else:
            # For non-iterable types (or types we don't handle specially),
            # return a single item or nothing based on page
            total_items = 1
            total_pages = 1
            items = value if page == 1 else None

        # Create and return the paginated response
        return PaginatedResponse(
            items=items,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    def _interpolate_value(self, value: Any, interpolation: InterpolationParams) -> Any:
        """Interpolate (sample) values from a collection based on interpolation parameters.
        Returns evenly spaced elements from list-like objects.
        """
        # If interpolation is disabled, return the original value
        if not interpolation.enabled:
            return value

        # Handle different types of collections
        if isinstance(value, (list, tuple, set)):
            # Convert to list if it's not already
            collection = list(value)
            collection_len = len(collection)

            # Don't interpolate if collection is too small
            if collection_len <= interpolation.min_size_to_interpolate:
                return collection

            # Calculate the step size to get `sample_count` samples
            sample_count = min(interpolation.sample_count, collection_len)

            # Handle edge cases
            if sample_count <= 1:
                return collection[:1]  # Return just the first element

            # For 2 samples and include_endpoints=True, return first and last
            if sample_count == 2 and interpolation.include_endpoints:
                return [collection[0], collection[-1]]

            # Create the interpolated list
            if interpolation.include_endpoints:
                # If including endpoints, we need to adjust sample spacing
                if sample_count == 2:
                    return [collection[0], collection[-1]]

                # Calculate step size between interior points
                interior_samples = sample_count - 2
                if interior_samples <= 0:
                    return [collection[0], collection[-1]]

                step = (collection_len - 1) / (interior_samples + 1)

                # Create list with first element, evenly spaced interior elements, and last element
                result = [collection[0]]
                for i in range(1, interior_samples + 1):
                    idx = min(int(i * step), collection_len - 1)
                    result.append(collection[idx])
                result.append(collection[-1])
                return result
            else:
                # Without endpoints constraint, just take evenly spaced samples
                step = collection_len / sample_count
                return [
                    collection[min(int(i * step), collection_len - 1)]
                    for i in range(sample_count)
                ]

        elif isinstance(value, dict):
            # For dictionaries, interpolate the keys, then create a sub-dictionary
            keys = list(value.keys())
            interpolated_keys = self._interpolate_value(keys, interpolation)
            return {k: value[k] for k in interpolated_keys}

        elif hasattr(value, "__iter__") and not isinstance(
            value, (str, bytes, BaseModel)
        ):
            # For other iterables that aren't strings or bytes, convert to list first
            try:
                as_list = list(value)
                return self._interpolate_value(as_list, interpolation)
            except Exception:
                # If conversion fails, return unmodified
                return value

        elif isinstance(value, BaseModel):
            # For Pydantic models, interpolate the dict representation
            model_dict = value.model_dump()
            interpolated_dict = self._interpolate_value(model_dict, interpolation)
            return interpolated_dict

        else:
            # For non-interpolatable values, return as is
            return value

    @classmethod
    def get_preview_for_reference(cls, ref: CacheReference) -> CachePreview | None:
        """Get a preview for a reference, but only when explicitly requested.
        This keeps the reference and preview completely separate.
        """
        if "preview" not in ref.allowed_response_types:
            logger.warning(f"Preview not allowed for reference {ref.ref_id}")
            return None

        with threading.RLock():  # Global lock for reference lookup
            cache = cls.get_cache_by_name(ref.cache_name)
            if not cache:
                return None

            cache_key = cache.reference_registry.get(ref.ref_id)
            if not cache_key:
                return None

            try:
                value, *_ = cache.get(cache_key)
                preview_text = cache._create_preview(value)
                return CachePreview(preview_text=preview_text, tool_name=ref.tool_name)
            except KeyError:
                return None

    @classmethod
    def get_cache_for_tool(cls, toolset_name: str) -> "ToolsetCache":
        """Get the appropriate cache for a given toolset.

        This is the recommended way to get a cache instance for a tool instead of
        directly initializing a new cache.
        """
        # If we have a registered implementation class, use that instead
        if cls._cache_implementation is not None and cls._cache_implementation != cls:
            return cls._cache_implementation.get_cache_for_tool(toolset_name)

        # Default implementation (original method continues below)
        if toolset_name in cls._cache_registry:
            return cls._cache_registry[toolset_name]

        # If no cache exists in the registry, create a new one with default settings
        if toolset_name.endswith("_toolset"):
            is_deterministic = toolset_name.startswith(
                "math"
            )  # Math toolsets are deterministic
            expiry = None if is_deterministic else 3600

            logger.info(
                f"Creating new cache for {toolset_name} (deterministic={is_deterministic})"
            )

            # Create a new cache with appropriate settings
            cache = cls(
                name=toolset_name,
                deterministic=is_deterministic,
                expiry_seconds=expiry,
                max_size=10000,  # Default max size
            )

            return cache

        # Fallback for unknown toolsets
        logger.warning(f"Unknown toolset: {toolset_name}, creating generic cache")
        return cls(name=toolset_name, deterministic=False)

    @classmethod
    def initialize_all_caches(cls):
        """Initialize all registered caches, loading deterministic ones from disk.
        This should be called during application startup.
        """
        logger.info("Initializing all registered caches...")

        # Ensure the base cache directory exists
        os.makedirs(cls.BASE_CACHE_DIR, exist_ok=True)

        # Load all deterministic caches from disk
        for name, cache in cls._cache_registry.items():
            if cache.deterministic and cache.cache_dir:
                logger.info(f"Loading deterministic cache from disk: {name}")
                cache._load_from_disk()

        logger.info(f"Initialized {len(cls._cache_registry)} caches")

        return list(cls._cache_registry.keys())

    def get(self, key: str) -> tuple[Any, float, str]:
        """Get a value, timestamp and reference ID from the cache, or raise KeyError if not found"""
        with self._cache_lock:
            if key not in self.cache:
                raise KeyError(f"Key {key} not found in cache")

            value, timestamp, ref_id = self.cache[key]

            # Check if expired for non-deterministic caches
            if not self.deterministic and self.expiry_seconds is not None:
                if time.time() - timestamp > self.expiry_seconds:
                    self.stats["expirations"] += 1
                    del self.cache[key]
                    if key in self.access_order:
                        self.access_order.remove(key)
                    raise KeyError(f"Key {key} has expired")

            # Update access order for LRU policy
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

            return value, timestamp, ref_id

    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache"""
        with self._cache_lock:
            timestamp = time.time()

            # Generate a consistent reference ID based on cache key and value
            # This is the critical part to ensure consistent IDs
            ref_id = self._generate_reference_id(key, value)

            # Store value with timestamp and reference ID
            self.cache[key] = (value, timestamp, ref_id)

            # Also store in reference registry
            self.reference_registry[ref_id] = key

            # Update access order for LRU policy
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

            # Trim if necessary
            if self.max_size is not None and len(self.cache) > self.max_size:
                self._trim_cache()

    def contains(self, key: str) -> bool:
        """Check if a key exists in the cache"""
        with self._cache_lock:
            if key not in self.cache:
                return False

            # For non-deterministic caches, check if expired
            if not self.deterministic and self.expiry_seconds is not None:
                # Unpack the 3-tuple correctly
                _, timestamp, _ = self.cache[key]
                if time.time() - timestamp > self.expiry_seconds:
                    self.stats["expirations"] += 1
                    del self.cache[key]
                    if key in self.access_order:
                        self.access_order.remove(key)
                    return False

            return True

    def _trim_cache(self) -> None:
        """Trim the cache to max_size by removing oldest entries (LRU policy)"""
        with self._cache_lock:
            if not self.max_size or len(self.cache) <= self.max_size:
                return

            # Calculate how many items to remove (25% of max size)
            remove_count = max(1, int(self.max_size * 0.25))

            # Get oldest keys using access order
            keys_to_remove = self.access_order[:remove_count]

            # Remove from cache and access order
            for key in keys_to_remove:
                if key in self.cache:
                    del self.cache[key]

            # Update access order
            self.access_order = self.access_order[remove_count:]

            logger.debug(
                f"Trimmed {len(keys_to_remove)} oldest entries from {self.name} cache"
            )

    def _get_cache_filepath(self) -> str | None:
        """Get the filepath for the cache file"""
        if not self.cache_dir:
            return None

        safe_name = os.path.basename(self.name).replace("/", "_").replace("\\", "_")
        return os.path.join(self.cache_dir, f"{safe_name}_cache.pkl")

    def _get_registry_filepath(self) -> str | None:
        """Get the filepath for the reference registry file"""
        if not self.cache_dir:
            return None

        safe_name = os.path.basename(self.name).replace("/", "_").replace("\\", "_")
        return os.path.join(self.cache_dir, f"{safe_name}_registry.pkl")

    def _load_from_disk(self) -> None:
        """Load cache and registry from disk if they exist"""
        if not self.deterministic or not self.cache_dir:
            return

        # Load cache data
        filepath = self._get_cache_filepath()
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    loaded_cache = pickle.load(f)
                    with self._cache_lock:
                        self.cache = loaded_cache
                    logger.info(f"Loaded {len(self.cache)} items from {filepath}")
            except Exception as e:
                logger.error(f"Error loading cache from {filepath}: {e}")

        # Load reference registry
        registry_filepath = self._get_registry_filepath()
        if registry_filepath and os.path.exists(registry_filepath):
            try:
                with open(registry_filepath, "rb") as f:
                    loaded_registry = pickle.load(f)
                    with self._cache_lock:
                        self.reference_registry = loaded_registry
                    logger.info(
                        f"Loaded {len(self.reference_registry)} references from {registry_filepath}"
                    )
            except Exception as e:
                logger.error(f"Error loading registry from {registry_filepath}: {e}")

    def _flush_to_disk(self) -> None:
        """Flush the cache and registry to disk"""
        if not self.deterministic or not self.cache_dir:
            return

        # Flush cache data
        filepath = self._get_cache_filepath()
        if filepath:
            try:
                with self._cache_lock, open(filepath, "wb") as f:
                    pickle.dump(self.cache, f)
                logger.info(f"Flushed {len(self.cache)} items to {filepath}")
            except Exception as e:
                logger.error(f"Error flushing cache to {filepath}: {e}")

        # Flush reference registry
        registry_filepath = self._get_registry_filepath()
        if registry_filepath:
            try:
                with self._cache_lock:
                    with open(registry_filepath, "wb") as f:
                        pickle.dump(self.reference_registry, f)
                logger.info(
                    f"Flushed {len(self.reference_registry)} references to {registry_filepath}"
                )
            except Exception as e:
                logger.error(f"Error flushing registry to {registry_filepath}: {e}")

    def _start_periodic_flush(self) -> None:
        """Start a background thread to periodically flush the cache to disk"""
        if not self.deterministic or self.flush_interval is None or not self.cache_dir:
            return

        def flush_periodically():
            while True:
                # Safe float conversion
                interval = (
                    float(self.flush_interval)
                    if self.flush_interval is not None
                    else 3600.0
                )
                time.sleep(interval)
                self._flush_to_disk()

        flush_thread = threading.Thread(
            target=flush_periodically,
            daemon=True,  # Make thread exit when the main program exits
            name=f"cache-flush-{self.name}",
        )
        flush_thread.start()
        logger.info(
            f"Started periodic flush thread for {self.name} (interval: {self.flush_interval}s)"
        )

    def _generate_reference_id(self, cache_key: str, value: Any) -> str:
        """Generate a unique, deterministic reference ID for a cached value.
        Ensure this method doesn't use timestamps or other non-deterministic elements.
        """
        # Create a composite that depends only on cache name, key, and value
        composite = f"{self.name}:{cache_key}"

        # Use SHA-256 to generate a unique, deterministic ID
        ref_id = hashlib.sha256(composite.encode()).hexdigest()
        return ref_id

    def _create_preview(self, value: Any) -> str:
        """Create a short preview of the cached value for internal use only"""
        try:
            if isinstance(value, dict):
                # For dictionaries, show a few key-value pairs
                preview_items = list(value.items())[:2]
                preview = "{" + ", ".join(
                    f"{k}: {str(v)[:20]}" for k, v in preview_items
                )
                if len(value) > 2:
                    preview += ", ..."
                preview += "}"
                return preview
            elif isinstance(value, list):
                # For lists, show a few items
                preview = "[" + ", ".join(str(item)[:20] for item in value[:2])
                if len(value) > 2:
                    preview += ", ..."
                preview += "]"
                return preview
            else:
                # For other types, just convert to string and truncate
                preview = str(value)
                if len(preview) > 50:
                    preview = preview[:47] + "..."
                return preview
        except Exception:
            return "Preview unavailable"

    def _get_minimal_unique_ref_id(self, ref_id: str) -> str:
        """Return the shortest unique prefix of the reference ID.
        Similar to how Git and Docker handle IDs.
        """
        # Start with at least 3 characters (was 8, making it too long)
        min_length = 3

        # Try increasing lengths until we find a unique prefix
        for length in range(min_length, len(ref_id) + 1):
            prefix = ref_id[:length]

            # Check if this prefix is unique in the reference registry
            matches = [
                r for r in self.reference_registry.keys() if r.startswith(prefix)
            ]
            if len(matches) == 1:
                return prefix

        # If we couldn't find a unique prefix, return the full ID
        return ref_id

    def handle_return_value(
        self,
        result: Any,
        options: ReturnOptions | dict[str, Any] | None = None,
        tool_name: str | None = None,
        ref_id: str | None = None,
    ) -> dict[str, Any]:
        """Prepares the return value with value and reference fields based on the provided options.

        This method controls how values and references are returned based on the options
        specified. It intelligently handles different return formats and ensures that
        only the data specified in the options is included in the response.

        Args:
            result: The result to process
            options: Controls how value and reference are returned
            tool_name: The name of the tool that generated this result
            ref_id: The reference ID for this result (if already generated)

        Returns:
            Dict with "value" and "reference" fields, each potentially None
        """
        # Convert dict to ReturnOptions if needed or use default options
        if options is None:
            options = ReturnOptions()
        elif isinstance(options, dict):
            options = ReturnOptions.from_dict(options)

        # Generate a cache key and reference ID if not provided
        if ref_id is None:
            cache_key = f"{result.__class__.__name__}:{id(result)}"
            ref_id = self._generate_reference_id(cache_key, result)

            # Store in reference registry
            with self._cache_lock:
                self.reference_registry[ref_id] = cache_key

        # Create basic response structure
        response = {}
        response["value"] = None
        response["reference"] = None

        # Use the provided tool_name, get it from the result, or use a default
        actual_tool_name = "<unknown>"
        if tool_name is not None:
            actual_tool_name = tool_name
        elif hasattr(result, "tool_name"):
            actual_tool_name = result.tool_name

        # Determine processing based on exactly which fields are specified in options
        # Case 1: No options specified (None or ReturnOptions with defaults)
        if options is None or (
            options.value_type is None and options.reference_type is None
        ):
            # Process both with defaults
            process_value = True
            value_type = ValueReturnType.DEFAULT
            process_reference = True
            reference_type = ReferenceReturnType.DEFAULT
        # Case 2: Only value_type specified
        elif options.value_type is not None and options.reference_type is None:
            process_value = True
            value_type = options.value_type
            process_reference = True
            reference_type = ReferenceReturnType.DEFAULT
        # Case 3: Only reference_type specified
        elif options.value_type is None and options.reference_type is not None:
            process_value = False
            value_type = None
            process_reference = True
            reference_type = options.reference_type
        # Case 4: Both specified
        else:
            process_value = options.value_type is not None
            value_type = options.value_type
            process_reference = options.reference_type is not None
            reference_type = options.reference_type

        # Process value when needed
        if process_value and value_type is not None:
            if value_type == ValueReturnType.FULL:
                # Apply interpolation if requested (before pagination)
                processed_result = result
                if options.interpolation and not isinstance(
                    processed_result, (CachePreview, CacheReference)
                ):
                    processed_result = self._interpolate_value(
                        processed_result, options.interpolation
                    )

                # Apply pagination if requested
                if options.pagination and not isinstance(
                    processed_result, (CachePreview, CacheReference)
                ):
                    internal_pagination = PaginationParams(
                        page=options.pagination.page,
                        page_size=options.pagination.page_size,
                    )
                    paginated_result = self._paginate_value(
                        processed_result, internal_pagination
                    )
                    response["value"] = make_json_serializable(paginated_result)
                else:
                    response["value"] = make_json_serializable(processed_result)

            elif value_type == ValueReturnType.PREVIEW:
                # Always return a preview
                if isinstance(result, CachePreview):
                    # Already a preview
                    response["value"] = result.model_dump_for_mcp()
                else:
                    # Create a preview
                    preview_text = self._create_preview(result)
                    preview = CachePreview(
                        preview_text=preview_text,
                        tool_name=actual_tool_name,
                    )
                    response["value"] = preview.model_dump_for_mcp()

            elif value_type == ValueReturnType.DEFAULT:
                # Smart logic - return full for small values, paginated/preview for large ones
                result_str = str(result)
                is_large = len(result_str) > 500  # Threshold for "large"

                if is_large:
                    # For large results, include a preview
                    preview_text = self._create_preview(result)
                    preview = CachePreview(
                        preview_text=preview_text,
                        tool_name=actual_tool_name,
                    )
                    response["value"] = preview.model_dump_for_mcp()
                else:
                    # Apply interpolation if requested (before pagination)
                    processed_result = result
                    if options.interpolation and not isinstance(
                        processed_result, (CachePreview, CacheReference)
                    ):
                        processed_result = self._interpolate_value(
                            processed_result, options.interpolation
                        )

                    # For small results, include full value with pagination if requested
                    if options.pagination and not isinstance(
                        processed_result, (CachePreview, CacheReference)
                    ):
                        internal_pagination = PaginationParams(
                            page=options.pagination.page,
                            page_size=options.pagination.page_size,
                        )
                        paginated_result = self._paginate_value(
                            processed_result, internal_pagination
                        )
                        response["value"] = make_json_serializable(paginated_result)
                    else:
                        response["value"] = make_json_serializable(processed_result)

        # Process reference when needed
        if process_reference and reference_type is not None:
            if reference_type == ReferenceReturnType.FULL:
                # Return complete reference object
                response["reference"] = {
                    "type": "cache_reference",
                    "ref_id": ref_id,
                    "cache_name": self.name,
                    "tool_name": actual_tool_name,
                    "created_at": time.time(),
                    "allowed_response_types": [rt.value for rt in ValueReturnType],
                }

            elif reference_type == ReferenceReturnType.SIMPLE:
                # Return simplified reference with just ID and cache name
                response["reference"] = {
                    "ref_id": ref_id,
                    "cache_name": self.name,
                }

            elif reference_type == ReferenceReturnType.DEFAULT:
                # Return minimal reference with just ID
                response["reference"] = {"ref_id": ref_id}

        return response

    def cached(self, func: Callable[..., ReturnT]) -> Callable[..., Any]:
        """Decorator that caches function results with granular control over return values.

        This decorator wraps functions to provide caching and reference capabilities.
        When a function is called, it first checks if the result is already cached.
        If found, it returns the cached result; otherwise, it executes the function
        and caches the result for future use.

        The decorated function can be called with an additional parameter:
        - options: contains value_type, reference_type, and pagination parameters

        Value return types:
        - "default": Smart return - full value for small results, preview for large ones
        - "preview": Always return a preview of the result
        - "full": Always return the complete result
        - If not specified: No value is returned

        Reference return types:
        - "default": Return just the reference ID
        - "simple": Return reference ID and cache name
        - "full": Return complete reference details
        - If not specified: No reference is returned

        Pagination can be used with value-returning types (default, full).

        Supports both sync and async functions.

        Returns:
            A wrapped function that implements caching behavior
        """
        # Check if the function is async
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self._execute_cached_async(func, args, kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return self._execute_cached_sync(func, args, kwargs)

            return sync_wrapper

    def cached_unwrapped(self, func: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
        """Decorator that caches function results but returns only the raw value.

        This is designed for MCP tools and other contexts where the wrapped
        dict format (with 'value' and 'reference' keys) is not desired.
        Caching still happens, but the return value is just the cached data.

        Supports both sync and async functions.

        Returns:
            A wrapped function that implements caching behavior with unwrapped returns
        """
        # Check if the function is async
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await self._execute_cached_async(func, args, kwargs)
                # Unwrap the result - if it's a dict with 'value', return just the value
                if isinstance(result, dict) and "value" in result:
                    return result["value"]
                return result

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                result = self._execute_cached_sync(func, args, kwargs)
                # Unwrap the result - if it's a dict with 'value', return just the value
                if isinstance(result, dict) and "value" in result:
                    return result["value"]
                return result

            return sync_wrapper

    async def _execute_cached_async(
        self, func: Callable, args: tuple, kwargs: dict
    ) -> Any:
        """Execute an async cached function call.

        This internal method handles the actual caching logic for async functions.
        """
        # Initialize result to None to ensure it's always bound
        result = None
        ref_id = None

        # Extract options if present - but don't include in cache key
        options_input = kwargs.pop("options", None)  # Remove from kwargs
        options = None

        if options_input:
            try:
                if isinstance(options_input, dict):
                    # Handle dictionary-style options
                    options = ReturnOptions.from_dict(options_input)
                elif hasattr(options_input, "value_type") and hasattr(
                    options_input, "reference_type"
                ):
                    # It's already a ReturnOptions or compatible object
                    options = options_input
                else:
                    logger.warning(f"Invalid options format: {options_input}")
                    options = ReturnOptions()
            except Exception as e:
                logger.warning(f"Error processing options: {e}")
                options = ReturnOptions()
        else:
            # Use defaults
            options = ReturnOptions()

        # Re-add options to kwargs so the function call works properly
        func_kwargs = kwargs.copy()
        if options_input is not None:
            func_kwargs["options"] = options_input

        # Log options
        pagination_str = ""
        if options.pagination is not None:
            pagination_str = f", pagination: page {options.pagination.page}, size {options.pagination.page_size}"

        logger.debug(
            f"Cache decorator for {func.__name__} using "
            f"value_type: {options.value_type}, "
            f"reference_type: {options.reference_type}{pagination_str}"
        )

        # Process arguments for references
        processed_args = []
        for arg in args:
            processed_args.append(self._process_reference_value(arg))

        processed_kwargs = {}
        for k, v in kwargs.items():
            processed_kwargs[k] = self._process_reference_value(v)

        # Generate normalized cache key (options excluded from kwargs earlier)
        cache_key = self._normalize_cache_key(
            func.__name__, processed_args, processed_kwargs
        )

        # Debug log the cache key
        logger.debug(
            f"Cache key: {cache_key[:50]}{'...' if len(cache_key) > 50 else ''}"
        )

        # Check if we have a valid cache entry
        cache_hit = False
        try:
            if self.contains(cache_key):
                with self._cache_lock:
                    # Get value, timestamp, and reference ID from cache
                    result, _, ref_id = self.cache[cache_key]

                logger.debug(f"Cache HIT for {self.name}.{func.__name__}")
                self.stats["hits"] += 1
                cache_hit = True
            else:
                logger.debug(f"Cache MISS for {self.name}.{func.__name__}")
        except Exception as e:
            logger.error(f"Error checking cache: {e}")

        # If not in cache or expired, execute the function
        if not cache_hit:
            try:
                # Use func_kwargs here which includes the options
                result = await func(*processed_args, **func_kwargs)
                self.stats["misses"] += 1
            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {e!s}")
                raise

            # Store in cache (set method now handles reference ID generation)
            with self._cache_lock:
                self.set(cache_key, result)
                # Get the reference ID that was just generated
                _, _, ref_id = self.cache[cache_key]

        # Store the function name as tool_name for the result
        # This is critical for accurate tool tracking in references
        tool_name = func.__name__

        # Handle return value with the specified options, tool name, and ref_id
        return self.handle_return_value(result, options, tool_name, ref_id)

    def _execute_cached_sync(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """Execute a sync cached function call.

        This internal method handles the actual caching logic for sync functions.
        """
        # Initialize result to None to ensure it's always bound
        result = None
        ref_id = None

        # Extract options if present - but don't include in cache key
        options_input = kwargs.pop("options", None)  # Remove from kwargs
        options = None

        if options_input:
            try:
                if isinstance(options_input, dict):
                    # Handle dictionary-style options
                    options = ReturnOptions.from_dict(options_input)
                elif hasattr(options_input, "value_type") and hasattr(
                    options_input, "reference_type"
                ):
                    # It's already a ReturnOptions or compatible object
                    options = options_input
                else:
                    logger.warning(f"Invalid options format: {options_input}")
                    options = ReturnOptions()
            except Exception as e:
                logger.warning(f"Error processing options: {e}")
                options = ReturnOptions()
        else:
            # Use defaults
            options = ReturnOptions()

        # Re-add options to kwargs so the function call works properly
        func_kwargs = kwargs.copy()
        if options_input is not None:
            func_kwargs["options"] = options_input

        # Log options
        pagination_str = ""
        if options.pagination is not None:
            pagination_str = f", pagination: page {options.pagination.page}, size {options.pagination.page_size}"

        logger.debug(
            f"Cache decorator for {func.__name__} using "
            f"value_type: {options.value_type}, "
            f"reference_type: {options.reference_type}{pagination_str}"
        )

        # Process arguments for references
        processed_args = []
        for arg in args:
            processed_args.append(self._process_reference_value(arg))

        processed_kwargs = {}
        for k, v in kwargs.items():
            processed_kwargs[k] = self._process_reference_value(v)

        # Generate normalized cache key (options excluded from kwargs earlier)
        cache_key = self._normalize_cache_key(
            func.__name__, processed_args, processed_kwargs
        )

        # Debug log the cache key
        logger.debug(
            f"Cache key: {cache_key[:50]}{'...' if len(cache_key) > 50 else ''}"
        )

        # Check if we have a valid cache entry
        cache_hit = False
        try:
            if self.contains(cache_key):
                with self._cache_lock:
                    # Get value, timestamp, and reference ID from cache
                    result, _, ref_id = self.cache[cache_key]

                logger.debug(f"Cache HIT for {self.name}.{func.__name__}")
                self.stats["hits"] += 1
                cache_hit = True
            else:
                logger.debug(f"Cache MISS for {self.name}.{func.__name__}")
        except Exception as e:
            logger.error(f"Error checking cache: {e}")

        # If not in cache or expired, execute the function
        if not cache_hit:
            try:
                # Use func_kwargs here which includes the options
                result = func(*processed_args, **func_kwargs)
                self.stats["misses"] += 1
            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {e!s}")
                raise

            # Store in cache (set method now handles reference ID generation)
            with self._cache_lock:
                self.set(cache_key, result)
                # Get the reference ID that was just generated
                _, _, ref_id = self.cache[cache_key]

        # Store the function name as tool_name for the result
        # This is critical for accurate tool tracking in references
        tool_name = func.__name__

        # Handle return value with the specified options, tool name, and ref_id
        return self.handle_return_value(result, options, tool_name, ref_id)

    def _normalize_cache_key(self, func_name: str, args: list, kwargs: dict) -> str:
        """Generate a normalized cache key based on function name and input parameters.

        For all caches, this excludes the 'options' parameter which controls return format.
        """
        # Start with the function name
        key_parts = [func_name]

        # Prioritize finding input_data or similar input parameters
        found_input_param = False

        # Look for input_data in kwargs first (most common pattern)
        if "input_data" in kwargs:
            input_data = kwargs["input_data"]
            if isinstance(input_data, BaseModel):
                key_parts.append(f"input_data={input_data.model_dump()}")
            else:
                key_parts.append(f"input_data={input_data}")
            found_input_param = True

        # If no input_data, try other common input parameter names
        if not found_input_param:
            for input_key in ["query", "parameters", "data", "request"]:
                if input_key in kwargs:
                    input_value = kwargs[input_key]
                    if isinstance(input_value, BaseModel):
                        key_parts.append(f"{input_key}={input_value.model_dump()}")
                    else:
                        key_parts.append(f"{input_key}={input_value}")
                    found_input_param = True
                    break

        # If still no recognized input parameters, use all args and kwargs
        if not found_input_param:
            # Handle Pydantic models specially
            for arg in args:
                if isinstance(arg, BaseModel):
                    # Extract only the model's dict values for the key
                    key_parts.append(str(arg.model_dump()))
                else:
                    key_parts.append(str(arg))

            # Handle keyword arguments (explicitly excluding options)
            for k, v in sorted(kwargs.items()):
                if isinstance(v, BaseModel):
                    key_parts.append(f"{k}={v.model_dump()}")
                else:
                    key_parts.append(f"{k}={v}")

        # Join all parts into final cache key
        return ":".join(key_parts)

    def _process_reference_value(self, value: Any) -> Any:
        """Process a value recursively, resolving any references.
        References can be:
        1. CacheReference objects
        2. Strings that match reference IDs
        3. Nested structures containing the above
        """
        # Handle CacheReference objects directly
        if isinstance(value, CacheReference):
            try:
                resolved_value = ToolsetCache.resolve_reference(value)
                self.stats["references_used"] += 1
                return resolved_value
            except Exception as e:
                logger.error(f"Error resolving reference: {e}")
                return value

        # Handle potential reference IDs (strings)
        elif isinstance(value, str) and len(value) >= 3:  # Changed from 8 to 3
            # Check if this string matches any reference ID prefix in this cache
            matching_refs = [
                ref_id
                for ref_id in self.reference_registry.keys()
                if ref_id.startswith(value)
            ]

            if len(matching_refs) == 1:
                # Found a unique match - create a reference and resolve it
                ref = CacheReference(
                    ref_id=matching_refs[0],
                    cache_name=self.name,
                    tool_name="<auto-resolved>",
                    created_at=time.time(),
                )
                try:
                    resolved_value = ToolsetCache.resolve_reference(ref)
                    self.stats["references_used"] += 1
                    return resolved_value
                except Exception as e:
                    logger.error(f"Error resolving string reference: {e}")
                    return value
            else:
                # Try other caches if not found in this one
                for cache_name, cache in ToolsetCache._cache_registry.items():
                    if cache_name == self.name:
                        continue  # Skip self, already checked

                    matching_refs = [
                        ref_id
                        for ref_id in cache.reference_registry.keys()
                        if ref_id.startswith(value)
                    ]

                    if len(matching_refs) == 1:
                        # Found a unique match in another cache
                        ref = CacheReference(
                            ref_id=matching_refs[0],
                            cache_name=cache_name,
                            tool_name="<cross-cache-resolved>",
                            created_at=time.time(),
                        )
                        try:
                            resolved_value = ToolsetCache.resolve_reference(ref)
                            self.stats["references_used"] += 1
                            return resolved_value
                        except Exception as e:
                            logger.error(f"Error resolving cross-cache reference: {e}")
                            return value

        # Handle dictionaries (recursively process each value)
        elif isinstance(value, dict):
            return {k: self._process_reference_value(v) for k, v in value.items()}

        # Handle lists and tuples (recursively process each item)
        elif isinstance(value, (list, tuple)):
            processed = [self._process_reference_value(item) for item in value]
            return type(value)(processed)

        # Return unmodified for other types
        return value

    def __contains__(self, key: str) -> bool:
        """Support for 'in' operator to check if a key is in the cache"""
        return self.contains(key)

    def clear(self) -> int:
        """Clear all cache entries and return the number of items cleared.
        """
        with self._cache_lock:
            count = len(self.cache)
            self.cache.clear()
            self.reference_registry.clear()
            self.access_order.clear()

            # Reset stats
            self.stats = {
                "hits": 0,
                "misses": 0,
                "expirations": 0,
                "references_used": 0,
            }

            logger.info(f"Cleared {count} items from {self.name} cache")

            # Remove the cache file if deterministic
            if self.deterministic and self.cache_dir:
                try:
                    filepath = self._get_cache_filepath()
                    registry_filepath = self._get_registry_filepath()

                    if filepath and os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Removed cache file {filepath}")

                    if registry_filepath and os.path.exists(registry_filepath):
                        os.remove(registry_filepath)
                        logger.info(f"Removed registry file {registry_filepath}")
                except Exception as e:
                    logger.error(f"Error removing cache files: {e}")

            return count

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about the current cache state.
        """
        with self._cache_lock:
            # Count expired entries (only relevant for non-deterministic caches)
            if not self.deterministic and self.expiry_seconds is not None:
                current_time = time.time()
                # We calculate but don't need to store the expired count since it's not used
                _ = sum(
                    1
                    for _, timestamp, *_ in self.cache.values()
                    if current_time - timestamp >= self.expiry_seconds
                )

            # Create stats model and return as dict
            stats = CacheStats(
                name=self.name,
                deterministic=self.deterministic,
                hits=self.stats["hits"],
                misses=self.stats["misses"],
                expirations=self.stats["expirations"],
                references_used=self.stats["references_used"],
                total_entries=len(self.cache),
                total_references=len(self.reference_registry),
                max_size=self.max_size,
                expiry_seconds=None if self.deterministic else self.expiry_seconds,
            )

            return stats.model_dump()

    def flush(self) -> None:
        """Manually flush the cache to disk if it's deterministic.
        """
        if self.deterministic and self.cache_dir:
            self._flush_to_disk()
        else:
            logger.warning(f"Cannot flush non-deterministic cache {self.name}")

    def inspect_cache(self) -> dict[str, Any]:
        """Print all cache keys and their expiration times for debugging"""
        with self._cache_lock:
            current_time = time.time()
            entries = []

            for i, (key, (_, timestamp, *_)) in enumerate(self.cache.items()):
                if not self.deterministic and self.expiry_seconds is not None:
                    expires_in = timestamp + self.expiry_seconds - current_time
                    entries.append(
                        {
                            "key": key[:50] + "..." if len(key) > 50 else key,
                            "expires_in": f"{expires_in:.1f}s"
                            if expires_in > 0
                            else "expired",
                            "age": f"{current_time - timestamp:.1f}s",
                        }
                    )
                else:
                    entries.append(
                        {
                            "key": key[:50] + "..." if len(key) > 50 else key,
                            "expires_in": "never",
                            "age": f"{current_time - timestamp:.1f}s",
                        }
                    )

            references = []
            for i, (ref_id, cache_key) in enumerate(self.reference_registry.items()):
                references.append(
                    {
                        "ref_id": ref_id[:8] + "...",
                        "cache_key": cache_key[:30] + "..."
                        if len(cache_key) > 30
                        else cache_key,
                    }
                )

            return {
                "cache_name": self.name,
                "entries": entries,
                "references": references,
                "stats": self.get_stats(),
            }
