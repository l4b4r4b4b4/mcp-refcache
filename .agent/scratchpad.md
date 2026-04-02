# mcp-refcache Development Scratchpad

## Current Status: v0.2.0 In Development 🟡

**Last Updated**: 2025-07-18

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
| 05 | [Real-Estate-Sustainability-MCP](./goals/05-Real-Estate-Sustainability-MCP/scratchpad.md) | ⚫ Superseded → 07, 08, 09 | - |
| 06 | [TypeScript-RefCache](./goals/06-TypeScript-RefCache/scratchpad.md) | 🟡 In Progress | P1 (High) |
| 07 | [RE-CapEx-OpEx-ROI-MCP](./goals/07-RE-CapEx-OpEx-ROI-MCP/scratchpad.md) | 🔴 Blocked (on 08) | P1 (High) |
| 08 | [BIM2Sim-MCP-Server](./goals/08-BIM2Sim-MCP-Server/scratchpad.md) | ⚪ Not Started | **P0 (Critical)** |
| 09 | [Parametric-Optimization-MCP](./goals/09-Parametric-Optimization-MCP/scratchpad.md) | 🔴 Blocked (on 07+08) | P2 (Medium) |
| 10 | [Release-Patch-Ref-Retrieval-Docs](./goals/10-Release-Patch-Ref-Retrieval-Docs/scratchpad.md) | 🟡 In Progress (Planning) | **P0 (Critical)** |

See [Goals Index](./goals/scratchpad.md) for full tracking.

### Goal Summaries

**01-Legal-MCP**: Comprehensive legal research MCP server with mcp-refcache integration. Starts with German law (dejure.org), expands to EU (EUR-Lex) and US law. Demonstrates real-world caching of large, stable legal documents.

**02-Faster-MCP**: Research feasibility of Robyn-based (Rust runtime) alternative to FastMCP. Motivated by 40x+ performance improvement potential (10k+ RPS vs ~246 RPS).

**04-Async-Task-Backends**: Add async task execution to `@cache.cached()` with pluggable backends. `TaskBackend` protocol enables `MemoryTaskBackend` (ThreadPoolExecutor, MVP) and future `HatchetTaskBackend` (distributed). When computations exceed `async_timeout`, returns reference immediately with "processing" status. Client polls for completion. **Tasks 01-05, 09 complete. 718 tests passing.** Next: Create minimal MCP server example, test in Zed, then release v0.2.0.

**06-TypeScript-RefCache**: Restructure repo into **Bun+Python monorepo** housing both implementations. Port `mcp-refcache` to TypeScript for Node.js MCP ecosystem. Target FastMCP (TypeScript) by @punkpeye. Full feature parity: RefCache, backends (Memory/SQLite/Redis), access control, preview system, async tasks. Plus companion `fastmcp-ts-template` (port of Python template). **Tasks 00–06 complete.** 596 TS tests passing (1331 assertions, 9.5s). Next: Task-07 (SQLite/Redis backends) or Task-09 (FastMCP integration). Primary reference: `fractal-agents-runtime` (`.agent/references/fractal-agents-runtime/`). Branch: `feat/monorepo-restructure`.

**08-BIM2Sim-MCP-Server** (**P0 — start here**): Factor bim2sim out of ifc-mcp into its own MCP server. Foundation layer — bottom-up build order means physics/energy simulation comes first, then financial model (07), then optimization (09). Wraps bim2sim (TEASER fast path + EnergyPlus detailed path) for building energy simulation. Multi-object/multi-system scenario support. DWD TRY weather data by PLZ. eMobility load curve simulation from iB-DOS AP 3.8. Async execution via mcp-refcache for long-running sims. 11 tasks defined.

**07-RE-CapEx-OpEx-ROI-MCP** (blocked on 08): Digital reimplementation of iB-DOS WAT (Wirtschaftlichkeitsanalysetool). DIN 276 CapEx (KG 100–700), BetrKV OpEx (all 17 Betriebskostenarten), energy cost model (kWh-based Arbeitspreis+Grundpreis per carrier), revenue model (Kaltmiete, Warmmiete, Mieterstrom, Fahrstrom), GuV engine (EBITDA→EBIT→EBT→EAT), NPV/IRR/Amortisation, sensitivity analysis. Pydantic data model constructible iteratively by agent MCP tools. WAT Excel reference files archived in `archive/ibdos-wat-reference/`. Data model design can proceed in parallel; validation needs Goal 08 output. 9 tasks defined.

**09-Parametric-Optimization-MCP** (blocked on 07+08): Multi-criteria parametric optimization across simulation + calculation. NSGA-II (pymoo) for Pareto front generation. Surrogate-assisted optimization (GP) to reduce simulation calls. Sobol sensitivity analysis (SALib). Varies building parameters (insulation, HVAC, PV, battery, building standard) against objectives (NPV, IRR, CO₂, tenant cost, primary energy). Capstone layer. 9 tasks defined.

**10-Release-Patch-Ref-Retrieval-Docs** (**P0 — in planning**): Patch release goal for `mcp-refcache` `0.2.1` to fix `full=True` retrieval discoverability and align retrieval behavior/docs across core and non-submodule examples. Scope includes: `@cache.cached()` injected doc updates, FastMCP instruction/guide updates, test hardening as doc contracts, non-submodule example parity (`full=True` + `max_size` forwarding), reusable prompt/doc asset optimizations, and release validation/version sync.

---

## Session Log (2025-07-18, Session 2)

### Completed This Session

1. **Task-04: RefCache Core + Resolution** ✅ (Commit: `6edf014`)
   - Discussed async vs sync RefCache design — decided async-only (matches CacheBackend interface, no breaking changes to 59 backend tests, idiomatic TS, future-proofs for Redis)
   - Created `src/resolution.ts` — `isRefId()`, `CircularReferenceError`, `ResolutionResult`, `RefResolver` (deep recursive async resolution with cycle detection), `resolveRefs()`, `resolveKwargs()`, `resolveArgsAndKwargs()` convenience functions. Opaque errors for security (missing vs permission denied are identical messages).
   - Created `src/cache.ts` — `RefCache` class with full CRUD: `set()`, `get()`, `resolve()`, `delete()`, `exists()`, `clear()`. SHA-256 ref ID generation (`cachename:hexhash`). Constructor injection for backend, measurer, tokenizer, preview generator, permission checker. Key-to-ref/ref-to-key bidirectional mappings. Auto-switch SampleGenerator→PaginateGenerator when page is specified. Hierarchical max_size (server default → per-call override). `setEntryValueForTesting()` for cycle detection tests.
   - Created `tests/resolution.test.ts` — 67 tests: isRefId (16), ResolutionResult (3), RefResolver (14), convenience functions (9), circular reference detection (6), security (4), edge cases (11), CircularReferenceError class (5)
   - Created `tests/cache.test.ts` — 122 tests: initialization (8), set (16), get (10), resolve (7), delete (6), exists (4), clear (4), TTL (5), namespaces (4), preview (4), context limiting (8), access control integration (21), pagination auto-switch (5), hierarchical maxSize (3), PreviewResult (3), edge cases (8), ref ID format (4)
   - Updated `src/index.ts` — barrel exports for RefCache, resolution module, all types/interfaces
   - Type checking: `bunx tsc --noEmit` clean
   - Full test suite: **596 TypeScript tests passing** (1331 assertions, 9.5s)
   - Python tests: **718 passing** (unaffected)

### Test Counts After This Session
| Test File | Tests | Assertions |
|-----------|-------|------------|
| `tests/index.test.ts` | 3 | 3 |
| `tests/models.test.ts` | 110 | 397 |
| `tests/backends.test.ts` | 59 | ~447 |
| `tests/context.test.ts` | 47 | 85 |
| `tests/preview.test.ts` | 53 | 155 |
| `tests/access.test.ts` | 135 | 310 |
| `tests/resolution.test.ts` | 67 | 165 |
| `tests/cache.test.ts` | 122 | 169 |
| **Total** | **596** | **1331** |

---

## Session Log (2025-07-18, Session 1)

### Completed This Session

1. **Task-05: Preview System & Context Layer** ✅ (Commit: `8363fcb`)
   - Ran `tests/context.test.ts` — all 47 tests pass (85 assertions), no fixes needed
   - Wrote `tests/preview.test.ts` — 53 tests (155 assertions) ported from Python `tests/test_preview.py`:
     - PreviewGenerator interface compliance (3 tests)
     - SampleGenerator: small/large list, evenly-spaced, dict, string, nested, empty, binary search, primitives (15 tests)
     - PaginateGenerator: first/middle/last page, dict, out-of-range, default page size, max_size trimming, empty, non-collection (10 tests)
     - TruncateGenerator: short unchanged, long truncated, list/dict stringified, empty, exact fit, metadata, primitives (11 tests)
     - getDefaultGenerator factory (5 tests)
     - Integration: cross-measurer, consistency, all strategies respect max_size, first/last preservation (9 tests)

2. **Task-06: Access Control System** ✅ (Commit: `7f147c6`)
   - Created `src/access/actor.ts` — `Actor` interface, `DefaultActor` class (immutable, frozen), factory methods (user, agent, system, fromLiteral), glob pattern matching, `resolveActor()`, `ActorLike` type
   - Created `src/access/namespace.ts` — `NamespaceInfo` class, `NamespaceResolver` interface, `DefaultNamespaceResolver` (public, session, user, agent, shared patterns)
   - Created `src/access/checker.ts` — `PermissionDenied` error, `PermissionChecker` interface, `DefaultPermissionChecker` with 6-step resolution (explicit deny → session binding → namespace ownership → explicit allow → owner permissions → role-based), `permissionNames()` helper
   - Created `src/access/index.ts` — barrel exports
   - Updated `src/index.ts` — replaced TODO access control comments with real exports
   - Wrote `tests/access.test.ts` — 135 tests (310 assertions) porting 3 Python test files
   - Reuses Permission, AccessPolicy, ActorType, policy presets from Task-02 models
   - Full test suite: **407 TypeScript tests passing** (997 assertions, 3.79s)
   - Python tests: **718 passing** (unaffected)
   - Type checking: `bunx tsc --noEmit` clean
   - Updated Task-06 scratchpad → 🟢 Complete
   - Updated goal scratchpad task table → Task-06 🟢

### Test Counts After Session 1
| Test File | Tests | Assertions |
|-----------|-------|------------|
| `tests/index.test.ts` | 3 | 3 |
| `tests/models.test.ts` | 110 | 397 |
| `tests/backends.test.ts` | 59 | ~447 |
| `tests/context.test.ts` | 47 | 85 |
| `tests/preview.test.ts` | 53 | 155 |
| `tests/access.test.ts` | 135 | 310 |
| **Total** | **407** | **997** |

---

## Session Log (2025-07-17)

### Completed This Session

1. **Task-03: Backend Protocol & MemoryBackend** ✅ (Commit: `c2394d2`)
   - Created `CacheBackend` interface (`src/backends/types.ts`) — 6 async methods matching Python protocol
   - Created `MemoryBackend` class (`src/backends/memory.ts`) — `Map<string, CacheEntry>` with lazy TTL eviction
   - All methods return `Promise<T>` for uniform sync/async backend support (Redis, SQLite)
   - Reuses `CacheEntry` and `isExpired()` from Task-02's `src/models/cache.ts`
   - 59 tests (`tests/backends.test.ts`), 447 assertions
   - **Total: 172 TS tests passing (62ms), 718 Python tests still passing**

2. **Task-05: Preview System & Context Layer** ✅ (Committed in next session as `8363fcb`)
   - All source files created, typecheck passes
   - Context tests written (not yet run), preview tests not yet written
   - See session log 2025-07-18 for completion details

### Files Created (Task-03)
- `packages/typescript/src/backends/types.ts` — `CacheBackend` async interface
- `packages/typescript/src/backends/memory.ts` — `MemoryBackend` class
- `packages/typescript/src/backends/index.ts` — barrel
- `packages/typescript/tests/backends.test.ts` — 59 tests

### Files Created (Task-05, committed `8363fcb` in next session)
- `packages/typescript/src/context/` — types, tokenizers, measurers, barrel (4 files)
- `packages/typescript/src/preview/` — types, generators, barrel (3 files)
- `packages/typescript/tests/context.test.ts` — 47 tests (473 lines)
- `packages/typescript/tests/preview.test.ts` — 53 tests (659 lines)

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
Continue mcp-refcache: Post Task-04 — Commit & Next Steps

## Context
- Goal 06: Porting mcp-refcache to TypeScript/Bun (polyglot monorepo)
- Tasks 00–06 ALL complete. 596 TS tests passing (1331 assertions). 718 Python tests passing.
- Branch: `feat/monorepo-restructure`
- See `.agent/scratchpad.md` for full session log
- See `.agent/goals/06-TypeScript-RefCache/scratchpad.md` for goal details

## What Was Done
- Task-04 ✅: RefCache Core + Resolution (NOT YET COMMITTED)
  - `src/resolution.ts` — isRefId, CircularReferenceError, RefResolver, resolveRefs/Kwargs/ArgsAndKwargs
  - `src/cache.ts` — RefCache class (set/get/resolve/delete/exists/clear, SHA-256 ref IDs, async)
  - `tests/resolution.test.ts` — 67 tests
  - `tests/cache.test.ts` — 122 tests
  - `src/index.ts` — barrel exports updated
  - `bunx tsc --noEmit` clean
- All prior tasks: 00 (monorepo), 01 (setup), 02 (models), 03 (backend), 05 (preview), 06 (access control)

## Immediate TODO
1. **Commit Task-04** — `git add . && git commit -m "feat(ts): implement RefCache core and resolution module (Task-04)"`
2. **Update goal scratchpad** — Mark Task-04 🟢 in the goal task table
3. **Decide next task** — Options:
   - Task-07: SQLite + Redis backends (persistent storage)
   - Task-08: Async task backend (background execution)
   - Task-09: FastMCP integration (MCP server template)
   - Task-10: npm package publishing

## Key Files
- `packages/typescript/src/cache.ts` — RefCache class
- `packages/typescript/src/resolution.ts` — Resolution utilities
- `packages/typescript/tests/cache.test.ts` — 122 cache tests
- `packages/typescript/tests/resolution.test.ts` — 67 resolution tests

## Guidelines
- Follow `.rules` (TDD, run `bun test` after changes, `bunx tsc --noEmit`)
- Don't break existing 596 TS tests or 718 Python tests
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
