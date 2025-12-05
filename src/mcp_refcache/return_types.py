from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ValueReturnType(str, Enum):
    """Control how the value field is returned"""

    DEFAULT = "default"  # Smart return - full or preview based on size
    PREVIEW = "preview"  # Always return a preview
    FULL = "full"  # Always return the full value


class ReferenceReturnType(str, Enum):
    """Control how the reference field is returned"""

    DEFAULT = "default"  # Return only the minimal ID
    SIMPLE = "simple"  # Return ID and cache name only
    FULL = "full"  # Return full reference details


class PaginationParams(BaseModel):
    """Parameters for paginating large responses"""

    page: int = Field(
        default=1, ge=1, description="Page number to retrieve (starting from 1)"
    )
    page_size: int = Field(default=20, ge=1, description="Number of items per page")


class InterpolationParams(BaseModel):
    """Parameters for interpolating (sampling) large collections"""

    enabled: bool = Field(default=True, description="Whether interpolation is enabled")
    sample_count: int = Field(
        default=10, ge=2, description="Number of items to sample from the collection"
    )
    min_size_to_interpolate: int = Field(
        default=20,
        ge=0,
        description="Minimum collection size to trigger interpolation (smaller collections return all elements)",
    )
    include_endpoints: bool = Field(
        default=True,
        description="Whether to always include the first and last elements in the sample",
    )


class ReturnOptions(BaseModel):
    """Options for controlling how values are returned from the cache"""

    value_type: Optional[ValueReturnType] = Field(
        default=ValueReturnType.DEFAULT,
        description="Controls how the value field is returned. Set to None for no value.",
    )
    reference_type: Optional[ReferenceReturnType] = Field(
        default=ReferenceReturnType.DEFAULT,
        description="Controls how the reference field is returned. Set to None for no reference.",
    )
    pagination: Optional[PaginationParams] = Field(
        default=None,
        description="Optional pagination parameters for value-returning responses",
    )
    interpolation: Optional[InterpolationParams] = Field(
        default=None,
        description="Optional interpolation parameters for sampling large collections",
    )

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ReturnOptions":
        """Create ReturnOptions from a dictionary, with proper error handling"""
        # Handle None or empty dict
        if not data:
            return cls()

        # Initialize with defaults
        value_type = ValueReturnType.DEFAULT
        reference_type = ReferenceReturnType.DEFAULT
        pagination = None
        interpolation = None

        # Extract value_type - check if key exists in data first
        if "value_type" in data:
            value_type_data = data["value_type"]
            if value_type_data is None:  # Explicitly set to None
                value_type = None
            elif isinstance(value_type_data, ValueReturnType):
                value_type = value_type_data
            else:
                try:
                    value_type = ValueReturnType(value_type_data)
                except (ValueError, TypeError):
                    # Invalid value_type, keep default
                    pass

        # Extract reference_type - check if key exists in data first
        if "reference_type" in data:
            reference_type_data = data["reference_type"]
            if reference_type_data is None:  # Explicitly set to None
                reference_type = None
            elif isinstance(reference_type_data, ReferenceReturnType):
                reference_type = reference_type_data
            else:
                try:
                    reference_type = ReferenceReturnType(reference_type_data)
                except (ValueError, TypeError):
                    # Invalid reference_type, keep default
                    pass

        # Extract pagination parameters
        pagination_data = data.get("pagination")
        if pagination_data is not None:
            try:
                if isinstance(pagination_data, dict):
                    pagination = PaginationParams(**pagination_data)
                elif hasattr(pagination_data, "page") and hasattr(
                    pagination_data, "page_size"
                ):
                    pagination = PaginationParams(
                        page=pagination_data.page, page_size=pagination_data.page_size
                    )
                # If it's not a valid pagination object, set pagination to None
                else:
                    pagination = None
            except Exception:
                # On error, set pagination to None
                pagination = None

        # Extract interpolation parameters
        interpolation_data = data.get("interpolation")
        if interpolation_data is not None:
            try:
                if isinstance(interpolation_data, dict):
                    interpolation = InterpolationParams(**interpolation_data)
                elif hasattr(interpolation_data, "enabled"):
                    # Start with default parameters
                    params = {
                        "enabled": False,
                        "sample_count": 10,
                        "min_size_to_interpolate": 20,
                        "include_endpoints": True,
                    }

                    # Override with values from the object
                    if interpolation_data.enabled is not None:
                        params["enabled"] = interpolation_data.enabled

                    if (
                        hasattr(interpolation_data, "sample_count")
                        and interpolation_data.sample_count is not None
                    ):
                        params["sample_count"] = interpolation_data.sample_count

                    # Don't override min_size_to_interpolate even if it exists
                    # This ensures we always use 20 as default

                    if (
                        hasattr(interpolation_data, "include_endpoints")
                        and interpolation_data.include_endpoints is not None
                    ):
                        params["include_endpoints"] = (
                            interpolation_data.include_endpoints
                        )

                    interpolation = InterpolationParams(**params)
                elif isinstance(interpolation_data, bool):
                    # Simple boolean flag
                    interpolation = InterpolationParams(enabled=interpolation_data)
                else:
                    # Set to None for invalid types
                    interpolation = None
            except Exception:
                # On error, set interpolation to None
                interpolation = None

        # Create and return the options object
        return cls(
            value_type=value_type,
            reference_type=reference_type,
            pagination=pagination,
            interpolation=interpolation,
        )
