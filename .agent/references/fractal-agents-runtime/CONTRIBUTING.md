# Contributing to Fractal Agents Runtime

Thank you for your interest in contributing! This guide covers development setup, project structure, coding standards, and the pull request process.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Dependency Rules](#dependency-rules)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Architecture Decisions](#architecture-decisions)
- [Release Process](#release-process)

---

## Development Setup

### Option A: Nix (recommended)

```bash
git clone https://github.com/l4b4r4b4b4/fractal-agents-runtime.git
cd fractal-agents-runtime
nix develop
```

The Nix dev shell provides Python 3.12, UV, Bun, Docker, Helm, kubectl, and Lefthook — and automatically runs `uv sync` and `bun install`.

### Option B: Manual

**Prerequisites:** Python 3.12, [UV](https://docs.astral.sh/uv/) ≥ 0.10, [Bun](https://bun.sh/) ≥ 1.1

```bash
git clone https://github.com/l4b4r4b4b4/fractal-agents-runtime.git
cd fractal-agents-runtime

# Root workspace (TypeScript tooling)
bun install

# Python app
cd apps/python
uv sync
cp .env.example .env  # Edit with your API keys
```

### Verify Your Setup

```bash
cd apps/python
uv run pytest                  # Should pass 867+ tests
uv run ruff check .            # Should report "All checks passed"
uv run ruff format --check .   # Should report all files formatted
```

---

## Project Structure

All Python source lives under `apps/python/src/` in three modules:

```text
fractal-agents-runtime/
├── apps/
│   ├── python/                         # Python runtime — v0.0.1
│   │   ├── src/
│   │   │   ├── server/                 # HTTP server (Robyn)
│   │   │   │   ├── routes/             #   Route handlers (assistants, threads, runs, etc.)
│   │   │   │   ├── crons/              #   APScheduler cron scheduling
│   │   │   │   ├── mcp/                #   MCP tool management
│   │   │   │   ├── a2a/                #   Agent-to-Agent protocol
│   │   │   │   ├── tests/              #   867+ tests (74% coverage)
│   │   │   │   ├── app.py              #   Robyn application + startup hooks
│   │   │   │   ├── config.py           #   Env var configuration
│   │   │   │   ├── agent.py            #   Agent graph wiring + invocation
│   │   │   │   ├── agent_sync.py       #   Startup assistant sync from Supabase
│   │   │   │   ├── auth.py             #   JWT auth middleware
│   │   │   │   ├── database.py         #   Postgres connection management
│   │   │   │   ├── storage.py          #   In-memory storage adapter
│   │   │   │   └── postgres_storage.py #   Full Postgres storage adapter
│   │   │   ├── graphs/
│   │   │   │   └── react_agent/        #   Portable ReAct agent graph
│   │   │   │       ├── agent.py        #     Graph factory (DI for persistence)
│   │   │   │       └── utils/          #     MCP interceptors, token exchange, RAG
│   │   │   └── infra/
│   │   │       ├── tracing.py          #   Langfuse init + inject_tracing()
│   │   │       ├── store_namespace.py  #   Canonical 4-component namespace
│   │   │       └── security/auth.py    #   Supabase JWT verification
│   │   ├── pyproject.toml
│   │   └── uv.lock
│   └── ts/                             # TypeScript runtime (Bun) — v0.0.0 stub
│       └── src/
├── .devops/
│   ├── docker/                         # Multi-stage Dockerfiles
│   │   ├── python.Dockerfile
│   │   └── ts.Dockerfile
│   └── helm/fractal-agents-runtime/    # Unified Helm chart (runtime toggle)
├── .github/workflows/                  # CI, image builds, release pipelines
├── docker-compose.yml                  # Local dev stack
├── lefthook.yml                        # Git hooks config
└── flake.nix                           # Nix dev environment
```

---

## Dependency Rules

The three Python modules form a strict one-way dependency hierarchy. Dependencies flow **downward only**:

```text
  server          ← top-level: wires everything together
    ↓  ↓
  graphs  infra   ← mid-level: graphs can use infra
    ↓
  infra           ← bottom-level: no upward imports
```

| Import direction | Allowed? | Example |
|------------------|----------|---------|
| `server` → `graphs` | ✅ Yes | `from graphs.react_agent import graph` |
| `server` → `infra` | ✅ Yes | `from infra.tracing import inject_tracing` |
| `graphs` → `infra` | ✅ Yes | `from infra.store_namespace import build_namespace` |
| `graphs` → `server` | ❌ **Never** | No `from server.config import ...` in graph code |
| `infra` → `server` | ❌ **Never** | Infra is the lowest layer |
| `infra` → `graphs` | ❌ **Never** | Infra knows nothing about agents |

### Why This Matters

The agent graph (`graphs/react_agent/`) must remain **portable** — it should work when:

- Served by the Robyn HTTP server (current runtime)
- Deployed to [LangGraph Platform](https://langchain-ai.github.io/langgraph/concepts/langgraph_platform/)
- Embedded in FastAPI, Lambda, or a CLI tool
- Run in tests without any server infrastructure

If the graph imports from `server`, it becomes coupled to Robyn and breaks portability.

### Dependency Injection for Persistence

Graphs receive persistence components as parameters — they never import them from a specific server:

```python
# In the graph module (portable — no server imports):
async def graph(config: RunnableConfig, *, checkpointer=None, store=None):
    ...
    return agent.compile(checkpointer=checkpointer, store=store)

# In the server module (wiring layer):
from server.database import get_checkpointer, get_store
from graphs.react_agent import graph

agent = await graph(config, checkpointer=get_checkpointer(), store=get_store())
```

When `checkpointer` and `store` are `None`, the agent runs without persistence — useful for testing or stateless invocations.

---

## Development Workflow

### Branch Strategy

- **`main`** — stable releases only (protected, requires CI + PR)
- **`development`** — integration branch, PRs merge here (protected, requires CI + PR)
- **`feature/*`**, **`fix/*`**, **`goal/*`** — working branches off `development`

### Day-to-Day Commands

```bash
cd apps/python

# Sync dependencies after pulling
uv sync

# Run tests with coverage
uv run pytest

# Lint and format (run before committing)
uv run ruff check . --fix --unsafe-fixes && uv run ruff format .

# Validate OpenAPI spec
uv run python -c "from server.openapi_spec import validate_spec; validate_spec()"
```

### Dependency Management

**Use `uv` exclusively** — never pip or pip-compile.

```bash
# Add a runtime dependency
uv add <package>

# Add a dev dependency
uv add --group dev <package>

# Always commit pyproject.toml + uv.lock together
```

- **Runtime deps** go in `[project.dependencies]`
- **Dev deps** go in `[dependency-groups.dev]`

### Git Hooks (Lefthook)

Lefthook runs automatically if installed:

- **pre-commit:** Ruff lint + format on staged files
- **pre-push:** Full test suite + coverage enforcement + diff-cover + OpenAPI validation

---

## Coding Standards

### Python

- **Python 3.12** target (supports ≥3.11, <3.13)
- **Ruff** for linting and formatting (`select = ["ALL"]` with tuned ignores)
- **Type annotations** required for all public functions, methods, and classes
- **Pydantic models** for public API data structures
- **Google-style docstrings** with summary, parameters, returns, and exceptions
- **No bare `except:`** — always catch specific exceptions
- **`__all__` alphabetically sorted** (enforced by Ruff RUF022)

### Naming

- **No single-letter variable names** — always descriptive
- **No abbreviations** — `user_repository` not `usr_repo`
- **No "Utils" or "Helper" classes** — organise into proper modules
- **Include units in names** only when types can't encode them

### Before Committing

```bash
cd apps/python
uv run ruff check . --fix --unsafe-fixes && uv run ruff format .
uv run pytest
```

---

## Testing

### Philosophy

We follow a **pragmatic testing** approach: implement → manual test → write tests.

### Rules

- **Test behaviour, not implementation** — tests should survive refactoring
- **One thing per test** — focused test cases with clear assertions
- **Deterministic tests** — mock time, randomness, and I/O
- **Test error paths** — exceptions with correct types and messages
- **Critical paths require tests** before merge

### Running Tests

```bash
cd apps/python

# Full suite (867+ tests, 74% coverage)
uv run pytest

# Specific test file
uv run pytest src/server/tests/test_tracing.py -v

# With short traceback
uv run pytest --tb=short

# Just route handler tests
uv run pytest src/server/tests/test_route_handlers.py -v
```

### Coverage Enforcement (Three Tiers)

1. **Global floor:** `pytest-cov` with `fail_under=73` — the full suite must maintain ≥73% coverage
2. **Per-file floor:** `coverage-threshold` — no individual file can drop to 0% (minimum 10% line coverage)
3. **New code:** `diff-cover` with `fail_under=80` — changed lines in PRs must be ≥80% covered

### Test Coverage Areas

The 867+ tests cover:

- Agent configuration and graph building
- Streaming and SSE event formatting
- Thread, run, and assistant CRUD operations
- Route handler request/response cycles
- Authentication and authorisation middleware
- Postgres storage adapter (unit + integration)
- Agent sync startup behaviour
- Tracing integration (Langfuse)
- A2A protocol handling
- Cron scheduling
- Store namespace conventions
- OpenAPI spec validation

---

## Pull Request Process

### Before Opening a PR

1. **Branch off `development`** (not `main`)
2. **Run the full verification suite:**
   ```bash
   cd apps/python
   uv run ruff check . --fix --unsafe-fixes && uv run ruff format .
   uv run pytest
   ```
3. **Check for stale references** if you moved or renamed modules:
   ```bash
   grep -rn "robyn_server\|fractal_agent_infra\|react_agent" --include="*.py" apps/python/src/
   ```
4. **Commit `pyproject.toml` + `uv.lock` together** for any dependency changes

### PR Guidelines

- Use descriptive commit messages ([Conventional Commits](https://www.conventionalcommits.org/) preferred)
- Keep PRs focused — one logical change per PR
- Update docstrings and README if the public API changed
- Add or update tests for new behaviour
- Target **`development`** as the base branch

### What Reviewers Check

- [ ] Tests pass (867+ in Python suite)
- [ ] Coverage ≥73% globally, ≥80% on changed lines
- [ ] Ruff clean
- [ ] No stale import references
- [ ] Dependency rules respected (no `graphs → server` or `infra → server` imports)
- [ ] Public APIs have docstrings
- [ ] Lock files committed alongside `pyproject.toml` changes
- [ ] OpenAPI spec valid (34 paths, 44 operations, 28 schemas)

---

## Architecture Decisions

### Why a Flat `src/` Layout?

The Python source was consolidated from a multi-package `packages/` layout into a single `apps/python/src/` tree in Goals 19–20. This simplifies:

- **Dependency resolution** — no complex path dependencies between packages
- **Testing** — single `pytest` invocation covers everything
- **Docker builds** — one `COPY` for all source
- **IDE support** — standard Python path resolution

The three modules (`server`, `graphs`, `infra`) are still logically separated via the [dependency rules](#dependency-rules), but they share a single `pyproject.toml` and venv.

### Why Dependency Injection for Persistence?

If `graph()` imports `get_checkpointer()` from a specific server, it's coupled to that server. Dependency injection makes the graph a pure function of its inputs — the runtime decides how to persist state.

### Why UV over pip?

UV is 10–100× faster, follows PEP 621, provides reproducible lockfiles, and is the single source of truth for dependency management. See the [UV docs](https://docs.astral.sh/uv/).

### Why Ruff `select = ["ALL"]`?

We enable all rules and explicitly ignore the ones that don't fit. This catches issues early and ensures consistency. The ignore list in `pyproject.toml` documents exactly which rules we've opted out of and why.

### Why a Unified Helm Chart?

Both the Python and TypeScript runtimes serve the same LangGraph API — same endpoints, same health checks, same secrets. A single Helm chart at `.devops/helm/fractal-agents-runtime/` with a `runtime` toggle (`python` or `ts`) avoids duplication. See the [Helm chart README](.devops/helm/fractal-agents-runtime/README.md).

---

## Release Process

### Versioning

All versions start at `0.0.0` and increment through patches before reaching `0.1.0`. This is intentional — it validates both the code and the release pipeline from day one.

**Version progression:** `0.0.0` → `0.0.x` (patches) → `0.1.0` (after 5–10 stable patches) → `1.0.0` (production-ready).

### Current Versions

| Component | Current | Source |
|-----------|---------|--------|
| Python runtime | 0.0.1 | `apps/python/pyproject.toml` |
| TypeScript runtime | 0.0.0 | `apps/ts/package.json` |
| Helm chart | 0.0.1 | `.devops/helm/fractal-agents-runtime/Chart.yaml` |

### Image Tags

Docker images are published to GHCR by GitHub Actions:

| Branch/Tag | Image Tag |
|------------|-----------|
| Feature branch push | `sha-<short>` |
| Merge to `development` | `development` |
| Merge to `main` | `nightly` |
| Release tag (`v0.0.1`) | `v0.0.1`, `latest` |

---

## Questions?

Open an [issue](https://github.com/l4b4r4b4b4/fractal-agents-runtime/issues) or start a [discussion](https://github.com/l4b4r4b4b4/fractal-agents-runtime/discussions).
