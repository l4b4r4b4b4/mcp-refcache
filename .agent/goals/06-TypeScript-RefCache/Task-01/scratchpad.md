# Task-01: TypeScript Package Setup & Tooling

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Set up the TypeScript package (`packages/typescript/`) within the restructured monorepo, including TypeScript configuration, testing framework, linting, and CI/CD pipeline integration.

**Prerequisite**: Task-00 (Monorepo Migration) must be complete first.

---

## Context
After Task-00 restructures the repo into a Bun+Python monorepo, this task sets up the TypeScript package within `packages/typescript/`. The monorepo root already has `package.json` with workspaces and `flake.nix` with Bun support. This task focuses on the TypeScript-specific configuration within that structure.

## Acceptance Criteria
- [ ] `packages/typescript/` directory created with proper structure
- [ ] TypeScript 5.x configured with strict mode (extends root tsconfig)
- [ ] Vitest configured for testing (Bun-compatible)
- [ ] ESLint + Prettier configured
- [ ] GitHub Actions CI workflow for lint/test/build
- [ ] Package.json with proper exports and type declarations
- [ ] README with project overview and development setup
- [ ] LICENSE file (MIT)
- [ ] `.gitignore` properly configured
- [ ] Dual runtime support (Bun + Node.js) verified

---

## Approach
Build on the monorepo structure created in Task-00. Create the TypeScript package within `packages/typescript/` and integrate it with the existing workspace configuration.

### Steps

1. **Create TypeScript package directory**
   ```bash
   mkdir -p packages/typescript/src
   cd packages/typescript
   ```

2. **Initialize package.json**
   ```bash
   # From packages/typescript/
   bun init -y
   # Edit to set proper name: "mcp-refcache"
   ```

3. **Link to workspace** (should auto-detect from root workspaces config)
   ```bash
   cd ../..  # back to repo root
   bun install
   ```

4. **Configure TypeScript**
   - Extend root `tsconfig.json` (already created in Task-00)
   - Package-specific `tsconfig.json` in `packages/typescript/`
   - Enable `moduleResolution: "bundler"` for modern resolution

5. **Set up Vitest**
   ```bash
   bun add -D vitest @vitest/coverage-v8
   ```

6. **Configure ESLint + Prettier**
   ```bash
   bun add -D eslint @typescript-eslint/eslint-plugin @typescript-eslint/parser
   bun add -D prettier eslint-config-prettier eslint-plugin-perfectionist
   ```

7. **Create GitHub Actions workflow**
   - Matrix testing: Bun + Node.js 20
   - Lint, type-check, test with coverage
   - Build and verify exports

8. **Set up package exports**
   ```json
   // packages/mcp-refcache/package.json
   {
     "name": "mcp-refcache",
     "type": "module",
     "exports": {
       ".": {
         "types": "./dist/index.d.ts",
         "import": "./dist/index.js"
       }
     },
     "files": ["dist", "README.md", "LICENSE"]
   }
   ```

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
│       ├── tsconfig.json
│       └── vitest.config.ts
├── package.json             # Root (from Task-00)
├── tsconfig.json            # Root (from Task-00)
├── flake.nix                # Updated in Task-00
└── ...
```

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with initial approach |

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-00: Monorepo Migration | Required | Repo must be restructured first |

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
    }
  },
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "lint": "eslint src tests --ext .ts",
    "format": "prettier --write .",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "zod": "^3.24.0",
    "nanoid": "^5.0.0"
  },
  "devDependencies": {
    "@types/bun": "latest",
    "@vitest/coverage-v8": "^1.6.0",
    "typescript": "^5.4.0",
    "vitest": "^1.6.0"
  },
  "peerDependencies": {
    "fastmcp": "^1.27.0"
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
  }
}
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

### GitHub Actions CI
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        runtime: [bun, node]
    steps:
      - uses: actions/checkout@v4

      - name: Setup Bun
        if: matrix.runtime == 'bun'
        uses: oven-sh/setup-bun@v1

      - name: Setup Node.js
        if: matrix.runtime == 'node'
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: bun install

      - name: Lint
        run: bun run lint

      - name: Type check
        run: bun run typecheck

      - name: Test
        run: bun run test:coverage

      - name: Build
        run: bun run build
```

---

## Verification
_How to confirm this task is complete._

```bash
# Clone fresh and verify
cd /tmp && git clone <repo>
cd mcp-refcache-ts

# Install dependencies
bun install

# All checks pass
bun run lint
bun run typecheck
bun run test
bun run build

# Verify with Node.js
node --version  # Should be 20+
npx vitest run  # Tests pass in Node.js too

# Check package exports
cd packages/mcp-refcache
bun run build
ls -la dist/  # index.js, index.d.ts exist
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-00: Monorepo Migration](../Task-00/scratchpad.md)
- **Blocks:** All subsequent tasks (Task-02 through Task-10)
- **External Links:**
  - [Bun Workspaces](https://bun.sh/docs/install/workspaces)
  - [Vitest](https://vitest.dev/)
  - [TypeScript Strict Mode](https://www.typescriptlang.org/tsconfig#strict)
