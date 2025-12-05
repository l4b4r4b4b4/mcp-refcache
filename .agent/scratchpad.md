# mcp-refcache Development Scratchpad

## Project Overview

Reference-based caching library for FastMCP servers. Enables:
- Context management via previews instead of full payloads
- Hidden computation - server-side ops on values agents see only by reference
- Namespace isolation (public, session, user, custom)
- Access control layer - separate permissions for users and agents
- CRUD + EXECUTE permissions (EXECUTE = use without seeing!)
- Cross-tool data flow - references as data bus between tools

## Current Session: Core Implementation Phase

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

### ✅ Completed - Phase 1: Core Implementation

#### Backend Protocol & Memory Backend ✅
- [x] `src/mcp_refcache/backends/base.py` - CacheEntry dataclass + CacheBackend Protocol
- [x] `src/mcp_refcache/backends/memory.py` - Thread-safe MemoryBackend with TTL support
- [x] `src/mcp_refcache/backends/__init__.py` - Public exports
- [x] `tests/test_backends.py` - 27 tests covering all backend operations

#### RefCache Class ✅
- [x] `src/mcp_refcache/cache.py` - Full RefCache implementation (~570 lines)
  - `set()` - Store values with namespace, policy, TTL
  - `get()` - Get preview with pagination support
  - `resolve()` - Get full value (permission checked)
  - `delete()` - Remove entries (permission checked)
  - `exists()` - Check if reference exists
  - `clear()` - Clear by namespace or all
  - `@cached` decorator - For caching function results (sync + async)
- [x] `tests/test_refcache.py` - 58 tests covering all RefCache operations
- [x] Updated `src/mcp_refcache/__init__.py` - Export RefCache and backends

#### Test Results
- **110 tests passing**
- **90% code coverage**
- All linting passes (ruff check, ruff format)

#### Key Implementation Details
1. **Actor-based permissions**: `actor="user"` or `actor="agent"` determines permission set
2. **Reference ID format**: `{cache_name}:{short_hash}` - globally unique, compact
3. **Preview generation**: Basic sampling for lists/dicts, truncation for strings
4. **Thread-safe**: MemoryBackend uses `threading.RLock`
5. **Flexible TTL**: Per-entry or cache-level defaults

### 🔧 Remaining Tasks - Phase 2
- [ ] Implement context limiting (`context.py`) - token counting with tiktoken
- [ ] Implement preview strategies (`preview.py`) - adaptive sampling with step size
- [ ] Add namespace hierarchy (`namespaces.py`) - inheritance and validation
- [ ] Add FastMCP integration (`tools/`) - optional dependency

## Architecture

### File Structure (Current)
```
src/mcp_refcache/
├── __init__.py          # Public API exports
├── permissions.py       # Permission enum, AccessPolicy ✅
├── models.py            # Pydantic models ✅
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
├── cache.py             # RefCache class (main interface) ✅
├── context.py           # Context limiting (token/char measurement)
├── preview.py           # Preview strategies (truncate, paginate, sample)
├── namespaces.py        # Namespace hierarchy
├── backends/
│   ├── __init__.py      # Backend exports ✅
│   ├── base.py          # Backend protocol ✅
│   └── memory.py        # In-memory backend ✅
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

## Notes

- EXECUTE permission is the killer feature - enables blind computation
- Preview should be **structured** (actual objects), not stringified
- Size limit applies to the **output** of whatever strategy is chosen
- Complementary to FastMCP's ResponseCachingMiddleware (different purposes)
- Python >=3.10 to match FastMCP compatibility
- Reference archived BundesMCP code in `archive/bundesmcp-cache/` for implementation ideas
- Archived code also copied to `.agent/files/tmp/session/` for easy reference

## Session Log

### 2024-XX-XX: Phase 1 Complete
- Implemented CacheBackend Protocol and CacheEntry dataclass
- Implemented thread-safe MemoryBackend with TTL support
- Implemented RefCache with full CRUD operations
- Implemented @cached decorator for sync and async functions
- 110 tests passing, 90% coverage
- Updated .rules for Python library context (removed FastAPI/microservice specifics)