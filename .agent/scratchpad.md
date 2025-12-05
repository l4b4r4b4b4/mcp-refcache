# mcp-refcache Development Scratchpad

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
~~~