/**
 * Tests for ref_id resolution utilities.
 *
 * These tests cover:
 * - Ref_id pattern detection (isRefId)
 * - ResolutionResult properties
 * - Deep recursive resolution in nested structures
 * - Error handling for missing/expired references
 * - Circular reference detection
 * - Convenience functions (resolveRefs, resolveKwargs, resolveArgsAndKwargs)
 * - Security (opaque errors for permission denied vs not found)
 *
 * Maps to Python: `tests/test_resolution.py`
 *
 * @module
 */

import { describe, expect, it, beforeEach } from "bun:test";

import { RefCache } from "../src/cache.js";
import {
  CircularReferenceError,
  isRefId,
  RefResolver,
  resolveArgsAndKwargs,
  resolveKwargs,
  resolveRefs,
  type ResolutionResult,
} from "../src/resolution.js";
import { Permission } from "../src/models/permissions.js";
import { AccessPolicySchema } from "../src/models/permissions.js";

// ── isRefId ──────────────────────────────────────────────────────────

describe("isRefId", () => {
  // Valid patterns

  it("recognizes a valid simple ref_id", () => {
    expect(isRefId("myapp:abc12345")).toBe(true);
  });

  it("recognizes a ref_id with hyphen in cache name", () => {
    expect(isRefId("my-cache:abc12345")).toBe(true);
  });

  it("recognizes a ref_id with underscore in cache name", () => {
    expect(isRefId("my_cache:abc12345")).toBe(true);
  });

  it("recognizes a ref_id with long hash", () => {
    expect(isRefId("finquant:2780226d27c57e49")).toBe(true);
  });

  it("recognizes minimum valid hash length (8 chars)", () => {
    expect(isRefId("myapp:12345678")).toBe(true);
  });

  it("recognizes uppercase cache name", () => {
    expect(isRefId("MyApp:abc12345")).toBe(true);
  });

  // Invalid patterns

  it("rejects string without colon", () => {
    expect(isRefId("just-a-string")).toBe(false);
  });

  it("rejects cache name starting with number", () => {
    expect(isRefId("123cache:abc12345")).toBe(false);
  });

  it("rejects hash shorter than 8 characters", () => {
    expect(isRefId("myapp:abc123")).toBe(false); // Only 6 chars
  });

  it("rejects non-hexadecimal hash", () => {
    expect(isRefId("myapp:abcdefgh")).toBe(false); // 'g' and 'h' not hex
  });

  it("rejects non-string values", () => {
    expect(isRefId(12345)).toBe(false);
    expect(isRefId(null)).toBe(false);
    expect(isRefId(undefined)).toBe(false);
    expect(isRefId({ key: "value" })).toBe(false);
    expect(isRefId(["a", "b"])).toBe(false);
  });

  it("rejects empty string", () => {
    expect(isRefId("")).toBe(false);
  });

  it("rejects string that is only a colon", () => {
    expect(isRefId(":")).toBe(false);
  });

  it("rejects boolean values", () => {
    expect(isRefId(true)).toBe(false);
    expect(isRefId(false)).toBe(false);
  });

  it("rejects cache name with spaces", () => {
    expect(isRefId("my app:abc12345")).toBe(false);
  });

  it("rejects hash with uppercase hex (pattern requires lowercase)", () => {
    expect(isRefId("myapp:ABCDEF12")).toBe(false);
  });
});

// ── ResolutionResult ─────────────────────────────────────────────────

describe("ResolutionResult", () => {
  // We test the structure returned by RefResolver.resolve()
  // rather than constructing ResolutionResult directly since
  // it's a plain object with computed getters in the TS version.

  it("has success=true when no errors", async () => {
    const cache = new RefCache({ name: "test" });
    const reference = await cache.set("data", { key: "value" });
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve(reference.refId);

    expect(result.success).toBe(true);
    expect(result.hasErrors).toBe(false);
    expect(result.resolvedCount).toBe(1);
  });

  it("has success=false when errors exist", async () => {
    const cache = new RefCache({ name: "test" });
    const resolver = new RefResolver(cache, { failOnMissing: false });

    const result = await resolver.resolve("test:abcd1234abcd1234");

    expect(result.success).toBe(false);
    expect(result.hasErrors).toBe(true);
    expect(result.errors["test:abcd1234abcd1234"]).toBeDefined();
  });

  it("tracks resolved refs", async () => {
    const cache = new RefCache({ name: "test" });
    const reference1 = await cache.set("a", "value_a");
    const reference2 = await cache.set("b", "value_b");
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve({
      first: reference1.refId,
      second: reference2.refId,
    });

    expect(result.resolvedCount).toBe(2);
    expect(result.resolvedRefs).toContain(reference1.refId);
    expect(result.resolvedRefs).toContain(reference2.refId);
  });
});

// ── RefResolver ──────────────────────────────────────────────────────

describe("RefResolver", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test" });
  });

  // --- Simple resolution ---

  it("resolves a simple ref_id value", async () => {
    const reference = await cache.set("prices", [100, 101, 102]);
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve(reference.refId);

    expect(result.success).toBe(true);
    expect(result.value).toEqual([100, 101, 102]);
    expect(result.resolvedCount).toBe(1);
    expect(result.resolvedRefs).toContain(reference.refId);
  });

  // --- Dict resolution ---

  it("resolves ref_id as dict value", async () => {
    const reference = await cache.set("data", { nested: "value" });
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve({
      key: reference.refId,
      other: "unchanged",
    });

    expect(result.success).toBe(true);
    expect(result.value).toEqual({
      key: { nested: "value" },
      other: "unchanged",
    });
    expect(result.resolvedCount).toBe(1);
  });

  // --- List/Array resolution ---

  it("resolves ref_id in an array", async () => {
    const reference = await cache.set("item", 42);
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve([1, 2, reference.refId, 4]);

    expect(result.success).toBe(true);
    expect(result.value).toEqual([1, 2, 42, 4]);
    expect(result.resolvedCount).toBe(1);
  });

  // --- Nested resolution ---

  it("resolves ref_id in deeply nested dict", async () => {
    const reference = await cache.set("deep", "found_it");
    const resolver = new RefResolver(cache);

    const nestedInput = {
      level1: { level2: { level3: reference.refId } },
    };
    const result = await resolver.resolve(nestedInput);

    expect(result.success).toBe(true);
    expect(result.value).toEqual({
      level1: { level2: { level3: "found_it" } },
    });
  });

  it("resolves ref_id in array inside dict", async () => {
    const reference = await cache.set("value", 999);
    const resolver = new RefResolver(cache);

    const inputData = { items: [1, 2, reference.refId, 4] };
    const result = await resolver.resolve(inputData);

    expect(result.success).toBe(true);
    expect(result.value).toEqual({ items: [1, 2, 999, 4] });
  });

  // --- Multiple refs ---

  it("resolves multiple ref_ids in same structure", async () => {
    const reference1 = await cache.set("a", "value_a");
    const reference2 = await cache.set("b", "value_b");
    const reference3 = await cache.set("c", "value_c");
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve({
      first: reference1.refId,
      second: reference2.refId,
      nested: { third: reference3.refId },
    });

    expect(result.success).toBe(true);
    expect(result.value).toEqual({
      first: "value_a",
      second: "value_b",
      nested: { third: "value_c" },
    });
    expect(result.resolvedCount).toBe(3);
  });

  // --- Mixed refs and values ---

  it("resolves structure with both refs and regular values", async () => {
    const reference = await cache.set("data", [1, 2, 3]);
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve({
      AAPL: [100, 101, reference.refId],
      MSX: reference.refId,
      factor: 2.5,
      name: "portfolio",
    });

    expect(result.success).toBe(true);
    expect(result.value).toEqual({
      AAPL: [100, 101, [1, 2, 3]],
      MSX: [1, 2, 3],
      factor: 2.5,
      name: "portfolio",
    });
  });

  // --- Non-ref values pass through ---

  it("passes non-ref values through unchanged", async () => {
    const resolver = new RefResolver(cache);

    const inputData = { num: 42, str: "hello", list: [1, 2, 3] };
    const result = await resolver.resolve(inputData);

    expect(result.success).toBe(true);
    expect(result.value).toEqual(inputData);
    expect(result.resolvedCount).toBe(0);
  });

  it("passes primitive values through unchanged", async () => {
    const resolver = new RefResolver(cache);

    expect((await resolver.resolve(42)).value).toBe(42);
    expect((await resolver.resolve("hello")).value).toBe("hello");
    expect((await resolver.resolve(true)).value).toBe(true);
    expect((await resolver.resolve(null)).value).toBe(null);
  });

  // --- Missing ref handling ---

  it("raises error for missing ref when failOnMissing=true", async () => {
    const resolver = new RefResolver(cache, { failOnMissing: true });

    await expect(
      resolver.resolve("test:abcd1234abcd1234"),
    ).rejects.toThrow("Invalid or inaccessible reference");
  });

  it("collects error for missing ref when failOnMissing=false", async () => {
    const resolver = new RefResolver(cache, { failOnMissing: false });

    const result = await resolver.resolve("test:abcd1234abcd1234");

    expect(result.hasErrors).toBe(true);
    expect(result.errors["test:abcd1234abcd1234"]).toBeDefined();
    // Original value kept when resolution fails
    expect(result.value).toBe("test:abcd1234abcd1234");
  });

  // --- Permission denied handling ---

  it("raises opaque error for permission denied when failOnMissing=true", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    const reference = await cache.set("secret", "hidden", { policy });
    const resolver = new RefResolver(cache, {
      actor: "agent",
      failOnMissing: true,
    });

    // Should throw with opaque message (not "permission denied")
    await expect(resolver.resolve(reference.refId)).rejects.toThrow(
      "Invalid or inaccessible reference",
    );
  });

  it("collects opaque error for permission denied when failOnMissing=false", async () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    const reference = await cache.set("secret", "hidden", { policy });
    const resolver = new RefResolver(cache, {
      actor: "agent",
      failOnMissing: false,
    });

    const result = await resolver.resolve(reference.refId);

    expect(result.hasErrors).toBe(true);
    expect(result.errors[reference.refId]).toBe(
      "Invalid or inaccessible reference",
    );
  });

  // --- Nested ref resolution (transitive) ---

  it("resolves nested refs within resolved values", async () => {
    // Store a value that itself contains a ref_id
    const innerReference = await cache.set("inner", "deep_value");
    const outerReference = await cache.set("outer", {
      nested: innerReference.refId,
    });
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve(outerReference.refId);

    expect(result.success).toBe(true);
    expect(result.value).toEqual({ nested: "deep_value" });
    expect(result.resolvedCount).toBe(2);
  });
});

// ── resolveRefs convenience function ─────────────────────────────────

describe("resolveRefs", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test" });
  });

  it("resolves refs in a simple structure", async () => {
    const reference = await cache.set("data", { key: "value" });

    const result = await resolveRefs(cache, { input: reference.refId });

    expect(result.success).toBe(true);
    expect(result.value).toEqual({ input: { key: "value" } });
  });

  it("resolves refs with specific actor", async () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
    });
    const reference = await cache.set("data", "secret", { policy });

    const result = await resolveRefs(cache, reference.refId, {
      actor: "user",
    });

    expect(result.success).toBe(true);
    expect(result.value).toBe("secret");
  });

  it("uses failOnMissing=true by default", async () => {
    await expect(
      resolveRefs(cache, "test:abcd1234abcd1234"),
    ).rejects.toThrow("Invalid or inaccessible reference");
  });

  it("respects failOnMissing=false option", async () => {
    const result = await resolveRefs(cache, "test:abcd1234abcd1234", {
      failOnMissing: false,
    });

    expect(result.hasErrors).toBe(true);
  });
});

// ── resolveKwargs convenience function ───────────────────────────────

describe("resolveKwargs", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test" });
  });

  it("resolves refs in function kwargs", async () => {
    const reference = await cache.set("prices", [100, 200, 300]);

    const result = await resolveKwargs(cache, {
      data: reference.refId,
      factor: 2.0,
    });

    expect(result.success).toBe(true);
    expect(result.value).toEqual({
      data: [100, 200, 300],
      factor: 2.0,
    });
  });

  it("passes through kwargs with no refs", async () => {
    const result = await resolveKwargs(cache, {
      name: "test",
      count: 5,
    });

    expect(result.success).toBe(true);
    expect(result.value).toEqual({ name: "test", count: 5 });
    expect(result.resolvedCount).toBe(0);
  });
});

// ── resolveArgsAndKwargs ─────────────────────────────────────────────

describe("resolveArgsAndKwargs", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test" });
  });

  it("resolves refs in both args and kwargs", async () => {
    const reference1 = await cache.set("arg_val", [1, 2, 3]);
    const reference2 = await cache.set("kwarg_val", { a: "b" });

    const args = [reference1.refId, "regular_arg"];
    const kwargs = { data: reference2.refId, count: 5 };

    const [argsResult, kwargsResult] = await resolveArgsAndKwargs(
      cache,
      args,
      kwargs,
    );

    expect(argsResult.success).toBe(true);
    expect(kwargsResult.success).toBe(true);
    expect(argsResult.value).toEqual([[1, 2, 3], "regular_arg"]);
    expect(kwargsResult.value).toEqual({ data: { a: "b" }, count: 5 });
  });

  it("resolves only in args when kwargs have no refs", async () => {
    const reference = await cache.set("val", 42);

    const args = [reference.refId];
    const kwargs = { normal: "value" };

    const [argsResult, kwargsResult] = await resolveArgsAndKwargs(
      cache,
      args,
      kwargs,
    );

    expect(argsResult.success).toBe(true);
    expect(kwargsResult.success).toBe(true);
    expect(argsResult.value).toEqual([42]);
    expect(kwargsResult.value).toEqual({ normal: "value" });
  });

  it("handles empty args and kwargs", async () => {
    const [argsResult, kwargsResult] = await resolveArgsAndKwargs(
      cache,
      [],
      {},
    );

    expect(argsResult.success).toBe(true);
    expect(kwargsResult.success).toBe(true);
    expect(argsResult.value).toEqual([]);
    expect(kwargsResult.value).toEqual({});
  });
});

// ── Circular Reference Detection ─────────────────────────────────────

describe("CircularReferenceDetection", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test" });
  });

  it("detects self-referencing value", async () => {
    // Store a value first to get a ref_id
    const reference = await cache.set("data", [1, 2, 3]);

    // Manually update the stored value to reference itself
    // (simulating circular reference)
    await cache.setEntryValueForTesting(reference.refId, {
      self: reference.refId,
    });

    const resolver = new RefResolver(cache);
    await expect(resolver.resolve(reference.refId)).rejects.toThrow(
      CircularReferenceError,
    );
  });

  it("detects indirect circular reference (A -> B -> A)", async () => {
    const referenceA = await cache.set("a", { placeholder: true });
    const referenceB = await cache.set("b", { next: referenceA.refId });

    // Update A to point to B (creating cycle)
    await cache.setEntryValueForTesting(referenceA.refId, {
      next: referenceB.refId,
    });

    const resolver = new RefResolver(cache);
    await expect(resolver.resolve(referenceA.refId)).rejects.toThrow(
      CircularReferenceError,
    );
  });

  it("detects three-level circular reference (A -> B -> C -> A)", async () => {
    const referenceA = await cache.set("a", { placeholder: true });
    const referenceB = await cache.set("b", { placeholder: true });
    const referenceC = await cache.set("c", { next: referenceA.refId });

    // Update A -> B and B -> C
    await cache.setEntryValueForTesting(referenceA.refId, {
      next: referenceB.refId,
    });
    await cache.setEntryValueForTesting(referenceB.refId, {
      next: referenceC.refId,
    });

    const resolver = new RefResolver(cache);
    await expect(resolver.resolve(referenceA.refId)).rejects.toThrow(
      CircularReferenceError,
    );
  });

  it("does not false-positive for same ref in sibling positions", async () => {
    const referenceData = await cache.set("data", [100, 200, 300]);

    // Same ref_id used multiple times in parallel (not circular)
    const structure = {
      first: referenceData.refId,
      second: referenceData.refId,
      nested: { also: referenceData.refId },
    };

    const resolver = new RefResolver(cache);
    const result = await resolver.resolve(structure);

    // Should resolve successfully — no cycle here
    expect(result.success).toBe(true);
    expect(result.value).toEqual({
      first: [100, 200, 300],
      second: [100, 200, 300],
      nested: { also: [100, 200, 300] },
    });
  });

  it("includes reference chain in CircularReferenceError", async () => {
    const reference = await cache.set("self_ref", { placeholder: true });
    await cache.setEntryValueForTesting(reference.refId, {
      loop: reference.refId,
    });

    const resolver = new RefResolver(cache);

    try {
      await resolver.resolve(reference.refId);
      // Should not reach here
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(CircularReferenceError);
      const circularError = error as CircularReferenceError;
      expect(circularError.refId).toBe(reference.refId);
      expect(circularError.chain).toContain(reference.refId);
      expect(circularError.message).toContain("Circular reference detected");
    }
  });

  it("includes chain path in error message", async () => {
    const referenceA = await cache.set("a", { placeholder: true });
    const referenceB = await cache.set("b", { next: referenceA.refId });

    await cache.setEntryValueForTesting(referenceA.refId, {
      next: referenceB.refId,
    });

    const resolver = new RefResolver(cache);

    try {
      await resolver.resolve(referenceA.refId);
      expect(true).toBe(false);
    } catch (error) {
      const circularError = error as CircularReferenceError;
      // Message should show the chain: A -> B -> A
      expect(circularError.message).toContain(referenceA.refId);
      expect(circularError.message).toContain(referenceB.refId);
    }
  });
});

// ── Security Considerations ──────────────────────────────────────────

describe("SecurityConsiderations", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "secure" });
  });

  it("uses identical opaque errors for missing vs permission denied", async () => {
    // Create a ref that agent can't access
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    const existingReference = await cache.set("secret", "hidden", {
      policy,
    });

    const resolver = new RefResolver(cache, {
      actor: "agent",
      failOnMissing: false,
    });

    // Resolve the existing (but denied) ref
    const result1 = await resolver.resolve(existingReference.refId);

    // Resolve a non-existent ref
    const result2 = await resolver.resolve("secure:abcd1234abcd1234");

    // Both should have errors
    expect(result1.hasErrors).toBe(true);
    expect(result2.hasErrors).toBe(true);

    // Error messages MUST be identical (opaque — no info leakage)
    const error1 = result1.errors[existingReference.refId];
    const error2 = result2.errors["secure:abcd1234abcd1234"];

    expect(error1).toBe(error2);
    expect(error1).toBe("Invalid or inaccessible reference");

    // Must not contain revealing keywords
    expect(error1!.toLowerCase()).not.toContain("permission");
    expect(error1!.toLowerCase()).not.toContain("denied");
    expect(error1!.toLowerCase()).not.toContain("not found");
    expect(error1!.toLowerCase()).not.toContain("expired");
  });

  it("raises opaque errors when failOnMissing=true", async () => {
    // Create a ref that agent can't access
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
    });
    const existingReference = await cache.set("secret", "hidden", {
      policy,
    });

    const resolver = new RefResolver(cache, {
      actor: "agent",
      failOnMissing: true,
    });

    // Permission denied should raise with opaque message
    let error1Message = "";
    try {
      await resolver.resolve(existingReference.refId);
    } catch (error) {
      error1Message = (error as Error).message;
    }

    // Not found should raise with same opaque message
    let error2Message = "";
    try {
      await resolver.resolve("secure:abcd1234abcd1234");
    } catch (error) {
      error2Message = (error as Error).message;
    }

    // Both should use opaque message format
    expect(error1Message).toContain("Invalid or inaccessible reference");
    expect(error2Message).toContain("Invalid or inaccessible reference");

    // Should not contain revealing info
    expect(error1Message.toLowerCase()).not.toContain("permission");
    expect(error1Message.toLowerCase()).not.toContain("denied");
  });

  it("ref_id pattern prevents injection attempts", () => {
    const maliciousInputs = [
      "../../../etc/passwd",
      "test:../secret",
      "test:; DROP TABLE users;",
      "test:$(whoami)",
      "test:`id`",
      "test:<script>alert(1)</script>",
      "test:' OR '1'='1",
    ];

    for (const malicious of maliciousInputs) {
      expect(isRefId(malicious)).toBe(false);
    }
  });

  it("ref_id pattern rejects path traversal in cache name", () => {
    expect(isRefId("../etc:abcd1234")).toBe(false);
    expect(isRefId("./local:abcd1234")).toBe(false);
    expect(isRefId("/root:abcd1234")).toBe(false);
  });
});

// ── Edge Cases ───────────────────────────────────────────────────────

describe("EdgeCases", () => {
  let cache: RefCache;

  beforeEach(() => {
    cache = new RefCache({ name: "test" });
  });

  it("handles empty object input", async () => {
    const resolver = new RefResolver(cache);
    const result = await resolver.resolve({});

    expect(result.success).toBe(true);
    expect(result.value).toEqual({});
    expect(result.resolvedCount).toBe(0);
  });

  it("handles empty array input", async () => {
    const resolver = new RefResolver(cache);
    const result = await resolver.resolve([]);

    expect(result.success).toBe(true);
    expect(result.value).toEqual([]);
    expect(result.resolvedCount).toBe(0);
  });

  it("handles deeply nested empty structures", async () => {
    const resolver = new RefResolver(cache);
    const result = await resolver.resolve({
      a: { b: { c: { d: [] } } },
    });

    expect(result.success).toBe(true);
    expect(result.value).toEqual({ a: { b: { c: { d: [] } } } });
  });

  it("resolves ref that stores null value", async () => {
    const reference = await cache.set("null_val", null);
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve(reference.refId);

    expect(result.success).toBe(true);
    expect(result.value).toBeNull();
    expect(result.resolvedCount).toBe(1);
  });

  it("resolves ref that stores empty string", async () => {
    const reference = await cache.set("empty", "");
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve(reference.refId);

    expect(result.success).toBe(true);
    expect(result.value).toBe("");
    expect(result.resolvedCount).toBe(1);
  });

  it("resolves ref that stores zero", async () => {
    const reference = await cache.set("zero", 0);
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve(reference.refId);

    expect(result.success).toBe(true);
    expect(result.value).toBe(0);
    expect(result.resolvedCount).toBe(1);
  });

  it("resolves ref that stores false", async () => {
    const reference = await cache.set("falsy", false);
    const resolver = new RefResolver(cache);

    const result = await resolver.resolve(reference.refId);

    expect(result.success).toBe(true);
    expect(result.value).toBe(false);
    expect(result.resolvedCount).toBe(1);
  });

  it("does not treat dict keys as ref_ids", async () => {
    const reference = await cache.set("data", "value");
    const resolver = new RefResolver(cache);

    // Keys should not be resolved, only values
    const result = await resolver.resolve({
      [reference.refId]: "not_a_ref_value",
    });

    expect(result.success).toBe(true);
    // The key should remain unchanged
    expect(result.value).toEqual({
      [reference.refId]: "not_a_ref_value",
    });
    expect(result.resolvedCount).toBe(0);
  });

  it("handles multiple errors when failOnMissing=false", async () => {
    const resolver = new RefResolver(cache, { failOnMissing: false });

    const result = await resolver.resolve({
      first: "test:aaaa1111aaaa1111",
      second: "test:bbbb2222bbbb2222",
      ok: "not a ref",
    });

    expect(result.hasErrors).toBe(true);
    expect(Object.keys(result.errors)).toHaveLength(2);
    expect(result.errors["test:aaaa1111aaaa1111"]).toBeDefined();
    expect(result.errors["test:bbbb2222bbbb2222"]).toBeDefined();
    // Non-ref value should pass through
    expect((result.value as Record<string, unknown>).ok).toBe("not a ref");
  });

  it("handles mixed success and failure when failOnMissing=false", async () => {
    const reference = await cache.set("real", "real_value");
    const resolver = new RefResolver(cache, { failOnMissing: false });

    const result = await resolver.resolve({
      good: reference.refId,
      bad: "test:dead0000beef1111",
    });

    expect(result.hasErrors).toBe(true);
    expect(result.resolvedCount).toBe(1);
    expect((result.value as Record<string, unknown>).good).toBe("real_value");
    expect((result.value as Record<string, unknown>).bad).toBe(
      "test:dead0000beef1111",
    );
  });
});

// ── CircularReferenceError class ─────────────────────────────────────

describe("CircularReferenceError", () => {
  it("is an instance of Error", () => {
    const error = new CircularReferenceError("test:abc12345678", [
      "test:def12345678",
    ]);
    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(CircularReferenceError);
  });

  it("has correct name property", () => {
    const error = new CircularReferenceError("test:abc12345678", [
      "test:def12345678",
    ]);
    expect(error.name).toBe("CircularReferenceError");
  });

  it("stores refId and chain", () => {
    const chain = ["test:aaa11111111", "test:bbb22222222"];
    const error = new CircularReferenceError("test:ccc33333333", chain);

    expect(error.refId).toBe("test:ccc33333333");
    expect(error.chain).toEqual(chain);
  });

  it("formats message with chain path", () => {
    const error = new CircularReferenceError("test:ccc33333333", [
      "test:aaa11111111",
      "test:bbb22222222",
    ]);

    expect(error.message).toContain("Circular reference detected");
    expect(error.message).toContain("test:aaa11111111");
    expect(error.message).toContain("test:bbb22222222");
    expect(error.message).toContain("test:ccc33333333");
  });

  it("handles single-element chain (self-reference)", () => {
    const error = new CircularReferenceError("test:abc12345678", [
      "test:abc12345678",
    ]);

    expect(error.message).toContain("Circular reference detected");
    expect(error.refId).toBe("test:abc12345678");
  });
});
