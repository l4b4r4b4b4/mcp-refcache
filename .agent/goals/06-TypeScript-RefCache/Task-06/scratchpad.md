# Task-06: Access Control System

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Implement the complete access control system including Actors (users, agents, system), Permissions (bitfield-based), Access Policies, Namespace resolution, and Permission checking. This system ensures that cached values are only accessible to authorized parties based on their identity and the value's policy.

---

## Context
Access control is fundamental to mcp-refcache's security model. The key insight is that **users and agents have different permissions** on the same cached value. For example:
- A user might have FULL access to their data
- An agent might only have EXECUTE permission (can use the value in computation but cannot read it directly)

This enables "private computation" where agents can work with sensitive values without ever seeing them.

The Python implementation has:
- `Actor` with type (user/agent/system) and identity
- `Permission` as a bitfield (READ, WRITE, EXECUTE, DELETE)
- `AccessPolicy` with separate user and agent permissions
- `NamespaceResolver` for dynamic namespace derivation
- `PermissionChecker` for enforcing access rules

## Acceptance Criteria
- [ ] `ActorType` enum (user, agent, system)
- [ ] `Actor` class with type, id, and optional attributes
- [ ] `DefaultActor` factory for common actor creation
- [ ] `Permission` bitfield constants and helpers
- [ ] `AccessPolicy` class with user/agent permission separation
- [ ] Pre-built policies: PUBLIC, READ_ONLY, USER_ONLY, EXECUTE_ONLY
- [ ] `NamespaceResolver` interface for dynamic namespaces
- [ ] `DefaultNamespaceResolver` with standard patterns
- [ ] `PermissionChecker` interface for access enforcement
- [ ] `DefaultPermissionChecker` with namespace ownership rules
- [ ] `PermissionDenied` error type
- [ ] Unit tests for all components
- [ ] JSDoc documentation with examples

---

## Approach
Port the Python access control system while leveraging TypeScript's type system for better compile-time safety. Use a class-based design for Actor and AccessPolicy while keeping Permission as constants with helper functions.

### Steps

1. **Define ActorType and Actor**
   - Enum for actor types
   - Actor class with factory methods
   - Support for custom attributes

2. **Define Permission system**
   - Bitfield constants (READ=1, WRITE=2, EXECUTE=4, DELETE=8)
   - Helper functions: hasPermission, combinePermissions
   - Common combinations: FULL, NONE

3. **Define AccessPolicy**
   - Separate userPermissions and agentPermissions
   - Optional owner field for ownership-based access
   - Factory methods for common patterns

4. **Implement NamespaceResolver**
   - Interface for resolving namespace from context
   - DefaultNamespaceResolver with standard patterns
   - Support for session:, user:, custom: namespaces

5. **Implement PermissionChecker**
   - Interface for permission checking
   - DefaultPermissionChecker with:
     - Permission-based access
     - Ownership-based access
     - Namespace ownership rules

6. **Create PermissionDenied error**
   - Custom error with actor, permission, and resource info
   - Helpful error messages

7. **Write comprehensive tests**

---

## Implementation Design

### Permission Constants
```typescript
// src/access/permission.ts

/**
 * Permission flags as a bitfield.
 * Can be combined with bitwise OR: Permission.READ | Permission.WRITE
 */
export const Permission = {
  /** No permissions */
  NONE: 0,
  /** Can read/retrieve the value */
  READ: 1 << 0,   // 1
  /** Can update/overwrite the value */
  WRITE: 1 << 1,  // 2
  /** Can use the value in computations without seeing it */
  EXECUTE: 1 << 2, // 4
  /** Can delete the value */
  DELETE: 1 << 3,  // 8
  /** All permissions */
  FULL: (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3), // 15
} as const;

export type PermissionFlags = number;

/**
 * Check if granted permissions include required permissions.
 */
export function hasPermission(granted: PermissionFlags, required: PermissionFlags): boolean {
  return (granted & required) === required;
}

/**
 * Combine multiple permissions.
 */
export function combinePermissions(...permissions: PermissionFlags[]): PermissionFlags {
  return permissions.reduce((acc, p) => acc | p, 0);
}

/**
 * Get human-readable permission names.
 */
export function permissionNames(flags: PermissionFlags): string[] {
  const names: string[] = [];
  if (flags & Permission.READ) names.push('READ');
  if (flags & Permission.WRITE) names.push('WRITE');
  if (flags & Permission.EXECUTE) names.push('EXECUTE');
  if (flags & Permission.DELETE) names.push('DELETE');
  return names;
}
```

### Actor
```typescript
// src/access/actor.ts

export const ActorType = {
  USER: 'user',
  AGENT: 'agent',
  SYSTEM: 'system',
} as const;

export type ActorType = typeof ActorType[keyof typeof ActorType];

export interface ActorAttributes {
  [key: string]: unknown;
}

export class Actor {
  constructor(
    public readonly type: ActorType,
    public readonly id: string,
    public readonly attributes: ActorAttributes = {}
  ) {}

  /**
   * Check if this actor represents a user.
   */
  isUser(): boolean {
    return this.type === ActorType.USER;
  }

  /**
   * Check if this actor represents an agent.
   */
  isAgent(): boolean {
    return this.type === ActorType.AGENT;
  }

  /**
   * Check if this actor represents the system.
   */
  isSystem(): boolean {
    return this.type === ActorType.SYSTEM;
  }

  /**
   * Check if this actor matches the given owner string.
   */
  matchesOwner(owner: string): boolean {
    return owner === `${this.type}:${this.id}`;
  }

  toString(): string {
    return `Actor(${this.type}:${this.id})`;
  }
}

/**
 * Factory for creating common actor types.
 */
export const DefaultActor = {
  user(id: string, attributes?: ActorAttributes): Actor {
    return new Actor(ActorType.USER, id, attributes);
  },

  agent(id: string, attributes?: ActorAttributes): Actor {
    return new Actor(ActorType.AGENT, id, attributes);
  },

  system(): Actor {
    return new Actor(ActorType.SYSTEM, 'system');
  },

  anonymous(): Actor {
    return new Actor(ActorType.AGENT, 'anonymous');
  },
};
```

### AccessPolicy
```typescript
// src/access/policy.ts

import { Permission, PermissionFlags } from './permission';

export interface AccessPolicyOptions {
  userPermissions?: PermissionFlags;
  agentPermissions?: PermissionFlags;
  owner?: string;
}

export class AccessPolicy {
  readonly userPermissions: PermissionFlags;
  readonly agentPermissions: PermissionFlags;
  readonly owner?: string;

  constructor(options: AccessPolicyOptions = {}) {
    this.userPermissions = options.userPermissions ?? Permission.FULL;
    this.agentPermissions = options.agentPermissions ?? Permission.READ;
    this.owner = options.owner;
  }

  /**
   * Get permissions for the given actor type.
   */
  getPermissions(actorType: ActorType): PermissionFlags {
    if (actorType === 'system') return Permission.FULL;
    if (actorType === 'user') return this.userPermissions;
    return this.agentPermissions;
  }

  /**
   * Create a copy with modified options.
   */
  with(options: Partial<AccessPolicyOptions>): AccessPolicy {
    return new AccessPolicy({
      userPermissions: options.userPermissions ?? this.userPermissions,
      agentPermissions: options.agentPermissions ?? this.agentPermissions,
      owner: options.owner ?? this.owner,
    });
  }

  // Factory methods for common policies

  /** Public: Users have full access, agents can read */
  static public(): AccessPolicy {
    return new AccessPolicy({
      userPermissions: Permission.FULL,
      agentPermissions: Permission.READ,
    });
  }

  /** Read-only: Both users and agents can only read */
  static readOnly(): AccessPolicy {
    return new AccessPolicy({
      userPermissions: Permission.READ,
      agentPermissions: Permission.READ,
    });
  }

  /** User-only: Only users have access, agents have none */
  static userOnly(): AccessPolicy {
    return new AccessPolicy({
      userPermissions: Permission.FULL,
      agentPermissions: Permission.NONE,
    });
  }

  /** Execute-only: Users have full, agents can only execute (private compute) */
  static executeOnly(): AccessPolicy {
    return new AccessPolicy({
      userPermissions: Permission.FULL,
      agentPermissions: Permission.EXECUTE,
    });
  }

  /** Owner-based: Full access only to the specified owner */
  static forOwner(owner: string): AccessPolicy {
    return new AccessPolicy({
      userPermissions: Permission.FULL,
      agentPermissions: Permission.NONE,
      owner,
    });
  }
}

// Pre-built policy instances
export const POLICY_PUBLIC = AccessPolicy.public();
export const POLICY_READ_ONLY = AccessPolicy.readOnly();
export const POLICY_USER_ONLY = AccessPolicy.userOnly();
export const POLICY_EXECUTE_ONLY = AccessPolicy.executeOnly();
```

### PermissionChecker
```typescript
// src/access/checker.ts

import { Actor } from './actor';
import { AccessPolicy } from './policy';
import { Permission, hasPermission, permissionNames } from './permission';

export class PermissionDenied extends Error {
  constructor(
    public readonly actor: Actor,
    public readonly required: number,
    public readonly resource: string,
    public readonly reason?: string
  ) {
    const requiredNames = permissionNames(required).join(', ');
    const message = reason
      ? `${actor} denied ${requiredNames} on ${resource}: ${reason}`
      : `${actor} denied ${requiredNames} on ${resource}`;
    super(message);
    this.name = 'PermissionDenied';
  }
}

export interface PermissionChecker {
  checkRead(policy: AccessPolicy, actor: Actor, resource?: string): void;
  checkWrite(policy: AccessPolicy, actor: Actor, resource?: string): void;
  checkExecute(policy: AccessPolicy, actor: Actor, resource?: string): void;
  checkDelete(policy: AccessPolicy, actor: Actor, resource?: string): void;
  check(policy: AccessPolicy, actor: Actor, required: number, resource?: string): void;
}

export class DefaultPermissionChecker implements PermissionChecker {
  /**
   * Check if actor has permission, considering ownership.
   */
  check(policy: AccessPolicy, actor: Actor, required: number, resource = 'unknown'): void {
    // System always has access
    if (actor.isSystem()) return;

    // Check ownership first
    if (policy.owner && actor.matchesOwner(policy.owner)) {
      return; // Owner has implicit full access
    }

    // Check permission based on actor type
    const granted = policy.getPermissions(actor.type);

    if (!hasPermission(granted, required)) {
      throw new PermissionDenied(actor, required, resource,
        `Has ${permissionNames(granted).join(', ') || 'NONE'}`);
    }
  }

  checkRead(policy: AccessPolicy, actor: Actor, resource?: string): void {
    this.check(policy, actor, Permission.READ, resource);
  }

  checkWrite(policy: AccessPolicy, actor: Actor, resource?: string): void {
    this.check(policy, actor, Permission.WRITE, resource);
  }

  checkExecute(policy: AccessPolicy, actor: Actor, resource?: string): void {
    this.check(policy, actor, Permission.EXECUTE, resource);
  }

  checkDelete(policy: AccessPolicy, actor: Actor, resource?: string): void {
    this.check(policy, actor, Permission.DELETE, resource);
  }
}
```

### NamespaceResolver
```typescript
// src/access/namespace.ts

export interface NamespaceInfo {
  namespace: string;
  owner?: string;
  isPublic: boolean;
}

export interface NamespaceResolver {
  resolve(namespace: string, context?: Record<string, unknown>): NamespaceInfo;
}

export class DefaultNamespaceResolver implements NamespaceResolver {
  resolve(namespace: string, context?: Record<string, unknown>): NamespaceInfo {
    // Handle template expansion
    let resolved = namespace;
    if (context) {
      resolved = this.expandTemplate(namespace, context);
    }

    // Determine owner from namespace pattern
    const owner = this.deriveOwner(resolved);
    const isPublic = resolved === 'public' || resolved.startsWith('public:');

    return {
      namespace: resolved,
      owner,
      isPublic,
    };
  }

  private expandTemplate(template: string, context: Record<string, unknown>): string {
    return template.replace(/\{(\w+)\}/g, (_, key) => {
      const value = context[key];
      return value !== undefined ? String(value) : `{${key}}`;
    });
  }

  private deriveOwner(namespace: string): string | undefined {
    // user:{id} -> user:{id} is the owner
    if (namespace.startsWith('user:')) {
      const parts = namespace.split(':');
      if (parts.length >= 2) {
        return `user:${parts[1]}`;
      }
    }

    // session:{id} -> no specific owner (session-scoped)
    // agent:{id} -> agent:{id} is the owner
    if (namespace.startsWith('agent:')) {
      const parts = namespace.split(':');
      if (parts.length >= 2) {
        return `agent:${parts[1]}`;
      }
    }

    return undefined;
  }
}
```

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with full implementation design |

### Design Decisions

1. **Permission as constants, not enum**: Using `as const` objects allows bitwise operations while maintaining type safety. Enums in TypeScript don't work as cleanly with bitfields.

2. **Actor as class**: Unlike Python's dataclass, using a TypeScript class allows helper methods (isUser(), isAgent()) and toString() for debugging.

3. **AccessPolicy factory methods**: Static factory methods like `AccessPolicy.public()` are more readable than remembering permission combinations.

4. **Owner-based access**: The owner field enables automatic full access for the resource owner, simplifying user-specific caching patterns.

5. **PermissionDenied error**: Custom error class includes all context needed for debugging access issues.

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | Required | Project structure needed |
| Task-02: Models & Schemas | Partial | Permission enum may be defined there |

---

## Verification
_How to confirm this task is complete._

```bash
# Run access control tests
bun test tests/access/

# Verify type checking
bun run typecheck

# Test coverage
bun test --coverage tests/access/
```

### Test Examples
```typescript
// tests/access/permission.test.ts
import { describe, expect, it } from 'vitest';
import { Permission, hasPermission, combinePermissions } from '../../src/access/permission';

describe('Permission', () => {
  it('allows combining permissions', () => {
    const readWrite = combinePermissions(Permission.READ, Permission.WRITE);
    expect(readWrite).toBe(3); // 1 | 2
    expect(hasPermission(readWrite, Permission.READ)).toBe(true);
    expect(hasPermission(readWrite, Permission.WRITE)).toBe(true);
    expect(hasPermission(readWrite, Permission.EXECUTE)).toBe(false);
  });

  it('FULL includes all permissions', () => {
    expect(hasPermission(Permission.FULL, Permission.READ)).toBe(true);
    expect(hasPermission(Permission.FULL, Permission.WRITE)).toBe(true);
    expect(hasPermission(Permission.FULL, Permission.EXECUTE)).toBe(true);
    expect(hasPermission(Permission.FULL, Permission.DELETE)).toBe(true);
  });
});

// tests/access/checker.test.ts
import { describe, expect, it } from 'vitest';
import { DefaultPermissionChecker, PermissionDenied } from '../../src/access/checker';
import { AccessPolicy } from '../../src/access/policy';
import { DefaultActor } from '../../src/access/actor';

describe('DefaultPermissionChecker', () => {
  const checker = new DefaultPermissionChecker();

  it('allows user read on public policy', () => {
    const policy = AccessPolicy.public();
    const actor = DefaultActor.user('alice');

    expect(() => checker.checkRead(policy, actor)).not.toThrow();
  });

  it('denies agent read on user-only policy', () => {
    const policy = AccessPolicy.userOnly();
    const actor = DefaultActor.agent('claude');

    expect(() => checker.checkRead(policy, actor)).toThrow(PermissionDenied);
  });

  it('allows execute-only agent to execute but not read', () => {
    const policy = AccessPolicy.executeOnly();
    const actor = DefaultActor.agent('claude');

    expect(() => checker.checkExecute(policy, actor)).not.toThrow();
    expect(() => checker.checkRead(policy, actor)).toThrow(PermissionDenied);
  });

  it('allows owner full access regardless of policy', () => {
    const policy = AccessPolicy.forOwner('user:alice');
    const actor = DefaultActor.user('alice');
    const otherUser = DefaultActor.user('bob');

    expect(() => checker.checkDelete(policy, actor)).not.toThrow();
    expect(() => checker.checkRead(policy, otherUser)).toThrow(PermissionDenied);
  });

  it('system actor always has access', () => {
    const policy = AccessPolicy.userOnly();
    const system = DefaultActor.system();

    expect(() => checker.checkDelete(policy, system)).not.toThrow();
  });
});
```

---

## File Structure
```
src/access/
├── index.ts          # Re-exports
├── actor.ts          # Actor class and DefaultActor
├── permission.ts     # Permission constants and helpers
├── policy.ts         # AccessPolicy class and presets
├── checker.ts        # PermissionChecker and PermissionDenied
└── namespace.ts      # NamespaceResolver and DefaultNamespaceResolver
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-02](../Task-02/scratchpad.md)
- **Blocks:** Task-04 (RefCache - full integration), Task-09 (FastMCP Integration)
- **External Links:**
  - [Python mcp-refcache access/](https://github.com/l4b4r4b4b4/mcp-refcache/tree/main/src/mcp_refcache/access)
  - [Bitfield patterns in TypeScript](https://www.typescriptlang.org/docs/handbook/enums.html#const-enums)
