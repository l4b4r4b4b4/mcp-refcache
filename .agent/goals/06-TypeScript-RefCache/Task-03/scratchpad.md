# Task-03: Backend Protocol & MemoryBackend

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Define the `CacheBackend` interface (TypeScript protocol) and implement the `MemoryBackend` as the default in-memory cache storage with TTL support and LRU eviction.

---

## Context
The backend abstraction is fundamental to mcp-refcache's pluggable architecture. The Python implementation uses a `CacheBackend` protocol (duck-typed interface) with methods for get/set/delete/list operations. The TypeScript version will use a proper interface with async methods, enabling both in-memory and external storage backends.

The `MemoryBackend` is the simplest backend, storing entries in a Map with TTL-based expiration. It should be production-ready for single-process MCP servers while being the reference implementation for other backends.

## Acceptance Criteria
- [ ] `CacheBackend` interface defined with all required methods
- [ ] `CacheEntry` type for internal storage representation
- [ ] `MemoryBackend` class implementing the interface
- [ ] TTL-based automatic expiration
- [ ] Optional LRU eviction when max entries exceeded
- [ ] Thread-safe for concurrent access (async-safe)
- [ ] Namespace filtering for list operations
- [ ] Unit tests with 90%+ coverage
- [ ] JSDoc documentation for interface and implementation

---

## Approach
Port the Python `CacheBackend` protocol to a TypeScript interface, adapting method signatures for async/await patterns. Implement `MemoryBackend` using JavaScript's `Map` with periodic cleanup of expired entries.

### Steps

1. **Define CacheEntry type**
   - Value storage (any serializable data)
   - Metadata: namespace, key, policy, timestamps
   - TTL and expiration tracking

2. **Define CacheBackend interface**
   - `get(refId: string): Promise<CacheEntry | null>`
   - `set(entry: CacheEntry): Promise<void>`
   - `delete(refId: string): Promise<boolean>`
   - `exists(refId: string): Promise<boolean>`
   - `list(options?: ListOptions): Promise<CacheEntry[]>`
   - `clear(namespace?: string): Promise<number>`
   - `stats(): Promise<BackendStats>`

3. **Implement MemoryBackend**
   - Use `Map<string, CacheEntry>` for storage
   - Implement lazy expiration check on get
   - Optional background cleanup interval
   - LRU eviction using insertion order tracking

4. **Add configuration options**
   - `maxEntries`: Maximum entries before eviction
   - `cleanupInterval`: Background cleanup frequency
   - `defaultTtl`: Default TTL for entries without explicit TTL

5. **Write comprehensive tests**
   - Basic CRUD operations
   - TTL expiration behavior
   - LRU eviction
   - Namespace filtering
   - Concurrent access patterns

---

## Interface Design

```typescript
// src/backends/base.ts

import type { AccessPolicy } from '../models/access';

export interface CacheEntry {
  /** Unique reference ID (format: namespace:key or just key for public) */
  refId: string;
  /** Namespace for isolation (e.g., 'public', 'session:abc', 'user:123') */
  namespace: string;
  /** Original key within the namespace */
  key: string;
  /** The cached value (must be JSON-serializable) */
  value: unknown;
  /** Access control policy */
  policy: AccessPolicy;
  /** Creation timestamp */
  createdAt: Date;
  /** Last access timestamp */
  accessedAt: Date;
  /** Expiration timestamp (null = no expiration) */
  expiresAt: Date | null;
  /** Optional metadata */
  metadata?: Record<string, unknown>;
}

export interface ListOptions {
  /** Filter by namespace prefix */
  namespace?: string;
  /** Include expired entries */
  includeExpired?: boolean;
  /** Maximum entries to return */
  limit?: number;
  /** Offset for pagination */
  offset?: number;
}

export interface BackendStats {
  /** Total number of entries */
  totalEntries: number;
  /** Number of active (non-expired) entries */
  activeEntries: number;
  /** Number of expired entries pending cleanup */
  expiredEntries: number;
  /** Memory usage estimate in bytes (if available) */
  memoryBytes?: number;
  /** Backend-specific stats */
  extra?: Record<string, unknown>;
}

export interface CacheBackend {
  /** Retrieve an entry by refId, returns null if not found or expired */
  get(refId: string): Promise<CacheEntry | null>;

  /** Store an entry, overwrites if exists */
  set(entry: CacheEntry): Promise<void>;

  /** Delete an entry, returns true if existed */
  delete(refId: string): Promise<boolean>;

  /** Check if entry exists and is not expired */
  exists(refId: string): Promise<boolean>;

  /** List entries with optional filtering */
  list(options?: ListOptions): Promise<CacheEntry[]>;

  /** Clear entries, optionally by namespace. Returns count deleted */
  clear(namespace?: string): Promise<number>;

  /** Get backend statistics */
  stats(): Promise<BackendStats>;

  /** Close/cleanup backend resources */
  close(): Promise<void>;
}
```

---

## MemoryBackend Implementation

```typescript
// src/backends/memory.ts

import type { CacheBackend, CacheEntry, ListOptions, BackendStats } from './base';

export interface MemoryBackendOptions {
  /** Maximum number of entries (0 = unlimited) */
  maxEntries?: number;
  /** Cleanup interval in ms (0 = no background cleanup) */
  cleanupIntervalMs?: number;
  /** Enable LRU eviction when maxEntries exceeded */
  enableLru?: boolean;
}

export class MemoryBackend implements CacheBackend {
  private store: Map<string, CacheEntry> = new Map();
  private accessOrder: string[] = []; // For LRU tracking
  private cleanupTimer?: Timer;

  constructor(private options: MemoryBackendOptions = {}) {
    const { cleanupIntervalMs = 60000 } = options;
    if (cleanupIntervalMs > 0) {
      this.startCleanup(cleanupIntervalMs);
    }
  }

  async get(refId: string): Promise<CacheEntry | null> {
    const entry = this.store.get(refId);
    if (!entry) return null;

    // Check expiration
    if (this.isExpired(entry)) {
      this.store.delete(refId);
      return null;
    }

    // Update access time and LRU order
    entry.accessedAt = new Date();
    this.updateLruOrder(refId);

    return entry;
  }

  async set(entry: CacheEntry): Promise<void> {
    // Evict if at capacity
    if (this.options.maxEntries && this.store.size >= this.options.maxEntries) {
      if (this.options.enableLru) {
        this.evictLru();
      }
    }

    this.store.set(entry.refId, entry);
    this.updateLruOrder(entry.refId);
  }

  async delete(refId: string): Promise<boolean> {
    const existed = this.store.has(refId);
    this.store.delete(refId);
    this.removeFromLruOrder(refId);
    return existed;
  }

  async exists(refId: string): Promise<boolean> {
    const entry = this.store.get(refId);
    if (!entry) return false;
    if (this.isExpired(entry)) {
      this.store.delete(refId);
      return false;
    }
    return true;
  }

  async list(options: ListOptions = {}): Promise<CacheEntry[]> {
    const { namespace, includeExpired = false, limit, offset = 0 } = options;

    let entries = Array.from(this.store.values());

    // Filter by namespace
    if (namespace) {
      entries = entries.filter(e =>
        e.namespace === namespace || e.namespace.startsWith(`${namespace}:`)
      );
    }

    // Filter expired
    if (!includeExpired) {
      entries = entries.filter(e => !this.isExpired(e));
    }

    // Sort by creation time (newest first)
    entries.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());

    // Apply pagination
    if (limit !== undefined) {
      entries = entries.slice(offset, offset + limit);
    } else if (offset > 0) {
      entries = entries.slice(offset);
    }

    return entries;
  }

  async clear(namespace?: string): Promise<number> {
    if (!namespace) {
      const count = this.store.size;
      this.store.clear();
      this.accessOrder = [];
      return count;
    }

    let count = 0;
    for (const [refId, entry] of this.store) {
      if (entry.namespace === namespace || entry.namespace.startsWith(`${namespace}:`)) {
        this.store.delete(refId);
        this.removeFromLruOrder(refId);
        count++;
      }
    }
    return count;
  }

  async stats(): Promise<BackendStats> {
    let activeEntries = 0;
    let expiredEntries = 0;

    for (const entry of this.store.values()) {
      if (this.isExpired(entry)) {
        expiredEntries++;
      } else {
        activeEntries++;
      }
    }

    return {
      totalEntries: this.store.size,
      activeEntries,
      expiredEntries,
      extra: {
        maxEntries: this.options.maxEntries ?? 'unlimited',
        lruEnabled: this.options.enableLru ?? false,
      },
    };
  }

  async close(): Promise<void> {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
    }
    this.store.clear();
  }

  // Private helpers

  private isExpired(entry: CacheEntry): boolean {
    if (!entry.expiresAt) return false;
    return new Date() > entry.expiresAt;
  }

  private updateLruOrder(refId: string): void {
    this.removeFromLruOrder(refId);
    this.accessOrder.push(refId);
  }

  private removeFromLruOrder(refId: string): void {
    const index = this.accessOrder.indexOf(refId);
    if (index > -1) {
      this.accessOrder.splice(index, 1);
    }
  }

  private evictLru(): void {
    while (this.accessOrder.length > 0 && this.store.size >= (this.options.maxEntries ?? 0)) {
      const oldest = this.accessOrder.shift();
      if (oldest) {
        this.store.delete(oldest);
      }
    }
  }

  private startCleanup(intervalMs: number): void {
    this.cleanupTimer = setInterval(() => {
      for (const [refId, entry] of this.store) {
        if (this.isExpired(entry)) {
          this.store.delete(refId);
          this.removeFromLruOrder(refId);
        }
      }
    }, intervalMs);
  }
}
```

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with interface and implementation design |

### Design Decisions

1. **Async interface even for MemoryBackend**: While MemoryBackend operations are synchronous, the interface uses Promise returns for consistency with async backends (SQLite, Redis).

2. **Lazy expiration**: Entries are checked for expiration on access rather than strictly at expiration time. Background cleanup handles stale entries.

3. **LRU as optional**: LRU eviction adds overhead. For simple use cases, users may prefer to just set maxEntries without LRU tracking.

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | Required | Project must be initialized |
| Task-02: Models & Schemas | Required | CacheEntry depends on AccessPolicy type |

---

## Verification
_How to confirm this task is complete._

```bash
# Run backend tests
bun test tests/backends/

# Verify interface compliance
bun run typecheck

# Test coverage
bun test --coverage tests/backends/memory.test.ts
```

### Test Examples
```typescript
// tests/backends/memory.test.ts
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { MemoryBackend } from '../../src/backends/memory';
import { Permission } from '../../src/models/access';

describe('MemoryBackend', () => {
  let backend: MemoryBackend;

  beforeEach(() => {
    backend = new MemoryBackend({ cleanupIntervalMs: 0 });
  });

  afterEach(async () => {
    await backend.close();
  });

  it('stores and retrieves entries', async () => {
    const entry = createTestEntry('test-ref', 'test-key', { data: 'value' });
    await backend.set(entry);

    const result = await backend.get('test-ref');
    expect(result?.value).toEqual({ data: 'value' });
  });

  it('returns null for expired entries', async () => {
    const entry = createTestEntry('test-ref', 'test-key', 'value');
    entry.expiresAt = new Date(Date.now() - 1000); // Already expired
    await backend.set(entry);

    const result = await backend.get('test-ref');
    expect(result).toBeNull();
  });

  it('evicts LRU entries when at capacity', async () => {
    const backend = new MemoryBackend({ maxEntries: 2, enableLru: true });

    await backend.set(createTestEntry('ref1', 'k1', 'v1'));
    await backend.set(createTestEntry('ref2', 'k2', 'v2'));
    await backend.get('ref1'); // Access ref1 to make it more recent
    await backend.set(createTestEntry('ref3', 'k3', 'v3')); // Should evict ref2

    expect(await backend.exists('ref1')).toBe(true);
    expect(await backend.exists('ref2')).toBe(false);
    expect(await backend.exists('ref3')).toBe(true);
  });
});

function createTestEntry(refId: string, key: string, value: unknown) {
  return {
    refId,
    namespace: 'public',
    key,
    value,
    policy: { userPermissions: Permission.FULL, agentPermissions: Permission.READ },
    createdAt: new Date(),
    accessedAt: new Date(),
    expiresAt: null,
  };
}
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-02](../Task-02/scratchpad.md)
- **Blocks:** Task-04, Task-07, Task-08
- **External Links:**
  - [Python mcp-refcache backends/](https://github.com/l4b4r4b4b4/mcp-refcache/tree/main/src/mcp_refcache/backends)
  - [lru-cache npm package](https://github.com/isaacs/node-lru-cache)
