/**
 * Size measurer implementations.
 *
 * Provides two strategies for measuring value sizes:
 * - `CharacterMeasurer`: Measures by JSON string length (fast, no dependencies).
 * - `TokenMeasurer`: Measures by token count using an injected `Tokenizer`
 *   (accurate for LLM context window management).
 *
 * Both measurers serialize values to JSON before measurement, matching
 * the Python implementation's behavior.
 *
 * Maps to Python: `context.CharacterMeasurer`, `context.TokenMeasurer`
 *
 * @module
 */

import type { SizeMeasurer, Tokenizer } from "./types.js";

// ── Serialization Helper ─────────────────────────────────────────────

/**
 * Serialize a value to a JSON string for measurement.
 *
 * Handles non-serializable values by falling back to `String()`.
 * Matches Python's `json.dumps(value, default=str)` behavior.
 *
 * @param value - The value to serialize.
 * @returns JSON string representation.
 *
 * @internal
 */
function serializeValue(value: unknown): string {
  try {
    return JSON.stringify(value, (_key, nestedValue) => {
      if (nestedValue === undefined) {
        return null;
      }
      if (
        typeof nestedValue === "bigint" ||
        typeof nestedValue === "symbol" ||
        typeof nestedValue === "function"
      ) {
        return String(nestedValue);
      }
      return nestedValue;
    });
  } catch {
    return String(value);
  }
}

// ── CharacterMeasurer ────────────────────────────────────────────────

/**
 * Measure value size by JSON character count.
 *
 * Simple and fast measurement using `JSON.stringify().length`.
 * Good for quick estimates when exact token counts are not needed.
 *
 * Maps to Python: `context.CharacterMeasurer`
 *
 * @example
 * ```typescript
 * const measurer = new CharacterMeasurer();
 * measurer.measure({ key: "value" });    // 15  (JSON: '{"key":"value"}')
 * measurer.measure([1, 2, 3]);           // 7   (JSON: '[1,2,3]')
 * measurer.measure("hello");             // 7   (JSON: '"hello"')
 * ```
 */
export class CharacterMeasurer implements SizeMeasurer {
  /**
   * Measure value size as JSON string length.
   *
   * @param value - The value to measure.
   * @returns Length of JSON-serialized value in characters.
   */
  measure(value: unknown): number {
    return serializeValue(value).length;
  }
}

// ── TokenMeasurer ────────────────────────────────────────────────────

/**
 * Measure value size by token count using an injected `Tokenizer`.
 *
 * Provides accurate token counts for LLM context window management.
 * The tokenizer is injected via the constructor for flexibility and
 * testability — any `Tokenizer` implementation works.
 *
 * Maps to Python: `context.TokenMeasurer`
 *
 * @example
 * ```typescript
 * import { TiktokenAdapter } from "./tokenizers.js";
 *
 * const tokenizer = new TiktokenAdapter("gpt-4o");
 * const measurer = new TokenMeasurer(tokenizer);
 * const size = measurer.measure({ key: "value" }); // ~5 tokens
 * ```
 */
export class TokenMeasurer implements SizeMeasurer {
  /**
   * The tokenizer used for token counting.
   *
   * @internal
   */
  private readonly tokenizer: Tokenizer;

  /**
   * Create a new TokenMeasurer.
   *
   * @param tokenizer - Tokenizer implementation to use for counting.
   */
  constructor(tokenizer: Tokenizer) {
    this.tokenizer = tokenizer;
  }

  /**
   * Measure value size in tokens.
   *
   * The value is JSON-serialized, then the resulting string is
   * passed to the tokenizer for counting.
   *
   * @param value - The value to measure.
   * @returns Token count of JSON-serialized value.
   */
  measure(value: unknown): number {
    const text = serializeValue(value);
    return this.tokenizer.countTokens(text);
  }
}
