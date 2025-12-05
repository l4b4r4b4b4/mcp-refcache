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