/**
 * Access control barrel — re-exports all actor, namespace, and checker
 * interfaces, implementations, and factory functions.
 *
 * @module
 */

// ── Actor ────────────────────────────────────────────────────────────
export type { Actor, ActorLike } from "./actor.js";
export { DefaultActor, resolveActor } from "./actor.js";

// ── Namespace ────────────────────────────────────────────────────────
export type { NamespaceResolver } from "./namespace.js";
export { DefaultNamespaceResolver, NamespaceInfo } from "./namespace.js";

// ── Checker ──────────────────────────────────────────────────────────
export type { PermissionChecker } from "./checker.js";
export {
  DefaultPermissionChecker,
  PermissionDenied,
  permissionNames,
} from "./checker.js";
