# Goal 10: Release Patch — Reference Retrieval Discoverability & Full-Parity Tooling

> **Status**: 🟡 In Progress (Planning)
> **Priority**: P0 (Critical)
> **Created**: 2026-04-02
> **Updated**: 2026-04-02
> **Target Release**: `0.2.1` (patch)

## Overview

Ship a focused patch release to fix a critical discoverability/documentation gap in `mcp-refcache`: agents are not reliably informed that full cached values can be retrieved via `get_cached_result(ref_id, full=True)`.

This goal covers:

1. **Core library doc surfaces** (`@cache.cached()` injected docs + FastMCP instruction generators)
2. **Example parity** across in-repo, non-submodule MCP servers (`full=True` + `max_size` forwarding)
3. **Prompt/doc injection optimizations** so tool modules importing `mcp-refcache` expose the library’s retrieval capabilities consistently
4. **Release hygiene** for `0.2.1` (tests, changelog, version sync)

---

## Success Criteria

- [ ] `RefCache.cached()` injected docstring text documents all retrieval modes:
  - preview (default)
  - larger preview (`max_size`)
  - full retrieval (`full=True`)
- [ ] `cache_instructions()` compact output documents `full=True`.
- [ ] `cache_guide_prompt()` / full guide quick-reference includes “Get full value”.
- [ ] Core tests enforce `full=True` documentation presence for these surfaces.
- [ ] Non-submodule examples with `get_cached_result` reach **full parity**:
  - accept `full: bool`
  - use `cache.resolve(...)` when `full=True`
  - forward `max_size` to `cache.get(...)`
  - include consistent tool docstrings/instructions
- [ ] Prompt/doc-injection utilities are improved so decorated tools/tool modules can expose capability guidance consistently.
- [ ] `CHANGELOG.md` updated and patch release versioning prepared for `0.2.1`.

---

## Context & Background

A real downstream failure pattern surfaced in `yt-mcp`:

- Agents could paginate and tweak preview size, but did not discover full retrieval.
- Manual workaround was needed in downstream server docs.
- Root causes included both:
  1. missing discoverability of `full=True` in library-generated docs
  2. inconsistent example implementations around retrieval behavior

The patch must fix root discoverability in the library and prevent repeated downstream drift by aligning non-submodule examples.

---

## Constraints & Requirements

### Hard Requirements

- Patch scope must include **both core and examples**, as approved by maintainer.
- **Do not modify submodule code** in this patch.
- Implement **full parity** (not partial) in applicable non-submodule examples.
- Preserve security posture (no value leaks in denied/inaccessible cases).
- Keep patch-level semantics (`0.2.1`): no unrelated breaking API changes.

### Soft Requirements

- Keep wording consistent across injected docs, compact instructions, and full guide.
- Prefer minimal, explicit API/documentation additions over broad refactors.
- Reuse existing patterns from `yt-mcp` where proven.

### Out of Scope

- Refactoring independent architecture in unrelated modules.
- New major features unrelated to retrieval discoverability/parity.
- Any edits inside git submodules.

---

## Scope Boundaries

### In Scope (Core)

- `packages/python/src/mcp_refcache/cache.py`
- `packages/python/src/mcp_refcache/fastmcp/instructions.py`
- Relevant core tests:
  - `packages/python/tests/test_refcache.py`
  - `packages/python/tests/test_fastmcp_instructions.py`

### In Scope (Examples, non-submodule only)

Examples currently in-repo and not listed in `.gitmodules`:
- `examples/document-mcp`
- `examples/optimize-mcp`
- `examples/real-estate-sustainability-mcp`
- `examples/yt-mcp` (validate existing behavior, normalize wording)
- `examples/data_tools.py` (if applicable retrieval API exists)

### Explicitly Out of Scope (Submodules)

No changes in:
- `examples/finquant-mcp`
- `examples/BundesMCP`
- `examples/fastmcp-template`
- `examples/ifc-mcp`
- `examples/portfolio-mcp`
- `examples/legal-mcp`
- `examples/bim2sim-mcp`

---

## Approach

1. **Baseline audit** of all retrieval-doc and retrieval-API surfaces.
2. **Core doc injection fixes** in decorator + instruction guides.
3. **Doc-contract tests** to prevent regression.
4. **Example full-parity rollout** (non-submodule only).
5. **Prompt/doc-asset optimization** for tool modules importing `mcp-refcache`.
6. **Release validation & changelog** for `0.2.1`.

---

## Tasks

| Task ID | Description | Status | Depends On |
|---------|-------------|--------|------------|
| Task-01 | Baseline audit of core + non-submodule example retrieval surfaces | 🟢 Complete | - |
| Task-02 | Core decorator doc injection fix (`@cache.cached()`) for full retrieval discoverability | 🟢 Complete | Task-01 |
| Task-03 | FastMCP instructions/guide updates (`cache_instructions`, `cache_guide_prompt`, quick refs) | 🟢 Complete | Task-01 |
| Task-04 | Tests as doc contracts for full retrieval discoverability in core | 🟢 Complete | Task-02, Task-03 |
| Task-05 | Non-submodule example full-parity implementation (`full=True` + `max_size` forwarding + doc sync) | 🟢 Complete | Task-01 |
| Task-06 | Prompt/doc asset optimization for tool modules importing `mcp-refcache` | 🟢 Complete | Task-02, Task-03, Task-05 |
| Task-07 | Release `0.2.1` validation: lint/tests/changelog/version consistency | ⚪ Not Started | Task-04, Task-05, Task-06 |

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Inconsistent wording across core and examples creates new confusion | High | Medium | Centralize canonical phrasing in core instruction helpers and mirror it in examples |
| Example parity changes introduce behavior drift in edge cases | Medium | Medium | Add/adjust example-level tests where available; preserve error semantics |
| Scope creep into submodules | Medium | Low | Enforce explicit submodule exclusion list in Task-01 audit checklist |
| Patch unintentionally changes public behavior beyond docs/retrieval | High | Low | Restrict to retrieval path and docs; run focused + full test validation before release |

---

## Dependencies

- **Upstream**:
  - Existing `full=True` reference implementation pattern in `examples/yt-mcp`
  - Existing core doc and instruction architecture
- **Downstream**:
  - All MCP servers using `@cache.cached()` benefit from discoverability fix
  - Future server templates and tool modules can inherit clearer retrieval guidance

---

## Notes & Decisions

### Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-02 | Include both core and examples in patch | Fix must address root cause and downstream consistency together |
| 2026-04-02 | Exclude submodules from edits | Maintainer directive; avoid cross-repo coupling for patch |
| 2026-04-02 | Enforce full parity (not partial) in applicable non-submodule examples | Prevent recurring discoverability and retrieval inconsistencies |
| 2026-04-02 | Target release `0.2.1` | Semver patch for bug fix + docs/consistency improvements |

### Open Questions

- [ ] Should prompt/doc injection optimization be delivered as wording-only updates, or include a reusable helper for example tool modules?
- [ ] Do we want a short README patch note in addition to changelog for `0.2.1` retrieval guidance?

---

## References

- `.agent/bugs/docstring-injestion-bug.md`
- `packages/python/src/mcp_refcache/cache.py`
- `packages/python/src/mcp_refcache/fastmcp/instructions.py`
- `packages/python/tests/test_refcache.py`
- `packages/python/tests/test_fastmcp_instructions.py`
- `examples/yt-mcp/app/tools/cache.py` (reference behavior)
- `.gitmodules` (submodule exclusion boundary)