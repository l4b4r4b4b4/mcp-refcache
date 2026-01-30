"""Tests for the mcp-refcache library."""

from typing import Any

from mcp_refcache import (
    AccessPolicy,
    CacheReference,
    CacheResponse,
    PaginatedResponse,
    Permission,
    PreviewConfig,
    __version__,
)
from mcp_refcache.models import PreviewStrategy, SizeMode


class TestVersion:
    """Test version information."""

    def test_version_exists(self) -> None:
        """Test that version is defined."""
        assert __version__ is not None
        assert isinstance(__version__, str)

    def test_version_format(self) -> None:
        """Test that version follows semver format."""
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)


class TestPermissions:
    """Tests for Permission enum and AccessPolicy."""

    def test_permission_flags(self) -> None:
        """Test that permission flags are defined correctly."""
        assert Permission.NONE.value == 0
        assert Permission.READ != Permission.NONE
        assert Permission.WRITE != Permission.READ
        assert Permission.EXECUTE != Permission.NONE

    def test_permission_combinations(self) -> None:
        """Test combining permissions with bitwise operators."""
        read_write = Permission.READ | Permission.WRITE
        assert Permission.READ in read_write
        assert Permission.WRITE in read_write
        assert Permission.DELETE not in read_write

    def test_permission_crud(self) -> None:
        """Test CRUD convenience combination."""
        assert Permission.READ in Permission.CRUD
        assert Permission.WRITE in Permission.CRUD
        assert Permission.UPDATE in Permission.CRUD
        assert Permission.DELETE in Permission.CRUD
        assert Permission.EXECUTE not in Permission.CRUD

    def test_permission_full(self) -> None:
        """Test FULL includes all permissions."""
        assert Permission.READ in Permission.FULL
        assert Permission.WRITE in Permission.FULL
        assert Permission.UPDATE in Permission.FULL
        assert Permission.DELETE in Permission.FULL
        assert Permission.EXECUTE in Permission.FULL

    def test_access_policy_defaults(self) -> None:
        """Test AccessPolicy default values."""
        policy = AccessPolicy()
        assert policy.user_permissions == Permission.FULL
        assert policy.agent_permissions == Permission.READ | Permission.EXECUTE

    def test_access_policy_custom(self) -> None:
        """Test AccessPolicy with custom permissions."""
        policy = AccessPolicy(
            user_permissions=Permission.READ,
            agent_permissions=Permission.EXECUTE,
        )
        assert policy.user_permissions == Permission.READ
        assert policy.agent_permissions == Permission.EXECUTE

    def test_access_policy_user_can(self) -> None:
        """Test user permission checking."""
        policy = AccessPolicy(user_permissions=Permission.READ | Permission.WRITE)
        assert policy.user_can(Permission.READ)
        assert policy.user_can(Permission.WRITE)
        assert not policy.user_can(Permission.DELETE)

    def test_access_policy_agent_can(self) -> None:
        """Test agent permission checking."""
        policy = AccessPolicy(agent_permissions=Permission.EXECUTE)
        assert policy.agent_can(Permission.EXECUTE)
        assert not policy.agent_can(Permission.READ)


class TestPreviewConfig:
    """Tests for PreviewConfig."""

    def test_preview_config_defaults(self) -> None:
        """Test PreviewConfig default values."""
        config = PreviewConfig()
        assert config.size_mode == SizeMode.TOKEN
        assert config.max_size == 1000
        assert config.default_strategy == PreviewStrategy.SAMPLE

    def test_preview_config_custom(self) -> None:
        """Test PreviewConfig with custom values."""
        config = PreviewConfig(
            size_mode=SizeMode.CHARACTER,
            max_size=500,
            default_strategy=PreviewStrategy.PAGINATE,
        )
        assert config.size_mode == SizeMode.CHARACTER
        assert config.max_size == 500
        assert config.default_strategy == PreviewStrategy.PAGINATE


class TestCacheReference:
    """Tests for CacheReference model."""

    def test_cache_reference_required_fields(self) -> None:
        """Test CacheReference with required fields."""
        ref = CacheReference(
            ref_id="abc123",
            cache_name="test-cache",
            created_at=1234567890.0,
        )
        assert ref.ref_id == "abc123"
        assert ref.cache_name == "test-cache"
        assert ref.namespace == "public"  # default
        assert ref.created_at == 1234567890.0

    def test_cache_reference_optional_fields(self) -> None:
        """Test CacheReference with optional fields."""
        ref = CacheReference(
            ref_id="abc123",
            cache_name="test-cache",
            created_at=1234567890.0,
            namespace="session:xyz",
            tool_name="my_tool",
            total_items=100,
            total_tokens=5000,
        )
        assert ref.namespace == "session:xyz"
        assert ref.tool_name == "my_tool"
        assert ref.total_items == 100
        assert ref.total_tokens == 5000


class TestPaginatedResponse:
    """Tests for PaginatedResponse model."""

    def test_paginated_response_from_list(self) -> None:
        """Test creating PaginatedResponse from a list."""
        items = list(range(100))
        response = PaginatedResponse.from_list(items, page=1, page_size=20)

        assert len(response.items) == 20
        assert response.items == list(range(20))
        assert response.page == 1
        assert response.page_size == 20
        assert response.total_items == 100
        assert response.total_pages == 5
        assert response.has_next is True
        assert response.has_previous is False

    def test_paginated_response_middle_page(self) -> None:
        """Test PaginatedResponse for a middle page."""
        items = list(range(100))
        response = PaginatedResponse.from_list(items, page=3, page_size=20)

        assert len(response.items) == 20
        assert response.items == list(range(40, 60))
        assert response.page == 3
        assert response.has_next is True
        assert response.has_previous is True

    def test_paginated_response_last_page(self) -> None:
        """Test PaginatedResponse for the last page."""
        items = list(range(100))
        response = PaginatedResponse.from_list(items, page=5, page_size=20)

        assert len(response.items) == 20
        assert response.items == list(range(80, 100))
        assert response.page == 5
        assert response.has_next is False
        assert response.has_previous is True

    def test_paginated_response_partial_page(self) -> None:
        """Test PaginatedResponse when last page is partial."""
        items = list(range(25))
        response = PaginatedResponse.from_list(items, page=2, page_size=20)

        assert len(response.items) == 5
        assert response.items == list(range(20, 25))
        assert response.total_pages == 2

    def test_paginated_response_empty(self) -> None:
        """Test PaginatedResponse with empty list."""
        response = PaginatedResponse.from_list([], page=1, page_size=20)

        assert response.items == []
        assert response.total_items == 0
        assert response.total_pages == 0


class TestCacheResponse:
    """Tests for CacheResponse model."""

    def test_cache_response_basic(self) -> None:
        """Test CacheResponse with basic fields."""
        response = CacheResponse(
            ref_id="abc123",
            cache_name="test-cache",
            preview=[{"id": 1}, {"id": 2}],
            preview_strategy=PreviewStrategy.SAMPLE,
        )
        assert response.ref_id == "abc123"
        assert response.cache_name == "test-cache"
        assert response.namespace == "public"
        assert response.preview == [{"id": 1}, {"id": 2}]
        assert response.preview_strategy == PreviewStrategy.SAMPLE

    def test_cache_response_with_pagination(self) -> None:
        """Test CacheResponse with pagination info."""
        response = CacheResponse(
            ref_id="abc123",
            cache_name="test-cache",
            preview=[{"id": 1}],
            preview_strategy=PreviewStrategy.PAGINATE,
            total_items=100,
            page=1,
            total_pages=10,
        )
        assert response.page == 1
        assert response.total_pages == 10
        assert response.total_items == 100

    def test_cache_response_available_actions(self) -> None:
        """Test CacheResponse default available actions."""
        response = CacheResponse(
            ref_id="abc123",
            cache_name="test-cache",
            preview={"key": "value"},
            preview_strategy=PreviewStrategy.TRUNCATE,
        )
        assert "get_page" in response.available_actions
        assert "resolve_full" in response.available_actions
        assert "pass_to_tool" in response.available_actions


class TestFixtures:
    """Tests using pytest fixtures."""

    def test_sample_value_fixture(self, sample_value: dict[str, Any]) -> None:
        """Test that the sample_value fixture works."""
        assert sample_value["id"] == 123
        assert sample_value["name"] == "Test User"
        assert "metadata" in sample_value

    def test_large_value_fixture(self, large_value: dict[str, Any]) -> None:
        """Test that the large_value fixture generates expected data."""
        assert len(large_value["items"]) == 1000
        assert large_value["total"] == 1000
        assert large_value["items"][0]["id"] == 0
        assert large_value["items"][999]["id"] == 999

    def test_namespace_fixtures(
        self,
        sample_namespace: str,
        session_namespace: str,
        user_namespace: str,
    ) -> None:
        """Test that namespace fixtures are properly formatted."""
        assert sample_namespace == "test:unit"
        assert session_namespace.startswith("session:")
        assert user_namespace.startswith("user:")
