/**
 * Tests for preview generators: sample, paginate, truncate strategies.
 *
 * Tests the PreviewGenerator interface and its implementations:
 * - SampleGenerator (binary search + evenly-spaced sampling)
 * - PaginateGenerator (page-based splitting)
 * - TruncateGenerator (string truncation)
 *
 * Also tests getDefaultGenerator factory function and integration scenarios.
 *
 * Maps to Python: `tests/test_preview.py`
 */

import { describe, expect, it } from "bun:test";

import {
  type PreviewGenerator,
  SampleGenerator,
  PaginateGenerator,
  TruncateGenerator,
  getDefaultGenerator,
  CharacterFallback,
  CharacterMeasurer,
  TokenMeasurer,
} from "../src/index.js";

import { PreviewStrategy } from "../src/models/enums.js";

// ═════════════════════════════════════════════════════════════════════
// PreviewGenerator Interface Tests
// ═════════════════════════════════════════════════════════════════════

describe("PreviewGenerator interface", () => {
  it("SampleGenerator satisfies PreviewGenerator", () => {
    const generator: PreviewGenerator = new SampleGenerator();
    expect(generator.generate).toBeFunction();
  });

  it("PaginateGenerator satisfies PreviewGenerator", () => {
    const generator: PreviewGenerator = new PaginateGenerator();
    expect(generator.generate).toBeFunction();
  });

  it("TruncateGenerator satisfies PreviewGenerator", () => {
    const generator: PreviewGenerator = new TruncateGenerator();
    expect(generator.generate).toBeFunction();
  });
});

// ═════════════════════════════════════════════════════════════════════
// SampleGenerator Tests
// ═════════════════════════════════════════════════════════════════════

describe("SampleGenerator", () => {
  const generator = new SampleGenerator();
  const measurer = new CharacterMeasurer();

  it("small list returned as-is", () => {
    const value = [1, 2, 3, 4, 5];
    const result = generator.generate(value, 1000, measurer);

    expect(result.value).toEqual(value);
    expect(result.strategy).toBe(PreviewStrategy.SAMPLE);
    expect(result.totalItems).toBe(5);
    expect(result.previewItems).toBe(5);
  });

  it("large list is sampled", () => {
    const value = Array.from({ length: 100 }, (_, index) => index);
    // Set a small limit that forces sampling
    const result = generator.generate(value, 50, measurer);

    expect((result.value as unknown[]).length).toBeLessThan(100);
    expect(result.strategy).toBe(PreviewStrategy.SAMPLE);
    expect(result.totalItems).toBe(100);
    expect(result.previewItems).toBe((result.value as unknown[]).length);
    // Preview should fit within limit
    expect(result.previewSize).toBeLessThanOrEqual(50);
  });

  it("evenly spaced sampling", () => {
    const value = Array.from({ length: 100 }, (_, index) => index);
    const result = generator.generate(value, 30, measurer);

    const preview = result.value as number[];
    // Check that samples are evenly distributed
    if (preview.length > 1) {
      // Items should be spread across the range
      expect(preview[0]!).toBeLessThan(10); // Near start
      expect(preview[preview.length - 1]!).toBeGreaterThan(90); // Near end
    }
  });

  it("small dict returned as-is", () => {
    const value = { a: 1, b: 2, c: 3 };
    const result = generator.generate(value, 1000, measurer);

    expect(result.value).toEqual(value);
    expect(result.strategy).toBe(PreviewStrategy.SAMPLE);
    expect(result.totalItems).toBe(3);
    expect(result.previewItems).toBe(3);
  });

  it("large dict is sampled", () => {
    const value: Record<string, string> = {};
    for (let index = 0; index < 100; index++) {
      value[`key_${index}`] = `value_${index}`;
    }
    const result = generator.generate(value, 100, measurer);

    const preview = result.value as Record<string, unknown>;
    expect(Object.keys(preview).length).toBeLessThan(100);
    expect(typeof preview).toBe("object");
    expect(result.strategy).toBe(PreviewStrategy.SAMPLE);
    expect(result.totalItems).toBe(100);
    expect(result.previewSize).toBeLessThanOrEqual(100);
  });

  it("string passed to truncate", () => {
    const value = "a".repeat(1000);
    const result = generator.generate(value, 50, measurer);

    // SampleGenerator handles strings by truncating
    expect((result.value as string).length).toBeLessThan(1000);
    expect(
      result.strategy === PreviewStrategy.SAMPLE ||
        result.strategy === PreviewStrategy.TRUNCATE,
    ).toBe(true);
  });

  it("nested structure", () => {
    // Use a structure where top-level sampling works
    const value: Record<string, { data: string }> = {};
    for (let index = 0; index < 50; index++) {
      value[`key_${index}`] = { data: `value_${index}` };
    }
    const result = generator.generate(value, 200, measurer);

    expect(typeof result.value).toBe("object");
    expect(result.previewSize).toBeLessThanOrEqual(200);
    expect(result.previewItems!).toBeLessThan(50);
  });

  it("empty list", () => {
    const result = generator.generate([], 100, measurer);

    expect(result.value).toEqual([]);
    expect(result.totalItems).toBe(0);
    expect(result.previewItems).toBe(0);
  });

  it("empty dict", () => {
    const result = generator.generate({}, 100, measurer);

    expect(result.value).toEqual({});
    expect(result.totalItems).toBe(0);
    expect(result.previewItems).toBe(0);
  });

  it("single item list", () => {
    const value = [{ complex: "object", with: "data" }];
    const result = generator.generate(value, 1000, measurer);

    expect(result.value).toEqual(value);
    expect(result.totalItems).toBe(1);
    expect(result.previewItems).toBe(1);
  });

  it("binary search finds optimal count", () => {
    // Create items of predictable size
    const value = Array.from({ length: 50 }, (_, index) => ({
      id: index,
      data: "x".repeat(10),
    }));
    const result = generator.generate(value, 200, measurer);

    // Should have found a good fit
    expect(result.previewSize).toBeLessThanOrEqual(200);
    // Adding one more item should exceed limit (approximately)
    expect(result.previewItems!).toBeGreaterThan(0);
  });

  it("with token measurer", () => {
    const tokenizer = new CharacterFallback();
    const tokenMeasurer = new TokenMeasurer(tokenizer);

    const value = Array.from({ length: 100 }, (_, index) => index);
    const result = generator.generate(value, 20, tokenMeasurer);

    expect(result.previewSize).toBeLessThanOrEqual(20);
    expect(result.previewItems!).toBeLessThan(100);
  });

  it("number returned as-is when fits", () => {
    const result = generator.generate(42, 100, measurer);

    expect(result.value).toBe(42);
    expect(result.strategy).toBe(PreviewStrategy.SAMPLE);
    expect(result.previewSize).toBeLessThanOrEqual(100);
  });

  it("boolean returned as-is when fits", () => {
    const result = generator.generate(true, 100, measurer);

    expect(result.value).toBe(true);
    expect(result.strategy).toBe(PreviewStrategy.SAMPLE);
  });

  it("null returned as-is when fits", () => {
    const result = generator.generate(null, 100, measurer);

    expect(result.value).toBe(null);
    expect(result.strategy).toBe(PreviewStrategy.SAMPLE);
  });
});

// ═════════════════════════════════════════════════════════════════════
// PaginateGenerator Tests
// ═════════════════════════════════════════════════════════════════════

describe("PaginateGenerator", () => {
  const generator = new PaginateGenerator();
  const measurer = new CharacterMeasurer();

  it("first page of list", () => {
    const value = Array.from({ length: 100 }, (_, index) => index);
    const result = generator.generate(value, 5000, measurer, 1, 10);

    expect(result.strategy).toBe(PreviewStrategy.PAGINATE);
    expect(result.page).toBe(1);
    expect((result.value as unknown[]).length).toBe(10);
    expect(result.value).toEqual(Array.from({ length: 10 }, (_, index) => index));
    expect(result.totalItems).toBe(100);
    expect(result.totalPages).toBe(10);
  });

  it("middle page of list", () => {
    const value = Array.from({ length: 100 }, (_, index) => index);
    const result = generator.generate(value, 1000, measurer, 5, 10);

    expect(result.page).toBe(5);
    expect(result.value).toEqual(
      Array.from({ length: 10 }, (_, index) => index + 40),
    );
  });

  it("last page of list", () => {
    const value = Array.from({ length: 95 }, (_, index) => index);
    const result = generator.generate(value, 1000, measurer, 10, 10);

    expect(result.page).toBe(10);
    expect(result.value).toEqual(
      Array.from({ length: 5 }, (_, index) => index + 90),
    );
    expect((result.value as unknown[]).length).toBe(5);
  });

  it("dict pagination", () => {
    const value: Record<string, number> = {};
    for (let index = 0; index < 50; index++) {
      value[`key_${index}`] = index;
    }
    const result = generator.generate(value, 1000, measurer, 1, 10);

    expect(result.strategy).toBe(PreviewStrategy.PAGINATE);
    expect(Object.keys(result.value as Record<string, unknown>).length).toBe(10);
    expect(typeof result.value).toBe("object");
    expect(result.totalItems).toBe(50);
    expect(result.totalPages).toBe(5);
  });

  it("page out of range returns empty", () => {
    const value = Array.from({ length: 10 }, (_, index) => index);
    const result = generator.generate(value, 1000, measurer, 100, 10);

    expect(result.value).toEqual([]);
    expect(result.page).toBe(100);
  });

  it("default page size", () => {
    const value = Array.from({ length: 100 }, (_, index) => index);
    const result = generator.generate(value, 5000, measurer, 1);

    // Default page size is 20
    expect((result.value as unknown[]).length).toBeLessThanOrEqual(20);
  });

  it("has next and previous pages", () => {
    const value = Array.from({ length: 100 }, (_, index) => index);

    // First page
    const firstResult = generator.generate(value, 1000, measurer, 1, 10);
    expect(firstResult.page).toBe(1);
    expect(firstResult.totalPages).toBe(10);

    // Middle page
    const middleResult = generator.generate(value, 1000, measurer, 5, 10);
    expect(middleResult.page).toBe(5);

    // Last page
    const lastResult = generator.generate(value, 1000, measurer, 10, 10);
    expect(lastResult.page).toBe(10);
  });

  it("empty list", () => {
    const result = generator.generate([], 1000, measurer, 1, 10);

    expect(result.value).toEqual([]);
    expect(result.totalItems).toBe(0);
    expect(result.totalPages).toBe(0);
  });

  it("page respects max size", () => {
    const value = Array.from({ length: 100 }, () => ({
      data: "x".repeat(100),
    }));
    const result = generator.generate(value, 50, measurer, 1, 10);

    // Should have fewer items than page_size due to max_size constraint
    expect(result.previewSize).toBeLessThanOrEqual(50);
  });

  it("non-collection type treated as single page", () => {
    const result = generator.generate(42, 100, measurer, 1, 10);

    expect(result.value).toBe(42);
    expect(result.strategy).toBe(PreviewStrategy.PAGINATE);
    expect(result.page).toBe(1);
    expect(result.totalPages).toBe(1);
    expect(result.totalItems).toBe(1);
  });
});

// ═════════════════════════════════════════════════════════════════════
// TruncateGenerator Tests
// ═════════════════════════════════════════════════════════════════════

describe("TruncateGenerator", () => {
  const generator = new TruncateGenerator();
  const measurer = new CharacterMeasurer();

  it("short string unchanged", () => {
    const value = "Hello, world!";
    const result = generator.generate(value, 100, measurer);

    expect(result.value).toBe(value);
    expect(result.strategy).toBe(PreviewStrategy.TRUNCATE);
  });

  it("long string truncated", () => {
    const value = "a".repeat(1000);
    const result = generator.generate(value, 50, measurer);

    const preview = result.value as string;
    expect(preview.length).toBeLessThan(1000);
    expect(preview.endsWith("...")).toBe(true);
    expect(result.strategy).toBe(PreviewStrategy.TRUNCATE);
    expect(result.previewSize).toBeLessThanOrEqual(50);
  });

  it("list stringified and truncated", () => {
    const value = Array.from({ length: 1000 }, (_, index) => index);
    const result = generator.generate(value, 50, measurer);

    const preview = result.value as string;
    expect(typeof preview).toBe("string");
    expect(preview.endsWith("...")).toBe(true);
    expect(result.previewSize).toBeLessThanOrEqual(50);
  });

  it("dict stringified and truncated", () => {
    const value: Record<string, number> = {};
    for (let index = 0; index < 100; index++) {
      value[`key_${index}`] = index;
    }
    const result = generator.generate(value, 50, measurer);

    const preview = result.value as string;
    expect(typeof preview).toBe("string");
    expect(preview.endsWith("...")).toBe(true);
    expect(result.previewSize).toBeLessThanOrEqual(50);
  });

  it("empty string", () => {
    const result = generator.generate("", 100, measurer);

    expect(result.value).toBe("");
  });

  it("exact fit", () => {
    const value = "x".repeat(10);
    // 10 chars + 2 quotes in JSON = 12 characters
    const result = generator.generate(value, 12, measurer);

    expect(result.value).toBe(value);
    expect((result.value as string).includes("...")).toBe(false);
  });

  it("preserves structure info in metadata", () => {
    const value = Array.from({ length: 100 }, (_, index) => index);
    const result = generator.generate(value, 50, measurer);

    expect(result.totalItems).toBe(100);
    expect(result.originalSize).toBeGreaterThan(50);
  });

  it("number is stringified when truncated", () => {
    // A number that fits
    const result = generator.generate(42, 100, measurer);
    expect(result.value).toBe("42");
    expect(result.strategy).toBe(PreviewStrategy.TRUNCATE);
  });

  it("boolean is stringified", () => {
    const result = generator.generate(true, 100, measurer);
    expect(result.value).toBe("true");
    expect(result.strategy).toBe(PreviewStrategy.TRUNCATE);
  });

  it("null is stringified", () => {
    const result = generator.generate(null, 100, measurer);
    expect(result.value).toBe("null");
    expect(result.strategy).toBe(PreviewStrategy.TRUNCATE);
  });
});

// ═════════════════════════════════════════════════════════════════════
// Factory Function Tests
// ═════════════════════════════════════════════════════════════════════

describe("getDefaultGenerator", () => {
  it("sample strategy", () => {
    const generator = getDefaultGenerator(PreviewStrategy.SAMPLE);
    expect(generator).toBeInstanceOf(SampleGenerator);
  });

  it("paginate strategy", () => {
    const generator = getDefaultGenerator(PreviewStrategy.PAGINATE);
    expect(generator).toBeInstanceOf(PaginateGenerator);
  });

  it("truncate strategy", () => {
    const generator = getDefaultGenerator(PreviewStrategy.TRUNCATE);
    expect(generator).toBeInstanceOf(TruncateGenerator);
  });

  it("unknown strategy defaults to sample", () => {
    const generator = getDefaultGenerator("unknown_strategy");
    expect(generator).toBeInstanceOf(SampleGenerator);
  });

  it("returns generators that implement PreviewGenerator", () => {
    for (const strategy of [
      PreviewStrategy.SAMPLE,
      PreviewStrategy.PAGINATE,
      PreviewStrategy.TRUNCATE,
    ]) {
      const generator = getDefaultGenerator(strategy);
      expect(generator.generate).toBeFunction();
    }
  });
});

// ═════════════════════════════════════════════════════════════════════
// Integration Tests
// ═════════════════════════════════════════════════════════════════════

describe("Preview Integration", () => {
  it("sample with token measurer", () => {
    const tokenizer = new CharacterFallback();
    const tokenMeasurer = new TokenMeasurer(tokenizer);
    const generator = new SampleGenerator();

    const value = Array.from({ length: 100 }, (_, index) => ({
      id: index,
      name: `Item ${index}`,
      data: "x".repeat(50),
    }));
    const result = generator.generate(value, 100, tokenMeasurer);

    expect(result.previewSize).toBeLessThanOrEqual(100);
    expect(result.previewItems!).toBeLessThan(100);
    expect(Array.isArray(result.value)).toBe(true);
  });

  it("paginate with character measurer", () => {
    const charMeasurer = new CharacterMeasurer();
    const generator = new PaginateGenerator();

    const value = Array.from({ length: 1000 }, (_, index) => index);
    const result = generator.generate(value, 500, charMeasurer, 1, 20);

    expect(result.page).toBe(1);
    expect(result.totalPages).toBe(50);
    expect((result.value as unknown[]).length).toBe(20);
  });

  it("complex nested sampling", () => {
    const charMeasurer = new CharacterMeasurer();
    const generator = new SampleGenerator();

    // Use a structure where each top-level item is reasonably sized
    const value: Record<string, { id: number; name: string; email: string }> =
      {};
    for (let index = 0; index < 100; index++) {
      value[`user_${index}`] = {
        id: index,
        name: `User ${index}`,
        email: `user${index}@example.com`,
      };
    }

    const result = generator.generate(value, 500, charMeasurer);

    expect(result.previewSize).toBeLessThanOrEqual(500);
    expect(typeof result.value).toBe("object");
    expect(result.previewItems!).toBeLessThan(100);
  });

  it("generator consistency", () => {
    const charMeasurer = new CharacterMeasurer();
    const generator = new SampleGenerator();

    const value = Array.from({ length: 100 }, (_, index) => index);

    const firstResult = generator.generate(value, 50, charMeasurer);
    const secondResult = generator.generate(value, 50, charMeasurer);

    expect(firstResult.value).toEqual(secondResult.value);
    expect(firstResult.previewItems).toBe(secondResult.previewItems);
  });

  it("truncate with token measurer", () => {
    const tokenizer = new CharacterFallback();
    const tokenMeasurer = new TokenMeasurer(tokenizer);
    const generator = new TruncateGenerator();

    const value = "a".repeat(1000);
    const result = generator.generate(value, 50, tokenMeasurer);

    expect(result.previewSize).toBeLessThanOrEqual(50);
    expect((result.value as string).endsWith("...")).toBe(true);
    expect(result.strategy).toBe(PreviewStrategy.TRUNCATE);
  });

  it("all generators respect max size", () => {
    const charMeasurer = new CharacterMeasurer();
    const largeList = Array.from({ length: 500 }, (_, index) => ({
      id: index,
      data: "x".repeat(20),
    }));
    const maxSize = 200;

    const sampleResult = new SampleGenerator().generate(
      largeList,
      maxSize,
      charMeasurer,
    );
    expect(sampleResult.previewSize).toBeLessThanOrEqual(maxSize);

    const paginateResult = new PaginateGenerator().generate(
      largeList,
      maxSize,
      charMeasurer,
      1,
      10,
    );
    expect(paginateResult.previewSize).toBeLessThanOrEqual(maxSize);

    const truncateResult = new TruncateGenerator().generate(
      largeList,
      maxSize,
      charMeasurer,
    );
    expect(truncateResult.previewSize).toBeLessThanOrEqual(maxSize);
  });

  it("sample preserves first and last elements in large list", () => {
    const charMeasurer = new CharacterMeasurer();
    const generator = new SampleGenerator();

    const value = Array.from({ length: 200 }, (_, index) => index);
    const result = generator.generate(value, 50, charMeasurer);

    const preview = result.value as number[];
    if (preview.length >= 2) {
      // First element should be 0
      expect(preview[0]).toBe(0);
      // Last element should be 199
      expect(preview[preview.length - 1]).toBe(199);
    }
  });

  it("paginate dict preserves key-value pairs", () => {
    const charMeasurer = new CharacterMeasurer();
    const generator = new PaginateGenerator();

    const value: Record<string, number> = {};
    for (let index = 0; index < 30; index++) {
      value[`key_${index}`] = index;
    }

    const result = generator.generate(value, 5000, charMeasurer, 1, 5);
    const preview = result.value as Record<string, number>;

    // Each entry should maintain key-value relationship
    for (const [key, val] of Object.entries(preview)) {
      expect(key.startsWith("key_")).toBe(true);
      expect(typeof val).toBe("number");
    }
  });

  it("different strategies produce different results for same input", () => {
    const charMeasurer = new CharacterMeasurer();
    const value = Array.from({ length: 100 }, (_, index) => index);
    const maxSize = 100;

    const sampleResult = new SampleGenerator().generate(
      value,
      maxSize,
      charMeasurer,
    );
    const truncateResult = new TruncateGenerator().generate(
      value,
      maxSize,
      charMeasurer,
    );

    expect(sampleResult.strategy).toBe(PreviewStrategy.SAMPLE);
    expect(truncateResult.strategy).toBe(PreviewStrategy.TRUNCATE);

    // Sample returns a list, truncate returns a string
    expect(Array.isArray(sampleResult.value)).toBe(true);
    expect(typeof truncateResult.value).toBe("string");
  });

  it("preview result contains all required metadata fields", () => {
    const charMeasurer = new CharacterMeasurer();
    const value = Array.from({ length: 50 }, (_, index) => index);

    const result = new SampleGenerator().generate(value, 100, charMeasurer);

    // All standard fields should be present
    expect(result).toHaveProperty("value");
    expect(result).toHaveProperty("strategy");
    expect(result).toHaveProperty("originalSize");
    expect(result).toHaveProperty("previewSize");
    expect(result).toHaveProperty("totalItems");
    expect(result).toHaveProperty("previewItems");
    expect(result).toHaveProperty("page");
    expect(result).toHaveProperty("totalPages");

    // Size fields should be numbers
    expect(typeof result.originalSize).toBe("number");
    expect(typeof result.previewSize).toBe("number");
    expect(result.originalSize).toBeGreaterThan(0);
    expect(result.previewSize).toBeGreaterThan(0);
  });
});
