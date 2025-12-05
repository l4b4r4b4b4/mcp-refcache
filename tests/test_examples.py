"""Tests for example MCP servers.

These tests verify that the example servers can be imported and
instantiated correctly, and that tools are properly registered.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_fastmcp() -> Generator[None, None, None]:
    """Mock FastMCP for testing without the actual dependency."""

    # Create mock classes
    class MockContext:
        """Mock Context for testing."""

        async def info(self, message: str) -> None:
            """Mock info logging."""
            pass

        async def warning(self, message: str) -> None:
            """Mock warning logging."""
            pass

        async def error(self, message: str) -> None:
            """Mock error logging."""
            pass

    class MockFastMCP:
        """Mock FastMCP server for testing."""

        def __init__(self, name: str = "test", **kwargs: object) -> None:
            self.name = name
            self.tools: list[object] = []
            self.prompts: list[object] = []
            self._kwargs = kwargs

        def tool(self, func: object = None) -> object:
            """Mock tool decorator."""
            if func is None:
                return self.tool

            self.tools.append(func)
            return func

        def prompt(self, func: object = None) -> object:
            """Mock prompt decorator."""
            if func is None:
                return self.prompt

            self.prompts.append(func)
            return func

        def run(self, **kwargs: object) -> None:
            """Mock run method."""
            pass

    # Patch fastmcp module
    mock_module = type(sys)("fastmcp")
    mock_module.FastMCP = MockFastMCP
    mock_module.Context = MockContext

    with patch.dict(sys.modules, {"fastmcp": mock_module}):
        yield


# =============================================================================
# Import Tests
# =============================================================================


class TestExampleImports:
    """Test that example modules can be imported."""

    def test_mcp_refcache_imports(self) -> None:
        """Test that mcp_refcache core imports work."""
        from mcp_refcache import (
            AccessPolicy,
            CacheResponse,
            DefaultActor,
            Permission,
            PreviewConfig,
            PreviewStrategy,
            RefCache,
            SizeMode,
        )

        # Verify classes exist
        assert RefCache is not None
        assert AccessPolicy is not None
        assert Permission is not None
        assert DefaultActor is not None
        assert PreviewConfig is not None
        assert PreviewStrategy is not None
        assert SizeMode is not None
        assert CacheResponse is not None

    def test_example_models_importable(self, mock_fastmcp: None) -> None:
        """Test that example Pydantic models can be imported."""
        # Import the example module with mocked FastMCP
        # We need to reload to pick up the mock

        # Import and reload to use mock
        if "examples.mcp_server" in sys.modules:
            del sys.modules["examples.mcp_server"]

        # Add examples to path temporarily
        import os

        examples_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "examples"
        )

        sys.path.insert(0, examples_path)
        try:
            # This will use our mocked FastMCP
            import mcp_server

            # Check models exist
            assert hasattr(mcp_server, "MathExpression")
            assert hasattr(mcp_server, "SequenceType")
            assert hasattr(mcp_server, "SequenceInput")
            assert hasattr(mcp_server, "MatrixInput")
            assert hasattr(mcp_server, "MatrixOperation")
        finally:
            sys.path.remove(examples_path)
            if "mcp_server" in sys.modules:
                del sys.modules["mcp_server"]


# =============================================================================
# RefCache Integration Tests
# =============================================================================


class TestRefCacheIntegration:
    """Test RefCache functionality used by examples."""

    def test_cache_set_and_get(self) -> None:
        """Test basic cache set/get operations."""
        from mcp_refcache import PreviewConfig, PreviewStrategy, RefCache, SizeMode

        cache = RefCache(
            name="test-cache",
            preview_config=PreviewConfig(
                size_mode=SizeMode.CHARACTER,
                max_size=100,
                default_strategy=PreviewStrategy.SAMPLE,
            ),
        )

        # Store a value
        ref = cache.set("test_key", list(range(100)))

        # Retrieve preview
        response = cache.get(ref.ref_id)

        assert response.ref_id == ref.ref_id
        assert response.preview is not None
        assert response.total_items == 100

    def test_cache_with_access_policy(self) -> None:
        """Test cache with custom access policy."""
        from mcp_refcache import (
            AccessPolicy,
            DefaultActor,
            Permission,
            PermissionDenied,
            RefCache,
        )

        cache = RefCache(name="test-policy")

        # Create execute-only policy for agents
        policy = AccessPolicy(
            user_permissions=Permission.FULL,
            agent_permissions=Permission.EXECUTE,  # No READ
        )

        ref = cache.set("secret", 42, policy=policy)

        # User can read
        user_actor = DefaultActor.user()
        value = cache.resolve(ref.ref_id, actor=user_actor)
        assert value == 42

        # Agent cannot read (only EXECUTE)
        agent_actor = DefaultActor.agent()
        with pytest.raises(PermissionDenied):
            cache.resolve(ref.ref_id, actor=agent_actor)

    def test_cache_pagination(self) -> None:
        """Test paginated access to cached values."""
        from mcp_refcache import (
            PaginateGenerator,
            PreviewConfig,
            PreviewStrategy,
            RefCache,
            SizeMode,
        )

        # Use paginate strategy explicitly for pagination
        cache = RefCache(
            name="test-pagination",
            preview_config=PreviewConfig(
                size_mode=SizeMode.CHARACTER,
                max_size=50,  # Small limit to force pagination
                default_strategy=PreviewStrategy.PAGINATE,
            ),
            preview_generator=PaginateGenerator(),
        )

        # Store a list
        data = list(range(100))
        ref = cache.set("paginated_data", data)

        # Get first page
        response = cache.get(ref.ref_id, page=1, page_size=10)
        assert response.page == 1
        assert response.total_pages is not None
        assert response.total_pages > 1

        # Get second page
        response = cache.get(ref.ref_id, page=2, page_size=10)
        assert response.page == 2


# =============================================================================
# Tool Logic Tests (without FastMCP)
# =============================================================================


class TestCalculatorLogic:
    """Test calculator logic without FastMCP dependency."""

    def test_safe_math_context(self, mock_fastmcp: None) -> None:
        """Test that safe math context is properly defined."""
        import os

        examples_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "examples"
        )
        sys.path.insert(0, examples_path)

        try:
            import mcp_server

            ctx = mcp_server.SAFE_MATH_CONTEXT

            # Test basic functions exist
            assert "sin" in ctx
            assert "cos" in ctx
            assert "sqrt" in ctx
            assert "log" in ctx

            # Test constants
            assert "pi" in ctx
            assert "e" in ctx

            # Test complex number support
            assert "j" in ctx
            assert "i" in ctx

            # Test evaluation works

            assert ctx["sin"](ctx["pi"] / 2) == pytest.approx(1.0)
            assert ctx["sqrt"](16) == 4.0

        finally:
            sys.path.remove(examples_path)
            if "mcp_server" in sys.modules:
                del sys.modules["mcp_server"]

    def test_expression_validation(self, mock_fastmcp: None) -> None:
        """Test that expression validation catches unsafe patterns."""
        import os

        examples_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "examples"
        )
        sys.path.insert(0, examples_path)

        try:
            import mcp_server

            # Safe expressions should pass
            safe = mcp_server.MathExpression(expression="2 + 2")
            assert safe.expression == "2 + 2"

            safe = mcp_server.MathExpression(expression="sin(pi/2)")
            assert "sin" in safe.expression

            # Unsafe expressions should fail
            with pytest.raises(ValueError, match="unsafe"):
                mcp_server.MathExpression(expression="__import__('os')")

            with pytest.raises(ValueError, match="unsafe"):
                mcp_server.MathExpression(expression="exec('print(1)')")

        finally:
            sys.path.remove(examples_path)
            if "mcp_server" in sys.modules:
                del sys.modules["mcp_server"]

    def test_matrix_validation(self, mock_fastmcp: None) -> None:
        """Test matrix input validation."""
        import os

        examples_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "examples"
        )
        sys.path.insert(0, examples_path)

        try:
            import mcp_server

            # Valid matrix
            valid = mcp_server.MatrixInput(data=[[1, 2], [3, 4]])
            assert valid.data == [[1, 2], [3, 4]]

            # Empty matrix should fail
            with pytest.raises(ValueError, match="empty"):
                mcp_server.MatrixInput(data=[])

            # Ragged matrix should fail
            with pytest.raises(ValueError, match="same length"):
                mcp_server.MatrixInput(data=[[1, 2], [3, 4, 5]])

        finally:
            sys.path.remove(examples_path)
            if "mcp_server" in sys.modules:
                del sys.modules["mcp_server"]


# =============================================================================
# Sequence Generation Tests
# =============================================================================


class TestSequenceGeneration:
    """Test sequence generation logic."""

    def test_fibonacci_sequence(self) -> None:
        """Test Fibonacci sequence generation."""
        # Generate manually to compare
        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

        a, b = 0, 1
        result = []
        for _ in range(10):
            result.append(a)
            a, b = b, a + b

        assert result == expected

    def test_prime_detection(self) -> None:
        """Test prime number detection."""

        def is_prime(n: int) -> bool:
            if n < 2:
                return False
            if n == 2:
                return True
            if n % 2 == 0:
                return False
            return all(n % i != 0 for i in range(3, int(n**0.5) + 1, 2))

        # Test known primes
        assert is_prime(2)
        assert is_prime(3)
        assert is_prime(5)
        assert is_prime(7)
        assert is_prime(11)
        assert is_prime(97)

        # Test non-primes
        assert not is_prime(0)
        assert not is_prime(1)
        assert not is_prime(4)
        assert not is_prime(9)
        assert not is_prime(100)


# =============================================================================
# Matrix Operation Tests
# =============================================================================


class TestMatrixOperations:
    """Test matrix operations logic."""

    def test_matrix_transpose(self) -> None:
        """Test matrix transposition."""
        matrix = [[1, 2, 3], [4, 5, 6]]
        transposed = [
            [matrix[j][i] for j in range(len(matrix))] for i in range(len(matrix[0]))
        ]

        expected = [[1, 4], [2, 5], [3, 6]]
        assert transposed == expected

    def test_matrix_determinant_2x2(self) -> None:
        """Test 2x2 determinant."""
        a = [[1, 2], [3, 4]]
        det = a[0][0] * a[1][1] - a[0][1] * a[1][0]

        assert det == -2

    def test_matrix_determinant_3x3(self) -> None:
        """Test 3x3 determinant."""
        a = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        det = (
            a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
        )

        assert det == 0  # This matrix is singular

    def test_matrix_multiplication(self) -> None:
        """Test matrix multiplication."""
        a = [[1, 2], [3, 4]]
        b = [[5, 6], [7, 8]]

        result = [
            [sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))]
            for i in range(len(a))
        ]

        expected = [[19, 22], [43, 50]]
        assert result == expected

    def test_matrix_addition(self) -> None:
        """Test matrix addition."""
        a = [[1, 2], [3, 4]]
        b = [[5, 6], [7, 8]]

        result = [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]

        expected = [[6, 8], [10, 12]]
        assert result == expected
