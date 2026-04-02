# Task-03: FastMCP Instructions & Cache Guide Update

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [x] Complete

## Objective
Update FastMCP-facing instruction surfaces so agents explicitly discover and use all retrieval modes, including `get_cached_result(ref_id, full=True)`, with consistent wording across compact and full guidance.

---

## Context
The bug report shows a documentation gap in instruction-level guidance: agents are taught pagination and preview-size overrides but not the full retrieval path. This task addresses the FastMCP instruction/guide layer (not decorator injection, and not example tool implementations).

Parent goal requires:
- patch release scope (`0.2.1`)
- consistency and discoverability improvements
- no submodule edits

---

## Acceptance Criteria
- [ ] `COMPACT_INSTRUCTIONS` explicitly documents full retrieval: `get_cached_result(ref_id, full=True)`.
- [ ] `FULL_CACHE_GUIDE` includes full retrieval in both narrative sections and Quick Reference table.
- [ ] Guidance clearly distinguishes three retrieval modes:
  - preview (default response)
  - larger preview (`max_size`)
  - full retrieval (`full=True`)
- [ ] Wording is consistent with core cache behavior and avoids ambiguous language.
- [ ] `cache_instructions()` and `cache_guide_prompt()` continue returning expected surfaces without API changes.
- [ ] No changes outside intended files for this task.

---

## Approach

### Files in Scope
- `packages/python/src/mcp_refcache/fastmcp/instructions.py`

### Planned Changes
1. **Compact instructions update**
   - Add a dedicated bullet under "Working with References":
     - Full value retrieval via `get_cached_result(ref_id, full=True)`.
   - Keep pagination and pass-to-tool guidance intact.

2. **Full guide narrative update**
   - In retrieval/exploration guidance, add a short “Full retrieval” subsection.
   - Clarify when to use full retrieval vs pagination vs larger previews.

3. **Quick Reference table update**
   - Add row:
     - `Get full value` → `get_cached_result(ref_id, full=True)`
   - Keep existing rows for preview, page navigation, tool passing, private compute.

4. **Consistency pass**
   - Ensure phraseology is aligned across:
     - `COMPACT_INSTRUCTIONS`
     - `FULL_CACHE_GUIDE`
     - any embedded action wording (e.g., `resolve_full` references in examples)

5. **Non-goals for this task**
   - No decorator doc injection edits (`cache.py`) — handled in Task-02.
   - No example server tool changes — handled in Task-05.
   - No release/version/changelog edits — handled in Task-07.

---

## Content Design Decisions
- Prefer explicit command examples over abstract descriptions.
- Keep compact instructions concise; put detail in full guide.
- Avoid introducing new user-facing concepts beyond existing API behavior.
- Preserve existing structure to minimize patch risk.

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Wording drift between compact and full docs | Medium | Medium | Define one canonical phrasing and mirror it in both sections |
| Overly verbose compact instructions | Low | Medium | Keep full retrieval to one clear bullet in compact mode |
| Accidental behavior implication not backed by API | High | Low | Restrict text to already-supported call patterns only |

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01 baseline audit results | Resolved | Wording targets confirmed from Goal 10 scope and bug report |
| Task-02 decorator wording | Resolved | Terminology aligned around preview, pagination, `max_size`, and `full=True` |

---

## Verification
- Confirm updated instruction constants include:
  - `full=True`
  - `max_size`
  - `page`/`page_size`
- Confirm Quick Reference table includes full retrieval row.
- Ensure no function signature/API changes in `cache_instructions()` / `cache_guide_prompt()`.

---

## Session Log

| Date | Summary |
|------|---------|
| 2026-04-02 | Task created and scoped for FastMCP instruction/guide updates in patch `0.2.1` |
| 2026-04-02 | Updated `COMPACT_INSTRUCTIONS` with explicit full retrieval and larger preview actions |
| 2026-04-02 | Updated `FULL_CACHE_GUIDE` pagination section to document `full=True` and `max_size` retrieval modes |
| 2026-04-02 | Updated full guide quick reference with rows for “Get full value” and “Larger preview” |
| 2026-04-02 | Added reusable `retrieval_guidance_snippet()` helper and integrated it into cache doc helpers |
| 2026-04-02 | Added/updated tests in `packages/python/tests/test_fastmcp_instructions.py`; targeted suite passed |

---

## Related
- **Parent Goal:** [Goal 10 — Release Patch: Ref Retrieval Discoverability & Full-Parity Tooling](../scratchpad.md)
- **Depends On:** Task-01 (Baseline Audit)
- **Blocks:** Task-04 (Tests as doc contracts), Task-06 (Prompt/doc asset optimization)
- **External Links:** `.agent/bugs/docstring-injestion-bug.md`
