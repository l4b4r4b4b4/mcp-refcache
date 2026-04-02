/**
 * Cache model schemas.
 *
 * Defines the core data structures for cache references, responses,
 * pagination, and internal cache entries. These are the primary types
 * that flow through the public API of mcp-refcache.
 *
 * Maps to Python: `models.CacheReference`, `models.CacheResponse`,
 * `models.PaginatedResponse`, `backends.base.CacheEntry`
 *
 * @module
 */

import { z } from "zod";

import { PreviewStrategySchema } from "./enums.js";
import { AccessPolicySchema } from "./permissions.js";

// ── Cache Reference ──────────────────────────────────────────────────

/**
 * Reference to a cached value.
 *
 * This is what gets returned to agents instead of the full value.
 * The agent can use this reference to:
 * - Paginate through the data
 * - Pass to another tool (server resolves it)
 * - Request the full value (if permitted)
 *
 * Maps to Python: `models.CacheReference`
 *
 * @example
 * ```typescript
 * const ref = CacheReferenceSchema.parse({
 *   refId: "my-cache:a1b2c3d4e5f6",
 *   cacheName: "my-cache",
 *   namespace: "session",
 *   toolName: "get_users",
 *   createdAt: Date.now() / 1000,
 *   totalItems: 5000,
 * });
 * ```
 */
export const CacheReferenceSchema = z.object({
  /** Unique identifier for this cached value (format: "cachename:hexhash"). */
  refId: z.string().min(1).describe("Unique identifier for this cached value."),

  /** Name of the cache containing this value. */
  cacheName: z
    .string()
    .min(1)
    .describe("Name of the cache containing this value."),

  /** Namespace for isolation and access control. */
  namespace: z
    .string()
    .default("public")
    .describe("Namespace for isolation and access control."),

  /** Name of the tool that created this reference. */
  toolName: z
    .string()
    .nullish()
    .default(null)
    .describe("Name of the tool that created this reference."),

  /** Unix timestamp (seconds) when the reference was created. */
  createdAt: z
    .number()
    .describe("Unix timestamp when the reference was created."),

  /** Unix timestamp (seconds) when the reference expires (null = never). */
  expiresAt: z
    .number()
    .nullish()
    .default(null)
    .describe("Unix timestamp when the reference expires (null = never)."),

  /** Total number of items if the cached value is a collection. */
  totalItems: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe(
      "Total number of items if the cached value is a collection.",
    ),

  /** Total size in bytes of the cached value. */
  totalSize: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe("Total size in bytes of the cached value."),

  /** Estimated token count of the full value. */
  totalTokens: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe("Estimated token count of the full value."),
});

/** Inferred type for {@link CacheReferenceSchema}. */
export type CacheReference = z.infer<typeof CacheReferenceSchema>;

// ── Paginated Response ───────────────────────────────────────────────

/**
 * Response containing a page of data with navigation info.
 *
 * Maps to Python: `models.PaginatedResponse`
 *
 * @example
 * ```typescript
 * const page = PaginatedResponseSchema.parse({
 *   items: [1, 2, 3],
 *   page: 1,
 *   pageSize: 20,
 *   totalItems: 100,
 *   totalPages: 5,
 *   hasNext: true,
 *   hasPrevious: false,
 * });
 * ```
 */
export const PaginatedResponseSchema = z.object({
  /** Items in the current page. */
  items: z.array(z.unknown()).describe("Items in the current page."),

  /** Current page number (1-indexed). */
  page: z.number().int().min(1).describe("Current page number (1-indexed)."),

  /** Number of items per page. */
  pageSize: z.number().int().min(1).describe("Number of items per page."),

  /** Total number of items across all pages. */
  totalItems: z
    .number()
    .int()
    .nonnegative()
    .describe("Total number of items across all pages."),

  /** Total number of pages. */
  totalPages: z
    .number()
    .int()
    .nonnegative()
    .describe("Total number of pages."),

  /** Whether there are more pages after this one. */
  hasNext: z
    .boolean()
    .describe("Whether there are more pages after this one."),

  /** Whether there are pages before this one. */
  hasPrevious: z
    .boolean()
    .describe("Whether there are pages before this one."),
});

/** Inferred type for {@link PaginatedResponseSchema}. */
export type PaginatedResponse = z.infer<typeof PaginatedResponseSchema>;

/**
 * Create a paginated response from a full list of items.
 *
 * Mirrors Python's `PaginatedResponse.from_list()` class method.
 *
 * @param items    - The complete list of items to paginate.
 * @param page     - The page number to return (1-indexed, default 1).
 * @param pageSize - Number of items per page (default 20).
 * @returns A validated {@link PaginatedResponse}.
 *
 * @example
 * ```typescript
 * const allUsers = Array.from({ length: 100 }, (_, index) => ({ id: index }));
 * const page1 = paginateList(allUsers, 1, 20);
 * // { items: [...20 items], page: 1, totalPages: 5, hasNext: true, ... }
 * ```
 */
export function paginateList(
  items: readonly unknown[],
  page: number = 1,
  pageSize: number = 20,
): PaginatedResponse {
  const totalItems = items.length;
  const totalPages =
    totalItems > 0 ? Math.ceil(totalItems / pageSize) : 0;
  const startIndex = (page - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const pageItems = items.slice(startIndex, endIndex);

  return PaginatedResponseSchema.parse({
    items: pageItems,
    page,
    pageSize,
    totalItems,
    totalPages,
    hasNext: page < totalPages,
    hasPrevious: page > 1,
  });
}

// ── Cache Response ───────────────────────────────────────────────────

/**
 * Standard response format for cached values.
 *
 * Combines reference metadata with preview/value data.
 * This is what MCP tools should return for large responses.
 *
 * Maps to Python: `models.CacheResponse`
 *
 * @example
 * ```typescript
 * const response = CacheResponseSchema.parse({
 *   refId: "my-cache:abc123",
 *   cacheName: "my-cache",
 *   totalItems: 5000,
 *   totalTokens: 25000,
 *   originalSize: 25000,
 *   previewSize: 950,
 *   preview: [{ id: 1 }, { id: 100 }, { id: 500 }],
 *   previewStrategy: "sample",
 *   availableActions: ["get_page", "resolve_full", "pass_to_tool"],
 * });
 * ```
 */
export const CacheResponseSchema = z.object({
  // --- Reference info (always present) ---

  /** Reference ID for accessing the cached value. */
  refId: z
    .string()
    .min(1)
    .describe("Reference ID for accessing the cached value."),

  /** Name of the cache containing this value. */
  cacheName: z
    .string()
    .min(1)
    .describe("Name of the cache containing this value."),

  /** Namespace for isolation. */
  namespace: z
    .string()
    .default("public")
    .describe("Namespace for isolation."),

  // --- Metadata about the full value ---

  /** Total number of items if the value is a collection. */
  totalItems: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe(
      "Total number of items if the value is a collection.",
    ),

  /** Estimated token count of the full value. */
  totalTokens: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe("Estimated token count of the full value."),

  // --- Size metadata from PreviewResult ---

  /** Size of the original value (in tokens or characters). */
  originalSize: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe(
      "Size of the original value (in tokens or characters).",
    ),

  /** Size of the preview (in tokens or characters). */
  previewSize: z
    .number()
    .int()
    .nonnegative()
    .nullish()
    .default(null)
    .describe("Size of the preview (in tokens or characters)."),

  // --- The preview (structured, not stringified!) ---

  /** Preview of the value (structured data, respects size limit). */
  preview: z
    .unknown()
    .describe(
      "Preview of the value (structured data, respects size limit).",
    ),

  /** Strategy used to generate the preview. */
  previewStrategy: PreviewStrategySchema.describe(
    "Strategy used to generate the preview.",
  ),

  // --- Pagination info (if applicable) ---

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

  // --- Available actions ---

  /**
   * Actions available to the agent.
   *
   * Defaults to `["get_page", "resolve_full", "pass_to_tool"]`.
   */
  availableActions: z
    .array(z.string())
    .default(["get_page", "resolve_full", "pass_to_tool"])
    .describe("Actions available to the agent."),
});

/** Inferred type for {@link CacheResponseSchema}. */
export type CacheResponse = z.infer<typeof CacheResponseSchema>;

// ── Cache Entry (Internal) ───────────────────────────────────────────

/**
 * Internal storage format for cached values.
 *
 * This is what backends store. It contains the value plus all metadata
 * needed for access control, expiration, and retrieval. Not part of the
 * public API — use {@link CacheReference} and {@link CacheResponse} instead.
 *
 * Maps to Python: `backends.base.CacheEntry`
 *
 * @example
 * ```typescript
 * const entry = CacheEntrySchema.parse({
 *   value: { users: [...] },
 *   namespace: "session",
 *   policy: { userPermissions: Permission.FULL, agentPermissions: Permission.READ },
 *   createdAt: Date.now() / 1000,
 *   expiresAt: Date.now() / 1000 + 3600,
 *   metadata: { toolName: "get_users", totalItems: 5000 },
 * });
 * ```
 */
export const CacheEntrySchema = z.object({
  /** The cached value (any JSON-serializable data). */
  value: z.unknown().describe("The cached value (any JSON-serializable data)."),

  /** Isolation namespace for this entry. */
  namespace: z.string().describe("Isolation namespace for this entry."),

  /** Access control policy for users and agents. */
  policy: AccessPolicySchema.describe(
    "Access control policy for users and agents.",
  ),

  /** Unix timestamp (seconds) when the entry was created. */
  createdAt: z
    .number()
    .describe("Unix timestamp when the entry was created."),

  /** Unix timestamp (seconds) when the entry expires (null = never). */
  expiresAt: z
    .number()
    .nullish()
    .default(null)
    .describe("Unix timestamp when the entry expires (null = never)."),

  /** Additional metadata (tool_name, total_items, etc.). */
  metadata: z
    .record(z.unknown())
    .default({})
    .describe("Additional metadata (toolName, totalItems, etc.)."),
});

/** Inferred type for {@link CacheEntrySchema}. */
export type CacheEntry = z.infer<typeof CacheEntrySchema>;

/**
 * Check if a cache entry has expired.
 *
 * Mirrors Python's `CacheEntry.is_expired()` method.
 *
 * @param entry       - The cache entry to check.
 * @param currentTime - Current Unix timestamp in seconds (defaults to `Date.now() / 1000`).
 * @returns `true` if the entry has an expiration time that has passed.
 */
export function isExpired(
  entry: CacheEntry,
  currentTime: number = Date.now() / 1000,
): boolean {
  if (entry.expiresAt == null) {
    return false;
  }
  return currentTime >= entry.expiresAt;
}
