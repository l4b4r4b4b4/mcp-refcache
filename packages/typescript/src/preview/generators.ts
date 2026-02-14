/**
 * Preview generator implementations.
 *
 * Provides three strategies for generating previews of large values:
 * - `SampleGenerator`: Binary search for optimal count, then evenly-spaced
 *   sampling from collections. Best for arrays and dicts.
 * - `PaginateGenerator`: Page-based splitting for sequential access.
 *   Good when users want to iterate through data in chunks.
 * - `TruncateGenerator`: JSON-stringify then cut at size limit with ellipsis.
 *   Escape hatch for plain text or when structured preview is not needed.
 *
 * Each generator respects the size limit measured by the injected
 * `SizeMeasurer` (tokens or characters).
 *
 * Maps to Python: `preview.SampleGenerator`, `preview.PaginateGenerator`,
 * `preview.TruncateGenerator`, `preview.get_default_generator`
 *
 * @module
 */

import type { PreviewResult } from "../models/preview.js";
import { PreviewStrategy } from "../models/enums.js";
import type { SizeMeasurer } from "../context/types.js";
import type { PreviewGenerator } from "./types.js";

// ── Serialization Helper ─────────────────────────────────────────────

/**
 * Serialize a value to a JSON string, handling non-serializable types.
 *
 * Matches Python's `json.dumps(value, default=str)` behavior.
 *
 * @param value - The value to serialize.
 * @returns JSON string representation.
 *
 * @internal
 */
function serializeToJson(value: unknown): string {
  try {
    return JSON.stringify(value, (_key, nestedValue) => {
      if (nestedValue === undefined) {
        return null;
      }
      if (
        typeof nestedValue === "bigint" ||
        typeof nestedValue === "symbol" ||
        typeof nestedValue === "function"
      ) {
        return String(nestedValue);
      }
      return nestedValue;
    });
  } catch {
    return String(value);
  }
}

// ═════════════════════════════════════════════════════════════════════
// SampleGenerator
// ═════════════════════════════════════════════════════════════════════

/**
 * Sample evenly-spaced items to fit within a size limit.
 *
 * Uses binary search to find the maximum number of items that fit within
 * the size constraint, then samples them at even intervals from the
 * original collection.
 *
 * - **Arrays**: samples evenly-spaced elements.
 * - **Objects**: samples evenly-spaced key-value pairs.
 * - **Strings**: truncates with ellipsis.
 * - **Other types**: returns as-is if it fits, otherwise JSON-truncates.
 *
 * Maps to Python: `preview.SampleGenerator`
 *
 * @example
 * ```typescript
 * const generator = new SampleGenerator();
 * const measurer = new CharacterMeasurer();
 *
 * const result = generator.generate(
 *   Array.from({ length: 1000 }, (_, index) => index),
 *   100,
 *   measurer,
 * );
 * // result.value might be [0, 111, 222, 333, ...] (~5 items)
 * ```
 */
export class SampleGenerator implements PreviewGenerator {
  /**
   * Generate a sampled preview.
   *
   * @param value    - The value to sample.
   * @param maxSize  - Maximum size in tokens or characters.
   * @param measurer - `SizeMeasurer` to measure value sizes.
   * @param _page    - Ignored for sample strategy.
   * @param _pageSize - Ignored for sample strategy.
   * @returns `PreviewResult` with sampled preview.
   */
  generate(
    value: unknown,
    maxSize: number,
    measurer: SizeMeasurer,
    _page?: number | null,
    _pageSize?: number | null,
  ): PreviewResult {
    const originalSize = measurer.measure(value);

    if (Array.isArray(value)) {
      return this.sampleList(value, maxSize, measurer, originalSize);
    }

    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      return this.sampleDict(
        value as Record<string, unknown>,
        maxSize,
        measurer,
        originalSize,
      );
    }

    if (typeof value === "string") {
      return this.truncateString(value, maxSize, measurer, originalSize);
    }

    // For other types (number, boolean, null), check if it fits
    if (originalSize <= maxSize) {
      return {
        value,
        strategy: PreviewStrategy.SAMPLE,
        originalSize,
        previewSize: originalSize,
        totalItems: null,
        previewItems: null,
        page: null,
        totalPages: null,
      };
    }

    // Doesn't fit — stringify and truncate
    return this.truncateString(
      serializeToJson(value),
      maxSize,
      measurer,
      originalSize,
    );
  }

  /**
   * Sample a list to fit within maxSize.
   *
   * @internal
   */
  private sampleList(
    items: unknown[],
    maxSize: number,
    measurer: SizeMeasurer,
    originalSize: number,
  ): PreviewResult {
    const totalItems = items.length;

    if (totalItems === 0) {
      return {
        value: [],
        strategy: PreviewStrategy.SAMPLE,
        originalSize,
        previewSize: measurer.measure([]),
        totalItems: 0,
        previewItems: 0,
        page: null,
        totalPages: null,
      };
    }

    // Check if full list fits
    if (originalSize <= maxSize) {
      return {
        value: items,
        strategy: PreviewStrategy.SAMPLE,
        originalSize,
        previewSize: originalSize,
        totalItems,
        previewItems: totalItems,
        page: null,
        totalPages: null,
      };
    }

    // Binary search for optimal count
    const targetCount = this.findTargetCount(items, maxSize, measurer);
    const sampled = sampleEvenly(items, targetCount);
    const previewSize = measurer.measure(sampled);

    return {
      value: sampled,
      strategy: PreviewStrategy.SAMPLE,
      originalSize,
      previewSize,
      totalItems,
      previewItems: sampled.length,
      page: null,
      totalPages: null,
    };
  }

  /**
   * Sample a dict to fit within maxSize.
   *
   * @internal
   */
  private sampleDict(
    value: Record<string, unknown>,
    maxSize: number,
    measurer: SizeMeasurer,
    originalSize: number,
  ): PreviewResult {
    const entries = Object.entries(value);
    const totalItems = entries.length;

    if (totalItems === 0) {
      return {
        value: {},
        strategy: PreviewStrategy.SAMPLE,
        originalSize,
        previewSize: measurer.measure({}),
        totalItems: 0,
        previewItems: 0,
        page: null,
        totalPages: null,
      };
    }

    // Check if full dict fits
    if (originalSize <= maxSize) {
      return {
        value,
        strategy: PreviewStrategy.SAMPLE,
        originalSize,
        previewSize: originalSize,
        totalItems,
        previewItems: totalItems,
        page: null,
        totalPages: null,
      };
    }

    // Binary search for optimal count
    const targetCount = this.findTargetCountDict(value, maxSize, measurer);
    const sampledEntries = sampleEvenly(entries, targetCount);
    const sampled = Object.fromEntries(sampledEntries);
    const previewSize = measurer.measure(sampled);

    return {
      value: sampled,
      strategy: PreviewStrategy.SAMPLE,
      originalSize,
      previewSize,
      totalItems,
      previewItems: sampledEntries.length,
      page: null,
      totalPages: null,
    };
  }

  /**
   * Truncate a string to fit within maxSize.
   *
   * Uses binary search to find the optimal cut point.
   *
   * @internal
   */
  private truncateString(
    value: string,
    maxSize: number,
    measurer: SizeMeasurer,
    originalSize: number,
  ): PreviewResult {
    if (originalSize <= maxSize) {
      return {
        value,
        strategy: PreviewStrategy.TRUNCATE,
        originalSize,
        previewSize: originalSize,
        totalItems: value.length,
        previewItems: value.length,
        page: null,
        totalPages: null,
      };
    }

    // Binary search for optimal length
    const ellipsis = "...";
    let low = 0;
    let high = value.length;
    let bestLength = 0;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const truncated = value.slice(0, mid) + ellipsis;
      const size = measurer.measure(truncated);

      if (size <= maxSize) {
        bestLength = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    const truncated =
      bestLength < value.length
        ? value.slice(0, bestLength) + ellipsis
        : value;
    const previewSize = measurer.measure(truncated);

    return {
      value: truncated,
      strategy: PreviewStrategy.TRUNCATE,
      originalSize,
      previewSize,
      totalItems: value.length,
      previewItems: bestLength,
      page: null,
      totalPages: null,
    };
  }

  /**
   * Binary search to find how many list items fit within maxSize.
   *
   * @internal
   */
  private findTargetCount(
    items: unknown[],
    maxSize: number,
    measurer: SizeMeasurer,
  ): number {
    let low = 1;
    let high = items.length;
    let result = 1;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const sampled = sampleEvenly(items, mid);
      const size = measurer.measure(sampled);

      if (size <= maxSize) {
        result = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    return result;
  }

  /**
   * Binary search to find how many dict items fit within maxSize.
   *
   * @internal
   */
  private findTargetCountDict(
    value: Record<string, unknown>,
    maxSize: number,
    measurer: SizeMeasurer,
  ): number {
    const entries = Object.entries(value);
    let low = 1;
    let high = entries.length;
    let result = 1;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const sampledEntries = sampleEvenly(entries, mid);
      const sampled = Object.fromEntries(sampledEntries);
      const size = measurer.measure(sampled);

      if (size <= maxSize) {
        result = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    return result;
  }
}

// ═════════════════════════════════════════════════════════════════════
// PaginateGenerator
// ═════════════════════════════════════════════════════════════════════

/** Default items per page when `pageSize` is not specified. */
const DEFAULT_PAGE_SIZE = 20;

/**
 * Split values into pages for sequential access.
 *
 * Each page respects the `maxSize` limit. If a page's items still exceed
 * the limit, items are trimmed from the end until they fit.
 *
 * - **Arrays**: sliced into page-sized chunks.
 * - **Objects**: entries sliced into page-sized chunks, reconstructed as dicts.
 * - **Other types**: returned as a single-page result.
 *
 * Maps to Python: `preview.PaginateGenerator`
 *
 * @example
 * ```typescript
 * const generator = new PaginateGenerator();
 * const measurer = new CharacterMeasurer();
 *
 * const result = generator.generate(
 *   Array.from({ length: 100 }, (_, index) => index),
 *   500,
 *   measurer,
 *   1,   // page
 *   10,  // pageSize
 * );
 * // result.value === [0, 1, 2, ..., 9]
 * // result.totalPages === 10
 * ```
 */
export class PaginateGenerator implements PreviewGenerator {
  /**
   * Generate a paginated preview.
   *
   * @param value    - The value to paginate.
   * @param maxSize  - Maximum size in tokens or characters.
   * @param measurer - `SizeMeasurer` to measure value sizes.
   * @param page     - Page number (1-indexed, defaults to 1).
   * @param pageSize - Items per page (defaults to 20).
   * @returns `PreviewResult` with page data and pagination metadata.
   */
  generate(
    value: unknown,
    maxSize: number,
    measurer: SizeMeasurer,
    page?: number | null,
    pageSize?: number | null,
  ): PreviewResult {
    const resolvedPage = page ?? 1;
    const resolvedPageSize = pageSize ?? DEFAULT_PAGE_SIZE;
    const originalSize = measurer.measure(value);

    if (Array.isArray(value)) {
      return this.paginateList(
        value,
        maxSize,
        measurer,
        originalSize,
        resolvedPage,
        resolvedPageSize,
      );
    }

    if (typeof value === "object" && value !== null) {
      return this.paginateDict(
        value as Record<string, unknown>,
        maxSize,
        measurer,
        originalSize,
        resolvedPage,
        resolvedPageSize,
      );
    }

    // For non-collection types, treat as single-page
    return {
      value,
      strategy: PreviewStrategy.PAGINATE,
      originalSize,
      previewSize: originalSize,
      totalItems: 1,
      previewItems: 1,
      page: 1,
      totalPages: 1,
    };
  }

  /**
   * Paginate a list.
   *
   * @internal
   */
  private paginateList(
    items: unknown[],
    maxSize: number,
    measurer: SizeMeasurer,
    originalSize: number,
    page: number,
    pageSize: number,
  ): PreviewResult {
    const totalItems = items.length;
    const totalPages = totalItems > 0 ? Math.ceil(totalItems / pageSize) : 0;

    // Calculate page slice
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    let pageItems = items.slice(startIndex, endIndex);

    // Trim page if it exceeds maxSize
    if (pageItems.length > 0) {
      pageItems = trimListToFit(pageItems, maxSize, measurer);
    }

    const previewSize = measurer.measure(pageItems);

    return {
      value: pageItems,
      strategy: PreviewStrategy.PAGINATE,
      originalSize,
      previewSize,
      totalItems,
      previewItems: pageItems.length,
      page,
      totalPages,
    };
  }

  /**
   * Paginate a dict.
   *
   * @internal
   */
  private paginateDict(
    value: Record<string, unknown>,
    maxSize: number,
    measurer: SizeMeasurer,
    originalSize: number,
    page: number,
    pageSize: number,
  ): PreviewResult {
    const entries = Object.entries(value);
    const totalItems = entries.length;
    const totalPages = totalItems > 0 ? Math.ceil(totalItems / pageSize) : 0;

    // Calculate page slice
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const pageEntries = entries.slice(startIndex, endIndex);

    // Convert to dict
    let pageDict = Object.fromEntries(pageEntries);

    // Trim if exceeds maxSize
    if (Object.keys(pageDict).length > 0) {
      pageDict = trimDictToFit(pageDict, maxSize, measurer);
    }

    const previewSize = measurer.measure(pageDict);

    return {
      value: pageDict,
      strategy: PreviewStrategy.PAGINATE,
      originalSize,
      previewSize,
      totalItems,
      previewItems: Object.keys(pageDict).length,
      page,
      totalPages,
    };
  }
}

// ═════════════════════════════════════════════════════════════════════
// TruncateGenerator
// ═════════════════════════════════════════════════════════════════════

/**
 * Truncate values as JSON strings with ellipsis.
 *
 * This is the escape hatch for when structured sampling is not appropriate.
 * Values are JSON-serialized and then truncated to fit the limit, with
 * `"..."` appended to indicate truncation.
 *
 * Maps to Python: `preview.TruncateGenerator`
 *
 * @example
 * ```typescript
 * const generator = new TruncateGenerator();
 * const measurer = new CharacterMeasurer();
 *
 * const result = generator.generate("a".repeat(1000), 50, measurer);
 * // result.value === "aaaaaa..."
 * // result.previewSize <= 50
 * ```
 */
export class TruncateGenerator implements PreviewGenerator {
  /**
   * Generate a truncated preview.
   *
   * @param value     - The value to truncate.
   * @param maxSize   - Maximum size in tokens or characters.
   * @param measurer  - `SizeMeasurer` to measure value sizes.
   * @param _page     - Ignored for truncate strategy.
   * @param _pageSize - Ignored for truncate strategy.
   * @returns `PreviewResult` with truncated string preview.
   */
  generate(
    value: unknown,
    maxSize: number,
    measurer: SizeMeasurer,
    _page?: number | null,
    _pageSize?: number | null,
  ): PreviewResult {
    // Convert to string if not already
    let text: string;
    let totalItems: number | null;

    if (typeof value === "string") {
      text = value;
      totalItems = value.length;
    } else {
      text = serializeToJson(value);
      totalItems = countItems(value);
    }

    const originalSize = measurer.measure(text);

    // Check if it fits
    if (originalSize <= maxSize) {
      return {
        value: typeof value === "string" ? value : text,
        strategy: PreviewStrategy.TRUNCATE,
        originalSize,
        previewSize: originalSize,
        totalItems,
        previewItems: totalItems,
        page: null,
        totalPages: null,
      };
    }

    // Binary search for optimal truncation point
    const ellipsis = "...";
    let low = 0;
    let high = text.length;
    let bestLength = 0;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const truncated = text.slice(0, mid) + ellipsis;
      const size = measurer.measure(truncated);

      if (size <= maxSize) {
        bestLength = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    const truncated = text.slice(0, bestLength) + ellipsis;
    const previewSize = measurer.measure(truncated);

    return {
      value: truncated,
      strategy: PreviewStrategy.TRUNCATE,
      originalSize,
      previewSize,
      totalItems,
      previewItems: bestLength,
      page: null,
      totalPages: null,
    };
  }
}

// ═════════════════════════════════════════════════════════════════════
// Factory Function
// ═════════════════════════════════════════════════════════════════════

/**
 * Get a default `PreviewGenerator` for the given strategy.
 *
 * Maps to Python: `preview.get_default_generator`
 *
 * @param strategy - The preview strategy to use.
 * @returns A `PreviewGenerator` implementation.
 *
 * @example
 * ```typescript
 * const generator = getDefaultGenerator("sample");
 * const result = generator.generate(value, 100, measurer);
 * ```
 */
export function getDefaultGenerator(
  strategy: string,
): PreviewGenerator {
  switch (strategy) {
    case PreviewStrategy.SAMPLE:
      return new SampleGenerator();
    case PreviewStrategy.PAGINATE:
      return new PaginateGenerator();
    case PreviewStrategy.TRUNCATE:
      return new TruncateGenerator();
    default:
      // Default to sample
      return new SampleGenerator();
  }
}

// ═════════════════════════════════════════════════════════════════════
// Shared Helpers
// ═════════════════════════════════════════════════════════════════════

/**
 * Sample `count` items evenly spaced from an array.
 *
 * The first and last items are always included when `count >= 2`.
 * Matches Python: `SampleGenerator._sample_evenly`.
 *
 * @param items - The array to sample from.
 * @param count - Number of items to select.
 * @returns Evenly-spaced subset of the input array.
 *
 * @internal
 */
function sampleEvenly<T>(items: T[], count: number): T[] {
  if (count >= items.length) {
    return items;
  }
  if (count <= 0) {
    return [];
  }
  if (count === 1) {
    return [items[0]!];
  }

  const step = (items.length - 1) / (count - 1);
  return Array.from({ length: count }, (_, index) => {
    return items[Math.round(index * step)]!;
  });
}

/**
 * Trim a list to fit within maxSize using binary search.
 *
 * Removes items from the end until the serialized list fits.
 * Matches Python: `PaginateGenerator._trim_to_fit`.
 *
 * @param items    - The list to trim.
 * @param maxSize  - Maximum size in measurer units.
 * @param measurer - SizeMeasurer to measure value sizes.
 * @returns Trimmed list that fits within maxSize.
 *
 * @internal
 */
function trimListToFit(
  items: unknown[],
  maxSize: number,
  measurer: SizeMeasurer,
): unknown[] {
  if (measurer.measure(items) <= maxSize) {
    return items;
  }

  let low = 0;
  let high = items.length;
  let result = 0;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const trimmed = items.slice(0, mid);
    if (measurer.measure(trimmed) <= maxSize) {
      result = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return items.slice(0, result);
}

/**
 * Trim a dict to fit within maxSize using binary search.
 *
 * Removes entries from the end until the serialized dict fits.
 * Matches Python: `PaginateGenerator._trim_dict_to_fit`.
 *
 * @param value    - The dict to trim.
 * @param maxSize  - Maximum size in measurer units.
 * @param measurer - SizeMeasurer to measure value sizes.
 * @returns Trimmed dict that fits within maxSize.
 *
 * @internal
 */
function trimDictToFit(
  value: Record<string, unknown>,
  maxSize: number,
  measurer: SizeMeasurer,
): Record<string, unknown> {
  if (measurer.measure(value) <= maxSize) {
    return value;
  }

  const entries = Object.entries(value);
  let low = 0;
  let high = entries.length;
  let result = 0;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const trimmed = Object.fromEntries(entries.slice(0, mid));
    if (measurer.measure(trimmed) <= maxSize) {
      result = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return Object.fromEntries(entries.slice(0, result));
}

/**
 * Count items in a collection value.
 *
 * @param value - The value to count items in.
 * @returns Number of items, or `null` for non-collection types.
 *
 * @internal
 */
function countItems(value: unknown): number | null {
  if (Array.isArray(value)) {
    return value.length;
  }
  if (typeof value === "object" && value !== null) {
    return Object.keys(value).length;
  }
  return null;
}
