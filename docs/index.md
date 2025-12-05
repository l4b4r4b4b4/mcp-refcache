# mcp-refcache Documentation

Welcome to the mcp-refcache documentation.

## Overview

mcp-refcache is a reference-based caching library for FastMCP servers that provides:

- **Context Explosion Prevention** - Large responses return previews, not full data
- **Private Computation** - Agents can use values without seeing them (EXECUTE permission)
- **Namespace Isolation** - Separate caches for public, session, user, and custom scopes
- **Access Control** - Fine-grained CRUD + EXECUTE permissions for users and agents

## Quick Links

- [Installation](installation.md)
- [Quick Start](quickstart.md)
- [API Reference](api/index.md)
- [Concepts](concepts/index.md)
  - [Namespaces](concepts/namespaces.md)
  - [Permissions](concepts/permissions.md)
  - [Private Computation](concepts/private-computation.md)
- [Contributing](../CONTRIBUTING.md)
- [Changelog](../CHANGELOG.md)

## Installation

```bash
# Core library
uv add mcp-refcache

# With Redis backend
uv add "mcp-refcache[redis]"

# With FastMCP integration
uv add "mcp-refcache[mcp]"

# Everything
uv add "mcp-refcache[all]"
```

## Basic Usage

```python
from mcp_refcache import RefCache, Permission, AccessPolicy

# Create cache
cache = RefCache(name="my-cache")

# Store a value
ref = cache.set("api-response", large_data)

# Agent sees only: {"ref_id": "abc123", "preview": "[truncated]", ...}
# Full data accessible via: cache.get(ref.ref_id)
```

## Documentation Status

> **Note**: This documentation is under construction. 
> See the [README](../README.md) for current usage information.

## License

MIT License - see [LICENSE](../LICENSE) for details.