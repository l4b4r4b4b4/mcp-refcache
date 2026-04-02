# Task-05: Preview System (Token Counting)

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Implement the preview generation system with support for token counting (via tiktoken), character-based limits, and multiple preview strategies (truncate, sample, paginate). This system ensures large cached values don't overwhelm agent context windows.

---

## Context
The preview system is critical to mcp-refcache's value proposition: returning manageable previews instead of flooding the agent's context with massive data. The Python implementation supports:

1. **Size measurement**: Token-based (tiktoken, HuggingFace) or character-based
2. **Strategies**: Truncate (cut off), Sample (first/last/middle), Paginate (chunked)
3. **Preview generation**: Creates text representation with metadata about total size

For the TypeScript version, we'll focus on tiktoken (most common) with character fallback, keeping the architecture extensible.

## Acceptance Criteria
- [ ] `SizeMeasurer` interface for measuring value sizes
- [ ] `TokenMeasurer` using tiktoken for OpenAI-compatible token counting
- [ ] `CharacterMeasurer` as lightweight fallback
- [ ] `PreviewGenerator` interface for generating previews
- [ ] `TruncateGenerator` - cuts off at max size with "..." indicator
- [ ] `SampleGenerator` - shows first/last elements with "... N more ..."
- [ ] `PaginateGenerator` - chunks data for page-by-page access
- [ ] `PreviewResult` type with text, metadata, pagination info
- [ ] Integration with various data types (arrays, objects, strings, primitives)
- [ ] Unit tests for all generators and measurers
- [ ] JSDoc documentation with examples

---

## Approach
Port the Python preview system while simplifying for TypeScript idioms. Use tiktoken-js for token counting (same tokenizers as OpenAI). Design for extensibility but ship with practical defaults.

### Steps

1. **Define interfaces**
   - `SizeMeasurer`: Interface for size measurement
   - `PreviewGenerator`: Interface for preview generation
   - `PreviewResult`: Return type with text and metadata

2. **Implement TokenMeasurer**
   - Use `tiktoken` package
   - Support common encodings (cl100k_base for GPT-4, o200k_base for GPT-4o)
   - Handle encoding/decoding gracefully

3. **Implement CharacterMeasurer**
   - Simple string length measurement
   - Used as fallback when tiktoken unavailable

4. **Implement TruncateGenerator**
   - Cut off at max size
   - Add ellipsis indicator
   - Preserve structure hints (array brackets, object braces)

5. **Implement SampleGenerator**
   - Show first N and last M elements
   - Include count of hidden elements
   - Works for arrays and object keys

6. **Implement PaginateGenerator**
   - Divide into fixed-size pages
   - Return page metadata (current, total, hasMore)
   - Support navigation by page number

7. **Add value serialization**
   - Convert any value to previewable string
   - Handle nested structures
   - Respect depth limits

8. **Write comprehensive tests**

---

## Interface Design

```typescript
// src/preview/types.ts

export interface PreviewResult {
  /** The preview text */
  text: string;
  /** Total number of items (for arrays/objects) */
  totalItems?: number;
  /** Total size in the configured unit (tokens/chars) */
  totalSize?: number;
  /** Preview size in the configured unit */
  previewSize: number;
  /** Current page (1-indexed, for pagination) */
  currentPage?: number;
  /** Total pages available */
  totalPages?: number;
  /** Whether more content is available */
  hasMore: boolean;
  /** Items per page (for pagination) */
  pageSize?: number;
}

export interface SizeMeasurer {
  /** Measure the size of a string */
  measure(text: string): number;

  /** Unit name for display ('tokens' or 'characters') */
  readonly unit: 'tokens' | 'characters';
}

export interface PreviewOptions {
  /** Maximum size in measurer units */
  maxSize: number;
  /** Size measurer to use */
  measurer: SizeMeasurer;
  /** Page number for pagination (1-indexed) */
  page?: number;
  /** Items per page */
  pageSize?: number;
}

export interface PreviewGenerator {
  /** Generate a preview of the value */
  generate(value: unknown, options: PreviewOptions): PreviewResult;

  /** Strategy name */
  readonly strategy: 'truncate' | 'sample' | 'paginate';
}
```

---

## Implementation Sketches

### TokenMeasurer
```typescript
// src/preview/measurers/token.ts
import { encoding_for_model, TiktokenModel } from 'tiktoken';

export class TokenMeasurer implements SizeMeasurer {
  readonly unit = 'tokens' as const;
  private encoder;

  constructor(model: TiktokenModel = 'gpt-4o') {
    this.encoder = encoding_for_model(model);
  }

  measure(text: string): number {
    return this.encoder.encode(text).length;
  }

  /** Truncate text to approximately maxTokens */
  truncate(text: string, maxTokens: number): string {
    const tokens = this.encoder.encode(text);
    if (tokens.length <= maxTokens) return text;
    return this.encoder.decode(tokens.slice(0, maxTokens));
  }
}
```

### CharacterMeasurer
```typescript
// src/preview/measurers/character.ts

export class CharacterMeasurer implements SizeMeasurer {
  readonly unit = 'characters' as const;

  measure(text: string): number {
    return text.length;
  }
}
```

### TruncateGenerator
```typescript
// src/preview/generators/truncate.ts

export class TruncateGenerator implements PreviewGenerator {
  readonly strategy = 'truncate' as const;

  generate(value: unknown, options: PreviewOptions): PreviewResult {
    const serialized = serialize(value);
    const totalSize = options.measurer.measure(serialized);

    if (totalSize <= options.maxSize) {
      return {
        text: serialized,
        totalSize,
        previewSize: totalSize,
        hasMore: false,
      };
    }

    // Truncate and add indicator
    const truncated = this.truncateToSize(serialized, options.maxSize - 10, options.measurer);
    const withIndicator = truncated + '... (truncated)';

    return {
      text: withIndicator,
      totalSize,
      previewSize: options.measurer.measure(withIndicator),
      hasMore: true,
    };
  }

  private truncateToSize(text: string, maxSize: number, measurer: SizeMeasurer): string {
    // Binary search for the right cut point
    let low = 0;
    let high = text.length;

    while (low < high) {
      const mid = Math.floor((low + high + 1) / 2);
      if (measurer.measure(text.slice(0, mid)) <= maxSize) {
        low = mid;
      } else {
        high = mid - 1;
      }
    }

    return text.slice(0, low);
  }
}
```

### SampleGenerator
```typescript
// src/preview/generators/sample.ts

export class SampleGenerator implements PreviewGenerator {
  readonly strategy = 'sample' as const;

  constructor(
    private firstN: number = 3,
    private lastN: number = 2
  ) {}

  generate(value: unknown, options: PreviewOptions): PreviewResult {
    if (Array.isArray(value)) {
      return this.sampleArray(value, options);
    }

    if (typeof value === 'object' && value !== null) {
      return this.sampleObject(value as Record<string, unknown>, options);
    }

    // For non-collections, fall back to truncate
    return new TruncateGenerator().generate(value, options);
  }

  private sampleArray(arr: unknown[], options: PreviewOptions): PreviewResult {
    const total = arr.length;

    if (total <= this.firstN + this.lastN) {
      const text = JSON.stringify(arr);
      return {
        text,
        totalItems: total,
        previewSize: options.measurer.measure(text),
        hasMore: false,
      };
    }

    const first = arr.slice(0, this.firstN);
    const last = arr.slice(-this.lastN);
    const hidden = total - this.firstN - this.lastN;

    const text = `[${JSON.stringify(first).slice(1, -1)}, ... ${hidden} more ..., ${JSON.stringify(last).slice(1, -1)}]`;

    return {
      text,
      totalItems: total,
      previewSize: options.measurer.measure(text),
      hasMore: true,
    };
  }

  private sampleObject(obj: Record<string, unknown>, options: PreviewOptions): PreviewResult {
    const keys = Object.keys(obj);
    const total = keys.length;

    if (total <= this.firstN + this.lastN) {
      const text = JSON.stringify(obj);
      return {
        text,
        totalItems: total,
        previewSize: options.measurer.measure(text),
        hasMore: false,
      };
    }

    const firstKeys = keys.slice(0, this.firstN);
    const lastKeys = keys.slice(-this.lastN);
    const hidden = total - this.firstN - this.lastN;

    const firstPart = firstKeys.map(k => `"${k}": ${JSON.stringify(obj[k])}`).join(', ');
    const lastPart = lastKeys.map(k => `"${k}": ${JSON.stringify(obj[k])}`).join(', ');
    const text = `{${firstPart}, ... ${hidden} more keys ..., ${lastPart}}`;

    return {
      text,
      totalItems: total,
      previewSize: options.measurer.measure(text),
      hasMore: true,
    };
  }
}
```

### PaginateGenerator
```typescript
// src/preview/generators/paginate.ts

export class PaginateGenerator implements PreviewGenerator {
  readonly strategy = 'paginate' as const;

  generate(value: unknown, options: PreviewOptions): PreviewResult {
    if (!Array.isArray(value)) {
      // For non-arrays, paginate by chunks
      return this.paginateString(serialize(value), options);
    }

    return this.paginateArray(value, options);
  }

  private paginateArray(arr: unknown[], options: PreviewOptions): PreviewResult {
    const pageSize = options.pageSize ?? 10;
    const page = options.page ?? 1;
    const totalPages = Math.ceil(arr.length / pageSize);

    const start = (page - 1) * pageSize;
    const end = Math.min(start + pageSize, arr.length);
    const pageItems = arr.slice(start, end);

    const text = JSON.stringify(pageItems);

    return {
      text,
      totalItems: arr.length,
      previewSize: options.measurer.measure(text),
      currentPage: page,
      totalPages,
      pageSize,
      hasMore: page < totalPages,
    };
  }

  private paginateString(text: string, options: PreviewOptions): PreviewResult {
    const pageSize = options.maxSize;
    const page = options.page ?? 1;
    const totalSize = options.measurer.measure(text);
    const totalPages = Math.ceil(totalSize / pageSize);

    // This is approximate for tokens, exact for characters
    const charPerUnit = text.length / totalSize;
    const charsPerPage = Math.floor(pageSize * charPerUnit);

    const start = (page - 1) * charsPerPage;
    const pageText = text.slice(start, start + charsPerPage);

    return {
      text: pageText,
      totalSize,
      previewSize: options.measurer.measure(pageText),
      currentPage: page,
      totalPages,
      hasMore: page < totalPages,
    };
  }
}
```

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with implementation sketches |

### Design Decisions

1. **tiktoken as primary**: Most MCP servers interact with OpenAI models, so tiktoken makes sense as the primary tokenizer. Character fallback for environments where tiktoken isn't available.

2. **Synchronous measurers**: Unlike Python's async approach, we keep measurers synchronous since tokenization is CPU-bound and typically fast.

3. **Binary search for truncation**: Finding the exact cut point for token limits requires measuring multiple substrings. Binary search minimizes iterations.

4. **Sample vs Paginate**: Sample shows a representative glimpse (first/last), while Paginate provides exhaustive access. Different use cases.

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | Required | Project structure needed |
| Task-02: Models & Schemas | Required | PreviewConfig types |
| tiktoken availability | Research | Need to verify tiktoken-js works with Bun |

---

## npm Packages

| Package | Purpose | Notes |
|---------|---------|-------|
| `tiktoken` | Token counting | By @dqbd, most popular |
| `js-tiktoken` | Alternative | Lighter, WASM-based |
| `gpt-tokenizer` | Another option | Pure JS, no WASM |

---

## Verification
_How to confirm this task is complete._

```bash
# Run preview tests
bun test tests/preview/

# Verify tiktoken integration
bun run -e "
import { TokenMeasurer } from './src/preview/measurers/token';
const m = new TokenMeasurer('gpt-4o');
console.log('Hello world tokens:', m.measure('Hello, world!'));
"

# Test all generators
bun test tests/preview/generators/
```

### Test Examples
```typescript
// tests/preview/measurers/token.test.ts
import { describe, expect, it } from 'vitest';
import { TokenMeasurer } from '../../../src/preview/measurers/token';

describe('TokenMeasurer', () => {
  it('counts tokens correctly', () => {
    const measurer = new TokenMeasurer('gpt-4');
    // "Hello, world!" is typically 4 tokens
    expect(measurer.measure('Hello, world!')).toBeGreaterThan(0);
  });

  it('handles empty string', () => {
    const measurer = new TokenMeasurer();
    expect(measurer.measure('')).toBe(0);
  });
});

// tests/preview/generators/sample.test.ts
import { describe, expect, it } from 'vitest';
import { SampleGenerator } from '../../../src/preview/generators/sample';
import { CharacterMeasurer } from '../../../src/preview/measurers/character';

describe('SampleGenerator', () => {
  const generator = new SampleGenerator(2, 1);
  const measurer = new CharacterMeasurer();

  it('samples arrays with first and last elements', () => {
    const arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const result = generator.generate(arr, { maxSize: 1000, measurer });

    expect(result.text).toContain('1');
    expect(result.text).toContain('2');
    expect(result.text).toContain('10');
    expect(result.text).toContain('7 more');
    expect(result.totalItems).toBe(10);
    expect(result.hasMore).toBe(true);
  });

  it('returns full array when small enough', () => {
    const arr = [1, 2, 3];
    const result = generator.generate(arr, { maxSize: 1000, measurer });

    expect(result.text).toBe('[1,2,3]');
    expect(result.hasMore).toBe(false);
  });
});
```

---

## File Structure
```
src/preview/
├── index.ts              # Re-exports
├── types.ts              # Interfaces and types
├── serialize.ts          # Value to string conversion
├── measurers/
│   ├── index.ts
│   ├── token.ts          # TokenMeasurer
│   └── character.ts      # CharacterMeasurer
└── generators/
    ├── index.ts
    ├── truncate.ts       # TruncateGenerator
    ├── sample.ts         # SampleGenerator
    └── paginate.ts       # PaginateGenerator
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-02](../Task-02/scratchpad.md)
- **Blocks:** Task-04 (RefCache Core - full integration)
- **External Links:**
  - [Python mcp-refcache preview.py](https://github.com/l4b4r4b4b4/mcp-refcache/blob/main/src/mcp_refcache/preview.py)
  - [Python mcp-refcache context.py](https://github.com/l4b4r4b4b4/mcp-refcache/blob/main/src/mcp_refcache/context.py)
  - [tiktoken npm package](https://github.com/dqbd/tiktoken)
  - [OpenAI tokenizer](https://platform.openai.com/tokenizer)
