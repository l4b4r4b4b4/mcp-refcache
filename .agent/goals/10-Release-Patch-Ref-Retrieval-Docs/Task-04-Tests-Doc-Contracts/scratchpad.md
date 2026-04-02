# Task-04: Tests as Documentation Contracts for Full Retrieval Discoverability

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [x] Complete

## Objective
Harden the Python test suite so `full=True` retrieval guidance is treated as a **contract**, not optional wording.  
If core docs drift and stop teaching agents how to retrieve full cached values, tests must fail immediately.

---

## Context
The bug report showed that core-generated guidance taught pagination and preview sizing but did not reliably teach full retrieval (`get_cached_result(ref_id, full=True)`).

Task-02 and Task-03 update core text surfaces; this task ensures those updates remain durable over time.

This task focuses on:
- `packages/python/tests/test_refcache.py`
- `packages/python/tests/test_fastmcp_instructions.py`

It verifies critical doc surfaces:
1. `@cache.cached()` auto-injected doc tail
2. `COMPACT_INSTRUCTIONS`
3. `FULL_CACHE_GUIDE` (including quick reference)
4. `cache_guide_prompt()` return content consistency

---

## Acceptance Criteria
- [x] Add tests asserting decorator-injected docstring includes explicit full retrieval guidance (`full=True`).
- [x] Add tests asserting compact instructions mention full retrieval usage.
- [x] Add tests asserting full guide includes full retrieval in both narrative section(s) and quick reference table.
- [x] Add tests asserting guide/prompt helper outputs remain aligned with updated source constants.
- [x] Existing tests continue to pass after additions (no regressions).
- [x] New assertions are specific enough to catch future accidental removals.

---

## Approach
Use a **contract-test style**:
- Assert on invariant phrases and API call snippets that must remain present.
- Avoid overfitting to punctuation/line breaks.
- Validate both high-level capability mention and actionable syntax.

### Planned Assertions (minimum)
1. Decorator docs contain:
   - `"full=True"`
   - `"get_cached_result"` and `"full"` in retrieval context
2. Compact instructions contain:
   - full retrieval bullet or equivalent syntax snippet
3. Full guide contains:
   - full retrieval explanation in retrieval/navigation content
   - quick-reference row for “Get full value” (or equivalent phrasing)
4. Prompt helper consistency:
   - `cache_guide_prompt()` still returns `FULL_CACHE_GUIDE` with full retrieval text present

---

## Steps
1. Review existing tests around:
   - `TestHierarchicalMaxSize` docstring assertions (`test_refcache.py`)
   - instruction constant assertions (`test_fastmcp_instructions.py`)
2. Add focused tests for full retrieval contract.
3. Run targeted tests first.
4. Run full Python test suite.
5. Tighten assertions if they are too weak (false pass risk).

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2026-04-02 | Task created as doc-contract hardening for `full=True` discoverability. |
| 2026-04-02 | Added contract tests for decorator injection, compact/full guide `full=True` discoverability, quick-reference rows, reusable retrieval guidance helper, and `with_cache_docs` coverage. |
| 2026-04-02 | Validation completed: targeted core tests passed (`181 passed`), and full Python suite remained green (`730 passed, 39 skipped`). |

### Design Notes
- Keep assertions stable but meaningful:
  - Prefer checking semantic markers (`full=True`, `get_cached_result`) over exact full paragraph match.
- If wording evolves, tests should still fail only when capability discoverability regresses.

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-02 core decorator doc updates | Resolved | Decorator-injected docs now include explicit `get_cached_result(ref_id, full=True)` guidance |
| Task-03 instruction/guide updates | Resolved | Compact/full guide surfaces now include full retrieval and larger-preview guidance |
| CI test runtime baseline | Resolved | Targeted tests were run first, then full package tests to confirm no regressions |

---

## Commands & Snippets

```/dev/null/commands.sh#L1-9
# Targeted runs (fast feedback)
cd packages/python
uv run pytest tests/test_refcache.py -q
uv run pytest tests/test_fastmcp_instructions.py -q

# Full validation
uv run pytest
uv run ruff check . --fix
uv run ruff format .
```

---

## Verification

```/dev/null/verification.sh#L1-12
# 1) Contract tests pass
cd packages/python
uv run pytest tests/test_refcache.py tests/test_fastmcp_instructions.py -q

# 2) No regressions in Python package tests
uv run pytest

# 3) Optional: ensure no formatting/lint drift
uv run ruff check . --fix
uv run ruff format .
```

Expected outcome:
- New tests fail on pre-fix content.
- New tests pass after Task-02/03 updates.
- Suite remains green.

---

## Related
- **Parent Goal:** [Goal 10: Release Patch — Reference Retrieval Discoverability & Full-Parity Tooling](../scratchpad.md)
- **Related Tasks:**
  - [Task-02 Core Decorator Doc Injection](../Task-02-Core-Decorator-Doc-Injection/scratchpad.md)
  - [Task-03 FastMCP Instructions Guide](../Task-03-FastMCP-Instructions-Guide/scratchpad.md)
- **External Links:** None