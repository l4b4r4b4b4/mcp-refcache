import functools
import logging
import pickle
import threading
import time
from collections.abc import Callable
from typing import (
    Any,
    TypeVar,
    cast,
)

import redis
from system_0.config import settings

from .cache import (
    CacheReference,
    ReturnT,
    ToolsetCache,
)
from .return_types import (
    ReturnOptions,
)

redis_url = settings.er_cache_url
logger = logging.getLogger(f"redis_cache connected at: {redis_url}")
logger.setLevel(logging.DEBUG)

# Redis key value type
RedisFunctionT = TypeVar("RedisFunctionT")


# Create a helper function to safely await Redis responses
def safe_redis_result(result: Any) -> Any:
    """Safely handle Redis results - works with both sync and async Redis clients."""
    # First, check if it's an awaitable (for future compatibility)
    if hasattr(result, "__await__"):
        # This would normally be: return await result
        # But since we're using the synchronous client, we should never get here
        raise RuntimeError(
            "Got an awaitable from Redis - check Redis client configuration"
        )
    return result


def redis_call(func: Callable[..., RedisFunctionT]) -> Callable[..., RedisFunctionT]:
    """Decorator to handle Redis API calls safely with proper error handling and type conversion"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> RedisFunctionT:
        try:
            result = func(*args, **kwargs)
            # Safely handle potentially async results
            safe_result = safe_redis_result(result)
            # Type checkers don't realize this result is already resolved
            return cast("RedisFunctionT", safe_result)
        except (redis.RedisError, Exception) as e:
            logger.error(f"Redis error in {func.__name__}: {e!s}")

            # Return sensible defaults based on function name, matching the return type
            if "get" in func.__name__:
                return cast("RedisFunctionT", None)
            elif "exists" in func.__name__ or "contains" in func.__name__:
                return cast("RedisFunctionT", False)
            elif "keys" in func.__name__ or "zrange" in func.__name__:
                return cast("RedisFunctionT", [])
            elif (
                "zcard" in func.__name__
                or "delete" in func.__name__
                or "len" in func.__name__
            ):
                return cast("RedisFunctionT", 0)
            elif "hgetall" in func.__name__:
                return cast("RedisFunctionT", {})
            # Default fallback
            return cast("RedisFunctionT", None)

    return wrapper


class RedisCompatibleCache(ToolsetCache):
    """Redis-compatible implementation of ToolsetCache using Dragonfly or Redis"""

    # Shared Redis client
    _redis_client: redis.Redis | None = None

    @classmethod
    def get_redis_client(cls) -> redis.Redis:
        """Get or create a shared Redis client"""
        if cls._redis_client is None:
            passkey = "owif5eh4eiuztwfio3n5dzuezrc"

            logger.info(
                f"Connecting to Redis at {redis_url.split('@')[-1]} with auth: True"
            )

            try:
                # Create Redis client with hardcoded password and explicitly disable async mode
                logger.info("Using hardcoded password for Redis connection")
                cls._redis_client = redis.Redis.from_url(
                    redis_url,
                    password=passkey,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    decode_responses=False,
                )

                # Test connection
                cls._redis_client.ping()
                logger.info("Connected to Redis successfully")
            except redis.RedisError as e:
                logger.error(f"Redis connection error: {e}")
                raise

        return cls._redis_client

    def _process_reference_value(self, value: Any) -> Any:
        """Redis-specific implementation of the reference processing logic.
        Handles resolving references in input values for Redis-backed caches.
        """
        # Handle CacheReference objects directly
        if isinstance(value, CacheReference):
            try:
                resolved_value = ToolsetCache.resolve_reference(value)
                self._update_stats_in_redis(references_used=1)
                logger.debug(
                    f"Resolved CacheReference: {value.ref_id} -> {type(resolved_value)}"
                )
                return resolved_value
            except Exception as e:
                logger.error(f"Error resolving reference: {e}")
                return value

        # Handle potential reference IDs (strings)
        elif isinstance(value, str) and len(value) >= 3:  # Changed from 8 to 3
            logger.debug(f"Checking if string '{value}' is a reference ID")

            # First check this cache's references in memory
            if hasattr(self, "reference_registry"):
                matching_refs = [
                    ref_id
                    for ref_id in self.reference_registry.keys()
                    if ref_id.startswith(value)
                ]

                logger.debug(
                    f"Found {len(matching_refs)} matching references in registry: {matching_refs}"
                )

                if len(matching_refs) == 1:
                    # Found a unique match in our local registry - create a reference and resolve it
                    ref = CacheReference(
                        ref_id=matching_refs[0],
                        cache_name=self.name,
                        tool_name="<auto-resolved>",
                        created_at=time.time(),
                    )
                    try:
                        resolved_value = ToolsetCache.resolve_reference(ref)
                        self._update_stats_in_redis(references_used=1)
                        logger.debug(
                            f"Resolved string reference: {value} -> {type(resolved_value)}"
                        )
                        return resolved_value
                    except Exception as e:
                        logger.error(f"Error resolving string reference: {e}")
                        logger.debug(f"Reference resolution error detail: {e!s}")
                        return value

            # If not found in memory, check Redis directly
            try:
                # Check all keys with our registry prefix
                registry_keys = self._get_keys(f"{self.registry_prefix}*")

                # Find keys that start with the value
                matching_refs = []
                for full_key in registry_keys:
                    # Extract the reference ID from the key
                    ref_id = ""
                    if isinstance(full_key, bytes):
                        ref_id = full_key.decode().replace(self.registry_prefix, "", 1)
                    else:
                        ref_id = str(full_key).replace(self.registry_prefix, "", 1)

                    if ref_id.startswith(value):
                        matching_refs.append(ref_id)

                logger.debug(
                    f"Found {len(matching_refs)} matching references in Redis keys"
                )

                if len(matching_refs) == 1:
                    # Found a unique match in Redis - create a reference and resolve it
                    ref = CacheReference(
                        ref_id=matching_refs[0],
                        cache_name=self.name,
                        tool_name="<redis-resolved>",
                        created_at=time.time(),
                    )
                    try:
                        resolved_value = ToolsetCache.resolve_reference(ref)
                        self._update_stats_in_redis(references_used=1)
                        logger.debug(
                            f"Resolved Redis reference: {value} -> {resolved_value}"
                        )
                        return resolved_value
                    except Exception as e:
                        logger.error(f"Error resolving Redis reference: {e}")
                        return value
            except Exception as e:
                logger.error(f"Error checking Redis for references: {e}")

            # If still not found, try other caches
            for cache_name, cache in ToolsetCache._cache_registry.items():
                if cache_name == self.name:
                    continue  # Skip self, already checked

                # Only try to access reference_registry if it exists
                if hasattr(cache, "reference_registry"):
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
                            self._update_stats_in_redis(references_used=1)
                            logger.debug(
                                f"Resolved cross-cache reference: {value} -> {resolved_value}"
                            )
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

    @classmethod
    def get_cache_for_tool(cls, toolset_name: str) -> "RedisCompatibleCache":
        """Get the appropriate Redis cache for a given toolset, ensuring
        cache instances are shared across processes via Redis.
        """
        key = f"{toolset_name}"
        logger.debug(f"[CACHE] Looking for cache with key: {key}")

        # First check Redis to see if cache exists globally
        try:
            redis_client = cls.get_redis_client()
            cache_exists = bool(
                safe_redis_result(redis_client.exists(f"cache_registry:{key}"))
            )

            # If cache exists in Redis but not in local registry
            if cache_exists:
                logger.debug(f"[CACHE] Found existing cache in Redis registry: {key}")

                # Return from local registry if available
                if key in cls._cache_registry and isinstance(
                    cls._cache_registry[key], RedisCompatibleCache
                ):
                    logger.debug(f"[CACHE] ✅ Found in local registry too: {key}")
                    return cast("RedisCompatibleCache", cls._cache_registry[key])
                else:
                    # Create a new local instance that points to existing Redis data
                    logger.debug(
                        f"[CACHE] Creating local instance for existing Redis cache: {key}"
                    )

                    # Determine cache properties from Redis
                    is_deterministic_raw = safe_redis_result(
                        redis_client.get(f"cache_meta:{key}:deterministic")
                    )
                    is_deterministic = False
                    if is_deterministic_raw:
                        if isinstance(is_deterministic_raw, bytes):
                            is_deterministic = bool(int(is_deterministic_raw.decode()))
                        else:
                            is_deterministic = bool(int(is_deterministic_raw))

                    expiry_seconds_raw = safe_redis_result(
                        redis_client.get(f"cache_meta:{key}:expiry")
                    )
                    expiry_seconds = 3600
                    if expiry_seconds_raw:
                        if isinstance(expiry_seconds_raw, bytes):
                            expiry_seconds = int(expiry_seconds_raw.decode())
                        else:
                            expiry_seconds = int(expiry_seconds_raw)

                    if is_deterministic:
                        expiry_seconds = None

                    max_size_raw = safe_redis_result(
                        redis_client.get(f"cache_meta:{key}:max_size")
                    )
                    max_size = 10000
                    if max_size_raw:
                        if isinstance(max_size_raw, bytes):
                            max_size = int(max_size_raw.decode())
                        else:
                            max_size = int(max_size_raw)

                    # Create cache instance that reuses existing Redis data
                    cache = RedisCompatibleCache(
                        name=key,
                        deterministic=is_deterministic,
                        expiry_seconds=expiry_seconds,
                        max_size=max_size,
                        reuse_existing=True,  # Flag to indicate we're connecting to existing Redis data
                    )

                    logger.debug(
                        f"[CACHE] Created local instance for Redis cache: {id(cache)}"
                    )
                    return cache
        except Exception as e:
            logger.error(f"[CACHE] Error checking Redis for cache existence: {e}")
            # Continue to fallback behavior

        # Local registry check (fallback if Redis check fails)
        if key in cls._cache_registry and isinstance(
            cls._cache_registry[key], RedisCompatibleCache
        ):
            logger.debug(f"[CACHE] ✅ Using existing cache from local registry: {key}")
            return cast("RedisCompatibleCache", cls._cache_registry[key])

        logger.debug(f"[CACHE] ❌ No existing cache found - creating new one: {key}")

        # If no cache exists, create a new one with default settings
        if toolset_name.endswith("_toolset"):
            is_deterministic = toolset_name.startswith("math")
            expiry = None if is_deterministic else 3600

            logger.debug(f"[CACHE] Toolset {toolset_name} matches naming pattern")
            logger.debug(
                f"[CACHE] Setting deterministic={is_deterministic}, expiry={expiry}"
            )
            logger.info(
                f"Creating new Redis cache for {toolset_name} (deterministic={is_deterministic})"
            )

            # Create a new cache with appropriate settings
            cache = RedisCompatibleCache(
                name=key,
                deterministic=is_deterministic,
                expiry_seconds=expiry,
                max_size=10000,  # Default max size
            )

            logger.debug(f"[CACHE] New cache created with ID: {id(cache)}")

            # Register in Redis for cross-process visibility
            try:
                redis_client = cls.get_redis_client()
                redis_client.set(f"cache_registry:{key}", "1")
                redis_client.set(
                    f"cache_meta:{key}:deterministic", "1" if is_deterministic else "0"
                )
                redis_client.set(
                    f"cache_meta:{key}:expiry", str(3600 if expiry is None else expiry)
                )
                redis_client.set(f"cache_meta:{key}:max_size", "10000")
                logger.debug(f"[CACHE] Cache {key} registered in Redis")
            except Exception as e:
                logger.error(f"[CACHE] Error registering cache in Redis: {e}")

            return cache

        # Fallback for unknown toolsets
        logger.warning(f"Unknown toolset: {toolset_name}, creating generic Redis cache")
        cache = RedisCompatibleCache(name=key, deterministic=False)

        # Register in Redis
        try:
            redis_client = cls.get_redis_client()
            redis_client.set(f"cache_registry:{key}", "1")
            redis_client.set(f"cache_meta:{key}:deterministic", "0")
            redis_client.set(f"cache_meta:{key}:expiry", "3600")
            redis_client.set(f"cache_meta:{key}:max_size", "10000")
        except Exception as e:
            logger.error(f"[CACHE] Error registering fallback cache in Redis: {e}")

        logger.debug(f"[CACHE] Fallback cache created with ID: {id(cache)}")
        return cache

    def __init__(
        self,
        name: str,
        deterministic: bool = False,
        expiry_seconds: int | float | None = 3600,
        max_size: int | None = 10000,
        cache_dir: str | None = None,
        flush_interval: int | None = 60 * 60,
        reuse_existing: bool = False,
    ):
        """Initialize a Redis-backed cache"""
        # Initialize basic attributes
        self.name = name
        self.deterministic = deterministic

        # For deterministic caches, override expiry_seconds to None (never expire)
        self.expiry_seconds = None if deterministic else expiry_seconds

        if deterministic and expiry_seconds is not None:
            logger.warning(
                f"Ignoring expiry_seconds for deterministic cache {name}. "
                f"Deterministic caches do not expire."
            )

        self.max_size = max_size
        self.flush_interval = flush_interval

        # Initialize stats locally - these will mirror what's in Redis
        self.stats = {"hits": 0, "misses": 0, "expirations": 0, "references_used": 0}

        # Reference registry and cache will be stored in Redis
        self.reference_registry: dict[str, str] = {}  # Local copy for compatibility

        # Thread lock for thread safety
        self._cache_lock = threading.RLock()

        # Register this cache instance globally
        ToolsetCache._cache_registry[name] = self

        # Get Redis client
        try:
            self.redis = self.get_redis_client()

            # Create Redis key prefixes
            self.cache_prefix = f"cache:{self.name}:"
            self.registry_prefix = f"registry:{self.name}:"
            self.stats_key = f"stats:{self.name}"
            self.keys_list = f"keys:{self.name}"

            # If this cache already exists in Redis, don't re-initialize stats
            if not reuse_existing and not self.redis.hexists(self.stats_key, "hits"):
                self.redis.hset(
                    self.stats_key,
                    mapping={
                        "hits": 0,
                        "misses": 0,
                        "expirations": 0,
                        "references_used": 0,
                    },
                )

            # Register this cache in Redis for cross-process visibility
            if not reuse_existing:
                self.redis.set(f"cache_registry:{name}", "1")
                self.redis.set(
                    f"cache_meta:{name}:deterministic", "1" if deterministic else "0"
                )
                self.redis.set(
                    f"cache_meta:{name}:expiry",
                    str(3600 if expiry_seconds is None else expiry_seconds),
                )
                self.redis.set(
                    f"cache_meta:{name}:max_size",
                    str(max_size if max_size is not None else 10000),
                )

            # Load local reference registry from Redis for quick lookups
            self._sync_reference_registry_from_redis()

            logger.info(
                f"Redis cache '{name}' {'reused' if reuse_existing else 'initialized'}"
            )

        except Exception as e:
            logger.error(f"Error initializing Redis cache: {e}")
            raise

    @redis_call
    def _sync_reference_registry_from_redis(self) -> None:
        """Load reference registry from Redis into local memory for faster lookups"""
        try:
            # Get all keys with the registry prefix
            registry_keys_raw = self.redis.keys(f"{self.registry_prefix}*")

            # Ensure we have a proper list to iterate over
            registry_keys = []
            if registry_keys_raw:
                if isinstance(registry_keys_raw, list):
                    registry_keys = registry_keys_raw
                else:
                    # Single key case
                    registry_keys = [registry_keys_raw]

            if not registry_keys:
                return

            # Clear local registry and repopulate
            self.reference_registry.clear()

            # Process each registry key
            for full_key in registry_keys:
                # Extract the reference ID from the key
                ref_id = ""
                if isinstance(full_key, bytes):
                    ref_id = full_key.decode().replace(self.registry_prefix, "", 1)
                else:
                    ref_id = str(full_key).replace(self.registry_prefix, "", 1)

                # Get cache key - convert the key to a valid type first
                if isinstance(full_key, bytes):
                    cache_key_bytes = self.redis.get(full_key)
                else:
                    # Convert the key to bytes or str as expected by Redis
                    try:
                        # Try bytes first
                        cache_key_bytes = self.redis.get(
                            full_key.encode()  # pyright: ignore
                            if hasattr(full_key, "encode")
                            else str(full_key).encode()
                        )
                    except Exception as exc:
                        # Fall back to string
                        logger.debug(f"Failed to get bytes key, trying string: {exc}")
                        cache_key_bytes = self.redis.get(str(full_key))

                # Apply safe_redis_result to the result
                cache_key_bytes = safe_redis_result(cache_key_bytes)

                if cache_key_bytes:
                    cache_key = ""
                    if isinstance(cache_key_bytes, bytes):
                        cache_key = cache_key_bytes.decode()
                    else:
                        cache_key = str(cache_key_bytes)
                    # Store in local registry
                    self.reference_registry[ref_id] = cache_key

            logger.debug(
                f"Loaded {len(self.reference_registry)} references from Redis for {self.name}"
            )
        except Exception as e:
            logger.error(f"Error syncing reference registry from Redis: {e}")

    @redis_call
    def _get_stats_from_redis(self) -> dict[str, int]:
        """Get stats from Redis"""
        try:
            stats_dict = self.redis.hgetall(self.stats_key)
            result = {}

            # Handle the case where stats_dict might be None
            if stats_dict is None:
                return {"hits": 0, "misses": 0, "expirations": 0, "references_used": 0}

            # Add type annotation to help the IDE
            stats_items = stats_dict.items()  # type: ignore
            # Convert bytes to strings and values to integers - safely handle different return types
            for k, v in stats_items:
                # Convert key to string
                key = k.decode() if isinstance(k, bytes) else str(k)
                # Convert value to integer
                try:
                    val = int(v.decode() if isinstance(v, bytes) else str(v))
                except (ValueError, TypeError, AttributeError):
                    val = 0
                result[key] = val

            return result
        except Exception as e:
            logger.error(f"Error getting stats from Redis: {e}")
            return {"hits": 0, "misses": 0, "expirations": 0, "references_used": 0}

    @redis_call
    def _update_stats_in_redis(self, **updates) -> None:
        """Update stats in Redis"""
        try:
            for key, value in updates.items():
                self.redis.hincrby(self.stats_key, key, value)
                # Also update local stats for compatibility
                self.stats[key] += value
        except Exception as e:
            logger.error(f"Error updating stats in Redis: {e}")

    # @redis_call
    def get(self, key: str) -> tuple[Any, float, str]:
        """Get a value, timestamp, and reference ID from the cache, or raise KeyError if not found"""
        try:
            # Get the full key
            redis_key = f"{self.cache_prefix}{key}"

            # Check existence explicitly
            if not self.redis.exists(redis_key):
                raise KeyError(f"Key {key} not found in cache")

            # Try to get the value
            data = self.redis.get(redis_key)
            if data is None:
                raise KeyError(f"Key {key} not found in cache")

            # Deserialize the data using pickle for complex objects
            try:
                # Ensure data is bytes (Redis client might return bytes already)
                data_bytes = self._ensure_bytes(data)
                entry = pickle.loads(data_bytes)

                # Extract all required values from the entry
                value = entry.get("value")
                timestamp = entry.get("timestamp", time.time())
                ref_id = entry.get("ref_id")

                # Verify we have a reference ID
                if ref_id is None:
                    # Generate one if missing (should not happen with new code)
                    ref_id = self._generate_reference_id(key, value)
                    # Store it back in Redis
                    entry["ref_id"] = ref_id
                    serialized_data = pickle.dumps(entry)
                    self.redis.set(redis_key, serialized_data)

                # Make sure this reference is in our registry
                self._update_reference_registry(ref_id, key)

                # Check expiration for non-deterministic caches
                if not self.deterministic and self.expiry_seconds is not None:
                    if time.time() - timestamp > self.expiry_seconds:
                        self._update_stats_in_redis(expirations=1)
                        self.redis.delete(redis_key)
                        raise KeyError(f"Key {key} has expired")

                # Update access order for LRU policy
                self.redis.zadd(self.keys_list, {key: time.time()})

                return value, timestamp, ref_id

            except (pickle.PickleError, AttributeError) as e:
                logger.error(f"Error deserializing cached value: {e}")
                raise KeyError(f"Could not deserialize cached value for {key}")

        except Exception as e:
            if not isinstance(e, KeyError):
                logger.error(f"Redis get error for {key}: {e}")
            raise KeyError(f"Key {key} not found in cache: {e!s}")

    def _ensure_bytes(self, data: Any) -> bytes:
        """Safely convert data to bytes"""
        if isinstance(data, bytes):
            return data
        elif hasattr(data, "encode") and callable(data.encode):
            # This still might error in type checking, but will work at runtime
            try:
                return data.encode()  # type: ignore
            except AttributeError:
                # Fall back to string conversion
                return str(data).encode()
        else:
            return str(data).encode()

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert any value to int"""
        if value is None:
            return default
        try:
            # Handle both primitive types and complex Redis responses
            if hasattr(value, "decode") and callable(value.decode):
                # If it's bytes-like
                return int(value.decode())  # type: ignore
            return int(value)  # type: ignore
        except (ValueError, TypeError, AttributeError):
            logger.warning(f"Could not convert {value} to int")
            return default

    @redis_call
    def set(self, key: str, value: Any) -> None:
        """Set a value in Redis"""
        try:
            # Generate reference ID
            ref_id = self._generate_reference_id(key, value)

            # Create the full key
            redis_key = f"{self.cache_prefix}{key}"

            # Prepare data for storage
            timestamp = time.time()
            entry = {"value": value, "timestamp": timestamp, "ref_id": ref_id}

            # Add to reference registry
            self._update_reference_registry(ref_id, key)

            # Serialize and store the data using pickle for complex objects
            serialized_data = pickle.dumps(entry)

            # Set in Redis
            if not self.deterministic and self.expiry_seconds is not None:
                # Set with expiry for non-deterministic caches
                self.redis.setex(redis_key, int(self.expiry_seconds), serialized_data)
            else:
                # Set without expiry for deterministic caches
                self.redis.set(redis_key, serialized_data)

            # Update access order for LRU policy
            self.redis.zadd(self.keys_list, {key: timestamp})

            # Trim if necessary
            if self.max_size is not None:
                self._trim_cache()

        except Exception as e:
            logger.error(f"Redis set error for {key}: {e}")
            raise

    @redis_call
    def contains(self, key: str) -> bool:
        """Check if a key exists in Redis"""
        try:
            # Get the full key
            redis_key = f"{self.cache_prefix}{key}"

            # Check if key exists
            exists_result = self.redis.exists(redis_key)
            exists = bool(exists_result)

            if not exists:
                return False

            # For non-deterministic caches, check if expired
            if not self.deterministic and self.expiry_seconds is not None:
                # Get the timestamp
                data = self.redis.get(redis_key)
                if data:
                    try:
                        # Ensure data is bytes
                        data_bytes = self._ensure_bytes(data)
                        entry = pickle.loads(data_bytes)
                        timestamp = entry.get("timestamp", 0)

                        if time.time() - timestamp > self.expiry_seconds:
                            self._update_stats_in_redis(expirations=1)
                            self.redis.delete(redis_key)
                            return False
                    except Exception as e:
                        logger.error(f"Error checking expiration: {e}")
                        return False

            return True
        except Exception as e:
            logger.error(f"Redis contains error for {key}: {e}")
            return False  # Return False for any errors, don't raise exceptions

    @redis_call
    def _trim_cache(self) -> None:
        """Trim the cache to max_size using Redis sorted set (ZSET) for LRU"""
        try:
            if not self.max_size:
                return

            # Count current items
            count_result = self.redis.zcard(self.keys_list)
            # Make sure we have an integer
            count = 0
            if count_result is not None:
                try:
                    # Safely convert to int - handles different return types
                    count = self._safe_int(count_result)
                except (TypeError, ValueError):
                    logger.error(f"Could not convert {count_result} to int")
                    count = 0

            if count <= self.max_size:
                return

            # Calculate how many items to remove (25% of excess)
            remove_count = max(1, int((count - self.max_size) * 0.25))

            # Get oldest keys from sorted set
            oldest_keys_result = self.redis.zrange(self.keys_list, 0, remove_count - 1)
            oldest_keys = self._convert_to_string_list(oldest_keys_result)

            if not oldest_keys:
                return

            # Create full Redis keys
            full_keys = [f"{self.cache_prefix}{k}" for k in oldest_keys]

            # Delete the keys
            if full_keys:
                self.redis.delete(*full_keys)

            # Remove from sorted set
            if oldest_keys:
                self.redis.zrem(self.keys_list, *oldest_keys)

            logger.debug(
                f"Trimmed {len(oldest_keys)} oldest entries from {self.name} cache"
            )

        except Exception as e:
            logger.error(f"Error trimming Redis cache: {e}")

    def _convert_to_string_list(self, data: Any) -> list[str]:
        """Safely convert data to a list of strings"""
        if data is None:
            return []

        # Handle case where it's already a list-like object
        if isinstance(data, (list, tuple)):
            return [k.decode() if isinstance(k, bytes) else str(k) for k in data]

        # Handle case where it's a single item
        return [data.decode() if isinstance(data, bytes) else str(data)]

    @redis_call
    def clear(self) -> int:
        """Clear all entries in this cache"""
        try:
            # Get cache keys
            all_keys_result = self.redis.keys(f"{self.cache_prefix}*")
            all_keys = self._convert_to_string_list(all_keys_result)
            count = len(all_keys)

            # Delete all keys if there are any
            if all_keys:
                self.redis.delete(*all_keys)

            # Clear registry keys
            registry_keys_result = self.redis.keys(f"{self.registry_prefix}*")
            registry_keys = self._convert_to_string_list(registry_keys_result)

            if registry_keys:
                self.redis.delete(*registry_keys)

            # Reset stats
            self.redis.hset(
                self.stats_key,
                mapping={
                    "hits": 0,
                    "misses": 0,
                    "expirations": 0,
                    "references_used": 0,
                },
            )

            # Clear key list
            self.redis.delete(self.keys_list)

            logger.info(f"Cleared {count} items from {self.name} Redis cache")
            return count

        except Exception as e:
            logger.error(f"Error clearing Redis cache: {e}")
            return 0

    @redis_call
    def get_stats(self) -> dict[str, Any]:
        """Return statistics about the current cache state."""
        try:
            # Get stats from Redis
            redis_stats = self._get_stats_from_redis()

            # Count entries and references
            cache_keys_result = self.redis.keys(f"{self.cache_prefix}*")
            registry_keys_result = self.redis.keys(f"{self.registry_prefix}*")

            # Safely convert to lists
            cache_keys = self._convert_to_string_list(cache_keys_result)
            registry_keys = self._convert_to_string_list(registry_keys_result)

            total_entries = len(cache_keys)
            total_references = len(registry_keys)

            # Safely access stats with proper defaults
            hits = redis_stats.get("hits", 0)
            misses = redis_stats.get("misses", 0)
            expirations = redis_stats.get("expirations", 0)
            references_used = redis_stats.get("references_used", 0)

            # Combine with other cache properties
            stats = {
                "name": self.name,
                "deterministic": self.deterministic,
                "hits": hits,
                "misses": misses,
                "expirations": expirations,
                "references_used": references_used,
                "total_entries": total_entries,
                "total_references": total_references,
                "max_size": self.max_size,
                "expiry_seconds": None if self.deterministic else self.expiry_seconds,
            }

            # Calculate hit rate
            total_ops = stats["hits"] + stats["misses"]
            if total_ops == 0:
                stats["hit_rate"] = "0.00%"
            else:
                stats["hit_rate"] = f"{(stats['hits'] / total_ops) * 100:.2f}%"

            return stats

        except Exception as e:
            logger.error(f"Error getting Redis cache stats: {e}")
            return {
                "name": self.name,
                "deterministic": self.deterministic,
                "hits": 0,
                "misses": 0,
                "expirations": 0,
                "references_used": 0,
                "total_entries": 0,
                "total_references": 0,
                "max_size": self.max_size,
                "expiry_seconds": None if self.deterministic else self.expiry_seconds,
                "error": str(e),
            }

    @redis_call
    def inspect_cache(self) -> dict[str, Any]:
        """Get detailed information about cache contents"""
        try:
            current_time = time.time()
            entries = []

            # Get all keys with the cache prefix
            all_key_patterns_result = self.redis.keys(f"{self.cache_prefix}*")
            all_key_list = self._convert_to_string_list(all_key_patterns_result)

            # Process up to 100 keys to avoid too large a response
            sample_keys = all_key_list[:100] if all_key_list else []

            for full_key in sample_keys:
                # Extract the original key
                key = full_key.replace(self.cache_prefix, "", 1)

                # Get data safely
                data_result = self.redis.get(full_key)
                if data_result is not None:
                    try:
                        # Ensure data is bytes
                        data_bytes = self._ensure_bytes(data_result)
                        entry = pickle.loads(data_bytes)
                        timestamp = entry.get("timestamp", 0)

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
                    except Exception as e:
                        logger.error(f"Error inspecting cache entry {key}: {e}")

            # Get references
            references = []
            all_registry_keys_result = self.redis.keys(f"{self.registry_prefix}*")
            registry_key_list = self._convert_to_string_list(all_registry_keys_result)

            sample_registry_keys = registry_key_list[:100] if registry_key_list else []

            for full_key in sample_registry_keys:
                # Extract reference ID
                ref_id = full_key.replace(self.registry_prefix, "", 1)

                # Get cache key
                cache_key_result = self.redis.get(full_key)
                if cache_key_result is not None:
                    # Convert to string safely
                    if isinstance(cache_key_result, bytes):
                        cache_key = cache_key_result.decode()
                    else:
                        cache_key = str(cache_key_result)

                    ref_preview = ref_id[:8] + "..." if len(ref_id) > 8 else ref_id
                    key_preview = (
                        cache_key[:30] + "..." if len(cache_key) > 30 else cache_key
                    )

                    references.append(
                        {
                            "ref_id": ref_preview,
                            "cache_key": key_preview,
                        }
                    )

            return {
                "cache_name": self.name,
                "entries": entries,
                "total_entries": len(all_key_list),
                "sample_size": len(entries),
                "references": references,
                "total_references": len(registry_key_list),
                "sample_references": len(references),
                "stats": self.get_stats(),
            }

        except Exception as e:
            logger.error(f"Error inspecting Redis cache: {e}")
            return {
                "cache_name": self.name,
                "error": str(e),
                "entries": [],
                "references": [],
                "stats": self.get_stats(),
            }

    @redis_call
    def _update_reference_registry(self, ref_id: str, cache_key: str) -> None:
        """Update the reference registry in Redis"""
        try:
            # Store the mapping in Redis
            full_key = f"{self.registry_prefix}{ref_id}"
            self.redis.set(full_key, cache_key)

            # Also keep a local reference in memory
            self.reference_registry[ref_id] = cache_key

        except Exception as e:
            logger.error(f"Error updating reference registry: {e}")

    def _get_cache_key_for_ref(self, ref_id: str) -> str | None:
        """Get the cache key for a reference ID from Redis"""
        try:
            # Try to get from local registry first (faster)
            if ref_id in self.reference_registry:
                return self.reference_registry[ref_id]

            # Try to get from Redis
            full_key = f"{self.registry_prefix}{ref_id}"
            result = self.redis.get(full_key)

            if result is None:
                return None

            # Convert to string
            if isinstance(result, bytes):
                return result.decode()
            else:
                return str(result)
        except Exception as e:
            logger.error(f"Error getting cache key for ref {ref_id}: {e}")
            return None

    def _normalize_cache_key(self, func_name: str, args: list, kwargs: dict) -> str:
        """Generate a normalized cache key based on function name and input parameters.
        For Redis cache, we need to ensure this matches the original implementation.
        """
        # Start with the function name
        key_parts = [func_name]

        # Prioritize finding input_data or similar input parameters
        found_input_param = False

        # Look for input_data in kwargs first (most common pattern)
        if "input_data" in kwargs:
            input_data = kwargs["input_data"]
            if hasattr(input_data, "model_dump") and callable(
                input_data.model_dump
            ):
                key_parts.append(f"input_data={input_data.model_dump()}")
            else:
                key_parts.append(f"input_data={input_data}")
            found_input_param = True

        # If no input_data, try other common input parameter names
        if not found_input_param:
            for input_key in ["query", "parameters", "data", "request"]:
                if input_key in kwargs:
                    input_value = kwargs[input_key]
                    if hasattr(input_value, "model_dump") and callable(
                        input_value.model_dump
                    ):
                        key_parts.append(f"{input_key}={input_value.model_dump()}")
                    else:
                        key_parts.append(f"{input_key}={input_value}")
                    found_input_param = True
                    break

        # If still no recognized input parameters, use all args and kwargs
        if not found_input_param:
            # Handle Pydantic models specially
            for arg in args:
                if hasattr(arg, "model_dump") and callable(arg.model_dump):
                    # Extract only the model's dict values for the key
                    key_parts.append(str(arg.model_dump()))
                else:
                    key_parts.append(str(arg))

            # Handle keyword arguments (explicitly excluding options)
            for k, v in sorted(kwargs.items()):
                if hasattr(v, "model_dump") and callable(v.model_dump):
                    key_parts.append(f"{k}={v.model_dump()}")
                else:
                    key_parts.append(f"{k}={v}")

        # Join all parts into final cache key
        return ":".join(key_parts)

    @redis_call
    def _get_keys(self, pattern: str) -> list[str]:
        """Get keys from Redis with proper error handling and type conversion"""
        try:
            keys_result = self.redis.keys(pattern)
            return self._convert_to_string_list(keys_result)
        except Exception as e:
            logger.error(f"Error getting keys with pattern {pattern}: {e}")
            return []

    @redis_call
    def _redis_get(self, key: str) -> bytes | None:
        """Get a value from Redis with proper error handling"""
        try:
            result = self.redis.get(key)
            # Return None if not found
            if result is None:
                return None
            # Ensure we return bytes
            return self._ensure_bytes(result)
        except Exception as e:
            logger.error(f"Error getting key {key} from Redis: {e}")
            return None

    def _create_preview(self, value: Any) -> str:
        """Create a short preview of the cached value"""
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
            elif isinstance(value, (list, tuple)):
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
        except Exception as e:
            logger.error(f"Error creating preview: {e}")
            return "Preview unavailable"

    @redis_call
    def _safe_delete(self, *keys) -> int:
        """Delete keys from Redis with proper error handling"""
        if not keys:
            return 0
        try:
            # Ensure all keys are valid types for Redis
            valid_keys = []
            for k in keys:
                if isinstance(k, (str, bytes)):
                    valid_keys.append(k)
                else:
                    # Try to convert to string
                    valid_keys.append(str(k))

            if not valid_keys:
                return 0

            result = self.redis.delete(*valid_keys)
            # Ensure we return an integer
            if result is None:
                return 0
            try:
                result = self.redis.delete(*valid_keys)
                return self._safe_int(result)
            except (TypeError, ValueError):
                logger.warning(f"Could not convert delete result to int: {result}")
                return 0
        except Exception as e:
            logger.error(f"Error deleting keys from Redis: {e}")
            return 0

    def cached(self, func: Callable[..., ReturnT]) -> Callable[..., Any]:
        """Redis-compatible decorator that caches function results with essential-input-based keys."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract options if present - but don't include in cache key
            options_input = kwargs.pop("options", None)  # Remove from kwargs
            options = None
            start_time = time.time()

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

            # Generate a cache key (options excluded from kwargs earlier)
            try:
                # Generate the normalized cache key using base class method
                cache_key = self._normalize_cache_key(
                    func.__name__, processed_args, processed_kwargs
                )

                # Debug log the key
                logger.debug(
                    f"Cache key: {cache_key[:50]}{'...' if len(cache_key) > 50 else ''}"
                )
            except Exception as e:
                logger.error(f"Error generating cache key: {e}")
                # Fall back to a simple key
                key_parts = [func.__name__]

                # Try to use input_data if available
                if "input_data" in processed_kwargs:
                    key_parts.append(
                        f"input_data={str(processed_kwargs['input_data'])[:50]}"
                    )
                else:
                    # Otherwise use all args and necessary kwargs
                    for arg in processed_args:
                        key_parts.append(str(arg)[:50])
                    for k, v in sorted(processed_kwargs.items()):
                        key_parts.append(f"{k}={str(v)[:50]}")

                cache_key = ":".join(key_parts)

            # Check if we have a valid cache entry
            cache_hit = False
            result = None
            ref_id = None
            try:
                if self.contains(cache_key):
                    result, _, ref_id = self.get(
                        cache_key
                    )  # Get the ref_id from the cache

                    logger.debug(f"Cache HIT for {self.name}.{func.__name__}")
                    end_time = time.time()
                    logger.debug(
                        f"⚡ Cache HIT for {self.name}.{func.__name__} [took {(end_time - start_time)*1000:.2f}ms]"
                    )
                    self._update_stats_in_redis(hits=1)
                    cache_hit = True
            except Exception as e:
                logger.error(f"Error checking cache: {e}")

            # If not in cache or expired, execute the function
            if not cache_hit:
                func_start_time = time.time()
                logger.debug(
                    f"Cache MISS for {self.name}.{func.__name__} with key: {cache_key}"
                )

                # Try to execute the function and handle errors
                try:
                    # Use func_kwargs here which includes the options
                    result = func(*processed_args, **func_kwargs)
                    self._update_stats_in_redis(misses=1)
                except Exception as e:
                    logger.error(f"Error in cached function {func.__name__}: {e!s}")
                    raise

                # Store in cache
                try:
                    self.set(cache_key, result)
                    # After setting, get the reference ID that was assigned
                    _, _, ref_id = self.get(cache_key)
                except Exception as e:
                    logger.error(f"Error setting cache: {e}")
                func_end_time = time.time()
                logger.debug(
                    f"🐢 Cache MISS for {self.name}.{func.__name__} [function execution took {(func_end_time - func_start_time)*1000:.2f}ms]"
                )

            total_time = time.time() - start_time
            logger.debug(
                f"Total time for {func.__name__}: {total_time*1000:.2f}ms (cache {'hit' if cache_hit else 'miss'})"
            )

            # Store the function name as tool_name for the result
            tool_name = func.__name__

            # Pass the options, tool name, and ref_id to handle_return_value
            return self.handle_return_value(result, options, tool_name, ref_id)

        return wrapper
