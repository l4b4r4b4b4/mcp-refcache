# Side Quest: FastMCP Template Repository

## Status: Phase 1 In Progress 🔨

---

## Task Overview

### Goal (Phase 1 - Current Focus)
Create a **FastMCP template starter repo** based on finquant-mcp patterns, with:
- mcp-refcache integration
- Langfuse tracing (optional)
- Complete project scaffolding

### Goal (Phase 2 - Later)
Build a **Zed Management MCP Server** for tracking/managing chat sessions per project

---

## Phase 1 Progress

### ✅ Completed Files

#### Project Configuration
- [x] `pyproject.toml` - UV project with dependencies, ruff/pytest/mypy config
- [x] `.python-version` - Python 3.12
- [x] `flake.nix` - Nix dev shell with FHS environment, auto-venv, uv sync
- [x] `.gitignore` - Comprehensive Python gitignore + archive/, .venv, Nix result
- [x] `.pre-commit-config.yaml` - Ruff, mypy, bandit, safety hooks

#### GitHub Integration
- [x] `.github/workflows/ci.yml` - Python 3.12/3.13 matrix, lint, test, security scan
- [x] `.github/workflows/release.yml` - Build on version tags, GitHub release
- [x] `.github/copilot-instructions.md` - Copilot guidance for the project

#### IDE Configuration
- [x] `.zed/settings.json` - Pyright LSP, ruff format, MCP context servers

#### Source Code
- [x] `src/fastmcp_template/__init__.py` - Version export
- [x] `src/fastmcp_template/server.py` - **MAIN FILE** - Complete server with:
  - `hello` tool (no caching, simple example)
  - `generate_items` tool (cached in PUBLIC namespace - demonstrates shared caching)
  - `store_secret` tool (EXECUTE-only for agents)
  - `compute_with_secret` tool (private computation)
  - `get_cached_result` tool (pagination)
  - `health_check` tool
  - Admin tools registration
  - `template_guide` prompt
  - CLI with stdio/sse transport options
- [x] `src/fastmcp_template/tools/__init__.py` - Placeholder with usage example

#### Tests
- [x] `tests/__init__.py`
- [x] `tests/conftest.py` - RefCache fixture, sample_items fixture
- [x] `tests/test_server.py` - Tests for hello, health_check, MCP config

#### Documentation & Guidelines
- [x] `.rules` - Copied from finquant-mcp (needs project name updates)
- [x] `CONTRIBUTING.md` - Copied from finquant-mcp (needs project name updates)

### ❌ Remaining Tasks

#### Documentation (Need to Create)
- [ ] `README.md` - Project overview, installation, usage, examples
- [ ] `docs/README.md` - Extended documentation
- [ ] `CHANGELOG.md` - Initial changelog entry
- [ ] `.agent/scratchpad.md` - Empty scratchpad for AI agents

#### File Updates Needed
- [ ] Update `.rules` - Replace finquant-mcp references with fastmcp-template
- [ ] Update `CONTRIBUTING.md` - Replace finquant-mcp references

#### GitHub Repo (Created but Empty)
- [ ] Push all files to `l4b4r4b4b4/fastmcp-template` (private repo already created)
- [ ] Or keep in mcp-refcache/examples/ and push there first

#### Testing & Verification
- [ ] Run `nix develop` to test flake
- [ ] Run `uv sync` to install dependencies
- [ ] Run `uv run pytest` to verify tests pass
- [ ] Run `uv run ruff check . --fix && uv run ruff format .` to lint
- [ ] Test server: `uv run fastmcp-template`

---

## Key Design Decisions Made

1. **Public namespace for generate_items**: Uses `@cache.cached(namespace="public")` to demonstrate shared caching that all users can access.

2. **Copied patterns from mcp_server.py**: Server structure, tool patterns, Pydantic models all follow the calculator example.

3. **Minimal but complete**: Template has enough to be useful but isn't overwhelming - users can delete what they don't need.

4. **No separate cache.py**: Cache is created inline in server.py following the mcp_server.py pattern. No wrapper needed - use mcp-refcache directly.

5. **Python 3.12+ only**: Simplified matrix to 3.12 and 3.13 (dropped 3.10/3.11 support for cleaner code).

---

## File Locations

All files are in: `mcp-refcache/examples/fastmcp-template/`

```
fastmcp-template/
├── .agent/                      # (empty - need to create scratchpad.md)
├── .github/
│   ├── workflows/
│   │   ├── ci.yml               ✅
│   │   └── release.yml          ✅
│   └── copilot-instructions.md  ✅
├── .zed/
│   └── settings.json            ✅
├── docs/                        # (empty - need README.md)
├── src/
│   └── fastmcp_template/
│       ├── __init__.py          ✅
│       ├── server.py            ✅ (main file)
│       └── tools/
│           └── __init__.py      ✅
├── tests/
│   ├── __init__.py              ✅
│   ├── conftest.py              ✅
│   └── test_server.py           ✅
├── .gitignore                   ✅
├── .pre-commit-config.yaml      ✅
├── .python-version              ✅
├── .rules                       ✅ (needs name updates)
├── CHANGELOG.md                 ❌
├── CONTRIBUTING.md              ✅ (needs name updates)
├── LICENSE                      ❌
├── README.md                    ❌
├── flake.nix                    ✅
└── pyproject.toml               ✅
```

---

## Session Log

### 2024-12-08: Research Complete
- Analyzed finquant-mcp, BundesMCP, calculator example
- Documented template specification
- Created implementation checklist

### 2024-12-09: Phase 1 Implementation Started
- Created GitHub repo `l4b4r4b4b4/fastmcp-template` (private)
- Scaffolded directory structure in `mcp-refcache/examples/fastmcp-template/`
- Created all config files (pyproject.toml, flake.nix, .pre-commit-config.yaml, etc.)
- Created GitHub workflows (ci.yml, release.yml)
- Copied and adapted server.py from mcp_server.py calculator example
- Created simplified tests from finquant-mcp patterns
- Copied .rules and CONTRIBUTING.md (need updates)
- **Key**: Used `@cache.cached(namespace="public")` for generate_items to demonstrate shared caching

---

## Next Session Starting Prompt

See codebox below.
