#!/usr/bin/env python3
"""Scientific Calculator MCP Server with RefCache Integration.

This example demonstrates how to use mcp-refcache with FastMCP to build
an MCP server that handles large computational results efficiently.

Features demonstrated:
- Reference-based caching for large results (matrices, sequences)
- Preview generation (sample, truncate, paginate strategies)
- Pagination for accessing large datasets
- Access control (user vs agent permissions)
- Private computation (EXECUTE without READ)
- Both sync and async tool implementations
- Multiple transport modes (stdio, SSE)

Usage:
    # Install dependencies
    uv add "mcp-refcache[mcp]"

    # Run with stdio (for Claude Desktop)
    python examples/mcp_server.py

    # Run with SSE (for web clients/debugging)
    python examples/mcp_server.py --transport sse --port 8000

Claude Desktop Configuration:
    Add to your claude_desktop_config.json:
    {
        "mcpServers": {
            "calculator": {
                "command": "python",
                "args": ["/path/to/mcp-refcache/examples/mcp_server.py"]
            }
        }
    }
"""

from __future__ import annotations

import argparse
import cmath
import math
import re
import sys
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Check for FastMCP availability
# =============================================================================

try:
    from fastmcp import Context, FastMCP
except ImportError:
    print(
        "Error: FastMCP is not installed. Install with:\n"
        "  uv add 'mcp-refcache[mcp]'\n"
        "  # or\n"
        "  pip install fastmcp>=2.0.0",
        file=sys.stderr,
    )
    sys.exit(1)

# =============================================================================
# Import mcp-refcache components
# =============================================================================

# Import context integration for testing context-scoped caching
import mcp_refcache.context_integration as ctx_integration
from mcp_refcache import (
    AccessPolicy,
    CacheResponse,
    DefaultActor,
    Permission,
    PreviewConfig,
    PreviewStrategy,
    RefCache,
)
from mcp_refcache.fastmcp import (
    cache_guide_prompt,
    cache_instructions,
    register_admin_tools,
    with_cache_docs,
)

# =============================================================================
# Initialize FastMCP Server
# =============================================================================

mcp = FastMCP(
    name="Scientific Calculator",
    instructions=f"""A scientific calculator with reference-based caching.

Available tools:
- calculate: Evaluate mathematical expressions
- generate_sequence: Generate mathematical sequences (Fibonacci, primes, etc.)
- matrix_operation: Perform matrix operations (multiply, transpose, etc.)
- store_secret: Store a secret value for private computation
- compute_with_secret: Use a secret in computation without revealing it
- get_cached_result: Retrieve or paginate through cached results

Admin tools (restricted):
- admin_list_references: Browse all cached references
- admin_get_cache_stats: Detailed cache statistics

{cache_instructions()}
""",
)

# =============================================================================
# Initialize RefCache
# =============================================================================

# Create a RefCache instance with sensible defaults for the calculator
# Uses token-based sizing (default) for accurate LLM context management
cache = RefCache(
    name="calculator",
    default_ttl=3600,  # 1 hour TTL
    preview_config=PreviewConfig(
        max_size=64,  # Max 64 tokens in previews
        default_strategy=PreviewStrategy.SAMPLE,  # Sample large collections
    ),
)

# =============================================================================
# Pydantic Models for Tool Inputs
# =============================================================================


class MathExpression(BaseModel):
    """Input model for mathematical expressions."""

    expression: str = Field(
        description="Mathematical expression to evaluate (e.g., 'sin(pi/2) + sqrt(16)')",
        min_length=1,
        max_length=1000,
        json_schema_extra={
            "examples": ["2 * (3 + 4)", "sin(0.5) + cos(pi/4)", "sqrt(16) + log(100)"]
        },
    )

    @field_validator("expression")
    @classmethod
    def validate_safe_expression(cls, value: str) -> str:
        """Validate expression doesn't contain unsafe patterns."""
        unsafe_pattern = r"(^|[^a-zA-Z])(__.*__|import|exec|eval|open|os|sys|subprocess|getattr|setattr|globals|locals)($|[^a-zA-Z])"
        if re.search(unsafe_pattern, value):
            raise ValueError("Potentially unsafe expression detected")
        return value


class SequenceType(str, Enum):
    """Types of mathematical sequences."""

    FIBONACCI = "fibonacci"
    PRIME = "prime"
    ARITHMETIC = "arithmetic"
    GEOMETRIC = "geometric"
    TRIANGULAR = "triangular"
    FACTORIAL = "factorial"


class SequenceInput(BaseModel):
    """Input model for sequence generation."""

    sequence_type: SequenceType = Field(
        description="Type of sequence to generate",
    )
    count: int = Field(
        default=20,
        ge=1,
        le=10000,
        description="Number of elements to generate",
    )
    start: int | None = Field(
        default=None,
        description="Starting value (for arithmetic/geometric sequences)",
    )
    step: int | None = Field(
        default=None,
        description="Step value for arithmetic sequence or ratio for geometric",
    )


class MatrixInput(BaseModel):
    """Input model for matrix data."""

    data: list[list[float]] = Field(
        description="Matrix data as nested lists (e.g., [[1, 2], [3, 4]])",
    )

    @field_validator("data")
    @classmethod
    def validate_matrix(cls, value: list[list[float]]) -> list[list[float]]:
        """Validate matrix is rectangular."""
        if not value:
            raise ValueError("Matrix cannot be empty")
        row_length = len(value[0])
        if not all(len(row) == row_length for row in value):
            raise ValueError("All rows must have the same length")
        return value


class MatrixOperation(str, Enum):
    """Available matrix operations."""

    TRANSPOSE = "transpose"
    DETERMINANT = "determinant"
    INVERSE = "inverse"
    MULTIPLY = "multiply"
    ADD = "add"
    SCALAR_MULTIPLY = "scalar_multiply"
    TRACE = "trace"
    EIGENVALUES = "eigenvalues"


class MatrixOperationInput(BaseModel):
    """Input model for matrix operations."""

    matrix_a: MatrixInput | str = Field(
        description="First matrix or reference ID to a cached matrix",
    )
    matrix_b: MatrixInput | str | None = Field(
        default=None,
        description="Second matrix or reference ID (for multiply/add operations)",
    )
    scalar: float | None = Field(
        default=None,
        description="Scalar value for scalar_multiply operation",
    )
    operation: MatrixOperation = Field(
        default=MatrixOperation.TRANSPOSE,
        description="Operation to perform",
    )


class SecretInput(BaseModel):
    """Input model for storing secret values."""

    name: str = Field(
        description="Name for the secret (used as key)",
        min_length=1,
        max_length=100,
    )
    value: float = Field(
        description="The secret numeric value",
    )


class SecretComputeInput(BaseModel):
    """Input model for computing with secrets."""

    secret_ref: str = Field(
        description="Reference ID of the secret value",
    )
    expression: str = Field(
        description="Expression using 'x' as the secret value (e.g., 'x * 2 + 1')",
    )


class CacheQueryInput(BaseModel):
    """Input model for cache queries."""

    ref_id: str = Field(
        description="Reference ID to look up",
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="Page number for pagination (1-indexed)",
    )
    page_size: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Number of items per page",
    )
    max_size: int | None = Field(
        default=None,
        ge=1,
        description="Maximum preview size (tokens/chars). Overrides tool and server defaults.",
    )


# =============================================================================
# Safe Math Evaluation Context
# =============================================================================

SAFE_MATH_CONTEXT: dict[str, Any] = {
    # Basic math
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    # Trigonometric
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    # Exponential/Logarithmic
    "sqrt": lambda x: cmath.sqrt(x) if x < 0 else math.sqrt(x),
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "pow": pow,
    # Rounding
    "ceil": math.ceil,
    "floor": math.floor,
    "trunc": math.trunc,
    # Other
    "factorial": math.factorial,
    "gcd": math.gcd,
    "degrees": math.degrees,
    "radians": math.radians,
    # Constants
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
    # Complex numbers
    "j": complex(0, 1),
    "i": complex(0, 1),
    "phase": cmath.phase,
    "polar": cmath.polar,
}


# =============================================================================
# Tool Implementations
# =============================================================================


@mcp.tool
def calculate(expression: str) -> dict[str, Any]:
    """Evaluate a mathematical expression safely.

    Supports standard math functions (sin, cos, sqrt, log, etc.) and constants (pi, e).
    Use ** for exponentiation (e.g., '2**3' for 2³).

    Examples:
        - "2 * (3 + 4)" → 14
        - "sin(pi/2)" → 1.0
        - "sqrt(16) + log(100)" → 8.605...
        - "factorial(10)" → 3628800
    """
    # Validate input
    validated = MathExpression(expression=expression)

    # Replace ^ with ** for exponentiation (common notation)
    expr = validated.expression.replace("^", "**")

    try:
        # Evaluate in safe context
        result = eval(expr, {"__builtins__": {}}, SAFE_MATH_CONTEXT)

        # Handle complex numbers
        if isinstance(result, complex) and abs(result.imag) < 1e-14:
            result = float(result.real)

        # For simple scalar results, return directly
        if isinstance(result, (int, float, complex)):
            return {
                "result": result,
                "expression": validated.expression,
                "type": type(result).__name__,
            }

        # For larger results, cache them
        ref = cache.set(
            key=f"calc_{hash(validated.expression)}",
            value=result,
            namespace="public",
        )

        response = cache.get(ref.ref_id)
        return {
            "result": response.preview,
            "ref_id": ref.ref_id,
            "expression": validated.expression,
            "cached": True,
        }

    except Exception as e:
        raise ValueError(f"Error evaluating expression: {e}") from e


@mcp.tool
@cache.cached(namespace="sequences")
async def generate_sequence(
    sequence_type: str,
    count: int = 20,
    start: int | None = None,
    step: int | None = None,
) -> list[int | float]:
    """Generate a mathematical sequence.

    Sequence types:
        - fibonacci: Fibonacci sequence (0, 1, 1, 2, 3, 5, 8, ...)
        - prime: Prime numbers (2, 3, 5, 7, 11, ...)
        - arithmetic: Arithmetic sequence with given start and step
        - geometric: Geometric sequence with given start and ratio
        - triangular: Triangular numbers (1, 3, 6, 10, 15, ...)
        - factorial: Factorials (1, 1, 2, 6, 24, 120, ...)

    For large sequences, returns a reference with a preview.
    Use get_cached_result to paginate through the full sequence.


    **Caching:** Large results are returned as references with previews.

    **Pagination:** Use `page` and `page_size` to navigate results.
    """
    # Validate input
    validated = SequenceInput(
        sequence_type=SequenceType(sequence_type),
        count=count,
        start=start,
        step=step,
    )

    # Generate the sequence
    sequence: list[int | float] = []

    if validated.sequence_type == SequenceType.FIBONACCI:
        a, b = 0, 1
        for _ in range(validated.count):
            sequence.append(a)
            a, b = b, a + b

    elif validated.sequence_type == SequenceType.PRIME:

        def is_prime(n: int) -> bool:
            if n < 2:
                return False
            if n == 2:
                return True
            if n % 2 == 0:
                return False
            return all(n % i != 0 for i in range(3, int(n**0.5) + 1, 2))

        num = 2
        while len(sequence) < validated.count:
            if is_prime(num):
                sequence.append(num)
            num += 1

    elif validated.sequence_type == SequenceType.ARITHMETIC:
        start_val = validated.start if validated.start is not None else 0
        step_val = validated.step if validated.step is not None else 1
        sequence = [start_val + i * step_val for i in range(validated.count)]

    elif validated.sequence_type == SequenceType.GEOMETRIC:
        start_val = validated.start if validated.start is not None else 1
        ratio = validated.step if validated.step is not None else 2
        sequence = [start_val * (ratio**i) for i in range(validated.count)]

    elif validated.sequence_type == SequenceType.TRIANGULAR:
        sequence = [(n * (n + 1)) // 2 for n in range(1, validated.count + 1)]

    elif validated.sequence_type == SequenceType.FACTORIAL:
        for n in range(validated.count):
            sequence.append(math.factorial(n))

    # Return raw sequence - decorator handles caching and structured response
    return sequence


@mcp.tool
@cache.cached(namespace="matrices")
async def matrix_operation(
    matrix_a: list[list[float]] | str,
    operation: str = "transpose",
    matrix_b: list[list[float]] | str | None = None,
    scalar: float | None = None,
) -> list[list[float]] | float:
    """Perform matrix operations.

    Operations:
        - transpose: Transpose the matrix
        - determinant: Calculate determinant (square matrices only)
        - inverse: Calculate inverse (square matrices only)
        - multiply: Matrix multiplication (requires matrix_b)
        - add: Matrix addition (requires matrix_b)
        - scalar_multiply: Multiply by scalar (requires scalar)
        - trace: Sum of diagonal elements (square matrices only)


    **Caching:** Large results are returned as references with previews.

    **References:** This tool accepts `ref_id` from previous tool calls.

    **Private Compute:** Values are processed server-side without exposure.
    """
    # Validate inputs (ref_ids are resolved by decorator before we get here)
    validated_a = MatrixInput(data=matrix_a)  # type: ignore[arg-type]
    validated_op = MatrixOperation(operation)

    # Convert to numpy-like operations (pure Python for simplicity)
    a = validated_a.data
    result: Any = None

    if validated_op == MatrixOperation.TRANSPOSE:
        result = [[a[j][i] for j in range(len(a))] for i in range(len(a[0]))]

    elif validated_op == MatrixOperation.DETERMINANT:
        if len(a) != len(a[0]):
            raise ValueError("Determinant requires a square matrix")
        # Simple 2x2 and 3x3 determinant
        if len(a) == 2:
            result = a[0][0] * a[1][1] - a[0][1] * a[1][0]
        elif len(a) == 3:
            result = (
                a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
                - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
                + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
            )
        else:
            raise ValueError("Determinant only implemented for 2x2 and 3x3 matrices")

    elif validated_op == MatrixOperation.TRACE:
        if len(a) != len(a[0]):
            raise ValueError("Trace requires a square matrix")
        result = sum(a[i][i] for i in range(len(a)))

    elif validated_op == MatrixOperation.SCALAR_MULTIPLY:
        if scalar is None:
            raise ValueError("scalar_multiply requires a scalar value")
        result = [[cell * scalar for cell in row] for row in a]

    elif validated_op == MatrixOperation.ADD:
        if matrix_b is None:
            raise ValueError("add requires matrix_b")
        validated_b = MatrixInput(data=matrix_b)  # type: ignore[arg-type]
        b = validated_b.data
        if len(a) != len(b) or len(a[0]) != len(b[0]):
            raise ValueError("Matrices must have the same dimensions for addition")
        result = [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]

    elif validated_op == MatrixOperation.MULTIPLY:
        if matrix_b is None:
            raise ValueError("multiply requires matrix_b")
        validated_b = MatrixInput(data=matrix_b)  # type: ignore[arg-type]
        b = validated_b.data
        if len(a[0]) != len(b):
            raise ValueError(
                f"Cannot multiply: matrix_a columns ({len(a[0])}) != matrix_b rows ({len(b)})"
            )
        result = [
            [sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))]
            for i in range(len(a))
        ]

    elif validated_op == MatrixOperation.INVERSE:
        if len(a) != len(a[0]):
            raise ValueError("Inverse requires a square matrix")
        if len(a) != 2:
            raise ValueError("Inverse only implemented for 2x2 matrices in this demo")
        det = a[0][0] * a[1][1] - a[0][1] * a[1][0]
        if abs(det) < 1e-10:
            raise ValueError("Matrix is singular (determinant is zero)")
        result = [
            [a[1][1] / det, -a[0][1] / det],
            [-a[1][0] / det, a[0][0] / det],
        ]

    # Return raw result - decorator handles caching and structured response
    return result


@mcp.tool
def store_secret(name: str, value: float) -> dict[str, Any]:
    """Store a secret value that agents cannot read, only use in computations.

    This demonstrates the EXECUTE permission - agents can use the value
    in compute_with_secret without ever seeing what it is.

    Example use case: Store an API rate limit, encryption key, or
    sensitive constant that should influence computations but not be exposed.
    """
    validated = SecretInput(name=name, value=value)

    # Create a policy where agents can EXECUTE but not READ
    secret_policy = AccessPolicy(
        user_permissions=Permission.FULL,  # Users can see everything
        agent_permissions=Permission.EXECUTE,  # Agents can only use in computation
    )

    ref = cache.set(
        key=f"secret_{validated.name}",
        value=validated.value,
        namespace="user:secrets",  # User-owned namespace
        policy=secret_policy,
        tool_name="store_secret",
    )

    return {
        "ref_id": ref.ref_id,
        "name": validated.name,
        "message": f"Secret '{validated.name}' stored. Agents can use it in compute_with_secret but cannot read the value.",
        "permissions": {
            "user": "FULL (can read, write, execute)",
            "agent": "EXECUTE only (can use in computation, cannot read)",
        },
    }


@mcp.tool
@with_cache_docs(accepts_references=True, private_computation=True)
def compute_with_secret(secret_ref: str, expression: str) -> dict[str, Any]:
    """Compute using a secret value without revealing it.

    The secret is available as 'x' in the expression.
    This demonstrates private computation - the agent orchestrates
    the computation but never sees the actual secret value.

    Examples:
        - "x * 2" - Double the secret
        - "x ** 2 + 1" - Square the secret and add 1
        - "sin(x)" - Sine of the secret


    **Caching:** Large results are returned as references with previews.

    **References:** This tool accepts `ref_id` from previous tool calls.

    **Private Compute:** Values are processed server-side without exposure.
    """
    validated = SecretComputeInput(secret_ref=secret_ref, expression=expression)

    # Create a system actor to resolve the secret (bypasses agent restrictions)
    system_actor = DefaultActor.system()

    try:
        # Resolve the secret value as system (has full access)
        secret_value = cache.resolve(validated.secret_ref, actor=system_actor)
    except KeyError as e:
        raise ValueError(f"Secret reference '{validated.secret_ref}' not found") from e

    # Create safe context with the secret as 'x'
    compute_context = {**SAFE_MATH_CONTEXT, "x": secret_value}

    # Validate and evaluate
    expr = validated.expression.replace("^", "**")

    try:
        result = eval(expr, {"__builtins__": {}}, compute_context)

        # Handle complex results
        if isinstance(result, complex) and abs(result.imag) < 1e-14:
            result = float(result.real)

        return {
            "result": result,
            "expression": validated.expression,
            "secret_ref": validated.secret_ref,
            "message": "Computed using secret value (value not revealed)",
        }

    except Exception as e:
        raise ValueError(f"Error in computation: {e}") from e


@mcp.tool
@with_cache_docs(accepts_references=True, supports_pagination=True)
async def get_cached_result(
    ref_id: str,
    page: int | None = None,
    page_size: int | None = None,
    max_size: int | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Retrieve a cached result, optionally with pagination.

    Use this to:
    - Get a preview of a cached value
    - Paginate through large sequences or matrices
    - Access the full value of a cached result

    Pagination:
        - page: Page number (1-indexed)
        - page_size: Items per page (default varies by data type)

    Preview Size:
        - max_size: Maximum preview size (tokens/chars). Overrides tool and server defaults.
          Use smaller values for quick summaries, larger for more context.


    **Caching:** Large results are returned as references with previews.

    **Pagination:** Use `page` and `page_size` to navigate results.

    **References:** This tool accepts `ref_id` from previous tool calls.
    """
    validated = CacheQueryInput(
        ref_id=ref_id, page=page, page_size=page_size, max_size=max_size
    )

    if ctx:
        await ctx.info(f"Retrieving cached result: {validated.ref_id}")

    try:
        # Get with pagination and/or custom max_size if specified
        response: CacheResponse = cache.get(
            validated.ref_id,
            page=validated.page,
            page_size=validated.page_size,
            max_size=validated.max_size,
            actor="agent",  # Agent access - respects permissions
        )

        result: dict[str, Any] = {
            "ref_id": validated.ref_id,
            "preview": response.preview,
            "preview_strategy": response.preview_strategy.value,
            "total_items": response.total_items,
        }

        # Add pagination info if applicable
        if response.page is not None:
            result["page"] = response.page
            result["total_pages"] = response.total_pages

        # Add size info
        if response.original_size:
            result["original_size"] = response.original_size
            result["preview_size"] = response.preview_size

        return result

    except (PermissionError, KeyError):
        # Opaque error: don't reveal whether ref exists or is permission-denied
        # This prevents enumeration attacks and information leakage
        return {
            "error": "Invalid or inaccessible reference",
            "message": "Reference not found, expired, or access denied",
            "ref_id": validated.ref_id,
        }


# =============================================================================
# Admin Tools (Permission-Gated)
# =============================================================================


# =============================================================================
# Context-Scoped Caching Demo (Test Mode)
# =============================================================================
# This section demonstrates context-scoped caching with testable mock context.
# In production, context comes from FastMCP middleware (e.g., IdentityMiddleware).
# For testing/demo purposes, we provide tools to simulate different user contexts.


class MockContext:
    """Mock FastMCP Context for testing context-scoped caching.

    This class simulates a FastMCP Context object with the minimum API
    needed for context-scoped caching:
    - session_id attribute
    - get_state(key) method for retrieving identity values
    """

    # Class-level state storage (shared across all instances)
    _state: ClassVar[dict[str, str]] = {
        "user_id": "demo_user",
        "org_id": "demo_org",
        "agent_id": "demo_agent",
    }
    _session_id: ClassVar[str] = "demo_session_001"

    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        return MockContext._session_id

    @property
    def client_id(self) -> str:
        """Get the client ID (for compatibility)."""
        return "demo_client"

    @property
    def request_id(self) -> str:
        """Get the request ID (for compatibility)."""
        return "demo_request"

    def get_state(self, key: str) -> str | None:
        """Get a state value by key."""
        return MockContext._state.get(key)

    @classmethod
    def set_state(cls, **kwargs: str) -> None:
        """Update state values."""
        cls._state.update(kwargs)

    @classmethod
    def set_session_id(cls, session_id: str) -> None:
        """Update the session ID."""
        cls._session_id = session_id

    @classmethod
    def get_current_state(cls) -> dict[str, Any]:
        """Get a copy of current state for inspection."""
        return {
            **cls._state,
            "session_id": cls._session_id,
        }

    @classmethod
    def reset(cls) -> None:
        """Reset to default test values."""
        cls._state = {
            "user_id": "demo_user",
            "org_id": "demo_org",
            "agent_id": "demo_agent",
        }
        cls._session_id = "demo_session_001"


# Store original function for restoration
_original_try_get_context = ctx_integration.try_get_fastmcp_context
_test_mode_enabled = False


def _mock_try_get_fastmcp_context() -> MockContext | None:
    """Mock version that returns our test context."""
    if _test_mode_enabled:
        return MockContext()
    return _original_try_get_context()


# Patch the context integration module
ctx_integration.try_get_fastmcp_context = _mock_try_get_fastmcp_context


@mcp.tool
def enable_test_context(enabled: bool = True) -> dict[str, Any]:
    """Enable or disable test context mode for context-scoped caching demos.

    When enabled, context-scoped caching tools will use the MockContext
    instead of trying to get a real FastMCP Context. This allows testing
    the context-scoped features without running a full FastMCP server
    with authentication middleware.

    Args:
        enabled: Whether to enable test context mode (default: True).

    Returns:
        Status dict with current test mode state and context values.

    Example:
        Enable test mode:
        >>> enable_test_context(True)
        {"test_mode": True, "context": {"user_id": "demo_user", ...}}

        Disable test mode:
        >>> enable_test_context(False)
        {"test_mode": False, "context": null}
    """
    global _test_mode_enabled
    _test_mode_enabled = enabled

    if enabled:
        return {
            "test_mode": True,
            "context": MockContext.get_current_state(),
            "message": "Test context mode enabled. Use set_test_context to change identity.",
        }
    return {
        "test_mode": False,
        "context": None,
        "message": "Test context mode disabled. Context-scoped caching will use real FastMCP context.",
    }


@mcp.tool
def set_test_context(
    user_id: str | None = None,
    org_id: str | None = None,
    session_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Set test context values for context-scoped caching demos.

    This tool allows you to simulate different user/org/session contexts
    to test cache isolation. Each unique combination of context values
    results in a different cache namespace.

    Args:
        user_id: User identity (e.g., "alice", "bob").
        org_id: Organization identity (e.g., "acme", "globex").
        session_id: Session identifier (for session-scoped caching).
        agent_id: Agent identity (for agent-specific contexts).

    Returns:
        Dict with updated context values and test mode status.

    Example:
        Simulate user "alice" from org "acme":
        >>> set_test_context(user_id="alice", org_id="acme")

        Switch to user "bob":
        >>> set_test_context(user_id="bob")

        Now cache lookups will use bob's namespace instead of alice's!
    """
    global _test_mode_enabled

    # Auto-enable test mode when setting context
    if not _test_mode_enabled:
        _test_mode_enabled = True

    # Update only provided values
    updates: dict[str, str] = {}
    if user_id is not None:
        updates["user_id"] = user_id
    if org_id is not None:
        updates["org_id"] = org_id
    if agent_id is not None:
        updates["agent_id"] = agent_id

    if updates:
        MockContext.set_state(**updates)

    if session_id is not None:
        MockContext.set_session_id(session_id)

    return {
        "test_mode": True,
        "context": MockContext.get_current_state(),
        "message": f"Context updated. Cache namespace will reflect: {MockContext.get_current_state()}",
    }


@mcp.tool
def reset_test_context() -> dict[str, Any]:
    """Reset test context to default demo values.

    Useful for cleaning up between test scenarios.

    Returns:
        Dict with reset context values.
    """
    MockContext.reset()
    return {
        "test_mode": _test_mode_enabled,
        "context": MockContext.get_current_state(),
        "message": "Context reset to default demo values.",
    }


# Context-scoped tool example
@mcp.tool
@cache.cached(
    namespace_template="org:{org_id}:user:{user_id}",
    owner_template="user:{user_id}",
    session_scoped=True,
    ttl=300,  # 5 minutes
)
async def get_user_profile(include_preferences: bool = False) -> dict[str, Any]:
    """Get the current user's profile (context-scoped caching demo).

    This tool demonstrates context-scoped caching. The result is cached
    in a namespace derived from the user's identity context:
    - Namespace: org:{org_id}:user:{user_id}
    - Owner: user:{user_id}
    - Session-scoped: Only accessible within the current session

    Different users get different cached results, and one user cannot
    access another user's cached profile data.

    Args:
        include_preferences: Whether to include user preferences.

    Returns:
        User profile dict with name, email, org, and optionally preferences.

    Example:
        First, enable test context and set identity:
        >>> enable_test_context(True)
        >>> set_test_context(user_id="alice", org_id="acme")
        >>> get_user_profile()
        # Returns alice's profile, cached in org:acme:user:alice namespace

        Switch to different user:
        >>> set_test_context(user_id="bob")
        >>> get_user_profile()
        # Returns bob's profile - CACHE MISS (different namespace)
    """
    # In a real app, this would fetch from a database
    # For demo, we construct profile from context
    ctx = MockContext() if _test_mode_enabled else None
    user_id = ctx.get_state("user_id") if ctx else "unknown"
    org_id = ctx.get_state("org_id") if ctx else "unknown"

    profile = {
        "user_id": user_id,
        "display_name": f"User {user_id.title()}",
        "email": f"{user_id}@{org_id}.example.com",
        "organization": org_id,
        "role": "member",
    }

    if include_preferences:
        profile["preferences"] = {
            "theme": "dark",
            "language": "en",
            "notifications": True,
        }

    return profile


@mcp.tool
@cache.cached(
    namespace_template="user:{user_id}:data",
    owner_template="user:{user_id}",
    ttl=600,  # 10 minutes
)
async def store_user_data(key: str, value: str) -> dict[str, Any]:
    """Store user-scoped data (context-scoped caching demo).

    Each user has their own isolated data namespace. Data stored by
    one user is not accessible to other users.

    Args:
        key: The data key to store.
        value: The value to store.

    Returns:
        Confirmation with stored key-value pair.

    Example:
        >>> set_test_context(user_id="alice")
        >>> store_user_data("favorite_color", "blue")
        # Stored in user:alice:data namespace

        >>> set_test_context(user_id="bob")
        >>> store_user_data("favorite_color", "green")
        # Stored in user:bob:data namespace (different from alice's)
    """
    ctx = MockContext() if _test_mode_enabled else None
    user_id = ctx.get_state("user_id") if ctx else "unknown"

    return {
        "user_id": user_id,
        "key": key,
        "value": value,
        "stored_at": "now",
        "namespace": f"user:{user_id}:data",
    }


# =============================================================================
# Admin Check
# =============================================================================


async def is_admin(ctx: Context | None) -> bool:
    """Check if the current context has admin privileges.

    In a real application, this would check:
    - User authentication/authorization
    - Role-based access control
    - Session tokens, etc.

    For this demo, we always return False (no admin access).
    Override this in your own server with proper auth logic.
    """
    # Demo: No admin access by default
    # In production, implement proper auth:
    # user_id = getattr(ctx, 'user_id', None)
    # return user_id in ADMIN_USER_IDS
    return False


# Register admin tools with the cache
# These are protected by the is_admin check
_admin_tools = register_admin_tools(
    mcp,
    cache,
    admin_check=is_admin,
    prefix="admin_",
    include_dangerous=False,  # Don't expose full values
)


# =============================================================================
# Prompts for Guidance
# =============================================================================


@mcp.prompt
def calculator_guide() -> str:
    """Guide for using the Scientific Calculator MCP server."""
    return f"""# Scientific Calculator Guide

## Context-Scoped Caching (NEW)

Test user isolation with context-scoped caching:

```
# Enable test mode
enable_test_context(True)

# Set user context
set_test_context(user_id="alice", org_id="acme")

# Get alice's profile (cached in alice's namespace)
get_user_profile()

# Switch to bob
set_test_context(user_id="bob")

# Get bob's profile (CACHE MISS - different namespace!)
get_user_profile()
```

Each user's data is isolated in their own namespace.

## Quick Start

1. **Basic Calculations**
   Use `calculate` for math expressions:
   - `calculate("2 + 2")` → 4
   - `calculate("sin(pi/2)")` → 1.0
   - `calculate("sqrt(16) + log(100)")` → 8.605...

2. **Generate Sequences**
   Use `generate_sequence` for mathematical sequences:
   - `generate_sequence("fibonacci", count=50)` → First 50 Fibonacci numbers
   - `generate_sequence("prime", count=100)` → First 100 prime numbers

3. **Matrix Operations**
   Use `matrix_operation` for linear algebra:
   - `matrix_operation([[1,2],[3,4]], "determinant")` → -2
   - `matrix_operation([[1,2],[3,4]], "transpose")` → [[1,3],[2,4]]

## Working with Large Results

Large results are cached and returned as references with previews.
Use `get_cached_result` to paginate:

```
# Generate a large sequence
result = generate_sequence("fibonacci", count=1000)
# result.ref_id = "abc123..."

# Get page 2 of results
get_cached_result("abc123...", page=2, page_size=50)
```

## Private Computation (Secrets)

Store values that agents can use but not see:

```
# Store a secret
store_secret("my_key", 42.0)
# Returns ref_id for the secret

# Use in computation (agent never sees 42.0)
compute_with_secret("ref_id...", "x * 2 + 1")
# Returns 85.0
```

## Available Math Functions

- **Basic**: abs, round, min, max, sum, pow
- **Trigonometric**: sin, cos, tan, asin, acos, atan, sinh, cosh, tanh
- **Exponential**: sqrt, exp, log, log10, log2
- **Rounding**: ceil, floor, trunc
- **Other**: factorial, gcd, degrees, radians
- **Constants**: pi, e, tau, inf, i/j (imaginary)

---

{cache_guide_prompt()}
"""


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run the MCP server."""
    parser = argparse.ArgumentParser(
        description="Scientific Calculator MCP Server with RefCache",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode (default: stdio for Claude Desktop)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)",
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        # Standard stdio transport for Claude Desktop
        mcp.run(transport="stdio")
    else:
        # SSE transport for web clients / debugging
        mcp.run(
            transport="sse",
            host=args.host,
            port=args.port,
        )


if __name__ == "__main__":
    main()
