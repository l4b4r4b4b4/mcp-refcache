# Task-09: FastMCP Integration

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Create seamless integration between `mcp-refcache-ts` and [FastMCP (TypeScript)](https://github.com/punkpeye/fastmcp) through decorators, middleware patterns, and context helpers. This enables MCP server developers to easily add reference-based caching to their tools.

---

## Context
FastMCP (TypeScript) by @punkpeye is the most popular TypeScript MCP framework, equivalent to Python's FastMCP by @jlowin. Our integration should feel native to FastMCP users while providing all the benefits of mcp-refcache:

- Automatic caching of large tool results
- Preview generation to avoid context overflow
- Reference-based data flow between tools
- Access control based on actor identity
- Async timeout fallback for long operations

The Python implementation provides:
- `@cache.cached()` decorator for automatic caching
- `cache_instructions()` helper for LLM guidance
- Context integration for deriving actor/namespace from FastMCP context

## Acceptance Criteria
- [ ] `cached()` higher-order function for wrapping tool execute functions
- [ ] Automatic reference resolution for tool inputs
- [ ] Support for `async_timeout` parameter
- [ ] Namespace derivation from FastMCP session context
- [ ] Actor derivation from FastMCP authentication
- [ ] `cacheInstructions()` helper for system prompts
- [ ] TypeScript types that work with FastMCP's tool definitions
- [ ] Examples showing common integration patterns
- [ ] Unit tests with mocked FastMCP context
- [ ] JSDoc documentation with FastMCP-specific examples

---

## Approach
Create a `fastmcp` submodule with utilities designed specifically for FastMCP integration. Use higher-order functions rather than decorators (more idiomatic in TypeScript) while maintaining API similarity to the Python version.

### Steps

1. **Define FastMCP context types**
   - Session information
   - Authentication context
   - Request metadata

2. **Create `cached()` wrapper function**
   - Wraps tool execute function
   - Handles caching automatically
   - Supports configuration options

3. **Implement reference resolution**
   - Detect ref_ids in tool arguments
   - Resolve before passing to execute
   - Handle resolution errors gracefully

4. **Implement async timeout support**
   - Race execution against timeout
   - Fall back to task backend
   - Return AsyncTaskResponse

5. **Create context helpers**
   - `deriveActorFromContext()` - Extract actor from auth
   - `deriveNamespaceFromContext()` - Build namespace from session
   - `getContextValues()` - Extract all context values

6. **Create instruction helpers**
   - `cacheInstructions()` - Generate LLM-friendly instructions
   - `toolAnnotations()` - Standard tool descriptions

7. **Write examples and tests**

---

## API Design

### cached() Wrapper
```typescript
// src/fastmcp/cached.ts

import type { RefCache } from '../cache';
import type { AccessPolicy } from '../access/policy';
import type { Actor } from '../access/actor';

export interface CachedOptions {
  /** Namespace for cached results (supports templates like 'session:{sessionId}') */
  namespace?: string;
  /** Access policy for cached entries */
  policy?: AccessPolicy;
  /** TTL in seconds */
  ttl?: number;
  /** Max preview size (tokens or characters) */
  maxSize?: number;
  /** Async timeout in milliseconds - if exceeded, returns reference for polling */
  asyncTimeout?: number;
  /** Custom key generator function */
  keyGenerator?: (args: unknown) => string;
  /** Whether to resolve ref_ids in arguments (default: true) */
  resolveRefs?: boolean;
}

export interface FastMCPContext {
  /** Session ID from MCP client */
  sessionId?: string;
  /** Request ID for this specific call */
  requestId?: string;
  /** Authenticated session data */
  session?: {
    id?: string;
    userId?: string;
    role?: string;
    [key: string]: unknown;
  };
  /** Logging interface */
  log?: {
    info: (message: string, data?: unknown) => void;
    error: (message: string, data?: unknown) => void;
    debug: (message: string, data?: unknown) => void;
    warn: (message: string, data?: unknown) => void;
  };
  /** Progress reporting */
  reportProgress?: (progress: { progress: number; total: number }) => Promise<void>;
}

/**
 * Wrap a tool execute function with automatic caching.
 *
 * @example
 * ```typescript
 * import { FastMCP } from 'fastmcp';
 * import { RefCache, cached } from 'mcp-refcache';
 *
 * const cache = new RefCache();
 * const server = new FastMCP({ name: 'My Server', version: '1.0.0' });
 *
 * server.addTool({
 *   name: 'get_large_dataset',
 *   description: 'Fetch a large dataset',
 *   parameters: z.object({ query: z.string() }),
 *   execute: cached(cache, { namespace: 'session:{sessionId}' },
 *     async (args, context) => {
 *       return await fetchLargeDataset(args.query);
 *     }
 *   ),
 * });
 * ```
 */
export function cached<TArgs, TResult>(
  cache: RefCache,
  options: CachedOptions,
  execute: (args: TArgs, context: FastMCPContext) => Promise<TResult>
): (args: TArgs, context: FastMCPContext) => Promise<TResult | CacheReference | AsyncTaskResponse> {
  return async (args: TArgs, context: FastMCPContext) => {
    // Resolve references in arguments if enabled
    const resolvedArgs = options.resolveRefs !== false
      ? await resolveRefsInArgs(cache, args, context)
      : args;

    // Derive namespace from context
    const namespace = expandNamespace(options.namespace ?? 'public', context);

    // Derive actor from context
    const actor = deriveActorFromContext(context);

    // Generate cache key
    const key = options.keyGenerator?.(resolvedArgs) ?? generateKey(resolvedArgs);

    // Handle async timeout if configured
    if (options.asyncTimeout && cache.taskBackend) {
      return cache.executeWithTimeout(
        () => execute(resolvedArgs, context),
        `${namespace}:${key}`,
        options.asyncTimeout
      );
    }

    // Execute and cache result
    const result = await execute(resolvedArgs, context);

    // Store in cache and return reference
    const ref = await cache.set(key, result, {
      namespace,
      policy: options.policy,
      ttl: options.ttl,
    });

    return ref;
  };
}
```

### Context Helpers
```typescript
// src/fastmcp/context.ts

import { Actor, DefaultActor, ActorType } from '../access/actor';
import type { FastMCPContext } from './cached';

/**
 * Derive an Actor from FastMCP context.
 */
export function deriveActorFromContext(context: FastMCPContext): Actor {
  // If authenticated with user info
  if (context.session?.userId) {
    return DefaultActor.user(context.session.userId, {
      role: context.session.role,
      sessionId: context.sessionId,
    });
  }

  // If only session ID (agent-like)
  if (context.sessionId) {
    return DefaultActor.agent(context.sessionId);
  }

  // Anonymous fallback
  return DefaultActor.anonymous();
}

/**
 * Expand namespace template with context values.
 *
 * @example
 * ```typescript
 * expandNamespace('session:{sessionId}', { sessionId: 'abc123' })
 * // Returns: 'session:abc123'
 *
 * expandNamespace('user:{session.userId}', { session: { userId: 'alice' }})
 * // Returns: 'user:alice'
 * ```
 */
export function expandNamespace(template: string, context: FastMCPContext): string {
  return template.replace(/\{([^}]+)\}/g, (match, path) => {
    const value = getNestedValue(context, path);
    return value !== undefined ? String(value) : match;
  });
}

function getNestedValue(obj: unknown, path: string): unknown {
  const parts = path.split('.');
  let current: unknown = obj;

  for (const part of parts) {
    if (current === null || current === undefined) return undefined;
    current = (current as Record<string, unknown>)[part];
  }

  return current;
}

/**
 * Extract context values for logging/debugging.
 */
export function getContextValues(context: FastMCPContext): Record<string, unknown> {
  return {
    sessionId: context.sessionId,
    requestId: context.requestId,
    userId: context.session?.userId,
    role: context.session?.role,
  };
}
```

### Reference Resolution
```typescript
// src/fastmcp/resolution.ts

import type { RefCache } from '../cache';
import { isRefId } from '../cache';
import type { FastMCPContext } from './cached';
import { deriveActorFromContext } from './context';

/**
 * Resolve reference IDs in tool arguments.
 * Recursively walks the args object and resolves any string that looks like a ref_id.
 */
export async function resolveRefsInArgs<T>(
  cache: RefCache,
  args: T,
  context: FastMCPContext
): Promise<T> {
  const actor = deriveActorFromContext(context);

  return resolveValue(args, async (refId: string) => {
    return cache.resolve(refId, { actor });
  }) as Promise<T>;
}

async function resolveValue(
  value: unknown,
  resolver: (refId: string) => Promise<unknown>
): Promise<unknown> {
  // Handle strings that look like ref_ids
  if (typeof value === 'string' && isRefId(value)) {
    try {
      return await resolver(value);
    } catch {
      // If resolution fails, return original string
      return value;
    }
  }

  // Handle arrays
  if (Array.isArray(value)) {
    return Promise.all(value.map(item => resolveValue(item, resolver)));
  }

  // Handle objects
  if (typeof value === 'object' && value !== null) {
    const resolved: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value)) {
      resolved[key] = await resolveValue(val, resolver);
    }
    return resolved;
  }

  // Return primitives as-is
  return value;
}
```

### Cache Instructions
```typescript
// src/fastmcp/instructions.ts

export interface CacheInstructionsOptions {
  /** Include pagination instructions */
  includePagination?: boolean;
  /** Include private compute instructions */
  includePrivateCompute?: boolean;
  /** Custom additional instructions */
  customInstructions?: string;
}

/**
 * Generate LLM-friendly instructions about cache usage.
 * Include these in your server's system prompt or tool descriptions.
 */
export function cacheInstructions(options: CacheInstructionsOptions = {}): string {
  const sections: string[] = [
    '## Reference-Based Caching',
    '',
    'This server uses reference-based caching for large data:',
    '- Large results return a `ref_id` instead of full data',
    '- Pass `ref_id` values to other tools that need the data',
    '- Use `get_cached_result` to retrieve or paginate through cached data',
  ];

  if (options.includePagination !== false) {
    sections.push(
      '',
      '### Pagination',
      '- Cached arrays can be paginated using `page` and `pageSize` parameters',
      '- Check `hasMore` and `totalPages` to navigate through large datasets',
    );
  }

  if (options.includePrivateCompute) {
    sections.push(
      '',
      '### Private Computation',
      '- Some values have EXECUTE-only permissions',
      '- You can use these values in computations without seeing them',
      '- Pass the `ref_id` to computation tools that accept secret references',
    );
  }

  if (options.customInstructions) {
    sections.push('', options.customInstructions);
  }

  return sections.join('\n');
}

/**
 * Standard annotations for cache-related tools.
 */
export const toolAnnotations = {
  cached: {
    readOnlyHint: true,
    openWorldHint: false,
  },
  getCachedResult: {
    readOnlyHint: true,
    openWorldHint: false,
  },
  privateCompute: {
    readOnlyHint: true,
    openWorldHint: false,
  },
};
```

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with API design |

### Design Decisions

1. **Higher-order function vs decorator**: TypeScript decorators are still experimental and don't work well with function arguments. Using `cached()` as a higher-order function is more idiomatic and type-safe.

2. **Context as second argument**: FastMCP passes context as the second argument to execute functions. We follow this pattern for consistency.

3. **Template-based namespaces**: Using `{sessionId}` style templates allows dynamic namespace derivation without complex callback APIs.

4. **Graceful ref resolution**: If a ref_id can't be resolved (expired, permission denied), we return the original string rather than throwing. Tools can validate if needed.

5. **Optional async timeout**: Only used when both `asyncTimeout` is set AND `taskBackend` is configured on the cache.

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | Required | Project structure needed |
| Task-04: RefCache Core | Required | RefCache class and methods |
| Task-06: Access Control | Required | Actor derivation |
| Task-08: Async Task System | Required | For asyncTimeout support |
| FastMCP version stability | Monitor | Track @punkpeye/fastmcp releases |

---

## Verification
_How to confirm this task is complete._

```bash
# Run FastMCP integration tests
bun test tests/fastmcp/

# Verify types work with FastMCP
bun run typecheck

# Integration example
bun run examples/fastmcp-basic.ts
```

### Example Usage
```typescript
// examples/fastmcp-basic.ts
import { FastMCP } from 'fastmcp';
import { z } from 'zod';
import { RefCache, cached, cacheInstructions, AccessPolicy } from 'mcp-refcache';

const cache = new RefCache({ name: 'example' });

const server = new FastMCP({
  name: 'Example Server',
  version: '1.0.0',
  instructions: cacheInstructions({ includePagination: true }),
});

// Simple cached tool
server.addTool({
  name: 'fetch_users',
  description: 'Fetch all users. Returns reference for large results.',
  parameters: z.object({
    department: z.string().optional()
  }),
  execute: cached(cache, {
    namespace: 'public',
    ttl: 300,
  }, async (args) => {
    // Simulate fetching users
    return Array.from({ length: 1000 }, (_, i) => ({
      id: i,
      name: `User ${i}`,
      department: args.department || 'general',
    }));
  }),
});

// Tool that uses cached data
server.addTool({
  name: 'analyze_users',
  description: 'Analyze user data from a reference',
  parameters: z.object({
    usersRef: z.string().describe('Reference ID from fetch_users'),
  }),
  execute: cached(cache, {
    namespace: 'session:{sessionId}',
    resolveRefs: true,
  }, async (args) => {
    // args.usersRef is already resolved to actual user array
    const users = args.usersRef as Array<{ department: string }>;
    const byDept = users.reduce((acc, u) => {
      acc[u.department] = (acc[u.department] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    return { totalUsers: users.length, byDepartment: byDept };
  }),
});

// Private computation example
server.addTool({
  name: 'store_secret',
  description: 'Store a secret value',
  parameters: z.object({
    name: z.string(),
    value: z.number(),
  }),
  execute: async (args, context) => {
    const ref = await cache.set(`secret_${args.name}`, args.value, {
      policy: AccessPolicy.executeOnly(),
    });
    return { refId: ref.refId, message: 'Secret stored (execute-only)' };
  },
});

server.start({ transportType: 'stdio' });
```

### Test Examples
```typescript
// tests/fastmcp/cached.test.ts
import { describe, expect, it, vi } from 'vitest';
import { cached, deriveActorFromContext, expandNamespace } from '../../src/fastmcp';
import { RefCache } from '../../src/cache';

describe('cached()', () => {
  it('caches results and returns reference', async () => {
    const cache = new RefCache();
    const execute = vi.fn().mockResolvedValue([1, 2, 3]);

    const wrapped = cached(cache, { namespace: 'test' }, execute);
    const result = await wrapped({ query: 'test' }, { sessionId: 'sess1' });

    expect(result).toHaveProperty('refId');
    expect(execute).toHaveBeenCalledTimes(1);
  });

  it('resolves ref_ids in arguments', async () => {
    const cache = new RefCache();
    const ref = await cache.set('data', [1, 2, 3]);

    const execute = vi.fn().mockImplementation(args => args.data);
    const wrapped = cached(cache, { resolveRefs: true }, execute);

    await wrapped({ data: ref.refId }, {});

    expect(execute).toHaveBeenCalledWith(
      expect.objectContaining({ data: [1, 2, 3] }),
      expect.anything()
    );
  });
});

describe('expandNamespace()', () => {
  it('expands simple templates', () => {
    const result = expandNamespace('session:{sessionId}', { sessionId: 'abc' });
    expect(result).toBe('session:abc');
  });

  it('expands nested templates', () => {
    const result = expandNamespace('user:{session.userId}', {
      session: { userId: 'alice' }
    });
    expect(result).toBe('user:alice');
  });

  it('preserves unresolved templates', () => {
    const result = expandNamespace('session:{sessionId}', {});
    expect(result).toBe('session:{sessionId}');
  });
});

describe('deriveActorFromContext()', () => {
  it('creates user actor from session', () => {
    const actor = deriveActorFromContext({
      session: { userId: 'alice', role: 'admin' },
    });

    expect(actor.type).toBe('user');
    expect(actor.id).toBe('alice');
  });

  it('creates agent actor from sessionId only', () => {
    const actor = deriveActorFromContext({ sessionId: 'sess123' });

    expect(actor.type).toBe('agent');
    expect(actor.id).toBe('sess123');
  });

  it('creates anonymous actor when no context', () => {
    const actor = deriveActorFromContext({});

    expect(actor.type).toBe('agent');
    expect(actor.id).toBe('anonymous');
  });
});
```

---

## File Structure
```
src/fastmcp/
├── index.ts          # Re-exports
├── cached.ts         # cached() wrapper function
├── context.ts        # Context helpers (deriveActor, expandNamespace)
├── resolution.ts     # Reference resolution in arguments
└── instructions.ts   # LLM instruction helpers
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-04](../Task-04/scratchpad.md), [Task-06](../Task-06/scratchpad.md), [Task-08](../Task-08/scratchpad.md)
- **Blocks:** Task-10 (Template Repository)
- **External Links:**
  - [FastMCP (TypeScript)](https://github.com/punkpeye/fastmcp)
  - [fastmcp-boilerplate](https://github.com/punkpeye/fastmcp-boilerplate)
  - [Python mcp-refcache fastmcp/](https://github.com/l4b4r4b4b4/mcp-refcache/tree/main/src/mcp_refcache/fastmcp)
