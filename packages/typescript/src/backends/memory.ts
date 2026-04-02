/**
 * In-memory cache backend implementation.
 *
 * Provides a Map-based storage backend with lazy TTL expiration.
 * This is the default backend for RefCache when no other backend
 * is configured.
 *
 * JavaScript is single-threaded, so no locking is needed (unlike
 * the Python version which uses `threading.RLock`).
 *
 * Maps to Python: `backends.memory.MemoryBackend`
 *
 * @module
 */

import type { CacheEntry } from "../models/cache.js";
import { isExpired } from "../models/cache.js";
import type { CacheBackend } from "./types.js";

// ── MemoryBackend ────────────────────────────────────────────────────

/**
 * In-memory cache backend using a `Map` for storage.
 *
 * Expired entries are cleaned up lazily on access — when a `get()` or
 * `exists()` call encounters an expired entry, it deletes it and returns
 * as if the key does not exist. The `keys()` method also filters out
 * and cleans up expired entries during iteration.
 *
 * All methods are async (returning `Promise`) to satisfy the
 * `CacheBackend` interface, which must also support networked
 * backends like Redis. For `MemoryBackend`, the promises resolve
 * immediately since there is no I/O.
 *
 * @example
 * ```typescript
 * import { MemoryBackend } from "./memory.js";
 * import { CacheEntrySchema } from "../models/cache.js";
 *
 * const backend = new MemoryBackend();
 *
 * const entry = CacheEntrySchema.parse({
 *   value: { data: "example" },
 *   namespace: "public",
 *   policy: {},
 *   createdAt: Date.now() / 1000,
 * });
 *
 * await backend.set("my_key", entry);
 * const result = await backend.get("my_key");
 * // result?.value === { data: "example" }
 * ```
 */
export class MemoryBackend implements CacheBackend {
  /**
   * Internal storage map. Keys are cache keys, values are `CacheEntry` objects.
   *
   * @internal
   */
  private readonly storage: Map<string, CacheEntry> = new Map();

  /**
   * Retrieve an entry by key.
   *
   * If the entry exists but is expired, it is deleted and `null` is
   * returned (lazy eviction).
   *
   * @param key - The cache key to look up.
   * @returns The `CacheEntry` if found and not expired, `null` otherwise.
   */
  async get(key: string): Promise<CacheEntry | null> {
    const entry = this.storage.get(key);
    if (entry === undefined) {
      return null;
    }

    if (isExpired(entry)) {
      this.storage.delete(key);
      return null;
    }

    return entry;
  }

  /**
   * Store an entry under the given key.
   *
   * If an entry already exists for this key, it is overwritten.
   *
   * @param key   - The cache key to store under.
   * @param entry - The `CacheEntry` to store.
   */
  async set(key: string, entry: CacheEntry): Promise<void> {
    this.storage.set(key, entry);
  }

  /**
   * Delete an entry by key.
   *
   * @param key - The cache key to delete.
   * @returns `true` if the entry existed and was deleted, `false` if
   *          the key was not found.
   */
  async delete(key: string): Promise<boolean> {
    return this.storage.delete(key);
  }

  /**
   * Check if a key exists and is not expired.
   *
   * If the entry exists but is expired, it is deleted and `false` is
   * returned (lazy eviction).
   *
   * @param key - The cache key to check.
   * @returns `true` if the key exists and is not expired, `false` otherwise.
   */
  async exists(key: string): Promise<boolean> {
    const entry = this.storage.get(key);
    if (entry === undefined) {
      return false;
    }

    if (isExpired(entry)) {
      this.storage.delete(key);
      return false;
    }

    return true;
  }

  /**
   * Clear entries from the cache.
   *
   * When `namespace` is provided, only entries belonging to that exact
   * namespace are removed. When omitted, all entries are removed.
   *
   * @param namespace - If provided, only clear entries in this namespace.
   *                    If omitted or `undefined`, clear all entries.
   * @returns The number of entries that were removed.
   */
  async clear(namespace?: string): Promise<number> {
    if (namespace === undefined) {
      const count = this.storage.size;
      this.storage.clear();
      return count;
    }

    const keysToDelete: string[] = [];
    for (const [key, entry] of this.storage) {
      if (entry.namespace === namespace) {
        keysToDelete.push(key);
      }
    }

    for (const key of keysToDelete) {
      this.storage.delete(key);
    }

    return keysToDelete.length;
  }

  /**
   * List all non-expired keys in the cache.
   *
   * Expired entries are excluded from the result and cleaned up
   * during iteration (matching the Python implementation's behavior).
   *
   * @param namespace - If provided, only return keys whose entry belongs
   *                    to this namespace. If omitted, return all non-expired keys.
   * @returns Array of cache keys.
   */
  async keys(namespace?: string): Promise<string[]> {
    const currentTime = Date.now() / 1000;
    const result: string[] = [];
    const expiredKeys: string[] = [];

    for (const [key, entry] of this.storage) {
      if (isExpired(entry, currentTime)) {
        expiredKeys.push(key);
      } else if (namespace === undefined || entry.namespace === namespace) {
        result.push(key);
      }
    }

    // Clean up expired entries
    for (const key of expiredKeys) {
      this.storage.delete(key);
    }

    return result;
  }
}
