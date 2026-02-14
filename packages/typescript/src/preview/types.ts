/**
 * Interface for preview generation strategies.
 *
 * Defines the contract that all preview generators (sample, paginate,
 * truncate) must satisfy. Generators transform large values into
 * smaller previews that fit within size constraints while preserving
 * as much useful information as possible.
 *
 * Maps to Python: `preview.PreviewGenerator`
 *
 * @module
 */

import type { PreviewResult } from "../models/preview.js";
import type { SizeMeasurer } from "../context/types.js";

// ── PreviewGenerator Interface ───────────────────────────────────────

/**
 * Contract for preview generation strategies.
 *
 * Implementations transform large values into smaller previews that fit
 * within size constraints. The strategy used determines how the value
 * is reduced:
 *
 * - **sample**: Evenly-spaced items from collections (best for arrays/dicts).
 * - **paginate**: Page-based splitting for sequential access.
 * - **truncate**: String truncation with ellipsis (escape hatch for text).
 *
 * @example
 * ```typescript
 * import type { PreviewGenerator } from "./types.js";
 * import { CharacterMeasurer } from "../context/measurers.js";
 *
 * class MyGenerator implements PreviewGenerator {
 *   generate(
 *     value: unknown,
 *     maxSize: number,
 *     measurer: SizeMeasurer,
 *   ): PreviewResult {
 *     // Custom preview logic...
 *   }
 * }
 * ```
 */
export interface PreviewGenerator {
  /**
   * Generate a preview of a value within size constraints.
   *
   * The generator should measure the original value's size, and if it
   * exceeds `maxSize`, produce a reduced version that fits. The returned
   * `PreviewResult` includes both the preview data and metadata about
   * the transformation (original size, preview size, items sampled, etc.).
   *
   * @param value    - The value to create a preview of.
   * @param maxSize  - Maximum size in tokens or characters (determined
   *                   by the `measurer`'s unit).
   * @param measurer - `SizeMeasurer` to measure value sizes.
   * @param page     - Page number for pagination (1-indexed, optional).
   *                   Ignored by non-paginate strategies.
   * @param pageSize - Items per page for pagination (optional).
   *                   Ignored by non-paginate strategies.
   * @returns `PreviewResult` with the preview data and metadata.
   */
  generate(
    value: unknown,
    maxSize: number,
    measurer: SizeMeasurer,
    page?: number | null,
    pageSize?: number | null,
  ): PreviewResult;
}
