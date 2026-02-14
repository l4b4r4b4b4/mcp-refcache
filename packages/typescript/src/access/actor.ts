/**
 * Actor types and identity model for access control.
 *
 * This module provides the core identity abstraction for the access control
 * system. Actors represent entities (users, agents, or system processes)
 * that can perform operations on cached values.
 *
 * Maps to Python: `access.actor`
 *
 * @module
 */

import { ActorType } from "../models/enums.js";

// ── Actor Interface ──────────────────────────────────────────────────

/**
 * Interface defining the contract for identity-aware actors.
 *
 * Actors encapsulate identity information used for access control decisions.
 * Any class implementing this interface can be used with the permission system.
 *
 * Maps to Python: `access.actor.Actor` (Protocol)
 *
 * @example
 * ```typescript
 * import type { Actor } from "./actor.js";
 *
 * class CustomActor implements Actor {
 *   readonly type = ActorType.USER;
 *   readonly actorId = "custom-user";
 *   readonly sessionId = null;
 *
 *   matches(pattern: string): boolean { ... }
 *   toString(): string { ... }
 * }
 * ```
 */
export interface Actor {
  /** The type of this actor (user, agent, or system). */
  readonly type: typeof ActorType[keyof typeof ActorType];

  /**
   * Unique identifier for this actor within its type.
   * `null` for anonymous actors.
   */
  readonly actorId: string | null;

  /**
   * Session identifier for session-scoped access control.
   * `null` if the actor is not associated with a session.
   */
  readonly sessionId: string | null;

  /**
   * Check if this actor matches an ACL pattern.
   *
   * Patterns follow the format `type:id` where:
   * - type: "user", "agent", or "system"
   * - id: specific ID, "*" for any, or glob pattern
   *
   * @param pattern - Pattern to match against (e.g., "user:alice", "agent:*").
   * @returns `true` if the actor matches the pattern.
   */
  matches(pattern: string): boolean;

  /**
   * Return canonical string representation.
   *
   * Format: `type:id` or `type:*` for anonymous actors.
   *
   * @returns String representation suitable for storage and ACL matching.
   */
  toString(): string;
}

// ── DefaultActor ─────────────────────────────────────────────────────

/**
 * Default implementation of the Actor interface.
 *
 * Provides an immutable actor with factory methods for common patterns.
 * All properties are readonly to enforce immutability.
 *
 * Maps to Python: `access.actor.DefaultActor`
 *
 * @example
 * ```typescript
 * // Anonymous actors
 * const user = DefaultActor.user();
 * const agent = DefaultActor.agent();
 *
 * // Identified actors
 * const alice = DefaultActor.user({ actorId: "alice", sessionId: "sess-123" });
 * const claude = DefaultActor.agent({ actorId: "claude-instance-1" });
 *
 * // System actor for internal operations
 * const system = DefaultActor.system();
 *
 * // Pattern matching
 * alice.matches("user:alice");  // true
 * alice.matches("user:*");      // true
 * alice.matches("agent:*");     // false
 * ```
 */
export class DefaultActor implements Actor {
  /** The type of this actor. */
  readonly type: typeof ActorType[keyof typeof ActorType];

  /** Unique identifier for this actor. `null` for anonymous actors. */
  readonly actorId: string | null;

  /** Session ID for session-scoped access control. */
  readonly sessionId: string | null;

  /**
   * Create a new DefaultActor.
   *
   * Prefer factory methods (`DefaultActor.user()`, `.agent()`, `.system()`)
   * over direct construction.
   *
   * @param type      - The actor type.
   * @param actorId   - Optional unique identifier.
   * @param sessionId - Optional session identifier.
   */
  constructor(
    type: typeof ActorType[keyof typeof ActorType],
    actorId: string | null = null,
    sessionId: string | null = null,
  ) {
    this.type = type;
    this.actorId = actorId;
    this.sessionId = sessionId;
    // Freeze to enforce immutability
    Object.freeze(this);
  }

  /**
   * Check if this actor matches an ACL pattern.
   *
   * Supports glob patterns:
   * - `*` matches any sequence of characters
   * - `?` matches any single character
   *
   * @param pattern - Pattern in format "type:id" or "type:*".
   * @returns `true` if the actor matches the pattern.
   *
   * @example
   * ```typescript
   * const actor = DefaultActor.user({ actorId: "alice" });
   * actor.matches("user:alice");   // true
   * actor.matches("user:*");       // true
   * actor.matches("user:bob");     // false
   * actor.matches("agent:*");      // false
   * ```
   */
  matches(pattern: string): boolean {
    if (!pattern.includes(":")) {
      return false;
    }

    const colonIndex = pattern.indexOf(":");
    const patternType = pattern.slice(0, colonIndex);
    const patternId = pattern.slice(colonIndex + 1);

    // Type must match exactly
    if (patternType !== this.type) {
      return false;
    }

    // Wildcard matches everything (including anonymous)
    if (patternId === "*") {
      return true;
    }

    // For anonymous actors, only wildcard matches
    if (this.actorId === null) {
      return false;
    }

    // Use glob matching for the ID portion
    return globMatch(this.actorId, patternId);
  }

  /**
   * Return canonical string representation.
   *
   * @returns String in format "type:id" or "type:*" for anonymous actors.
   */
  toString(): string {
    const identifier = this.actorId ?? "*";
    return `${this.type}:${identifier}`;
  }

  // ── Factory Methods ──────────────────────────────────────────────

  /**
   * Create a user actor.
   *
   * @param options - Optional actor ID and session ID.
   * @returns A DefaultActor instance with type USER.
   *
   * @example
   * ```typescript
   * const anonymous = DefaultActor.user();
   * const identified = DefaultActor.user({ actorId: "alice" });
   * const withSession = DefaultActor.user({
   *   actorId: "alice",
   *   sessionId: "sess-123",
   * });
   * ```
   */
  static user(
    options: { actorId?: string | null; sessionId?: string | null } = {},
  ): DefaultActor {
    return new DefaultActor(
      ActorType.USER,
      options.actorId ?? null,
      options.sessionId ?? null,
    );
  }

  /**
   * Create an agent actor.
   *
   * @param options - Optional actor ID and session ID.
   * @returns A DefaultActor instance with type AGENT.
   *
   * @example
   * ```typescript
   * const anonymous = DefaultActor.agent();
   * const identified = DefaultActor.agent({ actorId: "claude-instance-1" });
   * ```
   */
  static agent(
    options: { actorId?: string | null; sessionId?: string | null } = {},
  ): DefaultActor {
    return new DefaultActor(
      ActorType.AGENT,
      options.actorId ?? null,
      options.sessionId ?? null,
    );
  }

  /**
   * Create a system actor for internal operations.
   *
   * System actors typically have elevated privileges and are used
   * for administrative or internal operations.
   *
   * @returns A DefaultActor instance with type SYSTEM and id "internal".
   *
   * @example
   * ```typescript
   * const system = DefaultActor.system();
   * system.toString(); // "system:internal"
   * ```
   */
  static system(): DefaultActor {
    return new DefaultActor(ActorType.SYSTEM, "internal", null);
  }

  /**
   * Create an actor from a literal string (backwards compatibility).
   *
   * Provides backwards compatibility with the old `actor: "user" | "agent"`
   * parameter pattern.
   *
   * @param actor     - Either "user" or "agent".
   * @param sessionId - Optional session identifier.
   * @returns A DefaultActor instance with the appropriate type.
   *
   * @example
   * ```typescript
   * const user = DefaultActor.fromLiteral("user");
   * const agent = DefaultActor.fromLiteral("agent", "sess-123");
   * ```
   */
  static fromLiteral(
    actor: "user" | "agent",
    sessionId: string | null = null,
  ): DefaultActor {
    const actorType = actor === "user" ? ActorType.USER : ActorType.AGENT;
    return new DefaultActor(actorType, null, sessionId);
  }
}

// ── ActorLike ────────────────────────────────────────────────────────

/**
 * Type alias accepting both Actor instances and literal strings.
 *
 * Provides backwards compatibility with the old `"user" | "agent"` pattern.
 * Use {@link resolveActor} to normalize to a concrete Actor instance.
 *
 * Maps to Python: `access.actor.ActorLike`
 */
export type ActorLike = Actor | "user" | "agent";

// ── resolveActor ─────────────────────────────────────────────────────

/**
 * Resolve an ActorLike to a concrete Actor instance.
 *
 * Handles backwards compatibility by accepting either an Actor instance
 * or a literal "user"/"agent" string.
 *
 * @param actor     - Either an Actor instance or a literal "user"/"agent".
 * @param sessionId - Optional session ID (only used for literal actors).
 * @returns An Actor instance.
 *
 * @example
 * ```typescript
 * // New style (returned as-is)
 * const actor = resolveActor(DefaultActor.user({ actorId: "alice" }));
 *
 * // Old style (converted to DefaultActor)
 * const user = resolveActor("user");
 * const agent = resolveActor("agent", "sess-123");
 * ```
 */
export function resolveActor(
  actor: ActorLike,
  sessionId: string | null = null,
): Actor {
  if (typeof actor === "string") {
    return DefaultActor.fromLiteral(actor, sessionId);
  }
  return actor;
}

// ── Glob Matching ────────────────────────────────────────────────────

/**
 * Simple glob pattern matching supporting `*` and `?` wildcards.
 *
 * Matches Python's `fnmatch.fnmatch()` behavior for the subset of
 * patterns used in ACL matching:
 * - `*` matches any sequence of characters (including empty)
 * - `?` matches exactly one character
 *
 * @param text    - The text to match against.
 * @param pattern - The glob pattern.
 * @returns `true` if the text matches the pattern.
 *
 * @internal
 */
function globMatch(text: string, pattern: string): boolean {
  // Convert glob pattern to regex
  let regexString = "^";
  for (const character of pattern) {
    switch (character) {
      case "*":
        regexString += ".*";
        break;
      case "?":
        regexString += ".";
        break;
      // Escape regex special characters
      case ".":
      case "+":
      case "^":
      case "$":
      case "{":
      case "}":
      case "(":
      case ")":
      case "|":
      case "[":
      case "]":
      case "\\":
        regexString += `\\${character}`;
        break;
      default:
        regexString += character;
    }
  }
  regexString += "$";

  return new RegExp(regexString).test(text);
}
