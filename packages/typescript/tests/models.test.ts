import { describe, expect, it } from "bun:test";

import {
  // Enums
  ActorType,
  ActorTypeSchema,
  AsyncResponseFormat,
  AsyncResponseFormatSchema,
  PreviewStrategy,
  PreviewStrategySchema,
  SizeMode,
  SizeModeSchema,
  TaskStatus,
  TaskStatusSchema,
  // Permissions
  AccessPolicySchema,
  agentCan,
  combinePermissions,
  hasPermission,
  Permission,
  PermissionSchema,
  POLICY_EXECUTE_ONLY,
  POLICY_PUBLIC,
  POLICY_READ_ONLY,
  POLICY_USER_ONLY,
  userCan,
  // Preview
  PreviewConfigSchema,
  PreviewResultSchema,
  // Cache
  CacheEntrySchema,
  CacheReferenceSchema,
  CacheResponseSchema,
  isExpired,
  PaginatedResponseSchema,
  paginateList,
  // Tasks
  asyncTaskResponseFromInfo,
  AsyncTaskResponseSchema,
  asyncTaskResponseToDict,
  canRetry,
  elapsedSeconds,
  ExpectedSchemaSchema,
  isTerminal,
  RetryInfoSchema,
  TaskInfoSchema,
  TaskProgressSchema,
} from "../src/index.js";

// ═════════════════════════════════════════════════════════════════════
// Enums
// ═════════════════════════════════════════════════════════════════════

describe("SizeModeSchema", () => {
  it("accepts valid values", () => {
    expect(SizeModeSchema.parse("token")).toBe("token");
    expect(SizeModeSchema.parse("character")).toBe("character");
  });

  it("rejects invalid values", () => {
    expect(() => SizeModeSchema.parse("bytes")).toThrow();
    expect(() => SizeModeSchema.parse("")).toThrow();
    expect(() => SizeModeSchema.parse(42)).toThrow();
  });

  it("exposes convenience constants", () => {
    expect(SizeMode.TOKEN).toBe("token");
    expect(SizeMode.CHARACTER).toBe("character");
  });
});

describe("PreviewStrategySchema", () => {
  it("accepts valid values", () => {
    expect(PreviewStrategySchema.parse("truncate")).toBe("truncate");
    expect(PreviewStrategySchema.parse("paginate")).toBe("paginate");
    expect(PreviewStrategySchema.parse("sample")).toBe("sample");
  });

  it("rejects invalid values", () => {
    expect(() => PreviewStrategySchema.parse("compress")).toThrow();
  });

  it("exposes convenience constants", () => {
    expect(PreviewStrategy.TRUNCATE).toBe("truncate");
    expect(PreviewStrategy.PAGINATE).toBe("paginate");
    expect(PreviewStrategy.SAMPLE).toBe("sample");
  });
});

describe("AsyncResponseFormatSchema", () => {
  it("accepts valid values", () => {
    expect(AsyncResponseFormatSchema.parse("minimal")).toBe("minimal");
    expect(AsyncResponseFormatSchema.parse("standard")).toBe("standard");
    expect(AsyncResponseFormatSchema.parse("full")).toBe("full");
  });

  it("rejects invalid values", () => {
    expect(() => AsyncResponseFormatSchema.parse("verbose")).toThrow();
  });

  it("exposes convenience constants", () => {
    expect(AsyncResponseFormat.MINIMAL).toBe("minimal");
    expect(AsyncResponseFormat.STANDARD).toBe("standard");
    expect(AsyncResponseFormat.FULL).toBe("full");
  });
});

describe("TaskStatusSchema", () => {
  it("accepts all lifecycle states", () => {
    for (const status of [
      "pending",
      "processing",
      "complete",
      "failed",
      "cancelled",
    ]) {
      expect(TaskStatusSchema.parse(status)).toBe(status);
    }
  });

  it("rejects invalid statuses", () => {
    expect(() => TaskStatusSchema.parse("running")).toThrow();
    expect(() => TaskStatusSchema.parse("queued")).toThrow();
  });

  it("exposes convenience constants", () => {
    expect(TaskStatus.PENDING).toBe("pending");
    expect(TaskStatus.PROCESSING).toBe("processing");
    expect(TaskStatus.COMPLETE).toBe("complete");
    expect(TaskStatus.FAILED).toBe("failed");
    expect(TaskStatus.CANCELLED).toBe("cancelled");
  });
});

describe("ActorTypeSchema", () => {
  it("accepts valid actor types", () => {
    expect(ActorTypeSchema.parse("user")).toBe("user");
    expect(ActorTypeSchema.parse("agent")).toBe("agent");
    expect(ActorTypeSchema.parse("system")).toBe("system");
  });

  it("rejects invalid types", () => {
    expect(() => ActorTypeSchema.parse("admin")).toThrow();
    expect(() => ActorTypeSchema.parse("")).toThrow();
  });

  it("exposes convenience constants", () => {
    expect(ActorType.USER).toBe("user");
    expect(ActorType.AGENT).toBe("agent");
    expect(ActorType.SYSTEM).toBe("system");
  });
});

// ═════════════════════════════════════════════════════════════════════
// Permissions
// ═════════════════════════════════════════════════════════════════════

describe("Permission", () => {
  it("has correct bitfield values matching Python auto()", () => {
    expect(Permission.NONE).toBe(0);
    expect(Permission.READ).toBe(1);
    expect(Permission.WRITE).toBe(2);
    expect(Permission.UPDATE).toBe(4);
    expect(Permission.DELETE).toBe(8);
    expect(Permission.EXECUTE).toBe(16);
  });

  it("has correct compound values", () => {
    expect(Permission.CRUD).toBe(
      Permission.READ | Permission.WRITE | Permission.UPDATE | Permission.DELETE,
    );
    expect(Permission.CRUD).toBe(15);
    expect(Permission.FULL).toBe(Permission.CRUD | Permission.EXECUTE);
    expect(Permission.FULL).toBe(31);
  });

  it("supports bitwise combination", () => {
    const readWrite = Permission.READ | Permission.WRITE;
    expect(readWrite).toBe(3);
    expect(readWrite & Permission.READ).toBeTruthy();
    expect(readWrite & Permission.EXECUTE).toBeFalsy();
  });
});

describe("hasPermission", () => {
  it("returns true when all required bits are set", () => {
    expect(hasPermission(Permission.FULL, Permission.READ)).toBe(true);
    expect(hasPermission(Permission.FULL, Permission.EXECUTE)).toBe(true);
    expect(hasPermission(Permission.CRUD, Permission.READ)).toBe(true);
    expect(
      hasPermission(
        Permission.READ | Permission.WRITE,
        Permission.READ | Permission.WRITE,
      ),
    ).toBe(true);
  });

  it("returns false when required bits are missing", () => {
    expect(hasPermission(Permission.NONE, Permission.READ)).toBe(false);
    expect(hasPermission(Permission.READ, Permission.WRITE)).toBe(false);
    expect(hasPermission(Permission.CRUD, Permission.EXECUTE)).toBe(false);
  });

  it("handles NONE correctly", () => {
    expect(hasPermission(Permission.NONE, Permission.NONE)).toBe(true);
    expect(hasPermission(Permission.FULL, Permission.NONE)).toBe(true);
  });
});

describe("combinePermissions", () => {
  it("combines multiple flags", () => {
    const combined = combinePermissions(
      Permission.READ,
      Permission.WRITE,
      Permission.EXECUTE,
    );
    expect(hasPermission(combined, Permission.READ)).toBe(true);
    expect(hasPermission(combined, Permission.WRITE)).toBe(true);
    expect(hasPermission(combined, Permission.EXECUTE)).toBe(true);
    expect(hasPermission(combined, Permission.DELETE)).toBe(false);
  });

  it("returns NONE for empty input", () => {
    expect(combinePermissions()).toBe(Permission.NONE);
  });

  it("handles duplicates", () => {
    const combined = combinePermissions(Permission.READ, Permission.READ);
    expect(combined).toBe(Permission.READ);
  });
});

describe("PermissionSchema", () => {
  it("accepts valid permission values", () => {
    expect(PermissionSchema.parse(0)).toBe(0);
    expect(PermissionSchema.parse(Permission.READ)).toBe(1);
    expect(PermissionSchema.parse(Permission.FULL)).toBe(31);
  });

  it("rejects out-of-range values", () => {
    expect(() => PermissionSchema.parse(-1)).toThrow();
    expect(() => PermissionSchema.parse(32)).toThrow();
  });

  it("rejects non-integers", () => {
    expect(() => PermissionSchema.parse(1.5)).toThrow();
    expect(() => PermissionSchema.parse("read")).toThrow();
  });
});

describe("AccessPolicySchema", () => {
  it("parses with all defaults", () => {
    const policy = AccessPolicySchema.parse({});
    expect(policy.userPermissions).toBe(Permission.FULL);
    expect(policy.agentPermissions).toBe(
      Permission.READ | Permission.EXECUTE,
    );
    expect(policy.owner).toBeNull();
    expect(policy.ownerPermissions).toBe(Permission.FULL);
    expect(policy.allowedActors).toBeNull();
    expect(policy.deniedActors).toBeNull();
    expect(policy.boundSession).toBeNull();
  });

  it("parses with explicit permissions", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      agentPermissions: Permission.EXECUTE,
    });
    expect(policy.userPermissions).toBe(Permission.READ);
    expect(policy.agentPermissions).toBe(Permission.EXECUTE);
  });

  it("parses with ownership", () => {
    const policy = AccessPolicySchema.parse({
      owner: "user:alice",
      ownerPermissions: Permission.FULL,
    });
    expect(policy.owner).toBe("user:alice");
    expect(policy.ownerPermissions).toBe(Permission.FULL);
  });

  it("parses with ACL lists", () => {
    const policy = AccessPolicySchema.parse({
      allowedActors: ["user:alice", "agent:*"],
      deniedActors: ["user:untrusted"],
    });
    expect(policy.allowedActors).toEqual(["user:alice", "agent:*"]);
    expect(policy.deniedActors).toEqual(["user:untrusted"]);
  });

  it("parses with session binding", () => {
    const policy = AccessPolicySchema.parse({
      boundSession: "sess-abc123",
    });
    expect(policy.boundSession).toBe("sess-abc123");
  });

  it("rejects invalid permission values", () => {
    expect(() =>
      AccessPolicySchema.parse({ userPermissions: -1 }),
    ).toThrow();
    expect(() =>
      AccessPolicySchema.parse({ agentPermissions: 999 }),
    ).toThrow();
  });
});

describe("userCan / agentCan", () => {
  it("checks user permissions correctly", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ | Permission.WRITE,
      agentPermissions: Permission.EXECUTE,
    });
    expect(userCan(policy, Permission.READ)).toBe(true);
    expect(userCan(policy, Permission.WRITE)).toBe(true);
    expect(userCan(policy, Permission.EXECUTE)).toBe(false);
  });

  it("checks agent permissions correctly", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      agentPermissions: Permission.EXECUTE,
    });
    expect(agentCan(policy, Permission.EXECUTE)).toBe(true);
    expect(agentCan(policy, Permission.READ)).toBe(false);
  });
});

describe("Policy presets", () => {
  it("POLICY_PUBLIC grants full access to both", () => {
    expect(POLICY_PUBLIC.userPermissions).toBe(Permission.FULL);
    expect(POLICY_PUBLIC.agentPermissions).toBe(Permission.FULL);
  });

  it("POLICY_USER_ONLY blocks agents", () => {
    expect(POLICY_USER_ONLY.userPermissions).toBe(Permission.FULL);
    expect(POLICY_USER_ONLY.agentPermissions).toBe(Permission.NONE);
  });

  it("POLICY_EXECUTE_ONLY allows blind compute for agents", () => {
    expect(POLICY_EXECUTE_ONLY.userPermissions).toBe(Permission.FULL);
    expect(POLICY_EXECUTE_ONLY.agentPermissions).toBe(Permission.EXECUTE);
    expect(agentCan(POLICY_EXECUTE_ONLY, Permission.READ)).toBe(false);
    expect(agentCan(POLICY_EXECUTE_ONLY, Permission.EXECUTE)).toBe(true);
  });

  it("POLICY_READ_ONLY allows only read for both", () => {
    expect(POLICY_READ_ONLY.userPermissions).toBe(Permission.READ);
    expect(POLICY_READ_ONLY.agentPermissions).toBe(Permission.READ);
    expect(userCan(POLICY_READ_ONLY, Permission.WRITE)).toBe(false);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Preview
// ═════════════════════════════════════════════════════════════════════

describe("PreviewConfigSchema", () => {
  it("parses with all defaults", () => {
    const config = PreviewConfigSchema.parse({});
    expect(config.sizeMode).toBe("token");
    expect(config.maxSize).toBe(1000);
    expect(config.defaultStrategy).toBe("sample");
  });

  it("accepts custom values", () => {
    const config = PreviewConfigSchema.parse({
      sizeMode: "character",
      maxSize: 500,
      defaultStrategy: "truncate",
    });
    expect(config.sizeMode).toBe("character");
    expect(config.maxSize).toBe(500);
    expect(config.defaultStrategy).toBe("truncate");
  });

  it("rejects non-positive maxSize", () => {
    expect(() => PreviewConfigSchema.parse({ maxSize: 0 })).toThrow();
    expect(() => PreviewConfigSchema.parse({ maxSize: -10 })).toThrow();
  });

  it("rejects invalid sizeMode", () => {
    expect(() =>
      PreviewConfigSchema.parse({ sizeMode: "bytes" }),
    ).toThrow();
  });

  it("rejects invalid strategy", () => {
    expect(() =>
      PreviewConfigSchema.parse({ defaultStrategy: "compress" }),
    ).toThrow();
  });
});

describe("PreviewResultSchema", () => {
  it("parses a complete preview result", () => {
    const result = PreviewResultSchema.parse({
      value: [1, 2, 3],
      originalSize: 5000,
      previewSize: 450,
      strategy: "sample",
      totalItems: 200,
      previewItems: 3,
    });
    expect(result.originalSize).toBe(5000);
    expect(result.previewSize).toBe(450);
    expect(result.strategy).toBe("sample");
    expect(result.totalItems).toBe(200);
    expect(result.previewItems).toBe(3);
  });

  it("accepts null optional fields", () => {
    const result = PreviewResultSchema.parse({
      value: "hello",
      originalSize: 100,
      previewSize: 50,
      strategy: "truncate",
    });
    expect(result.totalItems).toBeNull();
    expect(result.previewItems).toBeNull();
    expect(result.page).toBeNull();
    expect(result.totalPages).toBeNull();
  });

  it("accepts pagination fields", () => {
    const result = PreviewResultSchema.parse({
      value: [1, 2, 3],
      originalSize: 5000,
      previewSize: 450,
      strategy: "paginate",
      page: 1,
      totalPages: 10,
    });
    expect(result.page).toBe(1);
    expect(result.totalPages).toBe(10);
  });

  it("rejects negative sizes", () => {
    expect(() =>
      PreviewResultSchema.parse({
        value: [],
        originalSize: -1,
        previewSize: 0,
        strategy: "truncate",
      }),
    ).toThrow();
  });
});

// ═════════════════════════════════════════════════════════════════════
// Cache
// ═════════════════════════════════════════════════════════════════════

describe("CacheReferenceSchema", () => {
  it("parses a complete reference", () => {
    const now = Date.now() / 1000;
    const ref = CacheReferenceSchema.parse({
      refId: "my-cache:abc123def456",
      cacheName: "my-cache",
      namespace: "session",
      toolName: "get_users",
      createdAt: now,
      totalItems: 5000,
      totalSize: 102400,
      totalTokens: 25000,
    });
    expect(ref.refId).toBe("my-cache:abc123def456");
    expect(ref.cacheName).toBe("my-cache");
    expect(ref.namespace).toBe("session");
    expect(ref.toolName).toBe("get_users");
    expect(ref.createdAt).toBe(now);
    expect(ref.totalItems).toBe(5000);
  });

  it("applies defaults for optional fields", () => {
    const ref = CacheReferenceSchema.parse({
      refId: "test:abc",
      cacheName: "test",
      createdAt: 1000,
    });
    expect(ref.namespace).toBe("public");
    expect(ref.toolName).toBeNull();
    expect(ref.expiresAt).toBeNull();
    expect(ref.totalItems).toBeNull();
    expect(ref.totalSize).toBeNull();
    expect(ref.totalTokens).toBeNull();
  });

  it("rejects empty refId", () => {
    expect(() =>
      CacheReferenceSchema.parse({
        refId: "",
        cacheName: "test",
        createdAt: 1000,
      }),
    ).toThrow();
  });

  it("rejects empty cacheName", () => {
    expect(() =>
      CacheReferenceSchema.parse({
        refId: "test:abc",
        cacheName: "",
        createdAt: 1000,
      }),
    ).toThrow();
  });

  it("rejects negative totalItems", () => {
    expect(() =>
      CacheReferenceSchema.parse({
        refId: "test:abc",
        cacheName: "test",
        createdAt: 1000,
        totalItems: -1,
      }),
    ).toThrow();
  });
});

describe("PaginatedResponseSchema", () => {
  it("parses a valid page", () => {
    const page = PaginatedResponseSchema.parse({
      items: [1, 2, 3],
      page: 1,
      pageSize: 20,
      totalItems: 100,
      totalPages: 5,
      hasNext: true,
      hasPrevious: false,
    });
    expect(page.items).toEqual([1, 2, 3]);
    expect(page.page).toBe(1);
    expect(page.hasNext).toBe(true);
    expect(page.hasPrevious).toBe(false);
  });

  it("rejects page < 1", () => {
    expect(() =>
      PaginatedResponseSchema.parse({
        items: [],
        page: 0,
        pageSize: 20,
        totalItems: 0,
        totalPages: 0,
        hasNext: false,
        hasPrevious: false,
      }),
    ).toThrow();
  });

  it("rejects pageSize < 1", () => {
    expect(() =>
      PaginatedResponseSchema.parse({
        items: [],
        page: 1,
        pageSize: 0,
        totalItems: 0,
        totalPages: 0,
        hasNext: false,
        hasPrevious: false,
      }),
    ).toThrow();
  });
});

describe("paginateList", () => {
  const items = Array.from({ length: 55 }, (_, index) => index + 1);

  it("returns first page correctly", () => {
    const result = paginateList(items, 1, 20);
    expect(result.items).toEqual(items.slice(0, 20));
    expect(result.page).toBe(1);
    expect(result.pageSize).toBe(20);
    expect(result.totalItems).toBe(55);
    expect(result.totalPages).toBe(3);
    expect(result.hasNext).toBe(true);
    expect(result.hasPrevious).toBe(false);
  });

  it("returns last page correctly", () => {
    const result = paginateList(items, 3, 20);
    expect(result.items).toEqual(items.slice(40, 55));
    expect(result.items).toHaveLength(15);
    expect(result.hasNext).toBe(false);
    expect(result.hasPrevious).toBe(true);
  });

  it("returns middle page correctly", () => {
    const result = paginateList(items, 2, 20);
    expect(result.items).toEqual(items.slice(20, 40));
    expect(result.hasNext).toBe(true);
    expect(result.hasPrevious).toBe(true);
  });

  it("handles empty list", () => {
    const result = paginateList([], 1, 20);
    expect(result.items).toEqual([]);
    expect(result.totalItems).toBe(0);
    expect(result.totalPages).toBe(0);
    expect(result.hasNext).toBe(false);
    expect(result.hasPrevious).toBe(false);
  });

  it("uses default page and pageSize", () => {
    const result = paginateList(items);
    expect(result.page).toBe(1);
    expect(result.pageSize).toBe(20);
    expect(result.items).toHaveLength(20);
  });

  it("returns empty items for out-of-range page", () => {
    const result = paginateList(items, 100, 20);
    expect(result.items).toEqual([]);
  });
});

describe("CacheResponseSchema", () => {
  it("parses a complete response", () => {
    const response = CacheResponseSchema.parse({
      refId: "my-cache:abc123",
      cacheName: "my-cache",
      namespace: "session",
      totalItems: 5000,
      totalTokens: 25000,
      originalSize: 25000,
      previewSize: 950,
      preview: [{ id: 1 }, { id: 100 }, { id: 500 }],
      previewStrategy: "sample",
      page: 1,
      totalPages: 50,
    });
    expect(response.refId).toBe("my-cache:abc123");
    expect(response.previewStrategy).toBe("sample");
    expect(response.availableActions).toEqual([
      "get_page",
      "resolve_full",
      "pass_to_tool",
    ]);
  });

  it("applies defaults for optional fields", () => {
    const response = CacheResponseSchema.parse({
      refId: "test:abc",
      cacheName: "test",
      preview: "hello world",
      previewStrategy: "truncate",
    });
    expect(response.namespace).toBe("public");
    expect(response.totalItems).toBeNull();
    expect(response.totalTokens).toBeNull();
    expect(response.originalSize).toBeNull();
    expect(response.previewSize).toBeNull();
    expect(response.page).toBeNull();
    expect(response.totalPages).toBeNull();
  });

  it("allows custom availableActions", () => {
    const response = CacheResponseSchema.parse({
      refId: "test:abc",
      cacheName: "test",
      preview: null,
      previewStrategy: "truncate",
      availableActions: ["resolve_full"],
    });
    expect(response.availableActions).toEqual(["resolve_full"]);
  });
});

describe("CacheEntrySchema", () => {
  it("parses a complete entry", () => {
    const now = Date.now() / 1000;
    const entry = CacheEntrySchema.parse({
      value: { users: [1, 2, 3] },
      namespace: "session",
      policy: {
        userPermissions: Permission.FULL,
        agentPermissions: Permission.READ,
      },
      createdAt: now,
      expiresAt: now + 3600,
      metadata: { toolName: "get_users", totalItems: 3 },
    });
    expect(entry.namespace).toBe("session");
    expect(entry.policy.userPermissions).toBe(Permission.FULL);
    expect(entry.policy.agentPermissions).toBe(Permission.READ);
    expect(entry.metadata).toEqual({ toolName: "get_users", totalItems: 3 });
  });

  it("applies defaults for optional fields", () => {
    const entry = CacheEntrySchema.parse({
      value: 42,
      namespace: "public",
      policy: {},
      createdAt: 1000,
    });
    expect(entry.expiresAt).toBeNull();
    expect(entry.metadata).toEqual({});
    // Policy uses its own defaults
    expect(entry.policy.userPermissions).toBe(Permission.FULL);
  });
});

describe("isExpired", () => {
  it("returns false for entries without expiration", () => {
    const entry = CacheEntrySchema.parse({
      value: "test",
      namespace: "public",
      policy: {},
      createdAt: 1000,
      expiresAt: null,
    });
    expect(isExpired(entry)).toBe(false);
  });

  it("returns false for entries that have not expired", () => {
    const futureTime = Date.now() / 1000 + 3600;
    const entry = CacheEntrySchema.parse({
      value: "test",
      namespace: "public",
      policy: {},
      createdAt: 1000,
      expiresAt: futureTime,
    });
    expect(isExpired(entry)).toBe(false);
  });

  it("returns true for entries that have expired", () => {
    const pastTime = Date.now() / 1000 - 100;
    const entry = CacheEntrySchema.parse({
      value: "test",
      namespace: "public",
      policy: {},
      createdAt: 1000,
      expiresAt: pastTime,
    });
    expect(isExpired(entry)).toBe(true);
  });

  it("accepts explicit currentTime parameter", () => {
    const entry = CacheEntrySchema.parse({
      value: "test",
      namespace: "public",
      policy: {},
      createdAt: 1000,
      expiresAt: 2000,
    });
    expect(isExpired(entry, 1999)).toBe(false);
    expect(isExpired(entry, 2000)).toBe(true);
    expect(isExpired(entry, 2001)).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Tasks
// ═════════════════════════════════════════════════════════════════════

describe("TaskProgressSchema", () => {
  it("parses with all fields", () => {
    const progress = TaskProgressSchema.parse({
      current: 15,
      total: 50,
      message: "Processing item 15/50",
      percentage: 30,
    });
    expect(progress.current).toBe(15);
    expect(progress.total).toBe(50);
    expect(progress.message).toBe("Processing item 15/50");
    expect(progress.percentage).toBe(30);
  });

  it("applies defaults for optional fields", () => {
    const progress = TaskProgressSchema.parse({});
    expect(progress.current).toBeNull();
    expect(progress.total).toBeNull();
    expect(progress.message).toBeNull();
    expect(progress.percentage).toBeNull();
  });

  it("auto-calculates percentage from current and total", () => {
    const progress = TaskProgressSchema.parse({
      current: 25,
      total: 100,
    });
    expect(progress.percentage).toBe(25);
  });

  it("auto-calculates percentage with non-trivial ratio", () => {
    const progress = TaskProgressSchema.parse({
      current: 1,
      total: 3,
    });
    expect(progress.percentage).toBeCloseTo(33.333, 2);
  });

  it("does not auto-calculate if percentage is already set", () => {
    const progress = TaskProgressSchema.parse({
      current: 25,
      total: 100,
      percentage: 50, // Explicit override
    });
    expect(progress.percentage).toBe(50);
  });

  it("does not auto-calculate if total is zero", () => {
    const progress = TaskProgressSchema.parse({
      current: 0,
      total: 0,
    });
    expect(progress.percentage).toBeNull();
  });

  it("does not auto-calculate if current is null", () => {
    const progress = TaskProgressSchema.parse({
      total: 100,
    });
    expect(progress.percentage).toBeNull();
  });

  it("does not auto-calculate if total is null", () => {
    const progress = TaskProgressSchema.parse({
      current: 50,
    });
    expect(progress.percentage).toBeNull();
  });

  it("rejects negative current", () => {
    expect(() => TaskProgressSchema.parse({ current: -1 })).toThrow();
  });

  it("rejects percentage out of range", () => {
    expect(() => TaskProgressSchema.parse({ percentage: 101 })).toThrow();
    expect(() => TaskProgressSchema.parse({ percentage: -1 })).toThrow();
  });
});

describe("RetryInfoSchema", () => {
  it("parses a valid retry", () => {
    const retry = RetryInfoSchema.parse({
      attempt: 1,
      error: "Connection timeout",
      timestamp: 1700000000,
    });
    expect(retry.attempt).toBe(1);
    expect(retry.error).toBe("Connection timeout");
    expect(retry.timestamp).toBe(1700000000);
  });

  it("rejects attempt < 1", () => {
    expect(() =>
      RetryInfoSchema.parse({ attempt: 0, error: "fail", timestamp: 0 }),
    ).toThrow();
  });
});

describe("ExpectedSchemaSchema", () => {
  it("parses with all defaults", () => {
    const schema = ExpectedSchemaSchema.parse({});
    expect(schema.returnType).toBeNull();
    expect(schema.fields).toBeNull();
    expect(schema.example).toBeNull();
    expect(schema.description).toBeNull();
  });

  it("parses with all fields", () => {
    const schema = ExpectedSchemaSchema.parse({
      returnType: "Record<string, number>",
      fields: { name: "string", count: "number" },
      example: { name: "test", count: 42 },
      description: "A mapping of names to counts",
    });
    expect(schema.returnType).toBe("Record<string, number>");
    expect(schema.fields).toEqual({ name: "string", count: "number" });
  });
});

describe("TaskInfoSchema", () => {
  it("parses with minimal fields", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "default:abc123",
      startedAt: 1700000000,
    });
    expect(taskInfo.refId).toBe("default:abc123");
    expect(taskInfo.status).toBe("pending");
    expect(taskInfo.progress).toBeNull();
    expect(taskInfo.completedAt).toBeNull();
    expect(taskInfo.error).toBeNull();
    expect(taskInfo.retryCount).toBe(0);
    expect(taskInfo.maxRetries).toBe(3);
    expect(taskInfo.retryHistory).toEqual([]);
  });

  it("parses with all fields", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "default:abc123",
      status: "processing",
      progress: { current: 10, total: 100 },
      startedAt: 1700000000,
      completedAt: null,
      error: null,
      retryCount: 1,
      maxRetries: 5,
      retryHistory: [
        { attempt: 1, error: "Timeout", timestamp: 1700000010 },
      ],
    });
    expect(taskInfo.status).toBe("processing");
    expect(taskInfo.progress?.current).toBe(10);
    expect(taskInfo.progress?.percentage).toBe(10); // Auto-calculated
    expect(taskInfo.retryHistory).toHaveLength(1);
  });
});

describe("canRetry", () => {
  it("returns true for failed tasks with retries remaining", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "failed",
      startedAt: 1000,
      retryCount: 1,
      maxRetries: 3,
    });
    expect(canRetry(taskInfo)).toBe(true);
  });

  it("returns false for failed tasks with exhausted retries", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "failed",
      startedAt: 1000,
      retryCount: 3,
      maxRetries: 3,
    });
    expect(canRetry(taskInfo)).toBe(false);
  });

  it("returns false for non-failed tasks", () => {
    for (const status of ["pending", "processing", "complete", "cancelled"] as const) {
      const taskInfo = TaskInfoSchema.parse({
        refId: "test:abc",
        status,
        startedAt: 1000,
        retryCount: 0,
      });
      expect(canRetry(taskInfo)).toBe(false);
    }
  });
});

describe("isTerminal", () => {
  it("returns true for complete tasks", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "complete",
      startedAt: 1000,
    });
    expect(isTerminal(taskInfo)).toBe(true);
  });

  it("returns true for cancelled tasks", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "cancelled",
      startedAt: 1000,
    });
    expect(isTerminal(taskInfo)).toBe(true);
  });

  it("returns true for failed tasks with exhausted retries", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "failed",
      startedAt: 1000,
      retryCount: 3,
      maxRetries: 3,
    });
    expect(isTerminal(taskInfo)).toBe(true);
  });

  it("returns false for failed tasks with retries remaining", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "failed",
      startedAt: 1000,
      retryCount: 1,
      maxRetries: 3,
    });
    expect(isTerminal(taskInfo)).toBe(false);
  });

  it("returns false for pending and processing tasks", () => {
    for (const status of ["pending", "processing"] as const) {
      const taskInfo = TaskInfoSchema.parse({
        refId: "test:abc",
        status,
        startedAt: 1000,
      });
      expect(isTerminal(taskInfo)).toBe(false);
    }
  });
});

describe("elapsedSeconds", () => {
  it("calculates elapsed time for running task", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "processing",
      startedAt: 1000,
    });
    const elapsed = elapsedSeconds(taskInfo, 1045);
    expect(elapsed).toBe(45);
  });

  it("calculates elapsed time for completed task", () => {
    const taskInfo = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "complete",
      startedAt: 1000,
      completedAt: 1030,
    });
    // Should use completedAt, not currentTime
    const elapsed = elapsedSeconds(taskInfo, 9999);
    expect(elapsed).toBe(30);
  });
});

describe("AsyncTaskResponseSchema", () => {
  it("parses a minimal response", () => {
    const response = AsyncTaskResponseSchema.parse({
      refId: "default:abc123",
      status: "processing",
      startedAt: "2025-01-15T12:00:00Z",
    });
    expect(response.refId).toBe("default:abc123");
    expect(response.status).toBe("processing");
    expect(response.progress).toBeNull();
    expect(response.etaSeconds).toBeNull();
    expect(response.error).toBeNull();
    expect(response.retryCount).toBe(0);
    expect(response.canRetry).toBe(true);
    expect(response.message).toBeNull();
    expect(response.expectedSchema).toBeNull();
  });

  it("parses a full response", () => {
    const response = AsyncTaskResponseSchema.parse({
      refId: "default:abc123",
      status: "processing",
      progress: { current: 15, total: 50 },
      startedAt: "2025-01-15T12:00:00Z",
      etaSeconds: 45.0,
      error: null,
      retryCount: 0,
      canRetry: true,
      message: "Processing item 15/50",
      expectedSchema: {
        returnType: "object",
        description: "Analysis result",
      },
    });
    expect(response.progress?.current).toBe(15);
    expect(response.progress?.percentage).toBe(30); // Auto-calculated
    expect(response.etaSeconds).toBe(45.0);
    expect(response.message).toBe("Processing item 15/50");
    expect(response.expectedSchema?.returnType).toBe("object");
  });
});

describe("asyncTaskResponseFromInfo", () => {
  const baseTaskInfo = TaskInfoSchema.parse({
    refId: "default:abc123",
    status: "processing",
    startedAt: 1705312800, // 2024-01-15T12:00:00Z (approx)
    progress: { current: 10, total: 100, message: "Working on it" },
  });

  it("creates minimal format response", () => {
    const response = asyncTaskResponseFromInfo(baseTaskInfo, {
      responseFormat: "minimal",
    });
    expect(response.refId).toBe("default:abc123");
    expect(response.status).toBe("processing");
    expect(response.startedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    // Minimal format: progress, etaSeconds, message should have defaults
    expect(response.progress).toBeNull();
    expect(response.etaSeconds).toBeNull();
    expect(response.message).toBeNull();
  });

  it("creates standard format response", () => {
    const response = asyncTaskResponseFromInfo(baseTaskInfo, {
      etaSeconds: 90,
      responseFormat: "standard",
    });
    expect(response.refId).toBe("default:abc123");
    expect(response.progress?.current).toBe(10);
    expect(response.etaSeconds).toBe(90);
    expect(response.message).toBe("Working on it"); // From progress.message
    expect(response.expectedSchema).toBeNull(); // Not in standard
  });

  it("creates full format response", () => {
    const response = asyncTaskResponseFromInfo(baseTaskInfo, {
      etaSeconds: 90,
      expectedSchema: {
        returnType: "object",
        description: "Result object",
      },
      responseFormat: "full",
    });
    expect(response.expectedSchema?.returnType).toBe("object");
    expect(response.etaSeconds).toBe(90);
  });

  it("generates default messages by status", () => {
    const pendingTask = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "pending",
      startedAt: 1000,
    });
    const response = asyncTaskResponseFromInfo(pendingTask);
    expect(response.message).toBe("Task is queued and will start shortly");

    const failedTask = TaskInfoSchema.parse({
      refId: "test:abc",
      status: "failed",
      startedAt: 1000,
      error: "Connection refused",
    });
    const failedResponse = asyncTaskResponseFromInfo(failedTask);
    expect(failedResponse.message).toBe("Task failed: Connection refused");
  });

  it("uses custom message when provided", () => {
    const response = asyncTaskResponseFromInfo(baseTaskInfo, {
      message: "Custom status message",
    });
    expect(response.message).toBe("Custom status message");
  });

  it("defaults to standard format", () => {
    const response = asyncTaskResponseFromInfo(baseTaskInfo);
    // Standard includes progress and message
    expect(response.progress).not.toBeNull();
    expect(response.message).not.toBeNull();
  });
});

describe("asyncTaskResponseToDict", () => {
  const response = AsyncTaskResponseSchema.parse({
    refId: "test:abc",
    status: "processing",
    startedAt: "2025-01-15T12:00:00Z",
    progress: { current: 5, total: 10 },
    etaSeconds: 30,
    error: null,
    retryCount: 1,
    canRetry: true,
    message: "Halfway there",
    expectedSchema: { returnType: "object" },
  });

  it("returns minimal dict", () => {
    const dict = asyncTaskResponseToDict(response, "minimal");
    expect(dict.ref_id).toBe("test:abc");
    expect(dict.status).toBe("processing");
    expect(dict.is_complete).toBe(false);
    expect(dict.is_async).toBe(true);
    // Minimal should NOT include these
    expect(dict.started_at).toBeUndefined();
    expect(dict.progress).toBeUndefined();
    expect(dict.eta_seconds).toBeUndefined();
  });

  it("returns standard dict", () => {
    const dict = asyncTaskResponseToDict(response, "standard");
    expect(dict.ref_id).toBe("test:abc");
    expect(dict.is_async).toBe(true);
    expect(dict.started_at).toBe("2025-01-15T12:00:00Z");
    expect(dict.progress).not.toBeNull();
    expect(dict.message).toBe("Halfway there");
    // Standard should NOT include these
    expect(dict.eta_seconds).toBeUndefined();
    expect(dict.expected_schema).toBeUndefined();
  });

  it("returns full dict", () => {
    const dict = asyncTaskResponseToDict(response, "full");
    expect(dict.ref_id).toBe("test:abc");
    expect(dict.started_at).toBe("2025-01-15T12:00:00Z");
    expect(dict.eta_seconds).toBe(30);
    expect(dict.error).toBeNull();
    expect(dict.retry_count).toBe(1);
    expect(dict.can_retry).toBe(true);
    expect(dict.expected_schema).not.toBeNull();
  });

  it("uses snake_case keys matching Python convention", () => {
    const dict = asyncTaskResponseToDict(response, "full");
    // Verify snake_case (not camelCase) for Python interop
    expect("ref_id" in dict).toBe(true);
    expect("is_complete" in dict).toBe(true);
    expect("is_async" in dict).toBe(true);
    expect("started_at" in dict).toBe(true);
    expect("eta_seconds" in dict).toBe(true);
    expect("retry_count" in dict).toBe(true);
    expect("can_retry" in dict).toBe(true);
    expect("expected_schema" in dict).toBe(true);
  });

  it("defaults to standard format", () => {
    const dict = asyncTaskResponseToDict(response);
    expect(dict.started_at).toBeDefined();
    expect(dict.eta_seconds).toBeUndefined();
  });
});
