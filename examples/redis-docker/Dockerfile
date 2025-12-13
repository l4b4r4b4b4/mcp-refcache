# Dockerfile for mcp-refcache Redis-based MCP servers
#
# Uses Chainguard secure base image with uv for fast dependency management.
# Minimal attack surface with fewer CVEs than standard Python images.

FROM cgr.dev/chainguard/python:latest-dev AS builder

# Set environment variables for uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy package files needed for installation
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/

# Create virtual environment and install all server dependencies
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Install with server extra (includes redis, fastmcp, langfuse)
RUN uv sync --frozen --extra server

# Copy example servers
COPY examples/redis-docker/*.py ./servers/

# =============================================================================
# Runtime stage - minimal Chainguard image
# =============================================================================
FROM cgr.dev/chainguard/python:latest

WORKDIR /app

# Copy virtual environment and app from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/servers /app/servers

# Set up virtual environment path
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Default environment variables (can be overridden)
ENV REDIS_HOST=valkey
ENV REDIS_PORT=6379
ENV REDIS_DB=0
ENV PYTHONUNBUFFERED=1

# Health check - use python instead of curl (not available in minimal image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${MCP_PORT:-8001}/sse')" || exit 1

# Default command - run calculator server
ENTRYPOINT ["python"]
CMD ["servers/calculator_server.py"]
