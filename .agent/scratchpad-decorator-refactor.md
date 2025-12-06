# Scratchpad: @cache.cached() Decorator Refactoring

## Task Overview

Refactor the `@cache.cached()` decorator to provide full MCP tool integration with:
1. **Pre-execution**: Deep recursive ref_id resolution in all inputs
2. **Post-execution**: Always return structured CacheResponse (never raw values)
3. **Size-based response**: Full value OR preview based on max_size threshold
4. **Security-aware resolution**: Integrate with access/permission system

---

## Current Status: Core Implementation Complete ✅

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

### TODO 📋
- [ ] Integrate ref resolution with access control (deny without leaking info) - opaque errors
- [ ] Add max recursion depth limit to prevent infinite loops
- [ ] Add async ref resolution tests
- [ ] Consider short ref_id prefix matching (like git/docker) - see discussion below
- [ ] Create a second example with character-based sizing for comparison
- [ ] Improve pagination UX (sample strategy doesn't respond to page params)

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

### Medium Priority (Polish)
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
