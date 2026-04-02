/**
 * Tests for cache backends.
 *
 * Tests the CacheBackend interface compliance, MemoryBackend CRUD operations,
 * TTL expiration handling, namespace-scoped clear/keys, and preservation of
 * complex values, policies, and metadata.
 *
 * Maps to Python: `tests/test_backends.py`
 * Skips: SQLite, Redis, and thread-safety tests (not applicable for Task-03).
 */

import { beforeEach, describe, expect, it } from "bun:test";

import {
  type CacheBackend,
  type CacheEntry,
  CacheEntrySchema,
  isExpired,
  MemoryBackend,
  Permission,
} from "../src/index.js";

// ═════════════════════════════════════════════════════════════════════
// Helpers
// ═════════════════════════════════════════════════════════════════════

/**
 * Create a sample CacheEntry for testing.
 *
 * Uses `CacheEntrySchema.parse()` to validate and apply defaults,
 * matching how entries flow through the real system.
 */
function createSampleEntry(overrides: Partial<CacheEntry> = {}): CacheEntry {
  return CacheEntrySchema.parse({
    value: { id: 1, name: "Test" },
    namespace: "public",
    policy: {},
    createdAt: Date.now() / 1000,
    ...overrides,
  });
}

// ═════════════════════════════════════════════════════════════════════
// CacheEntry & isExpired (model-level, mirrors Python TestCacheEntry)
// ═════════════════════════════════════════════════════════════════════

describe("CacheEntry (backend context)", () => {
  it("creates entry with required fields and correct defaults", () => {
    const entry = CacheEntrySchema.parse({
      value: { key: "value" },
      namespace: "public",
      policy: {},
      createdAt: 1234567890.0,
    });

    expect(entry.value).toEqual({ key: "value" });
    expect(entry.namespace).toBe("public");
    expect(entry.createdAt).toBe(1234567890.0);
    expect(entry.expiresAt).toBeNull();
    expect(entry.metadata).toEqual({});
  });

  it("creates entry with expiration time", () => {
    const entry = CacheEntrySchema.parse({
      value: "test",
      namespace: "session:abc",
      policy: {},
      createdAt: 1000.0,
      expiresAt: 2000.0,
    });

    expect(entry.expiresAt).toBe(2000.0);
  });

  it("creates entry with custom metadata", () => {
    const entry = CacheEntrySchema.parse({
      value: [1, 2, 3],
      namespace: "public",
      policy: {},
      createdAt: 1000.0,
      metadata: { toolName: "my_tool", totalItems: 100 },
    });

    expect(entry.metadata["toolName"]).toBe("my_tool");
    expect(entry.metadata["totalItems"]).toBe(100);
  });

  it("isExpired returns false when expiresAt is null", () => {
    const entry = createSampleEntry({ expiresAt: null });
    expect(isExpired(entry, 9999999.0)).toBe(false);
  });

  it("isExpired returns false before expiration time", () => {
    const entry = createSampleEntry({ createdAt: 1000.0, expiresAt: 2000.0 });
    expect(isExpired(entry, 1500.0)).toBe(false);
  });

  it("isExpired returns true at exact expiration time", () => {
    const entry = createSampleEntry({ createdAt: 1000.0, expiresAt: 2000.0 });
    expect(isExpired(entry, 2000.0)).toBe(true);
  });

  it("isExpired returns true after expiration time", () => {
    const entry = createSampleEntry({ createdAt: 1000.0, expiresAt: 2000.0 });
    expect(isExpired(entry, 2500.0)).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Protocol Compliance
// ═════════════════════════════════════════════════════════════════════

describe("Backend Protocol Compliance", () => {
  it("MemoryBackend satisfies CacheBackend interface", () => {
    // Structural typing: assigning to the interface type must compile.
    const backend: CacheBackend = new MemoryBackend();
    expect(backend).toBeDefined();
  });

  it("MemoryBackend has all required methods", () => {
    const backend = new MemoryBackend();
    expect(typeof backend.get).toBe("function");
    expect(typeof backend.set).toBe("function");
    expect(typeof backend.delete).toBe("function");
    expect(typeof backend.exists).toBe("function");
    expect(typeof backend.clear).toBe("function");
    expect(typeof backend.keys).toBe("function");
  });

  it("all methods return promises", async () => {
    const backend = new MemoryBackend();
    const entry = createSampleEntry();

    expect(backend.get("key")).toBeInstanceOf(Promise);
    expect(backend.set("key", entry)).toBeInstanceOf(Promise);
    expect(backend.delete("key")).toBeInstanceOf(Promise);
    expect(backend.exists("key")).toBeInstanceOf(Promise);
    expect(backend.clear()).toBeInstanceOf(Promise);
    expect(backend.keys()).toBeInstanceOf(Promise);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Basic Operations
// ═════════════════════════════════════════════════════════════════════

describe("Backend Basic Operations", () => {
  let backend: MemoryBackend;

  beforeEach(() => {
    backend = new MemoryBackend();
  });

  it("set and get round-trips an entry", async () => {
    const entry = createSampleEntry();
    await backend.set("test_key", entry);
    const result = await backend.get("test_key");

    expect(result).not.toBeNull();
    expect(result!.value).toEqual(entry.value);
    expect(result!.namespace).toBe(entry.namespace);
  });

  it("get returns null for nonexistent key", async () => {
    expect(await backend.get("nonexistent_key")).toBeNull();
  });

  it("set overwrites existing key", async () => {
    const original = createSampleEntry();
    await backend.set("test_key", original);

    const replacement = createSampleEntry({
      value: { new: "value" },
      namespace: "private",
    });
    await backend.set("test_key", replacement);

    const result = await backend.get("test_key");
    expect(result).not.toBeNull();
    expect(result!.value).toEqual({ new: "value" });
    expect(result!.namespace).toBe("private");
  });

  it("delete removes an existing key", async () => {
    const entry = createSampleEntry();
    await backend.set("test_key", entry);
    expect(await backend.exists("test_key")).toBe(true);

    const deleted = await backend.delete("test_key");
    expect(deleted).toBe(true);
    expect(await backend.get("test_key")).toBeNull();
  });

  it("delete returns false for nonexistent key", async () => {
    const deleted = await backend.delete("nonexistent_key");
    expect(deleted).toBe(false);
  });

  it("exists returns true for existing key", async () => {
    const entry = createSampleEntry();
    await backend.set("test_key", entry);
    expect(await backend.exists("test_key")).toBe(true);
  });

  it("exists returns false for nonexistent key", async () => {
    expect(await backend.exists("nonexistent_key")).toBe(false);
  });

  it("stores complex nested data structures", async () => {
    const complexValue = {
      nested: { deep: { value: [1, 2, 3] } },
      list: [{ a: 1 }, { b: 2 }],
      number: 42.5,
      boolean: true,
      null: null,
    };

    const entry = createSampleEntry({ value: complexValue });
    await backend.set("complex_key", entry);
    const result = await backend.get("complex_key");

    expect(result).not.toBeNull();
    expect(result!.value).toEqual(complexValue);
  });

  it("stores list values directly", async () => {
    const listValue = [1, 2, 3, "four", { five: 5 }];

    const entry = createSampleEntry({ value: listValue });
    await backend.set("list_key", entry);
    const result = await backend.get("list_key");

    expect(result).not.toBeNull();
    expect(result!.value).toEqual(listValue);
  });

  it("preserves AccessPolicy through storage", async () => {
    const entry = createSampleEntry({
      value: "test",
      namespace: "user:alice",
      policy: {
        owner: "user:alice",
        userPermissions: Permission.READ,
        agentPermissions: Permission.EXECUTE,
      },
    });

    await backend.set("policy_key", entry);
    const result = await backend.get("policy_key");

    expect(result).not.toBeNull();
    expect(result!.policy.owner).toBe("user:alice");
    expect(result!.policy.userPermissions).toBe(Permission.READ);
    expect(result!.policy.agentPermissions).toBe(Permission.EXECUTE);
  });

  it("preserves metadata through storage", async () => {
    const metadata = {
      toolName: "test_tool",
      totalItems: 100,
      previewSize: 50,
    };

    const entry = createSampleEntry({
      value: "test",
      metadata,
    });

    await backend.set("metadata_key", entry);
    const result = await backend.get("metadata_key");

    expect(result).not.toBeNull();
    expect(result!.metadata).toEqual(metadata);
  });

  it("stores string values", async () => {
    const entry = createSampleEntry({ value: "just a string" });
    await backend.set("string_key", entry);
    const result = await backend.get("string_key");

    expect(result).not.toBeNull();
    expect(result!.value).toBe("just a string");
  });

  it("stores numeric values", async () => {
    const entry = createSampleEntry({ value: 42 });
    await backend.set("number_key", entry);
    const result = await backend.get("number_key");

    expect(result).not.toBeNull();
    expect(result!.value).toBe(42);
  });

  it("stores null values", async () => {
    const entry = createSampleEntry({ value: null });
    await backend.set("null_key", entry);
    const result = await backend.get("null_key");

    expect(result).not.toBeNull();
    expect(result!.value).toBeNull();
  });

  it("stores boolean values", async () => {
    const entry = createSampleEntry({ value: true });
    await backend.set("bool_key", entry);
    const result = await backend.get("bool_key");

    expect(result).not.toBeNull();
    expect(result!.value).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Expiration
// ═════════════════════════════════════════════════════════════════════

describe("Backend Expiration", () => {
  let backend: MemoryBackend;

  beforeEach(() => {
    backend = new MemoryBackend();
  });

  it("get returns null for expired entry", async () => {
    const expiredEntry = createSampleEntry({
      value: "expired",
      createdAt: Date.now() / 1000 - 100,
      expiresAt: Date.now() / 1000 - 1, // Already expired
    });
    await backend.set("expired_key", expiredEntry);

    const result = await backend.get("expired_key");
    expect(result).toBeNull();
  });

  it("accessing expired entry cleans it up", async () => {
    const expiredEntry = createSampleEntry({
      value: "expired",
      createdAt: Date.now() / 1000 - 100,
      expiresAt: Date.now() / 1000 - 1,
    });
    await backend.set("expired_key", expiredEntry);

    // Access the expired entry — triggers lazy eviction
    await backend.get("expired_key");

    // It should be cleaned up now
    expect(await backend.exists("expired_key")).toBe(false);
  });

  it("exists returns false for expired entry", async () => {
    const expiredEntry = createSampleEntry({
      value: "expired",
      createdAt: Date.now() / 1000 - 100,
      expiresAt: Date.now() / 1000 - 1,
    });
    await backend.set("expired_key", expiredEntry);

    expect(await backend.exists("expired_key")).toBe(false);
  });

  it("exists cleans up expired entry on check", async () => {
    const expiredEntry = createSampleEntry({
      value: "expired",
      createdAt: Date.now() / 1000 - 100,
      expiresAt: Date.now() / 1000 - 1,
    });
    await backend.set("expired_key", expiredEntry);

    // exists triggers lazy eviction too
    await backend.exists("expired_key");

    // Verify it was actually removed from storage
    expect(await backend.keys()).not.toContain("expired_key");
  });

  it("non-expired entry is accessible", async () => {
    const futureEntry = createSampleEntry({
      value: "future",
      createdAt: Date.now() / 1000,
      expiresAt: Date.now() / 1000 + 3600, // Expires in 1 hour
    });
    await backend.set("future_key", futureEntry);

    const result = await backend.get("future_key");
    expect(result).not.toBeNull();
    expect(result!.value).toBe("future");
  });

  it("entry without expiration never expires", async () => {
    const entry = createSampleEntry({
      value: "forever",
      expiresAt: null,
    });
    await backend.set("forever_key", entry);

    const result = await backend.get("forever_key");
    expect(result).not.toBeNull();
    expect(result!.value).toBe("forever");
  });

  it("entry at exact expiration boundary is treated as expired", async () => {
    const now = Date.now() / 1000;
    const entry = createSampleEntry({
      value: "boundary",
      createdAt: now - 10,
      expiresAt: now, // Expires exactly now
    });
    await backend.set("boundary_key", entry);

    // isExpired uses currentTime >= expiresAt, so exact match = expired
    const result = await backend.get("boundary_key");
    expect(result).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════
// Clear
// ═════════════════════════════════════════════════════════════════════

describe("Backend Clear", () => {
  let backend: MemoryBackend;

  beforeEach(() => {
    backend = new MemoryBackend();
  });

  it("clear() removes all entries and returns count", async () => {
    for (let index = 0; index < 5; index++) {
      const entry = createSampleEntry({
        value: `value_${index}`,
        namespace: `ns_${index}`,
      });
      await backend.set(`key_${index}`, entry);
    }

    const cleared = await backend.clear();
    expect(cleared).toBe(5);
    expect(await backend.keys()).toEqual([]);
  });

  it("clear(namespace) removes only entries in that namespace", async () => {
    // Create entries in namespace_1
    for (let index = 0; index < 3; index++) {
      const entry = createSampleEntry({
        value: `ns1_${index}`,
        namespace: "namespace_1",
      });
      await backend.set(`ns1_key_${index}`, entry);
    }

    // Create entries in namespace_2
    for (let index = 0; index < 2; index++) {
      const entry = createSampleEntry({
        value: `ns2_${index}`,
        namespace: "namespace_2",
      });
      await backend.set(`ns2_key_${index}`, entry);
    }

    // Clear only namespace_1
    const cleared = await backend.clear("namespace_1");
    expect(cleared).toBe(3);

    // namespace_2 entries should still exist
    const remainingKeys = await backend.keys();
    expect(remainingKeys).toHaveLength(2);
    expect(remainingKeys.every((key) => key.includes("ns2"))).toBe(true);
  });

  it("clear() on empty cache returns 0", async () => {
    const cleared = await backend.clear();
    expect(cleared).toBe(0);
  });

  it("clear(namespace) on nonexistent namespace returns 0", async () => {
    const entry = createSampleEntry({ namespace: "existing" });
    await backend.set("key1", entry);

    const cleared = await backend.clear("nonexistent");
    expect(cleared).toBe(0);

    // Original entry should remain
    expect(await backend.exists("key1")).toBe(true);
  });

  it("clear(namespace) does not match namespace prefixes", async () => {
    // "ns" should NOT match "ns_extended"
    const entry1 = createSampleEntry({ namespace: "ns" });
    const entry2 = createSampleEntry({ namespace: "ns_extended" });

    await backend.set("key1", entry1);
    await backend.set("key2", entry2);

    const cleared = await backend.clear("ns");
    expect(cleared).toBe(1);
    expect(await backend.exists("key2")).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Keys
// ═════════════════════════════════════════════════════════════════════

describe("Backend Keys", () => {
  let backend: MemoryBackend;

  beforeEach(() => {
    backend = new MemoryBackend();
  });

  it("keys() returns empty array for empty cache", async () => {
    expect(await backend.keys()).toEqual([]);
  });

  it("keys() returns all stored keys", async () => {
    for (let index = 0; index < 5; index++) {
      const entry = createSampleEntry({ value: `value_${index}` });
      await backend.set(`key_${index}`, entry);
    }

    const keys = await backend.keys();
    expect(keys).toHaveLength(5);

    const expectedKeys = new Set(
      Array.from({ length: 5 }, (_, index) => `key_${index}`),
    );
    expect(new Set(keys)).toEqual(expectedKeys);
  });

  it("keys(namespace) filters by namespace", async () => {
    // Create entries in namespace_1
    for (let index = 0; index < 3; index++) {
      const entry = createSampleEntry({
        value: `ns1_${index}`,
        namespace: "namespace_1",
      });
      await backend.set(`ns1_key_${index}`, entry);
    }

    // Create entries in namespace_2
    for (let index = 0; index < 2; index++) {
      const entry = createSampleEntry({
        value: `ns2_${index}`,
        namespace: "namespace_2",
      });
      await backend.set(`ns2_key_${index}`, entry);
    }

    const namespace1Keys = await backend.keys("namespace_1");
    expect(namespace1Keys).toHaveLength(3);
    expect(namespace1Keys.every((key) => key.includes("ns1"))).toBe(true);

    const namespace2Keys = await backend.keys("namespace_2");
    expect(namespace2Keys).toHaveLength(2);
    expect(namespace2Keys.every((key) => key.includes("ns2"))).toBe(true);
  });

  it("keys() excludes expired entries", async () => {
    // Valid entry
    const validEntry = createSampleEntry({
      value: "valid",
      createdAt: Date.now() / 1000,
      expiresAt: Date.now() / 1000 + 3600,
    });
    await backend.set("valid_key", validEntry);

    // Expired entry
    const expiredEntry = createSampleEntry({
      value: "expired",
      createdAt: Date.now() / 1000 - 100,
      expiresAt: Date.now() / 1000 - 1,
    });
    await backend.set("expired_key", expiredEntry);

    const keys = await backend.keys();
    expect(keys).toContain("valid_key");
    expect(keys).not.toContain("expired_key");
  });

  it("keys() cleans up expired entries during iteration", async () => {
    // Create a valid entry and an expired entry
    const validEntry = createSampleEntry({
      value: "valid",
      expiresAt: Date.now() / 1000 + 3600,
    });
    await backend.set("valid_key", validEntry);

    const expiredEntry = createSampleEntry({
      value: "expired",
      createdAt: Date.now() / 1000 - 100,
      expiresAt: Date.now() / 1000 - 1,
    });
    await backend.set("expired_key", expiredEntry);

    // Call keys() — should clean up expired during iteration
    await backend.keys();

    // The expired entry should now be gone from storage entirely
    // (not just filtered from results — actually deleted)
    // Verify by checking that a subsequent keys() call still excludes it
    const keysAfter = await backend.keys();
    expect(keysAfter).toEqual(["valid_key"]);
  });

  it("keys(namespace) with nonexistent namespace returns empty array", async () => {
    const entry = createSampleEntry({ namespace: "existing" });
    await backend.set("key1", entry);

    expect(await backend.keys("nonexistent")).toEqual([]);
  });

  it("keys(namespace) does not match namespace prefixes", async () => {
    const entry1 = createSampleEntry({ namespace: "ns" });
    const entry2 = createSampleEntry({ namespace: "ns_extended" });

    await backend.set("key1", entry1);
    await backend.set("key2", entry2);

    const nsKeys = await backend.keys("ns");
    expect(nsKeys).toEqual(["key1"]);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Multiple Backends (interface contract tests)
// ═════════════════════════════════════════════════════════════════════

describe("CacheBackend interface contract", () => {
  /**
   * Run a suite of contract tests against any CacheBackend implementation.
   * This pattern mirrors Python's parametrized backend fixture.
   *
   * When SQLite/Redis backends are added, they can be plugged in here.
   */
  function runContractTests(
    backendName: string,
    createBackend: () => CacheBackend,
  ): void {
    describe(`${backendName}`, () => {
      let backend: CacheBackend;

      beforeEach(() => {
        backend = createBackend();
      });

      it("round-trips a value", async () => {
        const entry = createSampleEntry({ value: "hello" });
        await backend.set("key", entry);
        const result = await backend.get("key");
        expect(result).not.toBeNull();
        expect(result!.value).toBe("hello");
      });

      it("returns null for missing key", async () => {
        expect(await backend.get("missing")).toBeNull();
      });

      it("delete returns true for existing, false for missing", async () => {
        const entry = createSampleEntry();
        await backend.set("key", entry);
        expect(await backend.delete("key")).toBe(true);
        expect(await backend.delete("key")).toBe(false);
      });

      it("exists tracks presence correctly", async () => {
        expect(await backend.exists("key")).toBe(false);

        const entry = createSampleEntry();
        await backend.set("key", entry);
        expect(await backend.exists("key")).toBe(true);

        await backend.delete("key");
        expect(await backend.exists("key")).toBe(false);
      });

      it("clear returns count and empties cache", async () => {
        await backend.set("a", createSampleEntry());
        await backend.set("b", createSampleEntry());
        await backend.set("c", createSampleEntry());

        expect(await backend.clear()).toBe(3);
        expect(await backend.keys()).toEqual([]);
      });

      it("keys returns all non-expired keys", async () => {
        await backend.set("a", createSampleEntry());
        await backend.set("b", createSampleEntry());

        const keys = await backend.keys();
        expect(keys).toHaveLength(2);
        expect(new Set(keys)).toEqual(new Set(["a", "b"]));
      });

      it("expired entries are invisible", async () => {
        const expired = createSampleEntry({
          createdAt: Date.now() / 1000 - 100,
          expiresAt: Date.now() / 1000 - 1,
        });
        await backend.set("expired", expired);

        expect(await backend.get("expired")).toBeNull();
        expect(await backend.exists("expired")).toBe(false);
        expect(await backend.keys()).not.toContain("expired");
      });
    });
  }

  // Run contract tests for MemoryBackend
  runContractTests("MemoryBackend", () => new MemoryBackend());

  // When additional backends are added, plug them in here:
  // runContractTests("SQLiteBackend", () => new SQLiteBackend(":memory:"));
  // runContractTests("RedisBackend", () => new RedisBackend({ ... }));
});

// ═════════════════════════════════════════════════════════════════════
// Edge Cases
// ═════════════════════════════════════════════════════════════════════

describe("Backend Edge Cases", () => {
  let backend: MemoryBackend;

  beforeEach(() => {
    backend = new MemoryBackend();
  });

  it("handles empty string keys", async () => {
    const entry = createSampleEntry({ value: "empty key" });
    await backend.set("", entry);
    const result = await backend.get("");
    expect(result?.value).toBe("empty key");
    expect(await backend.exists("")).toBe(true);
    expect(await backend.keys()).toContain("");
    expect(await backend.delete("")).toBe(true);
  });

  it("handles keys with special characters", async () => {
    const specialKeys = [
      "key:with:colons",
      "key/with/slashes",
      "key with spaces",
      "key.with.dots",
      "emoji-🔑",
      "unicode-日本語",
    ];

    for (const key of specialKeys) {
      const entry = createSampleEntry({ value: key });
      await backend.set(key, entry);
      const result = await backend.get(key);
      expect(result?.value).toBe(key);
    }

    expect(await backend.keys()).toHaveLength(specialKeys.length);
  });

  it("many entries can be stored and retrieved", async () => {
    const entryCount = 1000;

    for (let index = 0; index < entryCount; index++) {
      const entry = createSampleEntry({ value: index });
      await backend.set(`key_${index}`, entry);
    }

    expect(await backend.keys()).toHaveLength(entryCount);

    // Spot-check some entries
    const first = await backend.get("key_0");
    expect(first?.value).toBe(0);
    const middle = await backend.get("key_500");
    expect(middle?.value).toBe(500);
    const last = await backend.get("key_999");
    expect(last?.value).toBe(999);
  });

  it("set after delete works correctly", async () => {
    const entry1 = createSampleEntry({ value: "first" });
    await backend.set("key", entry1);
    await backend.delete("key");

    const entry2 = createSampleEntry({ value: "second" });
    await backend.set("key", entry2);

    const result = await backend.get("key");
    expect(result?.value).toBe("second");
  });

  it("multiple clears on empty cache are safe", async () => {
    expect(await backend.clear()).toBe(0);
    expect(await backend.clear()).toBe(0);
    expect(await backend.clear("nonexistent")).toBe(0);
  });

  it("keys and clear interact correctly", async () => {
    await backend.set("a", createSampleEntry({ namespace: "ns1" }));
    await backend.set("b", createSampleEntry({ namespace: "ns1" }));
    await backend.set("c", createSampleEntry({ namespace: "ns2" }));

    expect(await backend.keys()).toHaveLength(3);

    await backend.clear("ns1");
    expect(await backend.keys()).toEqual(["c"]);

    await backend.clear();
    expect(await backend.keys()).toEqual([]);
  });

  it("preserves full AccessPolicy with all permissions", async () => {
    const fullPolicy = {
      owner: "system:admin",
      userPermissions: Permission.FULL,
      agentPermissions: Permission.READ | Permission.EXECUTE,
    };

    const entry = createSampleEntry({
      value: "privileged",
      namespace: "admin",
      policy: fullPolicy,
    });

    await backend.set("admin_key", entry);
    const result = await backend.get("admin_key");

    expect(result).not.toBeNull();
    expect(result!.policy.owner).toBe("system:admin");
    expect(result!.policy.userPermissions).toBe(Permission.FULL);
    expect(result!.policy.agentPermissions).toBe(
      Permission.READ | Permission.EXECUTE,
    );
  });

  it("entries in different namespaces with same key are independent", async () => {
    // Same key name, different namespaces stored as different cache keys
    // (In practice the cache system prefixes keys with namespace,
    //  but at the backend level keys are opaque strings)
    const entry1 = createSampleEntry({
      value: "ns1_value",
      namespace: "ns1",
    });
    const entry2 = createSampleEntry({
      value: "ns2_value",
      namespace: "ns2",
    });

    await backend.set("ns1:data", entry1);
    await backend.set("ns2:data", entry2);

    const result1 = await backend.get("ns1:data");
    expect(result1?.value).toBe("ns1_value");
    const result2 = await backend.get("ns2:data");
    expect(result2?.value).toBe("ns2_value");
  });
});
