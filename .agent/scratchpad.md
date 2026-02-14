# mcp-refcache Development Scratchpad

## Current Status: v0.2.0 In Development 🟡

**Last Updated**: 2025-01-20

### Published Package

- **PyPI**: [pypi.org/project/mcp-refcache](https://pypi.org/project/mcp-refcache/)
- **GitHub**: Public repository ready

### v0.1.0 Feature Checklist

| Feature | Status | Notes |
|---------|--------|-------|
| Core RefCache class | ✅ Done | 652 tests passing |
| Memory backend (thread-safe) | ✅ Done | TTL support |
| SQLite backend | ✅ Done | Cross-process caching |
| Redis backend | ✅ Done | Optional `[redis]` extra |
| Namespaces (public, session, user, custom) | ✅ Done | Full isolation |
| Access control (Actor, Permission, ACLs) | ✅ Done | User/Agent/System |
| Context limiting (token/char) | ✅ Done | tiktoken + HF support |
| Preview strategies (sample/paginate/truncate) | ✅ Done | PreviewGenerator |
| EXECUTE permission (private compute) | ✅ Done | Blind computation |
| `@cache.cached()` decorator | ✅ Done | Automatic ref resolution |
| FastMCP integration helpers | ✅ Done | `cache_instructions()` |
| Admin tools | ✅ Done | Permission-gated |

**Test Results**: 652 passed (39 skipped for optional Redis/transformers deps)

---

## Active Goals

| ID | Goal Name | Status | Priority |
|----|-----------|--------|----------|
| 01 | [Legal-MCP](./goals/01-Legal-MCP/scratchpad.md) | ⚪ Not Started | P2 (Medium) |
| 02 | [Faster-MCP](./goals/02-Faster-MCP/scratchpad.md) | ⚪ Not Started | P3 (Low) |
| 04 | [Async-Task-Backends](./goals/04-Async-Timeout-Fallback/scratchpad.md) | 🟢 Tasks 01-05, 09 Done | P1 (High) |
| 05 | [Real-Estate-Sustainability-MCP](./goals/05-Real-Estate-Sustainability-MCP/scratchpad.md) | 🔴 Not Started | P1 (High) |
| 06 | [TypeScript-RefCache](./goals/06-TypeScript-RefCache/scratchpad.md) | 🟡 In Progress | P1 (High) |

See [Goals Index](./goals/scratchpad.md) for full tracking.

### Goal Summaries

**01-Legal-MCP**: Comprehensive legal research MCP server with mcp-refcache integration. Starts with German law (dejure.org), expands to EU (EUR-Lex) and US law. Demonstrates real-world caching of large, stable legal documents.

**02-Faster-MCP**: Research feasibility of Robyn-based (Rust runtime) alternative to FastMCP. Motivated by 40x+ performance improvement potential (10k+ RPS vs ~246 RPS).

**04-Async-Task-Backends**: Add async task execution to `@cache.cached()` with pluggable backends. `TaskBackend` protocol enables `MemoryTaskBackend` (ThreadPoolExecutor, MVP) and future `HatchetTaskBackend` (distributed). When computations exceed `async_timeout`, returns reference immediately with "processing" status. Client polls for completion. **Tasks 01-05, 09 complete. 718 tests passing.** Next: Create minimal MCP server example, test in Zed, then release v0.2.0.

**06-TypeScript-RefCache**: Restructure repo into **Bun+Python monorepo** housing both implementations. Port `mcp-refcache` to TypeScript for Node.js MCP ecosystem. Target FastMCP (TypeScript) by @punkpeye. Full feature parity: RefCache, backends (Memory/SQLite/Redis), access control, preview system, async tasks. Plus companion `fastmcp-ts-template` (port of Python template). **Tasks 00–03 complete. Task-04 next (RefCache core).** 171 TS tests passing (61ms). Primary reference: `fractal-agents-runtime` (`.agent/references/fractal-agents-runtime/`). Branch: `feat/monorepo-restructure`.

---

## Session Log (2025-07-17)

### Completed This Session

1. **Task-03: Backend Protocol & MemoryBackend** ✅
   - Created `CacheBackend` interface (`src/backends/types.ts`) — direct port of Python's `CacheBackend` protocol
     - 6 methods: `get`, `set`, `delete`, `exists`, `clear`, `keys`
     - Synchronous (not async) — `MemoryBackend` has no I/O, no need for `Promise` wrapping
   - Created `MemoryBackend` class (`src/backends/memory.ts`) — `Map<string, CacheEntry>` with lazy TTL eviction
     - Reuses `CacheEntry` and `isExpired()` from Task-02's `src/models/cache.ts`
     - No locking needed (JS is single-threaded, unlike Python's `threading.RLock`)
     - No LRU, no background timer, no `close()` — matching Python source exactly
   - Created barrel (`src/backends/index.ts`) and updated `src/index.ts` with real exports
   - Wrote 58 comprehensive tests (`tests/backends.test.ts`, 834 lines, 124 assertions):
     - CacheEntry model tests (7), protocol compliance (2), basic CRUD (14)
     - TTL expiration (7), namespace-scoped clear (5), namespace-scoped keys (7)
     - Interface contract tests (7, extensible for future backends), edge cases (9)
   - **Total: 171 TS tests passing (61ms), 718 Python tests still passing**

### Files Created
- `packages/typescript/src/backends/types.ts` — `CacheBackend` interface (109 lines)
- `packages/typescript/src/backends/memory.ts` — `MemoryBackend` class (187 lines)
- `packages/typescript/src/backends/index.ts` — barrel (11 lines)
- `packages/typescript/tests/backends.test.ts` — 58 tests (834 lines)

### Files Modified
- `packages/typescript/src/index.ts` — replaced backend TODO comments with real exports

---

## Session Log (2025-07-16)

### Completed This Session

1. **Goal 06 Reference Update** — Switched primary reference to `fractal-agents-runtime`
   - Copied 15+ reference files to `.agent/references/fractal-agents-runtime/`
   - Created README with file inventory and mapping to each task
   - Added Python ↔ TypeScript module mapping table to goal scratchpad
   - Key decisions: `bun test` over Vitest, Lefthook over pre-commit, `js-tiktoken`

2. **Task-01: Project Setup & Tooling** ✅
   - Created `packages/typescript/` with `package.json`, `tsconfig.json`, `src/index.ts`
   - `bun test`: 3 smoke tests passing (VERSION export, semver, package.json sync)
   - `tsc` build: `dist/index.js` + `dist/index.d.ts` + source maps
   - Lefthook installed: polyglot pre-commit (Python lint + TS typecheck) and pre-push (tests + reject merge commits)
   - GitHub Actions CI: added `test-typescript` job alongside existing Python jobs
   - Root `package.json`: `postinstall: lefthook install`, all cross-ecosystem scripts working
   - Commit: `a3fb939`

3. **Task-02: Models & Zod Schemas** ✅
   - Ported ALL Python Pydantic models to Zod schemas (6 files, ~1600 lines of source):
     - `enums.ts`: SizeMode, PreviewStrategy, AsyncResponseFormat, TaskStatus, ActorType
     - `permissions.ts`: Permission bitfield (exact Python `auto()` values), AccessPolicy, 4 policy presets, `hasPermission`/`combinePermissions`/`userCan`/`agentCan` helpers
     - `preview.ts`: PreviewConfig, PreviewResult
     - `cache.ts`: CacheReference, CacheResponse, PaginatedResponse, CacheEntry, `paginateList()`, `isExpired()`
     - `task.ts`: TaskProgress (with auto-percentage `.transform()`), RetryInfo, ExpectedSchema, TaskInfo, AsyncTaskResponse, `asyncTaskResponseFromInfo()`, `asyncTaskResponseToDict()`, `canRetry()`, `isTerminal()`, `elapsedSeconds()`
     - `index.ts`: barrel re-exporting all schemas, types, and helpers
   - 110 new tests (1217 lines) covering every schema, helper, edge case, and Python parity check
   - `src/index.ts` updated: real model re-exports replace TODO comments
   - **Total: 113 tests passing, 0 failures, 36ms**
   - Commit: `9e3f049`

### Files Created
- `packages/typescript/package.json` — npm library config
- `packages/typescript/tsconfig.json` — extends root, declarations
- `packages/typescript/src/index.ts` — barrel with VERSION + model re-exports
- `packages/typescript/src/models/enums.ts` — 5 enum schemas
- `packages/typescript/src/models/permissions.ts` — Permission bitfield + AccessPolicy
- `packages/typescript/src/models/preview.ts` — PreviewConfig + PreviewResult
- `packages/typescript/src/models/cache.ts` — CacheReference/Response/Entry + helpers
- `packages/typescript/src/models/task.ts` — TaskProgress/Info/AsyncResponse + factories
- `packages/typescript/src/models/index.ts` — barrel
- `packages/typescript/tests/index.test.ts` — 3 smoke tests
- `packages/typescript/tests/models.test.ts` — 110 model tests
- `packages/typescript/LICENSE`, `README.md`, `.gitignore`
- `lefthook.yml` — polyglot git hooks
- `.agent/references/fractal-agents-runtime/` — 15+ reference files + README

---

## Session Log (2025-01-30)

### Completed This Session
1. **Goal 06: TypeScript-RefCache** — Created comprehensive goal with 11 tasks
   - Researched FastMCP (TypeScript) by @punkpeye, @modelcontextprotocol/sdk, Bun capabilities
   - Created detailed task scratchpads (Task-00 through Task-10)
   - Task-00: Monorepo Migration — restructure repo to Bun+Python monorepo
   - Tasks 01-10: TypeScript implementation from setup to template

2. **Monorepo Reference Collection**
   - Explored `docproc-platform` Bun+Python monorepo pattern
   - Copied reference files to `archive/bun-python-monorepo-reference/`
   - Includes: root package.json, flake.nix, tsconfig.json, Python app examples

3. **Key Decisions Made**
   - Monorepo (not separate repo) — single source of truth
   - Follow docproc-platform pattern (proven Bun+Python structure)
   - Bun-first but Node.js compatible
   - Zod for schemas (matches FastMCP pattern)

### Files Created
- `.agent/goals/06-TypeScript-RefCache/scratchpad.md` — Main goal
- `.agent/goals/06-TypeScript-RefCache/Task-00/scratchpad.md` — Monorepo Migration
- `.agent/goals/06-TypeScript-RefCache/Task-01/scratchpad.md` — TS Package Setup
- `.agent/goals/06-TypeScript-RefCache/Task-02/scratchpad.md` — Models & Zod
- `.agent/goals/06-TypeScript-RefCache/Task-03/scratchpad.md` — Backend Protocol
- `.agent/goals/06-TypeScript-RefCache/Task-04/scratchpad.md` — RefCache Core
- `.agent/goals/06-TypeScript-RefCache/Task-05/scratchpad.md` — Preview System
- `.agent/goals/06-TypeScript-RefCache/Task-06/scratchpad.md` — Access Control
- `.agent/goals/06-TypeScript-RefCache/Task-07/scratchpad.md` — SQLite & Redis
- `.agent/goals/06-TypeScript-RefCache/Task-08/scratchpad.md` — Async Task System
- `.agent/goals/06-TypeScript-RefCache/Task-09/scratchpad.md` — FastMCP Integration
- `.agent/goals/06-TypeScript-RefCache/Task-10/scratchpad.md` — Template Repository
- `archive/bun-python-monorepo-reference/` — Reference files from docproc-platform

---

## Session Log (2025-01-20)

### Completed This Session
1. **Task-05**: Polling support in `RefCache.get()`
   - Updated `get()` to return `AsyncTaskResponse` for in-flight tasks
   - Added `_build_async_task_response()` and `_calculate_eta()` helpers
   - Cleans up `_active_tasks` after completion

2. **Task-09**: Comprehensive async task tests
   - Created `tests/test_async_timeout.py` with 21 tests
   - Test coverage: timeout behavior, polling, ETA, cleanup, errors, formats, concurrency

3. **Pre-commit fixes**
   - Moved `presentations/` to `.agent/presentations/` (excluded from ruff)
   - Fixed PT011: Added match param to pytest.raises
   - Fixed B105: Added nosec for bandit false positive

4. **Commit**: `73d6ed0` - "feat(async): implement async timeout with polling support"

### Test Results
- **718 tests passing** (697 + 21 new async tests)
- 39 skipped (Redis/transformers optional deps)

---

## Next Session Handoff

````
Goal 06: TypeScript-RefCache — Task-03 Backend Protocol & MemoryBackend

## Context
- Goal 06: Porting mcp-refcache to TypeScript/Bun (polyglot monorepo)
- Tasks 00–02 complete. 113 TS tests passing (36ms). 718 Python tests passing.
- Branch: `feat/monorepo-restructure` (already checked out)
- See `.agent/goals/06-TypeScript-RefCache/scratchpad.md` for full goal details
- See `.agent/scratchpad.md` for session log with all commits

## What Was Done (Previous Session)
- Task-01 ✅: `packages/typescript/` scaffolded, `bun test`, lefthook, CI
- Task-02 ✅: ALL Pydantic models → Zod schemas (6 files, 110 tests)
  - enums, permissions (bitfield), preview, cache, task models
  - Helpers: paginateList, isExpired, hasPermission, asyncTaskResponseFromInfo, etc.
  - All exported via barrel `src/models/index.ts` → `src/index.ts`
- Commits: `a3fb939` (Task-01), `9e3f049` (Task-02)

## Current Task: Task-03 — Backend Protocol & MemoryBackend
Port `backends/base.py` (CacheBackend protocol) and `backends/memory.py` to TypeScript.

1. Create `src/backends/types.ts` — `CacheBackend` interface
   - Methods: `get(key)`, `set(key, entry)`, `delete(key)`, `exists(key)`, `clear(namespace?)`, `keys(namespace?)`
   - Reference: `.agent/references/fractal-agents-runtime/ts-src-examples/storage-types.ts`
   - Python source: `packages/python/src/mcp_refcache/backends/base.py`

2. Create `src/backends/memory.ts` — `MemoryBackend` class
   - In-memory Map-based storage with TTL expiration
   - Reference: `.agent/references/fractal-agents-runtime/ts-src-examples/storage-memory.ts`
   - Python source: `packages/python/src/mcp_refcache/backends/memory.py`

3. Create `src/backends/index.ts` — barrel
4. Update `src/index.ts` — export CacheBackend type + MemoryBackend
5. Write tests in `tests/backends.test.ts`
   - Python reference: `packages/python/tests/test_backends.py`

## Key Files
- Task-03 scratchpad: `.agent/goals/06-TypeScript-RefCache/Task-03/scratchpad.md`
- Python CacheBackend: `packages/python/src/mcp_refcache/backends/base.py`
- Python MemoryBackend: `packages/python/src/mcp_refcache/backends/memory.py`
- TS reference (interface): `.agent/references/fractal-agents-runtime/ts-src-examples/storage-types.ts`
- TS reference (impl): `.agent/references/fractal-agents-runtime/ts-src-examples/storage-memory.ts`
- CacheEntry schema: `packages/typescript/src/models/cache.ts` (already done in Task-02)

## Guidelines
- Follow `.rules` (TDD — write tests first or alongside code)
- `CacheBackend` must be a TypeScript `interface` (maps to Python `Protocol`)
- `MemoryBackend` uses `Map<string, CacheEntry>` with TTL eviction
- Use `CacheEntry` and `isExpired()` from `src/models/cache.ts` (Task-02)
- Run `bun test` after each change, `bunx tsc --noEmit` for type safety
- Don't break existing 113 tests or 718 Python tests
````

---

## Previous Session Handoffs

### 2025-01-20

```
Continue mcp-refcache: Goal 04 - Test Async Timeout in Real MCP Server

## Context
- Goal 04: Tasks 01-05, 09 complete, 718 tests passing
- See `.agent/goals/04-Async-Timeout-Fallback/scratchpad.md` for details

## What Was Done
- TaskBackend protocol + MemoryTaskBackend (ThreadPoolExecutor)
- async_timeout + async_response_format in @cache.cached()
- RefCache.get() returns AsyncTaskResponse for in-flight tasks
- 21 new tests in tests/test_async_timeout.py
- Commit: 73d6ed0

## Next Steps
1. Create `examples/async_timeout_server.py` - minimal FastMCP MCP server
2. Add to `.zed/settings.json` context_servers section
3. Restart Zed and test the async timeout tool in chat
4. If working: Consider Hatchet backend (Task-11)
5. Release v0.2.0
6. Integrate into document-mcp

## Key Files
- Protocol: src/mcp_refcache/backends/task_base.py
- Backend: src/mcp_refcache/backends/task_memory.py
- Cache: src/mcp_refcache/cache.py (L325+ get(), L1020+ async_timeout)
- Tests: tests/test_async_timeout.py
- Manual test: examples/async_timeout/test_polling.py

## Example Usage
```python
from mcp_refcache import RefCache
from mcp_refcache.backends import MemoryTaskBackend

cache = RefCache(task_backend=MemoryTaskBackend())

@cache.cached(async_timeout=5.0)
async def slow_tool():
    await asyncio.sleep(30)
    return {"done": True}
# Returns {"status": "processing", "ref_id": "..."} after 5s
# Client polls cache.get(ref_id) until CacheResponse returned
```

## Guidelines
- Follow `.rules` (test, lint before commit)
- Run: uv run ruff check . --fix && uv run ruff format .
- Run: uv run pytest
```

**05-Real-Estate-Sustainability-MCP**: Build comprehensive Real Estate Sustainability Analysis MCP server using fastmcp-template and mcp-refcache. Four core toolsets: Excel processing, PDF analysis with Chroma semantic search, sustainability frameworks (ESG, LEED, BREEAM, DGNB), and IFC integration via ifc-mcp. Target users: developers, consultants, facility managers.

---

## Roadmap

### v0.2.0 (In Development) — Async Task Backends

- [ ] `TaskBackend` protocol for pluggable task execution
- [ ] `MemoryTaskBackend` using ThreadPoolExecutor (MVP)
- [ ] `async_timeout` parameter for `@cache.cached()` decorator
- [ ] Task tracking infrastructure (TaskInfo, TaskStatus, TaskProgress) — models exist ✅
- [ ] Polling support for in-flight computations
- [ ] Progress callback protocol
- [ ] Retry mechanism with exponential backoff
- [ ] Cancellation API
- [ ] Comprehensive tests (≥80% coverage)
- [ ] Documentation update
- [ ] (Future) `HatchetTaskBackend` for distributed execution

### v0.3.0 (Planned)

- [ ] Cache warming strategies
- [ ] TTL policies per namespace
- [ ] Compression for large values

### Future

- [ ] Distributed cache coordination
- [ ] Cache invalidation patterns
- [ ] Event hooks for cache operations

---

## Examples Roadmap

| Example | Status | Description |
|---------|--------|-------------|
| `fastmcp-template` | ✅ Done | Starter template for FastMCP + mcp-refcache |
| `legal-mcp` | ⚪ Planned | Legal research server (Goal 01) |
| `faster-mcp` | ⚪ Research | Robyn-based FastMCP alternative (Goal 02) |

---

## Session Notes

_Use this space for current development session notes._

### 2024-12-28

- Created Goal 05: Real-Estate-Sustainability-MCP
  - Comprehensive sustainability analysis MCP server using fastmcp-template and mcp-refcache
  - Four core toolsets: Excel, PDF (with Chroma), sustainability frameworks, IFC integration
  - Supports ESG, LEED, BREEAM, and DGNB assessment frameworks
  - 7 tasks defined from cookiecutter generation to production deployment
  - Ready to begin implementation with Task-01: Generate project with fastmcp-template

### 2025-01-15

- Created Goal 04: Async-Timeout-Fallback (main feature for v0.2.0)
  - Feature request from yt-api-mcp semantic search experience
  - Long-running operations (1-2 min) cause MCP client timeouts
  - Solution: `async_timeout` param returns reference immediately, computation continues in background
  - 9 tasks defined: models, task tracking, decorator, polling, progress, retry, cancellation, tests, docs
  - Key decisions:
    - Integrate task tracking into RefCache (not separate TaskRegistry)
    - In-process asyncio.create_task() for MVP (external queue later)
    - Retryable failed tasks with configurable defaults
- Updated roadmap: v0.2.0 = Async Timeout Fallback

### 2026-01-19

- Goal 04: Hatchet SDK research complete
  - Cloned hatchet-dev/hatchet to `.agent/goals/04-Async-Timeout-Fallback/hatchet-reference/`
  - Analyzed `@hatchet.task()` decorator: input validators, timeouts, retries, rate limits
  - Key insight: Hatchet requires separate worker process, too complex for MVP
  - Decision: `TaskBackend` protocol with pluggable implementations
    - `MemoryTaskBackend` (ThreadPoolExecutor) — like document-mcp's JobManager
    - `HatchetTaskBackend` (Future) — optional `[hatchet]` extra
  - Task models already exist in `models.py`: TaskStatus, TaskProgress, TaskInfo, AsyncTaskResponse
  - Updated Goal 04 scratchpad with architecture, 11 tasks, sequence diagrams
  - document-mcp will consume this feature to replace its custom JobManager

### 2025-01-07

- Created Goals & Tasks structure in `.rules`
- Scaffolded Goal 01: Legal-MCP
  - Will port C# DejureMcp to Python/FastMCP
  - Multi-jurisdiction: German → EU → US law
- Scaffolded Goal 02: Faster-MCP
  - Research phase for Robyn-based FastMCP
  - Performance analysis from Blueshoe comparison article
