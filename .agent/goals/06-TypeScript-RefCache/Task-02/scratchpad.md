# Task-02: Models & Zod Schemas

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Define all data models and Zod schemas that form the type foundation for `mcp-refcache-ts`. This includes cache references, responses, preview configurations, task status, and access control types.

---

## Context
The Python implementation uses Pydantic models for data validation and serialization. In TypeScript, Zod provides equivalent functionality with excellent type inference. These schemas will be used throughout the library for runtime validation while providing static type safety.

## Acceptance Criteria
- [ ] All cache-related schemas defined (`CacheReference`, `CacheResponse`, `CacheEntry`)
- [ ] Preview schemas defined (`PreviewConfig`, `PreviewStrategy`, `SizeMode`)
- [ ] Pagination schemas defined (`PaginatedResponse`)
- [ ] Async task schemas defined (`AsyncTaskResponse`, `TaskInfo`, `TaskStatus`, `TaskProgress`)
- [ ] Access control schemas defined (`Permission`, `AccessPolicy`, `ActorType`)
- [ ] All schemas export inferred TypeScript types
- [ ] Unit tests for schema validation
- [ ] JSDoc documentation for all exports

---

## Approach
Port each Python Pydantic model to an equivalent Zod schema, adapting to TypeScript idioms where appropriate. Use Zod's type inference to generate TypeScript types automatically.

### Steps

1. **Create models directory structure**
   ```
   src/models/
   ├── index.ts       # Re-exports
   ├── cache.ts       # CacheReference, CacheResponse, CacheEntry
   ├── preview.ts     # PreviewConfig, PreviewStrategy, SizeMode
   ├── pagination.ts  # PaginatedResponse
   ├── task.ts        # AsyncTaskResponse, TaskInfo, TaskStatus
   └── access.ts      # Permission, AccessPolicy, ActorType
   ```

2. **Define enum schemas**
   - `PreviewStrategy`: 'truncate' | 'sample' | 'paginate'
   - `SizeMode`: 'tokens' | 'characters'
   - `TaskStatus`: 'pending' | 'running' | 'complete' | 'failed' | 'cancelled'
   - `ActorType`: 'user' | 'agent' | 'system'
   - `Permission`: Bitfield enum (READ, WRITE, EXECUTE, DELETE)

3. **Define cache schemas**
   - `CacheReferenceSchema` with refId, namespace, preview
   - `CacheResponseSchema` with value, pagination info
   - `CacheEntrySchema` for backend storage

4. **Define preview schemas**
   - `PreviewConfigSchema` with strategy, maxSize, sizeMode

5. **Define task schemas**
   - `TaskStatusSchema` enum
   - `TaskProgressSchema` with progress, total, message
   - `TaskInfoSchema` with status, progress, timestamps
   - `AsyncTaskResponseSchema` for polling responses

6. **Define access schemas**
   - `PermissionSchema` as bitfield number
   - `AccessPolicySchema` with user/agent permissions
   - `ActorSchema` with type, id, attributes

7. **Add validation helpers**
   - `isRefId()` function to detect reference IDs
   - `parseRefId()` to extract namespace and key

8. **Write tests**
   - Valid/invalid input tests for each schema
   - Type inference verification

---

## Schema Mapping (Python → TypeScript)

| Python Model | Zod Schema | Notes |
|--------------|------------|-------|
| `SizeMode` | `z.enum(['tokens', 'characters'])` | String literal union |
| `PreviewStrategy` | `z.enum(['truncate', 'sample', 'paginate'])` | String literal union |
| `TaskStatus` | `z.enum(['pending', 'running', ...])` | String literal union |
| `ActorType` | `z.enum(['user', 'agent', 'system'])` | String literal union |
| `Permission` | `z.number()` + constants | Bitfield operations |
| `PreviewConfig` | `PreviewConfigSchema` | With defaults |
| `CacheReference` | `CacheReferenceSchema` | Core reference type |
| `CacheResponse` | `CacheResponseSchema` | Get response |
| `PaginatedResponse` | `PaginatedResponseSchema` | With generics |
| `TaskProgress` | `TaskProgressSchema` | Progress tracking |
| `TaskInfo` | `TaskInfoSchema` | Task metadata |
| `AsyncTaskResponse` | `AsyncTaskResponseSchema` | Polling response |
| `AccessPolicy` | `AccessPolicySchema` | User/agent perms |

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with schema mapping |

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | Required | Project must be initialized first |

---

## Commands & Snippets

### Permission Bitfield
```typescript
// src/models/access.ts
export const Permission = {
  NONE: 0,
  READ: 1 << 0,      // 1
  WRITE: 1 << 1,     // 2
  EXECUTE: 1 << 2,   // 4
  DELETE: 1 << 3,    // 8
  FULL: (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3), // 15
} as const;

export type PermissionFlags = typeof Permission[keyof typeof Permission];

export function hasPermission(granted: number, required: number): boolean {
  return (granted & required) === required;
}
```

### CacheReference Schema
```typescript
// src/models/cache.ts
import { z } from 'zod';

export const CacheReferenceSchema = z.object({
  refId: z.string().min(1),
  namespace: z.string().default('public'),
  key: z.string().min(1),
  preview: z.string().optional(),
  totalItems: z.number().int().nonnegative().optional(),
  expiresAt: z.date().optional(),
  createdAt: z.date().default(() => new Date()),
});

export type CacheReference = z.infer<typeof CacheReferenceSchema>;
```

### PreviewConfig Schema
```typescript
// src/models/preview.ts
import { z } from 'zod';

export const SizeModeSchema = z.enum(['tokens', 'characters']);
export type SizeMode = z.infer<typeof SizeModeSchema>;

export const PreviewStrategySchema = z.enum(['truncate', 'sample', 'paginate']);
export type PreviewStrategy = z.infer<typeof PreviewStrategySchema>;

export const PreviewConfigSchema = z.object({
  maxSize: z.number().int().positive().default(500),
  sizeMode: SizeModeSchema.default('tokens'),
  defaultStrategy: PreviewStrategySchema.default('truncate'),
});

export type PreviewConfig = z.infer<typeof PreviewConfigSchema>;
```

### AsyncTaskResponse Schema
```typescript
// src/models/task.ts
import { z } from 'zod';

export const TaskStatusSchema = z.enum([
  'pending',
  'running',
  'complete',
  'failed',
  'cancelled',
]);
export type TaskStatus = z.infer<typeof TaskStatusSchema>;

export const TaskProgressSchema = z.object({
  progress: z.number().min(0),
  total: z.number().min(0).optional(),
  message: z.string().optional(),
  percentage: z.number().min(0).max(100).optional(),
});
export type TaskProgress = z.infer<typeof TaskProgressSchema>;

export const TaskInfoSchema = z.object({
  taskId: z.string(),
  refId: z.string(),
  status: TaskStatusSchema,
  progress: TaskProgressSchema.optional(),
  startedAt: z.date().optional(),
  completedAt: z.date().optional(),
  error: z.string().optional(),
  retryCount: z.number().int().nonnegative().default(0),
});
export type TaskInfo = z.infer<typeof TaskInfoSchema>;

export const AsyncTaskResponseSchema = z.object({
  status: TaskStatusSchema,
  refId: z.string(),
  progress: TaskProgressSchema.optional(),
  eta: z.number().optional(), // seconds
  result: z.unknown().optional(),
  error: z.string().optional(),
});
export type AsyncTaskResponse = z.infer<typeof AsyncTaskResponseSchema>;
```

### Index Re-exports
```typescript
// src/models/index.ts
export * from './access';
export * from './cache';
export * from './pagination';
export * from './preview';
export * from './task';
```

---

## Verification
_How to confirm this task is complete._

```bash
# Run model tests
bun test tests/models/

# Verify type inference
bun run typecheck

# Check exports
import { CacheReference, PreviewConfig, Permission } from 'mcp-refcache';
```

### Test Examples
```typescript
// tests/models/cache.test.ts
import { describe, expect, it } from 'vitest';
import { CacheReferenceSchema } from '../../src/models/cache';

describe('CacheReferenceSchema', () => {
  it('validates valid reference', () => {
    const result = CacheReferenceSchema.parse({
      refId: 'abc123',
      key: 'user_data',
    });
    expect(result.refId).toBe('abc123');
    expect(result.namespace).toBe('public'); // default
  });

  it('rejects empty refId', () => {
    expect(() => CacheReferenceSchema.parse({ refId: '', key: 'k' }))
      .toThrow();
  });
});
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01: Project Setup](../Task-01/scratchpad.md)
- **Blocks:** Task-03, Task-04, Task-05, Task-06
- **External Links:**
  - [Zod Documentation](https://zod.dev)
  - [Python mcp-refcache models.py](https://github.com/l4b4r4b4b4/mcp-refcache/blob/main/src/mcp_refcache/models.py)
