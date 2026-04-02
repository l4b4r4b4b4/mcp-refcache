# Task-02: Core Decorator Doc Injection — Full Retrieval Discoverability

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [x] Complete

## Objective
Implement and validate the core `@cache.cached()` docstring injection update so every decorated tool explicitly documents all retrieval modes, including full-value retrieval via `get_cached_result(ref_id, full=True)`.

---

## Context
The current injected cache documentation in `RefCache.cached()` explains pagination and preview size overrides, but does not mention the primary escape hatch from preview truncation (`full=True`).

Because this text is auto-injected into decorated tool docstrings, the omission propagates across downstream MCP servers and causes agent behavior drift (pagination loops, oversized preview attempts, inability to discover full retrieval path).

This task addresses the **core library source of truth** for decorator-injected guidance.

---

## Acceptance Criteria
- [x] `packages/python/src/mcp_refcache/cache.py` injected docstring block includes explicit full retrieval instruction:
      `get_cached_result(ref_id, full=True)`
- [x] Injected text clearly distinguishes all three retrieval paths:
  - default preview
  - larger preview (`max_size`)
  - full value (`full=True`)
- [x] Existing max-size documentation behavior remains intact:
  - tool-specific max size (`max_size=...`)
  - server default when unset
- [x] Async/polling related guidance remains semantically correct and not contradicted by new text.
- [x] No unrelated behavior changes in decorator execution logic.

---

## Approach
Update only the decorator’s injected documentation string (`cache_doc`) and keep runtime behavior untouched.

### Planned edits
1. Locate `cache_doc` composition in `RefCache.cached()` decorator.
2. Add a dedicated “Full retrieval” line with the canonical call format.
3. Keep existing preview and pagination messaging, but make retrieval modes explicit and non-overlapping.
4. Keep wording compact so generated tool docs stay readable for MCP clients.

### Proposed wording baseline
- **Caching Behavior**
  - Any input parameter can accept `ref_id`.
  - Large results return `ref_id + preview`.
  - Use `get_cached_result(ref_id, page=..., page_size=...)` for pagination.
- **Full retrieval**
  - Use `get_cached_result(ref_id, full=True)` to fetch complete value without preview truncation.
- **Preview size**
  - Keep existing dynamic `max_size_doc` text and per-call override guidance.

---

## Implementation Steps
1. Edit `cache.py`:
   - Update `cache_doc` multi-line injected markdown in `RefCache.cached()`.
2. Ensure text is consistent with core terminology used in FastMCP guidance:
   - `ref_id`
   - preview
   - pagination
   - full retrieval
3. Confirm no linter/type issues due to formatting changes.
4. Hand off to Task-04 for doc-contract tests (this task does not add tests directly unless required for stability).

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2026-04-02 | Task created with implementation plan for core injected decorator docs. |
| 2026-04-02 | Updated `RefCache.cached()` injected `cache_doc` text to include explicit `get_cached_result(ref_id, full=True)` full retrieval guidance while preserving existing `max_size` and pagination guidance. |

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01 baseline audit | Resolved | Audit completed; wording aligned to canonical retrieval language |
| Task-03 instruction updates | Resolved | Terminology aligned with instruction/guide updates (`full=True`, `max_size`, pagination) |

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Ambiguous wording between pagination and full retrieval | High | Medium | Explicitly separate “page” flow vs “full=True” flow |
| Doc inflation harms MCP tool discoverability | Medium | Medium | Keep injection concise and action-oriented |
| Mismatch with example tool docs | Medium | Medium | Coordinate phrasing with Task-05 parity rollout |

---

## Verification
Validation completed with targeted and suite-level checks.

Executed verification commands:
- `uv run pytest packages/python/tests/test_refcache.py tests/test_fastmcp_instructions.py -q --tb=short`
- `uv run ruff check packages/python/src/mcp_refcache/cache.py`
- `uv run ruff format packages/python/src/mcp_refcache/cache.py --check`

Observed results:
- Core instruction/decorator tests passed.
- Lint and formatting checks passed.
- Decorated function docstrings now include `get_cached_result(ref_id, full=True)` alongside existing `max_size` and pagination guidance.

---

## Related
- **Parent Goal:** [Goal 10 — Release Patch: Ref Retrieval Docs](../scratchpad.md)
- **Depends On:** Task-01-Baseline-Audit
- **Feeds Into:** Task-04-Tests-Doc-Contracts, Task-06-Automatic-Tool-Module-Doc-Assets
- **External Links:** `.agent/bugs/docstring-injestion-bug.md`
