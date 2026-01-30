# Goals Index & Tracking Scratchpad

> Central hub for tracking all active goals in the mcp-refcache repository.

---

## Active Goals

| ID | Goal Name | Status | Priority | Last Updated |
|----|-----------|--------|----------|--------------|
| 01 | Legal-MCP | ⚪ Not Started | P2 | 2025-01-07 |
| 02 | Faster-MCP | ⚪ Not Started | P3 | 2025-01-07 |
| 03 | KI-Strategie-Presentation | 🟢 Complete | P1 | 2025-01-20 |
| 04 | Async-Task-Backends | 🟡 In Progress | P1 | 2026-01-19 |
| 05 | Real-Estate-Sustainability-MCP | 🔴 Not Started | P1 | 2024-12-28 |
| 06 | TypeScript-RefCache | ⚪ Not Started | P1 | 2025-01-30 |
| 07 | (Reserved) | ⚪ Not Started | - | - |
| 08 | (Reserved) | ⚪ Not Started | - | - |
| 09 | (Reserved) | ⚪ Not Started | - | - |
| 10 | (Reserved) | ⚪ Not Started | - | - |

---

## Status Legend

- 🟢 **Complete** — Goal achieved and verified
- 🟡 **In Progress** — Actively being worked on
- 🔴 **Blocked** — Waiting on external dependency or decision
- ⚪ **Not Started** — Planned but not yet begun
- ⚫ **Archived** — Abandoned or superseded

---

## Priority Levels

- **P0 (Critical)** — Blocking other work or system stability
- **P1 (High)** — Important for near-term objectives
- **P2 (Medium)** — Should be addressed when time permits
- **P3 (Low)** — Nice to have, no urgency

---

## Quick Links

- [00-Template-Goal](./00-Template-Goal/scratchpad.md) — Template for new goals
- [01-Legal-MCP](./01-Legal-MCP/scratchpad.md) — Comprehensive legal research MCP server with mcp-refcache
- [02-Faster-MCP](./02-Faster-MCP/scratchpad.md) — Robyn-based FastMCP alternative for high-performance MCP servers
- [03-KI-Strategie-Presentation](./03-KI-Strategie-Presentation/scratchpad.md) — 4-Folien PPTX für KI-Strategie 2026 Meeting
- [04-Async-Timeout-Fallback](./04-Async-Timeout-Fallback/scratchpad.md) — Async task execution with pluggable backends (v0.2.0 main feature)
- [05-Real-Estate-Sustainability-MCP](./05-Real-Estate-Sustainability-MCP/scratchpad.md) — Real Estate Sustainability Analysis MCP server with Excel, PDF, and sustainability frameworks
- [06-TypeScript-RefCache](./06-TypeScript-RefCache/scratchpad.md) — Port mcp-refcache to TypeScript/Bun with FastMCP (TS) integration and template repository

---

## Goal Summaries

### 01-Legal-MCP

Build a comprehensive legal research MCP server using FastMCP + mcp-refcache that provides AI assistants with structured access to legal information across multiple jurisdictions:

- **Phase 1**: German law via dejure.org (port from C# DejureMcp)
- **Phase 2**: EU law via EUR-Lex
- **Phase 3**: US law via Congress.gov, CourtListener
- **Use Case**: Demonstrates mcp-refcache for caching large, stable legal documents

### 02-Faster-MCP

Explore creating a Robyn-based (Rust runtime) alternative to FastMCP for performance-critical MCP servers:

- **Performance Target**: 10,000+ concurrent users (vs FastAPI's ~246 RPS limit)
- **Approach**: API parity with FastMCP, Rust runtime via Robyn
- **Status**: Research/feasibility phase

### 03-KI-Strategie-Presentation

4-Folien PPTX-Präsentation (Deutsch) für CEO-Meeting "Feierabendbier mit KI-Fokus":

- **Folie 1**: DSGVO-Compliance mit Azure OpenAI (EU-Deployment)
- **Folie 2**: Agent/MCP-Trennung mit Animation (mcp-refcache Beispiele)
- **Folie 3**: Flowise AI für Workflow-Orchestrierung
- **Folie 4**: Praxisbeispiele (IFC-MCP, BundesMCP)
- **Zielgruppe**: Nicht-technische Mitarbeiter (Immobilienberatung)
- **Technik**: python-pptx (separates UV-Projekt in presentations/)

### 04-Async-Task-Backends

Add async task execution to `@cache.cached()` with pluggable backends:

- **Problem**: Long-running operations (1-2 min) cause MCP client timeouts
- **Solution**: `async_timeout` param returns reference immediately, computation continues via TaskBackend
- **Architecture**: `TaskBackend` protocol with pluggable implementations
- **Backends**:
  - `MemoryTaskBackend` (MVP) - ThreadPoolExecutor, in-process
  - `HatchetTaskBackend` (Future) - Distributed, durable execution
- **Features**: Progress callbacks, retry mechanism, cancellation API
- **Use Cases**: document-mcp OCR jobs, yt-api-mcp semantic search
- **Status**: 🟡 In Progress — Main feature for v0.2.0
- **Tasks**: 11 tasks (protocol, backends, decorator, polling, progress, retry, cancellation, tests, docs)
- **Research**: Hatchet SDK cloned to `.agent/goals/04-Async-Timeout-Fallback/hatchet-reference/`

### 05-Real-Estate-Sustainability-MCP

Build a comprehensive Real Estate Sustainability Analysis MCP server using fastmcp-template and mcp-refcache integration:

- **Excel Toolset**: Handle large datasets with mcp-refcache for energy, cost, and building metrics
- **PDF Analysis**: Content extraction with Chroma-powered semantic search for certificates and reports
- **Sustainability Frameworks**: ESG, LEED, BREEAM, and DGNB assessment tools
- **IFC Integration**: Correlate building geometry/properties from ifc-mcp with sustainability metrics
- **Target Users**: Real estate developers, sustainability consultants, facility managers
- **Status**: 🔴 Not Started — Ready for cookiecutter generation

### 06-TypeScript-RefCache

Port `mcp-refcache` to TypeScript/Bun as `mcp-refcache-ts` for the Node.js MCP ecosystem:

- **Motivation**: TypeScript on Bun offers 4x faster startup, native SQLite, native TypeScript execution
- **Target Framework**: FastMCP (TypeScript) by @punkpeye - most popular TS MCP framework
- **Features**: Full feature parity with Python v0.2.0 including async task system
- **Components**:
  - Core RefCache class with set/get/resolve/delete
  - Memory, SQLite, Redis backends
  - Access control (Actor, Permission, AccessPolicy)
  - Preview system with token counting (tiktoken)
  - Async task execution with MemoryTaskBackend
  - FastMCP integration helpers (cached wrapper, context derivation)
- **Template**: `fastmcp-ts-template` - Cookiecutter template like Python's fastmcp-template
- **Status**: ⚪ Not Started — 10 tasks defined
- **Tasks**:
  1. Project Setup & Tooling
  2. Models & Zod Schemas
  3. Backend Protocol & MemoryBackend
  4. RefCache Core Implementation
  5. Preview System (Token Counting)
  6. Access Control System
  7. SQLite & Redis Backends
  8. Async Task System
  9. FastMCP Integration
  10. Template Repository

---

## Notes

- Each goal has its own directory under `.agent/goals/`
- Goals contain a `scratchpad.md` and one or more `Task-XX/` subdirectories
- Tasks are atomic, actionable units of work within a goal
- Use the template in `00-Template-Goal/` when creating new goals

---

## Recent Activity

### 2025-01-30
- Created Goal 06: TypeScript-RefCache
  - Port mcp-refcache to TypeScript/Bun for Node.js MCP ecosystem
  - Target FastMCP (TypeScript) by @punkpeye as integration framework
  - 10 tasks covering full port from project setup to template repository
  - Key decisions: Bun-first, Zod schemas, ESM-only, Vitest testing
  - Research completed: FastMCP TS API, @modelcontextprotocol/sdk, Bun capabilities
  - Includes companion `fastmcp-ts-template` (Task-10)

### 2026-01-19
- Goal 04: Hatchet SDK research complete
  - Cloned hatchet-dev/hatchet to `.agent/goals/04-Async-Timeout-Fallback/hatchet-reference/`
  - Analyzed `@hatchet.task()` decorator patterns
  - Decided: TaskBackend protocol for pluggable backends
  - MemoryTaskBackend (ThreadPoolExecutor) for MVP
  - HatchetTaskBackend as future optional enhancement
  - Updated scratchpad with architecture and 11 tasks
  - Models already exist: TaskStatus, TaskProgress, TaskInfo, AsyncTaskResponse

### 2024-12-28
- Created Goal 05: Real-Estate-Sustainability-MCP
  - Comprehensive sustainability analysis MCP server using fastmcp-template
  - Four core toolsets: Excel, PDF (with Chroma), sustainability frameworks, IFC integration
  - Supports ESG, LEED, BREEAM, and DGNB assessment frameworks
  - 7 tasks defined from project generation to production deployment
  - Ready to begin with cookiecutter generation

### 2025-01-15
- Created Goal 04: Async-Timeout-Fallback
  - Main feature for v0.2.0 release
  - Add `async_timeout` parameter to `@cache.cached()` decorator
  - 9 tasks: models, task tracking, decorator, polling, progress, retry, cancellation, tests, docs
  - Originated from yt-api-mcp semantic search timeout issues
  - General-purpose solution for any MCP server with long-running operations

### 2025-01-20
- Created Goal 03: KI-Strategie-Presentation
  - 4 Folien PPTX für CEO "Feierabendbier mit KI-Fokus"
  - Themen: DSGVO-Compliance, MCP-Trennung, Flowise AI, Praxisbeispiele
  - python-pptx Projekt in presentations/ki-strategie-2026/
  - 6 Tasks definiert (Setup, Folien, Animation, Beispiele, Recherche, Review)

### 2025-01-07
- Created Goal 01: Legal-MCP — Comprehensive legal research MCP server
  - Focus on German law via dejure.org initially
  - Will port existing C# DejureMcp implementation
  - Integrate mcp-refcache for efficient caching of legal texts
- Created Goal 02: Faster-MCP — Robyn-based FastMCP alternative
  - Research phase: Analyze feasibility of FastMCP → Robyn port
  - Performance motivation: Robyn handles 10k+ users vs FastAPI's ~246 RPS
- Updated `.rules` with Goals & Tasks Structure section
