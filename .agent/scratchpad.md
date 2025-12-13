# mcp-refcache Development Scratchpad

## Current Status: Pre-Release Feature Development 🔧

**Last Updated**: Pre-Release Feature Planning

### v0.0.1 Feature Checklist

| Feature | Status | Tests |
|---------|--------|-------|
| Core RefCache class | ✅ Done | 586 tests |
| Memory backend (thread-safe) | ✅ Done | TTL support |
| Namespaces (public, session, user, custom) | ✅ Done | Full isolation |
| Access control (Actor, Permission, ACLs) | ✅ Done | User/Agent/System |
| Context limiting (token/char) | ✅ Done | tiktoken + HF |
| Preview strategies (sample/paginate/truncate) | ✅ Done | PreviewGenerator |
| EXECUTE permission (private compute) | ✅ Done | Blind computation |
| `@cache.cached()` decorator | ✅ Done | Ref resolution |
| FastMCP integration helpers | ✅ Done | `cache_instructions()` |
| Langfuse observability | ✅ Done | TracedRefCache wrapper |

**Test Results**: 586 passed, 3 skipped (optional transformers dep)

### NOT in v0.0.1 (Move to v0.0.2)
- Disk persistence for memory backend
- Reference metadata (tags, descriptions)
- Redis/Valkey backend
- Audit logging

---

## Current Session: Pre-Release Feature Development

### User Decision: Add Key Features Before v0.0.1 Release

Before going public, implement two critical features:

1. **Automatic Type Extension for FastMCP Tools**
   - Problem: Currently, decorated tools need manual type annotations to match cache response structure
   - Solution: Decorator should automatically transform return type annotations
   - Impact: Better MCP client experience (no schema complaints)

2. **SQLite Backend for Cross-Process Caching**
   - Problem: Memory backend only works within a single process
   - Solution: Implement SQLite backend before jumping to Valkey
   - Benefits:
     - Cross-process caching (file-based)
     - No external service needed
     - Persistent storage
     - Natural stepping stone to Valkey
     - Easy testing

3. **Test Coverage Adjustment**
   - Update `pyproject.toml`: Change `fail_under = 80` to `fail_under = 73`

4. **Example .env File**
   - Create `.env.example` for examples that need configuration

### Implementation Plan

#### Task 1: Automatic Type Extension for @cache.cached() Decorator

**Current Behavior:**
```python
@mcp.tool
@cache.cached(namespace="data")
async def generate_sequence(count: int) -> list[int]:
    """Generate sequence."""
    return list(range(count))
```

The decorated function returns `dict[str, Any]` (CacheResponse structure), but the type annotation says `list[int]`. This causes MCP schema mismatches.

**Desired Behavior:**
```python
@mcp.tool
@cache.cached(namespace="data")
async def generate_sequence(count: int) -> list[int]:
    """Generate sequence."""
    return list(range(count))
```

The decorator should automatically transform the return type to `dict[str, Any]` or ideally a `CacheResponse` TypedDict so MCP clients see the correct schema.

**Implementation Approach:**
1. Use `typing.get_type_hints()` to extract original return type
2. Store original type in wrapper metadata
3. Update wrapper's `__annotations__` to reflect actual return type
4. Optionally: Create a `CacheResponse` TypedDict for better typing

**Files to Modify:**
- `src/mcp_refcache/cache.py` - Update `cached()` decorator
- `src/mcp_refcache/models.py` - Add `CacheResponseDict` TypedDict
- `tests/test_cache.py` - Add tests for type annotation transformation
- `examples/mcp_server.py` - Remove manual type annotations (should work automatically)

**Edge Cases:**
- Generic return types (List[T], Dict[K, V])
- Union types
- Optional types
- Complex nested types

#### Task 2: SQLite Backend Implementation

**Requirements:**
- Implement `CacheBackend` protocol with SQLite storage
- Thread-safe operations (sqlite3 is not thread-safe by default)
- TTL support with automatic expiration
- Efficient ref_id lookups
- Namespace isolation
- Cross-process compatibility

**Schema Design:**
```sql
CREATE TABLE cache_entries (
    ref_id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL,
    metadata_json TEXT,
    UNIQUE(namespace, key)
);

CREATE INDEX idx_namespace ON cache_entries(namespace);
CREATE INDEX idx_expires_at ON cache_entries(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_namespace_key ON cache_entries(namespace, key);
```

**Implementation Strategy:**
1. Create `src/mcp_refcache/backends/sqlite.py`
2. Use `threading.local()` for connection-per-thread
3. Use WAL mode for better concurrency
4. Implement background expiration cleanup (optional)
5. JSON serialization for values and policies

**Files to Create/Modify:**
- `src/mcp_refcache/backends/sqlite.py` - New SQLite backend
- `src/mcp_refcache/backends/__init__.py` - Export SqliteBackend
- `tests/test_backends.py` - Add SQLite backend tests
- `tests/conftest.py` - Add sqlite backend fixture
- `README.md` - Document SQLite backend usage
- `pyproject.toml` - No new dependencies (sqlite3 is in stdlib)

**Example Usage:**
```python
from mcp_refcache import RefCache
from mcp_refcache.backends import SqliteBackend

# In-memory SQLite (testing)
cache = RefCache(backend=SqliteBackend(":memory:"))

# File-based (production)
cache = RefCache(backend=SqliteBackend("cache.db"))

# With custom settings
backend = SqliteBackend(
    path="cache.db",
    timeout=5.0,
    check_same_thread=False,  # Allow cross-thread access
    isolation_level="DEFERRED",
)
cache = RefCache(backend=backend)
```

#### Task 3: Update Test Coverage Requirement

**Change:**
```toml
# pyproject.toml
[tool.coverage.report]
fail_under = 73  # Changed from 80
```

**Justification:**
- Current coverage: 91% (well above requirement)
- Lowering minimum allows flexibility during rapid development
- Still maintains high coverage standards

#### Task 4: Create Example .env File

**Create `.env.example` in repository root:**
```bash
# mcp-refcache Example Configuration

# Cache Backend Settings
# CACHE_BACKEND=memory|sqlite|redis
CACHE_BACKEND=memory

# SQLite Backend (when CACHE_BACKEND=sqlite)
# CACHE_SQLITE_PATH=cache.db
# CACHE_SQLITE_PATH=:memory:  # For testing

# Redis Backend (when CACHE_BACKEND=redis)
# REDIS_URL=redis://localhost:6379/0

# Preview Configuration
# CACHE_PREVIEW_MAX_SIZE=1024
# CACHE_PREVIEW_STRATEGY=sample|truncate|paginate

# Namespace Configuration
# CACHE_DEFAULT_NAMESPACE=public
# CACHE_DEFAULT_TTL=3600

# FastMCP Server Settings (for examples/)
# MCP_SERVER_NAME=MyServer
# MCP_SERVER_TRANSPORT=stdio|sse
# MCP_SERVER_PORT=8000

# Example-Specific Settings
# API_KEY=your_api_key_here
# LOG_LEVEL=INFO
```

**Also create `examples/.env.example`:**
```bash
# Example MCP Server Configuration

# Server Settings
SERVER_NAME=Scientific Calculator
SERVER_TRANSPORT=stdio
SERVER_PORT=8000

# Cache Settings
CACHE_BACKEND=sqlite
CACHE_SQLITE_PATH=examples/cache.db
CACHE_MAX_SIZE=2000

# Logging
LOG_LEVEL=INFO
```

### Implementation Timeline

**Phase 1: Type Extension (2-3 hours)**
- [ ] Create `CacheResponseDict` TypedDict in models.py
- [ ] Update `cached()` decorator to transform type annotations
- [ ] Add comprehensive tests for type transformation
- [ ] Update examples to rely on automatic typing
- [ ] Test with FastMCP to ensure MCP schema is correct

**Phase 2: SQLite Backend (3-4 hours)**
- [ ] Implement `SqliteBackend` class
- [ ] Add thread-safety mechanisms
- [ ] Implement full `CacheBackend` protocol
- [ ] Write comprehensive backend tests
- [ ] Add integration tests with `RefCache`
- [ ] Document usage in README
- [ ] Add example using SQLite backend

**Phase 3: Configuration & Cleanup (1 hour)**
- [ ] Update test coverage requirement to 73%
- [ ] Create `.env.example` files
- [ ] Add .env to .gitignore (already there)
- [ ] Update documentation

**Phase 4: Testing & Validation (1 hour)**
- [ ] Run full test suite
- [ ] Test examples with new features
- [ ] Verify SQLite backend works cross-process
- [ ] Check MCP client compatibility with type extensions

**Total Estimated Time: 7-9 hours**

### Success Criteria

**Type Extension:**
- ✅ Decorated functions automatically get correct return type
- ✅ MCP clients see proper schema (no complaints)
- ✅ Original type hints preserved in metadata
- ✅ Works with async and sync functions
- ✅ Examples run without manual type annotations

**SQLite Backend:**
- ✅ Implements full `CacheBackend` protocol
- ✅ Thread-safe operations
- ✅ Cross-process compatibility verified
- ✅ TTL and expiration work correctly
- ✅ Performance acceptable for typical use cases
- ✅ >= 80% test coverage for new code

**Overall:**
- ✅ All existing tests pass
- ✅ New tests pass with >= 73% total coverage
- ✅ Documentation updated
- ✅ Examples work with new features
- ✅ Ready for public v0.0.1 release

---

## Previous: Open Source Release Preparation

### Overview

Preparing mcp-refcache for public release on GitHub and PyPI.

### Release Plan (User's Preferred Order)

1. ✅ Make mcp-refcache repo public
2. 🔄 Make mcp-refcache release on PyPI (v0.0.1)
3. ⏳ Use the PyPI release in fastmcp-template
4. ⏳ Make fastmcp-template public
5. ⏳ Use PyPI release in other MCP server examples

### Tasks Breakdown

#### Task 1: Pre-Release Cleanup ✅

**What to Review:**
- [x] LICENSE file exists and is correct (MIT, present)
- [x] README.md references LICENSE correctly
- [x] pyproject.toml is ready for PyPI:
  - Version: 0.0.1 ✅
  - License: MIT ✅
  - URLs configured ✅
  - Dependencies properly declared ✅
  - Build system configured (hatchling) ✅
  - Proper excludes for sdist ✅
- [x] .gitignore properly excludes build artifacts and local files
- [x] Examples directory structure reviewed

**Findings:**
- ✅ LICENSE file exists with MIT license
- ✅ README already references LICENSE correctly
- ✅ pyproject.toml is well-configured for PyPI
- ✅ .gitignore is comprehensive
- ⚠️ Examples contain git submodules (BundesMCP, finquant-mcp, fastmcp-template)

**Submodule Handling:**
- Submodules in examples/ directory:
  - `examples/BundesMCP` - git submodule
  - `examples/finquant-mcp` - git submodule
  - `examples/fastmcp-template` - git submodule (not in .gitmodules yet)
- Submodules are excluded from sdist builds (good!)
- Submodules should remain as examples once dependent repos are public
- For now: Document that examples require separate setup

#### Task 2: Documentation Polish

**README.md updates needed:**
- ✅ LICENSE badge and link present
- ✅ Installation instructions for PyPI
- ✅ Git installation instructions (for pre-release)
- Consider adding:
  - PyPI badge (after publishing)
  - CI/CD badge (if adding GitHub Actions)
  - Downloads badge

#### Task 3: PyPI Publishing Prep

**Pre-flight checks:**
```bash
# 1. Clean build
uv build

# 2. Check package contents
tar -tzf dist/mcp-refcache-0.0.1.tar.gz
unzip -l dist/mcp_refcache-0.0.1-py3-none-any.whl

# 3. Test installation in clean env
uv venv test-env
source test-env/bin/activate
pip install dist/mcp_refcache-0.0.1-py3-none-any.whl
python -c "from mcp_refcache import RefCache; print('OK')"
deactivate
rm -rf test-env

# 4. Run full test suite
uv run pytest --cov

# 5. Security audit
uv run pip-audit

# 6. Publish to TestPyPI first
uv publish --publish-url https://test.pypi.org/legacy/

# 7. Test from TestPyPI
pip install --index-url https://test.pypi.org/simple/ mcp-refcache

# 8. If all good, publish to PyPI
uv publish
```

**Required credentials:**
- PyPI account token (via `~/.pypirc` or env var)
- Or use: `uv publish --token <token>`

#### Task 4: GitHub Repository Public Release

**Before making public:**
- [ ] Review all files for sensitive data
- [ ] Check .github/workflows if present
- [ ] Review issue templates
- [ ] Set repository description
- [ ] Add topics: mcp, fastmcp, cache, llm, ai-agents, python

**After making public:**
- [ ] Update repository visibility
- [ ] Add README badges for PyPI version/downloads
- [ ] Create v0.0.1 release with tag
- [ ] Write release notes in GitHub

#### Task 5: Submodule Examples Strategy

**Current state:**
- fastmcp-template, BundesMCP, finquant-mcp are git submodules
- They currently use local/git dependency on mcp-refcache
- Need to update to use PyPI after release

**Update sequence:**
1. Publish mcp-refcache to PyPI
2. Update each example's pyproject.toml:
   ```toml
   # From:
   dependencies = ["mcp-refcache @ git+https://github.com/..."]
   # To:
   dependencies = ["mcp-refcache>=0.0.1"]
   ```
3. Test each example works with PyPI version
4. Make example repos public
5. Update .gitmodules to point to public URLs (already done)

**For users cloning mcp-refcache:**
- Document that examples require: `git submodule update --init --recursive`
- Or skip examples: just clone without --recurse-submodules

#### Task 6: Documentation Updates

**Add to README or separate INSTALL.md:**
```markdown
## Examples Setup

The examples directory contains git submodules. To use them:

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/l4b4r4b4b4/mcp-refcache

# Or if already cloned:
git submodule update --init --recursive
```

Each example has its own README with setup instructions.
```

### Open Questions

1. **Submodule strategy:** Keep examples as submodules or copy into main repo?
   - **Recommendation:** Keep as submodules. Allows independent development.
   - Users who just want the library don't need examples.
   - Users who want examples can clone with --recurse-submodules.

2. **PyPI extras for examples:** Should we add a `[examples]` extra?
   - **Recommendation:** No. Examples are demos, not part of the library.
   - Keep extras focused on library features (redis, mcp, tiktoken, etc.)

3. **CI/CD:** Add GitHub Actions for automated testing/publishing?
   - **Recommendation:** Add later. Manual release for v0.0.1 is fine.
   - Can add in v0.0.2 with: pytest, ruff, mypy, coverage reports

### Next Steps

1. ✅ Review current state (DONE)
2. User approval of plan
3. Build and test package locally
4. Publish to TestPyPI
5. Test installation from TestPyPI
6. Publish to PyPI
7. Make GitHub repo public
8. Create v0.0.1 release/tag
9. Update example repos to use PyPI version
10. Make example repos public

---

## Archived: MCP Integration + Cross-Server Caching

### Goal
Integrate mcp-refcache with real MCP servers, then build toward cross-server caching with Valkey.

### Step 1: README Cleanup (5 min)
- Remove "disk persistence" claim from README (not implemented)
- Ensure v0.0.1 claims match actual implementation

### Step 2: Add MCP Submodules (5 min)
```bash
git submodule add https://github.com/l4b4r4b4b4/BundesMCP examples/BundesMCP
git submodule add https://github.com/l4b4r4b4b4/OpenStreetMapMCP examples/OpenStreetMapMCP
git submodule add https://github.com/l4b4r4b4b4/FinQuantMCP examples/FinQuantMCP
```

### Step 3: BundesMCP Integration (30-60 min)
1. Add `mcp-refcache` as dependency
2. Identify cacheable tools (API responses)
3. Wrap with `@cache.cached()`
4. Add `TracedRefCache` for Langfuse observability
5. Test in Zed with live Langfuse dashboard

### Step 4: Repeat for Other MCPs
- OpenStreetMapMCP
- FinQuantMCP

### Step 5: Valkey Backend Skeleton (if time permits)
- Create `src/mcp_refcache/backends/valkey.py`
- Implement `CacheBackend` protocol for Redis/Valkey
- Enable cross-server shared caching

---

## Langfuse Integration Summary (from Session 10)

### Key Learnings

**Cost Tracking Only for Real LLM Calls:**
| Scenario | Cost Tracking? | Observation Type |
|----------|---------------|------------------|
| Pure computation (math, sequences) | ❌ No | `span` |
| Cache operations | ❌ No | `span` |
| Real LLM API call (OpenAI, Anthropic) | ✅ Yes | `generation` |

**TracedRefCache Pattern:**
```python
from mcp_refcache import RefCache, PreviewConfig
from examples.langfuse_integration import TracedRefCache

# Create base cache
base_cache = RefCache(name="my-cache", preview_config=PreviewConfig(max_size=100))

# Wrap with tracing
cache = TracedRefCache(base_cache)

# Use as normal - all operations traced to Langfuse
@cache.cached(namespace="api_responses")
async def fetch_data(query: str) -> dict:
    return await api.get(query)
```

**User/Session Attribution:**
```python
# Set context for tracing
enable_test_context(True)
set_test_context(user_id="alice", org_id="acme", session_id="sess-123")

# All subsequent traces include user attribution
```

### Files for Langfuse Integration
- `examples/langfuse_integration.py` - Complete example with TracedRefCache
- Requires: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` env vars

---

## Previous Session Summary (Sessions 7-10)
### Session 10: Langfuse + RefCache Integration ✅
- Enhanced `TracedRefCache.cached()` with Langfuse spans
- Removed fake cost tracking (no LLM calls = no costs)
- Fixed return type annotations for cached functions
- 586 tests passing

### Sessions 7-9: Langfuse Observability ✅
- Created `examples/langfuse_integration.py` with TracedRefCache
- Added context-scoped testing tools
- Implemented Langfuse SDK v3 patterns (propagate_attributes, observe)

### Previous Sessions: Core Library ✅
- Phase 1-5 complete: RefCache with full access control
- Context limiting with token/char measurement
- Preview strategies (sample, paginate, truncate)
- FastMCP integration with `@cache.cached()` decorator

---

## Key Architecture Decisions

### FastMCP Tool Description Flow
1. `@mcp.tool(description="...")` - Explicit description takes precedence
2. Docstring via `inspect.getdoc(fn)` - Used if no explicit description
3. Both are exposed to LLM during MCP discovery

### Instruction Injection Levels
| Level | Mechanism | Use For |
|-------|-----------|---------|
| Server | `FastMCP(instructions=...)` | Overall caching behavior |
| Tool | Docstring or `description=` | Per-tool cache hints |
| Prompt | `@mcp.prompt` | Detailed cache guide |
| Response | `available_actions` field | Dynamic hints |

### Cache Admin Security
- Cache management tools MUST be admin-only
- Never expose `clear_cache`, `delete_reference` to agents
- Use separate server or permission gating

---

## Reference Files

### Examples
- `examples/mcp_server.py` - Scientific Calculator MCP (context-scoped caching)
- `examples/langfuse_integration.py` - Langfuse observability example
- `examples/README.md` - Example documentation

### FastMCP Integration
- `src/mcp_refcache/fastmcp/` - FastMCP helpers module
- `src/mcp_refcache/fastmcp/instructions.py` - `cache_instructions()`, `with_cache_docs()`

### Archived Reference
- `.agent/tmp/` - Copied toolsets from fractal-agents for reference

---

## Project Overview

Reference-based caching library for FastMCP servers. Enables:
- Context management via previews instead of full payloads
- Hidden computation - server-side ops on values agents see only by reference
- Namespace isolation (public, session, user, custom)
- Access control layer - separate permissions for users and agents
- CRUD + EXECUTE permissions (EXECUTE = use without seeing!)
- Cross-tool data flow - references as data bus between tools

## Current Status: Context Limiting Complete, RefCache Integration Next

**Test Results:** 325 tests passing, 88% coverage

## Session History

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

### ✅ Completed - Access Control Architecture

#### Phase 1-3: Core Access Control ✅
- [x] Designed Hybrid RBAC + Namespace Ownership architecture
- [x] Created `src/mcp_refcache/access/` module with protocols
- [x] `Actor` protocol + `DefaultActor` implementation (identity-aware actors)
- [x] `NamespaceResolver` protocol + `DefaultNamespaceResolver` (namespace ownership rules)
- [x] `PermissionChecker` protocol + `DefaultPermissionChecker` (permission resolution)
- [x] Enhanced `AccessPolicy` with owner, ACLs, session binding (backwards compatible)
- [x] 139 new tests for access control, 249 total tests, 92% coverage

See `.agent/features/access-control.md` for full architecture documentation.

### ✅ Completed: Phase 4 - Context Limiting RefCache Integration

**Completed Tasks:**
- [x] Updated `RefCache.__init__()` with `tokenizer`, `measurer`, `preview_generator` params
- [x] Refactored `_create_preview()` to return `PreviewResult`
- [x] Updated `get()` to populate `CacheResponse` with `PreviewResult` metadata
- [x] Added `original_size` and `preview_size` to `CacheResponse` model

- [x] Default to TOKEN mode with TiktokenAdapter (falls back to CharacterFallback)
- [x] 22 new tests for context limiting integration
- [x] All 347 tests pass, 89% coverage

**API Examples:**
```python
# Simple usage with tiktoken
cache = RefCache(tokenizer=TiktokenAdapter("gpt-4o"))

# Advanced usage with custom measurer and generator
cache = RefCache(
    measurer=TokenMeasurer(TiktokenAdapter("gpt-4o")),
    preview_generator=SampleGenerator(),
)

# Backwards compatible - works without any changes
cache = RefCache()
```

### ✅ Completed: Context Limiting & Preview Strategies (Phase 1-3)

#### Background
The old `RefCache._create_preview()` was basic:
- Used `max_size` as item count, not tokens/characters
- No tiktoken integration for accurate token counting
- Preview strategies not fully implemented

#### Architecture: Three Layers ✅ COMPLETE

**1. Tokenizer Adapters** (`context.py`) - Exact token counts!
| Class | Description |
|-------|-------------|
| `Tokenizer` (Protocol) | Encode text to tokens |
| `TiktokenAdapter` | OpenAI models (gpt-4o, gpt-4, etc.) |
| `HuggingFaceAdapter` | HF models (Llama, Mistral, Qwen, etc.) |
| `CharacterFallback` | ~4 chars per token approximation |

**2. Size Measurement** (`context.py`)
| Class | Description |
|-------|-------------|
| `SizeMeasurer` (Protocol) | Measure value size |
| `TokenMeasurer` | Uses injected Tokenizer |
| `CharacterMeasurer` | Simple JSON len() |

**3. Preview Strategies** (`preview.py`)
| Class | Description |
|-------|-------------|
| `PreviewGenerator` (Protocol) | How to create previews |
| `SampleGenerator` | Pick N evenly-spaced items, structured output |
| `PaginateGenerator` | Split into pages, each ≤ limit |
| `TruncateGenerator` | Stringify and cut (escape hatch) |

#### Key Design Decisions

1. **Adapter pattern for tokenizers** - DI for tiktoken AND HuggingFace transformers
2. **Lazy loading** - HF tokenizer loaded on first call, cached in adapter
3. **HF cache** - Uses `~/.cache/huggingface/hub/` (transformers default)
4. **Protocol-based** (like access control) - DI-friendly, testable
5. **Structured previews** - preview is actual data, not stringified
6. **Size applies to OUTPUT** - measure size of the preview, not input
7. **Binary search for target count** - find how many items fit within limit

#### Implementation Status

**Phase 1: Tokenizer Adapters (`context.py`)** ✅ COMPLETE
- [x] `Tokenizer` protocol with `encode()`, `count_tokens()`, `model_name`
- [x] `TiktokenAdapter` - OpenAI models, lazy load encoding
- [x] `HuggingFaceAdapter` - HF models, lazy load tokenizer
- [x] `CharacterFallback` - ~4 chars/token approximation
- [x] Tests for all adapters (35 tests, 8 skipped for optional deps)

**Phase 2: Size Measurement (`context.py`)** ✅ COMPLETE
- [x] `SizeMeasurer` protocol with `measure(value) -> int`
- [x] `TokenMeasurer` - uses injected Tokenizer
- [x] `CharacterMeasurer` - JSON stringify + len
- [x] `get_default_measurer(size_mode, tokenizer)` factory
- [x] Tests for measurers

**Phase 3: Preview Generators (`preview.py`)** ✅ COMPLETE
- [x] `PreviewGenerator` protocol
- [x] `PreviewResult` dataclass
- [x] `SampleGenerator` - binary search + evenly-spaced sampling
- [x] `PaginateGenerator` - page-based splitting
- [x] `TruncateGenerator` - string truncation
- [x] `get_default_generator(strategy)` factory
- [x] 41 tests for generators

**Phase 4: RefCache Integration (`cache.py`)** ✅ COMPLETE
- [x] `RefCache.__init__()` accepts `tokenizer`, `measurer`, `preview_generator`
- [x] `_create_preview()` returns `PreviewResult` instead of tuple
- [x] `get()` populates `CacheResponse` with size metadata
- [x] `CacheResponse` model updated with `original_size`, `preview_size`
- [x] All 347 tests pass
- [x] 22 new integration tests

**Known Limitations:**
1. Sampling happens at top-level only. Deeply nested structures where a single
   top-level key exceeds `max_size` won't be recursively shrunk.
2. tiktoken and transformers are optional deps - tests skip when not installed.

### ✅ Completed: Phase 5 - RefCache + Access Control Integration (Session 2024-XX-XX)

**Session Summary**: Integrated access control protocols into RefCache main class.

**Completed Tasks:**
- [x] Updated `RefCache.__init__()` with `permission_checker: PermissionChecker | None` parameter
- [x] Updated `RefCache.get/resolve/delete` to accept `actor: ActorLike` (Actor | Literal)
- [x] Replaced `_check_permission()` inline logic with injected PermissionChecker
- [x] Added namespace parameter to permission checking for ownership validation
- [x] 27 new integration tests for Actor + PermissionChecker + NamespaceResolver
- [x] Full backwards compatibility: literal "user"/"agent" strings still work
- [x] All tests pass: 374 passed, 89% coverage

**Key Changes:**
- `RefCache` now uses `DefaultPermissionChecker` by default
- Namespace ownership enforced: `user:alice` namespace only accessible by user alice
- Session namespaces require matching `session_id`
- System actors bypass namespace restrictions
- `PermissionDenied` exception with rich attributes (actor, required, reason, namespace)

### 🔜 Remaining Tasks

#### Priority 1: FastMCP Integration Example (~2-3 hours to working demo)
- [ ] Create `examples/mcp_server.py` with working MCP server
- [ ] Create `examples/README.md` with usage documentation
- [ ] Update main `README.md` with quick start guide
- [ ] Test with MCP client (Claude Desktop or similar)

#### Priority 2: Audit Logging (Optional)
- [ ] Define AuditLogger protocol
- [ ] Hook into permission checks
- [ ] Default no-op implementation

#### Priority 3: Integration
- [ ] Add FastMCP integration (`tools/`) - optional dependency

---

## Access Control Architecture - IMPLEMENTED ✅

**Architecture Decision**: Hybrid RBAC + Namespace Ownership

See `.agent/features/access-control.md` for full documentation.

### Key Components Implemented

1. **Actor Protocol** (`access/actor.py`)
   - `ActorType` enum: USER, AGENT, SYSTEM
   - `DefaultActor` with factory methods: `.user()`, `.agent()`, `.system()`
   - Pattern matching: `actor.matches("user:alice")`, wildcards supported
   - Backwards compat: `resolve_actor("user")` → `DefaultActor.user()`

2. **NamespaceResolver Protocol** (`access/namespace.py`)
   - Namespace patterns: `public`, `session:<id>`, `user:<id>`, `agent:<id>`
   - `validate_access(namespace, actor)` - ownership rules
   - `parse(namespace)` → `NamespaceInfo` with flags

3. **PermissionChecker Protocol** (`access/checker.py`)
   - Resolution order: deny → session → namespace → allow → owner → role
   - `check()` raises `PermissionDenied`, `has_permission()` returns bool
   - `get_effective_permissions()` for introspection

4. **Enhanced AccessPolicy** (`permissions.py`)
   - New fields: `owner`, `owner_permissions`, `allowed_actors`, `denied_actors`, `bound_session`
   - Backwards compatible - all new fields are optional

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
├── context.py           # Size measurement (SizeMeasurer protocol) - IN PROGRESS
├── preview.py           # Preview strategies (PreviewGenerator protocol) - NEXT
├── access/              # Access control module ✅
│   ├── __init__.py
│   ├── actor.py
│   ├── checker.py
│   └── namespace.py
├── backends/
│   ├── __init__.py      # Backend exports ✅
│   ├── base.py          # Backend protocol ✅
│   └── memory.py        # In-memory backend ✅
└── tools/
    ├── __init__.py
    └── mcp_tools.py     # FastMCP integration (optional)
```

### Context Limiting Architecture (Detailed)

**Three-Layer Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                     PreviewConfig                           │
│  size_mode: TOKEN | CHARACTER                               │
│  max_size: int (tokens or chars)                            │
│  default_strategy: SAMPLE | PAGINATE | TRUNCATE             │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────────┐
│  Tokenizer    │ │ SizeMeasurer  │ │ PreviewGenerator  │
│  (Protocol)   │ │ (Protocol)    │ │ (Protocol)        │
├───────────────┤ ├───────────────┤ ├───────────────────┤
│ TiktokenAdapt │ │ TokenMeasurer │ │ SampleGenerator   │
│ HuggingFaceAd │ │ CharMeasurer  │ │ PaginateGenerator │
│ CharFallback  │ └───────────────┘ │ TruncateGenerator │
└───────────────┘         ▲         └───────────────────┘
        │                 │
        └────► injects ───┘
```

**1. Tokenizer Protocol** (`context.py`)
```python
class Tokenizer(Protocol):
    """Protocol for tokenizer adapters - exact token counts!"""

    @property
    def model_name(self) -> str:
        """The model this tokenizer is for."""
        ...

    def encode(self, text: str) -> list[int]:
        """Encode text to token IDs."""
        ...

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        ...


class TiktokenAdapter:
    """OpenAI models (gpt-4o, gpt-4, gpt-3.5-turbo)."""

    def __init__(self, model: str = "gpt-4o"):
        self._model = model
        self._encoding = None  # Lazy load


class HuggingFaceAdapter:
    """HF models (Llama, Mistral, Qwen, etc.)."""

    def __init__(self, model: str = "meta-llama/Llama-3.1-8B"):
        self._model = model
        self._tokenizer = None  # Lazy load, cached by HF
```

**2. SizeMeasurer Protocol** (`context.py`)
```python
class SizeMeasurer(Protocol):
    def measure(self, value: Any) -> int:
        """Measure size of a value (tokens or chars)."""
        ...


class TokenMeasurer:
    def __init__(self, tokenizer: Tokenizer):
        self._tokenizer = tokenizer  # DI!

    def measure(self, value: Any) -> int:
        text = json.dumps(value, default=str)
        return self._tokenizer.count_tokens(text)
```

**3. PreviewGenerator Protocol** (`preview.py`)
```python
class PreviewGenerator(Protocol):
    def generate(
        self,
        value: Any,
        max_size: int,
        measurer: SizeMeasurer,
        page: int | None = None,
    ) -> PreviewResult:
        """Generate a preview within size constraints."""
        ...
```

**Key insight:** Preview should be **structured data**, not stringified truncation!

**Algorithm for Sample Strategy:**
1. Measure size of full value
2. If fits within `max_size`, return as-is
3. Binary search to find target item count that fits
4. Sample evenly-spaced items: `step = total / target`
5. Return `PreviewResult` with sampled data + metadata

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

### v0.0.1 (Current) ✅ COMPLETE
- Core caching with RefCache class
- Memory backend (thread-safe with TTL)
- Namespaces and permissions
- Context limiting (token/char + truncate/paginate/sample)
- EXECUTE for private compute
- `@cache.cached()` decorator with ref resolution
- FastMCP integration helpers
- Langfuse observability (TracedRefCache)

### Future Vision: Specialized Data Store Integration

**Key Insight:** mcp-refcache is for tool outputs and computed results, NOT for source data storage. However, we can integrate with specialized stores for specific data types.

#### Time Series Data (finquant-mcp, market data)
- **Backend:** TimescaleDB, InfluxDB, or local Parquet files
- **Pattern:** Incremental fetching - only fetch date ranges not in local store
- **Hot-swapping:** MCP tool requests data → check local store → fetch missing → cache result
- **Example flow:**
  ```
  get_prices(AAPL, 2024-01-01, 2024-12-31)
    → Check TimescaleDB: has 2024-01-01 to 2024-06-30
    → Fetch from Yahoo: 2024-07-01 to 2024-12-31
    → Store new data in TimescaleDB
    → Return full range (RefCache caches the tool output)
  ```

#### Vector Store (news-mcp, semantic search)
- **Backend:** ChromaDB, Qdrant, Pinecone, or local FAISS
- **Pattern:** Embeddings stored locally, incrementally updated
- **Hot-swapping:** New articles → embed → store → available for semantic search
- **Example flow:**
  ```
  search_news("Fed interest rate decision")
    → Query local vector store
    → If stale, fetch new articles from news API
    → Embed and store new articles
    → Return semantic search results (RefCache caches output)
  ```

#### Integration Pattern
```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Tool Layer                                │
│  @cache.cached() for tool outputs                                │
└─────────────────────────────────────────────────────────────────┘
                              ↑
                    tool output caching
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Domain Data Layer (App's job)                 │
│  - TimescaleDB for time series (prices, metrics)                 │
│  - Vector store for embeddings (news, documents)                 │
│  - PostgreSQL for structured data (users, portfolios)            │
└─────────────────────────────────────────────────────────────────┘
                              ↑
                    incremental fetching
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    External APIs                                 │
│  - Yahoo Finance, CoinGecko (market data)                        │
│  - News APIs (articles)                                          │
│  - Only fetch what's missing locally                             │
└─────────────────────────────────────────────────────────────────┘
```

**This is out of scope for v0.0.x** - but documented for future MCP integrations.

---

### v0.0.2 (Next)
- Valkey/Redis backend for cross-server caching
- Disk persistence for memory backend
- Reference metadata (tags, descriptions)
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
- **Deterministic cache**: Use `RefCache(default_ttl=None)` for never-expiring entries

## Session Log

### 2024-XX-XX: Phase 5 Complete - Access Control RefCache Integration
- Integrated `PermissionChecker` protocol into `RefCache`
- Added `permission_checker` parameter to `RefCache.__init__()`
- Changed `actor` parameter from `Literal["user", "agent"]` to `ActorLike`
- Replaced inline `_check_permission()` with injected checker
- Added namespace to permission checks for ownership validation
- 27 new integration tests added
- **Stats**: 374 tests, 89% coverage, all linting passes
- **Library Status**: Feature-complete for v0.0.1, ready for FastMCP integration

### 2024-XX-XX: Phase 1 Complete
- Implemented CacheBackend Protocol and CacheEntry dataclass
- Implemented thread-safe MemoryBackend with TTL support
- Implemented RefCache with full CRUD operations
- Implemented @cached decorator for sync and async functions
- 110 tests passing, 90% coverage
- Updated .rules for Python library context (removed FastAPI/microservice specifics)
- Identified need for sophisticated access control (user/agent IDs, not just roles)

### 2024-XX-XX: Access Control Architecture Complete
- Designed and implemented Hybrid RBAC + Namespace Ownership architecture
- Created `src/mcp_refcache/access/` module with 3 protocols + implementations
- `Actor` protocol with `DefaultActor` - identity-aware actors
- `NamespaceResolver` protocol with `DefaultNamespaceResolver` - namespace ownership
- `PermissionChecker` protocol with `DefaultPermissionChecker` - permission resolution
- Enhanced `AccessPolicy` with owner, ACLs, session binding (backwards compatible)
- 139 new tests for access control module
- 249 total tests passing, 92% coverage
- Next: Context Limiting & Preview Strategies

### 2024-XX-XX: Context Limiting & Preview Strategies ✅ COMPLETE
**Goal:** Implement sophisticated context limiting for LLM context windows

**Files Created:**
- `src/mcp_refcache/context.py` - Tokenizer adapters + SizeMeasurer (550 lines)
- `src/mcp_refcache/preview.py` - PreviewGenerator + implementations (761 lines)
- `tests/test_context.py` - 43 tests (35 pass, 8 skip for optional deps)
- `tests/test_preview.py` - 41 tests

**Architecture Implemented:**
1. `context.py` - Tokenizer adapters + SizeMeasurer
   - `Tokenizer` protocol (exact token counts!)
   - `TiktokenAdapter` (OpenAI models: gpt-4o, gpt-4, etc.)
   - `HuggingFaceAdapter` (Llama, Mistral, Qwen, etc.)
   - `CharacterFallback` (~4 chars/token approximation)
   - `SizeMeasurer` protocol + `TokenMeasurer`, `CharacterMeasurer`
   - Factory functions: `get_default_tokenizer()`, `get_default_measurer()`
2. `preview.py` - PreviewGenerator protocol + implementations
   - `PreviewResult` dataclass with full metadata
   - `SampleGenerator` - binary search + evenly-spaced sampling
   - `PaginateGenerator` - page-based splitting with max_size respect
   - `TruncateGenerator` - string truncation with ellipsis
   - Factory: `get_default_generator(strategy)`

**Key decisions:**
- **Adapter pattern** for tokenizers - support tiktoken AND HuggingFace
- **Lazy loading** - HF tokenizer loaded on first call, cached in adapter
- **HF cache** - Uses `~/.cache/huggingface/hub/` automatically
- tiktoken AND transformers as optional dependencies
- Protocols for testability and extensibility
- Structured output (not stringified)
- Size limit applies to preview OUTPUT, not input
- Binary search to find target item count

**pyproject.toml extras:**
- `mcp-refcache[tiktoken]` - OpenAI models
- `mcp-refcache[transformers]` - HuggingFace models

**Test Results:** 325 tests passing, 88% coverage

**Next Session:** Phase 4 - Integrate with RefCache._create_preview()

### Starting Prompt for Next Session

See bottom of this file for the codebox prompt to continue development.

**Future (v0.1.0+):** Embeddings for semantic search - see `.agent/features/embeddings.md`

---

## Next Session Starting Prompt

### CURRENT PROMPT (Tonight's Work):

```
mcp-refcache: Real MCP Integration + Cross-Server Caching

## Context
- v0.0.1 READY: 586 tests, all core features complete
- Langfuse integration working (TracedRefCache)
- See `.agent/scratchpad.md` for full context

## Tonight's Goals
1. Clean up README for v0.0.1 accuracy
2. Add BundesMCP, OpenStreetMapMCP, FinQuantMCP as submodules
3. Integrate mcp-refcache into BundesMCP (caching + tracing)
4. If time: Start Valkey backend skeleton

## Step 1: README Cleanup (5 min)
- Remove "disk persistence" claim (not implemented)
- Verify all v0.0.1 feature claims are accurate

## Step 2: Add Submodules (5 min)
git submodule add https://github.com/l4b4r4b4b4/BundesMCP examples/BundesMCP
git submodule add https://github.com/l4b4r4b4b4/OpenStreetMapMCP examples/OpenStreetMapMCP
git submodule add https://github.com/l4b4r4b4b4/FinQuantMCP examples/FinQuantMCP

## Step 3: BundesMCP Integration (30-60 min)
1. Explore repo structure, identify cacheable tools
2. Add mcp-refcache dependency
3. Wrap API-calling tools with @cache.cached()
4. Add TracedRefCache for Langfuse observability
5. Test in Zed, verify traces in Langfuse dashboard

## Step 4: Valkey Backend Skeleton (if time)
- Create src/mcp_refcache/backends/valkey.py
- Implement CacheBackend protocol
- Enable cross-server shared caching

## Key Files
- examples/langfuse_integration.py - TracedRefCache pattern to copy
- src/mcp_refcache/cache.py - @cache.cached() decorator
- README.md - Needs cleanup for v0.0.1

## Guidelines
- Follow .rules (TDD, document as you go)
- Run: uv run ruff check . --fix && uv run ruff format .
- Run: uv run pytest tests/
```

---

### PREVIOUS PROMPT (Archived):

\`\`\`
Continue mcp-refcache: FastMCP Integration Polish & Live Testing

## Context
- Phase 1-5 complete: RefCache fully functional with access control
- 389 tests, 89% coverage
- See `.agent/scratchpad.md` for full context

## What Was Done Last Session
1. Created `examples/mcp_server.py` - Scientific Calculator MCP (complete, working)
2. Created `examples/README.md` - Documentation
3. Created `tests/test_examples.py` - 15 tests, all passing
4. Created `src/mcp_refcache/fastmcp/` module - Instruction helpers
5. Added FastMCP as submodule at `.external/fastmcp`

## Current Task: Polish & Test

### Task 1: Update Example to Use Instruction Helpers
Update `examples/mcp_server.py` to use the new helpers:
- Replace manual instructions with `cache_instructions()`
- Add `@with_cache_docs()` decorator to tools
- Register `cache_guide_prompt` as a prompt

### Task 2: Add Calculator to Zed Settings
Add to `.zed/settings.json` for live testing in this chat.

### Task 3: Create Admin Tools Module (Optional)
Create `src/mcp_refcache/fastmcp/admin_tools.py` with permission-gated cache management.

### Guidelines
- Follow `.rules` (TDD, document as you go)
- FastMCP is optional dependency - handle import gracefully
- Keep admin tools separate and restricted
\`\`\`

---

## Previous Session Starting Prompt

Use the codebox below to continue in a new chat session:

```
Continue mcp-refcache: Priority 1 - FastMCP Integration Example

## Context
- Phase 1-5 complete: RefCache fully functional with access control
- 374 tests, 89% coverage
- See `.agent/scratchpad.md` for full context

## Current State (Feature-Complete for v0.0.1)
- RefCache with namespaces, TTL, previews
- Access control: PermissionChecker, Actor, NamespaceResolver protocols
- Context limiting: token/char measurement, sample/truncate/paginate strategies
- Identity-aware: user:*, session:*, agent:* namespace ownership

## Task: Create FastMCP Integration Example

### Goal
Create a working MCP server demo that showcases RefCache capabilities.

### Files to Create
1. `examples/mcp_server.py` - FastMCP server with RefCache-backed tools
2. `examples/README.md` - Usage documentation and setup instructions

### Example Server Features
- Tool that returns large data → cached with preview
- `get_page` tool for pagination
- `resolve_full` tool to get complete data
- Session-scoped namespaces for isolation
- Demonstrate agent vs user permissions

### Guidelines
- Follow `.rules` (TDD, document as you go)
- FastMCP is optional dependency - handle import gracefully
- Provide clear setup instructions for Claude Desktop
```

2. **FastMCP Integration Examples** (Priority 3)
   - Create example MCP server using RefCache
   - Document integration patterns

3. **Documentation Updates**
   - Update README with new API
   - Add usage examples for context limiting

4. **Additional Backends**
   - Redis backend for distributed caching
   - File-based backend for persistence

### Guidelines
- Follow `.rules` (TDD, protocol-based contracts)
- Maintain 80%+ coverage
```
~~~key="
