"""Redis cache backend implementation.

Provides a distributed cache backend using Redis for multi-user and
multi-machine scenarios. Supports connection pooling, native TTL,
and authentication.

Requires the `redis` package: pip install mcp-refcache[redis]
"""

import json
import os
import time
from typing import Any

from mcp_refcache.backends.base import CacheEntry
from mcp_refcache.permissions import AccessPolicy

try:
    import redis
    from redis import ConnectionPool, Redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None  # type: ignore[assignment]
    ConnectionPool = None  # type: ignore[assignment,misc]
    Redis = None  # type: ignore[assignment,misc]


class RedisBackend:
    """Redis-based distributed cache backend.

    Uses Redis for distributed caching across multiple machines or users.
    Supports connection pooling, native TTL handling, and authentication.

    Features:
        - Distributed caching across multiple machines
        - Native TTL handling via Redis expiration
        - Connection pooling for thread safety
        - Support for Redis authentication and SSL
        - Valkey compatible (drop-in Redis replacement)

    Example:
        ```python
        # Connect to local Redis with default settings
        backend = RedisBackend(password="your-password")

        # Connect to remote Redis
        backend = RedisBackend(
            host="redis.example.com",
            port=6379,
            password="secret",
            ssl=True,
        )

        # Connect via URL (password in URL)
        backend = RedisBackend(url="redis://:password@host:6379/0")

        # Connect via URL with SSL
        backend = RedisBackend(url="rediss://:password@host:6379/0")

        entry = CacheEntry(
            value={"data": "example"},
            namespace="public",
            policy=AccessPolicy(),
            created_at=time.time(),
        )
        backend.set("my_key", entry)
        result = backend.get("my_key")
        ```
    """

    KEY_PREFIX = "mcp-refcache:entry:"

    def __init__(
        self,
        url: str | None = None,
        host: str | None = None,
        port: int | None = None,
        db: int | None = None,
        password: str | None = None,
        ssl: bool | None = None,
        socket_timeout: float = 5.0,
        max_connections: int = 10,
    ) -> None:
        """Initialize Redis connection pool.

        Connection parameters can be provided directly or via environment
        variables. Direct parameters take precedence over environment variables.

        Environment Variables:
            REDIS_URL: Full connection URL (takes precedence over other env vars)
            REDIS_HOST: Redis host (default: localhost)
            REDIS_PORT: Redis port (default: 6379)
            REDIS_DB: Redis database number (default: 0)
            REDIS_PASSWORD: Redis password
            REDIS_SSL: Enable SSL ("true" or "1")

        Args:
            url: Redis connection URL (e.g., "redis://:password@host:6379/0").
                Takes precedence over individual parameters.
            host: Redis server hostname (default: localhost).
            port: Redis server port (default: 6379).
            db: Redis database number (default: 0).
            password: Redis password for authentication.
            ssl: Enable SSL/TLS connection.
            socket_timeout: Timeout for socket operations in seconds.
            max_connections: Maximum connections in the pool.

        Raises:
            ImportError: If the redis package is not installed.
            redis.ConnectionError: If unable to connect to Redis.
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis package not installed. "
                "Install with: pip install mcp-refcache[redis]"
            )

        # Resolve connection parameters from args, env vars, or defaults
        resolved_url = url or os.environ.get("REDIS_URL")
        resolved_host = host or os.environ.get("REDIS_HOST", "localhost")
        resolved_port = port or int(os.environ.get("REDIS_PORT", "6379"))
        resolved_db = db if db is not None else int(os.environ.get("REDIS_DB", "0"))
        resolved_password = password or os.environ.get("REDIS_PASSWORD")
        resolved_ssl = ssl
        if resolved_ssl is None:
            env_ssl = os.environ.get("REDIS_SSL", "").lower()
            resolved_ssl = env_ssl in ("true", "1", "yes")

        # Create connection pool
        if resolved_url:
            self._pool: ConnectionPool = ConnectionPool.from_url(
                resolved_url,
                socket_timeout=socket_timeout,
                max_connections=max_connections,
                decode_responses=True,
            )
        elif resolved_ssl:
            # Use SSL connection class for secure connections
            self._pool = ConnectionPool(
                host=resolved_host,
                port=resolved_port,
                db=resolved_db,
                password=resolved_password,
                socket_timeout=socket_timeout,
                max_connections=max_connections,
                decode_responses=True,
                connection_class=redis.connection.SSLConnection,
            )
        else:
            # Standard connection without SSL
            self._pool = ConnectionPool(
                host=resolved_host,
                port=resolved_port,
                db=resolved_db,
                password=resolved_password,
                socket_timeout=socket_timeout,
                max_connections=max_connections,
                decode_responses=True,
            )

        # Create Redis client with connection pool
        self._client: Redis = Redis(connection_pool=self._pool)

        # Store connection info for debugging
        self._connection_info = {
            "url": resolved_url,
            "host": resolved_host,
            "port": resolved_port,
            "db": resolved_db,
            "ssl": resolved_ssl,
        }

    def _make_key(self, key: str) -> str:
        """Create the full Redis key with prefix.

        Args:
            key: The cache key.

        Returns:
            Full Redis key with prefix.
        """
        return f"{self.KEY_PREFIX}{key}"

    def _serialize_entry(self, entry: CacheEntry) -> str:
        """Convert CacheEntry to JSON string for Redis storage.

        Args:
            entry: The CacheEntry to serialize.

        Returns:
            JSON string representation.
        """
        return json.dumps(
            {
                "value": entry.value,
                "namespace": entry.namespace,
                "policy": entry.policy.model_dump(mode="json"),
                "created_at": entry.created_at,
                "expires_at": entry.expires_at,
                "metadata": entry.metadata,
            },
            default=str,
        )

    def _deserialize_entry(self, data: str) -> CacheEntry:
        """Convert JSON string from Redis to CacheEntry.

        Args:
            data: JSON string from Redis.

        Returns:
            Reconstructed CacheEntry object.
        """
        parsed = json.loads(data)
        return CacheEntry(
            value=parsed["value"],
            namespace=parsed["namespace"],
            policy=AccessPolicy(**parsed["policy"]),
            created_at=parsed["created_at"],
            expires_at=parsed["expires_at"],
            metadata=parsed.get("metadata", {}),
        )

    def _calculate_ttl_seconds(self, entry: CacheEntry) -> int | None:
        """Calculate Redis TTL in seconds from entry expiration.

        Args:
            entry: The cache entry with potential expiration.

        Returns:
            TTL in seconds, or None if no expiration.
        """
        if entry.expires_at is None:
            return None

        ttl_seconds = int(entry.expires_at - time.time())
        if ttl_seconds <= 0:
            # Already expired, set minimal TTL so Redis removes it
            return 1
        return ttl_seconds

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve an entry by key.

        Redis handles TTL automatically, so expired entries are already removed.

        Args:
            key: The cache key to look up.

        Returns:
            The CacheEntry if found, None otherwise.
        """
        redis_key = self._make_key(key)
        data = self._client.get(redis_key)

        if data is None:
            return None

        entry = self._deserialize_entry(data)

        # Double-check expiration (in case TTL wasn't set or clock skew)
        if entry.expires_at is not None and time.time() >= entry.expires_at:
            self._client.delete(redis_key)
            return None

        return entry

    def set(self, key: str, entry: CacheEntry) -> None:
        """Store an entry with optional TTL.

        Uses Redis native TTL for automatic expiration.

        Args:
            key: The cache key to store under.
            entry: The CacheEntry to store.
        """
        redis_key = self._make_key(key)
        serialized = self._serialize_entry(entry)
        ttl_seconds = self._calculate_ttl_seconds(entry)

        if ttl_seconds is not None:
            self._client.setex(redis_key, ttl_seconds, serialized)
        else:
            self._client.set(redis_key, serialized)

    def delete(self, key: str) -> bool:
        """Delete an entry by key.

        Args:
            key: The cache key to delete.

        Returns:
            True if the entry was deleted, False if it didn't exist.
        """
        redis_key = self._make_key(key)
        deleted_count = self._client.delete(redis_key)
        return deleted_count > 0

    def exists(self, key: str) -> bool:
        """Check if a key exists.

        Redis automatically removes expired keys, so this is a simple check.

        Args:
            key: The cache key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        redis_key = self._make_key(key)

        if not self._client.exists(redis_key):
            return False

        # Double-check expiration for entries with expires_at set
        # (handles potential clock skew or manual expiration check)
        data = self._client.get(redis_key)
        if data is None:
            return False

        entry = self._deserialize_entry(data)
        if entry.expires_at is not None and time.time() >= entry.expires_at:
            self._client.delete(redis_key)
            return False

        return True

    def clear(self, namespace: str | None = None) -> int:
        """Clear entries from the cache.

        Args:
            namespace: If provided, only clear entries in this namespace.
                      If None, clear all mcp-refcache entries.

        Returns:
            The number of entries that were cleared.
        """
        pattern = f"{self.KEY_PREFIX}*"
        cleared_count = 0

        # Use SCAN to iterate through keys (safer than KEYS for large datasets)
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match=pattern, count=100)

            if keys:
                if namespace is None:
                    # Delete all matching keys
                    cleared_count += self._client.delete(*keys)
                else:
                    # Filter by namespace and delete
                    keys_to_delete = []
                    for redis_key in keys:
                        data = self._client.get(redis_key)
                        if data:
                            entry = self._deserialize_entry(data)
                            if entry.namespace == namespace:
                                keys_to_delete.append(redis_key)

                    if keys_to_delete:
                        cleared_count += self._client.delete(*keys_to_delete)

            if cursor == 0:
                break

        return cleared_count

    def keys(self, namespace: str | None = None) -> list[str]:
        """List all keys in the cache.

        Args:
            namespace: If provided, only return keys in this namespace.
                      If None, return all keys.

        Returns:
            List of cache keys (without the Redis prefix).
        """
        pattern = f"{self.KEY_PREFIX}*"
        result_keys: list[str] = []
        current_time = time.time()

        # Use SCAN to iterate through keys
        cursor = 0
        while True:
            cursor, redis_keys = self._client.scan(cursor, match=pattern, count=100)

            for redis_key in redis_keys:
                # Strip prefix to get original key
                original_key = redis_key[len(self.KEY_PREFIX) :]

                # Filter by namespace if specified
                if namespace is not None:
                    data = self._client.get(redis_key)
                    if data:
                        entry = self._deserialize_entry(data)
                        # Check expiration
                        if (
                            entry.expires_at is not None
                            and current_time >= entry.expires_at
                        ):
                            self._client.delete(redis_key)
                            continue
                        if entry.namespace == namespace:
                            result_keys.append(original_key)
                else:
                    # Check expiration for all keys
                    data = self._client.get(redis_key)
                    if data:
                        entry = self._deserialize_entry(data)
                        if (
                            entry.expires_at is not None
                            and current_time >= entry.expires_at
                        ):
                            self._client.delete(redis_key)
                            continue
                        result_keys.append(original_key)

            if cursor == 0:
                break

        return result_keys

    def close(self) -> None:
        """Close the connection pool.

        This should be called when the backend is no longer needed.
        """
        self._client.close()
        self._pool.disconnect()

    def ping(self) -> bool:
        """Test the Redis connection.

        Returns:
            True if Redis is reachable, False otherwise.
        """
        try:
            return self._client.ping()
        except Exception:
            return False

    @property
    def connection_info(self) -> dict[str, Any]:
        """Get connection information for debugging.

        Returns:
            Dictionary with connection parameters (password masked).
        """
        return self._connection_info.copy()
