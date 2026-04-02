/**
 * Namespace resolution and ownership for access control.
 *
 * This module provides the namespace abstraction for the access control system.
 * Namespaces partition cached values and define implicit ownership rules based
 * on naming patterns.
 *
 * Namespace Patterns:
 * - `public`: No ownership restriction, anyone can access
 * - `session:<id>`: Session-scoped, requires matching session_id
 * - `user:<id>`: User-scoped, requires matching user actor with id
 * - `agent:<id>`: Agent-scoped, requires matching agent actor with id
 * - `shared:<group>`: Group-scoped (future: group membership check)
 * - Custom namespaces follow no implicit rules
 *
 * Maps to Python: `access.namespace`
 *
 * @module
 */

import { ActorType } from "../models/enums.js";
import type { Actor } from "./actor.js";

// ── NamespaceInfo ────────────────────────────────────────────────────

/**
 * Parsed namespace information.
 *
 * Contains the decomposed components of a namespace string, including
 * scope flags and implied ownership. Instances are immutable (frozen).
 *
 * Maps to Python: `access.namespace.NamespaceInfo`
 *
 * @example
 * ```typescript
 * const info = new NamespaceInfo({
 *   raw: "user:alice",
 *   prefix: "user",
 *   identifier: "alice",
 *   isUserScoped: true,
 *   impliedOwner: "user:alice",
 * });
 *
 * info.isUserScoped;   // true
 * info.impliedOwner;   // "user:alice"
 * ```
 */
export class NamespaceInfo {
  /** The original namespace string. */
  readonly raw: string;

  /** The namespace prefix (e.g., "session", "user", "public"). */
  readonly prefix: string;

  /** The identifier part after the prefix, if any. */
  readonly identifier: string | null;

  /** Whether this is the public namespace. */
  readonly isPublic: boolean;

  /** Whether this namespace is session-scoped. */
  readonly isSessionScoped: boolean;

  /** Whether this namespace is user-scoped. */
  readonly isUserScoped: boolean;

  /** Whether this namespace is agent-scoped. */
  readonly isAgentScoped: boolean;

  /** The implied owner string, if any (e.g., "user:alice"). */
  readonly impliedOwner: string | null;

  /**
   * Create a new NamespaceInfo.
   *
   * @param options - Namespace components.
   */
  constructor(options: {
    raw: string;
    prefix: string;
    identifier?: string | null;
    isPublic?: boolean;
    isSessionScoped?: boolean;
    isUserScoped?: boolean;
    isAgentScoped?: boolean;
    impliedOwner?: string | null;
  }) {
    this.raw = options.raw;
    this.prefix = options.prefix;
    this.identifier = options.identifier ?? null;
    this.isPublic = options.isPublic ?? false;
    this.isSessionScoped = options.isSessionScoped ?? false;
    this.isUserScoped = options.isUserScoped ?? false;
    this.isAgentScoped = options.isAgentScoped ?? false;
    this.impliedOwner = options.impliedOwner ?? null;
    Object.freeze(this);
  }

  /**
   * Check equality based on raw namespace string.
   *
   * @param other - The other value to compare.
   * @returns `true` if both are NamespaceInfo with the same raw value.
   */
  equals(other: unknown): boolean {
    if (!(other instanceof NamespaceInfo)) {
      return false;
    }
    return this.raw === other.raw;
  }

  /**
   * Debug string representation.
   *
   * @returns Human-readable description.
   */
  toString(): string {
    return `NamespaceInfo(raw=${JSON.stringify(this.raw)}, prefix=${JSON.stringify(this.prefix)}, identifier=${JSON.stringify(this.identifier)})`;
  }
}

// ── NamespaceResolver Interface ──────────────────────────────────────

/**
 * Interface for namespace ownership resolution.
 *
 * Implementations determine access rules based on namespace patterns.
 * This enables implicit access control without explicit ACLs for common
 * patterns like session-scoped or user-scoped namespaces.
 *
 * Maps to Python: `access.namespace.NamespaceResolver` (Protocol)
 *
 * @example
 * ```typescript
 * class CustomResolver implements NamespaceResolver {
 *   validateAccess(namespace: string, actor: Actor): boolean { ... }
 *   getOwner(namespace: string): string | null { ... }
 *   getRequiredSession(namespace: string): string | null { ... }
 *   parse(namespace: string): NamespaceInfo { ... }
 * }
 * ```
 */
export interface NamespaceResolver {
  /**
   * Check if an actor can access this namespace.
   *
   * Applies implicit ownership rules based on the namespace pattern.
   * For example, `session:abc123` requires the actor to have a matching
   * session_id.
   *
   * @param namespace - The namespace to check access for.
   * @param actor     - The actor attempting to access.
   * @returns `true` if the actor is allowed to access the namespace.
   */
  validateAccess(namespace: string, actor: Actor): boolean;

  /**
   * Extract the owner identity from a namespace pattern.
   *
   * For ownership-implying namespaces like `user:alice` or `agent:claude-1`,
   * this returns the canonical owner string (e.g., "user:alice").
   *
   * @param namespace - The namespace to extract owner from.
   * @returns The owner identity string, or `null` if namespace has no implicit owner.
   */
  getOwner(namespace: string): string | null;

  /**
   * Extract the required session ID from a namespace pattern.
   *
   * For session-scoped namespaces like `session:abc123`, this returns
   * the session ID that actors must have to access.
   *
   * @param namespace - The namespace to check.
   * @returns The required session ID, or `null` if namespace is not session-scoped.
   */
  getRequiredSession(namespace: string): string | null;

  /**
   * Parse a namespace into its components.
   *
   * @param namespace - The namespace string to parse.
   * @returns A NamespaceInfo object with parsed components.
   */
  parse(namespace: string): NamespaceInfo;
}

// ── DefaultNamespaceResolver ─────────────────────────────────────────

/** Known namespace prefix for public namespaces. */
const PREFIX_PUBLIC = "public";

/** Known namespace prefix for session-scoped namespaces. */
const PREFIX_SESSION = "session";

/** Known namespace prefix for user-scoped namespaces. */
const PREFIX_USER = "user";

/** Known namespace prefix for agent-scoped namespaces. */
const PREFIX_AGENT = "agent";

/** Known namespace prefix for shared/group namespaces. */
const PREFIX_SHARED = "shared";

/**
 * Default implementation of the NamespaceResolver interface.
 *
 * Implements standard namespace patterns:
 * - `public`: No restrictions
 * - `session:<id>`: Requires `actor.sessionId === id`
 * - `user:<id>`: Requires `actor.type === USER` and `actor.actorId === id`
 * - `agent:<id>`: Requires `actor.type === AGENT` and `actor.actorId === id`
 * - `shared:<group>`: Currently allows all (group membership TBD)
 * - Custom namespaces: No implicit restrictions
 *
 * Maps to Python: `access.namespace.DefaultNamespaceResolver`
 *
 * @example
 * ```typescript
 * const resolver = new DefaultNamespaceResolver();
 *
 * // Parse namespace
 * const info = resolver.parse("session:abc123");
 * info.isSessionScoped; // true
 * info.identifier;      // "abc123"
 *
 * // Validate access
 * const alice = DefaultActor.user({ actorId: "alice" });
 * resolver.validateAccess("user:alice", alice); // true
 * resolver.validateAccess("user:bob", alice);   // false
 * ```
 */
export class DefaultNamespaceResolver implements NamespaceResolver {
  /**
   * Check if an actor can access this namespace.
   *
   * Applies implicit ownership rules:
   * - public: Always allowed
   * - session:\<id\>: Requires matching sessionId
   * - user:\<id\>: Requires USER type with matching actorId
   * - agent:\<id\>: Requires AGENT type with matching actorId
   * - shared:\<group\>: Currently allows all (TODO: group membership)
   * - SYSTEM actors bypass all namespace restrictions
   * - Custom namespaces: Always allowed (no implicit rules)
   *
   * @param namespace - The namespace to check access for.
   * @param actor     - The actor attempting to access.
   * @returns `true` if the actor is allowed to access the namespace.
   */
  validateAccess(namespace: string, actor: Actor): boolean {
    // System actors bypass namespace restrictions
    if (actor.type === ActorType.SYSTEM) {
      return true;
    }

    const info = this.parse(namespace);

    // Public namespace — always accessible
    if (info.isPublic) {
      return true;
    }

    // Session-scoped — require matching sessionId
    if (info.isSessionScoped) {
      if (actor.sessionId === null) {
        return false;
      }
      return actor.sessionId === info.identifier;
    }

    // User-scoped — require USER type with matching actorId
    if (info.isUserScoped) {
      if (actor.type !== ActorType.USER) {
        return false;
      }
      if (actor.actorId === null) {
        return false;
      }
      return actor.actorId === info.identifier;
    }

    // Agent-scoped — require AGENT type with matching actorId
    if (info.isAgentScoped) {
      if (actor.type !== ActorType.AGENT) {
        return false;
      }
      if (actor.actorId === null) {
        return false;
      }
      return actor.actorId === info.identifier;
    }

    // Shared namespace — allow all for now (group membership TBD)
    if (info.prefix === PREFIX_SHARED) {
      return true;
    }

    // Custom namespaces — no implicit restrictions
    return true;
  }

  /**
   * Extract the owner identity from a namespace pattern.
   *
   * @param namespace - The namespace to extract owner from.
   * @returns The owner identity string (e.g., "user:alice"), or `null`.
   */
  getOwner(namespace: string): string | null {
    const info = this.parse(namespace);
    return info.impliedOwner;
  }

  /**
   * Extract the required session ID from a namespace pattern.
   *
   * @param namespace - The namespace to check.
   * @returns The required session ID, or `null` if not session-scoped.
   */
  getRequiredSession(namespace: string): string | null {
    const info = this.parse(namespace);
    if (info.isSessionScoped) {
      return info.identifier;
    }
    return null;
  }

  /**
   * Parse a namespace into its components.
   *
   * Handles the following patterns:
   * - "public" → prefix="public", identifier=null, isPublic=true
   * - "session:abc123" → prefix="session", identifier="abc123", isSessionScoped=true
   * - "user:alice" → prefix="user", identifier="alice", isUserScoped=true
   * - "agent:claude" → prefix="agent", identifier="claude", isAgentScoped=true
   * - "custom" → prefix="custom", identifier=null
   * - "custom:value" → prefix="custom", identifier="value"
   *
   * @param namespace - The namespace string to parse.
   * @returns A NamespaceInfo object with parsed components.
   */
  parse(namespace: string): NamespaceInfo {
    // Handle public namespace specially
    if (namespace === PREFIX_PUBLIC) {
      return new NamespaceInfo({
        raw: namespace,
        prefix: PREFIX_PUBLIC,
        identifier: null,
        isPublic: true,
      });
    }

    // Split on first colon
    let prefix: string;
    let identifier: string | null;

    const colonIndex = namespace.indexOf(":");
    if (colonIndex !== -1) {
      prefix = namespace.slice(0, colonIndex);
      identifier = namespace.slice(colonIndex + 1);
    } else {
      prefix = namespace;
      identifier = null;
    }

    // Determine namespace type and implied owner
    const isSessionScoped = prefix === PREFIX_SESSION;
    const isUserScoped = prefix === PREFIX_USER;
    const isAgentScoped = prefix === PREFIX_AGENT;

    // Calculate implied owner for user/agent namespaces
    let impliedOwner: string | null = null;
    if (isUserScoped && identifier) {
      impliedOwner = `user:${identifier}`;
    } else if (isAgentScoped && identifier) {
      impliedOwner = `agent:${identifier}`;
    }

    return new NamespaceInfo({
      raw: namespace,
      prefix,
      identifier,
      isPublic: false,
      isSessionScoped,
      isUserScoped,
      isAgentScoped,
      impliedOwner,
    });
  }
}
