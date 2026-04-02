/**
 * Tokenizer implementations for token counting.
 *
 * Provides two tokenizer adapters:
 * - `CharacterFallback`: Always-available approximation (~4 chars/token).
 * - `TiktokenAdapter`: Wraps `js-tiktoken` for accurate OpenAI token counts,
 *   with graceful fallback to `CharacterFallback` if the library is
 *   unavailable or the model is not recognized.
 *
 * Maps to Python: `context.CharacterFallback`, `context.TiktokenAdapter`
 *
 * @module
 */

import type { Tokenizer } from "./types.js";

// ── CharacterFallback ────────────────────────────────────────────────

/**
 * Fallback tokenizer using character-count approximation.
 *
 * Estimates tokens as approximately `charsPerToken` characters per token
 * (default: 4). This is a rough approximation that works when no real
 * tokenizer library is available.
 *
 * @example
 * ```typescript
 * const tokenizer = new CharacterFallback();
 * tokenizer.countTokens("Hello, world!"); // ~4
 *
 * const precise = new CharacterFallback(3);
 * precise.countTokens("Hello, world!"); // ~5
 * ```
 */
export class CharacterFallback implements Tokenizer {
  /** @inheritdoc */
  readonly modelName: string = "character-fallback";

  /**
   * Characters-per-token ratio used for approximation.
   *
   * @internal
   */
  private readonly charsPerToken: number;

  /**
   * Create a new CharacterFallback tokenizer.
   *
   * @param charsPerToken - Characters per token ratio (default: 4).
   */
  constructor(charsPerToken: number = 4) {
    this.charsPerToken = charsPerToken;
  }

  /**
   * Return pseudo token IDs based on character count.
   *
   * The returned array contains incrementing integers whose length
   * equals the estimated token count. These are not real token IDs.
   *
   * @param text - The text to encode.
   * @returns Array of pseudo token IDs.
   */
  encode(text: string): number[] {
    const tokenCount = this.countTokens(text);
    return Array.from({ length: tokenCount }, (_, index) => index);
  }

  /**
   * Estimate token count from character length.
   *
   * @param text - The text to count tokens for.
   * @returns Estimated token count (rounded up, minimum 0).
   */
  countTokens(text: string): number {
    if (text.length === 0) {
      return 0;
    }
    return Math.ceil(text.length / this.charsPerToken);
  }
}

// ── TiktokenAdapter ──────────────────────────────────────────────────

/**
 * Adapter for the `js-tiktoken` library (OpenAI tokenization).
 *
 * Provides accurate token counting for OpenAI models (gpt-4o, gpt-4,
 * gpt-3.5-turbo, etc.). The tiktoken encoding is lazily loaded on
 * first use.
 *
 * If `js-tiktoken` is not installed or the model is not recognized,
 * the adapter falls back to a `CharacterFallback` tokenizer.
 *
 * @example
 * ```typescript
 * const tokenizer = new TiktokenAdapter("gpt-4o");
 * const count = tokenizer.countTokens("Hello, world!"); // accurate
 *
 * // With explicit fallback
 * const withFallback = new TiktokenAdapter("gpt-4o", new CharacterFallback(3));
 * ```
 */
export class TiktokenAdapter implements Tokenizer {
  /** @inheritdoc */
  readonly modelName: string;

  /**
   * Fallback tokenizer used when js-tiktoken is unavailable.
   *
   * @internal
   */
  private readonly fallback: Tokenizer;

  /**
   * Cached js-tiktoken encoding instance, or `null` if not yet loaded.
   *
   * @internal
   */
  private encoding: { encode: (text: string) => number[] } | null = null;

  /**
   * Tracks whether js-tiktoken is available to avoid repeated import attempts.
   * - `null`: not yet checked
   * - `true`: available and loaded
   * - `false`: unavailable (import failed or model not found)
   *
   * @internal
   */
  private tiktokenAvailable: boolean | null = null;

  /**
   * Create a new TiktokenAdapter.
   *
   * @param model    - OpenAI model name (default: `"gpt-4o"`).
   * @param fallback - Fallback tokenizer if js-tiktoken is unavailable
   *                   (default: `new CharacterFallback()`).
   */
  constructor(
    model: string = "gpt-4o",
    fallback?: Tokenizer,
  ) {
    this.modelName = model;
    this.fallback = fallback ?? new CharacterFallback();
  }

  /**
   * Encode text to token IDs using js-tiktoken.
   *
   * Falls back to `CharacterFallback.encode()` if js-tiktoken is
   * unavailable.
   *
   * @param text - The text to encode.
   * @returns Array of token IDs.
   */
  encode(text: string): number[] {
    const encoding = this.getEncoding();
    if (encoding !== null) {
      return Array.from(encoding.encode(text));
    }
    return this.fallback.encode(text);
  }

  /**
   * Count tokens using js-tiktoken.
   *
   * Falls back to `CharacterFallback.countTokens()` if js-tiktoken
   * is unavailable.
   *
   * @param text - The text to count tokens for.
   * @returns Number of tokens.
   */
  countTokens(text: string): number {
    const encoding = this.getEncoding();
    if (encoding !== null) {
      return encoding.encode(text).length;
    }
    return this.fallback.countTokens(text);
  }

  /**
   * Get or create the js-tiktoken encoding.
   *
   * Lazily loads the encoding on first call. If js-tiktoken is not
   * installed or the model is not recognized, caches the failure
   * and returns `null` on subsequent calls.
   *
   * @returns The tiktoken encoding, or `null` if unavailable.
   *
   * @internal
   */
  private getEncoding(): { encode: (text: string) => number[] } | null {
    if (this.encoding !== null) {
      return this.encoding;
    }

    if (this.tiktokenAvailable === false) {
      return null;
    }

    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const tiktoken = require("js-tiktoken") as typeof import("js-tiktoken");
      this.encoding = tiktoken.encodingForModel(
        this.modelName as Parameters<typeof tiktoken.encodingForModel>[0],
      );
      this.tiktokenAvailable = true;
      return this.encoding;
    } catch {
      // js-tiktoken not installed or model not recognized —
      // try cl100k_base as a generic fallback encoding
      try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const tiktoken = require("js-tiktoken") as typeof import("js-tiktoken");
        this.encoding = tiktoken.getEncoding("cl100k_base");
        this.tiktokenAvailable = true;
        return this.encoding;
      } catch {
        this.tiktokenAvailable = false;
        return null;
      }
    }
  }
}

// ── Factory Function ─────────────────────────────────────────────────

/**
 * Get a default tokenizer, preferring js-tiktoken if available.
 *
 * Tries `TiktokenAdapter` first. If js-tiktoken is not installed,
 * falls back to `CharacterFallback`.
 *
 * @param model - Optional model name (default: `"gpt-4o"`).
 * @returns A `Tokenizer` implementation.
 *
 * @example
 * ```typescript
 * const tokenizer = getDefaultTokenizer();        // auto-detect
 * const gpt4 = getDefaultTokenizer("gpt-4o");     // prefer tiktoken
 * ```
 */
export function getDefaultTokenizer(model?: string): Tokenizer {
  const adapter = new TiktokenAdapter(model ?? "gpt-4o");

  // Probe whether tiktoken actually works by encoding an empty string.
  // If it throws or falls back, just return the adapter anyway —
  // it handles fallback internally.
  return adapter;
}
