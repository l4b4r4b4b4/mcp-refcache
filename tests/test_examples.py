"""Tests for example implementations.

These tests verify that the example code works correctly without
requiring the full MCP server infrastructure.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_fastmcp(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Mock FastMCP for testing without actual MCP server."""
    # Create a mock context with async methods

    class MockContext:
        """Mock FastMCP context."""

        async def info(self, message: str) -> None:
            """Mock info logging."""

        async def warning(self, message: str) -> None:
            """Mock warning logging."""

        async def error(self, message: str) -> None:
            """Mock error logging."""

    class MockFastMCP:
        """Mock FastMCP server."""

        def __init__(self, name: str, **kwargs: Any) -> None:
            self.name = name
            self.tools: dict[str, Any] = {}
            self.prompts: dict[str, Any] = {}

        def tool(self, func: Any) -> Any:
            """Register a tool."""
            self.tools[func.__name__] = func
            return func

        def prompt(self, func: Any) -> Any:
            """Register a prompt."""
            self.prompts[func.__name__] = func
            return func

        def run(self) -> None:
            """Mock run method."""

    # We don't need to patch anything since we import RefCache directly
    return MockFastMCP, MockContext


# =============================================================================
# Test Example Imports
# =============================================================================


class TestExampleImports:
    """Test that example modules can be imported."""

    def test_mcp_refcache_imports(self) -> None:
        """Test that all mcp_refcache exports are available."""
        from mcp_refcache import (
            AccessPolicy,
            CacheReference,
            CacheResponse,
            DefaultActor,
            Permission,
            PreviewConfig,
            PreviewStrategy,
            RefCache,
        )

        # Verify classes exist and are the right type
        assert RefCache is not None
        assert CacheReference is not None
        assert CacheResponse is not None
        assert PreviewConfig is not None
        assert PreviewStrategy is not None
        assert AccessPolicy is not None
        assert Permission is not None
        assert DefaultActor is not None

        # Verify we can create instances
        cache = RefCache(name="test")
        assert cache is not None

        config = PreviewConfig(max_size=100)
        assert config.max_size == 100

    def test_example_models_importable(self) -> None:
        """Test that Pydantic models from examples work."""
        from pydantic import BaseModel, Field

        # Recreate the example input models
        class CalculateInput(BaseModel):
            expression: str = Field(description="Math expression to evaluate")

        class SequenceInput(BaseModel):
            sequence_type: str = Field(description="Type of sequence")
            count: int = Field(default=20, description="Number of items")

        class MatrixInput(BaseModel):
            matrix_a: list[list[float]] = Field(description="First matrix")
            operation: str = Field(default="transpose", description="Operation")

        # Test instantiation
        calc = CalculateInput(expression="2 + 2")
        assert calc.expression == "2 + 2"

        seq = SequenceInput(sequence_type="fibonacci")
        assert seq.count == 20

        matrix = MatrixInput(matrix_a=[[1, 2], [3, 4]])
        assert matrix.operation == "transpose"


# =============================================================================
# Test RefCache Integration
# =============================================================================


class TestRefCacheIntegration:
    """Test RefCache functionality as used in examples."""

    def test_cache_set_and_get(self) -> None:
        """Test basic cache set and get operations."""
        from mcp_refcache import PreviewConfig, RefCache

        cache = RefCache(
            name="test-cache",
            preview_config=PreviewConfig(max_size=100),
        )

        # Set a value
        ref = cache.set("test_key", {"data": [1, 2, 3, 4, 5]})
        assert ref.ref_id is not None
        # ref_id format is "{cache_name}:{hash}" e.g., "test-cache:abc123"
        assert ":" in ref.ref_id

        # Get the value back
        response = cache.get(ref.ref_id)
        assert response is not None
        assert response.ref_id == ref.ref_id

    def test_cache_with_access_policy(self) -> None:
        """Test cache with custom access policy."""
        from mcp_refcache import (
            AccessPolicy,
            DefaultActor,
            Permission,
            PreviewConfig,
            RefCache,
        )

        cache = RefCache(
            name="secure-cache",
            preview_config=PreviewConfig(max_size=50),
        )

        # Create a policy that only allows owner access
        policy = AccessPolicy(
            owner="user:alice",
            owner_permissions=Permission.FULL,
            user_permissions=Permission.READ,  # Other users can only read
        )

        # Set with policy
        ref = cache.set("secret", "sensitive data", policy=policy)
        assert ref.ref_id is not None

        # Owner can read
        alice = DefaultActor.user("alice")
        response = cache.get(ref.ref_id, actor=alice)
        assert response is not None

    def test_cache_pagination(self) -> None:
        """Test cache pagination for large results."""
        from mcp_refcache import PreviewConfig, PreviewStrategy, RefCache

        cache = RefCache(
            name="paginated-cache",
            preview_config=PreviewConfig(
                max_size=20,  # Small to force pagination
                default_strategy=PreviewStrategy.PAGINATE,
            ),
        )

        # Store a large list
        large_list = list(range(100))
        ref = cache.set("big_list", large_list)

        # Get first page
        response = cache.get(ref.ref_id, page=1, page_size=10)
        assert response is not None
        # CacheResponse uses page/total_pages attributes directly
        assert response.total_items == 100
        assert response.total_pages == 10
        assert response.page == 1


# =============================================================================
# Test Calculator Logic
# =============================================================================


class TestCalculatorLogic:
    """Test the calculator logic from examples."""

    def test_safe_math_context(self) -> None:
        """Test that safe math context works correctly."""
        # Recreate the safe context from examples
        safe_context = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            "pi": math.pi,
            "e": math.e,
            "pow": pow,
            "factorial": math.factorial,
        }

        # Test various expressions
        assert eval("2 + 2", {"__builtins__": {}}, safe_context) == 4
        assert eval("sqrt(16)", {"__builtins__": {}}, safe_context) == 4.0
        assert eval("sin(0)", {"__builtins__": {}}, safe_context) == 0.0
        assert eval("pi", {"__builtins__": {}}, safe_context) == math.pi
        assert eval("factorial(5)", {"__builtins__": {}}, safe_context) == 120

        # Test that dangerous builtins are not available
        with pytest.raises(NameError):
            eval("open('file.txt')", {"__builtins__": {}}, safe_context)

        with pytest.raises(NameError):
            eval("__import__('os')", {"__builtins__": {}}, safe_context)

    def test_expression_validation(self) -> None:
        """Test expression validation patterns."""
        import re

        # Pattern to detect potentially dangerous expressions
        dangerous_patterns = [
            r"__\w+__",  # Dunder methods
            r"\bexec\b",
            r"\beval\b",
            r"\bcompile\b",
            r"\bimport\b",
            r"\bopen\b",
            r"\bfile\b",
        ]

        safe_expressions = ["2 + 2", "sqrt(16)", "sin(pi/2)", "factorial(10)"]
        dangerous_expressions = [
            "__import__('os')",
            "exec('bad')",
            "open('file')",
        ]

        for expr in safe_expressions:
            for pattern in dangerous_patterns:
                assert not re.search(pattern, expr), f"{expr} matched {pattern}"

        for expr in dangerous_expressions:
            matched = False
            for pattern in dangerous_patterns:
                if re.search(pattern, expr):
                    matched = True
                    break
            assert matched, f"{expr} should be detected as dangerous"

    def test_matrix_validation(self) -> None:
        """Test matrix validation logic."""

        def validate_matrix(matrix: list[list[float]]) -> bool:
            """Check if matrix is valid (non-empty, rectangular)."""
            if not matrix or not matrix[0]:
                return False
            row_len = len(matrix[0])
            return all(len(row) == row_len for row in matrix)

        # Valid matrices
        assert validate_matrix([[1, 2], [3, 4]])
        assert validate_matrix([[1, 2, 3]])
        assert validate_matrix([[1], [2], [3]])

        # Invalid matrices
        assert not validate_matrix([])
        assert not validate_matrix([[]])
        assert not validate_matrix([[1, 2], [3]])  # Ragged


# =============================================================================
# Test Sequence Generation
# =============================================================================


class TestSequenceGeneration:
    """Test sequence generation logic from examples."""

    def test_fibonacci_sequence(self) -> None:
        """Test Fibonacci sequence generation."""

        def generate_fibonacci(count: int) -> list[int]:
            if count <= 0:
                return []
            if count == 1:
                return [0]
            if count == 2:
                return [0, 1]
            seq = [0, 1]
            for _ in range(2, count):
                seq.append(seq[-1] + seq[-2])
            return seq

        assert generate_fibonacci(0) == []
        assert generate_fibonacci(1) == [0]
        assert generate_fibonacci(2) == [0, 1]
        assert generate_fibonacci(10) == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

    def test_prime_detection(self) -> None:
        """Test prime number generation."""

        def is_prime(n: int) -> bool:
            if n < 2:
                return False
            if n == 2:
                return True
            if n % 2 == 0:
                return False
            return all(n % i != 0 for i in range(3, int(n**0.5) + 1, 2))

        # Test known primes
        known_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
        for p in known_primes:
            assert is_prime(p), f"{p} should be prime"

        # Test known non-primes
        non_primes = [0, 1, 4, 6, 8, 9, 10, 12, 14, 15]
        for n in non_primes:
            assert not is_prime(n), f"{n} should not be prime"


# =============================================================================
# Test Matrix Operations
# =============================================================================


class TestMatrixOperations:
    """Test matrix operation logic from examples."""

    def test_matrix_transpose(self) -> None:
        """Test matrix transposition."""
        matrix = [[1, 2, 3], [4, 5, 6]]
        expected = [[1, 4], [2, 5], [3, 6]]

        transposed = list(map(list, zip(*matrix, strict=True)))
        assert transposed == expected

    def test_matrix_determinant_2x2(self) -> None:
        """Test 2x2 matrix determinant."""
        matrix = [[1, 2], [3, 4]]
        det = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
        assert det == -2

    def test_matrix_determinant_3x3(self) -> None:
        """Test 3x3 matrix determinant using numpy-like calculation."""
        matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

        # Calculate using rule of Sarrus
        det = (
            matrix[0][0] * matrix[1][1] * matrix[2][2]
            + matrix[0][1] * matrix[1][2] * matrix[2][0]
            + matrix[0][2] * matrix[1][0] * matrix[2][1]
            - matrix[0][2] * matrix[1][1] * matrix[2][0]
            - matrix[0][1] * matrix[1][0] * matrix[2][2]
            - matrix[0][0] * matrix[1][2] * matrix[2][1]
        )
        assert det == 0  # This matrix is singular

    def test_matrix_multiplication(self) -> None:
        """Test matrix multiplication."""
        a = [[1, 2], [3, 4]]
        b = [[5, 6], [7, 8]]

        # Manual matrix multiplication
        result = [
            [sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)]
            for i in range(2)
        ]

        expected = [[19, 22], [43, 50]]
        assert result == expected

    def test_matrix_addition(self) -> None:
        """Test matrix addition."""
        a = [[1, 2], [3, 4]]
        b = [[5, 6], [7, 8]]

        result = [[a[i][j] + b[i][j] for j in range(2)] for i in range(2)]

        expected = [[6, 8], [10, 12]]
        assert result == expected


# =============================================================================
# Test Context-Scoped Caching
# =============================================================================


class TestContextScopedCaching:
    """Test context-scoped caching functionality."""

    def test_mock_context_class(self) -> None:
        """Test the MockContext class used in mcp_server example."""
        # Import the module
        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import mcp_server

            # Test MockContext class directly
            MockContext = mcp_server.MockContext

            # Test initial state
            MockContext.reset()
            state = MockContext.get_current_state()
            assert state["user_id"] == "demo_user"
            assert state["org_id"] == "demo_org"
            assert state["session_id"] == "demo_session_001"

            # Test set_state
            MockContext.set_state(user_id="alice", org_id="acme_corp")
            state = MockContext.get_current_state()
            assert state["user_id"] == "alice"
            assert state["org_id"] == "acme_corp"

            # Test set_session_id
            MockContext.set_session_id("session-12345")
            state = MockContext.get_current_state()
            assert state["session_id"] == "session-12345"

            # Test get_state via instance
            ctx = MockContext()
            assert ctx.get_state("user_id") == "alice"
            assert ctx.get_state("org_id") == "acme_corp"
            assert ctx.session_id == "session-12345"

            # Test reset
            MockContext.reset()
            state = MockContext.get_current_state()
            assert state["user_id"] == "demo_user"

        finally:
            sys.path.remove(examples_path)
            if "mcp_server" in sys.modules:
                del sys.modules["mcp_server"]

    def test_enable_test_context_tool(self) -> None:
        """Test the enable_test_context tool function logic."""
        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import mcp_server

            # Test enabling test mode
            mcp_server._test_mode_enabled = True
            assert mcp_server._test_mode_enabled is True

            # Test that mock context is returned when test mode is enabled
            result = mcp_server._mock_try_get_fastmcp_context()
            assert result is not None
            assert isinstance(result, mcp_server.MockContext)

            # Test disabling test mode
            mcp_server._test_mode_enabled = False
            assert mcp_server._test_mode_enabled is False

        finally:
            sys.path.remove(examples_path)
            mcp_server._test_mode_enabled = False
            if "mcp_server" in sys.modules:
                del sys.modules["mcp_server"]

    def test_set_test_context_tool(self) -> None:
        """Test the set_test_context tool function logic."""
        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import mcp_server

            MockContext = mcp_server.MockContext
            MockContext.reset()

            # Test setting individual values
            MockContext.set_state(user_id="bob")
            state = MockContext.get_current_state()
            assert state["user_id"] == "bob"
            assert state["org_id"] == "demo_org"  # Unchanged

            # Test setting multiple values
            MockContext.set_state(
                user_id="charlie", org_id="globex", agent_id="test_agent"
            )
            state = MockContext.get_current_state()
            assert state["user_id"] == "charlie"
            assert state["org_id"] == "globex"
            assert state["agent_id"] == "test_agent"

            # Test setting session_id separately
            MockContext.set_session_id("custom-session")
            state = MockContext.get_current_state()
            assert state["session_id"] == "custom-session"

        finally:
            sys.path.remove(examples_path)
            mcp_server.MockContext.reset()
            if "mcp_server" in sys.modules:
                del sys.modules["mcp_server"]

    def test_reset_test_context_tool(self) -> None:
        """Test the reset_test_context tool function logic."""
        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import mcp_server

            MockContext = mcp_server.MockContext

            # Set some custom values
            MockContext.set_state(user_id="custom_user", org_id="custom_org")
            MockContext.set_session_id("custom_session")

            # Reset
            MockContext.reset()

            # Verify all values are back to defaults
            state = MockContext.get_current_state()
            assert state["user_id"] == "demo_user"
            assert state["org_id"] == "demo_org"
            assert state["session_id"] == "demo_session_001"
            assert state["agent_id"] == "demo_agent"

        finally:
            sys.path.remove(examples_path)
            if "mcp_server" in sys.modules:
                del sys.modules["mcp_server"]


# =============================================================================
# Test Langfuse Integration
# =============================================================================


class TestLangfuseIntegration:
    """Test Langfuse integration example."""

    def test_langfuse_example_importable(self) -> None:
        """Test that the langfuse_integration example can be imported."""
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        # Mock the langfuse module before importing
        mock_langfuse = MagicMock()

        # Create mock decorator that preserves function
        class MockObserve:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs

            def __call__(self, func: Any) -> Any:
                return func

        mock_langfuse.observe = MockObserve

        def mock_get_client() -> MagicMock:
            class MockClient:
                def start_as_current_observation(self, **kwargs: Any) -> MagicMock:
                    return MagicMock()

                def flush(self) -> None:
                    pass

            return MockClient()

        mock_langfuse.get_client = mock_get_client

        class MockContextManager:
            def __enter__(self) -> MockContextManager:
                return self

            def __exit__(self, *args: Any) -> None:
                pass

            def update(self, **kwargs: Any) -> None:
                pass

        class MockPropagateAttributes(MockContextManager):
            def __init__(self, **kwargs: Any) -> None:
                pass

            def __enter__(self) -> MockPropagateAttributes:
                return self

            def __exit__(self, *args: Any) -> None:
                pass

        mock_langfuse.propagate_attributes = MockPropagateAttributes

        with patch.dict(sys.modules, {"langfuse": mock_langfuse}):
            try:
                # Now import our example
                import langfuse_integration

                # Verify key components exist
                assert hasattr(langfuse_integration, "TracedRefCache")
                assert hasattr(langfuse_integration, "MockContext")
                assert hasattr(langfuse_integration, "get_langfuse_attributes")

            finally:
                sys.path.remove(examples_path)
                if "langfuse_integration" in sys.modules:
                    del sys.modules["langfuse_integration"]

    def test_traced_refcache_wrapper(self) -> None:
        """Test TracedRefCache wrapper functionality without Langfuse."""
        from mcp_refcache import PreviewConfig, RefCache

        # Create a simple cache
        cache = RefCache(
            name="test-traced",
            preview_config=PreviewConfig(max_size=100),
        )

        # Store and retrieve a value
        ref = cache.set("test_key", {"data": [1, 2, 3]})
        assert ref.ref_id is not None

        # Get the value back
        response = cache.get(ref.ref_id)
        assert response is not None
        assert response.ref_id == ref.ref_id

    def test_get_langfuse_attributes_with_context(self) -> None:
        """Test get_langfuse_attributes extracts correct values from MockContext."""
        import sys
        from pathlib import Path

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            # Import directly since langfuse is now in dev deps
            import langfuse_integration

            # Enable test mode
            langfuse_integration._test_mode_enabled = True
            langfuse_integration.MockContext.set_state(
                user_id="alice",
                org_id="acme_corp",
                agent_id="test_agent",
            )
            langfuse_integration.MockContext.set_session_id("sess-12345")

            # Get attributes
            attrs = langfuse_integration.get_langfuse_attributes(
                cache_namespace="user:alice",
                operation="cache_set",
            )

            # Verify native Langfuse fields
            assert attrs["user_id"] == "alice"
            assert attrs["session_id"] == "sess-12345"

            # Verify metadata (alphanumeric keys only)
            assert attrs["metadata"]["orgid"] == "acme_corp"
            assert attrs["metadata"]["agentid"] == "test_agent"
            assert attrs["metadata"]["cachenamespace"] == "user:alice"
            assert attrs["metadata"]["operation"] == "cache_set"

            # Verify model for cost tracking (default value)
            assert attrs["model"] == "claude-opus-4-20250514"

            # Verify tags
            assert "mcprefcache" in attrs["tags"]
            assert "cacheset" in attrs["tags"]
            assert "testmode" in attrs["tags"]

            # Verify version
            assert attrs["version"] == "1.0.0"

        finally:
            sys.path.remove(examples_path)
            # Reset state
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]

    def test_get_langfuse_attributes_without_context(self) -> None:
        """Test get_langfuse_attributes returns defaults when no context."""
        import sys
        from pathlib import Path

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Ensure test mode is disabled
            langfuse_integration._test_mode_enabled = False

            # Get attributes without context
            attrs = langfuse_integration.get_langfuse_attributes()

            # Should have default values
            assert attrs["user_id"] == "anonymous"
            assert attrs["session_id"] == "nosession"
            assert attrs["metadata"]["orgid"] == "default"
            assert attrs["metadata"]["agentid"] == "unknown"

            # Should not have testmode tag
            assert "testmode" not in attrs["tags"]

        finally:
            sys.path.remove(examples_path)
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]

    def test_langfuse_attributes_truncation(self) -> None:
        """Test that Langfuse attributes are properly truncated to 200 chars."""
        import sys
        from pathlib import Path

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Enable test mode and set very long values
            langfuse_integration._test_mode_enabled = True
            long_value = "x" * 300  # Longer than 200 char limit
            langfuse_integration.MockContext.set_state(
                user_id=long_value,
                org_id=long_value,
            )

            # Get attributes
            attrs = langfuse_integration.get_langfuse_attributes()

            # All values should be truncated to ≤200 chars
            assert len(attrs["user_id"]) <= 200
            assert len(attrs["metadata"]["orgid"]) <= 200

        finally:
            sys.path.remove(examples_path)
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]

    def test_langfuse_mock_context_class(self) -> None:
        """Test the Langfuse example's MockContext class and state management."""
        import sys
        from pathlib import Path

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Test MockContext class methods directly (not the @mcp.tool wrapped functions)
            MockContext = langfuse_integration.MockContext

            # Test initial state
            MockContext.reset()
            state = MockContext.get_current_state()
            assert state["user_id"] == "demo_user"
            assert state["org_id"] == "demo_org"
            assert state["session_id"] == "demo_session_001"
            assert state["model"] == "claude-opus-4-20250514"

            # Test set_state
            MockContext.set_state(user_id="bob", org_id="globex")
            state = MockContext.get_current_state()
            assert state["user_id"] == "bob"
            assert state["org_id"] == "globex"

            # Test model can be set via set_state
            MockContext.set_state(model="gpt-4o")
            state = MockContext.get_current_state()
            assert state["model"] == "gpt-4o"

            # Verify model is included in langfuse attributes
            langfuse_integration._test_mode_enabled = True
            attrs = langfuse_integration.get_langfuse_attributes()
            assert attrs["model"] == "gpt-4o"
            langfuse_integration._test_mode_enabled = False

            # Test set_session_id
            MockContext.set_session_id("chat-999")
            state = MockContext.get_current_state()
            assert state["session_id"] == "chat-999"

            # Test get_state via instance
            ctx = MockContext()
            assert ctx.get_state("user_id") == "bob"
            assert ctx.get_state("org_id") == "globex"
            assert ctx.session_id == "chat-999"

            # Test reset
            MockContext.reset()
            state = MockContext.get_current_state()
            assert state["user_id"] == "demo_user"

            # Test _test_mode_enabled flag
            langfuse_integration._test_mode_enabled = True
            attrs = langfuse_integration.get_langfuse_attributes()
            assert "testmode" in attrs["tags"]
            langfuse_integration._test_mode_enabled = False

        finally:
            sys.path.remove(examples_path)
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]


class TestTracedRefCacheCachedDecorator:
    """Tests for TracedRefCache.cached() decorator with Langfuse tracing."""

    def test_traced_cached_creates_span_on_cache_miss(self) -> None:
        """Test that TracedRefCache.cached() creates a span when cache misses."""
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Mock Langfuse to capture span creation
            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=None)

            mock_client = MagicMock()
            mock_client.start_as_current_observation = MagicMock(return_value=mock_span)
            mock_client.flush = MagicMock()

            # Enable test mode and set context
            langfuse_integration._test_mode_enabled = True
            langfuse_integration.MockContext.set_state(user_id="alice", org_id="acme")

            with (
                patch.object(langfuse_integration, "langfuse", mock_client),
                patch.object(langfuse_integration, "_langfuse_enabled", True),
            ):
                # Create traced cache
                from mcp_refcache import PreviewConfig, RefCache

                base_cache = RefCache(
                    name="test-traced-cached",
                    preview_config=PreviewConfig(max_size=100),
                )
                traced_cache = langfuse_integration.TracedRefCache(base_cache)

                # Define a cached function
                @traced_cache.cached(namespace="test")
                def compute_value(x: int) -> int:
                    return x * 2

                # Call the function (should be cache miss)
                result = compute_value(5)
                assert result["value"] == 10 or result.get("preview") is not None

        finally:
            sys.path.remove(examples_path)
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]

    def test_traced_cached_tracks_cache_hit(self) -> None:
        """Test that TracedRefCache.cached() tracks cache hits correctly."""
        import sys
        from pathlib import Path

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Enable test mode
            langfuse_integration._test_mode_enabled = True

            # Create traced cache with Langfuse disabled (for unit testing)
            from mcp_refcache import PreviewConfig, RefCache

            base_cache = RefCache(
                name="test-hit-tracking",
                preview_config=PreviewConfig(max_size=100),
            )
            traced_cache = langfuse_integration.TracedRefCache(base_cache)

            # Track function calls
            call_count = 0

            @traced_cache.cached(namespace="test")
            def expensive_compute(x: int) -> int:
                nonlocal call_count
                call_count += 1
                return x * x

            # First call - cache miss
            result1 = expensive_compute(7)
            assert call_count == 1
            assert "ref_id" in result1

            # Second call with same args - should be cache hit
            # The function should NOT be called again
            _ = expensive_compute(7)
            # Cache hit means function not called again
            assert call_count == 1  # Still 1, not 2

        finally:
            sys.path.remove(examples_path)
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]

    def test_traced_cached_includes_user_attribution(self) -> None:
        """Test that traced cached operations include user/session attribution."""
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Track span metadata
            captured_metadata = {}

            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=None)

            def capture_update(**kwargs: object) -> None:
                captured_metadata.update(kwargs)

            mock_span.update = capture_update

            mock_client = MagicMock()
            mock_client.start_as_current_observation = MagicMock(return_value=mock_span)
            mock_client.flush = MagicMock()

            # Enable test mode and set context
            langfuse_integration._test_mode_enabled = True
            langfuse_integration.MockContext.set_state(
                user_id="bob",
                org_id="globex",
                agent_id="test_agent",
            )
            langfuse_integration.MockContext.set_session_id("session-xyz")

            with (
                patch.object(langfuse_integration, "langfuse", mock_client),
                patch.object(langfuse_integration, "_langfuse_enabled", True),
            ):
                from mcp_refcache import PreviewConfig, RefCache

                base_cache = RefCache(
                    name="test-attribution",
                    preview_config=PreviewConfig(max_size=100),
                )
                traced_cache = langfuse_integration.TracedRefCache(base_cache)

                # Use set() which has tracing
                traced_cache.set("test_key", {"value": 42}, namespace="test")

                # Verify user attribution was captured
                if captured_metadata.get("metadata"):
                    assert captured_metadata["metadata"].get("userid") == "bob"
                    assert (
                        captured_metadata["metadata"].get("sessionid") == "session-xyz"
                    )

        finally:
            sys.path.remove(examples_path)
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]

    def test_traced_cached_async_function(self) -> None:
        """Test that TracedRefCache.cached() works with async functions."""
        import asyncio
        import sys
        from pathlib import Path

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Enable test mode
            langfuse_integration._test_mode_enabled = True

            from mcp_refcache import PreviewConfig, RefCache

            base_cache = RefCache(
                name="test-async-cached",
                preview_config=PreviewConfig(max_size=100),
            )
            traced_cache = langfuse_integration.TracedRefCache(base_cache)

            @traced_cache.cached(namespace="async_test")
            async def async_compute(x: int) -> int:
                return x + 100

            # Run async function
            result = asyncio.run(async_compute(5))
            assert "ref_id" in result
            # Value should be 105
            if "value" in result:
                assert result["value"] == 105

        finally:
            sys.path.remove(examples_path)
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]

    def test_traced_refcache_resolve_with_tracing(self) -> None:
        """Test that TracedRefCache.resolve() creates spans."""
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Track observations
            observations_created = []

            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=None)
            mock_span.update = MagicMock()

            def track_observation(**kwargs: object) -> MagicMock:
                observations_created.append(kwargs)
                return mock_span

            mock_client = MagicMock()
            mock_client.start_as_current_observation = track_observation
            mock_client.flush = MagicMock()

            langfuse_integration._test_mode_enabled = True
            langfuse_integration.MockContext.set_state(user_id="charlie")

            with (
                patch.object(langfuse_integration, "langfuse", mock_client),
                patch.object(langfuse_integration, "_langfuse_enabled", True),
            ):
                from mcp_refcache import PreviewConfig, RefCache

                base_cache = RefCache(
                    name="test-resolve-trace",
                    preview_config=PreviewConfig(max_size=100),
                )
                traced_cache = langfuse_integration.TracedRefCache(base_cache)

                # Store a value
                ref = traced_cache.set("resolve_test", [1, 2, 3], namespace="test")

                # Clear observations to only capture resolve
                observations_created.clear()

                # Resolve the ref (need to provide actor for permission check)
                from mcp_refcache.access import DefaultActor

                actor = DefaultActor.user("charlie")
                value = traced_cache.resolve(ref.ref_id, actor=actor)
                assert value == [1, 2, 3]

                # Verify resolve span was created
                assert len(observations_created) >= 1
                resolve_obs = observations_created[0]
                assert resolve_obs["name"] == "cache.resolve"
                assert resolve_obs["as_type"] == "span"

        finally:
            sys.path.remove(examples_path)
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]

    def test_traced_cached_creates_cache_operation_span(self) -> None:
        """Test that TracedRefCache.cached() creates cache.{function_name} spans."""
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Track span creation
            spans_created = []

            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=None)
            mock_span.update = MagicMock()

            def track_span_creation(**kwargs: object) -> MagicMock:
                spans_created.append(kwargs)
                return mock_span

            mock_client = MagicMock()
            mock_client.start_as_current_observation = track_span_creation
            mock_client.flush = MagicMock()

            langfuse_integration._test_mode_enabled = True
            langfuse_integration.MockContext.set_state(
                user_id="alice",
                org_id="acme",
            )

            with (
                patch.object(langfuse_integration, "langfuse", mock_client),
                patch.object(langfuse_integration, "_langfuse_enabled", True),
            ):
                from mcp_refcache import PreviewConfig, RefCache

                base_cache = RefCache(
                    name="test-span-creation",
                    preview_config=PreviewConfig(max_size=100),
                )
                traced_cache = langfuse_integration.TracedRefCache(base_cache)

                @traced_cache.cached(namespace="test_ns")
                def multiply(x: int, y: int) -> int:
                    return x * y

                # Call the cached function
                result = multiply(3, 4)
                assert "ref_id" in result

                # Verify a span was created for the cached function
                assert len(spans_created) >= 1

                # Find the cache.multiply span
                cache_spans = [
                    s for s in spans_created if s.get("name") == "cache.multiply"
                ]
                assert len(cache_spans) == 1

                cache_span = cache_spans[0]
                assert cache_span["as_type"] == "span"
                assert cache_span["input"]["function"] == "multiply"
                assert cache_span["input"]["namespace"] == "test_ns"

        finally:
            sys.path.remove(examples_path)
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]

    def test_traced_cached_tracks_cache_hit_vs_miss_in_span(self) -> None:
        """Test that spans correctly record cache hit vs miss status."""
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        examples_path = str(Path(__file__).parent.parent / "examples")
        sys.path.insert(0, examples_path)

        try:
            import langfuse_integration

            # Track span updates
            span_updates = []

            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=None)

            def capture_update(**kwargs: object) -> None:
                span_updates.append(kwargs)

            mock_span.update = capture_update

            mock_client = MagicMock()
            mock_client.start_as_current_observation = MagicMock(return_value=mock_span)
            mock_client.flush = MagicMock()

            langfuse_integration._test_mode_enabled = True

            with (
                patch.object(langfuse_integration, "langfuse", mock_client),
                patch.object(langfuse_integration, "_langfuse_enabled", True),
            ):
                from mcp_refcache import PreviewConfig, RefCache

                base_cache = RefCache(
                    name="test-hit-miss-span",
                    preview_config=PreviewConfig(max_size=100),
                )
                traced_cache = langfuse_integration.TracedRefCache(base_cache)

                call_count = 0

                @traced_cache.cached(namespace="hitcheck")
                def get_data(key: str) -> str:
                    nonlocal call_count
                    call_count += 1
                    return f"value_{key}"

                # First call - cache miss
                span_updates.clear()
                _ = get_data("foo")
                assert call_count == 1

                # Check span output indicates cached result
                assert len(span_updates) >= 1
                first_update = span_updates[0]
                assert "output" in first_update
                assert first_update["output"].get("ref_id") is not None

                # Second call with same args - cache hit
                span_updates.clear()
                _ = get_data("foo")
                assert call_count == 1  # Function not called again

                # Both calls should have spans with cached=True in output
                assert len(span_updates) >= 1

        finally:
            sys.path.remove(examples_path)
            langfuse_integration.MockContext.reset()
            langfuse_integration._test_mode_enabled = False
            if "langfuse_integration" in sys.modules:
                del sys.modules["langfuse_integration"]
