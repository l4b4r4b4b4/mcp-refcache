/**
 * Backend interface types for cache storage.
 *
 * Defines the `CacheBackend` interface that all storage implementations
 * must satisfy. This is the TypeScript equivalent of Python's
 * `CacheBackend` protocol (duck-typed via structural typing).
 *
 * All methods return `Promise<T>` so the interface works uniformly
 * across in-memory, SQLite, and Redis backends. `MemoryBackend`
 * resolves immediately; async backends (Redis, SQLite) perform
 * real I/O inside their implementations.
 *
 * Maps to Python: `backends.base.CacheBackend`
 *
 * @module
 */

import type { CacheEntry } from "../models/cache.js";

// ── CacheBackend Interface ───────────────────────────────────────────

/**
 * Interface defining the contract for cache storage backends.
 *
 * All cache backends (memory, SQLite, Redis, etc.) must implement this
 * interface. TypeScript enforces compliance via structural typing — any
 * object with these methods satisfies `CacheBackend`.
 *
 * Every method is async (`Promise`-returning) so the same interface
 * works for both in-memory and networked/disk-based backends without
 * requiring separate sync/async variants.
 *
 * @example
 * ```typescript
 * import type { CacheBackend } from "./types.js";
 * import type { CacheEntry } from "../models/cache.js";
 *
 * class MyCustomBackend implements CacheBackend {
 *   async get(key: string): Promise<CacheEntry | null> { ... }
 *   async set(key: string, entry: CacheEntry): Promise<void> { ... }
 *   async delete(key: string): Promise<boolean> { ... }
 *   async exists(key: string): Promise<boolean> { ... }
 *   async clear(namespace?: string): Promise<number> { ... }
 *   async keys(namespace?: string): Promise<string[]> { ... }
 * }
 *
 * // Works because it has all required methods
 * const backend: CacheBackend = new MyCustomBackend();
 * ```
 */
export interface CacheBackend {
  /**
   * Retrieve an entry by key.
   *
   * If the entry exists but is expired, the implementation should
   * delete it and return `null` (lazy eviction).
   *
   * @param key - The cache key to look up.
   * @returns The `CacheEntry` if found and not expired, `null` otherwise.
   */
  get(key: string): Promise<CacheEntry | null>;

  /**
   * Store an entry under the given key.
   *
   * If an entry already exists for this key, it is overwritten.
   *
   * @param key   - The cache key to store under.
   * @param entry - The `CacheEntry` to store.
   */
  set(key: string, entry: CacheEntry): Promise<void>;

  /**
   * Delete an entry by key.
   *
   * @param key - The cache key to delete.
   * @returns `true` if the entry existed and was deleted, `false` if
   *          the key was not found.
   */
  delete(key: string): Promise<boolean>;

  /**
   * Check if a key exists and is not expired.
   *
   * If the entry exists but is expired, the implementation should
   * delete it and return `false` (lazy eviction).
   *
   * @param key - The cache key to check.
   * @returns `true` if the key exists and is not expired, `false` otherwise.
   */
  exists(key: string): Promise<boolean>;

  /**
   * Clear entries from the cache.
   *
   * @param namespace - If provided, only clear entries in this namespace.
   *                    If omitted or `undefined`, clear all entries.
   * @returns The number of entries that were removed.
   */
  clear(namespace?: string): Promise<number>;

  /**
   * List all non-expired keys in the cache.
   *
   * Expired entries should be excluded from the result. Implementations
   * may also clean up expired entries encountered during iteration.
   *
   * @param namespace - If provided, only return keys whose entry belongs
   *                    to this namespace. If omitted, return all keys.
   * @returns Array of cache keys.
   */
  keys(namespace?: string): Promise<string[]>;
}
