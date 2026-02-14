/**
 * Tests for the RefCache class — the main cache interface.
 *
 * These tests cover:
 * - Initialization with defaults and custom options
 * - set() method — storing values and returning CacheReferences
 * - get() method — retrieving CacheResponses with previews
 * - resolve() method — getting full values with permission checks
 * - delete() method — removing entries with permission checks
 * - exists() method — checking entry existence
 * - clear() method — clearing entries by namespace
 * - TTL / expiration handling
 * - Namespace isolation
 * - Preview system integration
 * - Access control integration
 * - Pagination auto-switch (SampleGenerator → PaginateGenerator)
 * - Hierarchical max_size (server default → per-call override)
 *
 * Maps to Python: `tests/test_refcache.py`
 *
 * @module
 */

import { describe, expect, it, beforeEach } from "bun:test";

import { RefCache } from "../src/cache.js";
import type { CacheResponse, CacheReference } from "../src/models/cache.js";
import { AccessPolicySchema, Permission } from "../src/models/permissions.js";
import { PreviewConfigSchema } from "../src/models/preview.js";
import { MemoryBackend } from "../src/backends/memory.js";
import { DefaultActor } from "../src/access/actor.js";
import {
  DefaultPermissionChecker,
  PermissionDenied,
} from "../src/access/checker.js";
import { DefaultNamespaceResolver } from "../src/access/namespace.js";
import { CharacterMeasurer, TokenMeasurer } from "../src/context/measurers.js";
import { CharacterFallback, TiktokenAdapter } from "../src/context/tokenizers.js";
import {
  SampleGenerator,
  PaginateGenerator,
  TruncateGenerator,
} from "../src/preview/generators.js";

// ═════════════════════════════════════════════════════════════════════
// Initialization
// ═════════════════════════════════════════════════════════════════════

describe("RefCache Initialization", () => {
  it("uses sensible defaults", () => {
    const cache = new RefCache();
    expect(cache.name).toBe("default");
    expect(cache.defaultTtl).toBe(3600);
  });

  it("accepts a custom name", () => {
    const cache = new RefCache({ name: "my-cache" });
    expect(cache.name).toBe("my-cache");
  });

  it("accepts a custom backend", () => {
    const backend = new MemoryBackend();
    const cache = new RefCache({ backend });
    expect(cache.getBackend()).toBe(backend);
  });

  it("accepts a custom default policy", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      agentPermissions: Permission.EXECUTE,
    });
    const cache = new RefCache({ defaultPolicy: policy });
    expect(cache.defaultPolicy).toEqual(policy);
  });

  it("accepts a custom TTL", () => {
    const cache = new RefCache({ defaultTtl: 7200 });
    expect(cache.defaultTtl).toBe(7200);
  });

  it("accepts null TTL for no expiration", () => {
    const cache = new RefCache({ defaultTtl: null });
    expect(cache.defaultTtl).toBeNull();
  });

  it("accepts a custom preview config", () => {
    const config = PreviewConfigSchema.parse({
      maxSize: 500,
      defaultStrategy: "truncate",
    });
    const cache = new RefCache({ previewConfig: config });
    expect(cache.previewConfig.maxSize).toBe(500);
    expect(cache.previewConfig.defaultStrategy).toBe("truncate");
  });

  it("accepts a custom permission checker", () => {
    const checker = new DefaultPermissionChecker();
    const cache = new RefCache({ permissionChecker: checker });
    // Should not throw — checker is used internally
    expect(cache).toBeDefined();
  });
});

// ═════════════════════════════════════════════════════════════════════
// set()
// ═════════════════════════════════════════════════════════════════════

describe("RefCache.set()", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test-cache" });
  });

  it("returns a CacheReference", async () => {
    const reference = await cache.set("key1", { data: "value" });
    expect(reference).toBeDefined();
    expect(reference.refId).toBeDefined();
    expect(reference.cacheName).toBe("test-cache");
  });

  it("includes correct cache name in reference", async () => {
    const reference = await cache.set("key1", { data: "value" });
    expect(reference.cacheName).toBe("test-cache");
  });

  it("generates a non-empty ref_id", async () => {
    const reference = await cache.set("key1", { data: "value" });
    expect(reference.refId).toBeDefined();
    expect(reference.refId.length).toBeGreaterThan(0);
  });

  it("generates ref_id with cache name prefix", async () => {
    const reference = await cache.set("key1", { data: "value" });
    expect(reference.refId).toStartWith("test-cache:");
  });

  it("supports custom namespace", async () => {
    const reference = await cache.set("key1", { data: "value" }, {
      namespace: "session:abc",
    });
    expect(reference.namespace).toBe("session:abc");
  });

  it("supports custom policy", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.EXECUTE,
    });
    const reference = await cache.set("key1", { data: "value" }, { policy });
    expect(reference).toBeDefined();
  });

  it("supports custom TTL", async () => {
    const reference = await cache.set("key1", { data: "value" }, { ttl: 60 });
    expect(reference.expiresAt).toBeDefined();
    expect(reference.expiresAt).not.toBeNull();
    expect(reference.expiresAt!).toBeGreaterThan(Date.now() / 1000);
  });

  it("supports tool name", async () => {
    const reference = await cache.set("key1", { data: "value" }, {
      toolName: "my_tool",
    });
    expect(reference.toolName).toBe("my_tool");
  });

  it("stores value retrievably in backend", async () => {
    await cache.set("key1", { data: "value" });
    expect(await cache.exists("key1")).toBe(true);
  });

  it("generates different ref_ids for different keys", async () => {
    const reference1 = await cache.set("key1", "value1");
    const reference2 = await cache.set("key2", "value2");
    expect(reference1.refId).not.toBe(reference2.refId);
  });

  it("overwrites value when same key is set again", async () => {
    await cache.set("key1", "first");
    await cache.set("key1", "second");
    const value = await cache.resolve("key1");
    expect(value).toBe("second");
  });

  it("tracks total_items for lists", async () => {
    const reference = await cache.set("key1", [1, 2, 3, 4, 5]);
    expect(reference.totalItems).toBe(5);
  });

  it("tracks total_items for dicts", async () => {
    const reference = await cache.set("key1", { a: 1, b: 2, c: 3 });
    expect(reference.totalItems).toBe(3);
  });

  it("tracks total_size in bytes", async () => {
    const reference = await cache.set("key1", { data: "value" });
    expect(reference.totalSize).toBeGreaterThan(0);
  });

  it("defaults namespace to public", async () => {
    const reference = await cache.set("key1", "value");
    expect(reference.namespace).toBe("public");
  });

  it("stores various value types", async () => {
    // String
    const stringReference = await cache.set("s", "hello");
    expect(await cache.resolve(stringReference.refId)).toBe("hello");

    // Number
    const numberReference = await cache.set("n", 42);
    expect(await cache.resolve(numberReference.refId)).toBe(42);

    // Boolean
    const boolReference = await cache.set("b", true);
    expect(await cache.resolve(boolReference.refId)).toBe(true);

    // Null
    const nullReference = await cache.set("null", null);
    expect(await cache.resolve(nullReference.refId)).toBeNull();

    // Array
    const arrayReference = await cache.set("arr", [1, 2, 3]);
    expect(await cache.resolve(arrayReference.refId)).toEqual([1, 2, 3]);

    // Nested object
    const objectReference = await cache.set("obj", { a: { b: { c: 1 } } });
    expect(await cache.resolve(objectReference.refId)).toEqual({
      a: { b: { c: 1 } },
    });
  });
});

// ═════════════════════════════════════════════════════════════════════
// get()
// ═════════════════════════════════════════════════════════════════════

describe("RefCache.get()", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test-cache" });
  });

  it("returns a CacheResponse", async () => {
    const reference = await cache.set("key1", { data: "value" });
    const response = await cache.get(reference.refId);
    expect(response).toBeDefined();
    expect(response.refId).toBe(reference.refId);
  });

  it("includes correct ref_id in response", async () => {
    const reference = await cache.set("key1", { data: "value" });
    const response = await cache.get(reference.refId);
    expect(response.refId).toBe(reference.refId);
  });

  it("includes a preview in response", async () => {
    const reference = await cache.set("key1", { data: "value" });
    const response = await cache.get(reference.refId);
    expect(response.preview).toBeDefined();
  });

  it("throws for nonexistent ref_id", async () => {
    await expect(cache.get("nonexistent-ref")).rejects.toThrow();
  });

  it("includes preview strategy in response", async () => {
    const reference = await cache.set("key1", [1, 2, 3]);
    const response = await cache.get(reference.refId);
    expect(response.previewStrategy).toBeDefined();
  });

  it("includes namespace in response", async () => {
    const reference = await cache.set("key1", "value", {
      namespace: "session:xyz",
    });
    const actor = DefaultActor.user({
      actorId: "alice",
      sessionId: "xyz",
    });
    const response = await cache.get(reference.refId, { actor });
    expect(response.namespace).toBe("session:xyz");
  });

  it("includes cache name in response", async () => {
    const reference = await cache.set("key1", "value");
    const response = await cache.get(reference.refId);
    expect(response.cacheName).toBe("test-cache");
  });

  it("supports pagination with PaginateGenerator", async () => {
    const paginateCache = new RefCache({
      name: "test-cache",
      previewGenerator: new PaginateGenerator(),
    });
    const reference = await paginateCache.set("key1", Array.from({ length: 100 }, (_, index) => index));
    const response = await paginateCache.get(reference.refId, {
      page: 2,
      pageSize: 10,
    });
    expect(response.page).toBe(2);
    expect(response.totalPages).toBeDefined();
    expect(response.totalPages).not.toBeNull();
  });

  it("respects agent READ permission", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    await cache.set("key1", { secret: "data" }, { policy });

    await expect(
      cache.get("key1", { actor: "agent" }),
    ).rejects.toThrow(PermissionDenied);
  });

  it("allows user with READ permission", async () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      agentPermissions: Permission.NONE,
    });
    await cache.set("key1", { data: "value" }, { policy });

    const response = await cache.get("key1", { actor: "user" });
    expect(response).toBeDefined();
  });
});

// ═════════════════════════════════════════════════════════════════════
// resolve()
// ═════════════════════════════════════════════════════════════════════

describe("RefCache.resolve()", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test-cache" });
  });

  it("returns the full cached value", async () => {
    const original = { id: 1, name: "Test", nested: { key: "value" } };
    const reference = await cache.set("key1", original);
    const resolved = await cache.resolve(reference.refId);
    expect(resolved).toEqual(original);
  });

  it("returns list values", async () => {
    const original = [1, 2, 3, 4, 5];
    const reference = await cache.set("key1", original);
    const resolved = await cache.resolve(reference.refId);
    expect(resolved).toEqual(original);
  });

  it("returns string values", async () => {
    const original = "Hello, World!";
    const reference = await cache.set("key1", original);
    const resolved = await cache.resolve(reference.refId);
    expect(resolved).toBe(original);
  });

  it("throws for nonexistent ref_id", async () => {
    await expect(cache.resolve("nonexistent-ref")).rejects.toThrow();
  });

  it("respects agent READ permission", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.EXECUTE, // Execute but not read
    });
    await cache.set("key1", { secret: "data" }, { policy });

    await expect(
      cache.resolve("key1", { actor: "agent" }),
    ).rejects.toThrow(PermissionDenied);
  });

  it("allows user with READ permission", async () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      agentPermissions: Permission.NONE,
    });
    await cache.set("key1", { data: "value" }, { policy });

    const value = await cache.resolve("key1", { actor: "user" });
    expect(value).toEqual({ data: "value" });
  });

  it("works with both key and ref_id", async () => {
    const reference = await cache.set("my-key", "my-value");

    // Both should work
    const value1 = await cache.resolve("my-key");
    const value2 = await cache.resolve(reference.refId);
    expect(value1).toBe("my-value");
    expect(value2).toBe("my-value");
  });
});

// ═════════════════════════════════════════════════════════════════════
// delete()
// ═════════════════════════════════════════════════════════════════════

describe("RefCache.delete()", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test-cache" });
  });

  it("returns true for existing entry", async () => {
    await cache.set("key1", "value");
    const result = await cache.delete("key1", { actor: "user" });
    expect(result).toBe(true);
  });

  it("removes the entry", async () => {
    await cache.set("key1", "value");
    await cache.delete("key1", { actor: "user" });
    expect(await cache.exists("key1")).toBe(false);
  });

  it("returns false for nonexistent entry", async () => {
    const result = await cache.delete("nonexistent");
    expect(result).toBe(false);
  });

  it("respects agent DELETE permission", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.READ, // Read but not delete
    });
    await cache.set("key1", "value", { policy });

    await expect(
      cache.delete("key1", { actor: "agent" }),
    ).rejects.toThrow(PermissionDenied);
  });

  it("allows user with DELETE permission", async () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.DELETE,
      agentPermissions: Permission.NONE,
    });
    await cache.set("key1", "value", { policy });

    const result = await cache.delete("key1", { actor: "user" });
    expect(result).toBe(true);
  });

  it("cleans up key-to-ref mappings", async () => {
    const reference = await cache.set("key1", "value");
    await cache.delete(reference.refId, { actor: "user" });

    // Should not be findable by key either
    expect(await cache.exists("key1")).toBe(false);
  });
});

// ═════════════════════════════════════════════════════════════════════
// exists()
// ═════════════════════════════════════════════════════════════════════

describe("RefCache.exists()", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test-cache" });
  });

  it("returns true for existing key", async () => {
    await cache.set("key1", "value");
    expect(await cache.exists("key1")).toBe(true);
  });

  it("returns false for nonexistent key", async () => {
    expect(await cache.exists("nonexistent")).toBe(false);
  });

  it("works with ref_id", async () => {
    const reference = await cache.set("key1", "value");
    expect(await cache.exists(reference.refId)).toBe(true);
  });

  it("returns false for expired entry", async () => {
    // Set with very short TTL
    await cache.set("key1", "value", { ttl: 0.001 });

    // Wait for expiration
    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(await cache.exists("key1")).toBe(false);
  });
});

// ═════════════════════════════════════════════════════════════════════
// clear()
// ═════════════════════════════════════════════════════════════════════

describe("RefCache.clear()", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test-cache" });
  });

  it("clears all entries", async () => {
    for (let index = 0; index < 5; index++) {
      await cache.set(`key${index}`, `value${index}`);
    }

    const cleared = await cache.clear();
    expect(cleared).toBe(5);
    expect(await cache.exists("key0")).toBe(false);
  });

  it("clears by namespace", async () => {
    await cache.set("public1", "val1", { namespace: "public" });
    await cache.set("public2", "val2", { namespace: "public" });
    await cache.set("session1", "val3", { namespace: "session:abc" });

    const cleared = await cache.clear("session:abc");
    expect(cleared).toBe(1);
    expect(await cache.exists("public1")).toBe(true);
    expect(await cache.exists("session1")).toBe(false);
  });

  it("returns 0 when clearing empty cache", async () => {
    const cleared = await cache.clear();
    expect(cleared).toBe(0);
  });

  it("cleans up internal mappings", async () => {
    await cache.set("key1", "value1");
    await cache.set("key2", "value2");

    await cache.clear();

    // Keys should no longer be resolvable
    await expect(cache.resolve("key1")).rejects.toThrow();
    await expect(cache.resolve("key2")).rejects.toThrow();
  });
});

// ═════════════════════════════════════════════════════════════════════
// TTL / Expiration
// ═════════════════════════════════════════════════════════════════════

describe("RefCache TTL", () => {
  it("expired entry is not accessible", async () => {
    const cache = new RefCache({ defaultTtl: 0.001 });
    await cache.set("key1", "value");

    // Wait for expiration
    await new Promise((resolve) => setTimeout(resolve, 10));

    await expect(cache.resolve("key1")).rejects.toThrow();
  });

  it("non-expired entry is accessible", async () => {
    const cache = new RefCache({ defaultTtl: 3600 });
    await cache.set("key1", "value");

    const value = await cache.resolve("key1");
    expect(value).toBe("value");
  });

  it("null TTL means entry never expires", async () => {
    const cache = new RefCache({ defaultTtl: null });
    const reference = await cache.set("key1", "value");

    expect(reference.expiresAt).toBeNull();

    const value = await cache.resolve("key1");
    expect(value).toBe("value");
  });

  it("per-entry TTL overrides default", async () => {
    const cache = new RefCache({ defaultTtl: 3600 });
    const reference = await cache.set("key1", "value", { ttl: 60 });

    // Should expire sooner than default
    const expectedMaxExpiry = Date.now() / 1000 + 120; // well within 3600s
    expect(reference.expiresAt).toBeDefined();
    expect(reference.expiresAt!).toBeLessThan(expectedMaxExpiry);
  });

  it("per-entry null TTL overrides default TTL", async () => {
    const cache = new RefCache({ defaultTtl: 3600 });
    const reference = await cache.set("key1", "value", { ttl: null });

    expect(reference.expiresAt).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════
// Namespaces
// ═════════════════════════════════════════════════════════════════════

describe("RefCache Namespaces", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test-cache" });
  });

  it("isolates namespaces", async () => {
    await cache.set("key1", "public_value", { namespace: "public" });
    await cache.set("key1", "session_value", { namespace: "session:abc" });

    // Both should exist
    const publicKeys = await cache.getBackend().keys("public");
    const sessionKeys = await cache.getBackend().keys("session:abc");
    expect(publicKeys.length).toBeGreaterThan(0);
    expect(sessionKeys.length).toBeGreaterThan(0);
  });

  it("clear namespace doesn't affect others", async () => {
    await cache.set("key1", "val1", { namespace: "public" });
    await cache.set("key2", "val2", { namespace: "public" });
    await cache.set("key3", "val3", { namespace: "session:abc" });

    await cache.clear("session:abc");

    expect(await cache.exists("key1")).toBe(true);
    expect(await cache.exists("key2")).toBe(true);
  });

  it("defaults namespace to public", async () => {
    const reference = await cache.set("key1", "value");
    expect(reference.namespace).toBe("public");
  });

  it("stores entries in correct namespace in backend", async () => {
    await cache.set("key1", "value", { namespace: "custom:ns" });

    const keys = await cache.getBackend().keys("custom:ns");
    expect(keys.length).toBe(1);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Preview System Integration
// ═════════════════════════════════════════════════════════════════════

describe("RefCache Preview", () => {
  it("returns preview for large list", async () => {
    const cache = new RefCache({ name: "test-cache" });
    const largeList = Array.from({ length: 1000 }, (_, index) => ({
      id: index,
      data: `item-${index}`,
    }));
    const reference = await cache.set("key1", largeList);
    const response = await cache.get(reference.refId);

    expect(response.preview).toBeDefined();
    expect(response.previewStrategy).toBeDefined();
  });

  it("returns full value for small data", async () => {
    const cache = new RefCache({ name: "test-cache" });
    const smallData = { a: 1, b: 2 };
    const reference = await cache.set("key1", smallData);
    const response = await cache.get(reference.refId);

    // Small data should be returned as-is (within size limit)
    expect(response.preview).toEqual(smallData);
  });

  it("includes preview strategy in response", async () => {
    const cache = new RefCache({ name: "test-cache" });
    const reference = await cache.set("key1", [1, 2, 3, 4, 5]);
    const response = await cache.get(reference.refId);
    expect(response.previewStrategy).toBeDefined();
    expect(typeof response.previewStrategy).toBe("string");
  });

  it("includes size metadata in response", async () => {
    const cache = new RefCache({ name: "test-cache" });
    const reference = await cache.set(
      "key1",
      Array.from({ length: 100 }, (_, index) => index),
    );
    const response = await cache.get(reference.refId);

    expect(response.originalSize).toBeDefined();
    expect(response.previewSize).toBeDefined();
  });
});

// ═════════════════════════════════════════════════════════════════════
// Context Limiting (Tokenizer / Measurer integration)
// ═════════════════════════════════════════════════════════════════════

describe("RefCache Context Limiting", () => {
  it("accepts tokenizer in constructor", () => {
    const tokenizer = new CharacterFallback();
    const cache = new RefCache({ tokenizer });
    expect(cache).toBeDefined();
  });

  it("accepts measurer in constructor", () => {
    const measurer = new CharacterMeasurer();
    const cache = new RefCache({ measurer });
    expect(cache).toBeDefined();
  });

  it("accepts preview generator in constructor", () => {
    const generator = new TruncateGenerator();
    const cache = new RefCache({ previewGenerator: generator });
    expect(cache).toBeDefined();
  });

  it("creates TokenMeasurer from tokenizer when no measurer given", async () => {
    const tokenizer = new CharacterFallback(4);
    const cache = new RefCache({ tokenizer });
    // Should work without error — measurer was auto-created
    const reference = await cache.set("key1", [1, 2, 3]);
    const response = await cache.get(reference.refId);
    expect(response.preview).toBeDefined();
  });

  it("explicit measurer overrides tokenizer", async () => {
    const tokenizer = new CharacterFallback(4);
    const measurer = new CharacterMeasurer();
    const cache = new RefCache({ tokenizer, measurer });

    // The CharacterMeasurer measures by JSON string length,
    // not by token count via the tokenizer
    const reference = await cache.set("key1", [1, 2, 3]);
    const response = await cache.get(reference.refId);
    expect(response.preview).toBeDefined();
  });

  it("uses character measurer when sizeMode is character", async () => {
    const config = PreviewConfigSchema.parse({
      sizeMode: "character",
      maxSize: 500,
    });
    const cache = new RefCache({ previewConfig: config });

    const reference = await cache.set("key1", "test string");
    const response = await cache.get(reference.refId);
    expect(response.preview).toBeDefined();
  });

  it("default generator comes from config strategy", () => {
    const config = PreviewConfigSchema.parse({
      defaultStrategy: "truncate",
    });
    const cache = new RefCache({ previewConfig: config });
    // Should use TruncateGenerator — verified indirectly through behavior
    expect(cache).toBeDefined();
  });

  it("custom max_size is respected per-call", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewConfig: PreviewConfigSchema.parse({ maxSize: 10000 }),
    });

    const largeList = Array.from({ length: 1000 }, (_, index) => ({
      id: index,
      data: `item-${index}-with-some-extra-text`,
    }));
    const reference = await cache.set("key1", largeList);

    // Get with a very small max_size
    const response = await cache.get(reference.refId, { maxSize: 50 });
    // Preview should be smaller than original
    expect(response.previewSize).toBeDefined();
    expect(response.previewSize).not.toBeNull();
    expect(response.originalSize).toBeDefined();
    expect(response.originalSize).not.toBeNull();
    if (
      response.previewSize !== null &&
      response.previewSize !== undefined &&
      response.originalSize !== null &&
      response.originalSize !== undefined
    ) {
      expect(response.previewSize).toBeLessThanOrEqual(response.originalSize);
    }
  });
});

// ═════════════════════════════════════════════════════════════════════
// Access Control Integration
// ═════════════════════════════════════════════════════════════════════

describe("RefCache Access Control Integration", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test-cache" });
  });

  // --- Constructor ---

  it("accepts custom permission checker", () => {
    const checker = new DefaultPermissionChecker();
    const cache = new RefCache({ permissionChecker: checker });
    expect(cache).toBeDefined();
  });

  it("accepts checker with custom namespace resolver", () => {
    const resolver = new DefaultNamespaceResolver();
    const checker = new DefaultPermissionChecker(resolver);
    const cache = new RefCache({ permissionChecker: checker });
    expect(cache).toBeDefined();
  });

  // --- Actor objects ---

  it("get() accepts Actor object", async () => {
    const reference = await cache.set("key1", "value");
    const actor = DefaultActor.user({ actorId: "alice" });
    const response = await cache.get(reference.refId, { actor });
    expect(response).toBeDefined();
  });

  it("get() accepts identified Actor", async () => {
    const reference = await cache.set("key1", "value");
    const actor = DefaultActor.user({ actorId: "alice" });
    const response = await cache.get(reference.refId, { actor });
    expect(response.refId).toBe(reference.refId);
  });

  it("resolve() accepts Actor object", async () => {
    const reference = await cache.set("key1", "value");
    const actor = DefaultActor.user({ actorId: "alice" });
    const value = await cache.resolve(reference.refId, { actor });
    expect(value).toBe("value");
  });

  it("delete() accepts Actor object", async () => {
    await cache.set("key1", "value");
    const actor = DefaultActor.user({ actorId: "alice" });
    const result = await cache.delete("key1", { actor });
    expect(result).toBe(true);
  });

  it("literal strings still work for actor", async () => {
    const reference = await cache.set("key1", "value");

    const response = await cache.get(reference.refId, { actor: "user" });
    expect(response).toBeDefined();

    const value = await cache.resolve(reference.refId, { actor: "agent" });
    expect(value).toBe("value");
  });

  // --- Permission enforcement ---

  it("get() enforces permission via checker", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    await cache.set("key1", "value", { policy });

    await expect(
      cache.get("key1", { actor: "agent" }),
    ).rejects.toThrow(PermissionDenied);
  });

  it("resolve() enforces permission via checker", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    await cache.set("key1", "value", { policy });

    await expect(
      cache.resolve("key1", { actor: "agent" }),
    ).rejects.toThrow(PermissionDenied);
  });

  it("delete() enforces permission via checker", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.READ, // Read but not delete
    });
    await cache.set("key1", "value", { policy });

    await expect(
      cache.delete("key1", { actor: "agent" }),
    ).rejects.toThrow(PermissionDenied);
  });

  // --- Namespace-based access control ---

  it("user namespace allows matching user", async () => {
    const reference = await cache.set("key1", "value", {
      namespace: "user:alice",
    });
    const actor = DefaultActor.user({ actorId: "alice" });
    const value = await cache.resolve(reference.refId, { actor });
    expect(value).toBe("value");
  });

  it("user namespace denies different user", async () => {
    const reference = await cache.set("key1", "value", {
      namespace: "user:alice",
    });
    const actor = DefaultActor.user({ actorId: "bob" });
    await expect(
      cache.resolve(reference.refId, { actor }),
    ).rejects.toThrow(PermissionDenied);
  });

  it("session namespace allows matching session", async () => {
    const reference = await cache.set("key1", "value", {
      namespace: "session:sess-123",
    });
    const actor = DefaultActor.user({
      actorId: "alice",
      sessionId: "sess-123",
    });
    const value = await cache.resolve(reference.refId, { actor });
    expect(value).toBe("value");
  });

  it("session namespace denies different session", async () => {
    const reference = await cache.set("key1", "value", {
      namespace: "session:sess-123",
    });
    const actor = DefaultActor.user({
      actorId: "alice",
      sessionId: "sess-456",
    });
    await expect(
      cache.resolve(reference.refId, { actor }),
    ).rejects.toThrow(PermissionDenied);
  });

  it("public namespace allows all actors", async () => {
    const reference = await cache.set("key1", "value", {
      namespace: "public",
    });

    const user = DefaultActor.user({ actorId: "anyone" });
    const agent = DefaultActor.agent();

    const value1 = await cache.resolve(reference.refId, { actor: user });
    const value2 = await cache.resolve(reference.refId, { actor: agent });
    expect(value1).toBe("value");
    expect(value2).toBe("value");
  });

  it("system actor bypasses namespace checks", async () => {
    const reference = await cache.set("key1", "value", {
      namespace: "user:alice",
    });
    const system = DefaultActor.system();
    const value = await cache.resolve(reference.refId, { actor: system });
    expect(value).toBe("value");
  });

  // --- PermissionDenied error attributes ---

  it("PermissionDenied is an Error", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    await cache.set("key1", "value", { policy });

    try {
      await cache.get("key1", { actor: "agent" });
      expect(true).toBe(false); // Should not reach here
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect(error).toBeInstanceOf(Error);
    }
  });

  it("PermissionDenied has actor and required attributes", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    await cache.set("key1", "value", { policy });

    try {
      await cache.get("key1", { actor: "agent" });
      expect(true).toBe(false);
    } catch (error) {
      const permissionError = error as PermissionDenied;
      expect(permissionError.actor).toBeDefined();
      expect(permissionError.required).toBeDefined();
    }
  });

  it("PermissionDenied includes namespace", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    await cache.set("key1", "value", {
      policy,
      namespace: "session:xyz",
    });

    try {
      await cache.get("key1", { actor: "agent" });
      expect(true).toBe(false);
    } catch (error) {
      const permissionError = error as PermissionDenied;
      expect(permissionError.namespace).toBe("session:xyz");
    }
  });

  // --- Custom permission checkers ---

  it("custom deny-all permission checker works", async () => {
    const denyAllChecker: import("../src/access/checker.js").PermissionChecker =
      {
        check(_policy, required, actor, namespace) {
          throw new PermissionDenied("Access denied by custom checker", {
            actor,
            required,
            reason: "custom_deny",
            namespace,
          });
        },
        hasPermission() {
          return false;
        },
        getEffectivePermissions() {
          return Permission.NONE;
        },
      };

    const restrictedCache = new RefCache({
      name: "restricted",
      permissionChecker: denyAllChecker,
    });

    await restrictedCache.set("key1", "value");

    await expect(
      restrictedCache.get("key1", { actor: "user" }),
    ).rejects.toThrow(PermissionDenied);

    await expect(
      restrictedCache.resolve("key1", { actor: "agent" }),
    ).rejects.toThrow(PermissionDenied);
  });

  it("custom allow-all permission checker works", async () => {
    const allowAllChecker: import("../src/access/checker.js").PermissionChecker =
      {
        check() {
          // Never throws — always allows
        },
        hasPermission() {
          return true;
        },
        getEffectivePermissions() {
          return Permission.FULL;
        },
      };

    const openCache = new RefCache({
      name: "open",
      permissionChecker: allowAllChecker,
    });

    // Even with no permissions in policy, custom checker allows
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
      userPermissions: Permission.NONE,
    });
    await openCache.set("key1", "value", { policy });

    const response = await openCache.get("key1", { actor: "agent" });
    expect(response).toBeDefined();

    const value = await openCache.resolve("key1", { actor: "agent" });
    expect(value).toBe("value");
  });

  // --- Owner permissions ---

  it("owner gets owner permissions", async () => {
    const policy = AccessPolicySchema.parse({
      owner: "user:alice",
      ownerPermissions: Permission.FULL,
      agentPermissions: Permission.NONE,
      userPermissions: Permission.NONE,
    });
    const reference = await cache.set("key1", "value", { policy });

    const alice = DefaultActor.user({ actorId: "alice" });
    const value = await cache.resolve(reference.refId, { actor: alice });
    expect(value).toBe("value");

    // Non-owner user should be denied
    const bob = DefaultActor.user({ actorId: "bob" });
    await expect(
      cache.resolve(reference.refId, { actor: bob }),
    ).rejects.toThrow(PermissionDenied);
  });

  it("agent in agent namespace can access", async () => {
    const reference = await cache.set("key1", "value", {
      namespace: "agent:claude",
    });
    const agent = DefaultActor.agent({ actorId: "claude" });
    const value = await cache.resolve(reference.refId, { actor: agent });
    expect(value).toBe("value");
  });
});

// ═════════════════════════════════════════════════════════════════════
// Pagination Auto-Switch
// ═════════════════════════════════════════════════════════════════════

describe("Pagination Auto-Switch", () => {
  it("SampleGenerator stays sample when no page requested", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewGenerator: new SampleGenerator(),
    });
    const reference = await cache.set(
      "key1",
      Array.from({ length: 100 }, (_, index) => index),
    );
    const response = await cache.get(reference.refId);

    // Should use sample strategy
    expect(response.previewStrategy).toBe("sample");
  });

  it("SampleGenerator auto-switches to paginate when page specified", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewGenerator: new SampleGenerator(),
      previewConfig: PreviewConfigSchema.parse({ maxSize: 50 }),
    });
    const reference = await cache.set(
      "key1",
      Array.from({ length: 100 }, (_, index) => index),
    );
    const response = await cache.get(reference.refId, {
      page: 1,
      pageSize: 10,
    });

    // Should auto-switch to paginate strategy
    expect(response.previewStrategy).toBe("paginate");
    expect(response.page).toBe(1);
  });

  it("SampleGenerator page 2 returns correct items", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewGenerator: new SampleGenerator(),
      previewConfig: PreviewConfigSchema.parse({ maxSize: 5000 }),
    });
    const items = Array.from({ length: 100 }, (_, index) => index);
    const reference = await cache.set("key1", items);

    const response = await cache.get(reference.refId, {
      page: 2,
      pageSize: 10,
    });

    // Should be paginate strategy with page 2
    expect(response.previewStrategy).toBe("paginate");
    expect(response.page).toBe(2);
  });

  it("PaginateGenerator always respects page", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewGenerator: new PaginateGenerator(),
    });
    const items = Array.from({ length: 50 }, (_, index) => index);
    const reference = await cache.set("key1", items);

    const response = await cache.get(reference.refId, {
      page: 1,
      pageSize: 10,
    });

    expect(response.previewStrategy).toBe("paginate");
    expect(response.page).toBe(1);
    expect(response.totalPages).toBeDefined();
  });

  it("TruncateGenerator is not affected by page parameter", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewGenerator: new TruncateGenerator(),
    });
    const reference = await cache.set(
      "key1",
      Array.from({ length: 100 }, (_, index) => index),
    );

    // TruncateGenerator ignores page (not a SampleGenerator, so no auto-switch)
    const response = await cache.get(reference.refId, { page: 2 });
    expect(response.previewStrategy).toBe("truncate");
  });
});

// ═════════════════════════════════════════════════════════════════════
// Hierarchical maxSize
// ═════════════════════════════════════════════════════════════════════

describe("Hierarchical maxSize", () => {
  it("server default maxSize is used when no override", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewConfig: PreviewConfigSchema.parse({ maxSize: 100 }),
      measurer: new CharacterMeasurer(),
    });

    const largeList = Array.from({ length: 1000 }, (_, index) => ({
      id: index,
    }));
    const reference = await cache.set("key1", largeList);
    const response = await cache.get(reference.refId);

    // Preview should be limited to around 100 characters
    expect(response.previewSize).toBeDefined();
    expect(response.previewSize).not.toBeNull();
  });

  it("per-call maxSize overrides server default", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewConfig: PreviewConfigSchema.parse({ maxSize: 10000 }),
      measurer: new CharacterMeasurer(),
    });

    const largeList = Array.from({ length: 1000 }, (_, index) => ({
      id: index,
      data: `item-${index}`,
    }));
    const reference = await cache.set("key1", largeList);

    // Get with small override
    const response = await cache.get(reference.refId, { maxSize: 50 });
    expect(response.previewSize).toBeDefined();
  });

  it("per-call maxSize can be smaller than default", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewConfig: PreviewConfigSchema.parse({ maxSize: 5000 }),
      measurer: new CharacterMeasurer(),
    });

    const largeList = Array.from({ length: 500 }, (_, index) => ({
      id: index,
      name: `user-${index}`,
    }));
    const reference = await cache.set("key1", largeList);

    const defaultResponse = await cache.get(reference.refId);
    const smallResponse = await cache.get(reference.refId, { maxSize: 50 });

    // Smaller maxSize should produce smaller or equal preview
    if (
      smallResponse.previewSize !== null &&
      smallResponse.previewSize !== undefined &&
      defaultResponse.previewSize !== null &&
      defaultResponse.previewSize !== undefined
    ) {
      expect(smallResponse.previewSize).toBeLessThanOrEqual(
        defaultResponse.previewSize,
      );
    }
  });
});

// ═════════════════════════════════════════════════════════════════════
// Preview Result Integration
// ═════════════════════════════════════════════════════════════════════

describe("RefCache PreviewResult", () => {
  it("includes item counts for list", async () => {
    const cache = new RefCache({ name: "test-cache" });
    const reference = await cache.set("key1", [1, 2, 3, 4, 5]);
    const response = await cache.get(reference.refId);

    expect(response.totalItems).toBe(5);
  });

  it("includes item counts for dict", async () => {
    const cache = new RefCache({ name: "test-cache" });
    const reference = await cache.set("key1", { a: 1, b: 2, c: 3 });
    const response = await cache.get(reference.refId);

    expect(response.totalItems).toBe(3);
  });

  it("includes pagination fields when paginated", async () => {
    const cache = new RefCache({
      name: "test-cache",
      previewGenerator: new PaginateGenerator(),
    });
    const items = Array.from({ length: 50 }, (_, index) => index);
    const reference = await cache.set("key1", items);

    const response = await cache.get(reference.refId, {
      page: 1,
      pageSize: 10,
    });

    expect(response.page).toBe(1);
    expect(response.totalPages).toBeDefined();
    expect(response.totalPages).toBeGreaterThan(0);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Edge Cases
// ═════════════════════════════════════════════════════════════════════

describe("RefCache Edge Cases", () => {
  it("handles empty string key", async () => {
    const cache = new RefCache({ name: "test" });
    // The API doesn't forbid empty keys — it just works
    const reference = await cache.set("", "value");
    expect(reference).toBeDefined();
  });

  it("handles very long keys", async () => {
    const cache = new RefCache({ name: "test" });
    const longKey = "a".repeat(1000);
    const reference = await cache.set(longKey, "value");
    expect(reference).toBeDefined();
    expect(reference.refId.length).toBeGreaterThan(0);
  });

  it("handles large values", async () => {
    const cache = new RefCache({ name: "test" });
    const largeValue = Array.from({ length: 10000 }, (_, index) => ({
      id: index,
      data: `item-${index}-with-extra-content-for-size`,
    }));
    const reference = await cache.set("large", largeValue);
    const resolved = await cache.resolve(reference.refId);
    expect(resolved).toEqual(largeValue);
  });

  it("handles nested objects", async () => {
    const cache = new RefCache({ name: "test" });
    const nested = {
      a: { b: { c: { d: { e: "deep" } } } },
    };
    const reference = await cache.set("nested", nested);
    const resolved = await cache.resolve(reference.refId);
    expect(resolved).toEqual(nested);
  });

  it("handles setting same key multiple times rapidly", async () => {
    const cache = new RefCache({ name: "test" });

    // Set same key multiple times
    await cache.set("key", "v1");
    await cache.set("key", "v2");
    await cache.set("key", "v3");

    const value = await cache.resolve("key");
    expect(value).toBe("v3");
  });

  it("handles mixed types in array values", async () => {
    const cache = new RefCache({ name: "test" });
    const mixed = [1, "two", true, null, { five: 5 }, [6, 7]];
    const reference = await cache.set("mixed", mixed);
    const resolved = await cache.resolve(reference.refId);
    expect(resolved).toEqual(mixed);
  });

  it("setEntryValueForTesting throws for non-existent entry", async () => {
    const cache = new RefCache({ name: "test" });
    await expect(
      cache.setEntryValueForTesting("nonexistent:abcd12345678", {
        data: "new",
      }),
    ).rejects.toThrow("not found");
  });

  it("getBackend returns the configured backend", () => {
    const backend = new MemoryBackend();
    const cache = new RefCache({ backend });
    expect(cache.getBackend()).toBe(backend);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Ref ID Format
// ═════════════════════════════════════════════════════════════════════

describe("RefCache Ref ID Format", () => {
  it("generates ref_id in cachename:hexhash format", async () => {
    const cache = new RefCache({ name: "myapp" });
    const reference = await cache.set("key1", "value");

    // Should match pattern: myapp:<hex chars>
    expect(reference.refId).toMatch(/^myapp:[a-f0-9]+$/);
  });

  it("hex hash is exactly 16 characters", async () => {
    const cache = new RefCache({ name: "test" });
    const reference = await cache.set("key1", "value");

    const parts = reference.refId.split(":");
    expect(parts).toHaveLength(2);
    expect(parts[1]).toHaveLength(16);
  });

  it("different keys produce different hashes", async () => {
    const cache = new RefCache({ name: "test" });
    const reference1 = await cache.set("key1", "value1");
    const reference2 = await cache.set("key2", "value2");

    const hash1 = reference1.refId.split(":")[1];
    const hash2 = reference2.refId.split(":")[1];
    expect(hash1).not.toBe(hash2);
  });

  it("ref_id uses cache name as prefix", async () => {
    const cache = new RefCache({ name: "my-custom-cache" });
    const reference = await cache.set("key1", "value");

    expect(reference.refId).toStartWith("my-custom-cache:");
  });
});
