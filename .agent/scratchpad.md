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

### ✅ Completed - Scaffolding Phase
- [x] Create git repo at `~/code/github.com/l4b4r4b4b4/mcp-refcache`
- [x] Set up nix flake dev environment
- [x] Initialize uv project with `uv init --lib`
- [x] Create pyproject.toml with proper metadata and dependencies
- [x] Create comprehensive README.md with roadmap
- [x] Create CONTRIBUTING.md with code conventions
- [x] Configure ruff, mypy, bandit in pyproject.toml
- [x] Update `.zed/settings.json` for this project
- [x] Add MCP servers (pypi, context7) to Zed config

### ✅ Completed - Clean Library Skeleton
- [x] Move BundesMCP cache files to `archive/bundesmcp-cache/` (gitignored)
- [x] Create `permissions.py` with Permission enum and AccessPolicy
- [x] Create `models.py` with CacheReference, CacheResponse, PaginatedResponse, PreviewConfig
- [x] Create `__init__.py` with public API exports
- [x] Update tests for new skeleton (25 tests passing)
- [x] All linting passes (ruff check, ruff format)

### 🔧 In Progress - Core Implementation
- [ ] Implement RefCache class (main cache interface)
- [ ] Implement memory backend
- [ ] Implement context limiting (token/char measurement)
- [ ] Implement preview strategies (truncate, paginate, sample)
- [ ] Add namespace support
- [ ] Add FastMCP integration (optional dependency)

## Architecture

### File Structure (Current)
```
src/mcp_refcache/
├── __init__.py          # Public API exports
├── permissions.py       # Permission enum, AccessPolicy
├── models.py            # CacheReference, CacheResponse, PaginatedResponse, PreviewConfig
└── py.typed             # PEP 561 marker

archive/bundesmcp-cache/ # Old code for reference (gitignored)
├── cache.py
├── cache_toolset.py
├── redis_cache.py
└── return_types.py
```

### File Structure (Planned)
```
src/mcp_refcache/
├── __init__.py          # Public API exports
├── permissions.py       # Permission enum, AccessPolicy ✅
├── models.py            # Pydantic models ✅
├── cache.py             # RefCache class (main interface)
├── context.py           # Context limiting (token/char measurement)
├── preview.py           # Preview strategies (truncate, paginate, sample)
├── namespaces.py        # Namespace hierarchy
├── backends/
│   ├── __init__.py
│   ├── base.py          # Backend protocol
│   └── memory.py        # In-memory backend
└── tools/
    ├── __init__.py
    └── mcp_tools.py     # FastMCP integration (optional)
```

### Context Limiting (Two Orthogonal Settings)

**1. Size Measurement** (how do we count?)
| Mode | Description |
|------|-------------|
| `token` (default) | Count tokens for LLM context accuracy |
| `character` | Simple char count, faster |

**2. Limiting Strategy** (how do we shrink?)
| Strategy | Description |
|----------|-------------|
| `sample` (default) | Pick N evenly-spaced items, structured output |
| `paginate` | Split into pages, each page ≤ limit |
| `truncate` | Stringify and cut (escape hatch for plain text) |

**Key insight:** Preview should be **structured data**, not stringified truncation!

### Permission Model
```python
class Permission(Flag):
    NONE = 0
    READ = auto()      # Resolve reference to see value
    WRITE = auto()     # Create new references
    UPDATE = auto()    # Modify existing cached values
    DELETE = auto()    # Remove/invalidate references
    EXECUTE = auto()   # Use value WITHOUT seeing it (blind compute)
    
    CRUD = READ | WRITE | UPDATE | DELETE
    FULL = CRUD | EXECUTE
```

### Namespace Hierarchy
```
public                          # Global, anyone can read
├── session:<session_id>        # Conversation-scoped
├── user:<user_id>              # User-scoped (across sessions)
│   └── session:<session_id>    # User's session-specific
└── custom:<namespace>          # Arbitrary custom namespaces
```

## Roadmap Reference

### v0.0.1 (Current)
- Core caching with RefCache class
- Memory backend
- Namespaces and permissions
- Context limiting (token/char + truncate/paginate/sample)
- EXECUTE for private compute

### v0.0.2
- Redis backend
- Audit logging
- Value transformations
- Permission delegation

### v0.0.3
- Lazy evaluation
- Derived references
- Encryption at rest

## Next Steps

1. **Push initial skeleton to GitHub**
2. **Implement RefCache class** - main cache interface
3. **Implement memory backend** - simple dict-based storage
4. **Implement context limiting** - token counting, preview generation
5. **Add namespace support** - isolation and hierarchy
6. **Add FastMCP integration** - optional decorator and tools

## Notes

- EXECUTE permission is the killer feature - enables blind computation
- Preview should be **structured** (actual objects), not stringified
- Size limit applies to the **output** of whatever strategy is chosen
- Complementary to FastMCP's ResponseCachingMiddleware (different purposes)
- Python >=3.10 to match FastMCP compatibility