#!/usr/bin/env python3
"""Async Timeout MCP Server - Demonstrates async timeout and polling.

This minimal example shows how to use mcp-refcache's async timeout feature
for long-running tools. When a tool exceeds the timeout, it returns immediately
with a processing status, and the task continues in the background.

Features demonstrated:
- async_timeout: Tool returns quickly even if computation takes long
- Polling: Use get_cached_result to poll for task completion
- MemoryTaskBackend: In-memory background task execution

Usage:
    # Run with stdio (for Zed/Claude Desktop)
    python examples/async_timeout_server.py

    # Run with SSE (for debugging)
    python examples/async_timeout_server.py --transport sse --port 8010

Zed Configuration:
    Add to .zed/settings.json context_servers:
    {
        "async-timeout": {
            "command": "uv",
            "args": ["run", "python", "examples/async_timeout_server.py"]
        }
    }

Polling Pattern:
    1. Call analyze_document() - returns immediately with {"status": "processing", "ref_id": "..."}
    2. Call get_task_status(ref_id) repeatedly until status is "complete"
    3. Final call returns the actual result
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Annotated

from pydantic import Field

# =============================================================================
# Check for FastMCP availability
# =============================================================================

try:
    from fastmcp import FastMCP
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

from mcp_refcache import CacheResponse, RefCache
from mcp_refcache.backends.task_memory import MemoryTaskBackend
from mcp_refcache.models import AsyncTaskResponse

# =============================================================================
# Initialize FastMCP Server
# =============================================================================

mcp = FastMCP(
    name="Async Timeout Demo",
    instructions="""Demo server for async timeout and polling.

**IMPORTANT: Polling Workflow**

1. Call `analyze_document` with your text
2. If it takes >3 seconds, you'll get: {"status": "processing", "ref_id": "..."}
3. Call `get_task_status` with the ref_id to check progress
4. Keep calling `get_task_status` every few seconds until status is "complete"
5. The final response contains the actual analysis result

Example conversation:
- User: "Analyze this document: [long text]"
- AI: *calls analyze_document* → gets processing status
- AI: "The analysis is running in the background. Let me check the status..."
- AI: *calls get_task_status* → still processing
- AI: *waits a few seconds, calls get_task_status again* → complete!
- AI: "Here are the results: ..."
""",
)

# =============================================================================
# Initialize RefCache with TaskBackend
# =============================================================================

# Create task backend for background execution
task_backend = MemoryTaskBackend(max_workers=4)

# Create cache with async support
cache = RefCache(
    name="async-demo",
    task_backend=task_backend,
    default_ttl=300,  # 5 minute TTL
)

# =============================================================================
# Tools
# =============================================================================


@mcp.tool()
@cache.cached(async_timeout=3.0, async_response_format="standard")
async def analyze_document(
    text: Annotated[
        str,
        Field(description="The document text to analyze", min_length=1),
    ],
    analysis_depth: Annotated[
        str,
        Field(
            description="Analysis depth: 'quick' (5s), 'standard' (10s), or 'deep' (20s)",
            default="standard",
        ),
    ] = "standard",
) -> dict:
    """Analyze a document with simulated processing time.

    This tool simulates a long-running document analysis. If processing
    exceeds 3 seconds, it returns a processing status immediately and
    continues in the background.

    Use get_task_status to poll for completion.
    """
    # Determine processing time based on depth
    processing_times = {
        "quick": 5,
        "standard": 10,
        "deep": 20,
    }
    duration = processing_times.get(analysis_depth, 10)

    # Simulate processing
    await asyncio.sleep(duration)

    # Return analysis results
    word_count = len(text.split())
    char_count = len(text)
    sentence_count = text.count(".") + text.count("!") + text.count("?")

    return {
        "analysis_depth": analysis_depth,
        "processing_time_seconds": duration,
        "statistics": {
            "word_count": word_count,
            "character_count": char_count,
            "sentence_count": max(1, sentence_count),
            "average_word_length": round(char_count / max(1, word_count), 2),
        },
        "summary": f"Analyzed {word_count} words in {sentence_count or 1} sentences.",
    }


@mcp.tool()
async def get_task_status(
    ref_id: Annotated[
        str,
        Field(description="The ref_id from a previous async task"),
    ],
) -> dict:
    """Check the status of an async task.

    Call this repeatedly with the ref_id from analyze_document until
    the status is "complete".

    Returns:
        - status: "processing" or "complete" or "failed"
        - If complete: the actual analysis result
        - If processing: progress info and ETA if available
    """
    response = cache.get(ref_id)

    if response is None:
        return {
            "status": "not_found",
            "message": f"No task found with ref_id: {ref_id}",
        }

    if isinstance(response, AsyncTaskResponse):
        result = {
            "status": response.status.value,
            "ref_id": ref_id,
            "message": response.message,
        }
        if response.eta_seconds:
            result["eta_seconds"] = response.eta_seconds
        if response.progress:
            result["progress"] = {
                "current": response.progress.current,
                "total": response.progress.total,
            }
        return result

    if isinstance(response, CacheResponse):
        # Task is complete - return the cached result
        return {
            "status": "complete",
            "ref_id": ref_id,
            "result": response.preview,
        }

    # Unexpected response type
    return {
        "status": "unknown",
        "ref_id": ref_id,
        "response_type": str(type(response)),
    }


@mcp.tool()
async def quick_task(
    message: Annotated[
        str,
        Field(description="A message to echo back"),
    ],
) -> dict:
    """A quick task that completes within the timeout.

    This demonstrates that fast operations return results directly,
    not a processing status.
    """
    await asyncio.sleep(0.5)  # Quick - within 3s timeout
    return {
        "message": message,
        "processed": True,
        "note": "This completed synchronously because it was fast enough.",
    }


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run the MCP server."""
    parser = argparse.ArgumentParser(
        description="Async Timeout Demo MCP Server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8010,
        help="Port for SSE transport (default: 8010)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)",
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="sse",
            host=args.host,
            port=args.port,
        )


if __name__ == "__main__":
    main()
