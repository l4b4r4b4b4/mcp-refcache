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

// Enums
export {
  ActorType,
  ActorTypeSchema,
  AsyncResponseFormat,
  AsyncResponseFormatSchema,
  PreviewStrategy,
  PreviewStrategySchema,
  SizeMode,
  SizeModeSchema,
  TaskStatus,
  TaskStatusSchema,
} from "./models/index.js";

export type {
  ActorTypeValue,
  AsyncResponseFormatValue,
  PreviewStrategyValue,
  SizeModeValue,
  TaskStatusValue,
} from "./models/index.js";

// Permissions
export {
  AccessPolicySchema,
  agentCan,
  combinePermissions,
  hasPermission,
  Permission,
  PermissionSchema,
  POLICY_EXECUTE_ONLY,
  POLICY_PUBLIC,
  POLICY_READ_ONLY,
  POLICY_USER_ONLY,
  userCan,
} from "./models/index.js";

export type { AccessPolicy, PermissionFlags } from "./models/index.js";

// Preview
export {
  PreviewConfigSchema,
  PreviewResultSchema,
} from "./models/index.js";

export type { PreviewConfig, PreviewResult } from "./models/index.js";

// Cache
export {
  CacheEntrySchema,
  CacheReferenceSchema,
  CacheResponseSchema,
  isExpired,
  PaginatedResponseSchema,
  paginateList,
} from "./models/index.js";

export type {
  CacheEntry,
  CacheReference,
  CacheResponse,
  PaginatedResponse,
} from "./models/index.js";

// Tasks
export {
  asyncTaskResponseFromInfo,
  AsyncTaskResponseSchema,
  asyncTaskResponseToDict,
  canRetry,
  elapsedSeconds,
  ExpectedSchemaSchema,
  isTerminal,
  RetryInfoSchema,
  TaskInfoSchema,
  TaskProgressSchema,
} from "./models/index.js";

export type {
  AsyncTaskResponse,
  ExpectedSchema,
  RetryInfo,
  TaskInfo,
  TaskProgress,
  TaskProgressInput,
} from "./models/index.js";

// ── Backends ─────────────────────────────────────────────────────────
export type { CacheBackend } from "./backends/index.js";
export { MemoryBackend } from "./backends/index.js";

// TODO(Task-07): SQLite and Redis backends
// export { SQLiteBackend } from "./backends/sqlite.js";
// export { RedisBackend } from "./backends/redis.js";

// TODO(Task-08): Async task backends
// export type { TaskBackend } from "./backends/task-types.js";
// export { MemoryTaskBackend } from "./backends/task-memory.js";

// ── Access Control ───────────────────────────────────────────────────
export type { Actor, ActorLike } from "./access/index.js";

export { DefaultActor, resolveActor } from "./access/index.js";

export type { PermissionChecker } from "./access/index.js";

export {
  DefaultPermissionChecker,
  PermissionDenied,
  permissionNames,
} from "./access/index.js";

export type { NamespaceResolver } from "./access/index.js";

export { DefaultNamespaceResolver, NamespaceInfo } from "./access/index.js";

// ── Preview System ───────────────────────────────────────────────────
export type { PreviewGenerator } from "./preview/index.js";

export {
  getDefaultGenerator,
  PaginateGenerator,
  SampleGenerator,
  TruncateGenerator,
} from "./preview/index.js";

// ── Context (Tokenizers & Measurers) ─────────────────────────────────
export type { SizeMeasurer, Tokenizer } from "./context/index.js";

export {
  CharacterFallback,
  CharacterMeasurer,
  getDefaultTokenizer,
  TiktokenAdapter,
  TokenMeasurer,
} from "./context/index.js";

// ── Core Cache ───────────────────────────────────────────────────────
// TODO(Task-04): Export RefCache class
// export { RefCache } from "./cache.js";

// ── Resolution ───────────────────────────────────────────────────────
// TODO(Task-04): Export ref resolution utilities
// export { RefResolver, isRefId, resolveRefs, resolveKwargs } from "./resolution.js";
// export { CircularReferenceError } from "./resolution.js";
