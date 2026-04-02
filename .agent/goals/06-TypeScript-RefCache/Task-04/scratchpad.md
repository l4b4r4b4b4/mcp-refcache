# Task-04: RefCache Core Implementation

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Implement the main `RefCache` class that provides the primary API for caching values, managing references, and integrating with backends. This is the central component that users interact with directly.

---

## Context
The `RefCache` class is the heart of the library, orchestrating:
- Value storage with automatic reference ID generation
- Preview generation for large values
- Access control enforcement
- Backend abstraction
- Namespace management

The Python implementation's `RefCache` class (~1200 lines) handles all these concerns. The TypeScript version should be cleaner with better separation of concerns while maintaining API compatibility.

## Acceptance Criteria
- [ ] `RefCache` class with configurable options
- [ ] `set()` method - store value, return `CacheReference`
- [ ] `get()` method - retrieve `CacheResponse` with preview/pagination
- [ ] `resolve()` method - get full value with permission check
- [ ] `delete()` method - remove entry
- [ ] `exists()` method - check entry existence
- [ ] `clear()` method - clear entries by namespace
- [ ] Automatic reference ID generation (nanoid-based)
- [ ] TTL support with expiration calculation
- [ ] Integration with preview system
- [ ] Integration with access control
- [ ] Comprehensive unit tests (90%+ coverage)
- [ ] JSDoc documentation with examples

---

## Approach
Build the RefCache class incrementally, starting with basic CRUD operations, then adding preview generation, access control, and advanced features. Use dependency injection for backend, preview generator, and permission checker.

### Steps

1. **Define RefCache options interface**
   - Name, backend, default policy, default TTL
   - Preview config, tokenizer/measurer
   - Permission checker

2. **Implement constructor**
   - Initialize with defaults
   - Create MemoryBackend if none provided
   - Set up preview generator

3. **Implement `set()` method**
   - Generate unique refId using nanoid
   - Calculate expiration from TTL
   - Create CacheEntry with metadata
   - Store via backend
   - Return CacheReference with preview

4. **Implement `get()` method**
   - Retrieve entry from backend
   - Check existence and expiration
   - Generate preview if value is large
   - Return CacheResponse with pagination info

5. **Implement `resolve()` method**
   - Retrieve entry from backend
   - Check permissions for actor
   - Return full value or throw PermissionDenied

6. **Implement helper methods**
   - `delete()`, `exists()`, `clear()`
   - `stats()` for cache statistics

7. **Add reference ID utilities**
   - `isRefId()` - detect if string is a reference
   - `parseRefId()` - extract namespace and key

8. **Write comprehensive tests**

---

## API Design

```typescript
// src/cache.ts

import { nanoid } from 'nanoid';
import type { CacheBackend, CacheEntry } from './backends/base';
import { MemoryBackend } from './backends/memory';
import type { AccessPolicy, Actor } from './models/access';
import type { CacheReference, CacheResponse, PreviewConfig } from './models';
import type { PreviewGenerator } from './preview';
import type { PermissionChecker } from './access/checker';

export interface RefCacheOptions {
  /** Cache instance name */
  name?: string;
  /** Storage backend (default: MemoryBackend) */
  backend?: CacheBackend;
  /** Default access policy for new entries */
  defaultPolicy?: AccessPolicy;
  /** Default TTL in seconds (null = no expiration) */
  defaultTtl?: number | null;
  /** Preview generation configuration */
  previewConfig?: PreviewConfig;
  /** Preview generator instance */
  previewGenerator?: PreviewGenerator;
  /** Permission checker for access control */
  permissionChecker?: PermissionChecker;
}

export interface SetOptions {
  /** Override namespace (default: 'public') */
  namespace?: string;
  /** Override access policy */
  policy?: AccessPolicy;
  /** Override TTL in seconds */
  ttl?: number | null;
  /** Custom key (default: auto-generated) */
  key?: string;
  /** Additional metadata */
  metadata?: Record<string, unknown>;
}

export interface GetOptions {
  /** Actor performing the get (for permission check) */
  actor?: Actor;
  /** Page number for pagination (1-indexed) */
  page?: number;
  /** Items per page */
  pageSize?: number;
  /** Max preview size (overrides config) */
  maxSize?: number;
}

export interface ResolveOptions {
  /** Actor performing the resolve */
  actor?: Actor;
}

export class RefCache {
  readonly name: string;
  private backend: CacheBackend;
  private defaultPolicy: AccessPolicy;
  private defaultTtl: number | null;
  private previewConfig: PreviewConfig;
  private previewGenerator: PreviewGenerator;
  private permissionChecker: PermissionChecker;

  constructor(options: RefCacheOptions = {}) {
    this.name = options.name ?? 'default';
    this.backend = options.backend ?? new MemoryBackend();
    this.defaultPolicy = options.defaultPolicy ?? AccessPolicy.public();
    this.defaultTtl = options.defaultTtl ?? 3600;
    this.previewConfig = options.previewConfig ?? PreviewConfig.default();
    this.previewGenerator = options.previewGenerator ?? new TruncateGenerator();
    this.permissionChecker = options.permissionChecker ?? new DefaultPermissionChecker();
  }

  /**
   * Store a value and return a reference.
   *
   * @example
   * ```typescript
   * const ref = await cache.set('user_data', { name: 'Alice', items: [1,2,3] });
   * console.log(ref.refId); // 'public:abc123'
   * ```
   */
  async set(key: string, value: unknown, options: SetOptions = {}): Promise<CacheReference> {
    const namespace = options.namespace ?? 'public';
    const policy = options.policy ?? this.defaultPolicy;
    const ttl = options.ttl !== undefined ? options.ttl : this.defaultTtl;

    const refId = this.generateRefId(namespace, options.key ?? key);
    const now = new Date();
    const expiresAt = ttl !== null ? new Date(now.getTime() + ttl * 1000) : null;

    const entry: CacheEntry = {
      refId,
      namespace,
      key: options.key ?? key,
      value,
      policy,
      createdAt: now,
      accessedAt: now,
      expiresAt,
      metadata: options.metadata,
    };

    await this.backend.set(entry);

    // Generate preview
    const preview = await this.previewGenerator.generate(value, this.previewConfig);

    return {
      refId,
      namespace,
      key: entry.key,
      preview: preview.text,
      totalItems: preview.totalItems,
      expiresAt,
      createdAt: now,
    };
  }

  /**
   * Get a cached response with preview and pagination.
   *
   * @example
   * ```typescript
   * const response = await cache.get('public:abc123');
   * console.log(response.preview); // '[1, 2, 3, ... and 97 more]'
   * ```
   */
  async get(refId: string, options: GetOptions = {}): Promise<CacheResponse | null> {
    const entry = await this.backend.get(refId);
    if (!entry) return null;

    // Check read permission if actor provided
    if (options.actor) {
      this.permissionChecker.checkRead(entry.policy, options.actor);
    }

    // Generate preview with optional pagination
    const previewOptions = {
      ...this.previewConfig,
      maxSize: options.maxSize ?? this.previewConfig.maxSize,
      page: options.page,
      pageSize: options.pageSize,
    };

    const preview = await this.previewGenerator.generate(entry.value, previewOptions);

    return {
      refId: entry.refId,
      namespace: entry.namespace,
      key: entry.key,
      preview: preview.text,
      totalItems: preview.totalItems,
      currentPage: preview.currentPage,
      totalPages: preview.totalPages,
      hasMore: preview.hasMore,
      createdAt: entry.createdAt,
      expiresAt: entry.expiresAt,
    };
  }

  /**
   * Resolve a reference to get the full value.
   * Requires appropriate permissions for the actor.
   *
   * @example
   * ```typescript
   * const data = await cache.resolve('public:abc123');
   * console.log(data); // { name: 'Alice', items: [1,2,3,...] }
   * ```
   */
  async resolve(refId: string, options: ResolveOptions = {}): Promise<unknown> {
    const entry = await this.backend.get(refId);
    if (!entry) {
      throw new Error(`Reference not found: ${refId}`);
    }

    // Check read permission
    const actor = options.actor ?? Actor.system();
    this.permissionChecker.checkRead(entry.policy, actor);

    return entry.value;
  }

  /**
   * Delete a cached entry.
   */
  async delete(refId: string, actor?: Actor): Promise<boolean> {
    if (actor) {
      const entry = await this.backend.get(refId);
      if (entry) {
        this.permissionChecker.checkDelete(entry.policy, actor);
      }
    }
    return this.backend.delete(refId);
  }

  /**
   * Check if a reference exists and is not expired.
   */
  async exists(refId: string): Promise<boolean> {
    return this.backend.exists(refId);
  }

  /**
   * Clear entries, optionally filtered by namespace.
   */
  async clear(namespace?: string): Promise<number> {
    return this.backend.clear(namespace);
  }

  /**
   * Get cache statistics.
   */
  async stats() {
    return this.backend.stats();
  }

  /**
   * Close the cache and release resources.
   */
  async close(): Promise<void> {
    await this.backend.close();
  }

  // Private helpers

  private generateRefId(namespace: string, key: string): string {
    const uniquePart = nanoid(12);
    return namespace === 'public'
      ? `${key}:${uniquePart}`
      : `${namespace}:${key}:${uniquePart}`;
  }
}

// Utility functions

/**
 * Check if a string looks like a reference ID.
 */
export function isRefId(value: string): boolean {
  // RefIds contain at least one colon and end with nanoid-like characters
  return typeof value === 'string' &&
         value.includes(':') &&
         /^[a-zA-Z0-9_:-]+$/.test(value);
}

/**
 * Parse a reference ID into its components.
 */
export function parseRefId(refId: string): { namespace: string; key: string } | null {
  const parts = refId.split(':');
  if (parts.length < 2) return null;

  // Last part is the unique ID, rest is namespace:key
  const uniquePart = parts.pop();
  if (!uniquePart) return null;

  if (parts.length === 1) {
    // Format: key:uniquePart (public namespace)
    return { namespace: 'public', key: parts[0]! };
  }

  // Format: namespace:key:uniquePart or namespace:subns:key:uniquePart
  const namespace = parts[0]!;
  const key = parts.slice(1).join(':');
  return { namespace, key };
}
```

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with API design |

### Design Decisions

1. **Reference ID format**: Using `namespace:key:nanoid` for uniqueness and parseability. Public namespace omits the namespace prefix for cleaner IDs.

2. **Lazy permission checking**: Permissions are only checked when an actor is provided. This allows internal operations to bypass checks while ensuring user-facing operations are secure.

3. **Preview on set**: Generating preview during `set()` allows returning it immediately in the `CacheReference`. This avoids recomputation on `get()`.

4. **Dependency injection**: All major components (backend, preview generator, permission checker) are injectable for testing and customization.

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | Required | Project structure needed |
| Task-02: Models & Schemas | Required | CacheReference, CacheResponse types |
| Task-03: Backend Protocol | Required | CacheBackend interface, MemoryBackend |
| Task-05: Preview System | Partial | Can stub initially, full integration later |
| Task-06: Access Control | Partial | Can stub initially, full integration later |

---

## Commands & Snippets

### Test Example
```typescript
// tests/cache.test.ts
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { RefCache, isRefId, parseRefId } from '../src/cache';

describe('RefCache', () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: 'test', defaultTtl: 60 });
  });

  afterEach(async () => {
    await cache.close();
  });

  describe('set()', () => {
    it('stores value and returns reference', async () => {
      const ref = await cache.set('user', { name: 'Alice' });

      expect(ref.refId).toContain('user');
      expect(ref.namespace).toBe('public');
      expect(ref.preview).toBeDefined();
    });

    it('respects custom namespace', async () => {
      const ref = await cache.set('data', [1, 2, 3], {
        namespace: 'session:abc'
      });

      expect(ref.namespace).toBe('session:abc');
      expect(ref.refId).toContain('session:abc');
    });
  });

  describe('get()', () => {
    it('retrieves stored value with preview', async () => {
      const ref = await cache.set('items', [1, 2, 3, 4, 5]);
      const response = await cache.get(ref.refId);

      expect(response).not.toBeNull();
      expect(response?.preview).toBeDefined();
      expect(response?.totalItems).toBe(5);
    });

    it('returns null for non-existent reference', async () => {
      const response = await cache.get('nonexistent:abc123');
      expect(response).toBeNull();
    });
  });

  describe('resolve()', () => {
    it('returns full value', async () => {
      const original = { name: 'Alice', items: [1, 2, 3] };
      const ref = await cache.set('data', original);

      const value = await cache.resolve(ref.refId);
      expect(value).toEqual(original);
    });

    it('throws for non-existent reference', async () => {
      await expect(cache.resolve('nonexistent:abc'))
        .rejects.toThrow('Reference not found');
    });
  });

  describe('delete()', () => {
    it('removes entry and returns true', async () => {
      const ref = await cache.set('temp', 'data');

      const deleted = await cache.delete(ref.refId);
      expect(deleted).toBe(true);

      const exists = await cache.exists(ref.refId);
      expect(exists).toBe(false);
    });
  });
});

describe('isRefId()', () => {
  it('returns true for valid ref IDs', () => {
    expect(isRefId('user:abc123')).toBe(true);
    expect(isRefId('session:xyz:data:abc123')).toBe(true);
  });

  it('returns false for invalid strings', () => {
    expect(isRefId('just-a-string')).toBe(false);
    expect(isRefId('')).toBe(false);
  });
});

describe('parseRefId()', () => {
  it('parses public namespace refs', () => {
    const result = parseRefId('user:abc123');
    expect(result).toEqual({ namespace: 'public', key: 'user' });
  });

  it('parses namespaced refs', () => {
    const result = parseRefId('session:xyz:data:abc123');
    expect(result).toEqual({ namespace: 'session', key: 'xyz:data' });
  });
});
```

---

## Verification
_How to confirm this task is complete._

```bash
# Run RefCache tests
bun test tests/cache.test.ts

# Verify type checking
bun run typecheck

# Test coverage
bun test --coverage tests/cache.test.ts

# Integration smoke test
bun run -e "
import { RefCache } from './src';
const cache = new RefCache();
const ref = await cache.set('test', { hello: 'world' });
console.log('Stored:', ref.refId);
const value = await cache.resolve(ref.refId);
console.log('Retrieved:', value);
await cache.close();
"
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-02](../Task-02/scratchpad.md), [Task-03](../Task-03/scratchpad.md)
- **Partial Dependencies:** Task-05 (Preview), Task-06 (Access Control)
- **Blocks:** Task-08 (Async Tasks), Task-09 (FastMCP Integration)
- **External Links:**
  - [Python mcp-refcache cache.py](https://github.com/l4b4r4b4b4/mcp-refcache/blob/main/src/mcp_refcache/cache.py)
  - [nanoid](https://github.com/ai/nanoid)
