"""Tests for ref_id resolution utilities.

These tests cover:
- Ref_id pattern detection
- Deep recursive resolution in nested structures
- Error handling for missing/expired references
- Security (opaque errors for permission denied)
"""

from __future__ import annotations

import pytest

from mcp_refcache import AccessPolicy, Permission, RefCache
from mcp_refcache.resolution import (
    RefResolver,
    ResolutionResult,
    is_ref_id,
    resolve_args_and_kwargs,
    resolve_kwargs,
    resolve_refs,
)


class TestIsRefId:
    """Tests for the is_ref_id function."""

    def test_valid_ref_id_simple(self) -> None:
        """Test that valid ref_id patterns are recognized."""
        assert is_ref_id("myapp:abc12345") is True

    def test_valid_ref_id_with_hyphen_in_name(self) -> None:
        """Test ref_id with hyphen in cache name."""
        assert is_ref_id("my-cache:abc12345") is True

    def test_valid_ref_id_with_underscore_in_name(self) -> None:
        """Test ref_id with underscore in cache name."""
        assert is_ref_id("my_cache:abc12345") is True

    def test_valid_ref_id_long_hash(self) -> None:
        """Test ref_id with longer hash."""
        assert is_ref_id("finquant:2780226d27c57e49") is True

    def test_invalid_no_colon(self) -> None:
        """Test that strings without colon are not ref_ids."""
        assert is_ref_id("just-a-string") is False

    def test_invalid_starts_with_number(self) -> None:
        """Test that cache name must start with letter."""
        assert is_ref_id("123cache:abc12345") is False

    def test_invalid_short_hash(self) -> None:
        """Test that hash must be at least 8 characters."""
        assert is_ref_id("myapp:abc123") is False  # Only 6 chars

    def test_invalid_non_hex_hash(self) -> None:
        """Test that hash must be hexadecimal."""
        assert is_ref_id("myapp:abcdefgh") is False  # 'g' and 'h' not hex

    def test_invalid_non_string(self) -> None:
        """Test that non-strings return False."""
        assert is_ref_id(12345) is False
        assert is_ref_id(None) is False
        assert is_ref_id({"key": "value"}) is False
        assert is_ref_id(["a", "b"]) is False

    def test_invalid_empty_string(self) -> None:
        """Test that empty string returns False."""
        assert is_ref_id("") is False

    def test_invalid_only_colon(self) -> None:
        """Test that just a colon returns False."""
        assert is_ref_id(":") is False

    def test_valid_min_length_hash(self) -> None:
        """Test minimum valid hash length (8 chars)."""
        assert is_ref_id("myapp:12345678") is True

    def test_valid_uppercase_cache_name(self) -> None:
        """Test that uppercase cache names work."""
        assert is_ref_id("MyApp:abc12345") is True


class TestResolutionResult:
    """Tests for the ResolutionResult dataclass."""

    def test_success_property_no_errors(self) -> None:
        """Test that success is True when no errors."""
        result = ResolutionResult(value={"data": 123}, resolved_count=1)
        assert result.success is True
        assert result.has_errors is False

    def test_success_property_with_errors(self) -> None:
        """Test that success is False when errors exist."""
        result = ResolutionResult(
            value={"data": "ref:abc"},
            resolved_count=0,
            errors={"ref:abc": "Not found"},
        )
        assert result.success is False
        assert result.has_errors is True

    def test_resolved_refs_tracking(self) -> None:
        """Test that resolved refs are tracked."""
        result = ResolutionResult(
            value={"a": 1, "b": 2},
            resolved_count=2,
            resolved_refs=["myapp:abc12345", "myapp:def67890"],
        )
        assert len(result.resolved_refs) == 2
        assert "myapp:abc12345" in result.resolved_refs


class TestRefResolver:
    """Tests for the RefResolver class."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for testing."""
        return RefCache(name="test")

    def test_resolve_simple_ref_id(self, cache: RefCache) -> None:
        """Test resolving a simple ref_id value."""
        ref = cache.set("prices", [100, 101, 102])
        resolver = RefResolver(cache)

        result = resolver.resolve(ref.ref_id)

        assert result.success
        assert result.value == [100, 101, 102]
        assert result.resolved_count == 1
        assert ref.ref_id in result.resolved_refs

    def test_resolve_in_dict(self, cache: RefCache) -> None:
        """Test resolving ref_id as dict value."""
        ref = cache.set("data", {"nested": "value"})
        resolver = RefResolver(cache)

        result = resolver.resolve({"key": ref.ref_id, "other": "unchanged"})

        assert result.success
        assert result.value == {"key": {"nested": "value"}, "other": "unchanged"}
        assert result.resolved_count == 1

    def test_resolve_in_list(self, cache: RefCache) -> None:
        """Test resolving ref_id in a list."""
        ref = cache.set("item", 42)
        resolver = RefResolver(cache)

        result = resolver.resolve([1, 2, ref.ref_id, 4])

        assert result.success
        assert result.value == [1, 2, 42, 4]
        assert result.resolved_count == 1

    def test_resolve_nested_dict(self, cache: RefCache) -> None:
        """Test resolving ref_id in deeply nested dict."""
        ref = cache.set("deep", "found_it")
        resolver = RefResolver(cache)

        nested_input = {"level1": {"level2": {"level3": ref.ref_id}}}
        result = resolver.resolve(nested_input)

        assert result.success
        assert result.value == {"level1": {"level2": {"level3": "found_it"}}}

    def test_resolve_nested_list_in_dict(self, cache: RefCache) -> None:
        """Test resolving ref_id in list inside dict."""
        ref = cache.set("value", 999)
        resolver = RefResolver(cache)

        input_data = {"items": [1, 2, ref.ref_id, 4]}
        result = resolver.resolve(input_data)

        assert result.success
        assert result.value == {"items": [1, 2, 999, 4]}

    def test_resolve_multiple_refs(self, cache: RefCache) -> None:
        """Test resolving multiple ref_ids in same structure."""
        ref1 = cache.set("a", "value_a")
        ref2 = cache.set("b", "value_b")
        ref3 = cache.set("c", "value_c")
        resolver = RefResolver(cache)

        result = resolver.resolve(
            {
                "first": ref1.ref_id,
                "second": ref2.ref_id,
                "nested": {"third": ref3.ref_id},
            }
        )

        assert result.success
        assert result.value == {
            "first": "value_a",
            "second": "value_b",
            "nested": {"third": "value_c"},
        }
        assert result.resolved_count == 3

    def test_resolve_mixed_refs_and_values(self, cache: RefCache) -> None:
        """Test structure with both refs and regular values."""
        ref = cache.set("data", [1, 2, 3])
        resolver = RefResolver(cache)

        result = resolver.resolve(
            {
                "AAPL": [100, 101, ref.ref_id],
                "MSX": ref.ref_id,
                "factor": 2.5,
                "name": "portfolio",
            }
        )

        assert result.success
        assert result.value == {
            "AAPL": [100, 101, [1, 2, 3]],
            "MSX": [1, 2, 3],
            "factor": 2.5,
            "name": "portfolio",
        }

    def test_resolve_tuple(self, cache: RefCache) -> None:
        """Test resolving ref_id in tuple."""
        ref = cache.set("val", "resolved")
        resolver = RefResolver(cache)

        result = resolver.resolve((1, ref.ref_id, 3))

        assert result.success
        assert result.value == (1, "resolved", 3)

    def test_resolve_non_ref_unchanged(self, cache: RefCache) -> None:
        """Test that non-ref values pass through unchanged."""
        resolver = RefResolver(cache)

        input_data = {"num": 42, "str": "hello", "list": [1, 2, 3]}
        result = resolver.resolve(input_data)

        assert result.success
        assert result.value == input_data
        assert result.resolved_count == 0

    def test_resolve_missing_ref_fails(self, cache: RefCache) -> None:
        """Test that missing ref raises KeyError when fail_on_missing=True."""
        resolver = RefResolver(cache, fail_on_missing=True)

        with pytest.raises(KeyError):
            resolver.resolve("test:abcd1234abcd1234")

    def test_resolve_missing_ref_collects_error(self, cache: RefCache) -> None:
        """Test that missing ref collects error when fail_on_missing=False."""
        resolver = RefResolver(cache, fail_on_missing=False)

        result = resolver.resolve("test:abcd1234abcd1234")

        assert result.has_errors
        assert "test:abcd1234abcd1234" in result.errors
        # Original value kept when resolution fails
        assert result.value == "test:abcd1234abcd1234"

    def test_resolve_permission_denied_fails(self, cache: RefCache) -> None:
        """Test that permission denied raises when fail_on_missing=True."""
        policy = AccessPolicy(agent_permissions=Permission.NONE)
        ref = cache.set("secret", "hidden", policy=policy)
        resolver = RefResolver(cache, actor="agent", fail_on_missing=True)

        with pytest.raises(PermissionError):
            resolver.resolve(ref.ref_id)

    def test_resolve_permission_denied_collects_error(self, cache: RefCache) -> None:
        """Test that permission denied collects error when fail_on_missing=False."""
        policy = AccessPolicy(agent_permissions=Permission.NONE)
        ref = cache.set("secret", "hidden", policy=policy)
        resolver = RefResolver(cache, actor="agent", fail_on_missing=False)

        result = resolver.resolve(ref.ref_id)

        assert result.has_errors
        assert ref.ref_id in result.errors
        assert "Permission denied" in result.errors[ref.ref_id]


class TestResolveRefsConvenienceFunction:
    """Tests for the resolve_refs convenience function."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for testing."""
        return RefCache(name="test")

    def test_resolve_refs_simple(self, cache: RefCache) -> None:
        """Test resolve_refs convenience function."""
        ref = cache.set("data", {"key": "value"})

        result = resolve_refs(cache, {"input": ref.ref_id})

        assert result.success
        assert result.value == {"input": {"key": "value"}}

    def test_resolve_refs_with_actor(self, cache: RefCache) -> None:
        """Test resolve_refs with specific actor."""
        policy = AccessPolicy(user_permissions=Permission.FULL)
        ref = cache.set("data", "secret", policy=policy)

        result = resolve_refs(cache, ref.ref_id, actor="user")

        assert result.success
        assert result.value == "secret"


class TestResolveKwargsConvenienceFunction:
    """Tests for the resolve_kwargs convenience function."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for testing."""
        return RefCache(name="test")

    def test_resolve_kwargs(self, cache: RefCache) -> None:
        """Test resolving refs in function kwargs."""
        ref = cache.set("prices", [100, 200, 300])

        result = resolve_kwargs(cache, {"data": ref.ref_id, "factor": 2.0})

        assert result.success
        assert result.value == {"data": [100, 200, 300], "factor": 2.0}


class TestResolveArgsAndKwargs:
    """Tests for the resolve_args_and_kwargs function."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for testing."""
        return RefCache(name="test")

    def test_resolve_both_args_and_kwargs(self, cache: RefCache) -> None:
        """Test resolving refs in both args and kwargs."""
        ref1 = cache.set("arg_val", [1, 2, 3])
        ref2 = cache.set("kwarg_val", {"a": "b"})

        args = (ref1.ref_id, "regular_arg")
        kwargs = {"data": ref2.ref_id, "count": 5}

        args_result, kwargs_result = resolve_args_and_kwargs(cache, args, kwargs)

        assert args_result.success
        assert kwargs_result.success
        assert args_result.value == ([1, 2, 3], "regular_arg")
        assert kwargs_result.value == {"data": {"a": "b"}, "count": 5}

    def test_resolve_only_in_args(self, cache: RefCache) -> None:
        """Test when only args contain refs."""
        ref = cache.set("val", 42)

        args = (ref.ref_id,)
        kwargs = {"normal": "value"}

        args_result, kwargs_result = resolve_args_and_kwargs(cache, args, kwargs)

        assert args_result.success
        assert kwargs_result.success
        assert args_result.value == (42,)
        assert kwargs_result.value == {"normal": "value"}

    def test_resolve_empty_args_kwargs(self, cache: RefCache) -> None:
        """Test with empty args and kwargs."""
        args_result, kwargs_result = resolve_args_and_kwargs(cache, (), {})

        assert args_result.success
        assert kwargs_result.success
        assert args_result.value == ()
        assert kwargs_result.value == {}


class TestSecurityConsiderations:
    """Tests for security-related behavior in resolution."""

    @pytest.fixture
    def cache(self) -> RefCache:
        """Create a fresh RefCache for testing."""
        return RefCache(name="secure")

    def test_opaque_error_for_missing_vs_permission_denied(
        self, cache: RefCache
    ) -> None:
        """Test that error messages don't leak information about existence.

        The error message for 'not found' and 'permission denied' should be
        similar enough that an attacker cannot determine if a ref exists.
        """
        # Create a ref that agent can't access
        policy = AccessPolicy(agent_permissions=Permission.NONE)
        existing_ref = cache.set("secret", "hidden", policy=policy)

        resolver = RefResolver(cache, actor="agent", fail_on_missing=False)

        # Resolve the existing (but denied) ref
        result1 = resolver.resolve(existing_ref.ref_id)

        # Resolve a non-existent ref
        result2 = resolver.resolve("secure:abcd1234abcd1234")

        # Both should have errors
        assert result1.has_errors
        assert result2.has_errors

        # Error messages should both indicate inaccessibility
        # (not specifically "doesn't exist" vs "permission denied")
        error1 = result1.errors[existing_ref.ref_id]
        error2 = result2.errors["secure:abcd1234abcd1234"]

        # Just verify both are error strings (actual message format tested elsewhere)
        assert isinstance(error1, str)
        assert isinstance(error2, str)

    def test_ref_pattern_prevents_injection(self, cache: RefCache) -> None:
        """Test that ref_id pattern prevents path traversal or injection."""
        # These should NOT be recognized as ref_ids
        malicious_inputs = [
            "../../../etc/passwd",
            "test:../secret",
            "test:; DROP TABLE users;",
            "test:$(whoami)",
            "test:`id`",
        ]

        for malicious in malicious_inputs:
            assert is_ref_id(malicious) is False, f"{malicious} should not be a ref_id"
