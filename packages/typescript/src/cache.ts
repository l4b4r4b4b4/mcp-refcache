/**
 * RefCache: Main cache interface for mcp-refcache.
 *
 * Provides the primary API for caching values and managing references
 * with namespace isolation and permission-based access control.
 *
 * Maps to Python: `cache.py`
 *
 * @module
 */

import { createHash } from "crypto";

import type { ActorLike } from "./access/actor.js";
import { resolveActor } from "./access/actor.js";
import type { PermissionChecker } from "./access/checker.js";
import { DefaultPermissionChecker } from "./access/checker.js";
import type { CacheBackend } from "./backends/types.js";
import { MemoryBackend } from "./backends/memory.js";
import type { SizeMeasurer, Tokenizer } from "./context/types.js";
import { CharacterMeasurer, TokenMeasurer } from "./context/measurers.js";
import { TiktokenAdapter } from "./context/tokenizers.js";
import type { AccessPolicy } from "./models/permissions.js";
import { AccessPolicySchema, Permission } from "./models/permissions.js";
import type { CacheEntry, CacheReference, CacheResponse } from "./models/cache.js";
import { CacheEntrySchema, CacheReferenceSchema, CacheResponseSchema } from "./models/cache.js";
import type { PreviewConfig, PreviewResult } from "./models/preview.js";
import { PreviewConfigSchema } from "./models/preview.js";
import { SizeMode } from "./models/enums.js";
import type { PreviewGenerator } from "./preview/types.js";
import {
  getDefaultGenerator,
  PaginateGenerator,
  SampleGenerator,
} from "./preview/generators.js";

// ── RefCacheOptions ──────────────────────────────────────────────────

/**
 * Options for constructing a RefCache instance.
 *
 * All options are optional — sensible defaults are provided.
 *
 * @example
 * ```typescript
 * // Simple usage with defaults
 * const cache = new RefCache();
 *
 * // Custom configuration
 * const cache = new RefCache({
 *   name: "my-app",
 *   defaultTtl: 7200,
 *   previewConfig: { maxSize: 500, defaultStrategy: "truncate" },
 * });
 *
 * // With tiktoken for accurate token counting
 * const cache = new RefCache({
 *   tokenizer: new TiktokenAdapter("gpt-4o"),
 * });
 * ```
 */
export interface RefCacheOptions {
  /** Name of this cache instance (default: "default"). */
  name?: string;

  /** Storage backend. Defaults to MemoryBackend. */
  backend?: CacheBackend;

  /** Default access policy for new entries. */
  defaultPolicy?: AccessPolicy;

  /** Default TTL in seconds. `null` means no expiration (default: 3600). */
  defaultTtl?: number | null;

  /** Configuration for preview generation. */
  previewConfig?: PreviewConfig;

  /**
   * Tokenizer for token counting. If provided without measurer,
   * a TokenMeasurer is created automatically.
   */
  tokenizer?: Tokenizer;

  /**
   * Size measurer for preview generation. Takes precedence over
   * tokenizer if both are provided.
   */
  measurer?: SizeMeasurer;

  /** Generator for creating previews. Defaults to generator matching config strategy. */
  previewGenerator?: PreviewGenerator;

  /**
   * Permission checker for access control. Defaults to
   * DefaultPermissionChecker which enforces namespace ownership rules.
   */
  permissionChecker?: PermissionChecker;
}

// ── Set/Get/Resolve/Delete Options ───────────────────────────────────

/**
 * Options for {@link RefCache.set}.
 */
export interface SetOptions {
  /** Isolation namespace (default: "public"). */
  namespace?: string;

  /** Access control policy. Defaults to cache's default policy. */
  policy?: AccessPolicy;

  /** Time-to-live in seconds. `null` uses cache default. */
  ttl?: number | null;

  /** Name of the tool that created this reference. */
  toolName?: string;
}

/**
 * Options for {@link RefCache.get}.
 */
export interface GetOptions {
  /** Page number for pagination (1-indexed). */
  page?: number | null;

  /** Number of items per page. */
  pageSize?: number | null;

  /**
   * Maximum preview size (tokens/chars). Overrides server default.
   * Use smaller values for quick summaries, larger for more context.
   */
  maxSize?: number | null;

  /** Who is requesting. Can be an Actor object or literal "user"/"agent". */
  actor?: ActorLike;
}

/**
 * Options for {@link RefCache.resolve}.
 */
export interface ResolveOptions {
  /** Who is requesting. Can be an Actor object or literal "user"/"agent". */
  actor?: ActorLike;
}

/**
 * Options for {@link RefCache.delete}.
 */
export interface DeleteOptions {
  /** Who is requesting. Can be an Actor object or literal "user"/"agent". */
  actor?: ActorLike;
}

// ── RefCache ─────────────────────────────────────────────────────────

/**
 * Main cache interface for storing values and managing references.
 *
 * RefCache provides a reference-based caching system with:
 * - Namespace isolation for multi-tenant scenarios
 * - Separate permissions for users and agents
 * - TTL-based expiration
 * - Preview generation for large values
 * - Integration with access control system
 *
 * All methods are async because the {@link CacheBackend} interface
 * is async (supporting both in-memory and networked backends).
 * For `MemoryBackend`, promises resolve immediately (microtask).
 *
 * Maps to Python: `cache.RefCache`
 *
 * @example
 * ```typescript
 * const cache = new RefCache({ name: "my-cache" });
 *
 * // Store a value and get a reference
 * const ref = await cache.set("user_data", { name: "Alice", items: [1, 2, 3] });
 *
 * // Get a preview of the value
 * const response = await cache.get(ref.refId);
 * console.log(response.preview);
 *
 * // Resolve to get the full value
 * const value = await cache.resolve(ref.refId);
 * ```
 */
export class RefCache {
  /** Name of this cache instance. */
  readonly name: string;

  /** Default access policy for new entries. */
  defaultPolicy: AccessPolicy;

  /** Default TTL in seconds. `null` means no expiration. */
  defaultTtl: number | null;

  /** Configuration for preview generation. */
  previewConfig: PreviewConfig;

  /** @internal Storage backend. */
  private readonly backend: CacheBackend;

  /** @internal Size measurer for preview generation. */
  private readonly measurer: SizeMeasurer;

  /** @internal Preview generator for creating previews. */
  private readonly previewGenerator: PreviewGenerator;

  /** @internal Permission checker for access control. */
  private readonly permissionChecker: PermissionChecker;

  /** @internal Mapping from namespaced key to ref_id. */
  private readonly keyToRef: Map<string, string> = new Map();

  /** @internal Mapping from ref_id to original key. */
  private readonly refToKey: Map<string, string> = new Map();

  /**
   * Create a new RefCache instance.
   *
   * @param options - Configuration options (all optional with sensible defaults).
   *
   * @example
   * ```typescript
   * // Simple usage with tiktoken
   * const cache = new RefCache({
   *   tokenizer: new TiktokenAdapter("gpt-4o"),
   * });
   *
   * // Custom permission checker with namespace resolver
   * const checker = new DefaultPermissionChecker(new DefaultNamespaceResolver());
   * const cache = new RefCache({ permissionChecker: checker });
   * ```
   */
  constructor(options: RefCacheOptions = {}) {
    this.name = options.name ?? "default";
    this.backend = options.backend ?? new MemoryBackend();

    this.defaultPolicy =
      options.defaultPolicy ?? AccessPolicySchema.parse({});

    this.defaultTtl = options.defaultTtl !== undefined
      ? options.defaultTtl
      : 3600;

    this.previewConfig =
      options.previewConfig ?? PreviewConfigSchema.parse({});

    // Determine measurer: explicit > from tokenizer > default
    if (options.measurer !== undefined) {
      this.measurer = options.measurer;
    } else if (options.tokenizer !== undefined) {
      this.measurer = new TokenMeasurer(options.tokenizer);
    } else {
      // Default: TOKEN mode with TiktokenAdapter (falls back to CharacterFallback)
      if (this.previewConfig.sizeMode === SizeMode.TOKEN) {
        this.measurer = new TokenMeasurer(new TiktokenAdapter());
      } else {
        this.measurer = new CharacterMeasurer();
      }
    }

    // Determine preview generator: explicit > from config
    this.previewGenerator =
      options.previewGenerator ??
      getDefaultGenerator(this.previewConfig.defaultStrategy);

    // Permission checker for access control
    this.permissionChecker =
      options.permissionChecker ?? new DefaultPermissionChecker();
  }

  // ── Public API ───────────────────────────────────────────────────

  /**
   * Store a value in the cache and return a reference.
   *
   * @param key     - Unique identifier for this value within the namespace.
   * @param value   - The value to cache. Should be JSON-serializable.
   * @param options - Optional settings for namespace, policy, TTL, and tool name.
   * @returns A CacheReference that can be used to retrieve the value.
   *
   * @example
   * ```typescript
   * const ref = await cache.set("user_123", { name: "Alice" });
   * console.log(ref.refId); // Use this to retrieve later
   *
   * // With custom namespace and policy
   * const ref = await cache.set("secret", data, {
   *   namespace: "user:alice",
   *   policy: { agentPermissions: Permission.EXECUTE },
   *   ttl: 300,
   * });
   * ```
   */
  async set(
    key: string,
    value: unknown,
    options: SetOptions = {},
  ): Promise<CacheReference> {
    const namespace = options.namespace ?? "public";
    const policy = options.policy ?? this.defaultPolicy;
    const effectiveTtl =
      options.ttl !== undefined ? options.ttl : this.defaultTtl;

    const createdAt = Date.now() / 1000;
    const expiresAt =
      effectiveTtl !== null ? createdAt + effectiveTtl : null;

    // Generate a unique ref_id
    const refId = this.generateRefId(key, namespace);

    // Calculate metadata
    const totalItems = this.countItems(value);
    const totalSize = this.estimateSize(value);

    const metadata: Record<string, unknown> = {
      toolName: options.toolName ?? null,
      totalItems,
      totalSize,
    };

    // Create the cache entry
    const entry = CacheEntrySchema.parse({
      value,
      namespace,
      policy,
      createdAt,
      expiresAt,
      metadata,
    });

    // Store in backend using ref_id as the key
    await this.backend.set(refId, entry);

    // Update mappings
    this.keyToRef.set(this.makeNamespacedKey(key, namespace), refId);
    this.refToKey.set(refId, key);

    // Create and return the reference
    return CacheReferenceSchema.parse({
      refId,
      cacheName: this.name,
      namespace,
      toolName: options.toolName ?? null,
      createdAt,
      expiresAt,
      totalItems,
      totalSize,
    });
  }

  /**
   * Get a preview of a cached value.
   *
   * Returns a CacheResponse with a preview of the value, generated
   * according to the configured preview strategy and size limits.
   *
   * @param refId   - Reference ID or key to look up.
   * @param options - Optional settings for pagination, max size, and actor.
   * @returns CacheResponse with preview data and metadata.
   *
   * @throws Error if the reference is not found.
   * @throws PermissionDenied if the actor lacks READ permission.
   *
   * @example
   * ```typescript
   * const response = await cache.get(ref.refId);
   * console.log(response.preview);
   *
   * // With pagination
   * const page2 = await cache.get(ref.refId, { page: 2, pageSize: 10 });
   *
   * // With actor
   * const response = await cache.get(ref.refId, {
   *   actor: DefaultActor.user({ actorId: "alice" }),
   * });
   * ```
   */
  async get(
    refId: string,
    options: GetOptions = {},
  ): Promise<CacheResponse> {
    const entry = await this.getEntry(refId);

    // Check permissions
    const actor = options.actor ?? "agent";
    this.checkPermission(entry.policy, Permission.READ, actor, entry.namespace);

    // Generate preview
    const previewResult = this.createPreview(
      entry.value,
      options.page ?? null,
      options.pageSize ?? null,
      options.maxSize ?? null,
    );

    return CacheResponseSchema.parse({
      refId,
      cacheName: this.name,
      namespace: entry.namespace,
      totalItems: previewResult.totalItems,
      originalSize: previewResult.originalSize,
      previewSize: previewResult.previewSize,
      preview: previewResult.value,
      previewStrategy: previewResult.strategy,
      page: previewResult.page,
      totalPages: previewResult.totalPages,
    });
  }

  /**
   * Resolve a reference to get the full cached value.
   *
   * @param refId   - Reference ID or key to look up.
   * @param options - Optional settings for actor.
   * @returns The full cached value.
   *
   * @throws Error if the reference is not found.
   * @throws PermissionDenied if the actor lacks READ permission.
   *
   * @example
   * ```typescript
   * const value = await cache.resolve(ref.refId);
   * console.log(value); // Full value
   *
   * // With actor
   * const value = await cache.resolve(ref.refId, {
   *   actor: DefaultActor.user({ actorId: "alice" }),
   * });
   * ```
   */
  async resolve(
    refId: string,
    options: ResolveOptions = {},
  ): Promise<unknown> {
    const entry = await this.getEntry(refId);

    // Check permissions
    const actor = options.actor ?? "agent";
    this.checkPermission(entry.policy, Permission.READ, actor, entry.namespace);

    return entry.value;
  }

  /**
   * Delete a cached entry.
   *
   * @param refId   - Reference ID or key to delete.
   * @param options - Optional settings for actor.
   * @returns `true` if deleted, `false` if not found.
   *
   * @throws PermissionDenied if the actor lacks DELETE permission.
   *
   * @example
   * ```typescript
   * const deleted = await cache.delete(ref.refId, { actor: "user" });
   * ```
   */
  async delete(
    refId: string,
    options: DeleteOptions = {},
  ): Promise<boolean> {
    // Try to get the entry to check permissions
    let entry: CacheEntry;
    try {
      entry = await this.getEntry(refId);
    } catch {
      return false;
    }

    const actor = options.actor ?? "agent";
    this.checkPermission(
      entry.policy,
      Permission.DELETE,
      actor,
      entry.namespace,
    );

    // Get the actual backend key
    const backendKey = await this.resolveToBackendKey(refId);
    if (backendKey === null) {
      return false;
    }

    // Clean up mappings
    const originalKey = this.refToKey.get(backendKey);
    if (originalKey !== undefined) {
      const namespacedKey = this.makeNamespacedKey(
        originalKey,
        entry.namespace,
      );
      this.keyToRef.delete(namespacedKey);
      this.refToKey.delete(backendKey);
    }

    return this.backend.delete(backendKey);
  }

  /**
   * Check if a reference exists and is not expired.
   *
   * @param refId - Reference ID or key to check.
   * @returns `true` if exists and not expired, `false` otherwise.
   *
   * @example
   * ```typescript
   * if (await cache.exists(ref.refId)) {
   *   console.log("Still cached!");
   * }
   * ```
   */
  async exists(refId: string): Promise<boolean> {
    const backendKey = await this.resolveToBackendKey(refId);
    if (backendKey === null) {
      return false;
    }
    return this.backend.exists(backendKey);
  }

  /**
   * Clear entries from the cache.
   *
   * @param namespace - If provided, only clear entries in this namespace.
   * @returns Number of entries cleared.
   *
   * @example
   * ```typescript
   * // Clear everything
   * const count = await cache.clear();
   *
   * // Clear only session entries
   * const count = await cache.clear("session:abc");
   * ```
   */
  async clear(namespace?: string): Promise<number> {
    // Clear from backend
    const cleared = await this.backend.clear(namespace);

    // Clear mappings
    if (namespace === undefined) {
      this.keyToRef.clear();
      this.refToKey.clear();
    } else {
      // Remove mappings for cleared namespace
      const keysToRemove: Array<[string, string]> = [];
      for (const [namespacedKey, mappedRefId] of this.keyToRef) {
        if (namespacedKey.startsWith(`${namespace}:`)) {
          keysToRemove.push([namespacedKey, mappedRefId]);
        }
      }

      for (const [namespacedKey, mappedRefId] of keysToRemove) {
        this.keyToRef.delete(namespacedKey);
        this.refToKey.delete(mappedRefId);
      }
    }

    return cleared;
  }

  // ── Testing Helpers ────────────────────────────────────────────────

  /**
   * Update the value of an existing cache entry (for testing only).
   *
   * This method exists to support circular reference detection tests
   * where we need to manually create self-referencing entries.
   *
   * @param refId - The ref_id of the entry to update.
   * @param newValue - The new value to store.
   *
   * @throws Error if the entry does not exist.
   *
   * @internal
   */
  async setEntryValueForTesting(
    refId: string,
    newValue: unknown,
  ): Promise<void> {
    const entry = await this.backend.get(refId);
    if (entry === null) {
      throw new Error(
        `Cannot update entry for testing: '${refId}' not found`,
      );
    }

    // Create a new entry with the updated value
    const updatedEntry = CacheEntrySchema.parse({
      ...entry,
      value: newValue,
    });
    await this.backend.set(refId, updatedEntry);
  }

  // ── Internal Accessors (for resolution module) ─────────────────────

  /**
   * Get the internal backend (for advanced usage / testing).
   *
   * @internal
   */
  getBackend(): CacheBackend {
    return this.backend;
  }

  // ── Private Helper Methods ─────────────────────────────────────────

  /**
   * Generate a unique reference ID.
   *
   * Uses SHA-256 hash of a composite key including cache name,
   * namespace, key, and current timestamp to produce a unique
   * ref_id in the format "cachename:hexhash".
   *
   * @param key       - The original cache key.
   * @param namespace - The namespace for this entry.
   * @returns A ref_id string (e.g., "my-cache:a1b2c3d4e5f67890").
   *
   * @internal
   */
  private generateRefId(key: string, namespace: string): string {
    const composite = `${this.name}:${namespace}:${key}:${Date.now() / 1000}`;
    const hashValue = createHash("sha256")
      .update(composite)
      .digest("hex")
      .slice(0, 16);
    return `${this.name}:${hashValue}`;
  }

  /**
   * Create a namespaced key for internal lookups.
   *
   * @param key       - The original cache key.
   * @param namespace - The namespace.
   * @returns Combined key in format "namespace:key".
   *
   * @internal
   */
  private makeNamespacedKey(key: string, namespace: string): string {
    return `${namespace}:${key}`;
  }

  /**
   * Resolve a ref_id or key to the backend storage key.
   *
   * Tries direct ref_id lookup first, then searches by key
   * across namespaces.
   *
   * @param refId - The ref_id or key to resolve.
   * @returns The backend key, or `null` if not found.
   *
   * @internal
   */
  private async resolveToBackendKey(refId: string): Promise<string | null> {
    // Direct ref_id lookup
    if (await this.backend.exists(refId)) {
      return refId;
    }

    // Try as a key in each namespace
    for (const [namespacedKey, storedRefId] of this.keyToRef) {
      // Check if refId matches the key part and entry exists
      if (
        namespacedKey.endsWith(`:${refId}`) &&
        (await this.backend.exists(storedRefId))
      ) {
        return storedRefId;
      }
    }

    return null;
  }

  /**
   * Get a cache entry by ref_id or key.
   *
   * @param refId - The ref_id or key to look up.
   * @returns The CacheEntry.
   *
   * @throws Error if the reference is not found or expired.
   *
   * @internal
   */
  private async getEntry(refId: string): Promise<CacheEntry> {
    const backendKey = await this.resolveToBackendKey(refId);
    if (backendKey === null) {
      throw new Error(`Reference '${refId}' not found`);
    }

    const entry = await this.backend.get(backendKey);
    if (entry === null) {
      throw new Error(`Reference '${refId}' not found or expired`);
    }

    return entry;
  }

  /**
   * Check if an actor has the required permission.
   *
   * @param policy    - The access policy to evaluate.
   * @param required  - The permission required for the operation.
   * @param actor     - The actor attempting the operation (Actor or literal).
   * @param namespace - The namespace of the resource.
   *
   * @throws PermissionDenied if the actor lacks the required permission.
   *
   * @internal
   */
  private checkPermission(
    policy: AccessPolicy,
    required: number,
    actor: ActorLike,
    namespace: string,
  ): void {
    const resolvedActorInstance = resolveActor(actor);
    this.permissionChecker.check(
      policy,
      required,
      resolvedActorInstance,
      namespace,
    );
  }

  /**
   * Count items in a collection.
   *
   * @param value - The value to count items in.
   * @returns Number of items, or `null` if not a collection.
   *
   * @internal
   */
  private countItems(value: unknown): number | null {
    if (Array.isArray(value)) {
      return value.length;
    }
    if (value !== null && typeof value === "object") {
      return Object.keys(value as Record<string, unknown>).length;
    }
    return null;
  }

  /**
   * Estimate size of a value in bytes.
   *
   * @param value - The value to estimate size of.
   * @returns Estimated size in bytes, or `null` if estimation fails.
   *
   * @internal
   */
  private estimateSize(value: unknown): number | null {
    try {
      const serialized = JSON.stringify(value, (_key, nestedValue) => {
        if (nestedValue === undefined) return null;
        if (typeof nestedValue === "bigint") return String(nestedValue);
        return nestedValue;
      });
      return new TextEncoder().encode(serialized).length;
    } catch {
      return null;
    }
  }

  /**
   * Create a preview of a value using the configured generator.
   *
   * When a page number is specified and the configured generator is
   * SampleGenerator, automatically switches to PaginateGenerator for
   * that call. This ensures pagination "just works" regardless of the
   * default preview strategy.
   *
   * @param value    - The value to create a preview of.
   * @param page     - Page number for pagination (1-indexed).
   * @param pageSize - Number of items per page.
   * @param maxSize  - Maximum preview size. Overrides server default.
   * @returns PreviewResult with preview data and metadata.
   *
   * @internal
   */
  private createPreview(
    value: unknown,
    page: number | null,
    pageSize: number | null,
    maxSize: number | null,
  ): PreviewResult {
    // Use provided max_size or fall back to config default
    const effectiveMaxSize = maxSize ?? this.previewConfig.maxSize;

    // Auto-switch to PaginateGenerator when page is specified
    // This ensures pagination works regardless of default strategy
    let generator = this.previewGenerator;
    if (page !== null && generator instanceof SampleGenerator) {
      generator = new PaginateGenerator();
    }

    return generator.generate(
      value,
      effectiveMaxSize,
      this.measurer,
      page,
      pageSize,
    );
  }
}
