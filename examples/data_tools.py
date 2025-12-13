#!/usr/bin/env python3
"""Data Tools MCP Server - Cross-Tool Reference Sharing Example.

This example demonstrates cross-tool reference sharing between MCP servers
using a shared SQLite backend. This server provides data analysis tools
that can consume references created by other MCP servers.

Use Case:
    1. langfuse-calculator: generate_primes(count=100) → returns ref_id
    2. data-tools: analyze_data(ref_id) → resolves and analyzes the primes

Both servers share the same SQLite database, enabling seamless reference
passing between tools in a single-user, single-machine setup (e.g., Zed IDE).

Features demonstrated:
- SQLite backend for persistent cross-tool caching
- Reference resolution from external MCP servers
- Access policy enforcement across tool boundaries
- Langfuse tracing for observability
- Data analysis tools that work with cached references

Prerequisites:
    1. Install dependencies: pip install langfuse
    2. Set Langfuse credentials (optional, for tracing):
        LANGFUSE_PUBLIC_KEY=pk-lf-...
        LANGFUSE_SECRET_KEY=sk-lf-...
        LANGFUSE_HOST=https://cloud.langfuse.com

Usage:
    # Run the server
    python examples/data_tools.py

    # Or with SSE transport for debugging
    python examples/data_tools.py --transport sse --port 8001

Zed Configuration (.zed/settings.json):
    "context_servers": {
        "data-tools": {
            "command": "uv",
            "args": ["run", "python", "examples/data_tools.py"],
            "env": {
                "LANGFUSE_PUBLIC_KEY": "pk-lf-...",
                "LANGFUSE_SECRET_KEY": "sk-lf-...",
                "LANGFUSE_HOST": "https://cloud.langfuse.com"
            }
        }
    }

Cross-Tool Reference Workflow:
    1. In langfuse-calculator: generate_primes(count=50)
       → Returns: {"ref_id": "langfuse-calculator:abc123", "value": [...]}

    2. In data-tools: analyze_data(data="langfuse-calculator:abc123")
       → Resolves the reference from shared SQLite cache
       → Returns: {"mean": 57.3, "median": 53, "std": 32.1, ...}

    3. Access policies are enforced - if the original ref was created
       with restricted permissions, resolution will fail appropriately.
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Check for dependencies
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
    from langfuse import get_client, observe, propagate_attributes
except ImportError:
    print(
        "Error: Langfuse is not installed. Install with:\n  pip install langfuse",
        file=sys.stderr,
    )
    sys.exit(1)

# =============================================================================
# Import mcp-refcache components
# =============================================================================

from mcp_refcache import (
    AccessPolicy,
    Permission,
    PreviewConfig,
    PreviewStrategy,
    RefCache,
    SQLiteBackend,
)
from mcp_refcache.fastmcp import cache_instructions

# =============================================================================
# Initialize Langfuse
# =============================================================================

langfuse = get_client()

_langfuse_enabled = all(
    [
        os.getenv("LANGFUSE_PUBLIC_KEY"),
        os.getenv("LANGFUSE_SECRET_KEY"),
    ]
)

if not _langfuse_enabled:
    print(
        "Warning: Langfuse credentials not set. Tracing will be disabled.\n"
        "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable tracing.",
        file=sys.stderr,
    )

# =============================================================================
# Initialize FastMCP Server
# =============================================================================

mcp = FastMCP(
    name="Data Tools",
    instructions=f"""Data analysis tools with cross-tool reference support.

This server shares a SQLite cache with other MCP servers (like langfuse-calculator),
allowing you to pass references between tools seamlessly.

Available tools:
- analyze_data: Statistical analysis of numeric data (accepts ref_id from other tools)
- transform_data: Transform data (scale, normalize, filter)
- aggregate_data: Aggregate multiple datasets
- create_sample_data: Generate sample datasets for testing
- get_cached_result: Retrieve or paginate through cached results
- list_shared_cache: View all references in the shared cache

Cross-Tool Reference Example:
    1. In langfuse-calculator: generate_primes(count=50) → ref_id
    2. In data-tools: analyze_data(data=ref_id) → statistics

{cache_instructions()}
""",
)

# =============================================================================
# Initialize RefCache with SQLite Backend (SHARED across tools)
# =============================================================================

# Use SQLite backend for persistence and cross-tool sharing
# Default path: ~/.cache/mcp-refcache/cache.db
sqlite_backend = SQLiteBackend()

print(f"SQLite cache path: {sqlite_backend.database_path}", file=sys.stderr)

cache = RefCache(
    name="data-tools",
    backend=sqlite_backend,
    default_ttl=3600,  # 1 hour TTL
    preview_config=PreviewConfig(
        max_size=64,
        default_strategy=PreviewStrategy.SAMPLE,
    ),
)


# =============================================================================
# Pydantic Models
# =============================================================================


class DataInput(BaseModel):
    """Input for data analysis - accepts raw data or ref_id."""

    data: list[float] | str = Field(
        ...,
        description="Numeric data as list OR a ref_id from another tool "
        "(e.g., 'langfuse-calculator:abc123'). The ref_id will be "
        "automatically resolved from the shared SQLite cache.",
    )


class TransformInput(BaseModel):
    """Input for data transformation."""

    data: list[float] | str = Field(
        ...,
        description="Numeric data or ref_id to transform.",
    )
    operation: str = Field(
        default="normalize",
        description="Transform operation: 'normalize', 'scale', 'log', 'sqrt', "
        "'filter_positive', 'filter_negative', 'abs', 'cumsum'.",
    )
    scale_factor: float = Field(
        default=1.0,
        description="Scale factor for 'scale' operation.",
    )


class AggregateInput(BaseModel):
    """Input for aggregating multiple datasets."""

    datasets: list[list[float] | str] = Field(
        ...,
        description="List of datasets (each can be a list or ref_id).",
    )
    operation: str = Field(
        default="concat",
        description="Aggregation: 'concat', 'sum', 'mean', 'zip'.",
    )


class SampleDataInput(BaseModel):
    """Input for generating sample data."""

    size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Number of data points to generate.",
    )
    distribution: str = Field(
        default="uniform",
        description="Distribution: 'uniform', 'normal', 'integers', 'fibonacci'.",
    )
    min_value: float = Field(default=0.0, description="Minimum value (for uniform).")
    max_value: float = Field(default=100.0, description="Maximum value (for uniform).")


# =============================================================================
# Helper Functions
# =============================================================================


def resolve_data(data: list[float] | str) -> list[float]:
    """Resolve data from ref_id or pass through if already a list.

    This is the key function for cross-tool reference sharing.
    If data is a ref_id string, it resolves from the shared SQLite cache.
    """
    if isinstance(data, list):
        return data

    # It's a ref_id - resolve from cache
    # The cache.resolve() method handles cross-tool refs because
    # all tools share the same SQLite database
    result = cache.resolve(data, actor="agent")
    return list(result.value)


def get_langfuse_attributes() -> dict[str, Any]:
    """Get Langfuse tracing attributes."""
    return {
        "user_id": "demo_user",
        "session_id": "demo_session",
        "metadata": {"tool": "data-tools", "cache_backend": "sqlite"},
        "tags": ["data-tools", "cross-reference"],
        "version": "1.0.0",
    }


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool
@observe(name="analyze_data")
@cache.cached(namespace="analysis", max_size=100)
async def analyze_data(data: list[float] | str) -> dict[str, Any]:
    """Perform statistical analysis on numeric data.

    Accepts either raw data or a ref_id from another MCP tool
    (e.g., langfuse-calculator). The ref_id is automatically resolved
    from the shared SQLite cache.

    Args:
        data: Numeric data as list OR ref_id string from another tool.
              Example ref_id: "langfuse-calculator:abc123"

    Returns:
        Statistical analysis including mean, median, std, quartiles, etc.

    Example:
        # Direct data
        analyze_data(data=[1, 2, 3, 4, 5])

        # Cross-tool reference (from langfuse-calculator)
        analyze_data(data="langfuse-calculator:abc123")
    """
    attributes = get_langfuse_attributes()

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata=attributes["metadata"],
        tags=attributes["tags"],
    ):
        # Resolve data (handles both raw lists and ref_ids)
        resolved_data = resolve_data(data)

        if not resolved_data:
            return {"error": "Empty dataset"}

        # Convert to floats
        numeric_data = [float(x) for x in resolved_data]

        # Calculate statistics
        result: dict[str, Any] = {
            "count": len(numeric_data),
            "sum": sum(numeric_data),
            "mean": statistics.mean(numeric_data),
            "min": min(numeric_data),
            "max": max(numeric_data),
            "range": max(numeric_data) - min(numeric_data),
        }

        if len(numeric_data) >= 2:
            result["std"] = statistics.stdev(numeric_data)
            result["variance"] = statistics.variance(numeric_data)
            result["median"] = statistics.median(numeric_data)

        if len(numeric_data) >= 4:
            result["quartiles"] = statistics.quantiles(numeric_data, n=4)

        # Additional insights
        result["is_sorted"] = numeric_data == sorted(numeric_data)
        result["unique_count"] = len(set(numeric_data))
        result["has_duplicates"] = result["unique_count"] < len(numeric_data)

        # For integer-like data, check if all primes (useful for cross-ref with calculator)
        if all(x == int(x) and x > 0 for x in numeric_data):
            integers = [int(x) for x in numeric_data]
            result["all_positive_integers"] = True
            # Check if sorted ascending (like prime sequence)
            result["is_ascending"] = integers == sorted(integers)

        langfuse.flush()
        return result


@mcp.tool
@observe(name="transform_data")
@cache.cached(namespace="transforms", max_size=100)
async def transform_data(
    data: list[float] | str,
    operation: str = "normalize",
    scale_factor: float = 1.0,
) -> list[float]:
    """Transform numeric data with various operations.

    Args:
        data: Numeric data or ref_id to transform.
        operation: Transform operation to apply.
        scale_factor: Scale factor for 'scale' operation.

    Returns:
        Transformed data as a list of floats.
    """
    attributes = get_langfuse_attributes()

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata={**attributes["metadata"], "operation": operation},
        tags=attributes["tags"],
    ):
        resolved_data = resolve_data(data)
        numeric_data = [float(x) for x in resolved_data]

        if not numeric_data:
            return []

        if operation == "normalize":
            min_val, max_val = min(numeric_data), max(numeric_data)
            if max_val == min_val:
                return [0.5] * len(numeric_data)
            return [(x - min_val) / (max_val - min_val) for x in numeric_data]

        elif operation == "scale":
            return [x * scale_factor for x in numeric_data]

        elif operation == "log":
            return [math.log(x) if x > 0 else float("-inf") for x in numeric_data]

        elif operation == "sqrt":
            return [math.sqrt(x) if x >= 0 else float("nan") for x in numeric_data]

        elif operation == "filter_positive":
            return [x for x in numeric_data if x > 0]

        elif operation == "filter_negative":
            return [x for x in numeric_data if x < 0]

        elif operation == "abs":
            return [abs(x) for x in numeric_data]

        elif operation == "cumsum":
            result = []
            cumulative = 0.0
            for x in numeric_data:
                cumulative += x
                result.append(cumulative)
            return result

        else:
            raise ValueError(f"Unknown operation: {operation}")


@mcp.tool
@observe(name="aggregate_data")
@cache.cached(namespace="aggregations", max_size=100)
async def aggregate_data(
    datasets: list[list[float] | str],
    operation: str = "concat",
) -> list[float]:
    """Aggregate multiple datasets into one.

    Can combine data from multiple tools - each dataset can be a ref_id.

    Args:
        datasets: List of datasets (each can be raw data or ref_id).
        operation: How to aggregate: 'concat', 'sum', 'mean', 'zip'.

    Returns:
        Aggregated data.
    """
    attributes = get_langfuse_attributes()

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata={**attributes["metadata"], "operation": operation},
        tags=attributes["tags"],
    ):
        # Resolve all datasets
        resolved_datasets = [resolve_data(d) for d in datasets]

        if operation == "concat":
            result: list[float] = []
            for dataset in resolved_datasets:
                result.extend(float(x) for x in dataset)
            return result

        elif operation == "sum":
            # Element-wise sum (pad shorter lists with 0)
            max_len = max(len(d) for d in resolved_datasets)
            result = [0.0] * max_len
            for dataset in resolved_datasets:
                for i, val in enumerate(dataset):
                    result[i] += float(val)
            return result

        elif operation == "mean":
            # Element-wise mean
            max_len = max(len(d) for d in resolved_datasets)
            sums = [0.0] * max_len
            counts = [0] * max_len
            for dataset in resolved_datasets:
                for i, val in enumerate(dataset):
                    sums[i] += float(val)
                    counts[i] += 1
            return [s / c if c > 0 else 0.0 for s, c in zip(sums, counts, strict=False)]

        elif operation == "zip":
            # Interleave datasets
            result = []
            max_len = max(len(d) for d in resolved_datasets)
            for i in range(max_len):
                for dataset in resolved_datasets:
                    if i < len(dataset):
                        result.append(float(dataset[i]))
            return result

        else:
            raise ValueError(f"Unknown operation: {operation}")


@mcp.tool
@observe(name="create_sample_data")
@cache.cached(namespace="samples", max_size=100)
async def create_sample_data(
    size: int = 100,
    distribution: str = "uniform",
    min_value: float = 0.0,
    max_value: float = 100.0,
) -> list[float]:
    """Generate sample data for testing.

    Args:
        size: Number of data points (1-10000).
        distribution: Type of distribution.
        min_value: Minimum value for uniform distribution.
        max_value: Maximum value for uniform distribution.

    Returns:
        Generated sample data.
    """
    import random

    attributes = get_langfuse_attributes()

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata={**attributes["metadata"], "distribution": distribution},
        tags=attributes["tags"],
    ):
        if distribution == "uniform":
            return [random.uniform(min_value, max_value) for _ in range(size)]

        elif distribution == "normal":
            mean = (min_value + max_value) / 2
            std = (max_value - min_value) / 4
            return [random.gauss(mean, std) for _ in range(size)]

        elif distribution == "integers":
            return [
                float(random.randint(int(min_value), int(max_value)))
                for _ in range(size)
            ]

        elif distribution == "fibonacci":
            result = [0.0, 1.0]
            while len(result) < size:
                result.append(result[-1] + result[-2])
            return result[:size]

        else:
            raise ValueError(f"Unknown distribution: {distribution}")


@mcp.tool
@observe(name="get_cached_result")
async def get_cached_result(
    ref_id: str,
    page: int | None = None,
    page_size: int | None = None,
    max_size: int | None = None,
) -> dict[str, Any]:
    """Retrieve a cached result from the shared SQLite cache.

    This can retrieve references created by ANY MCP server that shares
    the same SQLite database (e.g., langfuse-calculator, data-tools).

    Args:
        ref_id: Reference ID (e.g., 'langfuse-calculator:abc123').
        page: Page number for pagination (1-indexed).
        page_size: Items per page.
        max_size: Maximum preview size.

    Returns:
        Cached value with metadata.
    """
    attributes = get_langfuse_attributes()

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata={**attributes["metadata"], "ref_id": ref_id[:50]},
        tags=attributes["tags"],
    ):
        response = cache.get(
            ref_id,
            actor="agent",
            page=page,
            page_size=page_size,
            max_size=max_size,
        )

        langfuse.flush()

        return {
            "ref_id": response.ref_id,
            "value": response.value if hasattr(response, "value") else response.preview,
            "preview": response.preview,
            "is_complete": response.is_complete,
            "total_items": response.total_items,
            "page": response.page,
            "total_pages": response.total_pages,
        }


@mcp.tool
@observe(name="list_shared_cache")
async def list_shared_cache(namespace: str | None = None) -> dict[str, Any]:
    """List all references in the shared SQLite cache.

    Shows references from ALL MCP servers that share this cache,
    useful for discovering what data is available for cross-tool use.

    Args:
        namespace: Filter by namespace (optional).

    Returns:
        List of cached references with metadata.
    """
    attributes = get_langfuse_attributes()

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata=attributes["metadata"],
        tags=attributes["tags"],
    ):
        # Get all keys from the backend
        keys = sqlite_backend.keys(namespace=namespace)

        references = []
        for key in keys[:50]:  # Limit to 50 for display
            entry = sqlite_backend.get(key)
            if entry:
                # Extract tool name from ref_id if possible
                tool_name = key.split(":")[0] if ":" in key else "unknown"
                references.append(
                    {
                        "ref_id": key,
                        "tool": tool_name,
                        "namespace": entry.namespace,
                        "created_at": entry.created_at,
                        "expires_at": entry.expires_at,
                        "value_type": type(entry.value).__name__,
                        "value_preview": str(entry.value)[:100]
                        if entry.value
                        else None,
                    }
                )

        langfuse.flush()

        return {
            "total_keys": len(keys),
            "shown": len(references),
            "database_path": str(sqlite_backend.database_path),
            "references": references,
        }


@mcp.tool
@observe(name="create_policy_example")
async def create_policy_example(
    data: list[float],
    policy_type: str,
) -> dict[str, Any]:
    """Create test data with different access policies.

    Demonstrates how access policies are enforced across tool boundaries.

    Args:
        data: Data to cache.
        policy_type: 'public', 'user_only', 'agent_restricted', 'private'.

    Returns:
        Reference with access policy information.
    """

    attributes = get_langfuse_attributes()

    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata={**attributes["metadata"], "policy_type": policy_type},
        tags=attributes["tags"],
    ):
        # Create policy based on type
        if policy_type == "public":
            policy = AccessPolicy()  # Default: full access for users and agents
        elif policy_type == "user_only":
            policy = AccessPolicy(
                agent_permissions=Permission.NONE,  # Agents cannot access
            )
        elif policy_type == "agent_restricted":
            policy = AccessPolicy(
                agent_permissions=Permission.READ,  # Agents can read but not write
            )
        elif policy_type == "private":
            policy = AccessPolicy(
                user_permissions=Permission.READ,
                agent_permissions=Permission.EXECUTE,  # Agents can only use in computation
            )
        else:
            raise ValueError(f"Unknown policy type: {policy_type}")

        # Cache with the specified policy
        ref = cache.set(
            f"test_policy_{policy_type}",
            data,
            namespace="policy_tests",
            policy=policy,
        )

        langfuse.flush()

        return {
            "ref_id": ref.ref_id,
            "policy_type": policy_type,
            "user_permissions": str(policy.user_permissions),
            "agent_permissions": str(policy.agent_permissions),
            "data_size": len(data),
            "note": f"This reference has '{policy_type}' access policy. "
            "Try resolving it from another tool to test enforcement.",
        }


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run the Data Tools MCP server."""
    parser = argparse.ArgumentParser(
        description="Data Tools MCP Server with SQLite cross-tool caching"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for SSE transport (default: 8001)",
    )

    args = parser.parse_args()

    print("Starting Data Tools MCP Server...", file=sys.stderr)
    print(f"SQLite cache: {sqlite_backend.database_path}", file=sys.stderr)
    print(f"Transport: {args.transport}", file=sys.stderr)

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
