# mcp-refcache

**Reference-based caching for FastMCP servers with namespace isolation, access control, and private computation support.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.0.1-green.svg)](https://github.com/l4b4r4b4b4/mcp-refcache)

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
- **Pass the reference** to another tool (server resolves it)
- **Use without seeing** - Execute permission enables blind computation

## Installation

```bash
# Core library (memory backend)
uv add mcp-refcache

# With Redis backend
uv add "mcp-refcache[redis]"

# With FastMCP integration (cache management tools)
uv add "mcp-refcache[mcp]"

# Everything
uv add "mcp-refcache[all]"
```

### From Git (for development)

```bash
# Latest main branch
uv add "mcp-refcache @ git+https://github.com/l4b4r4b4b4/mcp-refcache"

# Specific version
uv add "mcp-refcache @ git+https://github.com/l4b4r4b4b4/mcp-refcache@v0.0.1"

# Local development (editable)
uv add --editable ../mcp-refcache
```

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

Namespace hierarchy enables **permission inheritance** - child namespaces inherit parent restrictions unless explicitly overridden.

### Permission Model

```python
from mcp_refcache import Permission, AccessPolicy

class Permission(Flag):
    NONE = 0
    READ = auto()      # Resolve reference to see value
    WRITE = auto()     # Create new references
    UPDATE = auto()    # Modify existing cached values
    DELETE = auto()    # Remove/invalidate references
    EXECUTE = auto()   # Use value in computation WITHOUT seeing it!
```

The **EXECUTE** permission is the key to private computation:

```python
# Agent can use this value but cannot read it
secret_policy = AccessPolicy(
    user_permissions=Permission.FULL,           # User sees everything
    agent_permissions=Permission.EXECUTE,       # Agent can use, not read!
)

# Store API key that agent can use but never see
cache.set(
    "api_key", 
    "sk-secret-123", 
    namespace="user:456",
    policy=secret_policy
)
```

### Access Control

Every cached value has separate permissions for **users** and **agents**:

```python
# User can read/write, agent can only execute (blind computation)
cache.set(
    key="user_secrets",
    value={"ssn": "123-45-6789", "credit_card": "..."},
    policy=AccessPolicy(
        user_permissions=Permission.READ | Permission.UPDATE,
        agent_permissions=Permission.EXECUTE,  # Can compute, can't see!
    )
)

# Agent tries to read - denied!
cache.get("user_secrets", accessor=Agent("gpt-4"))  # Raises AccessDenied

# Agent passes reference to tool - works! (EXECUTE permission)
@mcp.tool()
def validate_identity(secrets_ref: str) -> bool:
    secrets = cache.resolve(secrets_ref, permission=Permission.EXECUTE)
    return verify_ssn(secrets["ssn"])  # Server uses value, agent never sees it
```

### Private Computation

The killer feature: agents can orchestrate computations on sensitive data without ever accessing it:

```python
# 1. User uploads sensitive document
doc_ref = cache.store(
    sensitive_document,
    namespace="user:123",
    policy=AccessPolicy(
        user_permissions=Permission.FULL,
        agent_permissions=Permission.EXECUTE,  # Blind execution only
    )
)

# 2. Agent calls analysis tool with reference
# Agent sees: {"ref_id": "abc123", "preview": "[REDACTED - EXECUTE only]"}
# Agent calls: analyze_document(doc_ref="abc123")

# 3. Tool resolves reference server-side and processes
@mcp.tool()
def analyze_document(doc_ref: str) -> dict:
    doc = cache.resolve(doc_ref, permission=Permission.EXECUTE)
    # Full document available to tool, never sent to agent
    return {"summary": summarize(doc), "entities": extract_entities(doc)}
```

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

### Return Types

```python
from mcp_refcache import ReturnOptions, ValueReturnType

# Control what agent sees
options = ReturnOptions(
    value_type=ValueReturnType.PREVIEW,  # or FULL, REFERENCE_ONLY
    include_metadata=True,
    pagination=PaginationParams(page=1, page_size=20),
)
```

## Roadmap

### v0.0.1 (Current)
- [x] Core reference-based caching
- [x] Memory backend with disk persistence
- [x] Preview generation (truncate, sample, paginate)
- [x] Basic namespace support (public, session, user, custom)
- [x] CRUD + EXECUTE permission model
- [x] Separate user/agent access control
- [x] TTL per namespace
- [x] Reference metadata (tags, descriptions)
- [x] FastMCP integration tools

### v0.0.2
- [ ] Audit logging (who accessed what, when)
- [ ] Value transformations (redacted views)
- [ ] Permission delegation (user grants agent temporary access)
- [ ] Expiring permissions (time-bounded access)
- [ ] Redis backend improvements
- [ ] Bulk operations (batch resolve, batch permission check)

### v0.0.3
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
# Clone the repo
git clone https://github.com/l4b4r4b4b4/mcp-refcache
cd mcp-refcache

# Enter nix dev shell (recommended)
nix develop

# Or use uv directly
uv sync

# Run tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy src/
```

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

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.