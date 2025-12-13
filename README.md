# mcp-refcache

**Reference-based caching for FastMCP servers with namespace isolation, access control, and private computation support.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.1.0-green.svg)](https://pypi.org/project/mcp-refcache/)
[![PyPI](https://img.shields.io/pypi/v/mcp-refcache.svg)](https://pypi.org/project/mcp-refcache/)

## Overview

`mcp-refcache` is a caching library designed for [FastMCP](https://github.com/jlowin/fastmcp) servers that solves critical challenges when building AI agent systems:

1. **Context Explosion Prevention** - Large API responses are stored by reference, returning only previews to agents
2. **Private Computation** - Agents can use values in computations without ever seeing the actual data
3. **Namespace Isolation** - Separate caches for public data, user sessions, and custom scopes
4. **Access Control** - Fine-grained permissions for both users and agents (CRUD + Execute)
5. **Cross-Tool Data Flow** - References act as a "data bus" between tools without exposing values

## The Problem

When an AI agent calls a tool that returns a large dataset (e.g., 500KB JSON), the entire response goes into the agent's context window, causing:

- **Token explosion** - Expensive and hits context limits
- **Distraction** - Agent gets overwhelmed with data it doesn't need
- **Security risks** - Sensitive data exposed in conversation history

## The Solution

```python
# Instead of returning 500KB of data...
{"users": [{"id": 1, "name": "...", ...}, ... 10000 more ...]}

# mcp-refcache returns a reference + preview
{
    "ref_id": "a1b2c3",
    "preview": "[User(id=1), User(id=2), ... and 9998 more]",
    "total_items": 10000,
    "namespace": "session:abc123"
}
```

The agent can then:
- **Paginate** through the data as needed
- **Pass the reference** to another tool (server resolves it automatically)
- **Control preview size** at server, tool, or per-call level
- **Use without seeing** - Execute permission enables blind computation

## Installation

```bash
# Core library (memory backend)
uv add mcp-refcache

# With Redis backend
uv add "mcp-refcache[redis]"

# With FastMCP integration (cache management tools)
uv add "mcp-refcache[mcp]"

# With SQLite backend (persistent, cross-tool sharing)
# No extra install needed - SQLite is in Python stdlib!

# Everything
uv add "mcp-refcache[all]"
```

<!-- Uncomment when repository is public
### From Git (for development)

```bash
# Latest main branch
uv add "mcp-refcache @ git+https://github.com/l4b4r4b4b4/mcp-refcache"

# Specific version
uv add "mcp-refcache @ git+https://github.com/l4b4r4b4b4/mcp-refcache@v0.1.0"

# Local development (editable)
uv add --editable ../mcp-refcache
```
-->

## Repository Structure

```
mcp-refcache/
├── src/mcp_refcache/     # Main library code
├── tests/                # Test suite (80%+ coverage)
├── examples/             # Git submodules with demos (optional)
│   ├── BundesMCP/       # Government API server example
│   ├── finquant-mcp/    # Financial data server example
│   └── fastmcp-template/ # Template for new servers
└── docs/                # Additional documentation
```

**Note:** Examples are git submodules and not included in the PyPI package. They demonstrate real-world usage but are optional.

### Using Examples

Examples are included in the source distribution but not installed with pip.
See the `examples/` directory in the source code for usage patterns.

<!-- Uncomment when repository is public
To use the example servers after cloning:

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/l4b4r4b4b4/mcp-refcache

# Or if already cloned:
git submodule update --init --recursive
```
-->

## Quick Start

```python
from fastmcp import FastMCP
from mcp_refcache import RefCache, Namespace, Permission

# Create cache with namespaces
cache = RefCache(
    namespaces=[
        Namespace.PUBLIC,
        Namespace.session("conv-123"),
        Namespace.user("user-456"),
    ]
)

mcp = FastMCP("MyServer")

@mcp.tool()
@cache.cached(namespace="session:conv-123")
async def get_large_dataset(query: str) -> dict:
    """Returns large dataset - agent sees only preview."""
    return await fetch_huge_data(query)  # 500KB response

@mcp.tool()
async def process_data(data_ref: str) -> dict:
    """Process data by reference - agent never sees raw data."""
    # Server resolves reference, agent only passed ref_id
    data = cache.resolve(data_ref)
    return {"processed": len(data["items"])}
```

## Core Concepts

### Preview Size Control

Preview size can be configured at three levels (highest priority first):

```python
from mcp_refcache import RefCache, PreviewConfig

# Level 1: Server default (lowest priority)
cache = RefCache(
    preview_config=PreviewConfig(max_size=1024)  # tokens or chars
)

# Level 2: Per-tool (medium priority)
@cache.cached(max_size=500)  # Override for this tool
async def generate_large_data(...):
    ...

# Level 3: Per-call (highest priority)
response = cache.get(ref_id, max_size=100)  # Override for this call
# Or via tool:
get_cached_result(ref_id, max_size=100)
```

This hierarchy allows:
- **Server admins** to set sensible defaults
- **Tool authors** to specify appropriate limits per tool
- **Agents** to request smaller/larger previews as needed

### Namespaces

Namespaces provide isolation and scoping for cached values:

| Namespace | Scope | Typical TTL | Use Case |
|-----------|-------|-------------|----------|
| `public` | Global, shared | Long (hours/days) | API responses, static data |
| `session:<id>` | Single conversation | Short (minutes) | Conversation context |
| `user:<id>` | User across sessions | Medium (hours) | User preferences, history |
| `user:<id>:session:<id>` | User's specific session | Short | Session-specific user data |
| `org:<id>` | Organization | Long | Shared org resources |
| `custom:<name>` | Arbitrary | Configurable | Project-specific needs |

### Permission Model

```python
from mcp_refcache import Permission, AccessPolicy

# Permission flags (can be combined with |)
Permission.READ      # Resolve reference to see value
Permission.WRITE     # Create new references
Permission.UPDATE    # Modify existing cached values
Permission.DELETE    # Remove/invalidate references
Permission.EXECUTE   # Use value in computation WITHOUT seeing it!
Permission.CRUD      # READ | WRITE | UPDATE | DELETE
Permission.FULL      # CRUD | EXECUTE
```

The **EXECUTE** permission enables private computation - agents can use values without reading them.

### Access Control

The access control system supports multiple layers:

```python
from mcp_refcache import AccessPolicy, DefaultActor, Permission

# Role-based defaults (backwards compatible)
policy = AccessPolicy(
    user_permissions=Permission.FULL,
    agent_permissions=Permission.READ | Permission.EXECUTE,
)

# With ownership - owner gets special permissions
policy = AccessPolicy(
    user_permissions=Permission.READ,
    owner="user:alice",
    owner_permissions=Permission.FULL,
)

# With explicit allow/deny lists
policy = AccessPolicy(
    user_permissions=Permission.FULL,
    denied_actors=frozenset({"agent:untrusted-*"}),
    allowed_actors=frozenset({"agent:trusted-service"}),
)

# Session binding - lock to specific session
policy = AccessPolicy(
    user_permissions=Permission.FULL,
    bound_session="session-abc123",
)
```

### Identity-Aware Actors

Actors represent users, agents, or system processes with optional identity:

```python
from mcp_refcache import DefaultActor

# Anonymous actors (backwards compatible with "user"/"agent" strings)
user = DefaultActor.user()
agent = DefaultActor.agent()

# Identified actors
alice = DefaultActor.user(id="alice", session_id="sess-123")
claude = DefaultActor.agent(id="claude-instance-1")

# Pattern matching for ACLs
alice.matches("user:alice")  # True
alice.matches("user:*")      # True (wildcard)
claude.matches("agent:claude-*")  # True (glob pattern)
```

### Private Computation

Agents can orchestrate computations on sensitive data without accessing it:

```python
# Store with EXECUTE-only for agents
cache.set(
    "user_secrets",
    {"ssn": "123-45-6789"},
    policy=AccessPolicy(
        user_permissions=Permission.FULL,
        agent_permissions=Permission.EXECUTE,  # Can use, can't see!
    )
)

# Tool resolves reference server-side
@mcp.tool()
def validate_identity(secrets_ref: str) -> bool:
    secrets = cache.resolve(secrets_ref)  # Server sees value
    return verify_ssn(secrets["ssn"])     # Agent never sees it
```

## Backends

mcp-refcache supports multiple storage backends for different deployment scenarios:

### Memory Backend (Default)

In-memory caching for testing and simple single-process use cases:

```python
from mcp_refcache import RefCache
from mcp_refcache.backends import MemoryBackend

cache = RefCache(
    name="my-cache",
    backend=MemoryBackend(),  # Default if not specified
)
```

**Use when:** Testing, simple scripts, single-process applications.

### SQLite Backend

Persistent caching with zero external dependencies. Enables cross-tool reference sharing between multiple MCP servers on the same machine:

```python
from mcp_refcache import RefCache
from mcp_refcache.backends import SQLiteBackend

# Default path: ~/.cache/mcp-refcache/cache.db
cache = RefCache(
    name="my-cache",
    backend=SQLiteBackend(),
)

# Custom path
cache = RefCache(
    name="my-cache",
    backend=SQLiteBackend("/path/to/cache.db"),
)

# Or via environment variable
# export MCP_REFCACHE_DB_PATH=/path/to/cache.db
```

**Features:**
- WAL mode for concurrent access
- Thread-safe with connection-per-thread model
- Cross-process reference sharing
- XDG-compliant default path
- Zero external dependencies (SQLite is in stdlib)

**Use when:** Single-machine deployments, multiple MCP servers sharing cache, persistent cache across restarts.

### Redis Backend

Distributed caching for multi-user, multi-machine scenarios:

```python
from mcp_refcache import RefCache
from mcp_refcache.backends import RedisBackend

# Connect to Redis/Valkey
cache = RefCache(
    name="my-cache",
    backend=RedisBackend(
        host="localhost",
        port=6379,
        password="your-password",  # Optional
    ),
)

# Or via URL
cache = RefCache(
    name="my-cache",
    backend=RedisBackend(url="redis://:password@localhost:6379/0"),
)
```

**Features:**
- Valkey/Redis compatible
- Native TTL via Redis expiration
- Connection pooling for thread safety
- Cross-server reference sharing
- Horizontal scaling ready

**Use when:** Multi-user deployments, distributed systems, Docker/Kubernetes environments.

#### Docker Deployment Example

See `examples/redis-docker/` for a complete Docker Compose setup with:
- Valkey (Redis-compatible) server
- Two MCP servers sharing the cache
- Health checks and proper dependencies

```bash
# Start the stack
cd examples/redis-docker
docker compose up -d

# Zed IDE configuration
# Add to .zed/settings.json:
{
  "context_servers": {
    "redis-calculator": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8001/sse"]
    },
    "redis-data-analysis": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8002/sse"]
    }
  }
}
```

Cross-tool workflow:
1. `redis-calculator`: `generate_primes(50)` → returns `ref_id`
2. `redis-data-analysis`: `analyze_data(ref_id)` → resolves from shared Redis cache
3. Both servers see the same cached data!

## API Reference

### RefCache

```python
cache = RefCache(
    name="my-cache",
    backend="memory",              # or "redis"
    default_namespace="public",
    default_ttl=3600,              # seconds
    max_size=10000,                # max entries
    preview_length=500,            # chars for preview
)
```

### Decorators

```python
@cache.cached(
    namespace="session:123",
    ttl=300,
    policy=AccessPolicy(...),
    preview_type="summary",        # or "truncate", "sample"
)
async def my_tool(...): ...
```

### The @cache.cached() Decorator

The decorator provides full MCP tool integration:

```python
@mcp.tool
@cache.cached(
    namespace="data",        # Namespace for isolation
    max_size=500,            # Per-tool preview size limit
    ttl=3600,                # TTL in seconds
    resolve_refs=True,       # Auto-resolve ref_ids in inputs
)
async def process_data(data: list[int]) -> list[float]:
    """Process data - accepts ref_ids, returns structured response."""
    return [x * 1.5 for x in data]

# Agent can call with ref_id from previous tool:
# process_data(data="calculator:abc123")
# Decorator resolves ref_id → actual list before execution
```

**Features:**
- **Pre-execution**: Recursively resolves ref_ids in all inputs
- **Post-execution**: Returns structured response with ref_id
- **Size-based**: Small results return full value, large return preview
- **Doc injection**: Adds caching info to tool docstrings automatically

## Roadmap

### v0.1.0 (Current)
- [x] Core reference-based caching with `@cache.cached()` decorator
- [x] Memory backend (thread-safe, TTL support)
- [x] SQLite backend (persistent, cross-tool sharing, zero dependencies)
- [x] Redis backend (distributed, multi-user, Docker-ready)
- [x] Preview generation (truncate, sample, paginate)
- [x] Namespace isolation (public, session, user, org, custom)
- [x] CRUD + EXECUTE permission model
- [x] Separate user/agent access control
- [x] TTL per namespace
- [x] FastMCP integration with auto-resolve
- [x] Langfuse observability (TracedRefCache)
- [x] Docker deployment example with Valkey

### v0.2.0 (Planned)
- [ ] MCP template (cookiecutter/copier for new servers)
- [ ] Time series backend (InfluxDB, TimescaleDB for financial data)
- [ ] Redis Cluster/Sentinel support
- [ ] Metrics/observability hooks (Prometheus, OpenTelemetry)
- [ ] Reference metadata (tags, descriptions)
- [ ] Audit logging (who accessed what, when)

### v0.3.0
- [ ] Lazy evaluation (compute-on-first-access references)
- [ ] Derived references (`ref.field.subfield` access)
- [ ] Encryption at rest for sensitive values
- [ ] Reference aliasing (human-readable names)
- [ ] Webhooks/events (notify on access, expiry)
- [ ] Distributed locking (Redis)

### Future
- [ ] Schema validation for cached values
- [ ] Import/export for backup and migration
- [ ] Rate limiting per reference
- [ ] Compression for large values
- [ ] Multi-region Redis support

## Development

```bash
# Install dependencies
uv sync

# Enter nix dev shell (optional, recommended)
nix develop

# Run tests
uv run pytest --cov

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy src/
```

### IDE Setup (Zed)

The project includes Zed IDE configuration in `.zed/settings.json` with:

- **Pyright** LSP with strict type checking
- **Ruff** for format-on-save
- **MCP Context Servers** for AI-assisted development:
  - `mcp-nixos` - NixOS/Home Manager options lookup
  - `pypi-query-mcp-server` - PyPI package intelligence
  - `context7` - Up-to-date framework documentation

To use the MCP servers, ensure you have `uvx` and `npx` available (included in the nix dev shell).

## Integration with FastMCP Caching Middleware

`mcp-refcache` is **complementary** to FastMCP's built-in `ResponseCachingMiddleware`:

| Feature | FastMCP Middleware | mcp-refcache |
|---------|-------------------|--------------|
| **Purpose** | Reduce API calls (TTL cache) | Manage context & permissions |
| **Returns** | Full cached response | Reference + preview |
| **Pagination** | ❌ | ✅ |
| **Access Control** | ❌ | ✅ (User + Agent) |
| **Private Compute** | ❌ | ✅ (EXECUTE permission) |
| **Namespaces** | ❌ | ✅ |

Use both together:
- FastMCP middleware: Cache expensive API calls
- mcp-refcache: Manage what agents see and can do

## Project Status

### Current Version: 0.0.1 (Alpha)

This is an early alpha release. The core API is functional but may change based on feedback. We're working toward a stable 1.0.0 release.

**Stability:** Core caching and access control features are stable. Preview strategies and FastMCP integration may see refinements.

**Production Use:** Suitable for experimentation and testing. For production use, pin to a specific version and review changes carefully when upgrading.

### Roadmap

See the [Roadmap](#roadmap) section above for planned features in upcoming releases.

### Community
## Support

- **PyPI:** [pypi.org/project/mcp-refcache](https://pypi.org/project/mcp-refcache/)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

```bash
# Install for development
uv sync

# Run tests
uv run pytest --cov

# Lint and format
uv run ruff check . --fix
uv run ruff format .
```
### Code Quality Standards

- **Test Coverage:** Minimum 80% (currently meeting this requirement)
- **Type Safety:** Full type annotations with mypy strict mode
- **Code Style:** Ruff for linting and formatting (PEP 8 compliant)
- **Documentation:** Docstrings for all public APIs (Google style)
