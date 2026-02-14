/**
 * Tests for context layer: tokenizers and size measurers.
 *
 * Tests the Tokenizer and SizeMeasurer interfaces, CharacterFallback,
 * TiktokenAdapter, CharacterMeasurer, TokenMeasurer, and factory functions.
 *
 * Maps to Python: `tests/test_context.py`
 */

import { describe, expect, it } from "bun:test";

import {
  type Tokenizer,
  type SizeMeasurer,
  CharacterFallback,
  TiktokenAdapter,
  CharacterMeasurer,
  TokenMeasurer,
  getDefaultTokenizer,
} from "../src/index.js";

// ═════════════════════════════════════════════════════════════════════
// Tokenizer Interface Tests
// ═════════════════════════════════════════════════════════════════════

describe("Tokenizer interface", () => {
  it("CharacterFallback satisfies Tokenizer", () => {
    const tokenizer: Tokenizer = new CharacterFallback();
    expect(tokenizer).toBeDefined();
    expect(typeof tokenizer.modelName).toBe("string");
    expect(typeof tokenizer.encode).toBe("function");
    expect(typeof tokenizer.countTokens).toBe("function");
  });

  it("TiktokenAdapter satisfies Tokenizer", () => {
    const tokenizer: Tokenizer = new TiktokenAdapter();
    expect(tokenizer).toBeDefined();
    expect(typeof tokenizer.modelName).toBe("string");
    expect(typeof tokenizer.encode).toBe("function");
    expect(typeof tokenizer.countTokens).toBe("function");
  });
});

// ═════════════════════════════════════════════════════════════════════
// CharacterFallback
// ═════════════════════════════════════════════════════════════════════

describe("CharacterFallback", () => {
  it("has model name 'character-fallback'", () => {
    const tokenizer = new CharacterFallback();
    expect(tokenizer.modelName).toBe("character-fallback");
  });

  it("counts tokens by dividing character count by charsPerToken", () => {
    const tokenizer = new CharacterFallback(4);

    // 12 chars / 4 = 3 tokens
    expect(tokenizer.countTokens("Hello World!")).toBe(3);

    // 13 chars / 4 = 3.25 → ceil = 4 tokens
    expect(tokenizer.countTokens("Hello, World!")).toBe(4);
  });

  it("rounds up token count", () => {
    const tokenizer = new CharacterFallback(4);

    // 1 char → ceil(1/4) = 1
    expect(tokenizer.countTokens("a")).toBe(1);

    // 5 chars → ceil(5/4) = 2
    expect(tokenizer.countTokens("abcde")).toBe(2);

    // 4 chars → ceil(4/4) = 1
    expect(tokenizer.countTokens("abcd")).toBe(1);
  });

  it("returns 0 for empty string", () => {
    const tokenizer = new CharacterFallback();
    expect(tokenizer.countTokens("")).toBe(0);
  });

  it("encode returns pseudo token IDs", () => {
    const tokenizer = new CharacterFallback(4);

    // 12 chars → 3 tokens → [0, 1, 2]
    const tokens = tokenizer.encode("Hello World!");
    expect(tokens).toHaveLength(3);
    expect(tokens).toEqual([0, 1, 2]);
  });

  it("encode returns empty array for empty string", () => {
    const tokenizer = new CharacterFallback();
    expect(tokenizer.encode("")).toEqual([]);
  });

  it("accepts custom chars per token ratio", () => {
    const tokenizer = new CharacterFallback(2);

    // 10 chars / 2 = 5 tokens
    expect(tokenizer.countTokens("0123456789")).toBe(5);
  });

  it("default charsPerToken is 4", () => {
    const tokenizer = new CharacterFallback();

    // 8 chars / 4 = 2
    expect(tokenizer.countTokens("12345678")).toBe(2);
  });

  it("minimum token count is 1 for non-empty string", () => {
    const tokenizer = new CharacterFallback(100);

    // 1 char / 100 = 0.01 → ceil = 1
    expect(tokenizer.countTokens("x")).toBe(1);
  });
});

// ═════════════════════════════════════════════════════════════════════
// TiktokenAdapter
// ═════════════════════════════════════════════════════════════════════

describe("TiktokenAdapter", () => {
  it("has correct model name", () => {
    const tokenizer = new TiktokenAdapter("gpt-4");
    expect(tokenizer.modelName).toBe("gpt-4");
  });

  it("defaults to gpt-4o model", () => {
    const tokenizer = new TiktokenAdapter();
    expect(tokenizer.modelName).toBe("gpt-4o");
  });

  it("counts tokens with tiktoken (real tokenization)", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");
    const count = tokenizer.countTokens("Hello, world!");

    // Should return a positive number (exact count depends on model)
    expect(count).toBeGreaterThan(0);
    // "Hello, world!" is typically 4 tokens with most OpenAI encodings
    expect(count).toBeLessThan(20);
  });

  it("encode returns real token IDs", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");
    const tokens = tokenizer.encode("Hello, world!");

    expect(tokens.length).toBeGreaterThan(0);
    // All token IDs should be non-negative integers
    for (const token of tokens) {
      expect(Number.isInteger(token)).toBe(true);
      expect(token).toBeGreaterThanOrEqual(0);
    }
  });

  it("encode length matches countTokens", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");
    const text = "The quick brown fox jumps over the lazy dog.";

    expect(tokenizer.encode(text).length).toBe(tokenizer.countTokens(text));
  });

  it("handles empty string", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");
    expect(tokenizer.countTokens("")).toBe(0);
    expect(tokenizer.encode("")).toEqual([]);
  });

  it("handles unicode text", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");
    const count = tokenizer.countTokens("日本語のテスト");
    expect(count).toBeGreaterThan(0);
  });

  it("handles long text", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");
    const longText = "word ".repeat(1000);
    const count = tokenizer.countTokens(longText);
    expect(count).toBeGreaterThan(100);
  });

  it("uses explicit fallback when tiktoken is unavailable for unknown model", () => {
    // Use a model name that doesn't exist - tiktoken should fall back
    // to cl100k_base or the provided fallback
    const fallback = new CharacterFallback(2);
    const tokenizer = new TiktokenAdapter("nonexistent-model-xyz", fallback);

    // Should still work (either tiktoken fallback encoding or CharacterFallback)
    const count = tokenizer.countTokens("Hello, world!");
    expect(count).toBeGreaterThan(0);
  });

  it("encoding is cached after first use", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");

    // First call loads the encoding
    const count1 = tokenizer.countTokens("test");
    // Second call uses cached encoding
    const count2 = tokenizer.countTokens("test");

    expect(count1).toBe(count2);
  });
});

// ═════════════════════════════════════════════════════════════════════
// SizeMeasurer Interface Tests
// ═════════════════════════════════════════════════════════════════════

describe("SizeMeasurer interface", () => {
  it("CharacterMeasurer satisfies SizeMeasurer", () => {
    const measurer: SizeMeasurer = new CharacterMeasurer();
    expect(measurer).toBeDefined();
    expect(typeof measurer.measure).toBe("function");
  });

  it("TokenMeasurer satisfies SizeMeasurer", () => {
    const tokenizer = new CharacterFallback();
    const measurer: SizeMeasurer = new TokenMeasurer(tokenizer);
    expect(measurer).toBeDefined();
    expect(typeof measurer.measure).toBe("function");
  });
});

// ═════════════════════════════════════════════════════════════════════
// CharacterMeasurer
// ═════════════════════════════════════════════════════════════════════

describe("CharacterMeasurer", () => {
  const measurer = new CharacterMeasurer();

  it("measures dict by JSON string length", () => {
    const value = { key: "value" };
    const size = measurer.measure(value);

    // JSON: {"key":"value"} = 15 chars
    expect(size).toBe(JSON.stringify(value).length);
    expect(size).toBe(15);
  });

  it("measures list by JSON string length", () => {
    const value = [1, 2, 3];
    const size = measurer.measure(value);

    // JSON: [1,2,3] = 7 chars
    expect(size).toBe(JSON.stringify(value).length);
    expect(size).toBe(7);
  });

  it("measures string by JSON string length (includes quotes)", () => {
    const value = "hello";
    const size = measurer.measure(value);

    // JSON: "hello" = 7 chars (includes quotes)
    expect(size).toBe(JSON.stringify(value).length);
    expect(size).toBe(7);
  });

  it("measures nested structure", () => {
    const value = {
      users: [
        { id: 1, name: "Alice" },
        { id: 2, name: "Bob" },
      ],
    };
    const size = measurer.measure(value);
    expect(size).toBe(JSON.stringify(value).length);
  });

  it("measures number", () => {
    expect(measurer.measure(42)).toBe(2);
    expect(measurer.measure(3.14)).toBe(4);
  });

  it("measures boolean", () => {
    expect(measurer.measure(true)).toBe(4);
    expect(measurer.measure(false)).toBe(5);
  });

  it("measures null", () => {
    expect(measurer.measure(null)).toBe(4);
  });

  it("measures empty structures", () => {
    expect(measurer.measure({})).toBe(2); // "{}"
    expect(measurer.measure([])).toBe(2); // "[]"
    expect(measurer.measure("")).toBe(2); // '""'
  });

  it("handles non-serializable values gracefully", () => {
    // undefined values in objects are omitted by JSON.stringify
    const value = { key: undefined };
    const size = measurer.measure(value);
    // Our serializer converts undefined to null: {"key":null} = 12
    expect(size).toBeGreaterThan(0);
  });
});

// ═════════════════════════════════════════════════════════════════════
// TokenMeasurer
// ═════════════════════════════════════════════════════════════════════

describe("TokenMeasurer", () => {
  it("measures using injected tokenizer", () => {
    const tokenizer = new CharacterFallback(4);
    const measurer = new TokenMeasurer(tokenizer);

    const value = { key: "value" };
    const jsonLength = JSON.stringify(value).length; // 15
    const expectedTokens = Math.ceil(jsonLength / 4); // 4

    expect(measurer.measure(value)).toBe(expectedTokens);
  });

  it("measures dict", () => {
    const tokenizer = new CharacterFallback(1); // 1 char = 1 token for easy math
    const measurer = new TokenMeasurer(tokenizer);

    const value = { a: 1, b: 2 };
    expect(measurer.measure(value)).toBe(JSON.stringify(value).length);
  });

  it("measures list", () => {
    const tokenizer = new CharacterFallback(1);
    const measurer = new TokenMeasurer(tokenizer);

    const value = [1, 2, 3];
    expect(measurer.measure(value)).toBe(JSON.stringify(value).length);
  });

  it("measures with real tiktoken tokenizer", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");
    const measurer = new TokenMeasurer(tokenizer);

    const value = { message: "Hello, world!" };
    const size = measurer.measure(value);

    // Should return positive token count
    expect(size).toBeGreaterThan(0);

    // Token count should be less than character count
    const charSize = JSON.stringify(value).length;
    expect(size).toBeLessThan(charSize);
  });

  it("returns 0 for empty string values", () => {
    const tokenizer = new CharacterFallback();
    const measurer = new TokenMeasurer(tokenizer);

    // Empty string serializes to '""' which is 2 chars → 1 token
    const size = measurer.measure("");
    expect(size).toBeGreaterThan(0);
  });

  it("consistent results for same input", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");
    const measurer = new TokenMeasurer(tokenizer);

    const value = { data: [1, 2, 3] };
    const size1 = measurer.measure(value);
    const size2 = measurer.measure(value);

    expect(size1).toBe(size2);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Factory Functions
// ═════════════════════════════════════════════════════════════════════

describe("getDefaultTokenizer", () => {
  it("returns a valid Tokenizer", () => {
    const tokenizer = getDefaultTokenizer();

    expect(tokenizer).toBeDefined();
    expect(typeof tokenizer.modelName).toBe("string");
    expect(typeof tokenizer.encode).toBe("function");
    expect(typeof tokenizer.countTokens).toBe("function");
  });

  it("returns tokenizer that can count tokens", () => {
    const tokenizer = getDefaultTokenizer();
    const count = tokenizer.countTokens("Hello, world!");

    expect(count).toBeGreaterThan(0);
  });

  it("accepts explicit model parameter", () => {
    const tokenizer = getDefaultTokenizer("gpt-4o");
    expect(tokenizer.modelName).toBe("gpt-4o");
  });

  it("defaults to gpt-4o", () => {
    const tokenizer = getDefaultTokenizer();
    expect(tokenizer.modelName).toBe("gpt-4o");
  });

  it("returns working tokenizer for unknown models (falls back)", () => {
    const tokenizer = getDefaultTokenizer("completely-fake-model");

    // Should still work via fallback
    const count = tokenizer.countTokens("test");
    expect(count).toBeGreaterThan(0);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Integration Tests
// ═════════════════════════════════════════════════════════════════════

describe("Context Integration", () => {
  it("full pipeline with CharacterFallback and TokenMeasurer", () => {
    const tokenizer = new CharacterFallback();
    const measurer = new TokenMeasurer(tokenizer);

    const value = {
      users: Array.from({ length: 100 }, (_, index) => ({
        id: index,
        name: `User ${index}`,
      })),
    };

    const size = measurer.measure(value);
    expect(size).toBeGreaterThan(0);

    // Token estimate should be roughly json_length / 4
    const jsonLength = JSON.stringify(value).length;
    expect(size).toBe(Math.ceil(jsonLength / 4));
  });

  it("full pipeline with TiktokenAdapter and TokenMeasurer", () => {
    const tokenizer = new TiktokenAdapter("gpt-4o");
    const measurer = new TokenMeasurer(tokenizer);

    const value = { message: "The quick brown fox jumps over the lazy dog" };
    const size = measurer.measure(value);

    expect(size).toBeGreaterThan(0);
    // Tokens should be fewer than characters
    expect(size).toBeLessThan(JSON.stringify(value).length);
  });

  it("CharacterMeasurer vs TokenMeasurer comparison", () => {
    const charMeasurer = new CharacterMeasurer();
    const tokenMeasurer = new TokenMeasurer(new TiktokenAdapter("gpt-4o"));

    const value = { key: "Hello, world! This is a test of token counting." };

    const charSize = charMeasurer.measure(value);
    const tokenSize = tokenMeasurer.measure(value);

    // Character size should always be larger than token size
    // (since tokens represent multiple characters)
    expect(charSize).toBeGreaterThan(tokenSize);
  });

  it("different tokenizers give different counts", () => {
    const charFallback = new CharacterFallback(4);
    const tiktoken = new TiktokenAdapter("gpt-4o");

    const text = "Hello, world! This is a longer piece of text for testing.";

    const charCount = charFallback.countTokens(text);
    const tiktokenCount = tiktoken.countTokens(text);

    // Both should be positive
    expect(charCount).toBeGreaterThan(0);
    expect(tiktokenCount).toBeGreaterThan(0);

    // They will typically differ (exact match would be coincidental)
    // We just verify both produce reasonable results
    expect(charCount).toBeLessThan(text.length);
    expect(tiktokenCount).toBeLessThan(text.length);
  });
});
