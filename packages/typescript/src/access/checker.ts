/**
 * Permission checking for access control.
 *
 * This module provides the permission checking abstraction for the access
 * control system. Permission checkers evaluate whether an actor has the
 * required permissions to perform an operation on a cached value.
 *
 * The permission resolution algorithm:
 * 1. DENY if actor is in denied_actors (explicit deny)
 * 2. DENY if bound_session is set and actor's session doesn't match
 * 3. DENY if namespace ownership rules are violated
 * 4. ALLOW if actor is in allowed_actors (explicit allow, bypass role check)
 * 5. ALLOW with owner_permissions if actor matches the owner
 * 6. ALLOW/DENY based on role permissions (user_permissions/agent_permissions)
 *
 * Maps to Python: `access.checker`
 *
 * @module
 */

import { ActorType } from "../models/enums.js";
import { Permission, hasPermission } from "../models/permissions.js";
import type { AccessPolicy, PermissionFlags } from "../models/permissions.js";
import type { Actor } from "./actor.js";
import {
  DefaultNamespaceResolver,
  type NamespaceResolver,
} from "./namespace.js";

// ── permissionNames ──────────────────────────────────────────────────

/**
 * Get human-readable permission names from a permission flags value.
 *
 * @param flags - The permission flags to decode.
 * @returns Array of permission name strings (e.g., ["READ", "WRITE"]).
 *
 * @example
 * ```typescript
 * permissionNames(Permission.READ | Permission.WRITE);
 * // ["READ", "WRITE"]
 *
 * permissionNames(Permission.FULL);
 * // ["READ", "WRITE", "UPDATE", "DELETE", "EXECUTE"]
 *
 * permissionNames(Permission.NONE);
 * // []
 * ```
 */
export function permissionNames(flags: PermissionFlags): string[] {
  const names: string[] = [];
  if (flags & Permission.READ) names.push("READ");
  if (flags & Permission.WRITE) names.push("WRITE");
  if (flags & Permission.UPDATE) names.push("UPDATE");
  if (flags & Permission.DELETE) names.push("DELETE");
  if (flags & Permission.EXECUTE) names.push("EXECUTE");
  return names;
}

// ── PermissionDenied Error ───────────────────────────────────────────

/**
 * Error raised when an actor lacks the required permission.
 *
 * This error provides detailed information about why permission was denied,
 * useful for debugging and audit logging.
 *
 * Maps to Python: `access.checker.PermissionDenied`
 *
 * @example
 * ```typescript
 * try {
 *   checker.check(policy, Permission.READ, actor, "public");
 * } catch (error) {
 *   if (error instanceof PermissionDenied) {
 *     console.log(error.reason);    // "role_insufficient"
 *     console.log(error.actor);     // the actor that was denied
 *     console.log(error.required);  // Permission.READ
 *     console.log(error.namespace); // "public"
 *   }
 * }
 * ```
 */
export class PermissionDenied extends Error {
  /** The name of this error type. */
  override readonly name = "PermissionDenied";

  /** The actor that was denied. */
  readonly actor: Actor | null;

  /** The permission that was required. */
  readonly required: PermissionFlags | null;

  /** Human-readable explanation of the denial. */
  readonly reason: string | null;

  /** The namespace involved (if applicable). */
  readonly namespace: string | null;

  /**
   * Create a new PermissionDenied error.
   *
   * @param message   - The error message.
   * @param options   - Additional context about the denial.
   */
  constructor(
    message: string,
    options: {
      actor?: Actor | null;
      required?: PermissionFlags | null;
      reason?: string | null;
      namespace?: string | null;
    } = {},
  ) {
    super(message);
    this.actor = options.actor ?? null;
    this.required = options.required ?? null;
    this.reason = options.reason ?? null;
    this.namespace = options.namespace ?? null;
  }
}

// ── PermissionChecker Interface ──────────────────────────────────────

/**
 * Interface for permission checking strategies.
 *
 * Implementations evaluate access control policies and determine
 * whether an actor has the required permissions.
 *
 * Maps to Python: `access.checker.PermissionChecker` (Protocol)
 *
 * @example
 * ```typescript
 * class CustomChecker implements PermissionChecker {
 *   check(policy, required, actor, namespace) { ... }
 *   hasPermission(policy, required, actor, namespace) { ... }
 *   getEffectivePermissions(policy, actor, namespace) { ... }
 * }
 * ```
 */
export interface PermissionChecker {
  /**
   * Check if an actor has the required permission.
   *
   * @param policy    - The access policy to evaluate.
   * @param required  - The permission required for the operation.
   * @param actor     - The actor attempting the operation.
   * @param namespace - The namespace of the resource.
   * @throws {PermissionDenied} If the actor lacks the required permission.
   */
  check(
    policy: AccessPolicy,
    required: PermissionFlags,
    actor: Actor,
    namespace: string,
  ): void;

  /**
   * Check if an actor has the required permission (non-throwing).
   *
   * @param policy    - The access policy to evaluate.
   * @param required  - The permission required for the operation.
   * @param actor     - The actor attempting the operation.
   * @param namespace - The namespace of the resource.
   * @returns `true` if the actor has the required permission.
   */
  hasPermission(
    policy: AccessPolicy,
    required: PermissionFlags,
    actor: Actor,
    namespace: string,
  ): boolean;

  /**
   * Get the effective permissions for an actor.
   *
   * Returns all permissions the actor has under the given policy
   * and namespace, useful for introspection.
   *
   * @param policy    - The access policy to evaluate.
   * @param actor     - The actor to get permissions for.
   * @param namespace - The namespace context.
   * @returns Combined Permission flags for all granted permissions.
   */
  getEffectivePermissions(
    policy: AccessPolicy,
    actor: Actor,
    namespace: string,
  ): PermissionFlags;
}

// ── DefaultPermissionChecker ─────────────────────────────────────────

/**
 * Default implementation of the PermissionChecker interface.
 *
 * Implements the standard permission resolution algorithm:
 * 1. Explicit deny (deniedActors)
 * 2. Session binding check (boundSession)
 * 3. Namespace ownership check (via NamespaceResolver)
 * 4. Explicit allow (allowedActors)
 * 5. Owner permissions (owner + ownerPermissions)
 * 6. Role-based permissions (userPermissions / agentPermissions)
 *
 * Maps to Python: `access.checker.DefaultPermissionChecker`
 *
 * @example
 * ```typescript
 * const checker = new DefaultPermissionChecker();
 *
 * const policy = AccessPolicySchema.parse({
 *   userPermissions: Permission.FULL,
 *   agentPermissions: Permission.READ | Permission.EXECUTE,
 *   owner: "user:alice",
 * });
 *
 * const alice = DefaultActor.user({ actorId: "alice" });
 * checker.check(policy, Permission.DELETE, alice, "public"); // OK (owner)
 *
 * const agent = DefaultActor.agent();
 * checker.check(policy, Permission.READ, agent, "public"); // OK
 * checker.check(policy, Permission.DELETE, agent, "public"); // throws PermissionDenied
 * ```
 */
export class DefaultPermissionChecker implements PermissionChecker {
  private readonly namespaceResolver: NamespaceResolver;

  /**
   * Create a new DefaultPermissionChecker.
   *
   * @param namespaceResolver - Optional namespace resolver for ownership checks.
   *                            Defaults to DefaultNamespaceResolver.
   */
  constructor(namespaceResolver?: NamespaceResolver | null) {
    this.namespaceResolver =
      namespaceResolver ?? new DefaultNamespaceResolver();
  }

  /**
   * Check if an actor has the required permission.
   *
   * Applies the permission resolution algorithm in order:
   * 1. Check explicit deny list
   * 2. Check session binding
   * 3. Check namespace ownership
   * 4. Check explicit allow list
   * 5. Check owner permissions
   * 6. Check role-based permissions
   *
   * @param policy    - The access policy to evaluate.
   * @param required  - The permission required for the operation.
   * @param actor     - The actor attempting the operation.
   * @param namespace - The namespace of the resource.
   * @throws {PermissionDenied} If the actor lacks the required permission.
   */
  check(
    policy: AccessPolicy,
    required: PermissionFlags,
    actor: Actor,
    namespace: string,
  ): void {
    const actorString = actor.toString();

    // 1. Explicit deny always wins
    if (this.isExplicitlyDenied(policy, actor)) {
      throw new PermissionDenied(
        `Actor ${actorString} is explicitly denied`,
        {
          actor,
          required,
          reason: "explicit_deny",
          namespace,
        },
      );
    }

    // 2. Session binding check
    if (!this.checkSessionBinding(policy, actor)) {
      throw new PermissionDenied(
        `Actor ${actorString} session does not match bound session`,
        {
          actor,
          required,
          reason: "session_mismatch",
          namespace,
        },
      );
    }

    // 3. Namespace ownership check
    if (!this.namespaceResolver.validateAccess(namespace, actor)) {
      throw new PermissionDenied(
        `Actor ${actorString} cannot access namespace ${namespace}`,
        {
          actor,
          required,
          reason: "namespace_ownership",
          namespace,
        },
      );
    }

    // 4. Explicit allow bypasses role check
    if (this.isExplicitlyAllowed(policy, actor)) {
      return; // Allowed
    }

    // 5. Owner gets owner permissions
    if (this.isOwner(policy, actor)) {
      const ownerPermissions = this.getOwnerPermissions(policy);
      if (hasPermission(ownerPermissions, required)) {
        return; // Allowed
      }
      throw new PermissionDenied(
        `Owner ${actorString} lacks ${permissionNames(required).join(", ")} permission`,
        {
          actor,
          required,
          reason: "owner_insufficient",
          namespace,
        },
      );
    }

    // 6. Fall back to role-based permissions
    const rolePermissions = this.getRolePermissions(policy, actor);
    if (hasPermission(rolePermissions, required)) {
      return; // Allowed
    }

    const typeLabel =
      actor.type.charAt(0).toUpperCase() + actor.type.slice(1);
    throw new PermissionDenied(
      `${typeLabel} lacks ${permissionNames(required).join(", ")} permission`,
      {
        actor,
        required,
        reason: "role_insufficient",
        namespace,
      },
    );
  }

  /**
   * Check if an actor has the required permission (non-throwing).
   *
   * @param policy    - The access policy to evaluate.
   * @param required  - The permission required for the operation.
   * @param actor     - The actor attempting the operation.
   * @param namespace - The namespace of the resource.
   * @returns `true` if the actor has the required permission.
   */
  hasPermission(
    policy: AccessPolicy,
    required: PermissionFlags,
    actor: Actor,
    namespace: string,
  ): boolean {
    try {
      this.check(policy, required, actor, namespace);
      return true;
    } catch (error) {
      if (error instanceof PermissionDenied) {
        return false;
      }
      throw error;
    }
  }

  /**
   * Get the effective permissions for an actor.
   *
   * Evaluates the policy to determine all permissions the actor has,
   * considering all resolution steps.
   *
   * @param policy    - The access policy to evaluate.
   * @param actor     - The actor to get permissions for.
   * @param namespace - The namespace context.
   * @returns Combined Permission flags for all granted permissions.
   */
  getEffectivePermissions(
    policy: AccessPolicy,
    actor: Actor,
    namespace: string,
  ): PermissionFlags {
    // If explicitly denied, no permissions
    if (this.isExplicitlyDenied(policy, actor)) {
      return Permission.NONE;
    }

    // If session doesn't match, no permissions
    if (!this.checkSessionBinding(policy, actor)) {
      return Permission.NONE;
    }

    // If namespace access denied, no permissions
    if (!this.namespaceResolver.validateAccess(namespace, actor)) {
      return Permission.NONE;
    }

    // Owner permissions
    if (this.isOwner(policy, actor)) {
      return this.getOwnerPermissions(policy);
    }

    // Role-based permissions
    return this.getRolePermissions(policy, actor);
  }

  // ── Private Helpers ────────────────────────────────────────────────

  /**
   * Check if actor is in the explicit deny list.
   *
   * @internal
   */
  private isExplicitlyDenied(policy: AccessPolicy, actor: Actor): boolean {
    const denied = policy.deniedActors;
    if (denied === null || denied === undefined) {
      return false;
    }

    const actorString = actor.toString();
    for (const pattern of denied) {
      if (actor.matches(pattern)) {
        return true;
      }
      // Also check exact match
      if (actorString === pattern) {
        return true;
      }
    }
    return false;
  }

  /**
   * Check if actor is in the explicit allow list.
   *
   * @internal
   */
  private isExplicitlyAllowed(policy: AccessPolicy, actor: Actor): boolean {
    const allowed = policy.allowedActors;
    if (allowed === null || allowed === undefined) {
      return false;
    }

    const actorString = actor.toString();
    for (const pattern of allowed) {
      if (actor.matches(pattern)) {
        return true;
      }
      if (actorString === pattern) {
        return true;
      }
    }
    return false;
  }

  /**
   * Check if actor's session matches the bound session.
   *
   * @internal
   */
  private checkSessionBinding(policy: AccessPolicy, actor: Actor): boolean {
    const boundSession = policy.boundSession;
    if (boundSession === null || boundSession === undefined) {
      return true; // No binding, always OK
    }

    return actor.sessionId === boundSession;
  }

  /**
   * Check if actor is the owner of the resource.
   *
   * @internal
   */
  private isOwner(policy: AccessPolicy, actor: Actor): boolean {
    const owner = policy.owner;
    if (owner === null || owner === undefined) {
      return false;
    }

    return actor.toString() === owner;
  }

  /**
   * Get the permissions granted to the owner.
   *
   * @internal
   */
  private getOwnerPermissions(policy: AccessPolicy): PermissionFlags {
    return policy.ownerPermissions ?? Permission.FULL;
  }

  /**
   * Get the role-based permissions for an actor.
   *
   * @internal
   */
  private getRolePermissions(
    policy: AccessPolicy,
    actor: Actor,
  ): PermissionFlags {
    if (actor.type === ActorType.SYSTEM) {
      // System actors get full permissions
      return Permission.FULL;
    }
    if (actor.type === ActorType.USER) {
      return policy.userPermissions;
    }
    if (actor.type === ActorType.AGENT) {
      return policy.agentPermissions;
    }
    return Permission.NONE;
  }
}
