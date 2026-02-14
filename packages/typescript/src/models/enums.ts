/**
 * Enum schemas for mcp-refcache.
 *
 * These Zod enums mirror the Python `str, Enum` classes in `models.py`,
 * `permissions.py`, and `access/actor.py`. Each enum is defined as a Zod
 * schema so it can be used for both runtime validation and static type
 * inference.
 *
 * @module
 */

import { z } from "zod";

// ── Size Mode ────────────────────────────────────────────────────────

/**
 * How to measure size for context limiting.
 *
 * - `token` — Count tokens (accurate for LLM context windows).
 * - `character` — Count characters (faster, no tokenizer dependency).
 *
 * Maps to Python: `models.SizeMode`
 */
export const SizeModeSchema = z.enum(["token", "character"]);

/** Inferred type for {@link SizeModeSchema}. */
export type SizeMode = z.infer<typeof SizeModeSchema>;

/** Convenience constants matching the Python enum members. */
export const SizeMode = {
  TOKEN: "token",
  CHARACTER: "character",
} as const satisfies Record<string, SizeMode>;

// ── Preview Strategy ─────────────────────────────────────────────────

/**
 * Strategy for generating previews of large cached values.
 *
 * - `truncate` — Stringify and cut at the size limit.
 * - `paginate` — Split into pages, each respecting the limit.
 * - `sample`   — Pick evenly-spaced items so output respects the limit.
 *
 * Maps to Python: `models.PreviewStrategy`
 */
export const PreviewStrategySchema = z.enum(["truncate", "paginate", "sample"]);

/** Inferred type for {@link PreviewStrategySchema}. */
export type PreviewStrategy = z.infer<typeof PreviewStrategySchema>;

/** Convenience constants matching the Python enum members. */
export const PreviewStrategy = {
  TRUNCATE: "truncate",
  PAGINATE: "paginate",
  SAMPLE: "sample",
} as const satisfies Record<string, PreviewStrategy>;

// ── Async Response Format ────────────────────────────────────────────

/**
 * Detail level for async task polling responses.
 *
 * Controls how much information is included when a task goes async:
 * - `minimal`  — Just ref_id, status, is_async (lightweight polling).
 * - `standard` — Above + started_at, progress, message (default).
 * - `full`     — Above + expected_schema, eta_seconds, retry_info.
 *
 * Maps to Python: `models.AsyncResponseFormat`
 */
export const AsyncResponseFormatSchema = z.enum([
  "minimal",
  "standard",
  "full",
]);

/** Inferred type for {@link AsyncResponseFormatSchema}. */
export type AsyncResponseFormat = z.infer<typeof AsyncResponseFormatSchema>;

/** Convenience constants matching the Python enum members. */
export const AsyncResponseFormat = {
  MINIMAL: "minimal",
  STANDARD: "standard",
  FULL: "full",
} as const satisfies Record<string, AsyncResponseFormat>;

// ── Task Status ──────────────────────────────────────────────────────

/**
 * Lifecycle status of an async background task.
 *
 * - `pending`    — Task created but not yet started.
 * - `processing` — Task is actively running.
 * - `complete`   — Task finished successfully.
 * - `failed`     — Task finished with an error.
 * - `cancelled`  — Task was cancelled.
 *
 * Maps to Python: `models.TaskStatus`
 */
export const TaskStatusSchema = z.enum([
  "pending",
  "processing",
  "complete",
  "failed",
  "cancelled",
]);

/** Inferred type for {@link TaskStatusSchema}. */
export type TaskStatus = z.infer<typeof TaskStatusSchema>;

/** Convenience constants matching the Python enum members. */
export const TaskStatus = {
  PENDING: "pending",
  PROCESSING: "processing",
  COMPLETE: "complete",
  FAILED: "failed",
  CANCELLED: "cancelled",
} as const satisfies Record<string, TaskStatus>;

// ── Actor Type ───────────────────────────────────────────────────────

/**
 * Type of actor performing a cache operation.
 *
 * - `user`   — Human user interacting with the system.
 * - `agent`  — AI agent (LLM, assistant) operating on behalf of a user.
 * - `system` — Internal system process with elevated privileges.
 *
 * Maps to Python: `access.actor.ActorType`
 */
export const ActorTypeSchema = z.enum(["user", "agent", "system"]);

/** Inferred type for {@link ActorTypeSchema}. */
export type ActorType = z.infer<typeof ActorTypeSchema>;

/** Convenience constants matching the Python enum members. */
export const ActorType = {
  USER: "user",
  AGENT: "agent",
  SYSTEM: "system",
} as const satisfies Record<string, ActorType>;
