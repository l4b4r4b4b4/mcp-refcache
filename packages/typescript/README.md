# mcp-refcache

Reference-based caching for [FastMCP](https://github.com/punkpeye/fastmcp) servers (TypeScript/Bun).

> **Status**: 🚧 In Development — This is the TypeScript port of the [Python mcp-refcache](https://pypi.org/project/mcp-refcache/) library, targeting full feature parity.

## Overview

`mcp-refcache` solves a fundamental problem in MCP (Model Context Protocol) servers: **large data doesn't fit in LLM context windows**. Instead of stuffing thousands of rows into a tool response, `mcp-refcache` stores the data and returns a compact **reference** that the LLM can pass to other tools.

### The Problem

```
Tool returns 50,000 rows → LLM context window overflows → conversation breaks
```

### The Solution

```
Tool returns ref_id → LLM passes ref_id to next tool → next tool resolves full data internally
```

## Installation

```bash
# Bun (recommended)
bun add mcp-refcache

# npm
npm install mcp-refcache

# pnpm
pnpm add mcp-refcache
```

## Quick Start

```typescript
import { RefCache, MemoryBackend } from "mcp-refcache";

const cache = new RefCache({ name: "my-server" });

// Store large data, get a compact reference
const ref = await cache.set("users", fetchAllUsers());
// ref.refId → "my-server:a1b2c3d4e5f6"

// Retrieve with preview (fits in context window)
const response = await cache.get(ref.refId);
// { preview: [...first 50 items...], totalItems: 50000, refId: "..." }

// Resolve full data (for tool-to-tool passing)
const fullData = await cache.resolve(ref.refId);
```

### With FastMCP

```typescript
import { FastMCP } from "fastmcp";
import { z } from "zod";
import { RefCache } from "mcp-refcache";
import { cached, cacheInstructions } from "mcp-refcache/fastmcp";

const cache = new RefCache({ name: "my-server" });

const server = new FastMCP({
  name: "My Server",
  version: "1.0.0",
  instructions: cacheInstructions(),
});

server.addTool({
  name: "get_large_dataset",
  description: "Fetch a large dataset",
  parameters: z.object({ query: z.string() }),
  execute: cached(cache, { namespace: "session" }, async (args) => {
    return await fetchHugeDataset(args.query);
  }),
});
```

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| Core RefCache | 🚧 | `set()`, `get()`, `resolve()`, `delete()` |
| Memory Backend | 🚧 | In-memory cache with TTL support |
| SQLite Backend | 🚧 | Persistent cache via `bun:sqlite` |
| Redis Backend | 🚧 | Distributed cache via `ioredis` |
| Access Control | 🚧 | Actor, Permission, AccessPolicy |
| Namespaces | 🚧 | public, session, user, custom isolation |
| Preview System | 🚧 | Truncate, sample, paginate strategies |
| Token Counting | 🚧 | `js-tiktoken` for accurate context limits |
| Async Tasks | 🚧 | Background execution with polling |
| FastMCP Integration | 🚧 | `cached()` wrapper, instructions helper |

## Feature Parity with Python

This package targets full feature parity with the [Python `mcp-refcache`](https://pypi.org/project/mcp-refcache/) library (v0.2.0). The Python implementation is the reference — if behavior differs, the Python version is considered correct unless explicitly documented otherwise.

## Development

This package lives in the `mcp-refcache` monorepo under `packages/typescript/`.

```bash
# From repo root
bun install

# Run tests
cd packages/typescript
bun test

# Type-check
bunx tsc --noEmit

# Build for publishing
bun run build
```

### Monorepo Structure

```
mcp-refcache/
├── packages/
│   ├── python/          # Python implementation (PyPI)
│   └── typescript/      # This package (npm)
├── examples/
│   ├── fastmcp-template/       # Python template
│   └── fastmcp-ts-template/    # TypeScript template (planned)
├── package.json         # Bun workspace root
└── flake.nix            # Nix dev environment
```

## License

[MIT](./LICENSE)