# Task-01: Baseline Audit of Retrieval Discoverability and Parity

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [x] Complete

## Objective
Create a complete, reviewable baseline of all places where retrieval behavior is documented or implemented, so the `0.2.1` patch can fix root discoverability gaps (`full=True`) and enforce full parity across non-submodule examples.

---

## Context
The bug report shows that agents are not reliably told how to retrieve complete cached values (`get_cached_result(ref_id, full=True)`), even though the capability exists in some downstream implementations.

Before implementation, we need an explicit audit matrix that identifies:
1. Core library doc surfaces to update
2. Core tests to harden
3. Non-submodule examples that need full parity
4. Submodule paths that must be excluded from edits

This task defines and locks scope for all subsequent tasks in Goal 10.

## Acceptance Criteria
- [x] Produce a **core surface inventory** with current behavior and required changes:
  - [x] `packages/python/src/mcp_refcache/cache.py` (`RefCache.cached()` doc injection)
  - [x] `packages/python/src/mcp_refcache/fastmcp/instructions.py` (`cache_instructions`, `cache_guide_prompt`, quick references, helper docs)
- [x] Produce a **core test inventory** with required assertions:
  - [x] `packages/python/tests/test_refcache.py`
  - [x] `packages/python/tests/test_fastmcp_instructions.py`
- [x] Produce a **non-submodule example parity matrix** for all applicable `get_cached_result` tools:
  - [x] Inputs include `full: bool = False`
  - [x] `full=True` path uses `cache.resolve(...)`
  - [x] Preview path forwards `max_size` into `cache.get(...)`
  - [x] Tool docstrings/instructions mention full retrieval + larger preview + pagination
- [x] Produce an explicit **excluded scope list** from `.gitmodules` (no edits allowed)
- [x] Capture audit decisions and open questions needed for implementation approval
- [x] Parent goal task table can be advanced with concrete implementation-ready findings

---

## Approach

### Step 1 — Build scope boundary table
- Enumerate all touched areas by category:
  - Core source
  - Core tests
  - Non-submodule examples
  - Submodule exclusions
- Confirm this task is strictly audit/planning (no code behavior changes).

### Step 2 — Core discoverability audit
- For each core surface, document:
  - Current wording
  - Missing capability signal (`full=True`)
  - Proposed canonical wording target
- Flag related helper APIs that might benefit from alignment (for Task-06).

### Step 3 — Example parity audit (non-submodule only)
- For each in-scope example retrieval tool:
  - Does input schema include `full`?
  - Is `full` forwarded to a full-value retrieval path?
  - Is `max_size` forwarded to `cache.get(...)`?
  - Are docs/instructions aligned with full retrieval guidance?
- Group examples by delta type:
  - Type A: already full parity
  - Type B: missing `full` only
  - Type C: missing `max_size` forwarding
  - Type D: missing both + doc mismatch

### Step 4 — Risk and rollout recommendations
- Identify high-risk edits (behavioral) vs low-risk edits (doc-only).
- Recommend rollout ordering for Task-02 to Task-06.

---

## Deliverables

1. **Audit Matrix (Core + Tests + Examples)**
   - Path
   - Current state
   - Required change
   - Risk level
   - Owner task

2. **Scope Boundary Record**
   - In-scope non-submodule examples
   - Out-of-scope submodules from `.gitmodules`

3. **Canonical Retrieval Wording Draft**
   - One normalized phrasing to be reused across:
     - decorator-injected docs
     - compact instructions
     - full guide quick reference
     - example tool docstrings

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2026-04-02 | Task created. Scope requires both core and examples, excludes submodules, targets `0.2.1`, and requires full parity. |
| 2026-04-02 | Baseline audit completed for core and non-submodule surfaces; implementation tasks now have concrete targets. |
| 2026-04-02 | Task marked complete after delivering scope matrix, exclusions, parity findings, and implementation handoff inputs to Tasks 02–07. |

### Audit Findings Snapshot
- Core discoverability gap confirmed in decorator injection (`RefCache.cached()`) and FastMCP instruction assets.
- Core tests lacked explicit contract coverage for `full=True` guidance before this patch plan.
- Non-submodule examples showed parity drift:
  - Several retrieval tools accepted `max_size` but did not consistently forward it.
  - `full=True` retrieval support was inconsistent outside `yt-mcp`.
- Submodule exclusion boundary confirmed from `.gitmodules` and locked for this goal.

### Initial Working Assumptions
- Full retrieval is an intentional capability and should be discoverable by default.
- Patch release can include additive docs and parity behavior without semver breakage.
- Example consistency is part of bug prevention, not optional cleanup.

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Parent Goal 10 approval | Resolved | Goal and task scope approved and documented in Goal 10 scratchpad |
| Final canonical wording sign-off | Resolved | Canonical retrieval wording handed off to Tasks 02/03/06 |
| Confirmation of non-submodule example set | Resolved | Scope boundary locked using `.gitmodules` exclusion list |

---

## Verification

- [x] Audit matrix is complete and references all required paths
- [x] Submodule exclusion list is explicit and matches `.gitmodules`
- [x] Every in-scope example has a parity classification (A/B/C/D)
- [x] Implementation tasks (02–07) have unambiguous inputs from this audit

---

## Related
- **Parent Goal:** [Goal 10 — Release Patch: Ref Retrieval Discoverability & Full Parity](../scratchpad.md)
- **Next Tasks:** Task-02, Task-03, Task-04, Task-05, Task-06
- **Primary Bug Reference:** `.agent/bugs/docstring-injestion-bug.md`
