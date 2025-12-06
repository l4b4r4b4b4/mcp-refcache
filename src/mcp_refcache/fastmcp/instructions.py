"""Instruction generators for cache-aware MCP tools.

This module provides utilities for generating consistent, comprehensive
instructions that help LLM agents understand how to work with RefCache.

The instructions cover three main areas:
1. Response Types - Understanding direct values vs references
2. Pagination & Exploration - Navigating large datasets
3. Passing References as Inputs - Chaining tools together

These helpers can be used at multiple levels:
- Server instructions (FastMCP constructor)
- Tool descriptions (docstrings or description parameter)
- Prompts (guide prompts for detailed help)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# =============================================================================
# Response Type Documentation
# =============================================================================

RESPONSE_TYPES_SECTION = """
## Response Types

Tools in this server may return two types of responses:

### Direct Values
Small results are returned directly:
```json
{"result": 42, "expression": "6 * 7"}
```

### Reference Responses
Large results are cached and returned as references with previews:
```json
{
    "ref_id": "abc123",
    "preview": [1, 1, 2, 3, 5, 8, "... and 994 more"],
    "total_items": 1000,
    "preview_strategy": "sample",
    "available_actions": ["get_page", "resolve_full", "pass_to_tool"]
}
```

Key fields in reference responses:
- `ref_id`: Unique identifier for accessing the cached value
- `preview`: A representative sample/truncation of the data
- `total_items`: Total number of items in the full dataset
- `preview_strategy`: How the preview was generated (sample, truncate, paginate)
- `page` / `total_pages`: Present when using pagination

### Error Responses
You may encounter these errors:
- **Permission denied**: You don't have access to this reference
- **Not found / Expired**: The reference has expired or doesn't exist
""".strip()

# =============================================================================
# Pagination Documentation
# =============================================================================

PAGINATION_SECTION = """
## Pagination & Exploration

When you receive a reference response, you can explore the data:

### Getting Specific Pages
Use the cache retrieval tool with `page` and `page_size` parameters:
```
get_cached_result(ref_id="abc123", page=2, page_size=20)
```

This returns:
```json
{
    "ref_id": "abc123",
    "preview": [... items 21-40 ...],
    "page": 2,
    "total_pages": 50,
    "total_items": 1000
}
```

### Preview Strategies
The server uses different strategies to create previews:
- **sample**: Evenly-spaced items from the collection (default for lists)
- **truncate**: First N characters/tokens (for strings)
- **paginate**: Sequential pages of items

## Navigation Tips
1. Check `total_items` and `total_pages` to understand data size
2. Use sequential pages to scan through data
3. The preview gives you a representative sample to understand the data structure

## Preview Size Control

Preview size can be configured at three levels (highest priority first):
1. **Per-call**: `get_cached_result(ref_id, max_size=100)` - override for this request
2. **Per-tool**: Set by the tool author - check tool description for details
3. **Server default**: Falls back to server configuration

Use smaller `max_size` for quick summaries, larger for more context.
""".strip()

# =============================================================================
# Reference Input Documentation
# =============================================================================

REFERENCE_INPUT_SECTION = """
## Passing References as Inputs

References can be passed to other tools that accept them:

### Basic Usage
When a tool accepts a reference, pass the `ref_id`:
```
process_data(data_ref="abc123")
analyze_results(input_ref="abc123", output_format="summary")
```

### Private Computation
Some references have restricted access - you can use them in computations
without seeing the actual value:
```
# Store a secret (you won't see the value)
store_secret(name="api_key", value="...")
# Returns: {"ref_id": "secret_xyz", "message": "Stored securely"}

# Use in computation (server resolves internally)
compute_with_secret(secret_ref="secret_xyz", expression="hash(x)")
# Returns: {"result": "a1b2c3...", "message": "Computed using secret"}
```

This is useful for:
- API keys and credentials
- Personal data that shouldn't be in conversation
- Sensitive business logic

### Chaining Tools
References act as a "data bus" between tools:
```
# Step 1: Fetch data
data = fetch_large_dataset(query="sales")
# Returns: {"ref_id": "data_123", "preview": [...], "total_items": 50000}

# Step 2: Process using reference (not the full data!)
result = aggregate_data(data_ref="data_123", operation="sum")
# Server resolves the reference internally

# Step 3: Pass result to another tool
export_result(result_ref=result["ref_id"], format="csv")
```
""".strip()

# =============================================================================
# Cache Management Documentation (Admin Only)
# =============================================================================

CACHE_MANAGEMENT_SECTION = """
## Cache Management (Admin Only)

⚠️ These operations are restricted to elevated users and not available to agents.

Administrative tools may include:
- `list_caches`: View all cache instances
- `list_references`: Browse cached references
- `get_cache_stats`: View cache statistics
- `clear_cache`: Remove cached data
- `delete_reference`: Remove specific references

If you need cache information, ask a human operator for assistance.
""".strip()

# =============================================================================
# Complete Guide
# =============================================================================

FULL_CACHE_GUIDE = f"""
# Working with Cached Data

This server uses reference-based caching to handle large data efficiently.
Instead of returning massive datasets directly, it returns lightweight
references with previews that you can explore incrementally.

{RESPONSE_TYPES_SECTION}

{PAGINATION_SECTION}

{REFERENCE_INPUT_SECTION}

{CACHE_MANAGEMENT_SECTION}

## Quick Reference

| Action | How |
|--------|-----|
| View preview | Included in response |
| Get page N | `get_cached_result(ref_id, page=N)` |
| Pass to tool | Use `ref_id` as parameter |
| Private compute | Tools resolve references server-side |
""".strip()

# =============================================================================
# Compact Server Instructions
# =============================================================================

COMPACT_INSTRUCTIONS = """
This server uses reference-based caching for large results.

**Response Types:**
- Small results: returned directly
- Large results: returned as `{ref_id, preview, total_items}`

**Working with References:**
- Paginate: `get_cached_result(ref_id, page=2, page_size=20)`
- Pass to tools: use `ref_id` as input parameter
- Some refs are execute-only (use in computation, can't read)

**Preview Size Control:**
- Per-call override: `get_cached_result(ref_id, max_size=100)`
- Per-tool: Check tool description for tool-specific limits
- Server default: Used when no override specified

**Note:** References may expire. Cache admin tools are restricted to elevated users.
""".strip()


# =============================================================================
# Public API Functions
# =============================================================================


def cache_instructions(compact: bool = True) -> str:
    """Generate cache-aware instructions for FastMCP server.

    Use this in the FastMCP constructor to inform agents about
    how caching works in your server.

    Args:
        compact: If True, returns a shorter version suitable for
            server instructions. If False, returns the full guide.

    Returns:
        Instruction string to include in FastMCP(instructions=...).

    Example:
        ```python
        from fastmcp import FastMCP
        from mcp_refcache.fastmcp import cache_instructions

        mcp = FastMCP(
            name="MyServer",
            instructions=cache_instructions(),
        )
        ```
    """
    return COMPACT_INSTRUCTIONS if compact else FULL_CACHE_GUIDE


def get_full_cache_guide() -> str:
    """Get the complete cache guide.

    This is the full documentation covering all aspects of
    working with cached data. Suitable for use in prompts
    or detailed documentation.

    Returns:
        Complete cache guide as a string.
    """
    return FULL_CACHE_GUIDE


def cached_tool_description(
    base_description: str,
    *,
    returns_reference: bool = True,
    supports_pagination: bool = False,
    accepts_references: bool = False,
    private_computation: bool = False,
) -> str:
    """Generate a cache-aware tool description.

    Appends relevant cache information to a tool's base description
    so agents understand how to work with its inputs and outputs.

    Args:
        base_description: The tool's core description.
        returns_reference: If True, notes that large results return references.
        supports_pagination: If True, documents pagination parameters.
        accepts_references: If True, notes that ref_ids can be passed as input.
        private_computation: If True, notes that values are used without reading.

    Returns:
        Enhanced description string.

    Example:
        ```python
        @mcp.tool(description=cached_tool_description(
            "Fetches user records from the database.",
            returns_reference=True,
            supports_pagination=True,
        ))
        async def get_users(query: str, page: int = 1) -> dict:
            ...
        ```
    """
    parts = [base_description.rstrip(".") + "."]

    if returns_reference:
        parts.append(
            "Large results return a reference with preview. "
            "Use `ref_id` to paginate or pass to other tools."
        )

    if supports_pagination:
        parts.append("Supports `page` and `page_size` parameters for navigation.")

    if accepts_references:
        parts.append("Accepts `ref_id` from previous tool calls as input.")

    if private_computation:
        parts.append(
            "Values are used server-side without exposing to the conversation "
            "(private computation)."
        )

    return " ".join(parts)


def format_response_hint(
    *,
    has_reference: bool = True,
    has_preview: bool = True,
    has_pagination: bool = False,
    available_actions: list[str] | None = None,
) -> str:
    """Generate a response format hint for tool docstrings.

    Use this in docstrings to document the response structure.

    Args:
        has_reference: Include ref_id documentation.
        has_preview: Include preview documentation.
        has_pagination: Include pagination documentation.
        available_actions: List of actions (e.g., ["get_page", "pass_to_tool"]).

    Returns:
        Formatted response documentation string.

    Example:
        ```python
        @mcp.tool
        def search_data(query: str) -> dict:
            '''Search the database.

            {format_response_hint(has_pagination=True)}
            '''
            ...
        ```
    """
    lines = ["Returns:"]

    if has_reference:
        lines.append("    ref_id: Reference ID for accessing the cached result")

    if has_preview:
        lines.append("    preview: Sample/truncation of the data")
        lines.append("    total_items: Total number of items")

    if has_pagination:
        lines.append("    page: Current page number")
        lines.append("    total_pages: Total pages available")

    if available_actions:
        actions_str = ", ".join(available_actions)
        lines.append(f"    available_actions: [{actions_str}]")

    return "\n".join(lines)


def cache_guide_prompt() -> str:
    """A prompt providing the complete cache usage guide.

    Register this as a prompt in your FastMCP server to give
    agents access to detailed cache documentation.

    Returns:
        The complete cache guide.

    Example:
        ```python
        from fastmcp import FastMCP
        from mcp_refcache.fastmcp import cache_guide_prompt

        mcp = FastMCP(name="MyServer")

        @mcp.prompt
        def cache_help() -> str:
            '''Get help on working with cached data and references.'''
            return cache_guide_prompt()
        ```
    """
    return FULL_CACHE_GUIDE


# =============================================================================
# Decorator Helpers (Future Enhancement)
# =============================================================================


def with_cache_docs(
    *,
    returns_reference: bool = True,
    supports_pagination: bool = False,
    accepts_references: bool = False,
    private_computation: bool = False,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Decorator to enhance a function's docstring with cache documentation.

    This decorator appends cache-related documentation to a function's
    docstring, making it cache-aware for MCP discovery.

    Args:
        returns_reference: If True, documents reference returns.
        supports_pagination: If True, documents pagination support.
        accepts_references: If True, documents reference inputs.
        private_computation: If True, documents private computation.

    Returns:
        Decorator function.

    Example:
        ```python
        @mcp.tool
        @with_cache_docs(returns_reference=True, supports_pagination=True)
        async def get_large_dataset(query: str) -> dict:
            '''Fetch a large dataset based on the query.'''
            ...
        ```
    """

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        original_doc = func.__doc__ or ""

        # Build additional documentation
        additions: list[str] = []

        if returns_reference:
            additions.append(
                "**Caching:** Large results are returned as references with previews."
            )

        if supports_pagination:
            additions.append(
                "**Pagination:** Use `page` and `page_size` to navigate results."
            )

        if accepts_references:
            additions.append(
                "**References:** This tool accepts `ref_id` from previous tool calls."
            )

        if private_computation:
            additions.append(
                "**Private Compute:** Values are processed server-side without exposure."
            )

        if additions:
            cache_docs = "\n\n".join(additions)
            func.__doc__ = f"{original_doc}\n\n{cache_docs}"

        return func

    return decorator
