/**
 * Models barrel — re-exports all schemas, types, and helpers.
 *
 * @module
 */

// ── Enums ────────────────────────────────────────────────────────────
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
} from "./enums.js";

export type {
  ActorType as ActorTypeValue,
  AsyncResponseFormat as AsyncResponseFormatValue,
  PreviewStrategy as PreviewStrategyValue,
  SizeMode as SizeModeValue,
  TaskStatus as TaskStatusValue,
} from "./enums.js";

// ── Permissions ──────────────────────────────────────────────────────
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
} from "./permissions.js";

export type { AccessPolicy, PermissionFlags } from "./permissions.js";

// ── Preview ──────────────────────────────────────────────────────────
export {
  PreviewConfigSchema,
  PreviewResultSchema,
} from "./preview.js";

export type { PreviewConfig, PreviewResult } from "./preview.js";

// ── Cache ────────────────────────────────────────────────────────────
export {
  CacheEntrySchema,
  CacheReferenceSchema,
  CacheResponseSchema,
  isExpired,
  PaginatedResponseSchema,
  paginateList,
} from "./cache.js";

export type {
  CacheEntry,
  CacheReference,
  CacheResponse,
  PaginatedResponse,
} from "./cache.js";

// ── Tasks ────────────────────────────────────────────────────────────
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
} from "./task.js";

export type {
  AsyncTaskResponse,
  ExpectedSchema,
  RetryInfo,
  TaskInfo,
  TaskProgress,
  TaskProgressInput,
} from "./task.js";
