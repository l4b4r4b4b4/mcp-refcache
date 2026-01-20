# mcp-refcache Development Scratchpad

## Current Status: v0.2.0 In Development 🟡

**Last Updated**: January 2025

### Published Package

- **PyPI**: [pypi.org/project/mcp-refcache](https://pypi.org/project/mcp-refcache/)
- **GitHub**: Public repository ready

### v0.1.0 Feature Checklist

| Feature | Status | Notes |
|---------|--------|-------|
| Core RefCache class | ✅ Done | 652 tests passing |
| Memory backend (thread-safe) | ✅ Done | TTL support |
| SQLite backend | ✅ Done | Cross-process caching |
| Redis backend | ✅ Done | Optional `[redis]` extra |
| Namespaces (public, session, user, custom) | ✅ Done | Full isolation |
| Access control (Actor, Permission, ACLs) | ✅ Done | User/Agent/System |
| Context limiting (token/char) | ✅ Done | tiktoken + HF support |
| Preview strategies (sample/paginate/truncate) | ✅ Done | PreviewGenerator |
| EXECUTE permission (private compute) | ✅ Done | Blind computation |
| `@cache.cached()` decorator | ✅ Done | Automatic ref resolution |
| FastMCP integration helpers | ✅ Done | `cache_instructions()` |
| Admin tools | ✅ Done | Permission-gated |

**Test Results**: 652 passed (39 skipped for optional Redis/transformers deps)

---

## Active Goals

| ID | Goal Name | Status | Priority |
|----|-----------|--------|----------|
| 01 | [Legal-MCP](./goals/01-Legal-MCP/scratchpad.md) | ⚪ Not Started | P2 (Medium) |
| 02 | [Faster-MCP](./goals/02-Faster-MCP/scratchpad.md) | ⚪ Not Started | P3 (Low) |
| 04 | [Async-Task-Backends](./goals/04-Async-Timeout-Fallback/scratchpad.md) | 🟡 In Progress | P1 (High) |
| 05 | [Real-Estate-Sustainability-MCP](./goals/05-Real-Estate-Sustainability-MCP/scratchpad.md) | 🔴 Not Started | P1 (High) |

See [Goals Index](./goals/scratchpad.md) for full tracking.

### Goal Summaries

**01-Legal-MCP**: Comprehensive legal research MCP server with mcp-refcache integration. Starts with German law (dejure.org), expands to EU (EUR-Lex) and US law. Demonstrates real-world caching of large, stable legal documents.

**02-Faster-MCP**: Research feasibility of Robyn-based (Rust runtime) alternative to FastMCP. Motivated by 40x+ performance improvement potential (10k+ RPS vs ~246 RPS).

**04-Async-Task-Backends**: Add async task execution to `@cache.cached()` with pluggable backends. `TaskBackend` protocol enables `MemoryTaskBackend` (ThreadPoolExecutor, MVP) and future `HatchetTaskBackend` (distributed). When computations exceed `async_timeout`, returns reference immediately with "processing" status. Client polls for completion. Includes progress callbacks, retry mechanism, cancellation API. **Main feature for v0.2.0.** Hatchet SDK researched (2026-01-19).

**05-Real-Estate-Sustainability-MCP**: Build comprehensive Real Estate Sustainability Analysis MCP server using fastmcp-template and mcp-refcache. Four core toolsets: Excel processing, PDF analysis with Chroma semantic search, sustainability frameworks (ESG, LEED, BREEAM, DGNB), and IFC integration via ifc-mcp. Target users: developers, consultants, facility managers.

---

## Roadmap

### v0.2.0 (In Development) — Async Task Backends

- [ ] `TaskBackend` protocol for pluggable task execution
- [ ] `MemoryTaskBackend` using ThreadPoolExecutor (MVP)
- [ ] `async_timeout` parameter for `@cache.cached()` decorator
- [ ] Task tracking infrastructure (TaskInfo, TaskStatus, TaskProgress) — models exist ✅
- [ ] Polling support for in-flight computations
- [ ] Progress callback protocol
- [ ] Retry mechanism with exponential backoff
- [ ] Cancellation API
- [ ] Comprehensive tests (≥80% coverage)
- [ ] Documentation update
- [ ] (Future) `HatchetTaskBackend` for distributed execution

### v0.3.0 (Planned)

- [ ] Cache warming strategies
- [ ] TTL policies per namespace
- [ ] Compression for large values

### Future

- [ ] Distributed cache coordination
- [ ] Cache invalidation patterns
- [ ] Event hooks for cache operations

---

## Examples Roadmap

| Example | Status | Description |
|---------|--------|-------------|
| `fastmcp-template` | ✅ Done | Starter template for FastMCP + mcp-refcache |
| `legal-mcp` | ⚪ Planned | Legal research server (Goal 01) |
| `faster-mcp` | ⚪ Research | Robyn-based FastMCP alternative (Goal 02) |

---

## Session Notes

_Use this space for current development session notes._

### 2024-12-28

- Created Goal 05: Real-Estate-Sustainability-MCP
  - Comprehensive sustainability analysis MCP server using fastmcp-template and mcp-refcache
  - Four core toolsets: Excel, PDF (with Chroma), sustainability frameworks, IFC integration
  - Supports ESG, LEED, BREEAM, and DGNB assessment frameworks
  - 7 tasks defined from cookiecutter generation to production deployment
  - Ready to begin implementation with Task-01: Generate project with fastmcp-template

### 2025-01-15

- Created Goal 04: Async-Timeout-Fallback (main feature for v0.2.0)
  - Feature request from yt-api-mcp semantic search experience
  - Long-running operations (1-2 min) cause MCP client timeouts
  - Solution: `async_timeout` param returns reference immediately, computation continues in background
  - 9 tasks defined: models, task tracking, decorator, polling, progress, retry, cancellation, tests, docs
  - Key decisions:
    - Integrate task tracking into RefCache (not separate TaskRegistry)
    - In-process asyncio.create_task() for MVP (external queue later)
    - Retryable failed tasks with configurable defaults
- Updated roadmap: v0.2.0 = Async Timeout Fallback

### 2026-01-19

- Goal 04: Hatchet SDK research complete
  - Cloned hatchet-dev/hatchet to `.agent/goals/04-Async-Timeout-Fallback/hatchet-reference/`
  - Analyzed `@hatchet.task()` decorator: input validators, timeouts, retries, rate limits
  - Key insight: Hatchet requires separate worker process, too complex for MVP
  - Decision: `TaskBackend` protocol with pluggable implementations
    - `MemoryTaskBackend` (ThreadPoolExecutor) — like document-mcp's JobManager
    - `HatchetTaskBackend` (Future) — optional `[hatchet]` extra
  - Task models already exist in `models.py`: TaskStatus, TaskProgress, TaskInfo, AsyncTaskResponse
  - Updated Goal 04 scratchpad with architecture, 11 tasks, sequence diagrams
  - document-mcp will consume this feature to replace its custom JobManager

### 2025-01-07

- Created Goals & Tasks structure in `.rules`
- Scaffolded Goal 01: Legal-MCP
  - Will port C# DejureMcp to Python/FastMCP
  - Multi-jurisdiction: German → EU → US law
- Scaffolded Goal 02: Faster-MCP
  - Research phase for Robyn-based FastMCP
  - Performance analysis from Blueshoe comparison article
