/**
 * mcp-refcache — Reference-based caching for FastMCP servers.
 *
 * This library provides context-aware caching with:
 * - Namespace isolation (public, session, user, custom)
 * - Access control (separate permissions for users and agents)
 * - Identity-aware actors (users, agents, system)
 * - Private computation (EXECUTE permission for blind compute)
 * - Context limiting (token/char-based with truncate/paginate/sample strategies)
 *
 * @packageDocumentation
 */

/**
 * Library version. Keep in sync with package.json.
 */
export const VERSION = "0.1.0";

// ── Models & Schemas ─────────────────────────────────────────────────
// TODO(Task-02): Export Zod schemas and inferred types
// export { CacheReferenceSchema, type CacheReference } from "./models/cache-reference.js";
// export { CacheResponseSchema, type CacheResponse } from "./models/cache-response.js";
// export { PaginatedResponseSchema, type PaginatedResponse } from "./models/paginated-response.js";
// export { PreviewConfigSchema, type PreviewConfig } from "./models/preview-config.js";
// export { PreviewStrategy, SizeMode } from "./models/enums.js";
// export { AsyncTaskResponseSchema, type AsyncTaskResponse } from "./models/async-task-response.js";
// export { TaskInfoSchema, type TaskInfo, TaskStatus, type TaskProgress } from "./models/task-info.js";

// ── Backends ─────────────────────────────────────────────────────────
// TODO(Task-03): Export backend interfaces and implementations
// export type { CacheBackend, CacheEntry } from "./backends/types.js";
// export { MemoryBackend } from "./backends/memory.js";

// TODO(Task-07): SQLite and Redis backends
// export { SQLiteBackend } from "./backends/sqlite.js";
// export { RedisBackend } from "./backends/redis.js";

// TODO(Task-08): Async task backends
// export type { TaskBackend } from "./backends/task-types.js";
// export { MemoryTaskBackend } from "./backends/task-memory.js";

// ── Access Control ───────────────────────────────────────────────────
// TODO(Task-06): Export access control types
// export { Permission, AccessPolicy } from "./access/permissions.js";
// export { POLICY_PUBLIC, POLICY_USER_ONLY, POLICY_EXECUTE_ONLY, POLICY_READ_ONLY } from "./access/permissions.js";
// export type { Actor, ActorLike } from "./access/actor.js";
// export { DefaultActor, ActorType, resolveActor } from "./access/actor.js";
// export type { PermissionChecker } from "./access/checker.js";
// export { DefaultPermissionChecker, PermissionDenied } from "./access/checker.js";
// export type { NamespaceResolver } from "./access/namespace.js";
// export { DefaultNamespaceResolver, type NamespaceInfo } from "./access/namespace.js";

// ── Preview System ───────────────────────────────────────────────────
// TODO(Task-05): Export preview generators and size measurers
// export type { PreviewGenerator, PreviewResult } from "./preview/types.js";
// export { SampleGenerator, PaginateGenerator, TruncateGenerator } from "./preview/generators.js";
// export { getDefaultGenerator } from "./preview/generators.js";
// export type { SizeMeasurer, Tokenizer } from "./context/types.js";
// export { TokenMeasurer, CharacterMeasurer } from "./context/measurers.js";

// ── Core Cache ───────────────────────────────────────────────────────
// TODO(Task-04): Export RefCache class
// export { RefCache } from "./cache.js";

// ── Resolution ───────────────────────────────────────────────────────
// TODO(Task-04): Export ref resolution utilities
// export { RefResolver, isRefId, resolveRefs, resolveKwargs } from "./resolution.js";
// export { CircularReferenceError } from "./resolution.js";
