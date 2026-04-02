# Task-07: Release 0.2.1 Validation and Readiness

## Status
- [ ] Not Started
- [x] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Finalize and verify the `0.2.1` patch release for reference retrieval discoverability and full-parity example behavior, ensuring quality gates pass and release metadata is consistent.

---

## Context
This task is the release gate for Goal 10. Core changes (decorator injection + FastMCP instructions), test hardening, and non-submodule example parity must be validated together before publishing `0.2.1`.

The release is patch-scoped and must remain focused:
- Fix discoverability of `get_cached_result(ref_id, full=True)`
- Ensure consistent retrieval guidance and behavior
- Avoid unrelated refactors or breaking API changes

---

## Acceptance Criteria
- [x] All Task-04, Task-05, and Task-06 deliverables are complete and reviewed.
- [x] `ruff check . --fix` and `ruff format .` run clean in `packages/python`.
- [x] Targeted tests pass for changed modules and behaviors.
- [x] Full Python test suite passes.
- [ ] Coverage remains at or above project threshold (>= 80%).
- [x] `pyproject.toml` version and `src/mcp_refcache/__init__.py` `__version__` both set to `0.2.1`.
- [x] `CHANGELOG.md` includes clear `0.2.1` patch notes.
- [x] No submodule files are modified.
- [ ] Release branch diff is limited to approved patch scope.
- [ ] Final release checklist is signed off.

---

## Approach

### 1) Scope Integrity Check
1. Verify modified files are only within approved core and non-submodule example scope.
2. Confirm no accidental edits under submodule paths listed in `.gitmodules`.
3. Review diff for unrelated changes (format churn, import churn, non-goal edits).

### 2) Static Quality Gates
1. Run lint and formatting in Python package context.
2. Resolve all diagnostics introduced by this patch.
3. Re-run checks to ensure clean, deterministic output.

### 3) Test Validation
1. Run focused tests first:
   - `tests/test_refcache.py`
   - `tests/test_fastmcp_instructions.py`
   - any updated example tests
2. Run full package tests.
3. Validate no regressions in retrieval behavior, doc-contract assertions, or permissions/error semantics.

### 4) Release Metadata & Documentation
1. Bump version to `0.2.1` in:
   - `packages/python/pyproject.toml`
   - `packages/python/src/mcp_refcache/__init__.py`
2. Update `CHANGELOG.md` with:
   - bug summary
   - impacted surfaces
   - compatibility notes
3. Confirm release notes accurately describe patch scope and exclusions (submodules not changed).

### 5) Final Readiness Review
1. Validate branch status is clean and review-ready.
2. Produce final checklist summary:
   - quality gates
   - version sync
   - changelog complete
   - scope boundary respected
3. Mark task complete only after all checklist items are green.

---

## Release Checklist (0.2.1)

- [x] Scope validated (no submodule edits)
- [x] Lint clean
- [x] Format clean
- [x] Targeted tests pass
- [x] Full tests pass
- [ ] Coverage threshold met
- [x] Version sync complete (`pyproject.toml` + `__init__.py`)
- [x] Changelog updated
- [ ] Diff reviewed for patch-only scope
- [ ] Ready for PR review

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2026-04-02 | Task created with release-quality gate plan for patch `0.2.1`. |
| 2026-04-02 | Validation in progress: targeted core tests passed (`181 passed`), full Python suite passed (`730 passed, 39 skipped`), and lint/format checks passed. |
| 2026-04-02 | Release metadata updated: version bumped to `0.2.1` in `pyproject.toml` and `__init__.py`; `CHANGELOG.md` updated with 0.2.1 patch notes. |

### Key Validation Focus
- Doc discoverability for `full=True` must be present in all intended core surfaces.
- Example parity must include both `full=True` retrieval and `max_size` forwarding where applicable.
- Error messaging and permission behavior must remain stable.

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-04: Core doc-contract tests | Resolved | Completed and validated in targeted and full test runs |
| Task-05: Example/template full parity | Resolved | Non-submodule parity surface completed and documented |
| Task-06: Prompt/doc asset optimization | Resolved | Helper-based guidance optimization completed and tested |
| Maintainer release approval | Pending | Required after final checklist items are green |

---

## Verification

Use the Python package workspace (`packages/python`) for these checks:

- Lint: `uv run ruff check . --fix`
- Format: `uv run ruff format .`
- Focused tests: `uv run pytest tests/test_refcache.py tests/test_fastmcp_instructions.py -ra --tb=short`
- Full tests: `uv run pytest -ra --tb=short`
- Coverage: `uv run pytest --cov=src/mcp_refcache --cov-report=term-missing`
- Version sync check:
  - `pyproject.toml` has `version = "0.2.1"`
  - `src/mcp_refcache/__init__.py` has `__version__ = "0.2.1"`

---

## Related
- **Parent Goal:** [Goal 10: Release Patch — Reference Retrieval Discoverability & Full-Parity Tooling](../scratchpad.md)
- **Depends On:** Task-04, Task-05, Task-06
- **Related Tasks:** Task-01 through Task-06
- **External Links:** `.agent/bugs/docstring-injestion-bug.md`
