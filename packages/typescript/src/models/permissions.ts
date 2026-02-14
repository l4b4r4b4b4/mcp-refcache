/**
 * Permission model for access control.
 *
 * Provides fine-grained permissions for both users and agents,
 * including the EXECUTE permission for private/blind computation.
 *
 * Permissions are represented as bitfield numbers so they can be
 * combined with bitwise operators, mirroring Python's `enum.Flag`.
 *
 * Maps to Python: `permissions.py`
 *
 * @module
 */

import { z } from "zod";

// ── Permission Bitfield ──────────────────────────────────────────────

/**
 * Permission flags for cache access control.
 *
 * Permissions can be combined using bitwise operators:
 *
 * ```typescript
 * const readWrite = Permission.READ | Permission.WRITE;
 * const full = Permission.FULL;
 *
 * hasPermission(readWrite, Permission.READ);  // true
 * hasPermission(readWrite, Permission.EXECUTE); // false
 * ```
 *
 * Bit values match Python's `enum.Flag` with `auto()`:
 * - NONE    = 0b00000 = 0
 * - READ    = 0b00001 = 1
 * - WRITE   = 0b00010 = 2
 * - UPDATE  = 0b00100 = 4
 * - DELETE  = 0b01000 = 8
 * - EXECUTE = 0b10000 = 16
 */
export const Permission = {
  /** No permissions granted. */
  NONE: 0,

  /** Resolve a reference to see the cached value. */
  READ: 1 << 0, // 1

  /** Create new cache references. */
  WRITE: 1 << 1, // 2

  /** Modify existing cached values. */
  UPDATE: 1 << 2, // 4

  /** Remove/invalidate cache references. */
  DELETE: 1 << 3, // 8

  /** Use value in computation WITHOUT seeing it (blind/private compute). */
  EXECUTE: 1 << 4, // 16

  /** All CRUD operations (READ | WRITE | UPDATE | DELETE). */
  CRUD: (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3), // 15

  /** Everything including EXECUTE (CRUD | EXECUTE). */
  FULL: (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4), // 31
} as const;

/**
 * A permission value — a number representing one or more bitfield flags.
 *
 * Use the {@link Permission} constants to construct values, and
 * {@link hasPermission} to check them.
 */
export type PermissionFlags = number;

/**
 * Check whether `granted` permissions include all bits in `required`.
 *
 * @param granted  - The permission flags that have been granted.
 * @param required - The permission flags to check for.
 * @returns `true` if every bit in `required` is set in `granted`.
 *
 * @example
 * ```typescript
 * const perms = Permission.READ | Permission.WRITE;
 * hasPermission(perms, Permission.READ);    // true
 * hasPermission(perms, Permission.EXECUTE); // false
 * hasPermission(perms, Permission.READ | Permission.WRITE); // true
 * ```
 */
export function hasPermission(
  granted: PermissionFlags,
  required: PermissionFlags,
): boolean {
  return (granted & required) === required;
}

/**
 * Combine multiple permission flags into a single value.
 *
 * @param flags - Permission flags to combine.
 * @returns A single number with all flags OR'd together.
 *
 * @example
 * ```typescript
 * const perms = combinePermissions(Permission.READ, Permission.EXECUTE);
 * // equivalent to: Permission.READ | Permission.EXECUTE
 * ```
 */
export function combinePermissions(
  ...flags: readonly PermissionFlags[]
): PermissionFlags {
  let combined = Permission.NONE;
  for (const flag of flags) {
    combined |= flag;
  }
  return combined;
}

// ── Permission Schema ────────────────────────────────────────────────

/**
 * Zod schema for permission values.
 *
 * Validates that the value is a non-negative integer within the valid
 * permission range (0 through {@link Permission.FULL}).
 */
export const PermissionSchema = z
  .number()
  .int()
  .min(0)
  .max(Permission.FULL)
  .describe("Bitfield permission flags (0 = NONE, 31 = FULL).");

// ── Access Policy ────────────────────────────────────────────────────

/**
 * Zod schema for access policies.
 *
 * Defines separate permissions for users and agents, plus ownership,
 * ACL (allow/deny lists), and session binding.
 *
 * This separation enables private computation where agents can use
 * values (EXECUTE) without being able to read them (READ).
 *
 * Maps to Python: `permissions.AccessPolicy`
 *
 * @example
 * ```typescript
 * // Agent can use but not see the value
 * const policy = AccessPolicySchema.parse({
 *   userPermissions: Permission.FULL,
 *   agentPermissions: Permission.EXECUTE,
 * });
 *
 * // With ownership
 * const owned = AccessPolicySchema.parse({
 *   userPermissions: Permission.READ,
 *   owner: "user:alice",
 *   ownerPermissions: Permission.FULL,
 * });
 * ```
 */
export const AccessPolicySchema = z.object({
  // === Role-based permissions ===

  /** Permissions granted to human users. */
  userPermissions: PermissionSchema.default(Permission.FULL).describe(
    "Permissions granted to human users.",
  ),

  /** Permissions granted to AI agents. */
  agentPermissions: PermissionSchema.default(
    Permission.READ | Permission.EXECUTE,
  ).describe("Permissions granted to AI agents."),

  // === Ownership ===

  /**
   * Owner identity string (e.g., "user:alice", "agent:claude-1").
   * When set, the owner receives `ownerPermissions` regardless of role.
   */
  owner: z
    .string()
    .nullish()
    .default(null)
    .describe(
      'Owner identity string (e.g., "user:alice", "agent:claude-1").',
    ),

  /** Permissions granted to the owner. */
  ownerPermissions: PermissionSchema.default(Permission.FULL).describe(
    "Permissions granted to the owner.",
  ),

  // === ACL (Access Control Lists) ===

  /**
   * Explicit allow list of actor patterns (e.g., ["user:alice", "agent:*"]).
   * When set, only matching actors are allowed (in addition to role-based checks).
   */
  allowedActors: z
    .array(z.string())
    .nullish()
    .default(null)
    .describe(
      'Explicit allow list of actor patterns (e.g., ["user:alice", "agent:*"]).',
    ),

  /**
   * Explicit deny list of actor patterns.
   * Deny takes precedence over allow.
   */
  deniedActors: z
    .array(z.string())
    .nullish()
    .default(null)
    .describe(
      "Explicit deny list of actor patterns. Deny takes precedence over allow.",
    ),

  // === Session binding ===

  /**
   * If set, only actors with this session_id can access the entry.
   */
  boundSession: z
    .string()
    .nullish()
    .default(null)
    .describe(
      "If set, only actors with this session_id can access the entry.",
    ),
});

/** Inferred type for {@link AccessPolicySchema}. */
export type AccessPolicy = z.infer<typeof AccessPolicySchema>;

// ── Helper Methods ───────────────────────────────────────────────────

/**
 * Check if a user has a specific permission under this policy.
 *
 * @param policy     - The access policy to check.
 * @param permission - The permission flag(s) to check for.
 * @returns `true` if the user has the required permission(s).
 */
export function userCan(
  policy: AccessPolicy,
  permission: PermissionFlags,
): boolean {
  return hasPermission(policy.userPermissions, permission);
}

/**
 * Check if an agent has a specific permission under this policy.
 *
 * @param policy     - The access policy to check.
 * @param permission - The permission flag(s) to check for.
 * @returns `true` if the agent has the required permission(s).
 */
export function agentCan(
  policy: AccessPolicy,
  permission: PermissionFlags,
): boolean {
  return hasPermission(policy.agentPermissions, permission);
}

// ── Common Policy Presets ────────────────────────────────────────────

/**
 * Public policy — full permissions for both users and agents.
 *
 * Maps to Python: `POLICY_PUBLIC`
 */
export const POLICY_PUBLIC: AccessPolicy = AccessPolicySchema.parse({
  userPermissions: Permission.FULL,
  agentPermissions: Permission.FULL,
});

/**
 * User-only policy — full permissions for users, none for agents.
 *
 * Maps to Python: `POLICY_USER_ONLY`
 */
export const POLICY_USER_ONLY: AccessPolicy = AccessPolicySchema.parse({
  userPermissions: Permission.FULL,
  agentPermissions: Permission.NONE,
});

/**
 * Execute-only policy — full for users, only EXECUTE for agents.
 *
 * This enables "blind compute" where agents can use a value in
 * computations without ever seeing its contents.
 *
 * Maps to Python: `POLICY_EXECUTE_ONLY`
 */
export const POLICY_EXECUTE_ONLY: AccessPolicy = AccessPolicySchema.parse({
  userPermissions: Permission.FULL,
  agentPermissions: Permission.EXECUTE,
});

/**
 * Read-only policy — only READ permission for both users and agents.
 *
 * Maps to Python: `POLICY_READ_ONLY`
 */
export const POLICY_READ_ONLY: AccessPolicy = AccessPolicySchema.parse({
  userPermissions: Permission.READ,
  agentPermissions: Permission.READ,
});
