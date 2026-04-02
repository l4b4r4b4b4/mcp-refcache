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
| 05 | Real-Estate-Sustainability-MCP | ⚫ Superseded | - | 2025-08-01 |
| 06 | TypeScript-RefCache | 🟡 In Progress | P1 | 2025-07-16 |
| 07 | RE-CapEx-OpEx-ROI-MCP | 🔴 Blocked (on 08) | P1 | 2025-08-01 |
| 08 | BIM2Sim-MCP-Server | ⚪ Not Started | **P0** | 2025-08-01 |
| 09 | Parametric-Optimization-MCP | 🔴 Blocked (on 07+08) | P2 | 2025-08-01 |
| 10 | Release-Patch-Ref-Retrieval-Docs | 🟡 In Progress (Planning) | P0 | 2026-04-02 |

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
- [05-Real-Estate-Sustainability-MCP](./05-Real-Estate-Sustainability-MCP/scratchpad.md) — ⚫ Superseded — split into Goals 07, 08, 09
- [06-TypeScript-RefCache](./06-TypeScript-RefCache/scratchpad.md) — Port mcp-refcache to TypeScript/Bun with FastMCP (TS) integration and template repository
- [07-RE-CapEx-OpEx-ROI-MCP](./07-RE-CapEx-OpEx-ROI-MCP/scratchpad.md) — DIN 276 CapEx, BetrKV OpEx, annuity NPV/IRR/GuV calculation engine (WAT reimplementation)
- [08-BIM2Sim-MCP-Server](./08-BIM2Sim-MCP-Server/scratchpad.md) — **Foundation layer** — bim2sim energy simulation MCP server (factored from ifc-mcp)
- [09-Parametric-Optimization-MCP](./09-Parametric-Optimization-MCP/scratchpad.md) — Multi-criteria parametric optimization (NSGA-II, Pareto, sensitivity) across sim + calc
- [10-Release-Patch-Ref-Retrieval-Docs](./10-Release-Patch-Ref-Retrieval-Docs/scratchpad.md) — Patch release to fix `full=True` retrieval discoverability and enforce non-submodule example parity

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

### 05-Real-Estate-Sustainability-MCP (⚫ Superseded)

Original broad goal has been split into three focused goals:
- **Goal 07**: CapEx/OpEx/ROI calculation engine (the WAT)
- **Goal 08**: BIM2Sim energy simulation MCP server (the physics)
- **Goal 09**: Multi-criteria parametric optimization (the optimizer)

Remaining scope (PDF analysis, ESG/LEED/BREEAM/DGNB frameworks) may become a future goal.

### 06-TypeScript-RefCache

Port `mcp-refcache` to TypeScript/Bun for the Node.js MCP ecosystem (polyglot monorepo):

- **Motivation**: TypeScript on Bun offers 4x faster startup, native SQLite, native TypeScript execution
- **Target Framework**: FastMCP (TypeScript) by @punkpeye — most popular TS MCP framework
- **Primary Reference**: `fractal-agents-runtime` — proven Bun+Python+Nix polyglot monorepo (same author)
- **Features**: Full feature parity with Python v0.2.0 including async task system
- **Components**:
  - Core RefCache class with set/get/resolve/delete
  - Memory, SQLite (`bun:sqlite`), Redis backends
  - Access control (Actor, Permission, AccessPolicy)
  - Preview system with token counting (`js-tiktoken`)
  - Async task execution with MemoryTaskBackend
  - FastMCP integration helpers (cached wrapper, context derivation)
- **Template**: `fastmcp-ts-template` — Cookiecutter template (port of Python `fastmcp-template`)
- **Tooling**: `bun test` (built-in), Lefthook (polyglot git hooks), `tsc` (type-check)
- **Status**: 🟡 In Progress — Task-00 complete, Task-01 next
- **Branch**: `feat/monorepo-restructure`
- **Reference files**: `.agent/references/fractal-agents-runtime/`
- **Tasks**:
  0. ✅ Monorepo Migration (Bun + Python)
  1. Project Setup & Tooling (`bun test`, lefthook, CI)
  2. Models & Zod Schemas
  3. Backend Protocol & MemoryBackend
  4. RefCache Core Implementation
  5. Preview System (Token Counting)
  6. Access Control System
  7. SQLite (`bun:sqlite`) & Redis Backends
  8. Async Task System
  9. FastMCP Integration
  10. Template Repository (`fastmcp-ts-template`)

---

## Notes

- Each goal has its own directory under `.agent/goals/`
- Goals contain a `scratchpad.md` and one or more `Task-XX/` subdirectories
- Tasks are atomic, actionable units of work within a goal
- Use the template in `00-Template-Goal/` when creating new goals

---

## Recent Activity

### 2026-04-02
- Created Goal 10: Release-Patch-Ref-Retrieval-Docs
  - Scope approved: core + examples, explicitly excluding submodules
  - Target release: `0.2.1`
  - Full parity required for non-submodule example retrieval tools (`full=True` + `max_size` forwarding)
  - Added 7 tasks:
    1. Baseline audit
    2. Core decorator doc injection update
    3. FastMCP instruction/guide update
    4. Doc-contract test hardening
    5. Non-submodule example parity rollout
    6. Prompt/doc asset optimization
    7. Release validation and readiness

### 2025-07-16
- Goal 06: Updated with `fractal-agents-runtime` as primary monorepo reference
  - Copied reference files to `.agent/references/fractal-agents-runtime/`
  - Key patterns: Bun workspaces, Lefthook, Nix FHS, TypeScript interfaces, `bun test`
  - Updated decisions: `bun test` over Vitest, Lefthook over pre-commit, `js-tiktoken` over native tiktoken
  - Added Python ↔ TypeScript module mapping table for feature parity tracking
  - All work on `feat/monorepo-restructure` branch
  - Task-00 (Monorepo Migration) confirmed complete
  - Task-01 (Project Setup & Tooling) ready to start

### 2025-01-30
- Created Goal 06: TypeScript-RefCache
  - Port mcp-refcache to TypeScript/Bun for Node.js MCP ecosystem
  - Target FastMCP (TypeScript) by @punkpeye as integration framework
  - 11 tasks covering full port from monorepo migration to template repository
  - Key decisions: Bun-first, Zod schemas, ESM-only, monorepo (not separate repo)
  - Research completed: FastMCP TS API, @modelcontextprotocol/sdk, Bun capabilities
  - Includes companion `fastmcp-ts-template` (Task-10)

### 07-RE-CapEx-OpEx-ROI-MCP

Digital reimplementation of the iB-DOS WAT (Wirtschaftlichkeitsanalysetool) as MCP tools:

- **DIN 276 CapEx**: Cost groups KG 100–700, 4 hierarchy levels, AfA per VDI 2067, HOAI phase mapping
- **BetrKV OpEx**: All 17 legally defined Betriebskostenarten (§2 BetrKV), kalte + warme BK
- **Energy Cost Model**: kWh-based Arbeitspreis + Grundpreis per carrier (Wärme, Kälte, Strom WE/GE/LIS privat/LIS öffentlich)
- **Revenue Model**: Kaltmiete, Warmmiete, Mieterstrom, Fahrstrom, Einspeisevergütung, KWK-Zuschlag
- **GuV Engine**: Year-by-year P&L (EBITDA → EBIT → EBT → EAT) over configurable horizon (20y)
- **NPV/IRR**: Cashflow, discounted cashflow, Kapitalwert, interner Zinsfuß, dynamische Amortisation
- **Sensitivity**: Parametric variation of Netzverluste, Energiepreis, Kalkulationszins, FK-Anteil
- **Status**: 🔴 Blocked on Goal 08 — data model design can proceed, but validation needs simulation data
- **Reference**: WAT Excel files archived in `archive/ibdos-wat-reference/` (gitignored)

### 08-BIM2Sim-MCP-Server

**Foundation layer** — Factor bim2sim out of ifc-mcp into dedicated MCP server:

- **Build order**: This comes FIRST (bottom-up: physics → finance → optimization)
- **bim2sim integration**: Wraps TEASER (fast, Python-native) and EnergyPlus (detailed) backends
- **Multi-object/multi-system scenarios**: Vary insulation, HVAC, glazing, PV sizing per building object
- **Weather data**: DWD Testreferenzjahr (TRY) by PLZ/coordinates
- **eMobility simulation**: Load curves for uncontrolled/controlled charging, peak shaving (from iB-DOS AP 3.8)
- **Output contract**: Structured Pydantic models aligned with Goal 07 EnergySystem input schema
- **Async execution**: Long-running EnergyPlus sims via mcp-refcache async tasks
- **Status**: ⚪ Not Started — **Next to begin** (P0 Critical)
- **11 tasks**: Research → Scaffolding → Data Model → TEASER → Scenarios → Weather → EnergyPlus → eMobility → MCP Tools → Async → Goal 07 contract

### 09-Parametric-Optimization-MCP

Capstone layer — multi-criteria parametric optimization across simulation + calculation:

- **Orchestrates**: Goal 08 (simulation) + Goal 07 (financial calc) as objective function evaluators
- **Multi-objective**: NSGA-II (pymoo) for Pareto front generation (NPV vs CO₂ vs tenant cost vs ...)
- **Surrogate-assisted**: Gaussian Process surrogate to reduce expensive simulation calls (~100–200 vs 1000+)
- **Sensitivity analysis**: Sobol indices (SALib) to identify most impactful design parameters
- **Parameter space**: Insulation, glazing, HVAC type, PV/battery sizing, building standard (KfW 55/40/40+), eMobility
- **Status**: 🔴 Blocked on Goal 07 + Goal 08

### 10-Release-Patch-Ref-Retrieval-Docs

Patch-release goal to fix and harden retrieval discoverability for cached references:

- **Core bug fix**: Ensure `@cache.cached()` injected docs include full-value retrieval via `get_cached_result(ref_id, full=True)`
- **FastMCP guidance alignment**: Update compact/full instruction surfaces and quick-reference tables to include `full=True`
- **Example parity (non-submodule only)**: Enforce full parity in in-repo examples (`full` param, `cache.resolve(...)` path, `max_size` forwarding)
- **Prompt/doc asset optimization**: Reduce downstream drift by centralizing retrieval guidance assets for tool modules
- **Release target**: `0.2.1` patch with tests, changelog, and version sync
- **Status**: 🟡 In Progress (Planning)

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
- Created Goal 05: Real-Estate-Sustainability-MCP (now ⚫ Superseded)
  - Original broad goal split into Goals 07, 08, 09 on 2025-08-01
  - See individual goal scratchpads for current scope

### 2025-08-01
- **Split Goal 05 into three focused goals (bottom-up build order)**:
  - **Goal 08 (P0)**: BIM2Sim MCP Server — physics/energy simulation foundation (comes FIRST)
  - **Goal 07 (P1)**: RE CapEx/OpEx ROI MCP — WAT financial calculation (blocked on 08)
  - **Goal 09 (P2)**: Parametric Optimization MCP — multi-criteria optimizer (blocked on 07+08)
- Archived iB-DOS WAT reference files to `archive/ibdos-wat-reference/` (gitignored)
  - WAT Excel with 23 sheets (6 variants × Eingabe/GuV/Ergebnis + Sensitivität)
  - BetrKV operating cost breakdown, DIN 276 KG400/KG700, VDI 2067 AfA tables
  - Bruttowarmmietenvergleich, GuV, Flächen/Nutzung, Förderungen
- Analyzed WAT structure in detail: Eingabe (55 params), GuV (103 rows × 22 years), NPV/IRR/Amortisation
- Identified bim2sim-mcp as the correct starting point (bottom-up: simulation data before financial model)

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
