/**
 * Tests for access control system: actors, namespaces, and permission checking.
 *
 * Tests the Actor interface, DefaultActor, NamespaceResolver,
 * DefaultNamespaceResolver, PermissionChecker, DefaultPermissionChecker,
 * PermissionDenied error, and integration scenarios.
 *
 * Ports from Python:
 * - `tests/test_access_actor.py`
 * - `tests/test_access_namespace.py`
 * - `tests/test_access_checker.py`
 *
 * @module
 */

import { describe, expect, it } from "bun:test";

import {
  type Actor,
  type ActorLike,
  DefaultActor,
  resolveActor,
  type NamespaceResolver,
  DefaultNamespaceResolver,
  NamespaceInfo,
  type PermissionChecker,
  DefaultPermissionChecker,
  PermissionDenied,
  permissionNames,
  ActorType,
  Permission,
  AccessPolicySchema,
  hasPermission,
} from "../src/index.js";

import type { AccessPolicy } from "../src/index.js";

// ═════════════════════════════════════════════════════════════════════
// ActorType Tests
// ═════════════════════════════════════════════════════════════════════

describe("ActorType", () => {
  it("has expected string values", () => {
    expect(ActorType.USER).toBe("user");
    expect(ActorType.AGENT).toBe("agent");
    expect(ActorType.SYSTEM).toBe("system");
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultActor Creation Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultActor creation", () => {
  it("user factory creates anonymous user actor", () => {
    const actor = DefaultActor.user();
    expect(actor.type).toBe(ActorType.USER);
    expect(actor.actorId).toBeNull();
    expect(actor.sessionId).toBeNull();
  });

  it("user factory accepts actorId", () => {
    const actor = DefaultActor.user({ actorId: "alice" });
    expect(actor.type).toBe(ActorType.USER);
    expect(actor.actorId).toBe("alice");
    expect(actor.sessionId).toBeNull();
  });

  it("user factory accepts sessionId", () => {
    const actor = DefaultActor.user({ sessionId: "sess-123" });
    expect(actor.type).toBe(ActorType.USER);
    expect(actor.actorId).toBeNull();
    expect(actor.sessionId).toBe("sess-123");
  });

  it("user factory accepts both actorId and sessionId", () => {
    const actor = DefaultActor.user({
      actorId: "alice",
      sessionId: "sess-123",
    });
    expect(actor.type).toBe(ActorType.USER);
    expect(actor.actorId).toBe("alice");
    expect(actor.sessionId).toBe("sess-123");
  });

  it("agent factory creates anonymous agent actor", () => {
    const actor = DefaultActor.agent();
    expect(actor.type).toBe(ActorType.AGENT);
    expect(actor.actorId).toBeNull();
    expect(actor.sessionId).toBeNull();
  });

  it("agent factory accepts actorId", () => {
    const actor = DefaultActor.agent({ actorId: "claude-instance-1" });
    expect(actor.type).toBe(ActorType.AGENT);
    expect(actor.actorId).toBe("claude-instance-1");
    expect(actor.sessionId).toBeNull();
  });

  it("agent factory accepts sessionId", () => {
    const actor = DefaultActor.agent({ sessionId: "sess-456" });
    expect(actor.type).toBe(ActorType.AGENT);
    expect(actor.actorId).toBeNull();
    expect(actor.sessionId).toBe("sess-456");
  });

  it("system factory creates system actor with internal id", () => {
    const actor = DefaultActor.system();
    expect(actor.type).toBe(ActorType.SYSTEM);
    expect(actor.actorId).toBe("internal");
    expect(actor.sessionId).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultActor Protocol Compliance Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultActor protocol compliance", () => {
  it("satisfies Actor interface", () => {
    const actor: Actor = DefaultActor.user();
    expect(actor.type).toBe(ActorType.USER);
    expect(actor.matches).toBeFunction();
    expect(actor.toString).toBeFunction();
  });

  it("has type property", () => {
    const actor = DefaultActor.user();
    expect(actor.type).toBe(ActorType.USER);
  });

  it("has actorId property", () => {
    const actor = DefaultActor.user({ actorId: "test" });
    expect(actor.actorId).toBe("test");
  });

  it("has sessionId property", () => {
    const actor = DefaultActor.user({ sessionId: "sess-test" });
    expect(actor.sessionId).toBe("sess-test");
  });

  it("has matches method", () => {
    const actor = DefaultActor.user();
    expect(actor.matches).toBeFunction();
  });

  it("has toString method", () => {
    const actor = DefaultActor.user();
    expect(actor.toString).toBeFunction();
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultActor Pattern Matching Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultActor pattern matching", () => {
  it("matches exact user pattern", () => {
    const actor = DefaultActor.user({ actorId: "alice" });
    expect(actor.matches("user:alice")).toBe(true);
    expect(actor.matches("user:bob")).toBe(false);
  });

  it("matches exact agent pattern", () => {
    const actor = DefaultActor.agent({ actorId: "claude-1" });
    expect(actor.matches("agent:claude-1")).toBe(true);
    expect(actor.matches("agent:claude-2")).toBe(false);
  });

  it("matches wildcard pattern", () => {
    const user = DefaultActor.user({ actorId: "alice" });
    const agent = DefaultActor.agent({ actorId: "claude-1" });

    expect(user.matches("user:*")).toBe(true);
    expect(user.matches("agent:*")).toBe(false);
    expect(agent.matches("agent:*")).toBe(true);
    expect(agent.matches("user:*")).toBe(false);
  });

  it("matches wildcard for anonymous actor", () => {
    const actor = DefaultActor.user();
    expect(actor.matches("user:*")).toBe(true);
    expect(actor.matches("agent:*")).toBe(false);
  });

  it("anonymous actor does not match specific pattern", () => {
    const actor = DefaultActor.user();
    expect(actor.matches("user:alice")).toBe(false);
    expect(actor.matches("user:*")).toBe(true);
  });

  it("type must match", () => {
    const user = DefaultActor.user({ actorId: "alice" });
    const agent = DefaultActor.agent({ actorId: "alice" });

    expect(user.matches("user:alice")).toBe(true);
    expect(user.matches("agent:alice")).toBe(false);
    expect(agent.matches("agent:alice")).toBe(true);
    expect(agent.matches("user:alice")).toBe(false);
  });

  it("supports glob patterns", () => {
    const actor = DefaultActor.user({ actorId: "alice-admin" });

    expect(actor.matches("user:alice-*")).toBe(true);
    expect(actor.matches("user:*-admin")).toBe(true);
    expect(actor.matches("user:alice-???in")).toBe(true);
    expect(actor.matches("user:bob-*")).toBe(false);
  });

  it("returns false for patterns without colon", () => {
    const actor = DefaultActor.user({ actorId: "alice" });
    expect(actor.matches("useralice")).toBe(false);
    expect(actor.matches("alice")).toBe(false);
    expect(actor.matches("")).toBe(false);
  });

  it("system actor matches system patterns", () => {
    const actor = DefaultActor.system();
    expect(actor.matches("system:internal")).toBe(true);
    expect(actor.matches("system:*")).toBe(true);
    expect(actor.matches("user:internal")).toBe(false);
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultActor String Representation Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultActor string representation", () => {
  it("toString returns type:id for identified user", () => {
    const actor = DefaultActor.user({ actorId: "alice" });
    expect(actor.toString()).toBe("user:alice");
  });

  it("toString returns type:* for anonymous user", () => {
    const actor = DefaultActor.user();
    expect(actor.toString()).toBe("user:*");
  });

  it("toString works for identified agent", () => {
    const actor = DefaultActor.agent({ actorId: "claude-1" });
    expect(actor.toString()).toBe("agent:claude-1");
  });

  it("toString returns agent:* for anonymous agent", () => {
    const actor = DefaultActor.agent();
    expect(actor.toString()).toBe("agent:*");
  });

  it("toString works for system actor", () => {
    const actor = DefaultActor.system();
    expect(actor.toString()).toBe("system:internal");
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultActor fromLiteral Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultActor fromLiteral", () => {
  it("fromLiteral user creates anonymous user", () => {
    const actor = DefaultActor.fromLiteral("user");
    expect(actor.type).toBe(ActorType.USER);
    expect(actor.actorId).toBeNull();
    expect(actor.sessionId).toBeNull();
  });

  it("fromLiteral agent creates anonymous agent", () => {
    const actor = DefaultActor.fromLiteral("agent");
    expect(actor.type).toBe(ActorType.AGENT);
    expect(actor.actorId).toBeNull();
    expect(actor.sessionId).toBeNull();
  });

  it("fromLiteral with sessionId", () => {
    const actor = DefaultActor.fromLiteral("user", "sess-123");
    expect(actor.type).toBe(ActorType.USER);
    expect(actor.actorId).toBeNull();
    expect(actor.sessionId).toBe("sess-123");
  });
});

// ═════════════════════════════════════════════════════════════════════
// resolveActor Tests
// ═════════════════════════════════════════════════════════════════════

describe("resolveActor", () => {
  it("passes through Actor instances", () => {
    const original = DefaultActor.user({ actorId: "alice" });
    const resolved = resolveActor(original);
    expect(resolved).toBe(original);
  });

  it("converts user literal", () => {
    const resolved = resolveActor("user");
    expect(resolved.type).toBe(ActorType.USER);
    expect(resolved.actorId).toBeNull();
  });

  it("converts agent literal", () => {
    const resolved = resolveActor("agent");
    expect(resolved.type).toBe(ActorType.AGENT);
    expect(resolved.actorId).toBeNull();
  });

  it("attaches sessionId to literal actors", () => {
    const resolved = resolveActor("user", "sess-123");
    expect(resolved.type).toBe(ActorType.USER);
    expect(resolved.sessionId).toBe("sess-123");
  });

  it("ignores sessionId for Actor objects", () => {
    const original = DefaultActor.user({
      actorId: "alice",
      sessionId: "original",
    });
    const resolved = resolveActor(original, "different");
    expect(resolved.sessionId).toBe("original");
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultActor Immutability Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultActor immutability", () => {
  it("is frozen (immutable)", () => {
    const actor = DefaultActor.user({ actorId: "alice" });
    expect(Object.isFrozen(actor)).toBe(true);
  });

  it("cannot be modified", () => {
    const actor = DefaultActor.user({ actorId: "alice" });
    expect(() => {
      (actor as Record<string, unknown>).actorId = "bob";
    }).toThrow();
  });
});

// ═════════════════════════════════════════════════════════════════════
// ActorLike Type Tests
// ═════════════════════════════════════════════════════════════════════

describe("ActorLike type", () => {
  it("accepts Actor instances", () => {
    const actor: ActorLike = DefaultActor.user({ actorId: "alice" });
    expect(typeof actor).toBe("object");
  });

  it("accepts literal user", () => {
    const actor: ActorLike = "user";
    expect(actor).toBe("user");
  });

  it("accepts literal agent", () => {
    const actor: ActorLike = "agent";
    expect(actor).toBe("agent");
  });
});

// ═════════════════════════════════════════════════════════════════════
// NamespaceInfo Tests
// ═════════════════════════════════════════════════════════════════════

describe("NamespaceInfo", () => {
  it("creates with required fields", () => {
    const info = new NamespaceInfo({ raw: "public", prefix: "public" });
    expect(info.raw).toBe("public");
    expect(info.prefix).toBe("public");
    expect(info.identifier).toBeNull();
    expect(info.isPublic).toBe(false);
    expect(info.isSessionScoped).toBe(false);
    expect(info.isUserScoped).toBe(false);
    expect(info.isAgentScoped).toBe(false);
    expect(info.impliedOwner).toBeNull();
  });

  it("creates with all fields", () => {
    const info = new NamespaceInfo({
      raw: "user:alice",
      prefix: "user",
      identifier: "alice",
      isPublic: false,
      isSessionScoped: false,
      isUserScoped: true,
      isAgentScoped: false,
      impliedOwner: "user:alice",
    });
    expect(info.raw).toBe("user:alice");
    expect(info.prefix).toBe("user");
    expect(info.identifier).toBe("alice");
    expect(info.isUserScoped).toBe(true);
    expect(info.impliedOwner).toBe("user:alice");
  });

  it("has toString representation", () => {
    const info = new NamespaceInfo({
      raw: "session:abc",
      prefix: "session",
      identifier: "abc",
    });
    const representation = info.toString();
    expect(representation).toContain("NamespaceInfo");
    expect(representation).toContain("session:abc");
    expect(representation).toContain("session");
    expect(representation).toContain("abc");
  });

  it("equals compares by raw value", () => {
    const info1 = new NamespaceInfo({ raw: "public", prefix: "public" });
    const info2 = new NamespaceInfo({ raw: "public", prefix: "public" });
    const info3 = new NamespaceInfo({ raw: "private", prefix: "private" });

    expect(info1.equals(info2)).toBe(true);
    expect(info1.equals(info3)).toBe(false);
  });

  it("equals returns false for non-NamespaceInfo", () => {
    const info = new NamespaceInfo({ raw: "public", prefix: "public" });
    expect(info.equals("public")).toBe(false);
    expect(info.equals(42)).toBe(false);
  });

  it("is frozen (immutable)", () => {
    const info = new NamespaceInfo({ raw: "public", prefix: "public" });
    expect(Object.isFrozen(info)).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultNamespaceResolver.parse() Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultNamespaceResolver parse", () => {
  const resolver = new DefaultNamespaceResolver();

  it("parses public namespace", () => {
    const info = resolver.parse("public");
    expect(info.raw).toBe("public");
    expect(info.prefix).toBe("public");
    expect(info.identifier).toBeNull();
    expect(info.isPublic).toBe(true);
    expect(info.isSessionScoped).toBe(false);
    expect(info.isUserScoped).toBe(false);
    expect(info.isAgentScoped).toBe(false);
    expect(info.impliedOwner).toBeNull();
  });

  it("parses session namespace", () => {
    const info = resolver.parse("session:abc123");
    expect(info.raw).toBe("session:abc123");
    expect(info.prefix).toBe("session");
    expect(info.identifier).toBe("abc123");
    expect(info.isPublic).toBe(false);
    expect(info.isSessionScoped).toBe(true);
    expect(info.isUserScoped).toBe(false);
    expect(info.isAgentScoped).toBe(false);
    expect(info.impliedOwner).toBeNull();
  });

  it("parses user namespace", () => {
    const info = resolver.parse("user:alice");
    expect(info.raw).toBe("user:alice");
    expect(info.prefix).toBe("user");
    expect(info.identifier).toBe("alice");
    expect(info.isPublic).toBe(false);
    expect(info.isSessionScoped).toBe(false);
    expect(info.isUserScoped).toBe(true);
    expect(info.isAgentScoped).toBe(false);
    expect(info.impliedOwner).toBe("user:alice");
  });

  it("parses agent namespace", () => {
    const info = resolver.parse("agent:claude-1");
    expect(info.raw).toBe("agent:claude-1");
    expect(info.prefix).toBe("agent");
    expect(info.identifier).toBe("claude-1");
    expect(info.isPublic).toBe(false);
    expect(info.isSessionScoped).toBe(false);
    expect(info.isUserScoped).toBe(false);
    expect(info.isAgentScoped).toBe(true);
    expect(info.impliedOwner).toBe("agent:claude-1");
  });

  it("parses shared namespace", () => {
    const info = resolver.parse("shared:team-alpha");
    expect(info.raw).toBe("shared:team-alpha");
    expect(info.prefix).toBe("shared");
    expect(info.identifier).toBe("team-alpha");
    expect(info.isPublic).toBe(false);
    expect(info.isSessionScoped).toBe(false);
    expect(info.isUserScoped).toBe(false);
    expect(info.isAgentScoped).toBe(false);
    expect(info.impliedOwner).toBeNull();
  });

  it("parses custom namespace without colon", () => {
    const info = resolver.parse("custom");
    expect(info.raw).toBe("custom");
    expect(info.prefix).toBe("custom");
    expect(info.identifier).toBeNull();
    expect(info.isPublic).toBe(false);
    expect(info.isSessionScoped).toBe(false);
    expect(info.isUserScoped).toBe(false);
    expect(info.isAgentScoped).toBe(false);
  });

  it("parses custom namespace with colon", () => {
    const info = resolver.parse("custom:my-namespace");
    expect(info.raw).toBe("custom:my-namespace");
    expect(info.prefix).toBe("custom");
    expect(info.identifier).toBe("my-namespace");
    expect(info.isPublic).toBe(false);
  });

  it("parses namespace with multiple colons (splits on first)", () => {
    const info = resolver.parse("user:alice:extra:stuff");
    expect(info.raw).toBe("user:alice:extra:stuff");
    expect(info.prefix).toBe("user");
    expect(info.identifier).toBe("alice:extra:stuff");
    expect(info.isUserScoped).toBe(true);
    expect(info.impliedOwner).toBe("user:alice:extra:stuff");
  });

  it("parses empty identifier after colon", () => {
    const info = resolver.parse("session:");
    expect(info.raw).toBe("session:");
    expect(info.prefix).toBe("session");
    expect(info.identifier).toBe("");
    expect(info.isSessionScoped).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultNamespaceResolver.validateAccess() Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultNamespaceResolver validateAccess", () => {
  const resolver = new DefaultNamespaceResolver();

  it("public allows all actors", () => {
    expect(resolver.validateAccess("public", DefaultActor.user())).toBe(true);
    expect(
      resolver.validateAccess(
        "public",
        DefaultActor.user({ actorId: "alice" }),
      ),
    ).toBe(true);
    expect(resolver.validateAccess("public", DefaultActor.agent())).toBe(true);
    expect(
      resolver.validateAccess(
        "public",
        DefaultActor.agent({ actorId: "claude-1" }),
      ),
    ).toBe(true);
  });

  it("session namespace requires matching sessionId", () => {
    const actor = DefaultActor.user({ sessionId: "sess-123" });
    expect(resolver.validateAccess("session:sess-123", actor)).toBe(true);

    const actorWrong = DefaultActor.user({ sessionId: "sess-456" });
    expect(resolver.validateAccess("session:sess-123", actorWrong)).toBe(false);

    const actorNoSession = DefaultActor.user();
    expect(resolver.validateAccess("session:sess-123", actorNoSession)).toBe(
      false,
    );
  });

  it("session namespace works for agents too", () => {
    const agent = DefaultActor.agent({ sessionId: "sess-123" });
    expect(resolver.validateAccess("session:sess-123", agent)).toBe(true);

    const agentWrong = DefaultActor.agent({ sessionId: "sess-456" });
    expect(resolver.validateAccess("session:sess-123", agentWrong)).toBe(false);
  });

  it("user namespace requires matching user id", () => {
    const alice = DefaultActor.user({ actorId: "alice" });
    expect(resolver.validateAccess("user:alice", alice)).toBe(true);

    const bob = DefaultActor.user({ actorId: "bob" });
    expect(resolver.validateAccess("user:alice", bob)).toBe(false);

    const anonymous = DefaultActor.user();
    expect(resolver.validateAccess("user:alice", anonymous)).toBe(false);
  });

  it("user namespace rejects agents", () => {
    const agent = DefaultActor.agent({ actorId: "alice" });
    expect(resolver.validateAccess("user:alice", agent)).toBe(false);
  });

  it("agent namespace requires matching agent id", () => {
    const claude = DefaultActor.agent({ actorId: "claude-1" });
    expect(resolver.validateAccess("agent:claude-1", claude)).toBe(true);

    const other = DefaultActor.agent({ actorId: "other-agent" });
    expect(resolver.validateAccess("agent:claude-1", other)).toBe(false);

    const anonymous = DefaultActor.agent();
    expect(resolver.validateAccess("agent:claude-1", anonymous)).toBe(false);
  });

  it("agent namespace rejects users", () => {
    const user = DefaultActor.user({ actorId: "claude-1" });
    expect(resolver.validateAccess("agent:claude-1", user)).toBe(false);
  });

  it("shared namespace allows all", () => {
    expect(
      resolver.validateAccess("shared:team-alpha", DefaultActor.user()),
    ).toBe(true);
    expect(
      resolver.validateAccess("shared:team-alpha", DefaultActor.agent()),
    ).toBe(true);
    expect(
      resolver.validateAccess(
        "shared:team-alpha",
        DefaultActor.user({ actorId: "alice" }),
      ),
    ).toBe(true);
  });

  it("custom namespace allows all", () => {
    expect(resolver.validateAccess("custom", DefaultActor.user())).toBe(true);
    expect(
      resolver.validateAccess("custom:value", DefaultActor.agent()),
    ).toBe(true);
    expect(
      resolver.validateAccess(
        "myapp:data",
        DefaultActor.user({ actorId: "alice" }),
      ),
    ).toBe(true);
  });

  it("system actor bypasses all namespace restrictions", () => {
    const system = DefaultActor.system();

    expect(resolver.validateAccess("session:abc123", system)).toBe(true);
    expect(resolver.validateAccess("user:alice", system)).toBe(true);
    expect(resolver.validateAccess("agent:claude-1", system)).toBe(true);
    expect(resolver.validateAccess("public", system)).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultNamespaceResolver.getOwner() Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultNamespaceResolver getOwner", () => {
  const resolver = new DefaultNamespaceResolver();

  it("public returns null", () => {
    expect(resolver.getOwner("public")).toBeNull();
  });

  it("session returns null", () => {
    expect(resolver.getOwner("session:abc123")).toBeNull();
  });

  it("user namespace returns user:<id>", () => {
    expect(resolver.getOwner("user:alice")).toBe("user:alice");
    expect(resolver.getOwner("user:bob")).toBe("user:bob");
  });

  it("agent namespace returns agent:<id>", () => {
    expect(resolver.getOwner("agent:claude-1")).toBe("agent:claude-1");
    expect(resolver.getOwner("agent:gpt-4")).toBe("agent:gpt-4");
  });

  it("shared returns null", () => {
    expect(resolver.getOwner("shared:team-alpha")).toBeNull();
  });

  it("custom returns null", () => {
    expect(resolver.getOwner("custom")).toBeNull();
    expect(resolver.getOwner("custom:value")).toBeNull();
    expect(resolver.getOwner("myapp:data")).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultNamespaceResolver.getRequiredSession() Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultNamespaceResolver getRequiredSession", () => {
  const resolver = new DefaultNamespaceResolver();

  it("session namespace returns required session id", () => {
    expect(resolver.getRequiredSession("session:abc123")).toBe("abc123");
    expect(resolver.getRequiredSession("session:sess-456")).toBe("sess-456");
  });

  it("public has no required session", () => {
    expect(resolver.getRequiredSession("public")).toBeNull();
  });

  it("user has no required session", () => {
    expect(resolver.getRequiredSession("user:alice")).toBeNull();
  });

  it("agent has no required session", () => {
    expect(resolver.getRequiredSession("agent:claude-1")).toBeNull();
  });

  it("custom has no required session", () => {
    expect(resolver.getRequiredSession("custom")).toBeNull();
    expect(resolver.getRequiredSession("custom:value")).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════
// NamespaceResolver Protocol Compliance Tests
// ═════════════════════════════════════════════════════════════════════

describe("NamespaceResolver protocol compliance", () => {
  it("DefaultNamespaceResolver satisfies NamespaceResolver interface", () => {
    const resolver: NamespaceResolver = new DefaultNamespaceResolver();
    expect(resolver.validateAccess).toBeFunction();
    expect(resolver.getOwner).toBeFunction();
    expect(resolver.getRequiredSession).toBeFunction();
    expect(resolver.parse).toBeFunction();
  });
});

// ═════════════════════════════════════════════════════════════════════
// Namespace Edge Cases Tests
// ═════════════════════════════════════════════════════════════════════

describe("Namespace edge cases", () => {
  const resolver = new DefaultNamespaceResolver();

  it("empty namespace treated as custom", () => {
    const info = resolver.parse("");
    expect(info.raw).toBe("");
    expect(info.prefix).toBe("");
    expect(info.identifier).toBeNull();
    expect(info.isPublic).toBe(false);

    // Empty namespace allows access (custom namespace)
    expect(resolver.validateAccess("", DefaultActor.user())).toBe(true);
  });

  it("namespace prefixes are case-sensitive", () => {
    const infoUpper = resolver.parse("PUBLIC");
    expect(infoUpper.isPublic).toBe(false);

    const infoSession = resolver.parse("SESSION:abc");
    expect(infoSession.isSessionScoped).toBe(false);

    const infoUser = resolver.parse("USER:alice");
    expect(infoUser.isUserScoped).toBe(false);
  });

  it("namespaces can contain special characters", () => {
    const info = resolver.parse("user:alice@example.com");
    expect(info.prefix).toBe("user");
    expect(info.identifier).toBe("alice@example.com");
    expect(info.isUserScoped).toBe(true);
    expect(info.impliedOwner).toBe("user:alice@example.com");
  });

  it("namespaces work with UUID identifiers", () => {
    const uuid = "550e8400-e29b-41d4-a716-446655440000";
    const info = resolver.parse(`session:${uuid}`);
    expect(info.prefix).toBe("session");
    expect(info.identifier).toBe(uuid);
    expect(info.isSessionScoped).toBe(true);

    const actor = DefaultActor.user({ sessionId: uuid });
    expect(resolver.validateAccess(`session:${uuid}`, actor)).toBe(true);
  });

  it("namespaces work with path-like identifiers", () => {
    const info = resolver.parse("custom:org/repo/branch");
    expect(info.prefix).toBe("custom");
    expect(info.identifier).toBe("org/repo/branch");
  });
});

// ═════════════════════════════════════════════════════════════════════
// permissionNames Tests
// ═════════════════════════════════════════════════════════════════════

describe("permissionNames", () => {
  it("returns empty array for NONE", () => {
    expect(permissionNames(Permission.NONE)).toEqual([]);
  });

  it("returns single name for single permission", () => {
    expect(permissionNames(Permission.READ)).toEqual(["READ"]);
    expect(permissionNames(Permission.WRITE)).toEqual(["WRITE"]);
    expect(permissionNames(Permission.EXECUTE)).toEqual(["EXECUTE"]);
  });

  it("returns multiple names for combined permissions", () => {
    const names = permissionNames(Permission.READ | Permission.WRITE);
    expect(names).toContain("READ");
    expect(names).toContain("WRITE");
    expect(names).toHaveLength(2);
  });

  it("returns all names for FULL", () => {
    const names = permissionNames(Permission.FULL);
    expect(names).toContain("READ");
    expect(names).toContain("WRITE");
    expect(names).toContain("UPDATE");
    expect(names).toContain("DELETE");
    expect(names).toContain("EXECUTE");
    expect(names).toHaveLength(5);
  });
});

// ═════════════════════════════════════════════════════════════════════
// PermissionDenied Tests
// ═════════════════════════════════════════════════════════════════════

describe("PermissionDenied", () => {
  it("creates with just a message", () => {
    const error = new PermissionDenied("Access denied");
    expect(error.message).toBe("Access denied");
    expect(error.actor).toBeNull();
    expect(error.required).toBeNull();
    expect(error.reason).toBeNull();
    expect(error.namespace).toBeNull();
  });

  it("stores all attributes", () => {
    const actor = DefaultActor.user({ actorId: "alice" });
    const error = new PermissionDenied("User lacks READ permission", {
      actor,
      required: Permission.READ,
      reason: "role_insufficient",
      namespace: "public",
    });

    expect(error.message).toBe("User lacks READ permission");
    expect(error.actor).toBe(actor);
    expect(error.required).toBe(Permission.READ);
    expect(error.reason).toBe("role_insufficient");
    expect(error.namespace).toBe("public");
  });

  it("is an Error", () => {
    const error = new PermissionDenied("Test");
    expect(error).toBeInstanceOf(Error);
  });

  it("has name PermissionDenied", () => {
    const error = new PermissionDenied("Test");
    expect(error.name).toBe("PermissionDenied");
  });

  it("can be caught as Error", () => {
    expect(() => {
      throw new PermissionDenied("Test");
    }).toThrow(Error);
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultPermissionChecker.check() Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultPermissionChecker check", () => {
  const checker = new DefaultPermissionChecker();

  it("allows user with permission", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
    });
    const actor = DefaultActor.user();

    // Should not throw
    checker.check(policy, Permission.READ, actor, "public");
  });

  it("denies user without permission", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.NONE,
    });
    const actor = DefaultActor.user();

    try {
      checker.check(policy, Permission.READ, actor, "public");
      expect(true).toBe(false); // Should not reach here
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("role_insufficient");
      expect((error as PermissionDenied).required).toBe(Permission.READ);
    }
  });

  it("allows agent with permission", () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.EXECUTE,
    });
    const actor = DefaultActor.agent();

    // Should not throw
    checker.check(policy, Permission.EXECUTE, actor, "public");
  });

  it("denies agent without permission", () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.READ,
    });
    const actor = DefaultActor.agent();

    try {
      checker.check(policy, Permission.DELETE, actor, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("role_insufficient");
    }
  });

  it("system actor has full permissions", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.NONE,
      agentPermissions: Permission.NONE,
    });
    const system = DefaultActor.system();

    // System can do anything
    checker.check(policy, Permission.READ, system, "public");
    checker.check(policy, Permission.WRITE, system, "public");
    checker.check(policy, Permission.DELETE, system, "public");
    checker.check(policy, Permission.EXECUTE, system, "public");
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultPermissionChecker Explicit Deny Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultPermissionChecker explicit deny", () => {
  const checker = new DefaultPermissionChecker();

  it("explicit deny blocks actor", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      deniedActors: ["user:alice"],
    });
    const alice = DefaultActor.user({ actorId: "alice" });

    try {
      checker.check(policy, Permission.READ, alice, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("explicit_deny");
    }
  });

  it("explicit deny with wildcard", () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.FULL,
      deniedActors: ["agent:*"],
    });
    const agent = DefaultActor.agent({ actorId: "claude-1" });

    try {
      checker.check(policy, Permission.READ, agent, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("explicit_deny");
    }
  });

  it("explicit deny does not affect other actors", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      deniedActors: ["user:alice"],
    });
    const bob = DefaultActor.user({ actorId: "bob" });

    // Bob is not denied
    checker.check(policy, Permission.READ, bob, "public");
  });

  it("explicit deny takes precedence over owner", () => {
    const policy = AccessPolicySchema.parse({
      owner: "user:alice",
      ownerPermissions: Permission.FULL,
      deniedActors: ["user:alice"],
    });
    const alice = DefaultActor.user({ actorId: "alice" });

    try {
      checker.check(policy, Permission.READ, alice, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("explicit_deny");
    }
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultPermissionChecker Session Binding Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultPermissionChecker session binding", () => {
  const checker = new DefaultPermissionChecker();

  it("allows matching session", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      boundSession: "sess-123",
    });
    const actor = DefaultActor.user({ sessionId: "sess-123" });

    // Should not throw
    checker.check(policy, Permission.READ, actor, "public");
  });

  it("denies non-matching session", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      boundSession: "sess-123",
    });
    const actor = DefaultActor.user({ sessionId: "sess-456" });

    try {
      checker.check(policy, Permission.READ, actor, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("session_mismatch");
    }
  });

  it("denies actor without session when binding is set", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      boundSession: "sess-123",
    });
    const actor = DefaultActor.user();

    try {
      checker.check(policy, Permission.READ, actor, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("session_mismatch");
    }
  });

  it("no session binding allows any session", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
    });

    checker.check(policy, Permission.READ, DefaultActor.user(), "public");
    checker.check(
      policy,
      Permission.READ,
      DefaultActor.user({ sessionId: "any" }),
      "public",
    );
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultPermissionChecker Namespace Ownership Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultPermissionChecker namespace ownership", () => {
  const checker = new DefaultPermissionChecker();

  it("denies non-owner for user namespace", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
    });
    const bob = DefaultActor.user({ actorId: "bob" });

    try {
      checker.check(policy, Permission.READ, bob, "user:alice");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("namespace_ownership");
    }
  });

  it("allows owner for user namespace", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
    });
    const alice = DefaultActor.user({ actorId: "alice" });

    // Should not throw
    checker.check(policy, Permission.READ, alice, "user:alice");
  });

  it("session namespace requires session match", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
    });

    const actor = DefaultActor.user({ sessionId: "wrong" });
    try {
      checker.check(policy, Permission.READ, actor, "session:correct");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("namespace_ownership");
    }
  });

  it("public namespace allows all", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      agentPermissions: Permission.READ,
    });

    checker.check(policy, Permission.READ, DefaultActor.user(), "public");
    checker.check(policy, Permission.READ, DefaultActor.agent(), "public");
  });

  it("custom namespace resolver can be injected", () => {
    const alwaysDenyResolver: NamespaceResolver = {
      validateAccess(_namespace: string, _actor: Actor): boolean {
        return false;
      },
      getOwner(_namespace: string): string | null {
        return null;
      },
      getRequiredSession(_namespace: string): string | null {
        return null;
      },
      parse(namespace: string): NamespaceInfo {
        return new NamespaceInfo({ raw: namespace, prefix: namespace });
      },
    };

    const customChecker = new DefaultPermissionChecker(alwaysDenyResolver);
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
    });

    try {
      customChecker.check(
        policy,
        Permission.READ,
        DefaultActor.user(),
        "any",
      );
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("namespace_ownership");
    }
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultPermissionChecker Explicit Allow Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultPermissionChecker explicit allow", () => {
  const checker = new DefaultPermissionChecker();

  it("explicit allow grants access despite NONE permissions", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.NONE, // Would normally deny
      allowedActors: ["user:alice"],
    });
    const alice = DefaultActor.user({ actorId: "alice" });

    // Should not throw despite NONE permissions
    checker.check(policy, Permission.READ, alice, "public");
  });

  it("explicit allow with wildcard", () => {
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.NONE,
      allowedActors: ["agent:claude-*"],
    });
    const claude = DefaultActor.agent({ actorId: "claude-instance-1" });

    // Matches wildcard pattern
    checker.check(policy, Permission.READ, claude, "public");
  });

  it("explicit allow does not bypass deny", () => {
    const policy = AccessPolicySchema.parse({
      allowedActors: ["user:alice"],
      deniedActors: ["user:alice"],
    });
    const alice = DefaultActor.user({ actorId: "alice" });

    try {
      checker.check(policy, Permission.READ, alice, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("explicit_deny");
    }
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultPermissionChecker Ownership Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultPermissionChecker ownership", () => {
  const checker = new DefaultPermissionChecker();

  it("owner gets owner permissions", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ, // Limited
      owner: "user:alice",
      ownerPermissions: Permission.FULL, // Full for owner
    });
    const alice = DefaultActor.user({ actorId: "alice" });

    // Alice can delete because she's owner
    checker.check(policy, Permission.DELETE, alice, "public");
  });

  it("owner denied if owner permissions insufficient", () => {
    const policy = AccessPolicySchema.parse({
      owner: "user:alice",
      ownerPermissions: Permission.READ, // Owner can only read
    });
    const alice = DefaultActor.user({ actorId: "alice" });

    try {
      checker.check(policy, Permission.DELETE, alice, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PermissionDenied);
      expect((error as PermissionDenied).reason).toBe("owner_insufficient");
    }
  });

  it("non-owner uses role permissions", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      owner: "user:alice",
      ownerPermissions: Permission.FULL,
    });
    const bob = DefaultActor.user({ actorId: "bob" });

    // Bob can read (role permission)
    checker.check(policy, Permission.READ, bob, "public");

    // Bob cannot delete (not owner, role only has READ)
    expect(() => {
      checker.check(policy, Permission.DELETE, bob, "public");
    }).toThrow(PermissionDenied);
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultPermissionChecker.hasPermission() Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultPermissionChecker hasPermission", () => {
  const checker = new DefaultPermissionChecker();

  it("returns true when allowed", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
    });
    const actor = DefaultActor.user();

    expect(checker.hasPermission(policy, Permission.READ, actor, "public")).toBe(
      true,
    );
  });

  it("returns false when denied", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.NONE,
    });
    const actor = DefaultActor.user();

    expect(checker.hasPermission(policy, Permission.READ, actor, "public")).toBe(
      false,
    );
  });

  it("does not throw", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.NONE,
      deniedActors: ["user:*"],
    });
    const actor = DefaultActor.user({ actorId: "alice" });

    // Should return false, not throw
    const result = checker.hasPermission(
      policy,
      Permission.READ,
      actor,
      "public",
    );
    expect(result).toBe(false);
  });
});

// ═════════════════════════════════════════════════════════════════════
// DefaultPermissionChecker.getEffectivePermissions() Tests
// ═════════════════════════════════════════════════════════════════════

describe("DefaultPermissionChecker getEffectivePermissions", () => {
  const checker = new DefaultPermissionChecker();

  it("returns user permissions for user actors", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ | Permission.WRITE,
      agentPermissions: Permission.EXECUTE,
    });
    const user = DefaultActor.user();

    const permissions = checker.getEffectivePermissions(
      policy,
      user,
      "public",
    );
    expect(permissions).toBe(Permission.READ | Permission.WRITE);
  });

  it("returns agent permissions for agent actors", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      agentPermissions: Permission.READ | Permission.EXECUTE,
    });
    const agent = DefaultActor.agent();

    const permissions = checker.getEffectivePermissions(
      policy,
      agent,
      "public",
    );
    expect(permissions).toBe(Permission.READ | Permission.EXECUTE);
  });

  it("returns FULL for system actors", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.NONE,
      agentPermissions: Permission.NONE,
    });
    const system = DefaultActor.system();

    const permissions = checker.getEffectivePermissions(
      policy,
      system,
      "public",
    );
    expect(permissions).toBe(Permission.FULL);
  });

  it("returns owner permissions when actor is owner", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      owner: "user:alice",
      ownerPermissions: Permission.CRUD,
    });
    const alice = DefaultActor.user({ actorId: "alice" });

    const permissions = checker.getEffectivePermissions(
      policy,
      alice,
      "public",
    );
    expect(permissions).toBe(Permission.CRUD);
  });

  it("returns NONE when explicitly denied", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      deniedActors: ["user:alice"],
    });
    const alice = DefaultActor.user({ actorId: "alice" });

    const permissions = checker.getEffectivePermissions(
      policy,
      alice,
      "public",
    );
    expect(permissions).toBe(Permission.NONE);
  });

  it("returns NONE when session mismatch", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      boundSession: "sess-123",
    });
    const actor = DefaultActor.user({ sessionId: "wrong" });

    const permissions = checker.getEffectivePermissions(
      policy,
      actor,
      "public",
    );
    expect(permissions).toBe(Permission.NONE);
  });

  it("returns NONE when namespace denied", () => {
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
    });
    const bob = DefaultActor.user({ actorId: "bob" });

    const permissions = checker.getEffectivePermissions(
      policy,
      bob,
      "user:alice",
    );
    expect(permissions).toBe(Permission.NONE);
  });
});

// ═════════════════════════════════════════════════════════════════════
// PermissionChecker Protocol Compliance Tests
// ═════════════════════════════════════════════════════════════════════

describe("PermissionChecker protocol compliance", () => {
  it("DefaultPermissionChecker satisfies PermissionChecker interface", () => {
    const checker: PermissionChecker = new DefaultPermissionChecker();
    expect(checker.check).toBeFunction();
    expect(checker.hasPermission).toBeFunction();
    expect(checker.getEffectivePermissions).toBeFunction();
  });
});

// ═════════════════════════════════════════════════════════════════════
// Integration Tests
// ═════════════════════════════════════════════════════════════════════

describe("Access Control Integration", () => {
  it("full resolution order", () => {
    const checker = new DefaultPermissionChecker();

    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      agentPermissions: Permission.EXECUTE,
      owner: "user:owner",
      ownerPermissions: Permission.CRUD,
      allowedActors: ["user:special"],
      deniedActors: ["user:banned"],
      boundSession: "valid-session",
    });

    // 1. Explicit deny wins
    const banned = DefaultActor.user({
      actorId: "banned",
      sessionId: "valid-session",
    });
    try {
      checker.check(policy, Permission.READ, banned, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect((error as PermissionDenied).reason).toBe("explicit_deny");
    }

    // 2. Session binding
    const wrongSession = DefaultActor.user({ sessionId: "wrong-session" });
    try {
      checker.check(policy, Permission.READ, wrongSession, "public");
      expect(true).toBe(false);
    } catch (error) {
      expect((error as PermissionDenied).reason).toBe("session_mismatch");
    }

    // 3. Namespace ownership (via user namespace)
    const bob = DefaultActor.user({
      actorId: "bob",
      sessionId: "valid-session",
    });
    try {
      checker.check(policy, Permission.READ, bob, "user:alice");
      expect(true).toBe(false);
    } catch (error) {
      expect((error as PermissionDenied).reason).toBe("namespace_ownership");
    }

    // 4. Explicit allow bypasses role check
    const special = DefaultActor.user({
      actorId: "special",
      sessionId: "valid-session",
    });
    checker.check(policy, Permission.DELETE, special, "public"); // Would fail role check

    // 5. Owner gets owner permissions
    const owner = DefaultActor.user({
      actorId: "owner",
      sessionId: "valid-session",
    });
    checker.check(policy, Permission.DELETE, owner, "public"); // CRUD includes DELETE

    // 6. Role-based fallback
    const regular = DefaultActor.user({
      actorId: "regular",
      sessionId: "valid-session",
    });
    checker.check(policy, Permission.READ, regular, "public"); // User has READ
  });

  it("combined permissions", () => {
    const checker = new DefaultPermissionChecker();
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ | Permission.WRITE,
    });
    const user = DefaultActor.user();

    // Individual permissions work
    checker.check(policy, Permission.READ, user, "public");
    checker.check(policy, Permission.WRITE, user, "public");

    // Permission not in set fails
    expect(() => {
      checker.check(policy, Permission.DELETE, user, "public");
    }).toThrow(PermissionDenied);
  });

  it("CRUD convenience permission", () => {
    const checker = new DefaultPermissionChecker();
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.CRUD,
    });
    const user = DefaultActor.user();

    // All CRUD operations work
    checker.check(policy, Permission.READ, user, "public");
    checker.check(policy, Permission.WRITE, user, "public");
    checker.check(policy, Permission.UPDATE, user, "public");
    checker.check(policy, Permission.DELETE, user, "public");

    // EXECUTE is not included
    expect(() => {
      checker.check(policy, Permission.EXECUTE, user, "public");
    }).toThrow(PermissionDenied);
  });

  it("agent with session in user namespace is denied", () => {
    const checker = new DefaultPermissionChecker();
    const policy = AccessPolicySchema.parse({
      agentPermissions: Permission.FULL,
    });

    // Agent has session but that doesn't help with user namespace
    const agent = DefaultActor.agent({
      actorId: "claude",
      sessionId: "sess-123",
    });
    expect(() => {
      checker.check(policy, Permission.READ, agent, "user:alice");
    }).toThrow(PermissionDenied);
  });

  it("anonymous actor patterns in deny list", () => {
    const checker = new DefaultPermissionChecker();

    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      deniedActors: ["user:*"],
    });
    const anonymous = DefaultActor.user(); // Anonymous user

    // Anonymous user matches user:* and is denied
    expect(() => {
      checker.check(policy, Permission.READ, anonymous, "public");
    }).toThrow(PermissionDenied);
  });

  it("actor and namespace resolver work together end-to-end", () => {
    const checker = new DefaultPermissionChecker();

    // Alice creates data in her namespace with execute-only for agents
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.FULL,
      agentPermissions: Permission.EXECUTE,
      owner: "user:alice",
      ownerPermissions: Permission.FULL,
    });

    const alice = DefaultActor.user({ actorId: "alice" });
    const agent = DefaultActor.agent({ actorId: "claude-1" });

    // Alice can do everything in her namespace
    checker.check(policy, Permission.READ, alice, "user:alice");
    checker.check(policy, Permission.DELETE, alice, "user:alice");

    // Agent cannot access Alice's user namespace at all
    expect(() => {
      checker.check(policy, Permission.EXECUTE, agent, "user:alice");
    }).toThrow(PermissionDenied);

    // But agent can execute in public namespace
    checker.check(policy, Permission.EXECUTE, agent, "public");

    // Agent cannot read in public namespace (only EXECUTE)
    expect(() => {
      checker.check(policy, Permission.READ, agent, "public");
    }).toThrow(PermissionDenied);
  });

  it("resolveActor integrates with checker", () => {
    const checker = new DefaultPermissionChecker();
    const policy = AccessPolicySchema.parse({
      userPermissions: Permission.READ,
      agentPermissions: Permission.EXECUTE,
    });

    // Old-style literal usage
    const resolvedUser = resolveActor("user");
    checker.check(policy, Permission.READ, resolvedUser, "public");

    const resolvedAgent = resolveActor("agent");
    checker.check(policy, Permission.EXECUTE, resolvedAgent, "public");

    // New-style Actor usage
    const alice = DefaultActor.user({ actorId: "alice" });
    const resolvedAlice = resolveActor(alice);
    checker.check(policy, Permission.READ, resolvedAlice, "public");
  });
});
