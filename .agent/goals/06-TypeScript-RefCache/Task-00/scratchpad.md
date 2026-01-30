# Task-00: Monorepo Migration (Bun + Python)

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Restructure the `mcp-refcache` repository from a Python-only project to a Bun-powered monorepo that houses both the Python and TypeScript implementations of mcp-refcache. Use the `docproc-platform` monorepo pattern as reference.

---

## Context
The existing `mcp-refcache` repository is a pure Python project managed by `uv`. To add a TypeScript implementation alongside it, we need to restructure the repo into a monorepo pattern that:

1. Uses Bun workspaces at the root level
2. Keeps the Python implementation in a dedicated directory
3. Adds TypeScript packages as Bun workspace members
4. Updates the Nix flake to support both ecosystems
5. Maintains backward compatibility for existing Python users

### Reference: docproc-platform Pattern

The `docproc-platform` repo demonstrates this pattern successfully:
- Root `package.json` with Bun workspaces (`apps/*`, `packages/*`)
- Python apps in `apps/api/` and `apps/ocr-inference/` with their own `pyproject.toml` and `uv.lock`
- TypeScript packages in `packages/types/`, etc.
- Unified `flake.nix` providing both Bun and Python/uv tooling
- Scripts that orchestrate both ecosystems

Reference files copied to: `archive/bun-python-monorepo-reference/`

## Acceptance Criteria
- [ ] Repository restructured with new directory layout
- [ ] Python implementation moved to `python/` or `packages/python/` directory
- [ ] Root `package.json` created with Bun workspace configuration
- [ ] Root `tsconfig.json` created for TypeScript base configuration
- [ ] `flake.nix` updated to support both Bun and Python/uv
- [ ] Existing Python tests still pass (`uv run pytest`)
- [ ] PyPI publishing workflow still works
- [ ] `.gitignore` updated for both ecosystems
- [ ] README updated to explain monorepo structure
- [ ] All existing functionality preserved

---

## Approach

### Phase 1: Create Branch and New Structure

1. Create feature branch `feat/monorepo-restructure`
2. Create new directory structure
3. Move Python code without breaking imports

### Phase 2: Add Bun Configuration

1. Initialize root `package.json` with workspaces
2. Add root `tsconfig.json`
3. Update `.gitignore`

### Phase 3: Update Nix Flake

1. Add Bun to FHS environment
2. Keep Python/uv support
3. Update shell hooks for both ecosystems

### Phase 4: Verify and Test

1. Run Python tests
2. Verify PyPI metadata still correct
3. Test `uv sync` and `bun install`

---

## Proposed Directory Structure

```
mcp-refcache/
├── .agent/                      # AI assistant workspace (unchanged)
├── .github/
│   └── workflows/
│       ├── ci.yml               # Updated for both ecosystems
│       └── publish.yml          # Python PyPI publishing
├── packages/
│   ├── python/                  # Python implementation (moved from root)
│   │   ├── src/mcp_refcache/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── uv.lock
│   └── typescript/              # TypeScript implementation (new)
│       ├── src/
│       ├── tests/
│       ├── package.json
│       └── tsconfig.json
├── examples/
│   ├── fastmcp-template/        # Python template (unchanged)
│   └── fastmcp-ts-template/     # TS template (future Task-10)
├── docs/                        # Shared documentation
├── package.json                 # Bun workspace root
├── tsconfig.json                # TypeScript base config
├── flake.nix                    # Nix dev environment (updated)
├── flake.lock
├── .gitignore                   # Updated for both ecosystems
└── README.md                    # Updated with monorepo docs
```

### Alternative: Simpler Flat Structure

```
mcp-refcache/
├── python/                      # Python implementation
│   ├── src/mcp_refcache/
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
├── typescript/                  # TypeScript implementation
│   ├── src/
│   ├── tests/
│   ├── package.json
│   └── tsconfig.json
├── examples/
├── package.json                 # Bun workspace: ["typescript"]
├── ...
```

---

## Key Files to Create/Modify

### Root package.json
```json
{
  "name": "@mcp-refcache/monorepo",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "workspaces": [
    "packages/typescript"
  ],
  "scripts": {
    "dev:ts": "cd packages/typescript && bun run dev",
    "test:ts": "cd packages/typescript && bun test",
    "test:py": "cd packages/python && uv run pytest",
    "test": "bun run test:ts && bun run test:py",
    "lint:ts": "cd packages/typescript && bun run lint",
    "lint:py": "cd packages/python && uv run ruff check .",
    "build:ts": "cd packages/typescript && bun run build"
  },
  "devDependencies": {
    "@types/bun": "latest",
    "typescript": "^5.4.0"
  },
  "engines": {
    "bun": ">=1.1.0"
  }
}
```

### Updated pyproject.toml Path
The `pyproject.toml` will need its paths updated:
- `packages = [{include = "mcp_refcache", from = "src"}]` stays the same
- Build/publish commands run from `packages/python/`

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created, reference files copied to archive/ |

### Reference Files Copied
Location: `archive/bun-python-monorepo-reference/`
- `package.json` - Root Bun workspace config
- `flake.nix` - Nix dev shell with Bun + Python
- `tsconfig.json` - TypeScript base config
- `.gitignore` - Combined ignore patterns
- `apps/api/pyproject.toml` - Python app example
- `apps/ocr-inference/pyproject.toml` - Another Python app
- `packages/types/package.json` - TS package example

### Key Patterns from docproc-platform

1. **Bun workspaces**: `"workspaces": ["apps/*", "packages/*"]`
2. **Python apps**: Each has own `pyproject.toml`, `uv.lock`, `.venv`
3. **Script orchestration**: Root scripts like `test:api` run `cd apps/api && uv run pytest`
4. **Nix FHS**: Uses `buildFHSEnv` for complex environment with both ecosystems
5. **Alias protection**: Prevents using wrong package managers (pip → uv, npm → bun)

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| None | - | First task in restructured goal |

---

## Commands & Snippets

### Create Branch
```bash
git checkout -b feat/monorepo-restructure
```

### Move Python Code
```bash
mkdir -p packages/python
git mv src packages/python/
git mv tests packages/python/
git mv pyproject.toml packages/python/
git mv uv.lock packages/python/
```

### Initialize Bun
```bash
bun init -y
# Edit package.json to add workspaces
```

### Verify Python Still Works
```bash
cd packages/python
uv sync
uv run pytest
uv run ruff check .
```

---

## Verification

```bash
# From repo root
git checkout feat/monorepo-restructure

# Python tests pass
cd packages/python && uv run pytest && cd ../..

# Bun workspace works
bun install
bun run test:py

# TypeScript scaffold ready (for Task-01)
ls packages/typescript/ 2>/dev/null || echo "TS package not yet created (Task-01)"

# Nix shell works
nix develop
```

---

## Migration Checklist

- [ ] Create feature branch
- [ ] Create `packages/python/` directory
- [ ] Move `src/`, `tests/`, `pyproject.toml`, `uv.lock`
- [ ] Update `pyproject.toml` if needed
- [ ] Create root `package.json`
- [ ] Create root `tsconfig.json`
- [ ] Update `.gitignore`
- [ ] Update `flake.nix`
- [ ] Update GitHub Actions CI
- [ ] Update README.md
- [ ] Run Python tests
- [ ] Run `bun install`
- [ ] Commit and push
- [ ] Create PR for review

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** None (prerequisite for all other tasks)
- **Blocks:** All other tasks (Task-01 through Task-10)
- **Reference:** `archive/bun-python-monorepo-reference/`
- **External Links:**
  - [Bun Workspaces](https://bun.sh/docs/install/workspaces)
  - [docproc-platform repo](file:///home/lukes/code/github.com/AIS/docproc-platform)
