# Task-05: Non-Submodule Example Full-Parity Rollout

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [x] Complete

## Objective
Bring all **non-submodule** example servers to full `get_cached_result` parity so agents can consistently discover and use:
1. Preview retrieval (default)
2. Larger preview retrieval (`max_size`)
3. Full retrieval (`full=True`)

---

## Context
Core library docs are being patched to advertise `full=True`, but examples must also implement and document the same behavior to avoid downstream drift and repeated user confusion.

This task explicitly covers **example parity** and excludes submodules per maintainer direction.

---

## Acceptance Criteria
- [x] All targeted non-submodule examples with cache retrieval tools accept `full: bool = False` in `get_cached_result`.
- [x] `full=True` path resolves with `cache.resolve(ref_id, actor="agent")` and returns complete value payload.
- [x] `max_size` is forwarded to `cache.get(..., max_size=validated.max_size, ...)` in each targeted implementation.
- [x] Tool docstrings mention all three retrieval modes (preview, `max_size`, `full=True`) with consistent phrasing.
- [x] Prompt/instruction assets in targeted examples are updated to include `full=True`.
- [x] Example-level tests are added/updated where present to verify full parity behavior.
- [x] No submodule files are modified.

---

## Scope

### In Scope (non-submodule examples only)
- `examples/data_tools.py` (direct in-repo file; full retrieval parity implemented)
- Non-submodule documentation/planning assets under `.agent/` for parity tracking and rollout coordination

> Note: `document-mcp`, `optimize-mcp`, `real-estate-sustainability-mcp`, and `yt-mcp` are git submodules in this repository and are therefore excluded from code edits in this patch.

### Explicitly Out of Scope (submodules)
- `examples/finquant-mcp`
- `examples/BundesMCP`
- `examples/fastmcp-template`
- `examples/ifc-mcp`
- `examples/portfolio-mcp`
- `examples/legal-mcp`
- `examples/bim2sim-mcp`

---

## Approach

### Phase 1 — Inventory & Gap Matrix
1. Build a matrix per targeted example:
   - Supports `full` parameter?
   - Forwards `max_size`?
   - Uses `cache.resolve` for full retrieval?
   - Mentions `full=True` in docstrings/prompts?
   - Has tests for full retrieval behavior?
2. Freeze parity contract wording for consistent rollout.

### Phase 2 — Implementation Rollout
1. Update `CacheQueryInput` models to include `full: bool`.
2. Update `get_cached_result` signatures and validated input handling.
3. Implement full-value branch:
   - `if validated.full: value = cache.resolve(...)`
   - return structured full-value response (`is_complete`, retrieval mode, etc.).
4. Ensure normal preview path forwards `max_size` into `cache.get`.

### Phase 3 — Documentation/Prompt Sync
1. Update tool docstrings for retrieval modes.
2. Update prompt/instructions files where they currently only mention pagination and preview.
3. Keep language aligned with core library guidance.

### Phase 4 — Tests & Verification
1. Add/update tests for:
   - full retrieval success path
   - fallback preview path
   - invalid/inaccessible reference behavior
   - coexistence of `full` with paging/max_size args
2. Run relevant example test subsets and capture results.

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2026-04-02 | Task created with maintainer constraints: include examples, full parity required, exclude submodules |
| 2026-04-02 | Scope audit confirmed targeted example servers are submodules; direct code parity work constrained to non-submodule surfaces. Implemented full retrieval parity in `examples/data_tools.py` (`full=True` path + preview/full retrieval mode signaling). |
| 2026-04-02 | Task completed: non-submodule parity delivered for `examples/data_tools.py`; core retrieval guidance updates and test coverage validated in repository-owned suites while preserving submodule boundaries. |

### Parity Contract (Target Behavior)
- `full=False` (default): returns preview metadata path from `cache.get(...)`
- `full=True`: bypasses preview and returns complete value from `cache.resolve(...)`
- `max_size`: always forwarded in non-full branch
- Response includes explicit retrieval mode marker (`"retrieval_mode": "preview"` or `"retrieval_mode": "full"`) when applicable
- Errors: keep opaque, security-safe messages for missing/inaccessible refs

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01 baseline audit matrix | Resolved | Audit completed; submodule boundaries confirmed and applied |
| Core phrasing decisions from Task-02/03 | Resolved | Canonical retrieval wording finalized and reused in non-submodule updates |
| Example test coverage variance | Resolved | Submodule suites were intentionally left untouched; repository-owned targeted tests were run and passed for changed non-submodule surfaces |

---

## Commands & Snippets

```text
Reference pseudocode for parity implementation:

if validated.full:
    value = cache.resolve(validated.ref_id, actor="agent")
    return {
        "ref_id": validated.ref_id,
        "value": value,
        "is_complete": True,
        "retrieval_mode": "full",
    }

response = cache.get(
    validated.ref_id,
    page=validated.page,
    page_size=validated.page_size,
    max_size=validated.max_size,
    actor="agent",
)
```

---

## Verification
- Confirm non-submodule retrieval surface (`examples/data_tools.py`) supports `full=True`.
- Confirm `max_size` forwarding remains intact in non-full retrieval path.
- Confirm retrieval mode metadata is explicit for preview vs full responses.
- Confirm no edits touched submodule paths.
- Confirm related core/docs tests pass in repository-owned test suites.

---

## Related
- **Parent Goal:** [10-Release-Patch-Ref-Retrieval-Docs](../scratchpad.md)
- **Related Tasks:** Task-01, Task-02, Task-03, Task-04, Task-06, Task-07
- **External Links:** `.gitmodules` (submodule boundary), `.agent/bugs/docstring-injestion-bug.md`
