/**
 * Interfaces for tokenization and size measurement.
 *
 * Defines the contracts that all tokenizer and size-measurer
 * implementations must satisfy. These enable pluggable token
 * counting (tiktoken, character fallback) and size measurement
 * (token-based, character-based) for context limiting.
 *
 * Maps to Python: `context.Tokenizer`, `context.SizeMeasurer`
 *
 * @module
 */

// ── Tokenizer Interface ──────────────────────────────────────────────

/**
 * Contract for tokenizer adapters.
 *
 * Implementations provide token counting for different LLM families.
 * All implementations should support lazy loading for fast initialization.
 *
 * @example
 * ```typescript
 * const tokenizer: Tokenizer = new TiktokenAdapter("gpt-4o");
 * const count = tokenizer.countTokens("Hello, world!");
 * const ids = tokenizer.encode("Hello, world!");
 * ```
 */
export interface Tokenizer {
  /**
   * The model this tokenizer targets.
   *
   * @example `"gpt-4o"`, `"character-fallback"`
   */
  readonly modelName: string;

  /**
   * Encode text to token IDs.
   *
   * @param text - The text to encode.
   * @returns Array of integer token IDs.
   */
  encode(text: string): number[];

  /**
   * Count tokens in text.
   *
   * May be more efficient than `encode(text).length` for some
   * implementations, but the default expectation is equivalence.
   *
   * @param text - The text to count tokens for.
   * @returns Number of tokens in the text.
   */
  countTokens(text: string): number;
}

// ── SizeMeasurer Interface ───────────────────────────────────────────

/**
 * Contract for measuring the size of arbitrary values.
 *
 * Implementations serialize the value to a string (typically JSON)
 * and measure its size in either tokens or characters. The preview
 * system uses this to decide whether values need to be truncated,
 * sampled, or paginated.
 *
 * @example
 * ```typescript
 * const measurer: SizeMeasurer = new CharacterMeasurer();
 * const size = measurer.measure({ key: "value" });
 * // Returns JSON character length
 * ```
 */
export interface SizeMeasurer {
  /**
   * Measure the size of a value.
   *
   * The value is typically JSON-serialized before measurement.
   * The unit depends on the implementation (tokens or characters).
   *
   * @param value - The value to measure (dict, list, string, etc.).
   * @returns Size in the implementation's unit (tokens or characters).
   */
  measure(value: unknown): number;
}
