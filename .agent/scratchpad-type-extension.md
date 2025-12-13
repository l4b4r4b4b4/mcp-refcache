# Type Extension Fix for @cache.cached() Decorator

## Status: ✅ COMPLETE

## Problem Statement

When using `@cache.cached()` with FastMCP tools, there was a type mismatch:

```python
@mcp.tool
@cache.cached(namespace="sequences")
async def generate_primes(count: int) -> list[int]:
    """Generate prime numbers."""
    return sieve_of_eratosthenes(count)
```

**Expected behavior:** Tool returns structured `dict[str, Any]` (CacheResponse)
**Actual behavior:** MCP validation failed because schema still expected `list[int]`

**Error:**
```
Output validation error: {'ref_id': 'langfuse-calculator:cec5a85ecdd5ddfc', 'value': [2, 3, 5, 7, 11, 13, 17, 19, 23, 29], 'is_complete': True, 'size': 30, 'total_items': 10} is not of type 'array'
```

## Root Cause

The issue was in `examples/langfuse_integration.py`, specifically in the `TracedRefCache.cached()` decorator.

The decorator chain was:
1. `@cache.cached()` wraps original func, sets return type to `dict[str, Any]` ✅
2. `TracedRefCache.tracing_decorator` wraps with `@functools.wraps(func)` → **resets to original signature!** ❌

The bug was using `@functools.wraps(func)` (the original function) instead of `@functools.wraps(cached_func)` (the already-wrapped function).

## Solution

Changed `@functools.wraps(func)` to `@functools.wraps(cached_func)` in both the async and sync wrappers in `TracedRefCache.cached()`:

```python
# BEFORE (wrong):
@functools.wraps(func)
async def async_traced_wrapper(...) -> dict[str, Any]:

# AFTER (correct):
@functools.wraps(cached_func)
async def async_traced_wrapper(...) -> dict[str, Any]:
```

## Files Modified

- `examples/langfuse_integration.py` - Fixed lines 561 and 629

## Verification

After fix:
- `generate_fibonacci(count=15)` ✅ Returns structured response
- `generate_primes(count=10)` ✅ Returns structured response
- All 586 tests pass ✅
- Output schema correctly shows `{'additionalProperties': True, 'type': 'object'}`

## Key Learnings

1. **`functools.wraps` copies `__wrapped__`** - This attribute tells `inspect.signature()` where to find the "real" function signature.

2. **Decorator order matters** - When stacking decorators, each `@functools.wraps` should wrap the immediately preceding wrapper, not the original function.

3. **FastMCP uses `inspect.signature(fn)`** - In `ParsedFunction.from_function()`, FastMCP extracts the return type via `inspect.signature(fn).return_annotation` for schema generation.

4. **The core library fix was already working** - The `@cache.cached()` decorator correctly sets `__annotations__` and `__signature__`. The bug was specific to the `TracedRefCache` wrapper in the example file.

## Session Log

### Session 1 (Previous)
- Identified the type mismatch problem
- Attempted fix with `__signature__` update in core library
- Fix works at Python level but MCP still failed
- Created scratchpad for handoff

### Session 2 (Current - Completed)
- Investigated FastMCP source code (`tools/tool.py`, `ParsedFunction.from_function`)
- Confirmed `inspect.signature()` returns correct type after `@cache.cached()`
- Discovered `TracedRefCache.cached()` uses `@functools.wraps(func)` instead of `@functools.wraps(cached_func)`
- Applied fix to both async and sync wrappers
- Verified fix works - MCP tools now return structured responses without validation errors
- All tests pass (586 passed, 3 skipped)
