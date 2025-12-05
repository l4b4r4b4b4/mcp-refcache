# mcp-refcache Development Scratchpad

## Project Overview

Reference-based caching library for FastMCP servers. Enables:
- Context management via previews instead of full payloads
- Hidden computation - server-side ops on values agents see only by reference
- Namespace isolation (public, session, user, custom)
- Access control layer - separate permissions for users and agents
- CRUD + EXECUTE permissions (EXECUTE = use without seeing!)
- Cross-tool data flow - references as data bus between tools

## Current Session: v0.0.1 Implementation

### Completed
- [x] Create git repo at `~/code/github.com/l4b4r4b4b4/mcp-refcache`
- [x] Set up nix flake dev environment
- [x] Copy cache source files from BundesMCP
- [x] Initialize uv project with `uv init --lib`
- [x] Create pyproject.toml with proper metadata and dependencies
- [x] Create comprehensive README.md with roadmap

### In Progress
- [ ] Clean up imports in source files (remove BundesMCP-specific deps)
- [ ] Create proper `__init__.py` with public API exports
- [ ] Implement namespace hierarchy
- [ ] Implement Permission enum and AccessPolicy
- [ ] Refactor redis_cache.py to remove `system_0.config` dependency

### TODO: v0.0.1 Features
- [ ] Core reference-based caching (exists, needs cleanup)
- [ ] Memory backend with disk persistence (exists)
- [ ] Preview generation - truncate, sample, paginate (exists)
- [ ] Namespace support: public, session, user, custom
- [ ] Permission model: READ, WRITE, UPDATE, DELETE, EXECUTE
- [ ] Separate user/agent access control
- [ ] TTL per namespace
- [ ] Reference metadata (tags, descriptions)
- [ ] FastMCP integration tools (optional dependency)

## Architecture

### Namespace Hierarchy
```
public                          # Global, anyone can read
├── session:<session_id>        # Conversation-scoped
├── user:<user_id>              # User-scoped (across sessions)
│   └── session:<session_id>    # User's session-specific
├── org:<org_id>                # Organization-scoped
│   └── user:<user_id>          # Org member's private
│   └── project:<project_id>    # Project-scoped within org
└── custom:<namespace>          # Arbitrary custom namespaces
```

### Permission Model
```python
class Permission(Flag):
    NONE = 0
    READ = auto()      # Resolve reference to see value
    WRITE = auto()     # Create new references
    UPDATE = auto()    # Modify existing cached values
    DELETE = auto()    # Remove/invalidate references
    EXECUTE = auto()   # Use value WITHOUT seeing it (private compute!)

class AccessPolicy:
    user_permissions: Permission    # What human user can do
    agent_permissions: Permission   # What AI agent can do
```

### Files to Refactor

| File | Status | Changes Needed |
|------|--------|----------------|
| `return_types.py` | ✅ Clean | No external deps |
| `cache.py` | 🔧 Needs work | Fix relative imports, add namespaces/permissions |
| `redis_cache.py` | 🔧 Needs work | Remove `system_0.config`, make Redis URL configurable |
| `cache_toolset.py` | 🔧 Needs work | Fix imports, make FastMCP optional |
| `__init__.py` | 🆕 Create | Define public API exports |

## Roadmap Reference

### v0.0.1 (Current)
- Core caching, namespaces, permissions, EXECUTE for private compute

### v0.0.2
- Audit logging, value transformations, delegation, expiring permissions

### v0.0.3
- Lazy evaluation, derived references, encryption, aliasing

## Notes

- EXECUTE permission is the killer feature - enables blind computation
- Complementary to FastMCP's ResponseCachingMiddleware (different purposes)
- Python >=3.10 to match FastMCP compatibility
- Optional deps: redis, fastmcp (mcp tools)

---

## Zed IDE Setup

### Current Status
- [x] Terminal integration working
- [ ] Update `.zed/settings.json` for this project (copied from BundesMCP, needs cleanup)

### Settings.json Changes Needed
1. **Remove**: TypeScript/TSX settings (not needed for Python library)
2. **Update**: PYTHONPATH to `./src` instead of `apps/api`
3. **Update**: Pyright pythonPath to `.venv/bin/python`
4. **Update**: extraPaths to `["src"]`
5. **Remove**: BundesMCP context server (not relevant)
6. **Keep**: nixos, sqlite MCP servers

---

## MCP Server Research (2025-12-05)

### Recommended MCP Servers for Python Library Development

#### 🔴 HIGH PRIORITY - Immediate Value

| Server | Description | Install |
|--------|-------------|---------|
| **[mcp-nixos](https://github.com/utensils/mcp-nixos)** | NixOS/Home Manager/nix-darwin options lookup - prevents AI hallucinations | `uvx mcp-nixos` ✅ Already installed |
| **[pypi-query-mcp-server](https://github.com/loonghao/pypi-query-mcp-server)** | PyPI package intelligence - dependency analysis, version tracking, metadata | `uvx pypi-query-mcp-server` |
| **[context7](https://github.com/upstash/context7)** | Up-to-date framework docs for LLMs - FastMCP, Pydantic, etc. | `npx -y @upstash/context7-mcp` |

#### 🟡 MEDIUM PRIORITY - Nice to Have

| Server | Description | Install |
|--------|-------------|---------|
| **[mcp-package-version](https://github.com/sammcj/mcp-package-version)** | Latest stable package versions when writing code | `npx -y mcp-package-version` |
| **[mcp-package-docs](https://github.com/sammcj/mcp-package-docs)** | Access package documentation across languages (archived but useful) | `npx @anthropic/package-docs` |
| **[mcp-redis](https://github.com/redis/mcp-redis)** | Official Redis MCP - manage/search data in Redis (relevant for redis_cache.py) | `uvx mcp-redis` |

#### 🟢 LOW PRIORITY - Future Consideration

| Server | Description | Notes |
|--------|-------------|-------|
| **[mcp-debugpy](https://github.com/markomanninen/mcp-debugpy)** | AI-assisted Python debugging | Good for complex debugging |
| **[grafana-mcp](https://github.com/grafana/mcp-grafana)** | Grafana integration | If we add monitoring |
| **[sentry-mcp](https://github.com/getsentry/sentry-mcp)** | Error tracking | If we add error tracking |

### Proposed `.zed/settings.json` Update

```json
{
  "$schema": "zed://schemas/settings",
  "terminal": {
    "env": {
      "PYTHONPATH": "./src"
    }
  },
  "lsp": {
    "pyright": {
      "settings": {
        "python.pythonPath": ".venv/bin/python",
        "python.analysis": {
          "extraPaths": ["src"],
          "diagnosticMode": "workspace",
          "typeCheckingMode": "strict"
        }
      }
    }
  },
  "languages": {
    "Python": {
      "format_on_save": {
        "external": {
          "command": "ruff",
          "arguments": ["format", "-"]
        }
      },
      "language_servers": ["pyright"]
    }
  },
  "context_servers": {
    "nixos": {
      "command": "uvx",
      "args": ["mcp-nixos"]
    },
    "pypi": {
      "command": "uvx",
      "args": ["pypi-query-mcp-server"]
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

### Action Items
- [ ] User approval for settings.json update
- [ ] User approval for MCP server additions (pypi, context7)
- [ ] Test new MCP servers work correctly

---

## Next Session: Immediate Actions

### 1. Update `.zed/settings.json` (approved by user)
Apply the proposed settings.json from the MCP Server Research section above.

### 2. Start Code Refactoring
Priority order:
1. **`src/mcp_refcache/__init__.py`** - Create public API exports
2. **`src/mcp_refcache/cache.py`** - Fix imports, add Permission enum, AccessPolicy
3. **`src/mcp_refcache/redis_cache.py`** - Remove `system_0.config` dependency, make configurable
4. **`src/mcp_refcache/cache_toolset.py`** - Make FastMCP optional import

### 3. Run Tests & Linting
```bash
uv sync
ruff check . --fix && ruff format .
pytest
```

### Starting Prompt for New Session
See below for copy-paste prompt.