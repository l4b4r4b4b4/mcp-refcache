# Goal: TypeScript RefCache (mcp-refcache-ts)

> **Status**: 🟡 In Progress
> **Priority**: P1 (High)
> **Created**: 2025-01-30
> **Updated**: 2025-01-30

## Overview

Restructure `mcp-refcache` into a **Bun-powered monorepo** that houses both the Python and TypeScript implementations. The TypeScript implementation (`mcp-refcache` npm package) provides reference-based caching for [FastMCP (TypeScript)](https://github.com/punkpeye/fastmcp) servers, with full feature parity to the Python version.

**Key Decision**: Instead of creating a separate repository, we're converting the existing repo into a monorepo pattern (following `docproc-platform` as reference) that supports both Python (uv) and TypeScript (Bun) in a unified development environment.

### Why TypeScript/Bun?

After extensive experience building custom MCP servers, TypeScript on Bun offers significant advantages:

- **Performance**: Bun starts 4x faster than Node.js, critical for MCP server cold starts
- **Native TypeScript**: No transpilation step needed, first-class `.ts` support
- **Built-in SQLite**: `bun:sqlite` is native and fast, perfect for the SQLite backend
- **Built-in Redis**: Bun has native Redis client support
- **All-in-one**: Runtime, package manager, test runner, bundler in single binary
- **Web APIs**: Native `fetch`, `WebSocket`, `ReadableStream` support
- **Node.js Compatible**: Drop-in replacement for most Node.js code

## Success Criteria

- [ ] `mcp-refcache-ts` npm package published with feature parity to Python v0.2.0
- [ ] TypeScript-first API with full type safety (Zod schemas)
- [ ] Works with FastMCP (TypeScript) by @punkpeye
- [ ] Memory, SQLite, and Redis backends implemented
- [ ] Access control system (Actor, Permission, AccessPolicy)
- [ ] Namespace isolation (public, session, user, custom)
- [ ] Preview generation with token counting (tiktoken-compatible)
- [ ] Async task execution with TaskBackend protocol
- [ ] `fastmcp-ts-template` cookiecutter template repository
- [ ] 80%+ test coverage with Vitest
- [ ] Documentation with API reference and examples
- [ ] Bun-optimized but Node.js compatible

## Context & Background

### The Python Implementation

`mcp-refcache` (Python) provides:

1. **Core RefCache Class** (`cache.py`)
   - `set()` - Store value, return reference
   - `get()` - Get cached response with preview
   - `resolve()` - Get full value (permission-checked)
   - `delete()` - Remove entry
   - `@cache.cached()` decorator for automatic caching

2. **Models** (`models.py`)
   - `CacheReference`, `CacheResponse`, `PaginatedResponse`
   - `PreviewConfig`, `PreviewStrategy`, `SizeMode`
   - `AsyncTaskResponse`, `TaskInfo`, `TaskStatus`, `TaskProgress`

3. **Backends** (`backends/`)
   - `CacheBackend` protocol
   - `MemoryBackend` - In-memory with TTL
   - `SQLiteBackend` - Persistent, cross-process
   - `RedisBackend` - Distributed, multi-server
   - `TaskBackend` protocol for async execution
   - `MemoryTaskBackend` - ThreadPoolExecutor-based

4. **Access Control** (`access/`)
   - `Actor`, `ActorType` (User, Agent, System)
   - `Permission` (READ, WRITE, EXECUTE, DELETE)
   - `AccessPolicy` with separate user/agent permissions
   - `NamespaceResolver` for dynamic namespace resolution
   - `PermissionChecker` for access enforcement

5. **Preview System** (`preview.py`, `context.py`)
   - Token/character-based size limiting
   - Strategies: truncate, sample, paginate
   - tiktoken and HuggingFace tokenizer support

6. **Context Integration** (`context_integration.py`)
   - FastMCP context extraction
   - Dynamic namespace/owner derivation
   - Template expansion for context-scoped caching

### TypeScript MCP Ecosystem

**FastMCP (TypeScript)** by @punkpeye:
- Most popular TypeScript MCP framework (equivalent to Python's FastMCP)
- Built on `@modelcontextprotocol/sdk`
- Features: Tools, Resources, Prompts, Authentication, Sessions, HTTP Streaming
- Zod-based schema validation
- `fastmcp-boilerplate` exists but is minimal (no caching integration)

**@modelcontextprotocol/sdk** (Official):
- v2 in development (Q1 2026 stable release)
- Packages: `@modelcontextprotocol/server`, `@modelcontextprotocol/client`
- Middleware: `@modelcontextprotocol/node`, `@modelcontextprotocol/express`, `@modelcontextprotocol/hono`

### Bun-Specific Advantages

| Feature | Bun | Node.js |
|---------|-----|---------|
| Startup time | 4x faster | Baseline |
| SQLite | Native `bun:sqlite` | External package |
| TypeScript | Native execution | Requires tsx/ts-node |
| Package install | 30x faster | Baseline |
| Test runner | Built-in (Jest-compatible) | External (Jest/Vitest) |
| HTTP server | Native `Bun.serve()` | External (Express, etc.) |

## Constraints & Requirements

### Hard Requirements

- **TypeScript-first**: All exports must be typed, no `any` types in public API
- **Bun-optimized**: Use native Bun APIs where available (`bun:sqlite`, etc.)
- **Node.js compatible**: Must work with Node.js 20+ for users not using Bun
- **FastMCP integration**: Seamless decorator/middleware pattern
- **Zod schemas**: Use Zod for runtime validation (matches FastMCP pattern)
- **ESM only**: Modern ES modules, no CommonJS
- **Semantic versioning**: Start at v0.1.0

### Soft Requirements

- **API parity**: Match Python API where TypeScript idioms allow
- **Minimal dependencies**: Only essential packages
- **Tree-shakeable**: Support partial imports for smaller bundles
- **Vitest tests**: Jest-compatible but faster

### Out of Scope (v0.1.0)

- HatchetTaskBackend (future enhancement)
- HuggingFace tokenizer adapter (tiktoken only)
- Compression middleware
- Cache warming strategies

## Approach

### Phase 1: Core Library (Tasks 01-05)

1. **Project Setup** - Monorepo structure, Bun workspace, tooling
2. **Models & Types** - Zod schemas for all data structures
3. **Backend Protocol** - Interface and MemoryBackend implementation
4. **RefCache Core** - Main cache class with set/get/resolve/delete
5. **Preview System** - Token counting and preview generation

### Phase 2: Advanced Features (Tasks 06-08)

6. **Access Control** - Actor, Permission, Policy, Namespace system
7. **Additional Backends** - SQLite and Redis implementations
8. **Async Task System** - TaskBackend protocol and MemoryTaskBackend

### Phase 3: Integration & Template (Tasks 09-10)

9. **FastMCP Integration** - Decorator, middleware, context helpers
10. **Template Repository** - `fastmcp-ts-template` cookiecutter equivalent

## Tasks

| Task ID | Description | Status | Depends On |
|---------|-------------|--------|------------|
| Task-00 | Monorepo Migration (Bun + Python) | 🟢 Complete | - |
| Task-01 | Project Setup & Tooling | ⚪ Not Started | Task-00 |
| Task-02 | Models & Zod Schemas | ⚪ Not Started | Task-01 |
| Task-03 | Backend Protocol & MemoryBackend | ⚪ Not Started | Task-02 |
| Task-04 | RefCache Core Implementation | ⚪ Not Started | Task-03 |
| Task-05 | Preview System (Token Counting) | ⚪ Not Started | Task-02 |
| Task-06 | Access Control System | ⚪ Not Started | Task-02 |
| Task-07 | SQLite & Redis Backends | ⚪ Not Started | Task-03 |
| Task-08 | Async Task System | ⚪ Not Started | Task-03, Task-04 |
| Task-09 | FastMCP Integration | ⚪ Not Started | Task-04, Task-06 |
| Task-10 | Template Repository | ⚪ Not Started | Task-09 |

**Note**: Task-00 restructures the repo into a monorepo before TypeScript development begins.

## Architecture

### Monorepo Structure (Bun + Python)

```
mcp-refcache/                    # Existing repo, restructured
├── .agent/                      # AI assistant workspace (unchanged)
├── .github/workflows/
│   ├── ci.yml                   # Updated for both ecosystems
│   └── publish-python.yml       # Python PyPI publishing
│   └── publish-npm.yml          # npm publishing (new)
├── packages/
│   ├── python/                  # Python implementation (moved from root)
│   │   ├── src/mcp_refcache/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── uv.lock
│   └── typescript/              # TypeScript implementation (new)
│       ├── src/
│       │   ├── index.ts
│       │   ├── cache.ts
│       │   ├── models/
│       │   ├── backends/
│       │   ├── access/
│       │   ├── preview/
│       │   └── fastmcp/
│       ├── tests/
│       ├── package.json
│       └── tsconfig.json
├── examples/
│   ├── fastmcp-template/        # Python template (unchanged)
│   └── fastmcp-ts-template/     # TS template (Task-10)
├── archive/
│   └── bun-python-monorepo-reference/  # Reference files from docproc-platform
├── package.json                 # Bun workspace root
├── tsconfig.json                # TypeScript base config
├── flake.nix                    # Nix dev environment (both ecosystems)
├── flake.lock
└── README.md
```

### Reference: docproc-platform Pattern

We're following the pattern established in `docproc-platform` which successfully manages:
- Bun workspaces at root level
- Python apps with independent `pyproject.toml` + `uv.lock`
- Shared Nix flake providing both Bun and Python/uv
- Script orchestration across ecosystems

Reference files copied to: `archive/bun-python-monorepo-reference/`

### TypeScript API Design

```typescript
// Main RefCache class
import { RefCache, MemoryBackend, AccessPolicy, Permission } from 'mcp-refcache';

const cache = new RefCache({
  name: 'my-cache',
  backend: new MemoryBackend(),
  defaultTtl: 3600,
  defaultPolicy: AccessPolicy.public(),
});

// Store and retrieve
const ref = await cache.set('user_data', { name: 'Alice', items: [1, 2, 3] });
const response = await cache.get(ref.refId);
const value = await cache.resolve(ref.refId);

// FastMCP integration
import { FastMCP } from 'fastmcp';
import { cached, withRefCache } from 'mcp-refcache/fastmcp';

const server = new FastMCP({ name: 'My Server', version: '1.0.0' });
const cache = new RefCache();

server.addTool({
  name: 'get_large_dataset',
  description: 'Fetch large dataset',
  parameters: z.object({ query: z.string() }),
  execute: cached(cache, { namespace: 'session' }, async (args) => {
    return await fetchHugeData(args.query);
  }),
});
```

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| FastMCP API changes | High | Medium | Pin FastMCP version, follow releases closely |
| Bun-specific APIs break Node.js | High | Low | Abstract behind interfaces, CI tests both runtimes |
| tiktoken-js performance | Medium | Medium | Consider WASM alternative if slow |
| MCP SDK v2 breaking changes | Medium | High | Build against v1.x, plan v2 migration |

## Dependencies

### Upstream (This Goal Depends On)

- Python mcp-refcache v0.2.0 feature complete (reference implementation)
- FastMCP (TypeScript) stable API

### Downstream (Depends on This Goal)

- TypeScript MCP server projects
- `fastmcp-ts-template` (Task-10)

## npm Packages to Use

| Package | Purpose | Alternative |
|---------|---------|-------------|
| `zod` | Schema validation | - (required by FastMCP) |
| `fastmcp` | MCP framework integration | - |
| `tiktoken` | Token counting | `js-tiktoken` (lighter) |
| `ioredis` | Redis client | `redis` (official) |
| `better-sqlite3` | Node.js SQLite | `bun:sqlite` (Bun) |
| `lru-cache` | Memory backend LRU | Custom implementation |
| `nanoid` | ID generation | `uuid` |

## Notes & Decisions

### Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-01-30 | Use Bun as primary runtime | 4x faster startup, native TS, built-in SQLite/Redis |
| 2025-01-30 | Target FastMCP (TypeScript) | Most popular TS MCP framework, active development |
| 2025-01-30 | ESM-only, no CommonJS | Modern standard, better tree-shaking |
| 2025-01-30 | Zod for schemas | Matches FastMCP pattern, excellent TS integration |
| 2025-01-30 | Monorepo with both languages | Single repo, easier feature parity, shared docs |
| 2025-01-30 | Follow docproc-platform pattern | Proven Bun+Python monorepo structure |

### Open Questions

- [x] ~~Separate repo or monorepo?~~ → Monorepo (decided 2025-01-30)
- [ ] Should we support Deno as well? (Lower priority)
- [ ] tiktoken vs js-tiktoken vs WASM tokenizer?
- [ ] Exact decorator API for FastMCP integration?
- [ ] Should template use Bun or remain Node.js compatible?

## References

### Python Implementation
- [mcp-refcache](https://github.com/l4b4r4b4b4/mcp-refcache) - Source of truth
- [fastmcp-template](https://github.com/l4b4r4b4b4/fastmcp-template) - Python template

### TypeScript MCP Ecosystem
- [FastMCP (TypeScript)](https://github.com/punkpeye/fastmcp) - Target framework
- [fastmcp-boilerplate](https://github.com/punkpeye/fastmcp-boilerplate) - Minimal boilerplate
- [@modelcontextprotocol/sdk](https://github.com/modelcontextprotocol/typescript-sdk) - Official SDK

### Bun
- [Bun Documentation](https://bun.sh/docs) - Runtime docs
- [bun:sqlite](https://bun.sh/docs/api/sqlite) - Native SQLite
- [Bun.serve](https://bun.sh/docs/api/http) - HTTP server

### TypeScript Libraries
- [Zod](https://zod.dev) - Schema validation
- [ioredis](https://github.com/redis/ioredis) - Redis client
- [tiktoken](https://github.com/dqbd/tiktoken) - Token counting
- [lru-cache](https://github.com/isaacs/node-lru-cache) - LRU implementation
