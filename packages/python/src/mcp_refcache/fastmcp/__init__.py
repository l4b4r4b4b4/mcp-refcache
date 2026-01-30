"""FastMCP integration helpers for mcp-refcache.

This module provides utilities for integrating RefCache with FastMCP servers,
including instruction generators for tools, prompts, and server descriptions.

The goal is to automatically inject cache-aware instructions so that LLM agents
understand how to work with:
1. Response types (direct values vs references)
2. Pagination and navigation
3. Passing references as inputs

Example:
    ```python
    from fastmcp import FastMCP
    from mcp_refcache import RefCache
    from mcp_refcache.fastmcp import (
        cache_instructions,
        cached_tool_description,
        cache_guide_prompt,
    )

    mcp = FastMCP(
        name="MyServer",
        instructions=cache_instructions(),  # Add cache-aware instructions
    )

    cache = RefCache(name="my-cache")

    @mcp.tool(description=cached_tool_description(
        "Fetches user data from the database.",
        returns_reference=True,
        supports_pagination=True,
    ))
    async def get_users(query: str) -> dict:
        ...

    # Register the cache guide prompt
    mcp.prompt(cache_guide_prompt)
    ```
"""

from mcp_refcache.fastmcp.admin_tools import (
    AdminChecker,
    AdminToolError,
    PermissionDeniedError,
    register_admin_tools,
)
from mcp_refcache.fastmcp.instructions import (
    cache_guide_prompt,
    cache_instructions,
    cached_tool_description,
    format_response_hint,
    get_full_cache_guide,
    with_cache_docs,
)

__all__ = [
    "AdminChecker",
    "AdminToolError",
    "PermissionDeniedError",
    "cache_guide_prompt",
    "cache_instructions",
    "cached_tool_description",
    "format_response_hint",
    "get_full_cache_guide",
    "register_admin_tools",
    "with_cache_docs",
]
