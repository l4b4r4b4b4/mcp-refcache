# Task-01: TypeScript Package Setup & Tooling

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [x] Complete ✅ (2025-07-16)

## Objective
Set up the TypeScript package (`packages/typescript/`) within the restructured monorepo, including TypeScript configuration, `bun test` runner, lefthook polyglot git hooks, and CI/CD pipeline integration.

**Prerequisite**: Task-00 (Monorepo Migration) must be complete first. ✅

---

## Context
Task-00 restructured the repo into a Bun+Python monorepo. The root already has `package.json` with workspaces and `flake.nix` with Bun support. This task sets up the TypeScript package within `packages/typescript/` and adds polyglot tooling (lefthook) following the `fractal-agents-runtime` reference pattern.

**Key reference**: `.agent/references/fractal-agents-runtime/` — see `ts-app-package.json`, `ts-app-tsconfig.json`, `lefthook.yml`, and `ts-src-examples/` for proven patterns.

## Acceptance Criteria
- [ ] `packages/typescript/` directory created with proper structure
- [ ] TypeScript 5.x configured with strict mode (extends root tsconfig)
- [ ] `bun test` configured (built-in Jest-compatible runner, zero external deps)
- [ ] Lefthook installed and configured for polyglot git hooks (replaces pre-commit)
- [ ] GitHub Actions CI workflow for lint/test/build (both ecosystems)
- [ ] Package.json with proper exports and type declarations
- [ ] Root `package.json` scripts updated for both ecosystems
- [ ] README with project overview and development setup
- [ ] LICENSE file (MIT)
- [ ] `.gitignore` properly configured
- [ ] Dual runtime support (Bun + Node.js) verified

---

## Approach
Build on the monorepo structure created in Task-00. Create the TypeScript package within `packages/typescript/`, add `bun test` for testing, install lefthook for polyglot git hooks, and integrate with the existing workspace configuration.

### Steps

1. **Create TypeScript package directory**
   ```bash
   mkdir -p packages/typescript/src packages/typescript/tests
   ```

2. **Create package.json** (see Commands & Snippets below)
   - Name: `mcp-refcache`
   - Use `bun test` (built-in, no Vitest dependency)
   - Peer dependency on `fastmcp` (optional)

3. **Link to workspace** (auto-detected from root `package.json` workspaces)
   ```bash
   cd ../..  # back to repo root
   bun install
   ```

4. **Configure TypeScript**
   - Extend root `tsconfig.json` (already created in Task-00)
   - Package-specific `tsconfig.json` in `packages/typescript/`
   - `moduleResolution: "bundler"`, `outDir: "dist"`, declarations enabled

5. **Set up `bun test`**
   - No external deps needed — Bun's built-in test runner is Jest-compatible
   - Uses `describe`, `it`, `expect` from `bun:test`
   - Create `tests/index.test.ts` as smoke test
   - See `.agent/references/fractal-agents-runtime/ts-src-examples/storage.test.ts` for pattern

6. **Install and configure Lefthook** (replaces `.pre-commit-config.yaml`)
   ```bash
   # From repo root
   bun add -D lefthook
   # lefthook.yml at repo root
   ```
   - Pre-commit: Python ruff lint + TS type-check (parallel)
   - Pre-push: Python tests + TS tests + reject merge commits (parallel)
   - Follow `.agent/references/fractal-agents-runtime/lefthook.yml` pattern

7. **Update root package.json scripts**
   - Add `postinstall: lefthook install`
   - Ensure `test:ts`, `test:py`, `lint:ts`, `lint:py` all work

8. **Create GitHub Actions CI workflow**
   - Matrix testing: Bun + Node.js 22
   - Steps: lint, type-check, test, build
   - Both Python and TypeScript in single workflow

9. **Set up package exports for npm publishing**
   ```json
   {
     "exports": {
       ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js" },
       "./fastmcp": { "types": "./dist/fastmcp/index.d.ts", "import": "./dist/fastmcp/index.js" }
     },
     "files": ["dist", "README.md", "LICENSE"]
   }
   ```

10. **Create initial `src/index.ts`** — placeholder re-export barrel file

---

## Project Structure

After Task-00, the repo structure is:
```
mcp-refcache/
├── packages/
│   ├── python/              # Existing Python implementation
│   │   ├── src/mcp_refcache/
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── typescript/          # NEW: This task creates this
│       ├── src/
│       │   └── index.ts
│       ├── tests/
│       │   └── index.test.ts
│       ├── package.json
│       └── tsconfig.json
├── package.json             # Root (from Task-00)
├── tsconfig.json            # Root (from Task-00)
├── lefthook.yml             # NEW: Polyglot git hooks
├── flake.nix                # Updated in Task-00
└── ...
```

**Note**: No `vitest.config.ts` — we use `bun test` directly (zero-config for `.test.ts` files).

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with initial approach |
| 2025-07-16 | Updated: Vitest → `bun test`, added Lefthook, added fractal-agents-runtime reference |
| 2025-07-16 | **Completed**: Scaffolded `packages/typescript/`, `bun test` (3 pass), lefthook, CI, build verified |

### Key Decisions

1. **`bun test` over Vitest**: Bun's built-in test runner is Jest-compatible (`describe`/`it`/`expect`), zero external deps, and faster. Confirmed working in fractal-agents-runtime. Import from `bun:test`.

2. **Lefthook over pre-commit**: Pre-commit (Python tool) only handles Python hooks well. Lefthook is a single Go binary that handles polyglot hooks natively. fractal-agents-runtime uses it successfully for parallel Python+TS linting and testing.

3. **No ESLint for v0.1.0**: TypeScript strict mode + `bunx tsc --noEmit` provides sufficient type safety. ESLint can be added later if needed. This keeps dev deps minimal (fractal-agents-runtime uses the same approach).

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-00: Monorepo Migration | ✅ Complete | Repo restructured, Python in `packages/python/` |

---

## Commands & Snippets

### packages/typescript/package.json
```json
{
  "name": "mcp-refcache",
  "version": "0.1.0",
  "type": "module",
  "description": "Reference-based caching for FastMCP servers",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    },
    "./fastmcp": {
      "types": "./dist/fastmcp/index.d.ts",
      "import": "./dist/fastmcp/index.js"
    }
  },
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "test": "bun test",
    "test:watch": "bun test --watch",
    "lint": "bunx tsc --noEmit",
    "typecheck": "bunx tsc --noEmit"
  },
  "dependencies": {
    "zod": "^3.24.0"
  },
  "devDependencies": {
    "@types/bun": "latest",
    "typescript": "^5.7.0"
  },
  "peerDependencies": {
    "fastmcp": ">=1.27.0"
  },
  "peerDependenciesMeta": {
    "fastmcp": { "optional": true }
  },
  "files": ["dist", "README.md", "LICENSE"],
  "repository": {
    "type": "git",
    "url": "https://github.com/l4b4r4b4b4/mcp-refcache",
    "directory": "packages/typescript"
  },
  "publishConfig": {
    "access": "public"
  },
  "keywords": [
    "mcp",
    "fastmcp",
    "cache",
    "reference",
    "context",
    "llm",
    "agent",
    "bun"
  ]
}
```

### Root lefthook.yml
```yaml
# Lefthook — Polyglot git hooks for mcp-refcache monorepo
# Reference: .agent/references/fractal-agents-runtime/lefthook.yml

pre-commit:
  parallel: true
  commands:
    python-lint:
      root: packages/python/
      glob: "*.py"
      run: uv run ruff check --fix {staged_files} && uv run ruff format {staged_files}
      stage_fixed: true

    ts-typecheck:
      root: packages/typescript/
      glob: "*.ts"
      run: bunx tsc --noEmit

pre-push:
  parallel: true
  commands:
    no-merge-commits:
      run: |
        MERGE_COMMITS=$(git log --merges --oneline @{upstream}..HEAD 2>/dev/null)
        if [ -n "$MERGE_COMMITS" ]; then
          echo "❌ Merge commits detected — use rebase instead:"
          echo "$MERGE_COMMITS"
          exit 1
        fi

    python-test:
      root: packages/python/
      run: uv run pytest -q

    ts-test:
      root: packages/typescript/
      run: bun test
```

### packages/typescript/tsconfig.json
```json
{
  "extends": "../../tsconfig.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src",
    "declaration": true,
    "declarationMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "tests"]
}
```

### GitHub Actions CI (Polyglot)
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  python:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: packages/python
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest --cov

  typescript:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: packages/typescript
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: cd ../.. && bun install
      - run: bunx tsc --noEmit
      - run: bun test
      - run: bun run build
```

---

## Verification
_How to confirm this task is complete._

```bash
# From repo root on feat/monorepo-restructure branch

# 1. Install dependencies (both ecosystems)
bun install
cd packages/python && uv sync && cd ../..

# 2. TypeScript checks pass
cd packages/typescript
bunx tsc --noEmit        # Type-check
bun test                 # Tests pass
bun run build            # Build succeeds
ls -la dist/             # index.js, index.d.ts exist
cd ../..

# 3. Python still works
bun run test:py          # Python tests still pass

# 4. Root scripts work
bun run test             # Runs both TS + Python tests
bun run lint             # Lints both ecosystems

# 5. Lefthook installed
bunx lefthook run pre-commit  # Runs lint hooks
bunx lefthook run pre-push    # Runs test hooks

# 6. Smoke test: import works
echo 'import { version } from "mcp-refcache"; console.log(version);' | bun run -
```

### Verification Results (2025-07-16)

All checks passed:

| Check | Result | Details |
|-------|--------|---------|
| `bun install` | ✅ | 12 packages installed (431ms) |
| `bunx tsc --noEmit` | ✅ | Clean (0 errors) |
| `bun test` | ✅ | 3 pass, 0 fail (11ms) |
| `bun run build` | ✅ | `dist/index.js` + `dist/index.d.ts` + source maps |
| `bun run test:py` | ✅ | 718 passed, 39 skipped (13.86s) |
| `bun run test` (root) | ✅ | Both TS + Python pass |
| `bun run lint:ts` | ✅ | `tsc --noEmit` clean |
| `lefthook install` | ✅ | pre-commit + pre-push hooks active |
| Lefthook on commit | ✅ | `ts-typecheck` ran automatically and passed (0.60s) |

Commit: `a3fb939` on `feat/monorepo-restructure`

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-00: Monorepo Migration](../Task-00/scratchpad.md) ✅
- **Blocks:** All subsequent tasks (Task-02 through Task-10)
- **Reference Files:** `.agent/references/fractal-agents-runtime/` (see README there)
  - `ts-app-package.json` — TypeScript app package.json pattern
  - `ts-app-tsconfig.json` — TypeScript strict config
  - `lefthook.yml` — Polyglot git hooks
  - `ts-src-examples/storage.test.ts` — `bun test` patterns
- **External Links:**
  - [Bun Workspaces](https://bun.sh/docs/install/workspaces)
  - [bun test](https://bun.sh/docs/cli/test) — Built-in test runner
  - [Lefthook](https://github.com/evilmartians/lefthook) — Polyglot git hooks
  - [TypeScript Strict Mode](https://www.typescriptlang.org/tsconfig#strict)
