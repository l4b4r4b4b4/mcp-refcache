# Goal: TypeScript RefCache (mcp-refcache-ts)

> **Status**: 🟡 In Progress
> **Priority**: P1 (High)
> **Created**: 2025-01-30
> **Updated**: 2025-07-16

## Overview

Restructure `mcp-refcache` into a **Bun-powered monorepo** that houses both the Python and TypeScript implementations. The TypeScript implementation (`mcp-refcache` npm package) provides reference-based caching for [FastMCP (TypeScript)](https://github.com/punkpeye/fastmcp) servers, with full feature parity to the Python version. This extends to the `fastmcp-template` as well — a TypeScript variant of the Cookiecutter template for scaffolding new MCP servers with refcache integration.

**Key Decision**: Instead of creating a separate repository, we're converting the existing repo into a monorepo pattern that supports both Python (uv) and TypeScript (Bun) in a unified development environment.

**Primary Reference**: [`fractal-agents-runtime`](file:///home/lukes/code/github.com/l4b4r4b4b4/fractal-agents-runtime) — a proven polyglot monorepo housing both Python (Robyn/LangGraph) and TypeScript (Bun/Hono) runtimes with the same Bun+uv+Nix pattern. Reference files copied to `.agent/references/fractal-agents-runtime/`.

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

- [ ] `mcp-refcache` npm package published with feature parity to Python v0.2.0
- [ ] TypeScript-first API with full type safety (Zod schemas)
- [ ] Works with FastMCP (TypeScript) by @punkpeye
- [ ] Memory, SQLite, and Redis backends implemented
- [ ] Access control system (Actor, Permission, AccessPolicy)
- [ ] Namespace isolation (public, session, user, custom)
- [ ] Preview generation with token counting (tiktoken-compatible)
- [ ] Async task execution with TaskBackend protocol
- [ ] `fastmcp-ts-template` cookiecutter template repository (port of `fastmcp-template`)
- [ ] 80%+ test coverage with `bun test` (built-in, Jest-compatible)
- [ ] Lefthook polyglot git hooks (lint + test both ecosystems)
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
- **`bun test` only**: Use Bun's built-in test runner (Jest-compatible), no Vitest dependency

### Soft Requirements

- **API parity**: Match Python API where TypeScript idioms allow
- **Minimal dependencies**: Only essential packages
- **Tree-shakeable**: Support partial imports for smaller bundles
- **Lefthook for git hooks**: Polyglot pre-commit and pre-push (follow fractal-agents-runtime pattern)

### Out of Scope (v0.1.0)

- HatchetTaskBackend (future enhancement)
- HuggingFaceAdapter tokenizer (tiktoken only)
- Compression middleware
- Cache warming strategies

## Approach

### Phase 1: Monorepo Infra (Task-00, done) + Core Library (Tasks 01-05)

0. **Monorepo Migration** ✅ — Bun workspaces, Nix FHS, Python moved to `packages/python/`
1. **Project Setup** — `packages/typescript/`, `bun test` config, lefthook, CI
2. **Models & Types** — Zod schemas for all data structures
3. **Backend Protocol** — Interface and MemoryBackend implementation
4. **RefCache Core** — Main cache class with set/get/resolve/delete
5. **Preview System** — Token counting and preview generation

### Phase 2: Advanced Features (Tasks 06-08)

6. **Access Control** — Actor, Permission, Policy, Namespace system
7. **Additional Backends** — SQLite (`bun:sqlite`) and Redis implementations
8. **Async Task System** — TaskBackend protocol and MemoryTaskBackend

### Phase 3: Integration & Template (Tasks 09-10)

9. **FastMCP Integration** — `cached()` wrapper, context helpers, instructions
10. **Template Repository** — `fastmcp-ts-template` (Cookiecutter, port of Python template)

## Tasks

| Task ID | Description | Status | Depends On |
|---------|-------------|--------|------------|
| Task-00 | Monorepo Migration (Bun + Python) | 🟢 Complete | - |
| Task-01 | Project Setup & Tooling (`bun test`, lefthook, CI) | ⚪ Not Started | Task-00 |
| Task-02 | Models & Zod Schemas | ⚪ Not Started | Task-01 |
| Task-03 | Backend Protocol & MemoryBackend | ⚪ Not Started | Task-02 |
| Task-04 | RefCache Core Implementation | ⚪ Not Started | Task-03 |
| Task-05 | Preview System (Token Counting) | ⚪ Not Started | Task-02 |
| Task-06 | Access Control System | ⚪ Not Started | Task-02 |
| Task-07 | SQLite (`bun:sqlite`) & Redis Backends | ⚪ Not Started | Task-03 |
| Task-08 | Async Task System | ⚪ Not Started | Task-03, Task-04 |
| Task-09 | FastMCP Integration | ⚪ Not Started | Task-04, Task-06 |
| Task-10 | Template Repository (`fastmcp-ts-template`) | ⚪ Not Started | Task-09 |

**Note**: Task-00 restructured the repo into a monorepo (complete). Task-01 is the next actionable step.

### Python ↔ TypeScript Module Mapping

This table maps every Python module to its planned TypeScript counterpart for feature parity tracking:

| Python Module | TypeScript File | Key Types/Exports | Notes |
|--------------|----------------|-------------------|-------|
| `models.py` | `src/models/` | `CacheReference`, `CacheResponse`, `PaginatedResponse`, `PreviewConfig`, `PreviewStrategy`, `SizeMode`, `AsyncTaskResponse`, `TaskInfo`, `TaskStatus`, `TaskProgress` | Zod schemas + inferred types |
| `permissions.py` | `src/access/permissions.ts` | `Permission` (flag enum), `AccessPolicy`, policy presets | Use bitwise flags or enum set |
| `access/actor.py` | `src/access/actor.ts` | `Actor` (interface), `DefaultActor`, `ActorType`, `resolve_actor` | Interface = Protocol |
| `access/checker.py` | `src/access/checker.ts` | `PermissionChecker` (interface), `DefaultPermissionChecker`, `PermissionDenied` | |
| `access/namespace.py` | `src/access/namespace.ts` | `NamespaceResolver` (interface), `DefaultNamespaceResolver`, `NamespaceInfo` | |
| `backends/base.py` | `src/backends/types.ts` | `CacheBackend` (interface), `CacheEntry` | See `storage-types.ts` reference |
| `backends/memory.py` | `src/backends/memory.ts` | `MemoryBackend` | See `storage-memory.ts` reference |
| `backends/sqlite.py` | `src/backends/sqlite.ts` | `SQLiteBackend` | Use `bun:sqlite` native API |
| `backends/redis.py` | `src/backends/redis.ts` | `RedisBackend` | Optional, use `ioredis` |
| `backends/task_base.py` | `src/backends/task-types.ts` | `TaskBackend` (interface) | |
| `backends/task_memory.py` | `src/backends/task-memory.ts` | `MemoryTaskBackend` | Use `Worker` or `Promise` pool |
| `cache.py` | `src/cache.ts` | `RefCache` class | Core — largest file |
| `preview.py` | `src/preview/` | `PreviewGenerator`, `SampleGenerator`, `PaginateGenerator`, `TruncateGenerator` | |
| `context.py` | `src/context/` | `SizeMeasurer`, `TokenMeasurer`, `CharacterMeasurer`, tokenizer adapters | |
| `context_integration.py` | `src/fastmcp/context.ts` | `deriveActorFromContext`, `expandTemplate`, `getContextValues` | FastMCP-specific |
| `resolution.py` | `src/resolution.ts` | `RefResolver`, `isRefId`, `resolveRefs`, `resolveKwargs`, `CircularReferenceError` | |
| `fastmcp/instructions.py` | `src/fastmcp/instructions.ts` | `cacheInstructions()` | |
| `fastmcp/admin_tools.py` | `src/fastmcp/admin-tools.ts` | Admin tool registrations | |
| `__init__.py` | `src/index.ts` | Re-exports all public API | |

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

### Reference: fractal-agents-runtime Pattern

We're following the pattern established in `fractal-agents-runtime` which successfully manages:
- Bun workspaces at root level (`apps/*`, `packages/*`)
- Python app with independent `pyproject.toml` + `uv.lock` + `.venv`
- TypeScript app with Bun build, `bun test`, strict TypeScript
- Unified `flake.nix` (Nix FHS) providing both Bun and Python/uv
- **Lefthook** for polyglot git hooks (pre-commit: lint both; pre-push: test both + reject merge commits)
- Package manager guardrails (aliases `pip` → error, `npm` → error, etc.)
- Script orchestration across ecosystems from root `package.json`

Reference files copied to: `.agent/references/fractal-agents-runtime/`

Previous reference (docproc-platform) also in: `archive/bun-python-monorepo-reference/`

### Key Differences from fractal-agents-runtime

| Aspect | fractal-agents-runtime | mcp-refcache |
|--------|----------------------|--------------|
| TS layout | `apps/ts/` (deployable app) | `packages/typescript/` (publishable npm library) |
| TS output | Bun app binary | npm package with `.d.ts` declarations |
| Python output | Robyn server app | PyPI package (already published) |
| Test runner | `bun test` | `bun test` (TS) + `uv run pytest` (Python) |
| Build | `bun build` (bundle) | `tsc` (needs declarations for npm consumers) |
| Git hooks | Lefthook | Lefthook (adopt from reference, replace pre-commit) |

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
| tiktoken-js performance | Medium | Medium | Consider `js-tiktoken` (lighter WASM) as alternative |
| MCP SDK v2 breaking changes | Medium | High | Build against v1.x, plan v2 migration |
| `bun:sqlite` not available in Node.js | Medium | Certain | Provide `better-sqlite3` fallback or document Bun-only |
| Lefthook migration from pre-commit | Low | Low | Both tools are well-documented; gradual migration |

## Dependencies

### Upstream (This Goal Depends On)

- Python mcp-refcache v0.2.0 feature complete (reference implementation)
- FastMCP (TypeScript) stable API

### Downstream (Depends on This Goal)

- TypeScript MCP server projects
- `fastmcp-ts-template` (Task-10)

## npm Packages to Use

| Package | Purpose | Alternative | Notes |
|---------|---------|-------------|-------|
| `zod` | Schema validation | - | Required by FastMCP |
| `fastmcp` | MCP framework integration | `@modelcontextprotocol/sdk` | Peer dependency (optional) |
| `js-tiktoken` | Token counting (WASM) | `tiktoken` (native) | Lighter, no native deps |
| `ioredis` | Redis client | `redis` (official) | Optional `[redis]` extra |
| `nanoid` | ID generation | `crypto.randomUUID()` | Consider Bun built-in |
| `lefthook` | Git hooks (dev) | `husky` | Polyglot, fast, no Node dep |

**Not needed** (use Bun built-ins instead):
- ~~`better-sqlite3`~~ → `bun:sqlite` (native, zero-dep)
- ~~`vitest`~~ → `bun test` (built-in, Jest-compatible)
- ~~`lru-cache`~~ → Simple `Map` with TTL eviction (no external dep for MVP)

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
| 2025-07-16 | `bun test` over Vitest | Bun's built-in test runner is Jest-compatible, zero-dep, faster. Confirmed by fractal-agents-runtime success. |
| 2025-07-16 | Adopt Lefthook (replace pre-commit) | Polyglot git hooks matching fractal-agents-runtime. Parallel pre-commit (lint both), pre-push (test both + reject merge commits). |
| 2025-07-16 | `fractal-agents-runtime` as primary reference | More directly analogous than docproc-platform: same author, same Bun+Python+Nix pattern, proven TS patterns for interfaces/storage/auth. |
| 2025-07-16 | `js-tiktoken` over `tiktoken` | Lighter WASM build, no native compilation, works in both Bun and Node.js. |
| 2025-07-16 | Feature branch `feat/monorepo-restructure` | All Goal 06 work happens on this branch, merged via PR when stable. |

### Open Questions

- [x] ~~Separate repo or monorepo?~~ → Monorepo (decided 2025-01-30)
- [x] ~~Vitest or bun test?~~ → `bun test` (decided 2025-07-16)
- [x] ~~tiktoken vs js-tiktoken?~~ → `js-tiktoken` (decided 2025-07-16)
- [ ] Should we support Deno as well? (Lower priority, probably not for v0.1.0)
- [ ] Exact decorator API for FastMCP integration? (Task-09 will finalize)
- [ ] Should template use Bun or remain Node.js compatible? (Bun-first, Node.js fallback)
- [ ] npm package name: `mcp-refcache` or `@mcp-refcache/core`? (Check npm registry availability)

## References

### Monorepo Reference (Primary)
- **fractal-agents-runtime** — `/home/lukes/code/github.com/l4b4r4b4b4/fractal-agents-runtime`
- Reference files: `.agent/references/fractal-agents-runtime/` (see README there for file inventory)
- Key patterns: Bun workspaces, Lefthook, Nix FHS, TypeScript interfaces, `bun test`

### Python Implementation (Source of Truth)
- [mcp-refcache](https://github.com/l4b4r4b4b4/mcp-refcache) — This repo, `packages/python/`
- [fastmcp-template](./examples/fastmcp-template/) — Python Cookiecutter template (to be ported in Task-10)

### TypeScript MCP Ecosystem
- [FastMCP (TypeScript)](https://github.com/punkpeye/fastmcp) — Target framework (v2.14.5, PyPI: `fastmcp`)
- [fastmcp-boilerplate](https://github.com/punkpeye/fastmcp-boilerplate) — Minimal boilerplate
- [@modelcontextprotocol/sdk](https://github.com/modelcontextprotocol/typescript-sdk) — Official SDK (v1.x)

### Bun
- [Bun Documentation](https://bun.sh/docs) — Runtime docs
- [bun:sqlite](https://bun.sh/docs/api/sqlite) — Native SQLite
- [bun test](https://bun.sh/docs/cli/test) — Built-in test runner (Jest-compatible)
- [Bun Workspaces](https://bun.sh/docs/install/workspaces) — Monorepo support

### TypeScript Libraries
- [Zod](https://zod.dev) — Schema validation
- [ioredis](https://github.com/redis/ioredis) — Redis client
- [js-tiktoken](https://github.com/dqbd/tiktoken/tree/main/js) — Token counting (WASM)
- [Lefthook](https://github.com/evilmartians/lefthook) — Polyglot git hooks

### Previous Reference (Secondary)
- docproc-platform files: `archive/bun-python-monorepo-reference/`
