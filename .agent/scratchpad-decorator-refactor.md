# Scratchpad: @cache.cached() Decorator Refactoring

## Task Overview

Refactor the `@cache.cached()` decorator to provide full MCP tool integration with:
1. **Pre-execution**: Deep recursive ref_id resolution in all inputs
2. **Post-execution**: Always return structured CacheResponse (never raw values)
3. **Size-based response**: Full value OR preview based on max_size threshold
4. **Security-aware resolution**: Integrate with access/permission system

---

## Current Status: Session 7 Complete ✅

### Completed ✅
- [x] Created `src/mcp_refcache/resolution.py` with ref_id detection and resolution utilities
- [x] Updated `cached` decorator to resolve refs in inputs before execution
- [x] Updated `cached` decorator to always return structured response
- [x] Added size-based decision logic (full value vs preview)
- [x] Fixed existing tests for new decorator behavior
- [x] Added 37 tests for ref_id resolution (`tests/test_resolution.py`)
- [x] Added 8 tests for decorator ref resolution (`TestRefCacheDecoratorRefResolution`)
- [x] Exported resolution utilities from main module
- [x] All 439 tests passing, linting clean
- [x] Added tiktoken to dev dependencies (was missing, causing test skips)
- [x] Updated `docs/rules-template.md` with new decorator patterns
- [x] Updated example server (`examples/mcp_server.py`) to use new decorator:
  - `generate_sequence` now uses `@cache.cached(namespace="sequences")`
  - `matrix_operation` now uses `@cache.cached(namespace="matrices")` with ref_id input support
  - Changed RefCache to use token-based sizing (default) instead of character-based
  - Updated docstrings with caching/pagination/references documentation tags
  - Kept `calculate`, `store_secret`, `compute_with_secret`, `get_cached_result` as-is
- [x] Fixed return type annotation issue for FastMCP compatibility:
  - Decorator now modifies `wrapper.__annotations__["return"]` to `dict[str, Any]`
  - This happens before `@mcp.tool` reads annotations
  - Users keep natural return types in source code
- [x] **Live tested with Zed/Claude** - all features verified:
  - ✅ Small results → full `value` + `is_complete: true`
  - ✅ Large results → `preview` + `is_complete: false` + pagination message
  - ✅ Token-based sizing (500 token threshold)
  - ✅ Ref_id resolution (single and multiple refs)
  - ✅ Cache hit (same inputs return same ref_id)
  - ✅ Cache miss (different inputs create new entry)
  - ✅ **Cache hit via ref_id resolution** (resolved values match previous call)
  - ✅ Secret storage with custom AccessPolicy
  - ✅ Secret computation (EXECUTE without READ)
  - ✅ Permission denied when agent tries to read secret
- [x] Committed all changes
- [x] **Session 3**: Pagination auto-switch, async tests, opaque errors (459 tests)
- [x] **Session 4**: Hierarchical max_size feature with documentation injection (499 tests)
- [x] **Session 5**: Research complete on FastMCP Context integration
- [x] **Session 6**: Context-scoped caching implementation (569 tests)
- [x] **Session 7**: Langfuse user_id/session_id/metadata propagation (579 tests)

### TODO 📋
- [ ] Consider short ref_id prefix matching (like git/docker) - see discussion below
- [ ] Create a second example with character-based sizing for comparison
- [ ] Live test Langfuse integration with real Langfuse credentials

---

## Design Decisions

### 1. Response Format (Always Structured)

**Small result (fits within max_size):**
```python
{
    "ref_id": "myapp:abc123",
    "value": [1, 2, 3, 4, 5],  # Full data included
    "is_complete": True,
    "size": 15,  # tokens or characters
    "total_items": 5,
}
```

**Large result (exceeds max_size):**
```python
{
    "ref_id": "myapp:abc123",
    "preview": [1, 50, 100, "... and 997 more"],
    "is_complete": False,
    "preview_strategy": "sample",
    "total_items": 1000,
    "original_size": 5000,
    "preview_size": 100,
    "page": 1,
    "total_pages": 20,
    "message": "Use get_cached_result(ref_id='myapp:abc123') to paginate.",
}
```

### 2. Ref_id Resolution Pattern

Agent calls with ref_ids anywhere in the input structure:
```python
process_data(
    prices={
        "AAPL": [100, 101, "finquant:abc111"],  # ref_id in nested list
        "MSX": "finquant:abc122"                 # ref_id as dict value
    },
    multiplier="finquant:abc123"                 # ref_id as top-level param
)
```

Decorator resolves ALL ref_ids recursively before function execution.

### 3. Ref_id Pattern

Pattern: `{cache_name}:{hex_hash}`
- Cache name: alphanumeric, hyphens, underscores, starts with letter
- Hash: 8+ hexadecimal characters
- Regex: `^[a-zA-Z][a-zA-Z0-9_-]*:[a-f0-9]{8,}$`

Examples:
- `finquant:2780226d27c57e49` ✅
- `my-cache:abc123def` ✅
- `myapp:12345678` ✅
- `just-a-string` ❌
- `123:abc` ❌ (doesn't start with letter)

### 4. Security Considerations

**CRITICAL**: Ref resolution must integrate with access control and NOT leak information.

When resolution fails due to permissions:
```python
# ❌ WRONG - Leaks existence of ref_id
{"error": "Permission denied for ref_id 'secret:abc123'"}

# ✅ CORRECT - Opaque error
{"error": "Invalid or inaccessible reference", "ref_id": "secret:abc123"}
```

Same error message for:
- Ref doesn't exist
- Ref expired
- Permission denied

This prevents enumeration attacks.

---

## Implementation Plan

### Phase 1: Core Decorator (Current Focus)
1. Fix failing tests by updating expectations
2. Add new tests for structured responses
3. Ensure basic ref resolution works

### Phase 2: Security Integration
1. Wrap resolution in try/except that catches KeyError AND PermissionError
2. Return opaque error for both cases
3. Add tests for permission-denied scenarios
4. Ensure no information leakage

### Phase 3: Edge Cases
1. Circular reference detection (ref A contains ref B which contains ref A)
2. Maximum resolution depth limit
3. Partial resolution failure handling (some refs fail, others succeed)

### Phase 4: Documentation & Instructions
1. Update docstrings with full behavior documentation
2. Update `rules-template.md`
3. Update example server
4. Add instructions injection to decorated functions

---

## Files Involved

### Created/Modified ✅
- `src/mcp_refcache/resolution.py` - NEW: Ref resolution utilities (335 lines)
- `src/mcp_refcache/cache.py` - Modified: Updated `cached` decorator with:
  - `resolve_refs=True` parameter (default)
  - `max_size` parameter (override cache default)
  - Always returns structured response (`is_complete`, `value`/`preview`)
  - Injects cache documentation into docstrings
- `src/mcp_refcache/__init__.py` - Export resolution utilities
- `tests/test_refcache.py` - Updated decorator tests + new ref resolution tests
- `tests/test_resolution.py` - NEW: 37 tests for resolution utilities

### Still Need to Update
- `docs/rules-template.md` - Update patterns
- `examples/mcp_server.py` - Update to use new decorator

---

## Test Cases Needed

### Ref Resolution Tests
```python
def test_is_ref_id_valid_pattern():
    assert is_ref_id("myapp:abc12345") == True
    assert is_ref_id("just-a-string") == False

def test_resolve_refs_nested_dict():
    # ref_ids at various nesting levels

def test_resolve_refs_mixed_list():
    # list with some ref_ids and some values

def test_resolve_refs_not_found():
    # missing ref returns error without leaking info

def test_resolve_refs_permission_denied():
    # same error as not found (security)
```

### Decorator Tests
```python
def test_cached_returns_structured_response():
    # Always returns dict with ref_id, value/preview, is_complete

def test_cached_small_result_includes_value():
    # is_complete=True, full value included

def test_cached_large_result_includes_preview():
    # is_complete=False, preview included

def test_cached_resolves_ref_in_input():
    # ref_id in parameter gets resolved before execution

def test_cached_resolves_nested_refs():
    # deeply nested ref_ids all get resolved
```

---

## Session Notes

### 2024-XX-XX: Core Implementation Complete
- Created resolution.py with RefResolver class
- Updated cached decorator to use new pattern
- Breaking change: decorator now always returns structured response
- Updated tests to expect new format
- Added comprehensive test coverage (37 resolution tests + 8 decorator tests)
- All 434 tests passing

### Key Insight
The decorator serves TWO purposes now:
1. **Memoization** - Same inputs → return cached result (but structured)
2. **MCP Integration** - Ref resolution, structured responses, size handling

This is intentional - all cached functions become MCP-ready automatically.

### New Decorator Signature
```python
@cache.cached(
    namespace="public",        # Namespace for isolation
    policy=AccessPolicy(...),  # Custom access control
    ttl=3600,                  # TTL in seconds
    max_size=500,              # Override cache default for size threshold
    resolve_refs=True,         # Resolve ref_ids in inputs (default True)
    actor="agent",             # Actor for permission checks
)
```

---

## Questions to Resolve

1. **Should we support a "raw mode" for non-MCP use cases?**
   - Current decision: No, always structured. Simple functions don't need caching.

2. **What happens if only SOME refs fail to resolve?**
   - Current: Fail entire call if any ref fails
   - Alternative: Partial resolution with error info?

3. **Maximum resolution depth?**
   - Need to prevent infinite loops if ref A contains ref B contains ref A
   - Proposal: Max depth of 10, then error

4. **Short ref_id prefix matching (like git/docker)?**
   - Currently: Full hashes like `finquant:2780226d27c57e49`
   - Idea: Accept short prefixes like `finquant:2780226d` (first 8 chars)
   - **Pros**: Easier for agents, less tokens
   - **Cons**: 
     - Need prefix-matching lookup (not just exact key)
     - Collision handling as cache grows
     - Redis: would need SCAN/pattern matching instead of direct GET
     - Ambiguity errors if multiple matches
   - **Decision**: Keep full hashes for v1. Nice-to-have for later.
   - **Future approach**: Resolution accepts short prefixes, expands internally; 
     return short form in responses for display; store prefix index for quick lookups

---

## Dependency Fixes

### tiktoken Added to Dev Dependencies
- Was optional extra only, not in dev group
- Tests were skipping tiktoken-dependent tests
- Fixed with: `uv add --dev tiktoken`
- Now 439 tests pass (only 3 transformers tests skipped - transformers is heavy, OK to skip)

---

## Live Testing Results (Zed/Claude)

### Test Matrix

| Test | Result | Details |
|------|--------|---------|
| Small sequence → full value | ✅ | `is_complete: true`, 10 fibonacci = 30 tokens |
| Large sequence → preview | ✅ | `is_complete: false`, 500 fibonacci = 9885 tokens |
| Matrix transpose | ✅ | Returns structured response |
| Ref_id as input | ✅ | `matrix_a="calculator:xxx"` resolved correctly |
| Multiple ref_ids | ✅ | Both matrix_a and matrix_b resolved |
| Cache hit (same inputs) | ✅ | Same ref_id returned |
| Cache hit via ref resolution | ✅ | **Key feature**: resolved values match → cache hit |
| Secret storage | ✅ | Custom AccessPolicy applied |
| Secret computation | ✅ | `42 * 2 + 10 = 94` |
| Secret read protection | ✅ | "Permission denied" for agent |
| FastMCP type validation | ✅ | No schema errors after annotation fix |

### Cache Hit via Ref Resolution Example

```
1. matrix_operation([[1,3],[2,4]], "transpose") → ref_id: calculator:4236fabde4424caf
2. matrix_operation("calculator:09c3ef408ad55e9a", "transpose")
   - Resolves ref to [[1,3],[2,4]]
   - Cache key matches step 1
   - Returns SAME ref_id: calculator:4236fabde4424caf ✅
```

---

## Next Steps

### Completed ✅
1. ~~Update `tests/test_refcache.py` to expect structured responses~~ ✅
2. ~~Add `tests/test_resolution.py` for resolution utilities~~ ✅
3. ~~Run full test suite~~ ✅ (439 passed)
4. ~~Update rules-template.md with new decorator patterns~~ ✅
5. ~~Add tiktoken to dev dependencies~~ ✅
6. ~~Update example server to use new decorator~~ ✅
7. ~~Live test with Zed/Claude~~ ✅
8. ~~Fix FastMCP return type validation~~ ✅

### High Priority (Security/Stability)
9. ~~**Circular reference detection**~~ ✅ - Prevent infinite loops if ref A → ref B → ref A
   - Track visited ref_ids to detect cycles immediately (no depth limit needed)
   - Raise `CircularReferenceError` with full chain on cycle detection
   - Support nested ref resolution (resolved values containing more ref_ids)
   - No false positives for same ref_id in sibling positions
   - Added 5 tests for circular reference scenarios

10. ~~**Opaque error messages**~~ ✅ - Security: same error for not-found, expired, permission-denied
    - Both KeyError and PermissionError now raise/return identical opaque messages
    - Error message: "Invalid or inaccessible reference" (no 'not found', 'expired', or 'permission denied')
    - Prevents attackers from determining if a ref_id exists via error message analysis
    - Added tests to verify opaque error handling

### Medium Priority (Polish) - Next Session
11. **Pagination UX** - The `sample` strategy doesn't respond to page params
    - Consider auto-switching to `paginate` when page is specified
    - Or document current behavior more clearly

12. **Async ref resolution tests** - Current tests are sync only
    - Add async function tests for resolution

### Lower Priority (Nice to Have)
13. **Short ref_id prefix matching** - Like git/docker (`calculator:861a` instead of full hash)
    - Accept short prefixes, expand internally
    - Handle ambiguity with clear errors

14. **Character-based sizing example** - Second example server for comparison

15. **Test with finquant-mcp** - Real-world validation with actual financial data server

---

## Session 2 Summary (Completed)

### Features Implemented
1. **Circular reference detection** - Immediate cycle detection without depth limit
2. **Opaque error messages** - Security hardening to prevent enumeration attacks
3. **Return type annotation fix** - Decorator auto-updates annotations for FastMCP compatibility

### Test Results
- 445 tests passing (up from 439)
- 5 new circular reference tests
- 2 new opaque error security tests

### Commits
1. `feat(decorator): add structured responses and ref_id resolution`
2. `docs(scratchpad): update with live testing results`
3. `docs(rules-template): update with latest features and patterns`
4. `feat(resolution): add circular reference detection`
5. `security(resolution): use opaque error messages to prevent info leakage`

---

## Testing the New Features

### Test Circular Reference Detection (in Zed/Claude)

Can be tested by creating a scenario where cached values reference each other:
1. Store a value that contains its own ref_id (self-reference)
2. Expected: `CircularReferenceError` with chain info

Note: In normal usage, circular refs are unlikely since tools don't typically
store ref_ids inside their return values. This is a safety net.

### Test Opaque Errors (in Zed/Claude)

1. Try to use `get_cached_result` with a non-existent ref_id
2. Try to read a secret ref_id directly (should be permission denied)
3. Both should return similar error messages (not revealing why it failed)

Example already tested in previous session:
```
get_cached_result(ref_id="calculator:8036bb698358a5f7")  # secret ref
→ {"error": "Permission denied", ...}

get_cached_result(ref_id="calculator:nonexistent12345")  # fake ref
→ {"error": "Not found", ...}
```

Note: The MCP server's `get_cached_result` tool still shows different messages.
The opaque errors are in the resolution layer. Consider updating the tool handlers
to use opaque messages as well for full security.

---

---

## Session 3: Medium Priority Polish Tasks

### Current Focus

#### Task 1: Pagination UX - Auto-switch to Paginate Strategy

**Problem:** When using `SampleGenerator` (default), the `page` and `page_size` parameters are explicitly ignored. The docstring even says "page: Ignored for sample strategy." However, instructions tell users to use `get_cached_result(ref_id, page=2)` for pagination - which does nothing with the sample strategy.

**Solution:** Auto-switch to `PaginateGenerator` when `page` is specified.

**Implementation:**
- Modify `RefCache._create_preview()` to check if `page` is not None
- If page is specified and current generator is `SampleGenerator`, use `PaginateGenerator` for that call
- This is transparent to the user and "just works"

**Files to modify:**
- `src/mcp_refcache/cache.py` - `_create_preview` method

**Tests to add:**
- `test_sample_generator_switches_to_paginate_when_page_specified`
- `test_sample_generator_stays_sample_when_no_page`
- `test_paginate_generator_respects_page_always`

---

#### Task 2: Async Ref Resolution Tests

**Problem:** Current resolution tests only test sync functions. The `@cache.cached()` decorator handles both sync and async functions, but we don't have explicit async tests for ref resolution.

**Files to modify:**
- `tests/test_resolution.py` - Add async test class

**Tests to add:**
- `test_async_function_resolves_refs_in_args`
- `test_async_function_resolves_refs_in_kwargs`
- `test_async_function_resolves_nested_refs`
- `test_async_function_circular_ref_detection`

---

#### Task 3 (Optional): Opaque Errors in MCP Tool Handlers

**Problem:** The `get_cached_result` tool in `examples/mcp_server.py` still returns different error messages:
- "Permission denied" for PermissionError
- "Not found" for KeyError

This could leak information about whether a reference exists.

**Solution:** Unify error messages like we did for the ref resolution layer.

**Files to modify:**
- `examples/mcp_server.py` - `get_cached_result` function

---

### Implementation Plan

1. **Start with Task 1** (Pagination UX) - most impactful for user experience
2. **Then Task 2** (Async tests) - improves test coverage
3. **Optionally Task 3** (Opaque errors) - minor security polish

### Session 3 Progress

- [x] Task 1: Pagination UX auto-switch ✅
  - [x] Implement auto-switch in `_create_preview`
  - [x] Add 7 tests for auto-switch behavior
  - [x] Verified: `get_cached_result(ref_id, page=2)` now returns page 2
- [x] Task 2: Async resolution tests ✅
  - [x] Add `TestAsyncDecoratorRefResolution` class (7 tests)
  - [x] Test async decorated functions with ref resolution
  - [x] Test cache hit via resolved refs in async
  - [x] Test circular ref detection in async context
- [x] Task 3: Opaque errors in get_cached_result ✅
  - [x] Unified error messages: "Invalid or inaccessible reference"
  - [x] PermissionError and KeyError return identical responses

### Session 3 Summary

**Tests:** 459 passing (up from 445)

**Changes Made:**
1. `src/mcp_refcache/cache.py`:
   - Added `SampleGenerator` and `PaginateGenerator` imports
   - Modified `_create_preview()` to auto-switch to `PaginateGenerator` when `page` is specified
   
2. `src/mcp_refcache/resolution.py`:
   - Fixed B904 linting errors with `from None` in exception re-raises

3. `tests/test_refcache.py`:
   - Added `TestPaginationAutoSwitch` class (7 tests)
   - Added `TestAsyncDecoratorRefResolution` class (7 tests)

4. `examples/mcp_server.py`:
   - Unified error handling in `get_cached_result` for opaque errors

**Key Improvements:**
- Pagination now "just works" even with SampleGenerator default
- Async functions properly resolve refs before execution
- No information leakage about ref existence vs permission denial

### Live Testing Results (Session 3)

Tested with `max_size=64` tokens:

| Test | Result |
|------|--------|
| Sample strategy (no page) | ✅ Returns evenly-spaced sample |
| Paginate strategy (with page=2) | ✅ Auto-switches, returns items 10-19 |
| Page 5 content | ✅ Items 40-49 correct |
| Opaque errors (fake ref_id) | ✅ Generic message, no info leak |
| Matrix pagination | ✅ Nested structures work |

---

## Session 4: Hierarchical max_size Feature ✅ COMPLETE

### Problem Statement

Currently, `max_size` is only configurable at the server level via `PreviewConfig`. This is inflexible because:

1. Some tools produce larger outputs that need bigger previews
2. Some calls may need custom sizes based on context
3. No way to override at runtime without reconfiguring the cache

### Solution: Three-Level max_size Hierarchy

**Priority (highest to lowest):**
1. **Per-call** - `get_cached_result(ref_id, max_size=200)`
2. **Per-tool** - `@cache.cached(max_size=500)`
3. **Server default** - `PreviewConfig(max_size=1024)`

### Implementation Complete ✅

#### Files Modified

1. **`src/mcp_refcache/fastmcp/instructions.py`**
   - Added "Preview Size Control" section to `COMPACT_INSTRUCTIONS`
   - Added "Preview Size Control" section to `FULL_CACHE_GUIDE`
   - Documents three-level priority with examples

2. **`src/mcp_refcache/cache.py`**
   - Added `max_size` parameter to `RefCache.get()` method
   - Added `max_size` parameter to `_create_preview()` method
   - Updated `cached()` decorator to inject max_size info into docstrings
   - Docstring now shows tool-specific max_size or "server default"

3. **`examples/mcp_server.py`**
   - Added `max_size` field to `CacheQueryInput` model
   - Added `max_size` parameter to `get_cached_result` tool
   - Passes max_size to `cache.get()`

#### Tests Added

**`tests/test_refcache.py` - `TestHierarchicalMaxSize` (9 tests):**
- `test_server_default_max_size_used_when_no_override`
- `test_per_call_max_size_overrides_server_default`
- `test_per_call_max_size_can_be_smaller_than_default`
- `test_get_method_accepts_max_size`
- `test_per_tool_max_size_in_cached_decorator`
- `test_per_tool_max_size_allows_larger_results`
- `test_decorator_docstring_includes_max_size_info`
- `test_decorator_docstring_mentions_server_default_when_no_max_size`
- `test_decorator_docstring_mentions_per_call_override`

**`tests/test_fastmcp_instructions.py` (31 tests):**
- Tests for compact instructions content
- Tests for full cache guide content
- Tests for preview size control documentation
- Tests for `cache_instructions()`, `cache_guide_prompt()`, etc.
- Tests for `with_cache_docs()` decorator
- Tests for `cached_tool_description()` function

### API Usage

```python
# Level 1: Server default (lowest priority)
cache = RefCache(
    preview_config=PreviewConfig(max_size=1024)
)

# Level 2: Tool-specific (medium priority)
@cache.cached(max_size=500)
async def generate_sequence(...):
    ...
# Docstring now includes: "**Preview Size:** max_size=500 tokens. Override per-call..."

# Level 3: Per-call (highest priority)
response = cache.get(ref_id, max_size=100)
# Or via tool:
get_cached_result(ref_id, max_size=100)
```

### Documentation Injection

The `@cache.cached()` decorator now injects max_size info into docstrings:

**With explicit max_size:**
```
**Preview Size:** max_size=500 tokens. Override per-call with `get_cached_result(ref_id, max_size=...)`.
```

**Without max_size (server default):**
```
**Preview Size:** server default. Override per-call with `get_cached_result(ref_id, max_size=...)`.
```

### Test Results

- **499 tests passing** (up from 459)
- 40 new tests added (9 hierarchical max_size + 31 instructions)
- All linting clean

### Live Testing Results ✅

Tested with Zed/Claude using the calculator MCP server:

| Test | Command | Result |
|------|---------|--------|
| Server default (64 tokens) | `generate_sequence("fibonacci", 100)` | ✅ `preview_size: 64`, 11 items |
| Per-call max_size=20 | `get_cached_result(ref_id, max_size=20)` | ✅ `preview_size: 18`, 3 items |
| Per-call max_size=200 | `get_cached_result(ref_id, max_size=200)` | ✅ `preview_size: 199`, 34 items |
| Pagination + max_size | `get_cached_result(ref_id, page=2, page_size=10, max_size=50)` | ✅ Both work together |
| Small result → full value | `matrix_operation([[1,2,3],[4,5,6],[7,8,9]], "transpose")` | ✅ `is_complete: true` |

**Key Observations:**
- Smaller `max_size` → fewer items in preview (more aggressive sampling)
- Larger `max_size` → more items in preview
- Pagination and max_size work independently and can be combined
- Tool docstrings now visible to agents with max_size info

---

## Next Session Starting Prompt

```
Continue mcp-refcache: Polish & Review

## Context
- Sessions 1-4 complete, 499 tests passing
- All core features implemented:
  - Ref resolution with circular detection
  - Structured responses (value vs preview)
  - Pagination auto-switch
  - Opaque error messages
  - Hierarchical max_size with doc injection
- See `.agent/scratchpad-decorator-refactor.md` for full context

## What Was Done (Session 4)
- Implemented three-level max_size hierarchy
- Added max_size to RefCache.get(), _create_preview(), and get_cached_result
- Updated cache_instructions() with Preview Size Control section
- Decorator injects max_size info into docstrings
- Added 40 new tests (9 + 31)

## Remaining Tasks
- [ ] Short ref_id prefix matching (like git/docker)
- [ ] Character-based sizing example

## Guidelines
- Follow `.rules` (TDD, document as you go)
- Run `uv run ruff check . --fix && uv run ruff format .`
- Run `uv run pytest tests/` before considering complete
```

---

## Session 5: Context-Scoped Caching (Research Complete, Implementation Planned)

### Problem Statement

Currently, namespaces are hardcoded at decoration time:
```python
@cache.cached(namespace="session:conv-123")  # ❌ Hardcoded!
```

In real-world MCP servers (banking, healthcare, enterprise), we need:
```python
@cache.cached(namespace="org:{org_id}:user:{user_id}")  # ✅ Dynamic!
```

Where `user_id`, `session_id`, and `org_id` come from:
1. **Session context** (set by the MCP client, NOT the agent)
2. **Tool call metadata** (injected by FastMCP middleware)
3. **NOT from function arguments** (agents shouldn't control their own scoping!)

### Security Concern

If we let agents pass `user_id` as a function parameter, a malicious agent could:
```python
# Agent tries to access another user's data
get_account_balance(user_id="victim_user")  # ❌ Should be forbidden!
```

Instead, `user_id` should come from the authenticated session context.

### FastMCP Context Research

**What FastMCP provides:**

| Source | Available Data |
|--------|----------------|
| `Context` | `session_id`, `request_id`, `client_id` |
| `Context.get_state(key)` | Any value set by middleware |
| `get_access_token()` | `client_id`, `scopes`, `claims` (JWT with `sub`, `tenant_id`, etc.) |

**Key Pattern:** Middleware extracts identity from auth tokens → sets in context state → tools read from context state.

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_access_token

# Middleware sets identity (runs before tool)
class IdentityMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        token = get_access_token()
        ctx = context.fastmcp_context
        if token:
            ctx.set_state("user_id", token.claims.get("sub"))
            ctx.set_state("org_id", token.claims.get("org_id"))
        return await call_next(context)

# Tool reads from context (NOT from agent input!)
@mcp.tool
async def get_balance(ctx: Context) -> dict:
    user_id = ctx.get_state("user_id")  # Secure - from auth
    ...
```

### Critical Discovery: Decorator Order Works!

**Question:** Can our decorator access FastMCP Context if it wraps `@mcp.tool`?

**Answer:** YES! FastMCP uses `ContextVar` and sets context BEFORE calling tools.

```python
# From fastmcp/server/dependencies.py
def get_context() -> Context:
    from fastmcp.server.context import _current_context
    context = _current_context.get()
    if context is None:
        raise RuntimeError("No active context found.")
    return context
```

**Execution flow:**
1. FastMCP receives request
2. FastMCP does `async with Context()` → sets `_current_context` ContextVar
3. FastMCP calls the tool (wrapped by both decorators)
4. Our `cache.cached` wrapper runs → can call `get_context()` ✅
5. Tool executes

**This means we don't need `ctx` as a parameter - we can call `get_context()` internally!**

### Proposed Solution: Context-Scoped Caching

```python
from mcp_refcache import RefCache

cache = RefCache(name="banking")

@cache.cached(
    namespace_template="org:{org_id}:user:{user_id}",  # Dynamic template
    owner_template="user:{user_id}",                   # Auto-set owner
    session_scoped=True,                               # Bind to session
)
@mcp.tool
async def get_account_balance(account_id: str) -> dict:
    # No ctx parameter needed in function signature!
    # Decorator internally calls get_context() to get:
    #   - user_id from ctx.get_state("user_id")
    #   - org_id from ctx.get_state("org_id")
    #   - session_id from ctx.session_id
    # 
    # Namespace becomes: "org:acme_corp:user:alice"
    # Owner becomes: "user:alice"
    # Session binding: Only this session can access
    ...
```

### Template Expansion Logic

**Template syntax:** `"org:{org_id}:user:{user_id}"`

**Value sources (in order):**
1. `ctx.get_state(key)` - Values set by middleware
2. `ctx.session_id` - For `{session_id}` placeholder
3. `ctx.client_id` - For `{client_id}` placeholder

**Default fallbacks when values are missing:**
- `{user_id}` → `"anonymous"`
- `{org_id}` → `"default"`
- `{session_id}` → `"nosession"`
- `{client_id}` → `"unknown"`

This keeps caching working even without full auth setup.

### Integration with Permission System

The existing permission system already supports all needed features:

| Feature | Existing Support | How We'll Use It |
|---------|------------------|------------------|
| `AccessPolicy.owner` | ✅ | Set from `owner_template` |
| `AccessPolicy.bound_session` | ✅ | Set from `ctx.session_id` when `session_scoped=True` |
| `DefaultActor.user(id, session_id)` | ✅ | Create from context for permission checks |
| Namespace ownership checks | ✅ | `DefaultPermissionChecker` validates access |

### New Decorator Parameters

```python
@cache.cached(
    # Existing parameters
    namespace: str = "public",           # Static namespace (existing)
    policy: AccessPolicy | None = None,
    ttl: float | None = None,
    max_size: int | None = None,
    resolve_refs: bool = True,
    actor: str = "agent",
    
    # NEW: Context-scoped parameters
    namespace_template: str | None = None,    # Dynamic namespace with {placeholders}
    owner_template: str | None = None,        # Dynamic owner with {placeholders}
    session_scoped: bool = False,             # Bind to ctx.session_id
    context_keys: list[str] | None = None,    # Required context keys (validation)
)
```

**Priority:** `namespace_template` > `namespace` (template wins if both provided)

### Implementation Phases

#### Phase 1: Context-Scoped Decorator (Core Feature)
- Add `namespace_template`, `owner_template`, `session_scoped` to `@cache.cached()`
- Import and use `get_context()` from `fastmcp.server.dependencies`
- Extract values from `ctx.get_state()` and `ctx.session_id`
- Build namespace and owner from templates with fallbacks
- Set `bound_session` if `session_scoped=True`
- Handle case where FastMCP is not installed (graceful degradation)

#### Phase 2: Convenience Middleware (Optional Helper)
- Provide `IdentityMiddleware` that extracts from access tokens
- Sets standard keys: `user_id`, `org_id`, `tenant_id`, `session_id`
- Users can use our middleware or write their own

**Phase 1 is self-contained** - it just needs context state to be set (by any middleware).

### Test Plan

```python
# Test with mock Context
class TestContextScopedCaching:
    def test_namespace_template_expansion(self):
        # Mock get_context() to return context with state
        ...
    
    def test_owner_template_expansion(self):
        ...
    
    def test_session_scoped_binds_to_session(self):
        ...
    
    def test_missing_context_value_uses_fallback(self):
        ...
    
    def test_no_fastmcp_graceful_degradation(self):
        # When fastmcp not installed, use static namespace
        ...
    
    def test_context_scoped_cache_isolation(self):
        # Different users get different cache entries
        ...
    
    def test_permission_check_uses_context_actor(self):
        # Actor derived from context for access control
        ...
```

### Files to Modify

1. **`src/mcp_refcache/cache.py`**
   - Add new parameters to `cached()` decorator
   - Add template expansion logic
   - Add `get_context()` integration (with try/except for non-FastMCP)

2. **`src/mcp_refcache/context_integration.py`** (NEW)
   - Template expansion utilities
   - Context value extraction helpers
   - Default fallback logic

3. **`tests/test_context_scoping.py`** (NEW)
   - Tests for context-scoped caching

4. **`examples/mcp_server.py`**
   - Add example with context-scoped tool

5. **`README.md`**
   - Document context-scoped caching pattern

---

## Session 6: Context-Scoped Caching Implementation ✅ COMPLETE

### Implementation Summary

Successfully implemented context-scoped caching in `@cache.cached()` decorator.

#### Files Created
- `src/mcp_refcache/context_integration.py` - Template expansion, context value extraction, actor derivation
- `tests/test_context_integration.py` - 49 tests for context integration utilities
- `tests/test_context_scoped_decorator.py` - 21 tests for decorator context scoping

#### Files Modified
- `src/mcp_refcache/cache.py` - Added new decorator parameters and context integration
- `src/mcp_refcache/__init__.py` - Exported new context integration functions

#### New Decorator Parameters
```python
@cache.cached(
    # Existing parameters...
    namespace_template: str | None = None,    # "org:{org_id}:user:{user_id}"
    owner_template: str | None = None,        # "user:{user_id}"
    session_scoped: bool = False,             # Bind to ctx.session_id
)
```

#### Key Features
1. **Dynamic Namespace**: `namespace_template="user:{user_id}"` expands from context
2. **Dynamic Owner**: `owner_template="user:{user_id}"` sets policy owner from context
3. **Session Binding**: `session_scoped=True` binds cache to current session
4. **Actor Derivation**: Automatically derives actor from context (`user_id` or `agent_id`)
5. **Graceful Degradation**: Works with fallbacks when FastMCP not available
6. **Security**: Agents cannot control scoping - identity comes from authenticated context

#### Template Expansion Sources (priority order)
1. `ctx.get_state(key)` - Middleware-set values
2. `ctx.session_id`, `ctx.client_id`, `ctx.request_id` - Built-in Context attrs
3. `DEFAULT_FALLBACKS` - Sensible defaults (`user_id→"anonymous"`, etc.)

#### Test Results
- **569 tests passing** (up from 499)
- 70 new tests for context integration
- All existing tests continue to pass

### Example Usage
```python
@cache.cached(
    namespace_template="org:{org_id}:user:{user_id}",
    owner_template="user:{user_id}",
    session_scoped=True,
)
@mcp.tool
async def get_account_balance(account_id: str) -> dict:
    # Namespace becomes "org:acme:user:alice" from authenticated context
    # Owner is automatically "user:alice"
    # Only this session can access the cached result
    ...
```

---

## Next Session Starting Prompt

```
Continue mcp-refcache: Documentation & Examples

## Context
- Sessions 1-6 complete, 569 tests passing
- Context-scoped caching fully implemented
- See `.agent/scratchpad-decorator-refactor.md` for full history

## Completed Features
- Dynamic namespace via `namespace_template`
- Dynamic owner via `owner_template`
- Session binding via `session_scoped`
- Actor derivation from context (user_id, agent_id)
- Graceful degradation without FastMCP

## Remaining Tasks

### High Priority
1. Update `examples/mcp_server.py` with context-scoped example
2. Update `README.md` with context-scoped caching documentation
3. Add example middleware showing identity extraction from JWT

### Optional Polish
- Add `IdentityMiddleware` helper class for common auth patterns
- Consider cacheTag/cacheLife integration for invalidation

## Guidelines
- Follow `.rules` (TDD, document as you go)
- Run `uv run ruff check . --fix && uv run ruff format .`
- Run `uv run pytest tests/` before considering complete
```

---

## Session 7: Testable Example + Langfuse Integration (PLANNED)

### Goals
1. Add testable context-scoped example to `examples/mcp_server.py`
2. Research and integrate Langfuse MCP for observability
3. Live test in Zed/Claude

### Task 1: Testable Context-Scoped Example

Since we don't have real FastMCP middleware in dev, we need to mock context for testing.

**Approach**: Add a test tool that patches `try_get_fastmcp_context` with configurable test values.

```python
# Example: Context-scoped tool with test mode
@cache.cached(
    namespace_template="user:{user_id}",
    owner_template="user:{user_id}",
    session_scoped=True,
)
@mcp.tool
async def get_user_data(key: str) -> dict:
    """Get user-scoped cached data.
    
    Each user gets isolated cache namespace.
    """
    return {"key": key, "data": f"Data for {key}"}

# Test tool to simulate different user contexts
@mcp.tool
async def set_test_context(user_id: str, org_id: str = "default") -> dict:
    """Set test context values for context-scoped caching demo."""
    # Store in module-level state that try_get_fastmcp_context can read
    ...
```

**Alternative**: Use environment variables or a config file to set test context values.

### Task 2: Langfuse MCP Integration

**Research needed:**
- What MCP tools/resources does Langfuse expose?
- How to trace tool calls and cache operations?
- Integration with existing RefCache operations

**Potential integration points:**
- Trace each `@cache.cached()` call with Langfuse spans
- Log cache hits/misses as events
- Track ref_id resolution chains
- Observe permission checks

### Files to Modify
1. `examples/mcp_server.py` - Add context-scoped example + test utilities
2. `examples/langfuse_integration.py` (NEW) - Langfuse-enabled server example
3. `README.md` - Document new features

### Test Plan
1. Start example server
2. Call `set_test_context(user_id="alice")`
3. Call `get_user_data(key="profile")` - should cache in `user:alice` namespace
4. Call `set_test_context(user_id="bob")`
5. Call `get_user_data(key="profile")` - should be cache MISS (different namespace)
6. Verify Langfuse traces show the operations

## Session 7: Testable Example + Langfuse Integration (IN PROGRESS)

### Completed ✅

#### Task 1: Context-Scoped Testing Tools
Added to `examples/mcp_server.py`:

1. **MockContext class**: Simulates FastMCP Context with:
   - `session_id` property
   - `get_state(key)` method for identity values
   - Class-level state storage (shared across instances)
   - `set_state()`, `set_session_id()`, `reset()` class methods

2. **Test context tools**:
   - `enable_test_context(enabled: bool)` - Enable/disable mock context mode
   - `set_test_context(user_id, org_id, session_id, agent_id)` - Set identity values
   - `reset_test_context()` - Reset to default demo values

3. **Context-scoped example tools**:
   - `get_user_profile(include_preferences)` - Demo with `namespace_template="org:{org_id}:user:{user_id}"`
   - `store_user_data(key, value)` - Demo with `namespace_template="user:{user_id}:data"`

4. **Tests added** to `tests/test_examples.py`:
   - `TestContextScopedCaching` class with 4 tests
   - `TestLangfuseIntegration` class with 2 tests
   - All 21 tests in test_examples.py passing

#### Task 2: Langfuse Integration Example
Created `examples/langfuse_integration.py` with basic tracing.

**Current implementation**:
- `TracedRefCache` wrapper class that traces cache.set/get/resolve operations
- Uses `@observe()` decorator on tools
- Uses `langfuse.start_as_current_observation()` for cache operation spans
- Records cache hits/misses in span metadata

### Langfuse Enhancement Implemented (Needs Debugging) ⚠️

**Implementation complete** but traces NOT appearing in Langfuse dashboard during live testing.

**Implementation details**:

1. **Added `get_langfuse_attributes()` helper function**:
   - Extracts `user_id`, `session_id` from MockContext/FastMCP
   - Builds `metadata` dict with alphanumeric keys (orgid, agentid, cachenamespace, operation)
   - Creates `tags` list for filtering (mcprefcache, cacheset, testmode, etc.)
   - Truncates all values to ≤200 characters (Langfuse requirement)

2. **Updated `TracedRefCache` class**:
   - `set()`, `get()`, `resolve()` now use `propagate_attributes()` context manager
   - Combined with `langfuse.start_as_current_observation()` using parenthesized `with` statement
   - All child spans inherit user_id, session_id, metadata, tags, version

3. **Added context management tools**:
   - `enable_test_context(enabled)` - Enable/disable mock context mode
   - `set_test_context(user_id, org_id, session_id, agent_id)` - Set identity values
   - `reset_test_context()` - Reset to default demo values

4. **Updated tool implementations**:
   - `calculate()`, `generate_fibonacci()`, `generate_primes()`, `get_cached_result()` 
   - All use `propagate_attributes()` early in execution
   - Return values include `traced_user` and `traced_session` for verification

5. **Added langfuse to dependencies**:
   - Added to `[project.optional-dependencies].langfuse` for optional install
   - Added to `[dependency-groups].dev` for testing

### Files Modified This Session
- `examples/langfuse_integration.py` - Complete rewrite with context propagation (~1050 lines)
- `tests/test_examples.py` - Added 4 new Langfuse tests (total 25 tests)
- `pyproject.toml` - Added langfuse to optional-dependencies and dev group

### Test Results
```
tests/test_examples.py: 25 passed
Full test suite: 579 passed, 3 skipped
```

### Live Testing Issue ⚠️

**Problem**: Traces are NOT appearing in Langfuse dashboard despite:
- `langfuse_enabled: true` in responses
- `public_key_set: true`, `secret_key_set: true`
- `traced_user` and `traced_session` appearing in tool responses
- Added `langfuse.flush()` calls after each operation

**Debugging needed**:
1. Verify Langfuse client is actually authenticating (no silent auth failures)
2. Check if `get_client()` returns a valid client or a no-op stub
3. Test Langfuse directly outside MCP server context
4. Check Langfuse SDK logs for errors
5. Verify the project in Langfuse dashboard matches the API keys

**Test command to try**:
```bash
uv run python -c "
from langfuse import get_client
import os

os.environ['LANGFUSE_PUBLIC_KEY'] = 'pk-lf-...'
os.environ['LANGFUSE_SECRET_KEY'] = 'sk-lf-...'
os.environ['LANGFUSE_HOST'] = 'https://cloud.langfuse.com'

client = get_client()
with client.start_as_current_observation(as_type='span', name='test-trace') as span:
    span.update(output={'test': 'hello'})
client.flush()
print('Check Langfuse dashboard for test-trace')
"
```

### Key Langfuse SDK v3 Pattern Used
```python
from langfuse import get_client, propagate_attributes

langfuse = get_client()

# Combined context managers (Python 3.10+ parenthesized with)
with (
    langfuse.start_as_current_observation(as_type="span", name="cache.set") as span,
    propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata=attributes["metadata"],
        tags=attributes["tags"],
        version=attributes["version"],
    ),
):
    # All child spans inherit these attributes
    result = cache.set(...)
```

---

## Session 8: Debug Langfuse Integration ✅ COMPLETE

### Problem Identified & Fixed

**Root Cause:** Decorator order was wrong!

```python
# WRONG - @observe wraps FunctionTool object, not the function
@observe(name="calculate")
@mcp.tool
def calculate(expression: str) -> dict:
    ...

# CORRECT - @mcp.tool wraps the observed function
@mcp.tool
@observe(name="calculate")
def calculate(expression: str) -> dict:
    ...
```

When decorators are stacked, they're applied **bottom-up**:
1. `@mcp.tool` was applied first, returning a `FunctionTool` object
2. `@observe` then tried to wrap that object instead of the actual function
3. Result: No traces created!

### Debugging Process
1. Tested Langfuse client directly in terminal → **Traces appeared!**
2. HTTP POST to `/api/public/otel/v1/traces` returned 200
3. Confirmed SDK was working correctly outside MCP context
4. Identified that `@observe` decorator wasn't being applied to actual function
5. Fixed decorator order in all tools

### Files Modified
- `examples/langfuse_integration.py` - Fixed decorator order for:
  - `calculate()` 
  - `generate_fibonacci()`
  - `generate_primes()`
  - `get_cached_result()`

### Live Testing Results ✅
After fix, traces appear in Langfuse dashboard with:
- **Users visible:** `alice`, `anonymous`, `debug-user-lukes`, `test-user`
- **Session tracking:** Working correctly
- **Context propagation:** `user_id`, `session_id` correctly attributed
- **Trace count:** 2 traces per user in test

### Correct Decorator Order Pattern
```python
@mcp.tool                           # OUTERMOST - registers with FastMCP
@observe(name="tool_name")          # Creates Langfuse trace
@cache.cached(namespace="ns")       # INNERMOST - caching (optional)
async def my_tool(...):
    ...
```

---

## Session 9: LLM Cost Tracking (PLANNED)

### Goals
1. Add LLM-based tools to demonstrate cost tracking in Langfuse
2. Track token usage for billing/invoicing purposes
3. Support Claude Opus 4.5 Preview model (current chat model)

### Langfuse Cost Tracking Requirements
For costs to appear, traces need:
- `model` - Model identifier (e.g., `claude-3-opus-20240229`)
- `input_tokens` / `output_tokens` / `total_tokens` - Usage counts
- Use `generation` observation type instead of `span`

### Implementation Plan

#### Option A: Mock LLM Usage (For Demo)
Create a tool that simulates LLM calls with realistic token counts:
```python
@mcp.tool
@observe(as_type="generation")
def ask_llm(prompt: str) -> str:
    # Simulate LLM response
    response = f"This is a simulated response to: {prompt}"
    
    # Manually set usage for cost tracking
    langfuse.update_current_observation(
        model="claude-3-opus-20240229",
        usage={
            "input_tokens": len(prompt.split()) * 1.3,  # Estimate
            "output_tokens": len(response.split()) * 1.3,
        }
    )
    return response
```

#### Option B: Real LLM Integration
Add Anthropic SDK and make actual API calls:
```python
import anthropic

client = anthropic.Anthropic()

@mcp.tool
@observe(as_type="generation")
def ask_claude(prompt: str, model: str = "claude-3-opus-20240229") -> str:
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    # Langfuse auto-captures usage from Anthropic response
    return response.content[0].text
```

### Supported Models for Invoicing
- `claude-3-opus-20240229` (Claude Opus 4.5 Preview)
- `claude-3-sonnet-20240229`
- `claude-3-haiku-20240307`
- `gpt-4-turbo`
- `gpt-4o`
- `gpt-3.5-turbo`

### Files to Modify
- `examples/langfuse_integration.py` - Add LLM tools
- `pyproject.toml` - Add `anthropic` to optional dependencies
- `.zed/settings.json` - Add `ANTHROPIC_API_KEY` env var

### Test Plan
1. Call LLM tool from Zed
2. Verify trace appears with `model` and usage
3. Check Langfuse dashboard shows cost calculation
4. Verify user-level cost aggregation works

---

## Research Findings: MCP Cost Tracking

### Key Discovery: MCP Trace Context Propagation

From Langfuse docs on MCP Tracing:
- MCP clients and servers produce **separate traces by default**
- Can link traces using MCP's `_meta` field with W3C Trace Context
- The **calling agent (Claude, etc.) creates the parent trace** with model info
- MCP tool calls are **child spans** that inherit from parent

### The Real Problem

The model information (e.g., `claude-sonnet-4-20250514`) is known by the **MCP client** 
(Zed/Claude), NOT the MCP server (our tools). Our tools don't know which model called them!

### Langfuse Cost Tracking Architecture

From Langfuse docs:
1. **Costs require `generation` type observations** with `model` and `usage_details`
2. **Langfuse has built-in model pricing** for OpenAI, Anthropic, Google models
3. **Usage can be ingested OR inferred** (inferred uses tokenizers)
4. **Custom models** can be defined in Langfuse Project Settings > Models

### Solution Options for MCP Tools

#### Option 1: Propagate Model via MCP `_meta` Field (Recommended)
The MCP client should pass model info in the tool call's `_meta`:
```python
# Client side (Zed/Claude integration)
tool_call = {
    "name": "calculate",
    "arguments": {"expression": "2+2"},
    "_meta": {
        "model": "claude-sonnet-4-20250514",
        "trace_context": "...",  # W3C format
    }
}

# Server side (our MCP tool)
@mcp.tool
@observe(as_type="generation")
def calculate(expression: str, _meta: dict = None):
    model = _meta.get("model") if _meta else os.getenv("DEFAULT_MODEL")
    langfuse.update_current_observation(model=model, ...)
```

#### Option 2: Environment Variable Default
Set `LANGFUSE_DEFAULT_MODEL` in MCP server config:
```json
{
  "langfuse-calculator": {
    "env": {
      "LANGFUSE_DEFAULT_MODEL": "claude-sonnet-4-20250514"
    }
  }
}
```

#### Option 3: Attribute Propagation from Parent Trace
If MCP client propagates trace context, the model info may already be in parent span.
Use Langfuse's trace linking to inherit model from parent.

### Langfuse MCP Tracing Example

From langfuse-examples repository (applications/mcp-tracing):
- Shows complete implementation of trace context propagation
- Uses W3C Trace Context format in `_meta` field
- Links client and server traces into single unified trace

### Next Steps for Implementation

1. **Check if Zed passes `_meta` to MCP tools** - Inspect actual tool call payloads
2. **Implement environment variable fallback** - Simple, works now
3. **Document proper MCP client integration** - For full cost tracking
4. **Consider using AnthropicInstrumentor** - Auto-captures usage from real API calls

### Code Pattern for MCP Tool with Cost Tracking

```python
import os
from langfuse import observe, get_client, propagate_attributes

langfuse = get_client()
DEFAULT_MODEL = os.getenv("LANGFUSE_DEFAULT_MODEL", "claude-sonnet-4-20250514")

@mcp.tool
@observe(name="calculate", as_type="generation", capture_input=True, capture_output=True)
def calculate(expression: str) -> dict[str, Any]:
    """Tool with cost tracking."""
    
    # Get model from context or environment
    # In future: extract from _meta if MCP client provides it
    model = DEFAULT_MODEL
    
    # Get Langfuse attributes for user attribution
    attributes = get_langfuse_attributes(operation="calculate")
    
    with propagate_attributes(
        user_id=attributes["user_id"],
        session_id=attributes["session_id"],
        metadata=attributes["metadata"],
    ):
        # Do the work
        result = eval(expression, {"__builtins__": {}}, safe_context)
        
        # Estimate token usage (or get from actual LLM response)
        input_tokens = len(expression) * 2  # Rough estimate
        output_tokens = len(str(result)) * 2
        
        # Update generation with model and usage for cost tracking
        langfuse.update_current_observation(
            model=model,
            usage_details={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )
        
        langfuse.flush()
        return {"result": result, "model": model}
```

---

## Session 9: Model from Session Context ✅ COMPLETE

### Problem Statement
The previous implementation got the model from an environment variable:
```python
model = os.getenv("LANGFUSE_MODEL", "claude-sonnet-4-20250514")
```

This is wrong because:
1. The model should come from session context, not env vars
2. The `agent_id` field was being conflated with the model name
3. Different sessions/users may use different models

### Solution Implemented
Added a dedicated `model` field to the session context:

1. **Added `model` to MockContext._state** - Default: `claude-sonnet-4-20250514`
2. **Updated `get_langfuse_attributes()`** - Returns `model` in attributes dict
3. **Updated `set_test_context()`** - Accepts `model` parameter
4. **Updated `calculate()`** - Gets model from `attributes["model"]`

### Files Modified
- `examples/langfuse_integration.py` - Added model to context and attributes
- `tests/test_examples.py` - Added tests for model field

### Code Pattern (Final)
```python
@mcp.tool
@observe(name="calculate", as_type="generation", capture_input=True, capture_output=True)
def calculate(expression: str) -> dict[str, Any]:
    # Model comes from session context for accurate cost tracking
    attributes = get_langfuse_attributes(operation="calculate")
    model = attributes["model"]  # From context, not env var!
    
    # ... do work ...
    
    # Use update_current_generation (not update_current_observation!)
    langfuse.update_current_generation(
        model=model,
        usage_details={"input": X, "output": Y},  # Note: "input"/"output" not "input_tokens"/"output_tokens"
    )
```

### Test Results
- All 579 tests pass (3 skipped for optional transformers)
- New tests verify model field in MockContext and get_langfuse_attributes

### How to Test in Zed/Claude
```
1. enable_test_context(true)
2. set_test_context(user_id="alice", model="gpt-4o")
3. calculate("2 + 2")
4. Check Langfuse dashboard - should show gpt-4o as model with costs
```

### Live Testing Results ✅
- Tested with `gpt-4o` model → costs tracked correctly
- Tested with `claude-opus-4-20250514` model → costs tracked correctly
- User attribution works (cost-test-alice, cost-test-bob visible in Langfuse)
- Default model updated to `claude-opus-4-20250514` to match actual Zed setup

### Bug Fixes Applied
1. Changed `langfuse.update_current_observation()` → `langfuse.update_current_generation()` (correct SDK v3 method)
2. Changed usage keys from `input_tokens`/`output_tokens` → `input`/`output` (Langfuse expected format)

---

## Session 10: Langfuse + RefCache Integration (PLANNED)

### Goals
1. Add Langfuse tracing to the `@cache.cached()` decorator
2. Track cache hits/misses as spans
3. Enable cost attribution for cache operations by user/session

### Key Integration Points

#### 1. TracedRefCache Enhancement
The `TracedRefCache` wrapper already exists but needs:
- Cache hit/miss tracking as spans
- User/session attribution from context
- Ref resolution tracing

#### 2. @cache.cached() Decorator Tracing
Options to consider:
- **Option A**: Add `trace=True` parameter to decorator
- **Option B**: Auto-detect Langfuse availability and trace if present
- **Option C**: Separate `@traced_cached()` decorator

#### 3. Cache Operation Spans
```python
@cache.cached(namespace="user:{user_id}", trace=True)
async def get_user_data(user_id: str) -> dict:
    # Langfuse will show:
    # - SPAN: cache_lookup (hit/miss)
    # - SPAN: cache_set (if miss)
    # - User attribution from context
    pass
```

### Design Decisions Needed
1. Should cache operations be `span` type (recommended) or `generation` type?
2. How to handle decorator stacking with `@observe`?
3. Should tracing be opt-in or automatic?

### Files to Modify
- `src/mcp_refcache/decorator.py` - Add tracing support
- `src/mcp_refcache/cache.py` - Add traced get/set methods
- `examples/langfuse_integration.py` - Enhance TracedRefCache
- `tests/test_decorator.py` - Add tracing tests

### Implementation Phases
1. **Phase 1**: Add tracing to TracedRefCache (standalone wrapper)
2. **Phase 2**: Add optional tracing to @cache.cached() decorator
3. **Phase 3**: Add cache hit/miss metrics to Langfuse

---

## Session 10: Langfuse + RefCache Integration ✅ COMPLETE

### Goals Achieved
1. ✅ Enhanced `TracedRefCache.cached()` to add Langfuse spans for cache operations
2. ✅ Track cache hit/miss status in span metadata
3. ✅ User/session attribution via `propagate_attributes()`
4. ✅ Comprehensive tests for traced caching behavior
5. ✅ Removed fake cost tracking (no LLM calls = no costs to track)
6. ✅ Fixed return type annotations for cached functions

### Implementation Summary

#### Problem 1: TracedRefCache.cached() Bypass
The original `TracedRefCache.cached()` simply delegated to the underlying cache:
```python
def cached(self, *args, **kwargs):
    return self._cache.cached(*args, **kwargs)
```

This bypassed the traced `set()`/`get()` methods because the decorator returned was bound to `self._cache`, not the `TracedRefCache` wrapper.

**Solution:** Enhanced `TracedRefCache.cached()` to wrap with Langfuse spans.

#### Problem 2: Fake Cost Tracking
The `calculate` function was faking token counts to demonstrate Langfuse cost tracking:
```python
input_tokens = len(expression) * 2  # FAKE!
langfuse.update_current_generation(model=model, usage_details={...})
```

**Reality:** These are pure computation tools with NO LLM calls. Cost tracking only makes sense for actual LLM API calls where you pay per token.

**Solution:** Removed all fake cost tracking. These tools now trace as spans (not generations) for observability only.

#### Problem 3: Return Type Mismatch
Functions declared `-> list[int]` but `@cache.cached()` wraps returns in a dict:
```python
{"ref_id": "...", "value": [...], "is_complete": True, ...}
```

**Solution:** Changed return type annotations to `-> dict[str, Any]`.

### Key Insight: When to Use Langfuse Cost Tracking

| Scenario | Cost Tracking? | Observation Type |
|----------|---------------|------------------|
| Pure computation (math, sequences) | ❌ No | `span` |
| Cache operations | ❌ No | `span` |
| Real LLM API call (OpenAI, Anthropic) | ✅ Yes | `generation` |

Cost tracking requires:
1. `as_type="generation"` in `@observe`
2. Real token counts from LLM API response
3. `langfuse.update_current_generation(model=..., usage_details=...)`

### Files Modified
- `examples/langfuse_integration.py`:
  - Enhanced `TracedRefCache.cached()` with Langfuse spans
  - Removed fake cost tracking from `calculate`
  - Changed `@observe(as_type="generation")` to `@observe()` (span)
  - Removed `model` field from MockContext and get_langfuse_attributes
  - Fixed return type annotations for cached functions
- `tests/test_examples.py`:
  - Added 7 tests for traced caching
  - Removed model-related assertions

### Tests Added
- `test_traced_cached_creates_span_on_cache_miss`
- `test_traced_cached_tracks_cache_hit`
- `test_traced_cached_includes_user_attribution`
- `test_traced_cached_async_function`
- `test_traced_refcache_resolve_with_tracing`
- `test_traced_cached_creates_cache_operation_span`
- `test_traced_cached_tracks_cache_hit_vs_miss_in_span`

### Test Results
- 586 tests passed, 3 skipped (optional transformers dependency)
- All linting passes

### Commits
1. `feat(langfuse): add Langfuse observability integration example` (Session 7-9)
2. `feat(langfuse): enhance TracedRefCache.cached() with Langfuse spans` (Session 10)
3. `fix(langfuse): fix return type annotations for cached functions`
4. `refactor(langfuse): remove fake cost tracking from pure computation tools`

---

## Next Session Starting Prompt

```
Continue mcp-refcache: Documentation & Polish

## Context
- Session 10 complete, Langfuse integration finalized!
- 586 tests passing
- See `.agent/scratchpad-decorator-refactor.md` Session 10 for details

## What Was Done (Session 10)
- Enhanced TracedRefCache.cached() with Langfuse spans
- Removed fake cost tracking (no LLM calls = no costs)
- Fixed return type annotations for cached functions
- Cleaned up model field from MockContext

## Key Learnings Documented
- Cost tracking only for real LLM API calls
- Pure computation tools use spans for observability
- @cache.cached() wraps returns in dict, not raw values

## Potential Next Tasks

### Option A: README & Documentation
- Update README with Langfuse integration section
- Document TracedRefCache usage pattern
- Add examples for real LLM cost tracking

### Option B: Core Library Polish
- Review and improve error messages
- Add more comprehensive docstrings
- Consider adding TracedRefCache to core library

### Option C: New Features
- Add metrics/stats collection
- Implement cache warming utilities
- Add export/import for cached values

## Guidelines
- Follow `.rules` (TDD, document as you go)
- Run `uv run ruff check . --fix && uv run ruff format .`
- Run `uv run pytest tests/` to verify
```

---

## Key Files Reference
- `examples/langfuse_integration.py` - MCP server with Langfuse tracing
- `.zed/settings.json` - MCP server config with env vars
- `.env` - Langfuse credentials (gitignored)
