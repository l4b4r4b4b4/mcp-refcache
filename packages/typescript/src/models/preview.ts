/**
 * Preview configuration schemas.
 *
 * Defines how cached values are previewed when returned to agents,
 * controlling size limits and the strategy used to generate previews.
 *
 * Maps to Python: `models.PreviewConfig`
 *
 * @module
 */

import { z } from "zod";

import { PreviewStrategySchema, SizeModeSchema } from "./enums.js";

// ── Preview Config ───────────────────────────────────────────────────

/**
 * Configuration for context limiting behavior.
 *
 * Controls how large cached values are previewed before being returned
 * to the LLM, ensuring they fit within context window limits.
 *
 * Maps to Python: `models.PreviewConfig`
 *
 * @example
 * ```typescript
 * // Default config: 1000 tokens, sample strategy
 * const config = PreviewConfigSchema.parse({});
 *
 * // Custom config: 500 characters, truncate strategy
 * const custom = PreviewConfigSchema.parse({
 *   sizeMode: "character",
 *   maxSize: 500,
 *   defaultStrategy: "truncate",
 * });
 * ```
 */
export const PreviewConfigSchema = z.object({
  /** How to measure size (tokens or characters). */
  sizeMode: SizeModeSchema.default("token").describe(
    "How to measure size (tokens or characters).",
  ),

  /**
   * Maximum size in tokens or characters.
   * Must be a positive integer.
   */
  maxSize: z
    .number()
    .int()
    .positive()
    .default(1000)
    .describe("Maximum size in tokens or characters."),

  /** Default strategy for generating previews. */
  defaultStrategy: PreviewStrategySchema.default("sample").describe(
    "Default strategy for generating previews.",
  ),
});

/** Inferred type for {@link PreviewConfigSchema}. */
export type PreviewConfig = z.infer<typeof PreviewConfigSchema>;

// ── Preview Result ───────────────────────────────────────────────────

/**
 * Result of generating a preview from a cached value.
 *
 * Contains both the preview data and metadata about sizing,
 * so callers know what was truncated/sampled/paginated.
 *
 * Maps to Python: `preview.PreviewResult`
 *
 * @example
 * ```typescript
 * const result = PreviewResultSchema.parse({
 *   value: [1, 2, 3],
 *   originalSize: 5000,
 *   previewSize: 450,
 *   strategy: "sample",
 *   totalItems: 200,
 *   previewItems: 10,
 * });
 * ```
 */
export const PreviewResultSchema = z.object({
  /** The preview data (structured, not stringified). */
  value: z.unknown().describe("The preview data (structured, not stringified)."),

  /** Size of the original value (in tokens or characters). */
  originalSize: z
    .number()
    .int()
    .nonnegative()
    .describe("Size of the original value (in tokens or characters)."),

  /** Size of the preview (in tokens or characters). */
  previewSize: z
    .number()
    .int()
    .nonnegative()
    .describe("Size of the preview (in tokens or characters)."),

  /** Strategy that was used to generate this preview. */
  strategy: PreviewStrategySchema.describe(
    "Strategy that was used to generate this preview.",
  ),

  /** Total number of items in the original value (if a collection). */
  totalItems: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe(
      "Total number of items in the original value (if a collection).",
    ),

  /** Number of items included in the preview (if a collection). */
  previewItems: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe(
      "Number of items included in the preview (if a collection).",
    ),

  /** Current page number (if paginated). */
  page: z
    .number()
    .int()
    .positive()
    .nullish()
    .default(null)
    .describe("Current page number (if paginated)."),

  /** Total pages available (if paginated). */
  totalPages: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe("Total pages available (if paginated)."),
});

/** Inferred type for {@link PreviewResultSchema}. */
export type PreviewResult = z.infer<typeof PreviewResultSchema>;
