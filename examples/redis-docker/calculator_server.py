#!/usr/bin/env python3
"""Calculator MCP Server with Redis Backend - Docker Deployment.

This server provides mathematical calculation tools with results cached
in Redis/Valkey for cross-tool reference sharing in distributed scenarios.

Features:
- Redis backend for distributed, multi-user caching
- HTTP streaming transport for containerized deployment
- Cross-tool reference sharing with data-analysis server
- Proper use of @cache.cached() decorator pattern

Environment Variables:
    REDIS_HOST: Redis/Valkey host (default: valkey)
    REDIS_PORT: Redis/Valkey port (default: 6379)
    REDIS_PASSWORD: Redis password (optional)
    MCP_PORT: HTTP server port (default: 8001)

Usage:
    # Run directly
    python calculator_server.py

    # Or via Docker Compose
    docker compose up calculator

Cross-Tool Workflow:
    1. calculator: generate_primes(count=50) → ref_id
    2. data-analysis: analyze_data(data=ref_id) → statistics
"""

from __future__ import annotations

import math
import os
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

from mcp_refcache import RefCache
from mcp_refcache.backends import RedisBackend

# =============================================================================
# Configuration
# =============================================================================

REDIS_HOST = os.getenv("REDIS_HOST", "valkey")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

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
    name="redis-calculator",
    backend=redis_backend,
    default_ttl=3600,  # 1 hour
)

# =============================================================================
# Initialize FastMCP Server
# =============================================================================

mcp = FastMCP(
    name="Redis Calculator",
    instructions="""A calculator server with Redis-backed caching.

Tools cache their results in Redis, enabling cross-tool reference sharing.
Use ref_ids from this server with the data-analysis server.

Available tools:
- calculate: Evaluate mathematical expressions
- generate_primes: Generate prime numbers (cached)
- generate_fibonacci: Generate Fibonacci sequence (cached)
- generate_sequence: Generate various mathematical sequences (cached)
- get_cached_result: Retrieve cached results with pagination
- list_cached_keys: List all cached keys from this server
""",
)

# =============================================================================
# Helper Functions
# =============================================================================


def generate_primes_list(count: int) -> list[int]:
    """Generate a list of prime numbers using Sieve of Eratosthenes."""
    if count <= 0:
        return []

    # Estimate upper bound for nth prime
    if count < 6:
        upper_bound = 15
    else:
        upper_bound = int(count * (math.log(count) + math.log(math.log(count)) + 2))

    # Sieve of Eratosthenes
    sieve = [True] * (upper_bound + 1)
    sieve[0] = sieve[1] = False

    for i in range(2, int(upper_bound**0.5) + 1):
        if sieve[i]:
            for j in range(i * i, upper_bound + 1, i):
                sieve[j] = False

    primes = [i for i, is_prime in enumerate(sieve) if is_prime]
    return primes[:count]


def generate_fibonacci_list(count: int) -> list[int]:
    """Generate Fibonacci sequence."""
    if count <= 0:
        return []
    if count == 1:
        return [0]
    if count == 2:
        return [0, 1]

    sequence = [0, 1]
    for _ in range(count - 2):
        sequence.append(sequence[-1] + sequence[-2])
    return sequence


def generate_arithmetic_list(count: int, start: int, step: int) -> list[int]:
    """Generate arithmetic sequence."""
    return [start + i * step for i in range(count)]


def generate_geometric_list(count: int, start: int, ratio: int) -> list[int]:
    """Generate geometric sequence."""
    return [start * (ratio**i) for i in range(count)]


def generate_triangular_list(count: int) -> list[int]:
    """Generate triangular numbers."""
    return [n * (n + 1) // 2 for n in range(1, count + 1)]


def generate_factorial_list(count: int) -> list[int]:
    """Generate factorial sequence."""
    result = []
    factorial = 1
    for n in range(count):
        if n > 0:
            factorial *= n
        result.append(factorial)
    return result


def safe_eval(expression: str) -> float:
    """Safely evaluate a mathematical expression."""
    allowed_names = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "floor": math.floor,
        "ceil": math.ceil,
        "pi": math.pi,
        "e": math.e,
        "factorial": math.factorial,
    }

    # Validate expression contains only allowed characters
    allowed_chars = set("0123456789+-*/.() ,")
    for char in expression:
        if char not in allowed_chars and not char.isalpha():
            raise ValueError(f"Invalid character in expression: {char}")

    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return float(result)
    except Exception as e:
        raise ValueError(f"Failed to evaluate expression: {e}") from e


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool()
async def calculate(expression: str) -> dict[str, Any]:
    """Evaluate a mathematical expression.

    Supports: +, -, *, /, **, (), sqrt, sin, cos, tan, log, exp, pi, e, factorial

    Args:
        expression: Mathematical expression to evaluate

    Returns:
        Result of the calculation
    """
    try:
        result = safe_eval(expression)
        return {
            "expression": expression,
            "result": result,
        }
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
@cache.cached(namespace="sequences")
async def generate_primes(count: int = 20) -> list[int]:
    """Generate prime numbers and cache the result.

    Args:
        count: Number of primes to generate (1-10000)

    Returns:
        Cached response with ref_id for cross-tool reference
    """
    if count < 1 or count > 10000:
        raise ValueError("Count must be between 1 and 10000")
    return generate_primes_list(count)


@mcp.tool()
@cache.cached(namespace="sequences")
async def generate_fibonacci(count: int = 20) -> list[int]:
    """Generate Fibonacci sequence and cache the result.

    Args:
        count: Number of Fibonacci numbers to generate (1-1000)

    Returns:
        Cached response with ref_id for cross-tool reference
    """
    if count < 1 or count > 1000:
        raise ValueError("Count must be between 1 and 1000")
    return generate_fibonacci_list(count)


@mcp.tool()
@cache.cached(namespace="sequences")
async def generate_sequence(
    sequence_type: str,
    count: int = 20,
    start: int | None = None,
    step: int | None = None,
) -> list[int]:
    """Generate a mathematical sequence and cache the result.

    Sequence types:
        - fibonacci: Fibonacci sequence (0, 1, 1, 2, 3, 5, 8, ...)
        - prime: Prime numbers (2, 3, 5, 7, 11, ...)
        - arithmetic: Arithmetic sequence with given start and step
        - geometric: Geometric sequence with given start and ratio
        - triangular: Triangular numbers (1, 3, 6, 10, 15, ...)
        - factorial: Factorials (1, 1, 2, 6, 24, 120, ...)

    Args:
        sequence_type: Type of sequence to generate
        count: Number of terms (1-1000)
        start: Starting value (for arithmetic/geometric)
        step: Step or ratio (for arithmetic/geometric)

    Returns:
        Cached response with ref_id for cross-tool reference
    """
    if count < 1 or count > 1000:
        raise ValueError("Count must be between 1 and 1000")

    sequence_type = sequence_type.lower()

    if sequence_type == "fibonacci":
        return generate_fibonacci_list(count)
    elif sequence_type == "prime":
        return generate_primes_list(count)
    elif sequence_type == "arithmetic":
        actual_start = start if start is not None else 0
        actual_step = step if step is not None else 1
        return generate_arithmetic_list(count, actual_start, actual_step)
    elif sequence_type == "geometric":
        actual_start = start if start is not None else 1
        actual_ratio = step if step is not None else 2
        return generate_geometric_list(count, actual_start, actual_ratio)
    elif sequence_type == "triangular":
        return generate_triangular_list(count)
    elif sequence_type == "factorial":
        return generate_factorial_list(count)
    else:
        raise ValueError(
            f"Unknown sequence type: {sequence_type}. "
            "Valid types: fibonacci, prime, arithmetic, geometric, triangular, factorial"
        )


@mcp.tool()
async def get_cached_result(
    ref_id: str,
    page: int | None = None,
    page_size: int | None = None,
    max_size: int | None = None,
) -> dict[str, Any]:
    """Retrieve a cached result with optional pagination.

    Args:
        ref_id: Reference ID from a previous tool call
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
async def list_cached_keys() -> dict[str, Any]:
    """List all cached keys from this server.

    Returns:
        List of cache keys and their namespaces
    """
    keys = redis_backend.keys()
    return {
        "tool": "redis-calculator",
        "keys": keys,
        "count": len(keys),
        "redis_host": REDIS_HOST,
        "redis_port": REDIS_PORT,
    }


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run the Calculator MCP server."""
    print(f"Starting Calculator MCP Server on port {MCP_PORT}...", file=sys.stderr)
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}", file=sys.stderr)

    # Run with HTTP streaming transport for Docker deployment
    mcp.run(transport="sse", host="0.0.0.0", port=MCP_PORT)


if __name__ == "__main__":
    main()
