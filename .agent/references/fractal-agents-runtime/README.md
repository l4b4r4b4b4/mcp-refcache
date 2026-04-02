# fractal-agents-runtime Reference Files

> Copied from `/home/lukes/code/github.com/l4b4r4b4b4/fractal-agents-runtime`
> Date: 2025-07-16

## Purpose

These files serve as the **primary reference** for porting `mcp-refcache` from a Python-only library to a polyglot Bun + Python monorepo. The `fractal-agents-runtime` project successfully implements the same pattern: a single repo housing both a Python app (LangGraph/Robyn) and a TypeScript app (Bun/Hono), orchestrated by Bun workspaces at the root.

## Why This Reference?

`fractal-agents-runtime` demonstrates a **proven, production-tested** pattern for:

- **Bun workspaces** managing TypeScript packages/apps alongside Python
- **Nix FHS dev shell** providing both `bun` and `uv`/`python` in one environment
- **Lefthook** for polyglot git hooks (Python linting + TS type-checking in parallel)
- **Script orchestration** from root `package.json` across both ecosystems
- **Package manager guardrails** (aliases that prevent `pip`/`npm`/`yarn` misuse)
- **Shared CI patterns** for testing both runtimes

## File Inventory

### Root Configuration

| File | Description |
|------|-------------|
| `root-package.json` | Bun workspace root with `apps/*` + `packages/*` patterns, cross-ecosystem scripts |
| `flake.nix` | Nix FHS environment with Bun, Python 3.12, uv, ruff, lefthook, k8s tools |
| `lefthook.yml` | Polyglot git hooks: pre-commit (lint both) + pre-push (test both, no merge commits) |
| `gitignore` | Combined ignore patterns for Node/Bun, Python, IDE, coverage, archive |
| `rules` | `.rules` file showing polyglot AI assistant conventions |
| `CONTRIBUTING.md` | Contributing guide for polyglot monorepo |
| `docker-compose.yml` | Docker Compose for local dev (Postgres, etc.) |

### TypeScript App (`apps/ts/`)

| File | Description |
|------|-------------|
| `ts-app-package.json` | TypeScript app `package.json` — scripts, deps (LangChain, Supabase), Bun build |
| `ts-app-tsconfig.json` | TypeScript config: ESNext, strict, bundler resolution, declaration maps |

### Python App (`apps/python/`)

| File | Description |
|------|-------------|
| `python-app-pyproject.toml` | Python app `pyproject.toml` — uv-managed, hatchling build, coverage config |

### TypeScript Source Examples (`ts-src-examples/`)

These show idiomatic Bun/TypeScript patterns for the same kinds of abstractions `mcp-refcache` needs:

| File | Maps to mcp-refcache | Description |
|------|----------------------|-------------|
| `config.ts` | Configuration/env | Zod-validated config from environment variables |
| `storage-types.ts` | `backends/base.py` | TypeScript interface (protocol) for storage backends |
| `storage-memory.ts` | `backends/memory.py` | In-memory implementation of the storage interface |
| `errors.ts` | Permission/access errors | Custom error classes with HTTP status codes |
| `index.ts` | Server entry point | Bun server startup, middleware composition |
| `storage.test.ts` | `tests/test_backends.py` | Bun test runner patterns for storage backends |
| `auth.test.ts` | `tests/test_access_*.py` | Auth/permission test patterns |

## Key Patterns to Replicate

### 1. Root package.json Workspace Layout

```json
{
  "workspaces": ["apps/*", "packages/*"],
  "scripts": {
    "test:python": "cd apps/python && uv run pytest",
    "test:ts": "cd apps/ts && bun test"
  }
}
```

For `mcp-refcache`, this becomes `packages/python` + `packages/typescript`.

### 2. Nix FHS with Package Manager Guards

The `flake.nix` uses `buildFHSEnv` and aliases `pip`/`npm`/`yarn` to error messages redirecting to `uv`/`bun`. This prevents accidental use of wrong package managers.

### 3. Lefthook Polyglot Hooks

Pre-commit runs Python linting and TypeScript type-checking **in parallel**. Pre-push runs both test suites and rejects merge commits (enforcing rebase workflow).

### 4. TypeScript Interface Pattern (→ Protocol)

The `storage-types.ts` file shows how TypeScript interfaces map to Python `Protocol` classes — the same pattern needed for `CacheBackend`, `Actor`, `PreviewGenerator`, etc.

### 5. Bun Test Runner

`storage.test.ts` and `auth.test.ts` show Bun's built-in test runner (Jest-compatible `describe`/`it`/`expect`) which eliminates the need for Vitest as a separate dependency.

## Differences from mcp-refcache

| Aspect | fractal-agents-runtime | mcp-refcache (target) |
|--------|----------------------|----------------------|
| Layout | `apps/*` (deployable) | `packages/*` (publishable libraries) |
| TS output | Bun app (not published) | npm package (published to registry) |
| Python output | Robyn server app | PyPI package (already published) |
| Test runner | `bun test` | `bun test` (switch from Vitest plan) |
| Build | `bun build` (bundle) | `tsc` (declarations needed for npm) |

## How to Use These References

1. **Task-00 (Monorepo Migration)**: Already complete — used `docproc-platform` pattern. These files validate and refine that work.
2. **Task-01 (TS Package Setup)**: Use `ts-app-package.json` and `ts-app-tsconfig.json` as starting points.
3. **Task-02 (Models & Zod)**: Use `config.ts` for Zod schema patterns.
4. **Task-03 (Backend Protocol)**: Use `storage-types.ts` + `storage-memory.ts` as direct analogs.
5. **Task-06 (Access Control)**: Use `errors.ts` + `auth.test.ts` for error and permission patterns.
6. **Task-10 (Template)**: Use `lefthook.yml` and `flake.nix` patterns for the generated template.
