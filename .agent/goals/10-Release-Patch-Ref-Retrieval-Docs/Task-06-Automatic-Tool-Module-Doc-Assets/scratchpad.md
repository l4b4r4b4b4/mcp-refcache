# Task-06: Automatic Tool-Module Doc Assets & Prompt Optimization

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [x] Complete

## Objective
Design and implement a consistent, reusable documentation/prompt asset strategy so tools that use `mcp-refcache` automatically communicate the full retrieval capabilities (`preview`, `max_size`, `full=True`) without manual workaround text.

---

## Context
Core docs are being fixed in Task-02 and Task-03, and non-submodule examples are being aligned in Task-05. This task closes the remaining gap: reducing ongoing doc drift by making it easier for tool modules to inherit correct guidance automatically.

The maintainer requested optimizations “along similar lines” so decorated tools and modules importing `mcp-refcache` expose capability guidance consistently, not only through ad-hoc server instructions.

This task must not modify submodule examples.

---

## Acceptance Criteria
- [x] Define a canonical doc-asset model for retrieval guidance that covers:
  - [x] Preview behavior
  - [x] Larger preview with `max_size`
  - [x] Full retrieval with `full=True`
  - [x] Reference passing / chaining behavior
- [x] Extend or add helper(s) in `mcp_refcache.fastmcp` so tool/module docs can be composed from shared assets instead of copy-paste strings.
- [x] Ensure helper output is compatible with existing FastMCP instruction surfaces and style.
- [x] Update non-submodule example tool modules to use the shared helper(s) where practical.
- [x] Keep behavior/documentation alignment between:
  - [x] `@cache.cached()` injected docs
  - [x] compact/full FastMCP instructions
  - [x] tool-level descriptions/docstrings
- [x] Add or update tests that lock these doc-asset contracts to prevent regressions.
- [x] Document the usage pattern for downstream authors (how to opt-in with minimal boilerplate).

---

## Approach

### Phase 1 — Asset Design
1. Define a minimal set of reusable doc fragments for retrieval behavior.
2. Decide integration points:
   - low-level string constants
   - helper function(s) for tool descriptions
   - optional decorator-style convenience for docstring augmentation
3. Keep output concise and unambiguous for LLM/tool discovery.

### Phase 2 — API Integration
1. Implement/extend helper APIs in `mcp_refcache.fastmcp.instructions`.
2. Ensure helper API naming is explicit and composable (no vague “utils/helper” pattern).
3. Preserve backward compatibility for existing helper calls where possible.

### Phase 3 — Adoption in Non-Submodule Examples
1. Apply helper-based docs to non-submodule tool modules that expose `get_cached_result` or related retrieval flows.
2. Remove duplicated wording where helper output now covers the same instructions.
3. Validate no accidental behavior changes in runtime logic.

### Phase 4 — Validation
1. Add/adjust tests for helper output contracts.
2. Run targeted tests for `fastmcp/instructions` and docstring injection.
3. Run full Python test suite in release validation task.

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2026-04-02 | Added `retrieval_guidance_snippet()` to FastMCP instruction assets for canonical retrieval guidance (`page/page_size`, `max_size`, `full=True`). |
| 2026-04-02 | Integrated helper output into `cached_tool_description()` and `with_cache_docs()` so tool/module docs inherit the same retrieval guidance contract. |
| 2026-04-02 | Aligned compact and full cache guides to include explicit full retrieval and larger preview actions, with matching quick-reference rows. |
| 2026-04-02 | Added regression tests in `packages/python/tests/test_fastmcp_instructions.py` for helper output and discoverability contracts. |

## Design Notes
- Canonical retrieval phrase now exists in a reusable helper, reducing copy/paste drift.
- Helper scope was kept intentionally small to avoid over-engineering.
- Security semantics were preserved: full retrieval still depends on normal cache permissions.

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Helper API over-engineering | Medium | Medium | Start with small API; optimize only repeated, proven patterns |
| Divergence between helper output and core docs | High | Medium | Share canonical constants; assert key phrases in tests |
| Example adoption causes noisy diffs | Low | Medium | Limit edits to retrieval/docs sections and keep behavior unchanged |
| Hidden dependency on submodule templates | Medium | Low | Explicitly skip submodule paths in update scope |

---

## Files Likely Involved
- `packages/python/src/mcp_refcache/fastmcp/instructions.py`
- `packages/python/src/mcp_refcache/fastmcp/__init__.py` (exports, if needed)
- `packages/python/tests/test_fastmcp_instructions.py`
- Non-submodule example tool modules under `examples/` that import/use `mcp-refcache` and expose retrieval tooling

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-02 core decorator doc injection final wording | Resolved | Canonical retrieval wording finalized and aligned |
| Task-03 FastMCP guide updates | Resolved | Helper assets aligned with compact/full guide action model |
| Task-05 example parity updates | Resolved | Non-submodule parity surface updated and synchronized with helper-guided wording |

---

## Verification
- [x] Confirm helper-generated docs include all required retrieval modes.
- [x] Confirm tests assert `full=True` presence in helper output where applicable.
- [x] Confirm non-submodule example docs no longer rely on stale/custom phrasing for retrieval capabilities.
- [x] Confirm no edits were made in submodule directories.

Validation summary:
- Targeted core tests passed, including new helper/discoverability assertions.
- Full Python suite remained green after helper integration changes.

---

## Related
- **Parent Goal:** [Goal 10 — Release Patch: Ref Retrieval Discoverability & Full-Parity Tooling](../scratchpad.md)
- **Depends On:** Task-02, Task-03, Task-05
- **Related Tasks:** Task-04 (doc-contract tests), Task-07 (release validation)
- **Reference Bug:** `.agent/bugs/docstring-injestion-bug.md`
