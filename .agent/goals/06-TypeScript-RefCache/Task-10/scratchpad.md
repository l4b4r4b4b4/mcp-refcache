# Task-10: Template Repository (fastmcp-ts-template)

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Create `fastmcp-ts-template`, a production-ready template repository for building FastMCP (TypeScript) servers with `mcp-refcache-ts` integration. This mirrors the Python `fastmcp-template` but is tailored for the TypeScript/Bun ecosystem.

---

## Context
The Python `fastmcp-template` is a Cookiecutter template that generates production-ready FastMCP servers with:
- mcp-refcache integration
- GitHub Actions CI/CD
- Docker support
- Testing setup
- Documentation structure
- Multiple variants (minimal, standard, full)

For TypeScript, we'll create a similar template optimized for Bun, using modern TypeScript tooling and patterns familiar to Node.js/TypeScript developers.

### Python Template Features to Port
From `mcp-refcache/examples/fastmcp-template`:
- Cookiecutter-based generation with `cookiecutter.json`
- Template variants (minimal, standard, full, custom)
- Optional features: demo tools, secret tools, Langfuse, custom rules
- GitHub Actions for CI/CD and PyPI publishing
- Docker multi-stage builds
- Pre-commit hooks for code quality
- Nix flake for development environment
- Comprehensive testing setup

## Acceptance Criteria
- [ ] Template repository with Cookiecutter or Yeoman generator
- [ ] Multiple variants: minimal, standard, full
- [ ] Bun-first but Node.js compatible
- [ ] `mcp-refcache` integration out of the box
- [ ] FastMCP server setup with example tools
- [ ] GitHub Actions CI workflow (lint, test, type-check)
- [ ] GitHub Actions release workflow (npm publish)
- [ ] Docker support with multi-stage builds
- [ ] Vitest testing configuration
- [ ] ESLint + Prettier configuration
- [ ] TypeScript strict mode
- [ ] README with setup instructions
- [ ] .agent/ directory for AI assistant workflow
- [ ] Optional Langfuse integration
- [ ] Verified generation for all variants

---

## Approach
Use Cookiecutter (Python) for generation to maintain consistency with the Python template and leverage existing tooling. The generated project will be pure TypeScript/Bun.

### Steps

1. **Create template repository structure**
   - Repository: `fastmcp-ts-template`
   - Cookiecutter configuration
   - Template files with Jinja2 placeholders

2. **Define cookiecutter.json**
   - Project name, slug, description
   - Author information
   - Template variant selection
   - Optional features toggles
   - Dependency versions

3. **Create minimal variant**
   - Basic FastMCP server
   - Health check tool
   - Cache query tool
   - No demo tools or Langfuse

4. **Create standard variant**
   - Includes mcp-refcache integration
   - Cache management tools
   - Documentation structure

5. **Create full variant**
   - Demo tools (hello, generate_items)
   - Secret/private compute tools
   - Langfuse integration
   - Custom rules file

6. **Set up GitHub Actions**
   - CI workflow (lint, test, type-check)
   - Release workflow (npm publish)
   - Docker build workflow

7. **Create Docker configuration**
   - Dockerfile with multi-stage build
   - docker-compose.yml for local development
   - Support for both Bun and Node.js runtimes

8. **Add validation scripts**
   - Template validation script
   - Test all variants

9. **Write documentation**
   - README with quick start
   - Variant comparison table
   - Feature documentation

---

## Template Structure

```
fastmcp-ts-template/
├── cookiecutter.json           # Cookiecutter configuration
├── hooks/
│   ├── pre_gen_project.py      # Validation before generation
│   └── post_gen_project.py     # Setup after generation
├── scripts/
│   └── validate-template.sh    # Test all variants
├── {{cookiecutter.project_slug}}/
│   ├── src/
│   │   ├── index.ts            # Entry point
│   │   ├── server.ts           # FastMCP server setup
│   │   └── tools/
│   │       ├── index.ts        # Tool exports
│   │       ├── health.ts       # Health check tool
│   │       ├── cache.ts        # Cache management tools
│   │       {% if cookiecutter.include_demo_tools == 'yes' %}
│   │       ├── demo.ts         # Demo tools
│   │       {% endif %}
│   │       {% if cookiecutter.include_secret_tools == 'yes' %}
│   │       └── secret.ts       # Private compute tools
│   │       {% endif %}
│   ├── tests/
│   │   ├── setup.ts            # Test setup
│   │   └── server.test.ts      # Server tests
│   ├── .github/
│   │   └── workflows/
│   │       ├── ci.yml          # CI workflow
│   │       └── release.yml     # Release workflow
│   ├── docker/
│   │   ├── Dockerfile          # Production Dockerfile
│   │   └── Dockerfile.dev      # Development Dockerfile
│   ├── .agent/
│   │   ├── scratchpad.md       # AI assistant notes
│   │   └── goals/
│   │       └── scratchpad.md   # Goals tracking
│   ├── .eslintrc.cjs
│   ├── .prettierrc
│   ├── .gitignore
│   ├── docker-compose.yml
│   ├── package.json
│   ├── tsconfig.json
│   ├── vitest.config.ts
│   ├── README.md
│   ├── CHANGELOG.md
│   └── LICENSE
├── README.md                   # Template documentation
└── VERIFICATION.md             # Verification results
```

---

## cookiecutter.json Design

```json
{
  "project_name": "My MCP Server",
  "project_slug": "{{ cookiecutter.project_name.lower().replace(' ', '-').replace('_', '-') }}",
  "project_description": "A FastMCP server with mcp-refcache integration",
  "author_name": "Your Name",
  "author_email": "you@example.com",
  "github_username": "",
  "license": ["MIT", "Apache-2.0", "GPL-3.0", "BSD-3-Clause"],
  "node_version": "20",
  "runtime": ["bun", "node"],
  "template_variant": ["minimal", "standard", "full", "custom"],
  "include_demo_tools": ["no", "yes"],
  "include_secret_tools": ["no", "yes"],
  "include_langfuse": ["no", "yes"],
  "include_docker": ["yes", "no"],
  "fastmcp_version": "^1.27.0",
  "mcp_refcache_version": "^0.1.0",
  "create_github_repo": ["no", "yes"],
  "trigger_initial_release": ["no", "yes"]
}
```

---

## Generated package.json

```json
{
  "name": "{{ cookiecutter.project_slug }}",
  "version": "0.0.0",
  "type": "module",
  "description": "{{ cookiecutter.project_description }}",
  "author": "{{ cookiecutter.author_name }} <{{ cookiecutter.author_email }}>",
  "license": "{{ cookiecutter.license }}",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "bin": {
    "{{ cookiecutter.project_slug }}": "./dist/index.js"
  },
  "scripts": {
    "build": "tsc",
    "start": "{{ cookiecutter.runtime }} run src/index.ts",
    "dev": "fastmcp dev src/index.ts",
    "inspect": "fastmcp inspect src/index.ts",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "lint": "eslint src tests --ext .ts",
    "format": "prettier --write .",
    "typecheck": "tsc --noEmit",
    "prepublishOnly": "npm run build"
  },
  "dependencies": {
    "fastmcp": "{{ cookiecutter.fastmcp_version }}",
    "mcp-refcache": "{{ cookiecutter.mcp_refcache_version }}",
    "zod": "^3.24.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@typescript-eslint/eslint-plugin": "^7.0.0",
    "@typescript-eslint/parser": "^7.0.0",
    "@vitest/coverage-v8": "^1.6.0",
    "eslint": "^8.57.0",
    "eslint-config-prettier": "^9.1.0",
    "prettier": "^3.2.0",
    "typescript": "^5.4.0",
    "vitest": "^1.6.0"
  },
  "files": ["dist", "README.md", "LICENSE"],
  "engines": {
    "node": ">=20.0.0"
  }
}
```

---

## Template Variants

### Minimal
- FastMCP server with basic setup
- Health check tool
- No mcp-refcache, no Langfuse
- ~50 tests

### Standard (Recommended)
- Full mcp-refcache integration
- Cache management tools
- Reference-based data flow examples
- ~75 tests

### Full
- Everything in Standard plus:
- Demo tools (hello, generate_items)
- Secret/private compute tools
- Langfuse observability
- ~100 tests

### Custom
- Pick and choose features:
  - Demo tools (yes/no)
  - Secret tools (yes/no)
  - Langfuse (yes/no)

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with template design |

### Design Decisions

1. **Cookiecutter over Yeoman**: Maintains consistency with Python template and works cross-platform. Users already have Cookiecutter if they've used the Python template.

2. **Bun-first**: Default runtime is Bun for performance, but generated projects are Node.js compatible.

3. **Vitest over Jest**: Faster, better TypeScript support, similar API to Jest so familiar to most developers.

4. **Minimal as default variant**: Start simple, add complexity as needed. Encourages incremental adoption.

5. **Separate Dockerfiles**: Production (Dockerfile) is optimized for size, development (Dockerfile.dev) includes dev tools and hot reload.

6. **.agent/ directory**: Include AI assistant workspace structure from the start, following the pattern established in mcp-refcache.

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | Required | mcp-refcache-ts must exist |
| Task-09: FastMCP Integration | Required | Integration patterns needed |
| mcp-refcache npm publish | Required | Package must be published for template to work |

---

## Verification
_How to confirm this task is complete._

```bash
# Test minimal variant
./scripts/validate-template.sh minimal

# Test standard variant
./scripts/validate-template.sh standard

# Test full variant
./scripts/validate-template.sh full

# Test all variants
./scripts/validate-template.sh --all

# Manual generation test
cookiecutter . --output-dir /tmp/test --no-input \
  project_name="Test Server" \
  template_variant=standard

cd /tmp/test/test-server
bun install
bun run lint
bun run typecheck
bun run test
bun run build
```

### Verification Checklist
- [ ] All variants generate without errors
- [ ] Generated projects pass lint
- [ ] Generated projects pass type-check
- [ ] Generated projects pass all tests
- [ ] Generated projects build successfully
- [ ] Docker builds work
- [ ] README is accurate and helpful
- [ ] No hardcoded template values in output

---

## Example Generated Server

```typescript
// src/server.ts (generated for standard variant)
import { FastMCP } from 'fastmcp';
import { z } from 'zod';
import { RefCache, cached, cacheInstructions, AccessPolicy } from 'mcp-refcache';

const cache = new RefCache({ name: '{{ cookiecutter.project_slug }}' });

export const server = new FastMCP({
  name: '{{ cookiecutter.project_name }}',
  version: '0.0.0',
  instructions: cacheInstructions({ includePagination: true }),
});

// Health check tool
server.addTool({
  name: 'health',
  description: 'Check server health status',
  parameters: z.object({}),
  annotations: { readOnlyHint: true },
  execute: async () => {
    const stats = await cache.stats();
    return JSON.stringify({
      status: 'healthy',
      cache: stats,
      timestamp: new Date().toISOString(),
    });
  },
});

// Cache query tool
server.addTool({
  name: 'get_cached_result',
  description: 'Retrieve a cached value by reference ID',
  parameters: z.object({
    refId: z.string().describe('The reference ID to look up'),
    page: z.number().optional().describe('Page number for pagination'),
    pageSize: z.number().optional().describe('Items per page'),
  }),
  annotations: { readOnlyHint: true },
  execute: async (args) => {
    const response = await cache.get(args.refId, {
      page: args.page,
      pageSize: args.pageSize,
    });

    if (!response) {
      return JSON.stringify({ error: 'Reference not found', refId: args.refId });
    }

    return JSON.stringify(response);
  },
});

export { cache };
```

---

## File Structure
```
fastmcp-ts-template/           # Separate repository
├── cookiecutter.json
├── hooks/
├── scripts/
├── {{cookiecutter.project_slug}}/
├── README.md
└── VERIFICATION.md
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-09](../Task-09/scratchpad.md)
- **External Links:**
  - [Python fastmcp-template](https://github.com/l4b4r4b4b4/fastmcp-template)
  - [Cookiecutter](https://github.com/cookiecutter/cookiecutter)
  - [FastMCP (TypeScript)](https://github.com/punkpeye/fastmcp)
  - [fastmcp-boilerplate](https://github.com/punkpeye/fastmcp-boilerplate)
