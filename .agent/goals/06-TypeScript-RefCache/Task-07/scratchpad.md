# Task-07: SQLite & Redis Backends

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Implement the `SQLiteBackend` and `RedisBackend` storage backends to enable persistent and distributed caching scenarios beyond the in-memory `MemoryBackend`.

---

## Context
While `MemoryBackend` is perfect for single-process MCP servers, real-world deployments often need:

1. **SQLite**: Persistent storage that survives process restarts, shareable across processes on the same machine. Excellent for local development and single-server production.

2. **Redis**: Distributed caching for multi-server deployments, microservices architectures, or when caching needs to be shared across different MCP servers.

Bun provides native SQLite support via `bun:sqlite`, making it an ideal choice. For Redis, `ioredis` is the most popular and feature-rich client for Node.js/Bun.

## Acceptance Criteria
- [ ] `SQLiteBackend` implementing `CacheBackend` interface
- [ ] SQLite schema with proper indexes
- [ ] Automatic schema migration on startup
- [ ] TTL-based expiration handled via cleanup query
- [ ] Works with both Bun native SQLite and `better-sqlite3` for Node.js
- [ ] `RedisBackend` implementing `CacheBackend` interface
- [ ] Redis key patterns for namespace isolation
- [ ] TTL handled via Redis native EXPIRE
- [ ] Connection pooling and reconnection handling
- [ ] JSON serialization for complex values
- [ ] Unit tests for both backends
- [ ] Integration tests with real SQLite and Redis
- [ ] Optional dependencies (Redis only when needed)

---

## Approach
Implement each backend following the `CacheBackend` interface established in Task-03. Use feature detection to support both Bun's native SQLite and `better-sqlite3` for Node.js compatibility.

### Steps

1. **SQLite Schema Design**
   - Define table structure with indexes
   - Store value as JSON blob
   - Store policy as JSON blob
   - Index on namespace for filtering

2. **Implement SQLiteBackend**
   - Constructor with database path option
   - Auto-create table on initialization
   - Implement all CacheBackend methods
   - Handle TTL via expiration column and cleanup

3. **Add Bun/Node.js compatibility layer**
   - Detect runtime (Bun vs Node.js)
   - Use `bun:sqlite` when available
   - Fallback to `better-sqlite3` for Node.js

4. **Redis Key Design**
   - Key pattern: `refcache:{namespace}:{key}:{uniqueId}`
   - Use HSET for structured storage
   - Use EXPIRE for TTL

5. **Implement RedisBackend**
   - Constructor with Redis connection options
   - Connection lifecycle management
   - Implement all CacheBackend methods
   - Handle serialization/deserialization

6. **Write tests**
   - Unit tests with mocked backends
   - Integration tests with real databases

---

## SQLite Implementation

### Schema
```sql
CREATE TABLE IF NOT EXISTS cache_entries (
  ref_id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,  -- JSON serialized
  policy TEXT NOT NULL, -- JSON serialized
  created_at INTEGER NOT NULL,
  accessed_at INTEGER NOT NULL,
  expires_at INTEGER,   -- NULL = no expiration
  metadata TEXT         -- JSON serialized, optional
);

CREATE INDEX IF NOT EXISTS idx_namespace ON cache_entries(namespace);
CREATE INDEX IF NOT EXISTS idx_expires_at ON cache_entries(expires_at) WHERE expires_at IS NOT NULL;
```

### SQLiteBackend
```typescript
// src/backends/sqlite.ts

import type { CacheBackend, CacheEntry, ListOptions, BackendStats } from './base';

export interface SQLiteBackendOptions {
  /** Path to SQLite database file (default: ':memory:') */
  path?: string;
  /** Cleanup interval in ms (default: 60000, 0 = disabled) */
  cleanupIntervalMs?: number;
}

export class SQLiteBackend implements CacheBackend {
  private db: any; // bun:sqlite or better-sqlite3
  private cleanupTimer?: Timer;

  constructor(private options: SQLiteBackendOptions = {}) {
    this.db = this.openDatabase(options.path ?? ':memory:');
    this.initSchema();

    const { cleanupIntervalMs = 60000 } = options;
    if (cleanupIntervalMs > 0) {
      this.startCleanup(cleanupIntervalMs);
    }
  }

  private openDatabase(path: string) {
    // Try Bun's native SQLite first
    if (typeof Bun !== 'undefined') {
      const { Database } = require('bun:sqlite');
      return new Database(path);
    }
    // Fallback to better-sqlite3 for Node.js
    const Database = require('better-sqlite3');
    return new Database(path);
  }

  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS cache_entries (
        ref_id TEXT PRIMARY KEY,
        namespace TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        policy TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        accessed_at INTEGER NOT NULL,
        expires_at INTEGER,
        metadata TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_namespace ON cache_entries(namespace);
      CREATE INDEX IF NOT EXISTS idx_expires_at ON cache_entries(expires_at) WHERE expires_at IS NOT NULL;
    `);
  }

  async get(refId: string): Promise<CacheEntry | null> {
    const row = this.db.prepare(
      'SELECT * FROM cache_entries WHERE ref_id = ? AND (expires_at IS NULL OR expires_at > ?)'
    ).get(refId, Date.now());

    if (!row) return null;

    // Update accessed_at
    this.db.prepare('UPDATE cache_entries SET accessed_at = ? WHERE ref_id = ?')
      .run(Date.now(), refId);

    return this.rowToEntry(row);
  }

  async set(entry: CacheEntry): Promise<void> {
    this.db.prepare(`
      INSERT OR REPLACE INTO cache_entries
      (ref_id, namespace, key, value, policy, created_at, accessed_at, expires_at, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      entry.refId,
      entry.namespace,
      entry.key,
      JSON.stringify(entry.value),
      JSON.stringify(entry.policy),
      entry.createdAt.getTime(),
      entry.accessedAt.getTime(),
      entry.expiresAt?.getTime() ?? null,
      entry.metadata ? JSON.stringify(entry.metadata) : null
    );
  }

  async delete(refId: string): Promise<boolean> {
    const result = this.db.prepare('DELETE FROM cache_entries WHERE ref_id = ?').run(refId);
    return result.changes > 0;
  }

  async exists(refId: string): Promise<boolean> {
    const row = this.db.prepare(
      'SELECT 1 FROM cache_entries WHERE ref_id = ? AND (expires_at IS NULL OR expires_at > ?)'
    ).get(refId, Date.now());
    return !!row;
  }

  async list(options: ListOptions = {}): Promise<CacheEntry[]> {
    const { namespace, includeExpired = false, limit, offset = 0 } = options;

    let query = 'SELECT * FROM cache_entries WHERE 1=1';
    const params: any[] = [];

    if (namespace) {
      query += ' AND (namespace = ? OR namespace LIKE ?)';
      params.push(namespace, `${namespace}:%`);
    }

    if (!includeExpired) {
      query += ' AND (expires_at IS NULL OR expires_at > ?)';
      params.push(Date.now());
    }

    query += ' ORDER BY created_at DESC';

    if (limit !== undefined) {
      query += ' LIMIT ? OFFSET ?';
      params.push(limit, offset);
    } else if (offset > 0) {
      query += ' LIMIT -1 OFFSET ?';
      params.push(offset);
    }

    const rows = this.db.prepare(query).all(...params);
    return rows.map((row: any) => this.rowToEntry(row));
  }

  async clear(namespace?: string): Promise<number> {
    if (!namespace) {
      const result = this.db.prepare('DELETE FROM cache_entries').run();
      return result.changes;
    }

    const result = this.db.prepare(
      'DELETE FROM cache_entries WHERE namespace = ? OR namespace LIKE ?'
    ).run(namespace, `${namespace}:%`);
    return result.changes;
  }

  async stats(): Promise<BackendStats> {
    const now = Date.now();

    const total = this.db.prepare('SELECT COUNT(*) as count FROM cache_entries').get();
    const active = this.db.prepare(
      'SELECT COUNT(*) as count FROM cache_entries WHERE expires_at IS NULL OR expires_at > ?'
    ).get(now);

    return {
      totalEntries: total.count,
      activeEntries: active.count,
      expiredEntries: total.count - active.count,
      extra: {
        path: this.options.path ?? ':memory:',
      },
    };
  }

  async close(): Promise<void> {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
    }
    this.db.close();
  }

  private rowToEntry(row: any): CacheEntry {
    return {
      refId: row.ref_id,
      namespace: row.namespace,
      key: row.key,
      value: JSON.parse(row.value),
      policy: JSON.parse(row.policy),
      createdAt: new Date(row.created_at),
      accessedAt: new Date(row.accessed_at),
      expiresAt: row.expires_at ? new Date(row.expires_at) : null,
      metadata: row.metadata ? JSON.parse(row.metadata) : undefined,
    };
  }

  private startCleanup(intervalMs: number): void {
    this.cleanupTimer = setInterval(() => {
      this.db.prepare('DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at <= ?')
        .run(Date.now());
    }, intervalMs);
  }
}
```

---

## Redis Implementation

### Key Patterns
```
refcache:{refId} -> HASH {
  namespace: string
  key: string
  value: JSON string
  policy: JSON string
  createdAt: timestamp
  accessedAt: timestamp
  metadata: JSON string (optional)
}
refcache:ns:{namespace} -> SET of refIds (for namespace queries)
```

### RedisBackend
```typescript
// src/backends/redis.ts

import type { CacheBackend, CacheEntry, ListOptions, BackendStats } from './base';
import Redis from 'ioredis';

export interface RedisBackendOptions {
  /** Redis connection URL or options */
  url?: string;
  /** Redis options (passed to ioredis) */
  redis?: Redis.RedisOptions;
  /** Key prefix (default: 'refcache') */
  prefix?: string;
}

export class RedisBackend implements CacheBackend {
  private client: Redis;
  private prefix: string;

  constructor(options: RedisBackendOptions = {}) {
    this.prefix = options.prefix ?? 'refcache';

    if (options.url) {
      this.client = new Redis(options.url);
    } else {
      this.client = new Redis(options.redis);
    }
  }

  private entryKey(refId: string): string {
    return `${this.prefix}:entry:${refId}`;
  }

  private namespaceSetKey(namespace: string): string {
    return `${this.prefix}:ns:${namespace}`;
  }

  async get(refId: string): Promise<CacheEntry | null> {
    const data = await this.client.hgetall(this.entryKey(refId));
    if (!data || Object.keys(data).length === 0) return null;

    // Update accessed_at
    await this.client.hset(this.entryKey(refId), 'accessedAt', Date.now().toString());

    return this.dataToEntry(refId, data);
  }

  async set(entry: CacheEntry): Promise<void> {
    const key = this.entryKey(entry.refId);

    await this.client.hset(key, {
      namespace: entry.namespace,
      key: entry.key,
      value: JSON.stringify(entry.value),
      policy: JSON.stringify(entry.policy),
      createdAt: entry.createdAt.getTime().toString(),
      accessedAt: entry.accessedAt.getTime().toString(),
      metadata: entry.metadata ? JSON.stringify(entry.metadata) : '',
    });

    // Set TTL if expires_at is set
    if (entry.expiresAt) {
      const ttlMs = entry.expiresAt.getTime() - Date.now();
      if (ttlMs > 0) {
        await this.client.pexpire(key, ttlMs);
      }
    }

    // Add to namespace set for list queries
    await this.client.sadd(this.namespaceSetKey(entry.namespace), entry.refId);
  }

  async delete(refId: string): Promise<boolean> {
    // Get entry to find namespace for cleanup
    const data = await this.client.hgetall(this.entryKey(refId));
    if (data && data.namespace) {
      await this.client.srem(this.namespaceSetKey(data.namespace), refId);
    }

    const result = await this.client.del(this.entryKey(refId));
    return result > 0;
  }

  async exists(refId: string): Promise<boolean> {
    return (await this.client.exists(this.entryKey(refId))) > 0;
  }

  async list(options: ListOptions = {}): Promise<CacheEntry[]> {
    const { namespace, limit, offset = 0 } = options;

    let refIds: string[];

    if (namespace) {
      // Get from namespace set
      refIds = await this.client.smembers(this.namespaceSetKey(namespace));
    } else {
      // Scan all entry keys
      refIds = [];
      let cursor = '0';
      do {
        const [newCursor, keys] = await this.client.scan(
          cursor,
          'MATCH',
          `${this.prefix}:entry:*`,
          'COUNT',
          100
        );
        cursor = newCursor;
        refIds.push(...keys.map(k => k.replace(`${this.prefix}:entry:`, '')));
      } while (cursor !== '0');
    }

    // Apply pagination
    const paginatedIds = limit !== undefined
      ? refIds.slice(offset, offset + limit)
      : refIds.slice(offset);

    // Fetch entries
    const entries: CacheEntry[] = [];
    for (const refId of paginatedIds) {
      const entry = await this.get(refId);
      if (entry) entries.push(entry);
    }

    return entries;
  }

  async clear(namespace?: string): Promise<number> {
    if (namespace) {
      const refIds = await this.client.smembers(this.namespaceSetKey(namespace));
      let count = 0;
      for (const refId of refIds) {
        if (await this.delete(refId)) count++;
      }
      await this.client.del(this.namespaceSetKey(namespace));
      return count;
    }

    // Clear all
    let count = 0;
    let cursor = '0';
    do {
      const [newCursor, keys] = await this.client.scan(cursor, 'MATCH', `${this.prefix}:*`, 'COUNT', 100);
      cursor = newCursor;
      if (keys.length > 0) {
        count += await this.client.del(...keys);
      }
    } while (cursor !== '0');

    return count;
  }

  async stats(): Promise<BackendStats> {
    let totalEntries = 0;
    let cursor = '0';
    do {
      const [newCursor, keys] = await this.client.scan(cursor, 'MATCH', `${this.prefix}:entry:*`, 'COUNT', 100);
      cursor = newCursor;
      totalEntries += keys.length;
    } while (cursor !== '0');

    return {
      totalEntries,
      activeEntries: totalEntries, // Redis handles TTL automatically
      expiredEntries: 0,
      extra: {
        prefix: this.prefix,
      },
    };
  }

  async close(): Promise<void> {
    await this.client.quit();
  }

  private dataToEntry(refId: string, data: Record<string, string>): CacheEntry {
    return {
      refId,
      namespace: data.namespace,
      key: data.key,
      value: JSON.parse(data.value),
      policy: JSON.parse(data.policy),
      createdAt: new Date(parseInt(data.createdAt, 10)),
      accessedAt: new Date(parseInt(data.accessedAt, 10)),
      expiresAt: null, // TTL handled by Redis
      metadata: data.metadata ? JSON.parse(data.metadata) : undefined,
    };
  }
}
```

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with SQLite and Redis implementations |

### Design Decisions

1. **Bun/Node.js SQLite compatibility**: Use runtime detection to choose between `bun:sqlite` (native, faster) and `better-sqlite3` (Node.js compatible).

2. **Redis namespace sets**: Maintain secondary index (SET) for efficient namespace queries instead of scanning all keys.

3. **Redis TTL via EXPIRE**: Let Redis handle TTL natively rather than manual expiration tracking. More efficient and atomic.

4. **JSON serialization**: Store complex values and policies as JSON strings. Both SQLite and Redis handle TEXT/strings efficiently.

5. **Optional Redis dependency**: Redis backend should be in a separate entry point so users who don't need it don't have to install ioredis.

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | Required | Project structure needed |
| Task-02: Models & Schemas | Required | CacheEntry type definition |
| Task-03: Backend Protocol | Required | CacheBackend interface |

---

## npm Packages

| Package | Purpose | Notes |
|---------|---------|-------|
| `better-sqlite3` | Node.js SQLite | Only needed when running on Node.js |
| `ioredis` | Redis client | Optional, for RedisBackend |

---

## Verification
_How to confirm this task is complete._

```bash
# Run backend tests
bun test tests/backends/sqlite.test.ts
bun test tests/backends/redis.test.ts

# Integration test with real SQLite
bun run -e "
import { SQLiteBackend } from './src/backends/sqlite';
const backend = new SQLiteBackend({ path: '/tmp/test.db' });
await backend.set({ refId: 'test:1', namespace: 'test', key: '1', value: { hello: 'world' }, policy: {}, createdAt: new Date(), accessedAt: new Date(), expiresAt: null });
console.log(await backend.get('test:1'));
await backend.close();
"

# Integration test with real Redis (requires running Redis)
REDIS_URL=redis://localhost:6379 bun test tests/backends/redis.integration.test.ts
```

### Test Examples
```typescript
// tests/backends/sqlite.test.ts
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { SQLiteBackend } from '../../src/backends/sqlite';

describe('SQLiteBackend', () => {
  let backend: SQLiteBackend;

  beforeEach(() => {
    backend = new SQLiteBackend({ path: ':memory:', cleanupIntervalMs: 0 });
  });

  afterEach(async () => {
    await backend.close();
  });

  it('persists entries across operations', async () => {
    const entry = createTestEntry('ref1', 'key1', { data: 'value' });
    await backend.set(entry);

    const retrieved = await backend.get('ref1');
    expect(retrieved?.value).toEqual({ data: 'value' });
  });

  it('handles TTL expiration', async () => {
    const entry = createTestEntry('ref2', 'key2', 'value');
    entry.expiresAt = new Date(Date.now() - 1000); // Already expired
    await backend.set(entry);

    const retrieved = await backend.get('ref2');
    expect(retrieved).toBeNull();
  });

  it('filters by namespace', async () => {
    await backend.set(createTestEntry('ns1:ref1', 'k1', 'v1', 'ns1'));
    await backend.set(createTestEntry('ns2:ref2', 'k2', 'v2', 'ns2'));

    const ns1Entries = await backend.list({ namespace: 'ns1' });
    expect(ns1Entries).toHaveLength(1);
    expect(ns1Entries[0].namespace).toBe('ns1');
  });
});

function createTestEntry(refId: string, key: string, value: unknown, namespace = 'public') {
  return {
    refId,
    namespace,
    key,
    value,
    policy: { userPermissions: 15, agentPermissions: 1 },
    createdAt: new Date(),
    accessedAt: new Date(),
    expiresAt: null,
  };
}
```

---

## File Structure
```
src/backends/
├── index.ts        # Re-exports (excluding optional Redis)
├── base.ts         # CacheBackend interface
├── memory.ts       # MemoryBackend (from Task-03)
├── sqlite.ts       # SQLiteBackend
└── redis.ts        # RedisBackend (separate entry point)
```

### Package.json exports
```json
{
  "exports": {
    ".": "./dist/index.js",
    "./redis": "./dist/backends/redis.js"
  },
  "optionalDependencies": {
    "ioredis": "^5.0.0"
  }
}
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-02](../Task-02/scratchpad.md), [Task-03](../Task-03/scratchpad.md)
- **External Links:**
  - [Python mcp-refcache backends/sqlite.py](https://github.com/l4b4r4b4b4/mcp-refcache/blob/main/src/mcp_refcache/backends/sqlite.py)
  - [Python mcp-refcache backends/redis.py](https://github.com/l4b4r4b4b4/mcp-refcache/blob/main/src/mcp_refcache/backends/redis.py)
  - [Bun SQLite](https://bun.sh/docs/api/sqlite)
  - [better-sqlite3](https://github.com/WiseLibs/better-sqlite3)
  - [ioredis](https://github.com/redis/ioredis)
