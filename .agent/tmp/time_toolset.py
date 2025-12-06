import datetime
import pytz
from typing import Optional, Union
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
from system_2.doc_tools.options import with_tool_options

from system_2.cache.cache import (
    CacheReference,
    ToolsetCache,
)
from system_2.cache.return_types import (
    ReturnOptions,
    # ValueReturnType,
    # ReferenceReturnType,
    # PaginationParams,
)
from system_2.cache.redis_cache import RedisCompatibleCache

# Create a named server with dependencies
mcp = FastMCP(
    name="Time Tools",
    description="Tools for working with time, dates, and timezones",
    dependencies=["pytz", "datetime", "pydantic>=2.0.0"],
    version="0.0.1",
)

ToolsetCache.register_cache_implementation(RedisCompatibleCache)

time_cache = ToolsetCache.get_cache_for_tool("time_toolset")


# ------ Pydantic Models for Strong Typing ------
class TimeResult(BaseModel):
    """Result model for current time information"""

    timezone: str = Field(description="The timezone name")
    iso_format: str = Field(description="ISO 8601 formatted datetime")
    date: str = Field(description="Date in YYYY-MM-DD format")
    time: str = Field(description="Time in HH:MM:SS format")
    day_of_week: str = Field(description="Full day name (e.g., Monday)")
    timestamp: float = Field(description="Unix timestamp (seconds since epoch)")


# Options parameter for controlling return type
# class ToolOptionsParam(BaseModel):
#     value_type: ValueReturnType = Field(
#         default=ValueReturnType.DEFAULT,
#         description="Controls how the value is returned: 'default' for smart return (full or preview based on size), 'full' for complete value, 'preview' for a preview, 'null' for no value",
#     )
#     reference_type: ReferenceReturnType = Field(
#         default=ReferenceReturnType.DEFAULT,
#         description="Controls how the reference is returned: 'default' for minimal ID, 'simple' for ID and cache name, 'full' for complete reference, 'null' for no reference",
#     )
#     pagination: Optional[PaginationParams] = Field(
#         default=None,
#         description="Optional pagination parameters for value-returning responses",
#     )


# Input model for current_time
class CurrentTimeInput(BaseModel):
    timezone: str = Field(
        default="UTC",
        description="Timezone name (e.g., 'UTC', 'US/Pacific', 'Europe/London')",
    )


# Input model for list_timezones
class ListTimezonesInput(BaseModel):
    # This is an empty model since list_timezones doesn't need any parameters
    pass


# Input model for convert_timezone
class ConvertTimezoneInput(BaseModel):
    source_time: Union[str, CacheReference] = Field(
        description="Time string in format 'YYYY-MM-DD HH:MM:SS' or a reference to a previous time result"
    )
    source_timezone: Optional[str] = Field(
        default=None,
        description="Source timezone name (ignored if source_time is a reference)",
    )
    target_timezone: str = Field(default="UTC", description="Target timezone name")


@mcp.tool(description="Get current time in any timezone")
@time_cache.cached
@with_tool_options()
def current_time(
    input_data: CurrentTimeInput, options: Optional[ReturnOptions] = None
) -> Union[TimeResult, str, CacheReference]:
    """
    Get the current time in the specified timezone.

    Parameters:
    - input_data: Input parameters
        - timezone: Timezone name (e.g., 'UTC', 'US/Pacific', 'Europe/London')
        If not specified, returns UTC time

    Returns:
    A response object containing:
    - value: The time information (or preview or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)

    Example:
    ```
    # Get current time in UTC
    utc_time = current_time(input_data={"timezone": "UTC"})

    # Access the time information
    print(f"The current UTC time is {utc_time['value'].time}")

    # Store as a reference for later use
    time_ref = current_time(
        input_data={"timezone": "UTC"},
        options={"value_type": None, "reference_type": "full"}
    )

    # The reference ID can be used directly in other time operations
    tokyo_time = convert_timezone(
        input_data={
            "source_time": time_ref["reference"]["ref_id"],  # Just use the reference ID string
            "target_timezone": "Asia/Tokyo"
        }
    )
    ```
    """
    try:
        tz = pytz.timezone(input_data.timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(
            f"Unknown timezone: {input_data.timezone}. Use a valid timezone from the IANA Time Zone Database."
        )

    now = datetime.datetime.now(tz)

    return TimeResult(
        timezone=input_data.timezone,
        iso_format=now.isoformat(),
        date=now.strftime("%Y-%m-%d"),
        time=now.strftime("%H:%M:%S"),
        day_of_week=now.strftime("%A"),
        timestamp=now.timestamp(),
    )


@mcp.tool(description="List all available timezone names")
@time_cache.cached
@with_tool_options(pagination=True)
def list_timezones(
    input_data: ListTimezonesInput,
    options: Optional[ReturnOptions] = None,
) -> Union[list, str, CacheReference]:
    """
    List all available timezone names.

    Parameters:
    - input_data: Empty model as this tool doesn't require input parameters

    Returns:
    A response object containing:
    - value: List of timezone names (or preview or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)
    """
    return sorted(pytz.all_timezones)


@mcp.tool(description="Convert a time between two timezones")
@time_cache.cached
@with_tool_options()
def convert_timezone(
    input_data: ConvertTimezoneInput,
    options: Optional[ReturnOptions] = None,
) -> Union[TimeResult, str, CacheReference]:
    """
    Convert a time from one timezone to another.

    Parameters:
    - input_data: Input parameters for timezone conversion
      - source_time: Time string in format "YYYY-MM-DD HH:MM:SS" or a reference ID to a previous time result
        You can pass:
        - A time string like "2023-06-01 12:34:56"
        - A reference ID as a string (e.g., "abc123") - automatically resolved by the cache
      - source_timezone: Source timezone name (ignored if source_time is a reference to a TimeResult)
      - target_timezone: Target timezone name

    Returns:
    A response object containing:
    - value: The converted time (or preview or null depending on value_type)
    - reference: Reference details (or null depending on reference_type)

    Example:
    ```python
    # Get current time in UTC
    utc_time = current_time(input_data={"timezone": "UTC"})

    # Convert to Tokyo time using the reference ID directly
    tokyo_time = convert_timezone(
        input_data={
            "source_time": utc_time["reference"]["ref_id"],
            "target_timezone": "Asia/Tokyo"
        }
    )
    ```
    """
    # Extract input parameters
    source_time = input_data.source_time
    source_timezone = input_data.source_timezone
    target_timezone = input_data.target_timezone

    # If source_time is a TimeResult object (automatically resolved from a reference)
    # This happens when the reference ID was passed and the cache decorator resolved it
    if isinstance(source_time, TimeResult):
        # Use the ISO format from the TimeResult
        time_str = source_time.iso_format
        source_timezone = source_time.timezone
    else:
        # Otherwise, use the source_time string directly
        time_str = str(source_time)

    # Parse source timezone
    try:
        source_tz = pytz.timezone(source_timezone) if source_timezone else pytz.UTC
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Unknown source timezone: {source_timezone}")

    # Parse target timezone
    try:
        target_tz = pytz.timezone(target_timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Unknown target timezone: {target_timezone}")

    # Parse the time string
    try:
        if "T" in time_str:  # ISO format
            dt = datetime.datetime.fromisoformat(time_str)
        else:
            dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise ValueError(
            "Invalid time format. Use 'YYYY-MM-DD HH:MM:SS' or ISO format 'YYYY-MM-DDTHH:MM:SS+00:00'"
        )

    # Ensure the datetime is timezone-aware
    if dt.tzinfo is None:
        dt = source_tz.localize(dt)

    # Convert to target timezone
    converted = dt.astimezone(target_tz)

    return TimeResult(
        timezone=target_timezone,
        iso_format=converted.isoformat(),
        date=converted.strftime("%Y-%m-%d"),
        time=converted.strftime("%H:%M:%S"),
        day_of_week=converted.strftime("%A"),
        timestamp=converted.timestamp(),
    )


@mcp.prompt()
def toolset_usage_guide() -> str:
    """
    A guide for using the Time Tools with various return types.
    """
    return """
    # Time Tools Usage Guide

    This toolset offers time-related functions with a flexible caching system.

    ## Working with References

    ### Creating References

    ```python
    # Get the current time as a reference
    time_ref = current_time(
        input_data={"timezone": "UTC"},
        options={"value_type": None, "reference_type": "full"}
    )
    ```

    ### Using References in Other Tools

    The caching system automatically resolves references at any nesting level in the input_data. You can simply use the reference ID directly:

    ```python
    # When you get a result with a reference
    result = current_time(input_data={"timezone": "UTC"})

    # Use the reference ID directly in another tool call
    # Just pass the reference ID string where you would normally put a value
    tokyo_time = convert_timezone(
        input_data={
            "source_time": result["reference"]["ref_id"],  # Just pass the reference ID string
            "target_timezone": "Asia/Tokyo"
        }
    )
    ```

    The cache system is smart enough to:

    1. Recognize reference IDs and automatically resolve them
    2. Handle nested references at any level in complex data structures
    3. Work with references from any cache (cross-cache resolution)

    You can use reference IDs with any parameter that accepts the referenced type:

    ```python
    # For deeply nested structures, references work at any level
    complex_input = {
        "main_data": {
            "nested": {
                "deeply_nested_field": result["reference"]["ref_id"]  # Reference here works too!
            }
        },
        "other_field": "normal value"
    }
    ```

    ## Return Type Options

    All tools in this toolset support granular control over how values and references are returned:

    ```python
    options = {
        "value_type": "default",  # Controls how the value is returned
        "reference_type": "default",  # Controls how the reference is returned
        "pagination": {"page": 1, "page_size": 20}  # Optional pagination
    }
    ```

    ### Value Return Types:

    - `"default"`: Smart return - full for small results, preview for large ones (default)
    - `"full"`: Always return the complete value
    - `"preview"`: Always return a preview of the value
    - `None`: Don't return any value (reference only)

    ### Reference Return Types:

    - `"default"`: Return minimal reference ID (default)
    - `"simple"`: Return reference ID and cache name
    - `"full"`: Return complete reference details
    - `None`: Don't return any reference (value only)

    ## Example Usage

    ```python
    # Get the current time with default return type (smart reference + value)
    result = current_time(input_data={"timezone": "UTC"})

    # Access the value directly if available
    if "value" in result and result["value"] is not None:
        time_data = result["value"]
        print(f"Current time: {time_data.time}")

    # Use the reference ID to convert to a different timezone
    tokyo_time = convert_timezone(
        input_data={
            "source_time": result["reference"]["ref_id"],  # Reference ID works directly
            "target_timezone": "Asia/Tokyo"
        }
    )
    ```

    Use this flexible system to optimize context usage and reuse values across multiple tool calls.
    """


if __name__ == "__main__":
    mcp.run(transport="stdio")
