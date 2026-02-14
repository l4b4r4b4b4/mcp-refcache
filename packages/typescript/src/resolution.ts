/**
 * Ref_id resolution utilities for mcp-refcache.
 *
 * This module provides utilities for detecting and resolving ref_ids
 * anywhere in input structures, enabling transparent reference passing
 * between MCP tools.
 *
 * Key features:
 * - Pattern matching for ref_id strings (e.g., "cachename:hexhash")
 * - Deep recursive resolution through nested objects and arrays
 * - Cycle detection to prevent infinite loops
 * - Error handling for missing/expired references
 * - Security: opaque errors that don't leak existence information
 *
 * Maps to Python: `resolution.py`
 *
 * @module
 */

import type { ActorLike } from "./access/actor.js";
import type { RefCache } from "./cache.js";

// ── REF_ID_PATTERN ───────────────────────────────────────────────────

/**
 * Pattern for ref_id: cachename:hexhash (e.g., "finquant:2780226d27c57e49").
 *
 * Cache name: starts with letter, followed by alphanumeric, hyphens, underscores.
 * Hash: lowercase hexadecimal characters, at least 8 characters long.
 *
 * Maps to Python: `REF_ID_PATTERN`
 */
const REF_ID_PATTERN = /^[a-zA-Z][a-zA-Z0-9_-]*:[a-f0-9]{8,}$/;

// ── isRefId ──────────────────────────────────────────────────────────

/**
 * Check if a value is a ref_id string.
 *
 * @param value - Any value to check.
 * @returns `true` if the value matches the ref_id pattern.
 *
 * @example
 * ```typescript
 * isRefId("finquant:2780226d27c57e49"); // true
 * isRefId("just a string");             // false
 * isRefId(12345);                       // false
 * isRefId({ key: "value" });            // false
 * ```
 */
export function isRefId(value: unknown): value is string {
  if (typeof value !== "string") {
    return false;
  }
  return REF_ID_PATTERN.test(value);
}

// ── CircularReferenceError ───────────────────────────────────────────

/**
 * Error raised when a circular reference is detected during resolution.
 *
 * Contains the ref_id that caused the cycle and the chain of ref_ids
 * that were being visited when the cycle was detected.
 *
 * Maps to Python: `resolution.CircularReferenceError`
 *
 * @example
 * ```typescript
 * try {
 *   await resolver.resolve(refId);
 * } catch (error) {
 *   if (error instanceof CircularReferenceError) {
 *     console.log(error.refId);  // The ref that caused the cycle
 *     console.log(error.chain);  // The chain leading to the cycle
 *   }
 * }
 * ```
 */
export class CircularReferenceError extends Error {
  override readonly name = "CircularReferenceError";

  /** The ref_id that caused the circular reference. */
  readonly refId: string;

  /** The chain of ref_ids that were being visited when the cycle was detected. */
  readonly chain: string[];

  /**
   * Create a new CircularReferenceError.
   *
   * @param refId - The ref_id that caused the circular reference.
   * @param chain - The chain of ref_ids being visited when the cycle was found.
   */
  constructor(refId: string, chain: string[]) {
    const chainString = [...chain, refId].join(" -> ");
    super(`Circular reference detected: ${chainString}`);
    this.refId = refId;
    this.chain = chain;
  }
}

// ── ResolutionResult ─────────────────────────────────────────────────

/**
 * Result of resolving ref_ids in an input structure.
 *
 * Maps to Python: `resolution.ResolutionResult`
 */
export interface ResolutionResult {
  /** The resolved value with all ref_ids replaced. */
  readonly value: unknown;

  /** Number of ref_ids that were resolved. */
  readonly resolvedCount: number;

  /** List of ref_ids that were resolved. */
  readonly resolvedRefs: string[];

  /** Dict mapping ref_ids to error messages for failed resolutions. */
  readonly errors: Record<string, string>;

  /** Check if any resolution errors occurred. */
  readonly hasErrors: boolean;

  /** Check if all resolutions succeeded. */
  readonly success: boolean;
}

/**
 * Create a ResolutionResult with computed properties.
 *
 * @internal
 */
function createResolutionResult(
  value: unknown,
  resolvedRefs: string[],
  errors: Record<string, string>,
): ResolutionResult {
  return {
    value,
    resolvedCount: resolvedRefs.length,
    resolvedRefs,
    errors,
    get hasErrors(): boolean {
      return Object.keys(errors).length > 0;
    },
    get success(): boolean {
      return Object.keys(errors).length === 0;
    },
  };
}

// ── RefResolver ──────────────────────────────────────────────────────

/**
 * Options for constructing a RefResolver.
 */
export interface RefResolverOptions {
  /** Actor identity for permission checks (default: "agent"). */
  actor?: ActorLike | undefined;

  /**
   * If `true`, raise an error for missing refs.
   * If `false`, collect errors and continue (default: `true`).
   */
  failOnMissing?: boolean | undefined;
}

/**
 * Resolves ref_ids in input structures.
 *
 * Recursively walks through input structures (objects, arrays)
 * and resolves any ref_id strings to their cached values.
 *
 * Maps to Python: `resolution.RefResolver`
 *
 * @example
 * ```typescript
 * const cache = new RefCache({ name: "myapp" });
 * const resolver = new RefResolver(cache);
 *
 * // Store some values
 * const ref1 = await cache.set("prices", [100, 101, 102]);
 * const ref2 = await cache.set("multiplier", 2.0);
 *
 * // Resolve refs in nested structure
 * const result = await resolver.resolve({
 *   data: ref1.refId,
 *   factor: ref2.refId,
 *   options: { nested: [1, 2, ref1.refId] },
 * });
 *
 * // result.value contains fully resolved structure:
 * // {
 * //   data: [100, 101, 102],
 * //   factor: 2.0,
 * //   options: { nested: [1, 2, [100, 101, 102]] },
 * // }
 * ```
 */
export class RefResolver {
  private readonly cache: RefCache;
  private readonly actor: ActorLike;
  private readonly failOnMissing: boolean;

  /**
   * Create a new RefResolver.
   *
   * @param cache   - The RefCache instance to resolve refs from.
   * @param options - Configuration options.
   */
  constructor(cache: RefCache, options: RefResolverOptions = {}) {
    this.cache = cache;
    this.actor = options.actor ?? "agent";
    this.failOnMissing = options.failOnMissing ?? true;
  }

  /**
   * Resolve all ref_ids in a value structure.
   *
   * Recursively walks through the input, resolving any ref_id strings
   * to their cached values.
   *
   * @param value - Any value that may contain ref_ids (nested or not).
   * @returns ResolutionResult containing the resolved value and metadata.
   *
   * @throws Error if `failOnMissing` is `true` and a ref_id is not found
   *         or permission is denied (opaque error message).
   * @throws CircularReferenceError if a circular reference is detected.
   */
  async resolve(value: unknown): Promise<ResolutionResult> {
    const resolvedRefs: string[] = [];
    const errors: Record<string, string> = {};
    const visiting = new Set<string>();

    const resolvedValue = await this.resolveRecursive(
      value,
      resolvedRefs,
      errors,
      visiting,
    );

    return createResolutionResult(resolvedValue, resolvedRefs, errors);
  }

  // ── Private Helpers ────────────────────────────────────────────────

  /**
   * Recursively resolve ref_ids in a value.
   *
   * @internal
   */
  private async resolveRecursive(
    value: unknown,
    resolvedRefs: string[],
    errors: Record<string, string>,
    visiting: Set<string>,
  ): Promise<unknown> {
    // Check if this is a ref_id string
    if (isRefId(value)) {
      return this.resolveRef(value, resolvedRefs, errors, visiting);
    }

    // Recursively handle plain objects (not null, not array)
    if (
      value !== null &&
      typeof value === "object" &&
      !Array.isArray(value)
    ) {
      const result: Record<string, unknown> = {};
      for (const [key, nestedValue] of Object.entries(
        value as Record<string, unknown>,
      )) {
        result[key] = await this.resolveRecursive(
          nestedValue,
          resolvedRefs,
          errors,
          visiting,
        );
      }
      return result;
    }

    // Recursively handle arrays
    if (Array.isArray(value)) {
      const result: unknown[] = [];
      for (const item of value) {
        result.push(
          await this.resolveRecursive(item, resolvedRefs, errors, visiting),
        );
      }
      return result;
    }

    // Non-container, non-ref value — return as-is
    return value;
  }

  /**
   * Resolve a single ref_id.
   *
   * @internal
   */
  private async resolveRef(
    refId: string,
    resolvedRefs: string[],
    errors: Record<string, string>,
    visiting: Set<string>,
  ): Promise<unknown> {
    // Check for circular reference
    if (visiting.has(refId)) {
      throw new CircularReferenceError(refId, [...visiting]);
    }

    try {
      // Mark as visiting before resolving
      visiting.add(refId);

      const resolvedValue = await this.cache.resolve(refId, {
        actor: this.actor,
      });
      resolvedRefs.push(refId);

      // If resolved value contains more ref_ids, resolve them too
      // (with cycle detection still active)
      if (containsRefIds(resolvedValue)) {
        const nestedResolved = await this.resolveRecursive(
          resolvedValue,
          resolvedRefs,
          errors,
          visiting,
        );
        return nestedResolved;
      }

      return resolvedValue;
    } catch (error) {
      // CircularReferenceError should always propagate
      if (error instanceof CircularReferenceError) {
        throw error;
      }

      if (this.failOnMissing) {
        // Raise opaque error that doesn't leak existence info
        // Both KeyError and PermissionDenied get the same message
        throw new Error(
          `Invalid or inaccessible reference: ${refId}`,
        );
      }

      // Collect error with opaque message
      errors[refId] = "Invalid or inaccessible reference";
      return refId; // Return original ref_id on failure
    } finally {
      // Remove from visiting set when done (whether success or failure)
      visiting.delete(refId);
    }
  }
}

// ── containsRefIds ───────────────────────────────────────────────────

/**
 * Check if a value contains any ref_ids (for nested resolution).
 *
 * @param value - The value to check.
 * @returns `true` if the value contains any ref_id strings.
 *
 * @internal
 */
function containsRefIds(value: unknown): boolean {
  if (isRefId(value)) {
    return true;
  }

  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return Object.values(value as Record<string, unknown>).some(
      containsRefIds,
    );
  }

  if (Array.isArray(value)) {
    return value.some(containsRefIds);
  }

  return false;
}

// ── Convenience Functions ────────────────────────────────────────────

/**
 * Options for convenience resolution functions.
 */
export interface ResolveOptions {
  /** Actor identity for permission checks (default: "agent"). */
  actor?: ActorLike;

  /**
   * If `true`, raise on missing refs.
   * If `false`, collect errors (default: `true`).
   */
  failOnMissing?: boolean;
}

/**
 * Convenience function to resolve all ref_ids in a value.
 *
 * @param cache   - The RefCache instance to resolve refs from.
 * @param value   - Any value that may contain ref_ids.
 * @param options - Resolution options.
 * @returns ResolutionResult containing the resolved value and metadata.
 *
 * Maps to Python: `resolution.resolve_refs`
 *
 * @example
 * ```typescript
 * const result = await resolveRefs(cache, {
 *   prices: "finquant:abc123def456",
 *   config: { factor: "finquant:def456abc789" },
 * });
 *
 * if (result.success) {
 *   console.log(`Resolved ${result.resolvedCount} refs`);
 *   useData(result.value);
 * } else {
 *   console.log("Errors:", result.errors);
 * }
 * ```
 */
export async function resolveRefs(
  cache: RefCache,
  value: unknown,
  options: ResolveOptions = {},
): Promise<ResolutionResult> {
  const resolver = new RefResolver(cache, {
    actor: options.actor,
    failOnMissing: options.failOnMissing,
  });
  return resolver.resolve(value);
}

/**
 * Resolve all ref_ids in function kwargs.
 *
 * Convenience wrapper for resolving refs in tool function arguments.
 *
 * @param cache   - The RefCache instance to resolve refs from.
 * @param kwargs  - Keyword arguments object that may contain ref_ids.
 * @param options - Resolution options.
 * @returns ResolutionResult with resolved kwargs as the value.
 *
 * Maps to Python: `resolution.resolve_kwargs`
 *
 * @example
 * ```typescript
 * const result = await resolveKwargs(cache, {
 *   data: someRefId,
 *   factor: 2.0,
 * });
 * if (result.success) {
 *   const resolvedKwargs = result.value as Record<string, unknown>;
 *   // Use resolvedKwargs...
 * }
 * ```
 */
export async function resolveKwargs(
  cache: RefCache,
  kwargs: Record<string, unknown>,
  options: ResolveOptions = {},
): Promise<ResolutionResult> {
  return resolveRefs(cache, kwargs, options);
}

/**
 * Resolve all ref_ids in both args and kwargs.
 *
 * @param cache   - The RefCache instance to resolve refs from.
 * @param args    - Positional arguments array.
 * @param kwargs  - Keyword arguments object.
 * @param options - Resolution options.
 * @returns Tuple of [argsResult, kwargsResult].
 *
 * Maps to Python: `resolution.resolve_args_and_kwargs`
 *
 * @example
 * ```typescript
 * const [argsResult, kwargsResult] = await resolveArgsAndKwargs(
 *   cache,
 *   [someRefId, "normalArg"],
 *   { data: anotherRefId, count: 5 },
 * );
 *
 * if (argsResult.success && kwargsResult.success) {
 *   const resolvedArgs = argsResult.value as unknown[];
 *   const resolvedKwargs = kwargsResult.value as Record<string, unknown>;
 *   // Use resolved values...
 * }
 * ```
 */
export async function resolveArgsAndKwargs(
  cache: RefCache,
  args: unknown[],
  kwargs: Record<string, unknown>,
  options: ResolveOptions = {},
): Promise<[ResolutionResult, ResolutionResult]> {
  const resolver = new RefResolver(cache, {
    actor: options.actor,
    failOnMissing: options.failOnMissing,
  });

  const argsResult = await resolver.resolve(args);
  const kwargsResult = await resolver.resolve(kwargs);

  return [argsResult, kwargsResult];
}
