/**
 * Async task model schemas.
 *
 * Defines data structures for tracking background computations that
 * exceed the `asyncTimeout` threshold. These types power the polling
 * API: when a tool takes too long, the decorator returns an
 * {@link AsyncTaskResponse} immediately, and the client polls until
 * the task reaches a terminal state.
 *
 * Maps to Python: `models.TaskProgress`, `models.RetryInfo`,
 * `models.TaskInfo`, `models.ExpectedSchema`, `models.AsyncTaskResponse`
 *
 * @module
 */

import { z } from "zod";

import { AsyncResponseFormatSchema, TaskStatusSchema } from "./enums.js";

// ── Task Progress ────────────────────────────────────────────────────

/**
 * Progress information for long-running tasks.
 *
 * Tools can report progress via the progress callback protocol,
 * enabling clients to display meaningful progress updates while polling.
 *
 * Maps to Python: `models.TaskProgress`
 *
 * @example
 * ```typescript
 * const progress = TaskProgressSchema.parse({
 *   current: 15,
 *   total: 50,
 *   message: "Indexing video 15/50",
 * });
 * // progress.percentage is auto-calculated: 30
 * ```
 */
export const TaskProgressSchema = z
  .object({
    /** Current item/step number (0-indexed or 1-indexed by convention). */
    current: z
      .number()
      .int()
      .nonnegative()
      .nullish()
      .default(null)
      .describe("Current item/step number."),

    /** Total items/steps expected for completion. */
    total: z
      .number()
      .int()
      .nonnegative()
      .nullish()
      .default(null)
      .describe("Total items/steps expected for completion."),

    /** Human-readable progress message for display. */
    message: z
      .string()
      .nullish()
      .default(null)
      .describe("Human-readable progress message for display."),

    /**
     * Completion percentage (0–100).
     * Auto-calculated from current/total if not provided.
     */
    percentage: z
      .number()
      .min(0)
      .max(100)
      .nullish()
      .default(null)
      .describe("Completion percentage (0–100)."),
  })
  .transform((value) => {
    // Auto-calculate percentage if current and total are provided
    // Mirrors Python's model_post_init behavior
    if (
      value.percentage == null &&
      value.current != null &&
      value.total != null &&
      value.total > 0
    ) {
      return { ...value, percentage: (value.current / value.total) * 100 };
    }
    return value;
  });

/** Inferred type for {@link TaskProgressSchema}. */
export type TaskProgress = z.output<typeof TaskProgressSchema>;

/**
 * Input type for {@link TaskProgressSchema} (before transform).
 * Use this when constructing progress objects before parsing.
 */
export type TaskProgressInput = z.input<typeof TaskProgressSchema>;

// ── Retry Info ───────────────────────────────────────────────────────

/**
 * Information about a single retry attempt.
 *
 * Stored in `TaskInfo.retryHistory` for debugging and analysis.
 *
 * Maps to Python: `models.RetryInfo`
 */
export const RetryInfoSchema = z.object({
  /** Retry attempt number (1-indexed). */
  attempt: z
    .number()
    .int()
    .min(1)
    .describe("Retry attempt number (1-indexed)."),

  /** Error message that triggered this retry. */
  error: z.string().describe("Error message that triggered this retry."),

  /** Unix timestamp (seconds) when the retry was initiated. */
  timestamp: z
    .number()
    .describe("Unix timestamp when the retry was initiated."),
});

/** Inferred type for {@link RetryInfoSchema}. */
export type RetryInfo = z.infer<typeof RetryInfoSchema>;

// ── Expected Schema ──────────────────────────────────────────────────

/**
 * Schema information for the expected result of an async task.
 *
 * Provides type hints and structure preview so agents know what
 * to expect when the task completes. Included only in "full"
 * response format.
 *
 * Maps to Python: `models.ExpectedSchema`
 */
export const ExpectedSchemaSchema = z.object({
  /** String representation of the return type annotation. */
  returnType: z
    .string()
    .nullish()
    .default(null)
    .describe("String representation of the return type annotation."),

  /** Field names and their types (for dict/object returns). */
  fields: z
    .record(z.string())
    .nullish()
    .default(null)
    .describe("Field names and their types (for object returns)."),

  /** Example/default structure of the expected result. */
  example: z
    .unknown()
    .nullish()
    .default(null)
    .describe("Example/default structure of the expected result."),

  /** Description of what the result contains. */
  description: z
    .string()
    .nullish()
    .default(null)
    .describe("Description of what the result contains."),
});

/** Inferred type for {@link ExpectedSchemaSchema}. */
export type ExpectedSchema = z.infer<typeof ExpectedSchemaSchema>;

// ── Task Info (Internal) ─────────────────────────────────────────────

/**
 * Internal tracking information for an async task.
 *
 * Stores the complete state of a background task, including status,
 * progress, timing, error information, and retry history. Not returned
 * directly to clients — use {@link AsyncTaskResponse} for API responses.
 *
 * Maps to Python: `models.TaskInfo`
 *
 * @example
 * ```typescript
 * const taskInfo = TaskInfoSchema.parse({
 *   refId: "default:abc123",
 *   status: "processing",
 *   startedAt: Date.now() / 1000,
 *   progress: { current: 5, total: 50 },
 * });
 * ```
 */
export const TaskInfoSchema = z.object({
  /** Reference ID for the cached result (once complete). */
  refId: z
    .string()
    .describe("Reference ID for the cached result (once complete)."),

  /** Current task status. */
  status: TaskStatusSchema.default("pending").describe("Current task status."),

  /** Progress information if reported by the task. */
  progress: TaskProgressSchema.nullish().default(null).describe(
    "Progress information if reported by the task.",
  ),

  /** Unix timestamp (seconds) when the task started. */
  startedAt: z
    .number()
    .describe("Unix timestamp when the task started."),

  /** Unix timestamp (seconds) when the task completed (success, failure, or cancel). */
  completedAt: z
    .number()
    .nullish()
    .default(null)
    .describe("Unix timestamp when the task completed."),

  /** Error message if task failed. */
  error: z
    .string()
    .nullish()
    .default(null)
    .describe("Error message if task failed."),

  /** Number of retry attempts made so far. */
  retryCount: z
    .number()
    .int()
    .nonnegative()
    .default(0)
    .describe("Number of retry attempts made so far."),

  /** Maximum retry attempts allowed for this task. */
  maxRetries: z
    .number()
    .int()
    .nonnegative()
    .default(3)
    .describe("Maximum retry attempts allowed for this task."),

  /** History of all retry attempts with errors and timestamps. */
  retryHistory: z
    .array(RetryInfoSchema)
    .default([])
    .describe("History of all retry attempts."),
});

/** Inferred type for {@link TaskInfoSchema}. */
export type TaskInfo = z.infer<typeof TaskInfoSchema>;

/**
 * Check if a task can be retried.
 *
 * Returns `true` if the task has failed and hasn't exhausted retries.
 * Mirrors Python's `TaskInfo.can_retry` property.
 *
 * @param taskInfo - The task info to check.
 * @returns `true` if the task is eligible for retry.
 */
export function canRetry(taskInfo: TaskInfo): boolean {
  return (
    taskInfo.status === "failed" && taskInfo.retryCount < taskInfo.maxRetries
  );
}

/**
 * Check if a task is in a terminal state.
 *
 * Terminal states are: complete, failed (with exhausted retries), cancelled.
 * Mirrors Python's `TaskInfo.is_terminal` property.
 *
 * @param taskInfo - The task info to check.
 * @returns `true` if the task will not change state further.
 */
export function isTerminal(taskInfo: TaskInfo): boolean {
  if (taskInfo.status === "complete" || taskInfo.status === "cancelled") {
    return true;
  }
  return taskInfo.status === "failed" && !canRetry(taskInfo);
}

/**
 * Calculate elapsed seconds since a task started.
 *
 * Mirrors Python's `TaskInfo.elapsed_seconds` property.
 *
 * @param taskInfo    - The task info to measure.
 * @param currentTime - Current Unix timestamp in seconds (defaults to `Date.now() / 1000`).
 * @returns Elapsed time in seconds.
 */
export function elapsedSeconds(
  taskInfo: TaskInfo,
  currentTime: number = Date.now() / 1000,
): number {
  const endTime = taskInfo.completedAt ?? currentTime;
  return endTime - taskInfo.startedAt;
}

// ── Async Task Response ──────────────────────────────────────────────

/**
 * Response format for in-flight async computations.
 *
 * Returned when polling for a task that hasn't completed yet.
 * Provides status, progress, timing, and retry information.
 *
 * The detail level is controlled by {@link AsyncResponseFormat}:
 * - `minimal`  — refId, status, isAsync only.
 * - `standard` — Above + startedAt, progress, message.
 * - `full`     — Above + expectedSchema, etaSeconds, retryInfo.
 *
 * Maps to Python: `models.AsyncTaskResponse`
 *
 * @example
 * ```typescript
 * const response = AsyncTaskResponseSchema.parse({
 *   refId: "default:abc123",
 *   status: "processing",
 *   startedAt: "2025-01-15T12:00:00Z",
 *   progress: { current: 15, total: 50 },
 *   etaSeconds: 45.0,
 *   message: "Processing item 15/50",
 * });
 * ```
 */
export const AsyncTaskResponseSchema = z.object({
  /** Reference ID for polling and eventual result retrieval. */
  refId: z
    .string()
    .describe("Reference ID for polling and eventual result retrieval."),

  /** Current task status. */
  status: TaskStatusSchema.describe("Current task status."),

  /** Progress information if available. */
  progress: TaskProgressSchema.nullish().default(null).describe(
    "Progress information if available.",
  ),

  /** ISO 8601 timestamp when the task started. */
  startedAt: z
    .string()
    .describe("ISO 8601 timestamp when the task started."),

  /** Estimated seconds until completion (based on progress rate). */
  etaSeconds: z
    .number()
    .nonnegative()
    .nullish()
    .default(null)
    .describe("Estimated seconds until completion."),

  /** Error message if status is "failed". */
  error: z
    .string()
    .nullish()
    .default(null)
    .describe('Error message if status is "failed".'),

  /** Number of retry attempts made so far. */
  retryCount: z
    .number()
    .int()
    .nonnegative()
    .default(0)
    .describe("Number of retry attempts made so far."),

  /** Whether the task can be retried (if failed). */
  canRetry: z
    .boolean()
    .default(true)
    .describe("Whether the task can be retried (if failed)."),

  /** Human-readable status message for the client. */
  message: z
    .string()
    .nullish()
    .default(null)
    .describe("Human-readable status message for the client."),

  /** Schema of expected result (included in "full" format only). */
  expectedSchema: ExpectedSchemaSchema.nullish()
    .default(null)
    .describe('Schema of expected result (included in "full" format only).'),
});

/** Inferred type for {@link AsyncTaskResponseSchema}. */
export type AsyncTaskResponse = z.infer<typeof AsyncTaskResponseSchema>;

// ── Factory Functions ────────────────────────────────────────────────

/**
 * Default status messages by task status.
 *
 * Used by {@link asyncTaskResponseFromInfo} when no custom message is provided.
 */
const DEFAULT_STATUS_MESSAGES: Record<string, (taskInfo: TaskInfo) => string> = {
  processing: (taskInfo) =>
    taskInfo.progress?.message ??
    `Task is processing (ref_id=${taskInfo.refId})`,
  pending: () => "Task is queued and will start shortly",
  failed: (taskInfo) => `Task failed: ${taskInfo.error ?? "unknown error"}`,
  cancelled: () => "Task was cancelled",
  complete: () => "Task completed successfully",
};

/**
 * Create an {@link AsyncTaskResponse} from internal {@link TaskInfo}.
 *
 * Mirrors Python's `AsyncTaskResponse.from_task_info()` class method.
 *
 * @param taskInfo       - Internal task tracking information.
 * @param options        - Optional overrides.
 * @param options.etaSeconds      - ETA override (calculated externally).
 * @param options.message         - Human-readable message override.
 * @param options.expectedSchema  - Schema of expected result (for "full" format).
 * @param options.responseFormat  - Detail level for the response (default: "standard").
 * @returns An {@link AsyncTaskResponse} suitable for returning to clients.
 *
 * @example
 * ```typescript
 * const taskInfo = TaskInfoSchema.parse({
 *   refId: "default:abc123",
 *   status: "processing",
 *   startedAt: Date.now() / 1000,
 *   progress: { current: 10, total: 100 },
 * });
 *
 * const response = asyncTaskResponseFromInfo(taskInfo, {
 *   etaSeconds: 90,
 *   responseFormat: "standard",
 * });
 * ```
 */
export function asyncTaskResponseFromInfo(
  taskInfo: TaskInfo,
  options: {
    etaSeconds?: number | null;
    message?: string | null;
    expectedSchema?: ExpectedSchema | null;
    responseFormat?: z.input<typeof AsyncResponseFormatSchema>;
  } = {},
): AsyncTaskResponse {
  const {
    etaSeconds = null,
    expectedSchema = null,
    responseFormat = "standard",
  } = options;

  const startedAtIso = new Date(taskInfo.startedAt * 1000).toISOString();

  // Generate default message based on status
  const resolvedMessage =
    options.message ??
    (DEFAULT_STATUS_MESSAGES[taskInfo.status]?.(taskInfo) ??
      `Task status: ${taskInfo.status}`);

  const taskCanRetry = canRetry(taskInfo);

  // Build response based on format level
  if (responseFormat === "minimal") {
    return AsyncTaskResponseSchema.parse({
      refId: taskInfo.refId,
      status: taskInfo.status,
      startedAt: startedAtIso,
    });
  }

  if (responseFormat === "standard") {
    return AsyncTaskResponseSchema.parse({
      refId: taskInfo.refId,
      status: taskInfo.status,
      progress: taskInfo.progress,
      startedAt: startedAtIso,
      etaSeconds,
      error: taskInfo.error,
      retryCount: taskInfo.retryCount,
      canRetry: taskCanRetry,
      message: resolvedMessage,
    });
  }

  // "full" format
  return AsyncTaskResponseSchema.parse({
    refId: taskInfo.refId,
    status: taskInfo.status,
    progress: taskInfo.progress,
    startedAt: startedAtIso,
    etaSeconds,
    error: taskInfo.error,
    retryCount: taskInfo.retryCount,
    canRetry: taskCanRetry,
    message: resolvedMessage,
    expectedSchema,
  });
}

/**
 * Convert an {@link AsyncTaskResponse} to a plain dictionary
 * with format-appropriate fields.
 *
 * Mirrors Python's `AsyncTaskResponse.to_dict()` method.
 *
 * @param response       - The async task response.
 * @param responseFormat - Detail level (default: "standard").
 * @returns A plain object suitable for returning from a cached decorator.
 */
export function asyncTaskResponseToDict(
  response: AsyncTaskResponse,
  responseFormat: z.input<typeof AsyncResponseFormatSchema> = "standard",
): Record<string, unknown> {
  const base: Record<string, unknown> = {
    ref_id: response.refId,
    status: response.status,
    is_complete: false,
    is_async: true,
  };

  if (responseFormat === "minimal") {
    return base;
  }

  // standard adds these fields
  base.started_at = response.startedAt;
  base.progress = response.progress ?? null;
  base.message = response.message ?? null;

  if (responseFormat === "standard") {
    return base;
  }

  // full adds these fields
  base.eta_seconds = response.etaSeconds ?? null;
  base.error = response.error ?? null;
  base.retry_count = response.retryCount;
  base.can_retry = response.canRetry;
  base.expected_schema = response.expectedSchema ?? null;

  return base;
}
