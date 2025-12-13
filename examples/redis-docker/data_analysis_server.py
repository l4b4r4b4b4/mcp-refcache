#!/usr/bin/env python3
"""Data Analysis MCP Server with Redis Backend - Docker Deployment.

This server provides data analysis tools that consume cached references
from other MCP servers (like calculator) via shared Redis/Valkey backend.

Features:
- Redis backend for distributed, multi-user caching
- HTTP streaming transport for containerized deployment
- Cross-tool reference resolution (consume refs from calculator server)
- Proper use of @cache.cached() decorator pattern

Environment Variables:
    REDIS_HOST: Redis/Valkey host (default: valkey)
    REDIS_PORT: Redis/Valkey port (default: 6379)
    REDIS_PASSWORD: Redis password (optional)
    MCP_PORT: HTTP server port (default: 8002)

Usage:
    # Run directly
    python data_analysis_server.py

    # Or via Docker Compose
    docker compose up data-analysis

Cross-Tool Workflow:
    1. calculator: generate_primes(count=50) → ref_id
    2. data-analysis: analyze_data(data=ref_id) → statistics
    3. data-analysis: transform_data(data=ref_id, operation="normalize") → new ref_id
"""

from __future__ import annotations

import math
import os
import random
import statistics
import sys
from typing import Any

# =============================================================================
# Dependency Checks
# =============================================================================

try:
    from fastmcp import FastMCP
except ImportError:
    print(
        "Error: FastMCP is not installed. Install with:\n  pip install fastmcp>=2.0.0",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import redis
except ImportError:
    print(
        "Error: redis is not installed. Install with:\n  pip install redis>=5.0.0",
        file=sys.stderr,
    )
    sys.exit(1)

from mcp_refcache import RefCache, is_ref_id
from mcp_refcache.backends import RedisBackend

# =============================================================================
# Configuration
# =============================================================================

REDIS_HOST = os.getenv("REDIS_HOST", "valkey")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
MCP_PORT = int(os.getenv("MCP_PORT", "8002"))

# =============================================================================
# Initialize Redis Backend and Cache
# =============================================================================

print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...", file=sys.stderr)

redis_backend = RedisBackend(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
)

# Verify connection
try:
    redis_backend._client.ping()
    print("Connected to Redis/Valkey successfully!", file=sys.stderr)
except redis.ConnectionError as e:
    print(f"Warning: Could not connect to Redis: {e}", file=sys.stderr)
    print("Continuing anyway - will retry on first cache operation", file=sys.stderr)

# Create RefCache with Redis backend
cache = RefCache(
    name="redis-data-analysis",
    backend=redis_backend,
    default_ttl=3600,  # 1 hour
)

# =============================================================================
# Initialize FastMCP Server
# =============================================================================

mcp = FastMCP(
    name="Redis Data Analysis",
    instructions="""A data analysis server with Redis-backed caching.

Consumes cached references from other MCP servers (like calculator)
via shared Redis backend. Can analyze, transform, and aggregate data.

Available tools:
- analyze_data: Statistical analysis (accepts ref_id or raw data)
- transform_data: Transform data (normalize, standardize, scale, etc.)
- aggregate_data: Combine multiple datasets
- create_sample_data: Generate sample data for testing
- get_cached_result: Retrieve cached results with pagination
- list_shared_cache: List all cached references from all servers
""",
)


# =============================================================================
# Helper Functions
# =============================================================================


def resolve_data(data: list[float] | str) -> list[float]:
    """Resolve data from either raw list or ref_id.

    This is the key function for cross-tool reference sharing.
    If data is a ref_id string, it fetches the cached value from Redis.
    """
    if isinstance(data, str) and is_ref_id(data):
        # Fetch from shared Redis cache - could be from any MCP server!
        # Use cache.resolve() to get the FULL value, not cache.get() which returns preview
        value = cache.resolve(data)
        if not isinstance(value, list):
            raise ValueError(f"Expected list data, got {type(value).__name__}")
        return [float(x) for x in value]
    elif isinstance(data, list):
        return [float(x) for x in data]
    else:
        raise ValueError(f"Invalid data type: {type(data).__name__}")


def compute_statistics(data: list[float]) -> dict[str, Any]:
    """Compute comprehensive statistics for numeric data."""
    if not data:
        return {"error": "Empty dataset"}

    n = len(data)
    sorted_data = sorted(data)

    result = {
        "count": n,
        "sum": sum(data),
        "mean": statistics.mean(data),
        "min": min(data),
        "max": max(data),
        "range": max(data) - min(data),
    }

    if n >= 2:
        result["std"] = statistics.stdev(data)
        result["variance"] = statistics.variance(data)

    # Quartiles
    result["median"] = statistics.median(data)
    if n >= 4:
        mid = n // 2
        lower_half = sorted_data[:mid]
        upper_half = sorted_data[mid:] if n % 2 == 0 else sorted_data[mid + 1 :]
        result["q1"] = statistics.median(lower_half) if lower_half else result["median"]
        result["q3"] = statistics.median(upper_half) if upper_half else result["median"]
        result["iqr"] = result["q3"] - result["q1"]

    return result


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool()
async def analyze_data(data: list[float] | str) -> dict[str, Any]:
    """Perform statistical analysis on numeric data.

    Accepts either raw data or a ref_id from another tool (e.g., calculator).
    This enables cross-tool workflows where one server generates data and
    this server analyzes it.

    Args:
        data: Numeric data as list OR ref_id from another tool

    Returns:
        Statistical analysis including mean, median, std, quartiles, etc.

    Example:
        # With raw data
        analyze_data(data=[1, 2, 3, 4, 5])

        # With cross-tool reference
        analyze_data(data="redis-calculator:abc123")
    """
    try:
        resolved = resolve_data(data)
        stats = compute_statistics(resolved)

        # Add source info
        if isinstance(data, str):
            stats["source_ref_id"] = data
        stats["input_size"] = len(resolved)

        return stats
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
@cache.cached(namespace="transforms")
async def transform_data(
    data: list[float] | str,
    operation: str = "normalize",
    scale_factor: float = 1.0,
) -> list[float]:
    """Transform numeric data and cache the result.

    Accepts either raw data or a ref_id from another tool.

    Operations:
        - normalize: Scale to [0, 1] range
        - standardize: Z-score normalization (mean=0, std=1)
        - scale: Multiply by scale_factor
        - log: Natural logarithm (values must be positive)
        - sqrt: Square root (values must be non-negative)
        - abs: Absolute value
        - diff: Differences between consecutive values
        - cumsum: Cumulative sum

    Args:
        data: Numeric data as list OR ref_id from another tool
        operation: Transform operation to apply
        scale_factor: Scale factor for 'scale' operation

    Returns:
        Cached response with transformed data
    """
    resolved = resolve_data(data)

    if not resolved:
        raise ValueError("Empty dataset")

    operation = operation.lower()

    if operation == "normalize":
        min_val, max_val = min(resolved), max(resolved)
        if max_val == min_val:
            return [0.5] * len(resolved)
        return [(x - min_val) / (max_val - min_val) for x in resolved]

    elif operation == "standardize":
        if len(resolved) < 2:
            raise ValueError("Need at least 2 values for standardization")
        mean = statistics.mean(resolved)
        std = statistics.stdev(resolved)
        if std == 0:
            return [0.0] * len(resolved)
        return [(x - mean) / std for x in resolved]

    elif operation == "scale":
        return [x * scale_factor for x in resolved]

    elif operation == "log":
        if any(x <= 0 for x in resolved):
            raise ValueError("All values must be positive for log transform")
        return [math.log(x) for x in resolved]

    elif operation == "sqrt":
        if any(x < 0 for x in resolved):
            raise ValueError("All values must be non-negative for sqrt transform")
        return [math.sqrt(x) for x in resolved]

    elif operation == "abs":
        return [abs(x) for x in resolved]

    elif operation == "diff":
        if len(resolved) < 2:
            raise ValueError("Need at least 2 values for diff")
        return [resolved[i] - resolved[i - 1] for i in range(1, len(resolved))]

    elif operation == "cumsum":
        result = []
        total = 0.0
        for x in resolved:
            total += x
            result.append(total)
        return result

    else:
        raise ValueError(
            f"Unknown operation: {operation}. "
            "Valid operations: normalize, standardize, scale, log, sqrt, abs, diff, cumsum"
        )


@mcp.tool()
@cache.cached(namespace="aggregates")
async def aggregate_data(
    datasets: list[list[float] | str],
    operation: str = "concat",
) -> list[float]:
    """Aggregate multiple datasets into one.

    Each dataset can be raw data or a ref_id from another tool.

    Operations:
        - concat: Concatenate all datasets
        - sum: Element-wise sum (datasets must be same length)
        - mean: Element-wise mean (datasets must be same length)
        - zip: Interleave values from each dataset

    Args:
        datasets: List of datasets (each can be raw data or ref_id)
        operation: Aggregation operation

    Returns:
        Cached response with aggregated data
    """
    if not datasets:
        raise ValueError("No datasets provided")

    # Resolve all datasets
    resolved_datasets = [resolve_data(ds) for ds in datasets]

    operation = operation.lower()

    if operation == "concat":
        result = []
        for ds in resolved_datasets:
            result.extend(ds)
        return result

    elif operation == "sum":
        if not all(len(ds) == len(resolved_datasets[0]) for ds in resolved_datasets):
            raise ValueError("All datasets must have the same length for sum operation")
        return [sum(values) for values in zip(*resolved_datasets)]

    elif operation == "mean":
        if not all(len(ds) == len(resolved_datasets[0]) for ds in resolved_datasets):
            raise ValueError(
                "All datasets must have the same length for mean operation"
            )
        return [statistics.mean(values) for values in zip(*resolved_datasets)]

    elif operation == "zip":
        result = []
        max_len = max(len(ds) for ds in resolved_datasets)
        for i in range(max_len):
            for ds in resolved_datasets:
                if i < len(ds):
                    result.append(ds[i])
        return result

    else:
        raise ValueError(
            f"Unknown operation: {operation}. Valid operations: concat, sum, mean, zip"
        )


@mcp.tool()
@cache.cached(namespace="samples")
async def create_sample_data(
    size: int = 100,
    distribution: str = "uniform",
    min_value: float = 0,
    max_value: float = 100,
) -> list[float]:
    """Generate sample data for testing.

    Args:
        size: Number of data points (1-10000)
        distribution: 'uniform', 'normal', or 'exponential'
        min_value: Minimum value (for uniform distribution)
        max_value: Maximum value (for uniform distribution)

    Returns:
        Cached response with generated sample data
    """
    if size < 1 or size > 10000:
        raise ValueError("Size must be between 1 and 10000")

    distribution = distribution.lower()

    if distribution == "uniform":
        return [random.uniform(min_value, max_value) for _ in range(size)]

    elif distribution == "normal":
        mean = (min_value + max_value) / 2
        std = (max_value - min_value) / 6  # ~99.7% within range
        return [random.gauss(mean, std) for _ in range(size)]

    elif distribution == "exponential":
        scale = (max_value - min_value) / 3
        return [min_value + random.expovariate(1 / scale) for _ in range(size)]

    else:
        raise ValueError(
            f"Unknown distribution: {distribution}. "
            "Valid distributions: uniform, normal, exponential"
        )


@mcp.tool()
async def get_cached_result(
    ref_id: str,
    page: int | None = None,
    page_size: int | None = None,
    max_size: int | None = None,
) -> dict[str, Any]:
    """Retrieve a cached result with optional pagination.

    Can retrieve references from ANY MCP server sharing the Redis cache.

    Args:
        ref_id: Reference ID (e.g., 'redis-calculator:abc123', 'redis-data-analysis:xyz789')
        page: Page number (1-indexed) for pagination
        page_size: Items per page
        max_size: Maximum preview size

    Returns:
        Cached value with metadata
    """
    try:
        response = cache.get(ref_id, page=page, page_size=page_size, max_size=max_size)
        if response is None:
            return {"error": f"Reference not found: {ref_id}"}
        return response.model_dump()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def list_shared_cache(namespace: str | None = None) -> dict[str, Any]:
    """List all cached references from all MCP servers.

    Shows references from the shared Redis cache, including those created
    by other servers like calculator.

    Args:
        namespace: Optional namespace filter

    Returns:
        List of cached references with metadata
    """
    try:
        keys = redis_backend.keys(namespace=namespace)

        references = []
        for key in keys[:50]:  # Limit to 50 entries
            entry = redis_backend.get(key)
            if entry:
                references.append(
                    {
                        "key": key,
                        "namespace": entry.namespace,
                        "created_at": entry.created_at,
                        "expires_at": entry.expires_at,
                    }
                )

        return {
            "total_keys": len(keys),
            "shown": len(references),
            "references": references,
            "redis_host": REDIS_HOST,
            "redis_port": REDIS_PORT,
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run the Data Analysis MCP server."""
    print(f"Starting Data Analysis MCP Server on port {MCP_PORT}...", file=sys.stderr)
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}", file=sys.stderr)

    # Run with HTTP streaming transport for Docker deployment
    mcp.run(transport="sse", host="0.0.0.0", port=MCP_PORT)


if __name__ == "__main__":
    main()
