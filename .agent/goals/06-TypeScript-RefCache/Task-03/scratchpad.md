# Task-03: Backend Protocol & MemoryBackend

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [x] Complete 🟢

## Objective
Define the `CacheBackend` interface (TypeScript protocol) and implement the `MemoryBackend` as the default in-memory cache storage with TTL support and LRU eviction.

---

## Context
The backend abstraction is fundamental to mcp-refcache's pluggable architecture. The Python implementation uses a `CacheBackend` protocol (duck-typed interface) with methods for get/set/delete/list operations. The TypeScript version will use a proper interface with async methods, enabling both in-memory and external storage backends.

The `MemoryBackend` is the simplest backend, storing entries in a Map with TTL-based expiration. It should be production-ready for single-process MCP servers while being the reference implementation for other backends.

## Acceptance Criteria
- [x] `CacheBackend` interface defined with all required methods
- [x] `CacheEntry` type for internal storage representation (reused from Task-02 `src/models/cache.ts`)
- [x] `MemoryBackend` class implementing the interface
- [x] TTL-based automatic expiration (lazy eviction on access)
- [ ] ~~Optional LRU eviction when max entries exceeded~~ (deferred — not in Python source)
- [x] ~~Thread-safe for concurrent access~~ N/A — JS is single-threaded
- [x] Namespace filtering for clear and keys operations
- [x] Unit tests with 90%+ coverage (58 tests, 124 assertions)
- [x] JSDoc documentation for interface and implementation

---

## Approach
Direct port of Python's `CacheBackend` protocol and `MemoryBackend` to TypeScript. The interface is **synchronous** (not async) because `MemoryBackend` has no I/O and wrapping `Map` operations in `Promise` adds noise with zero benefit. The `CacheEntry` type from Task-02 (`src/models/cache.ts`) is reused directly — no separate type definition needed.

### Steps (Completed)

1. **Reuse CacheEntry from Task-02** ✅
   - `CacheEntry` and `isExpired()` already defined in `src/models/cache.ts`
   - No duplication needed

2. **Define CacheBackend interface** ✅ (`src/backends/types.ts`)
   - `get(key: string): CacheEntry | null`
   - `set(key: string, entry: CacheEntry): void`
   - `delete(key: string): boolean`
   - `exists(key: string): boolean`
   - `clear(namespace?: string): number`
   - `keys(namespace?: string): string[]`

3. **Implement MemoryBackend** ✅ (`src/backends/memory.ts`)
   - `Map<string, CacheEntry>` for storage
   - Lazy TTL eviction on `get()`, `exists()`, and `keys()`
   - No locking needed (JS is single-threaded, unlike Python's `threading.RLock`)

4. **Barrel & exports** ✅
   - `src/backends/index.ts` — barrel
   - `src/index.ts` — replaced TODO comments with real exports

5. **Comprehensive tests** ✅ (`tests/backends.test.ts`, 58 tests)
   - CacheEntry model tests (7 tests)
   - Protocol compliance (2 tests)
   - Basic CRUD operations (14 tests)
   - TTL expiration behavior (7 tests)
   - Namespace-scoped clear (5 tests)
   - Namespace-scoped keys (7 tests)
   - Interface contract tests (7 tests, extensible for future backends)
   - Edge cases (9 tests: special chars, 1000 entries, empty keys, etc.)

---

## Final Interface (as implemented)

```typescript
// src/backends/types.ts
import type { CacheEntry } from "../models/cache.js";

export interface CacheBackend {
  get(key: string): CacheEntry | null;
  set(key: string, entry: CacheEntry): void;
  delete(key: string): boolean;
  exists(key: string): boolean;
  clear(namespace?: string): number;
  keys(namespace?: string): string[];
}
```

Exact 1:1 mapping to Python's `CacheBackend` protocol. Synchronous, no `Promise` wrapping.

---

## MemoryBackend Implementation (as implemented)

```typescript
// src/backends/memory.ts
import type { CacheEntry } from "../models/cache.js";
import { isExpired } from "../models/cache.js";
import type { CacheBackend } from "./types.js";

export class MemoryBackend implements CacheBackend {
  private readonly storage: Map<string, CacheEntry> = new Map();

  get(key: string): CacheEntry | null { /* lazy eviction via isExpired() */ }
  set(key: string, entry: CacheEntry): void { /* Map.set() */ }
  delete(key: string): boolean { /* Map.delete() */ }
  exists(key: string): boolean { /* lazy eviction via isExpired() */ }
  clear(namespace?: string): number { /* full or namespace-scoped */ }
  keys(namespace?: string): string[] { /* filters expired + optional namespace */ }
}
```

Key differences from the pre-implementation design:
- **No LRU**: Not in the Python source, unnecessary complexity for v0.1.0
- **No background cleanup timer**: Lazy eviction is sufficient
- **No `close()` or `stats()`**: Not in the Python `CacheBackend` protocol
- **No constructor options**: Zero-config, matching Python's `MemoryBackend()`
- **Reuses `isExpired()` from models**: No private `isExpired` method needed

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with interface and implementation design |
| 2025-07-17 | Implemented and completed — 58 tests, all passing |

### Design Decisions

1. **Sync interface, not async**: The Python `CacheBackend` protocol is synchronous. `MemoryBackend` has no I/O. Wrapping `Map.get()` in `Promise.resolve()` adds noise with zero benefit. If async backends are needed later, a separate `AsyncCacheBackend` can be introduced (pre-1.0, no breaking-change concerns).

2. **Lazy expiration only**: Entries are checked for expiration on access (`get`, `exists`, `keys`). No background cleanup timer — it adds complexity (timer lifecycle, cleanup on close) for minimal benefit in a single-process MCP server.

3. **No LRU eviction**: The Python implementation doesn't have it. For v0.1.0, YAGNI. Can be added later if needed.

4. **Reuse CacheEntry from Task-02**: The `CacheEntry` Zod schema and `isExpired()` helper were already defined in `src/models/cache.ts`. No need to create a separate backend-specific entry type.

5. **Exact namespace matching**: `clear("ns")` only clears entries with `namespace === "ns"`, not `namespace.startsWith("ns")`. This matches the Python implementation exactly.

6. **Contract test pattern**: Tests include a `runContractTests()` helper that runs the same behavioral suite against any `CacheBackend` implementation. When SQLite/Redis backends are added, they just need one line to plug in.

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | ✅ Complete | Commit `a3fb939` |
| Task-02: Models & Schemas | ✅ Complete | Commit `9e3f049` — CacheEntry + isExpired reused |

---

## Verification
_How to confirm this task is complete._

```bash
# Run backend tests (58 pass, 0 fail)
cd packages/typescript && bun test tests/backends.test.ts

# Verify interface compliance (no errors)
cd packages/typescript && bunx tsc --noEmit

# Run full test suite (171 pass = 113 prev + 58 new)
cd packages/typescript && bun test

# Python tests still passing (718 pass)
cd packages/python && uv run pytest tests/ -q --tb=no
```

### Files Created
- `src/backends/types.ts` — `CacheBackend` interface (109 lines)
- `src/backends/memory.ts` — `MemoryBackend` class (187 lines)
- `src/backends/index.ts` — barrel (11 lines)
- `tests/backends.test.ts` — 58 tests (834 lines)

### Test Results
- **58 tests, 124 assertions, 0 failures**
- **171 total TS tests passing (61ms)**
- **718 Python tests still passing**

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md) ✅, [Task-02](../Task-02/scratchpad.md) ✅
- **Blocks:** Task-04, Task-07, Task-08
- **Python Source:**
  - `packages/python/src/mcp_refcache/backends/base.py` — CacheBackend protocol
  - `packages/python/src/mcp_refcache/backends/memory.py` — MemoryBackend
  - `packages/python/tests/test_backends.py` — Test reference
