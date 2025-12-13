# Type Extension Fix for @cache.cached() Decorator

## Problem Statement

When using `@cache.cached()` with FastMCP tools, there's a type mismatch:

```python
@mcp.tool
@cache.cached(namespace="sequences")
async def generate_primes(count: int) -> list[int]:
    """Generate prime numbers."""
    return sieve_of_eratosthenes(count)
```

**Expected behavior:** Tool returns `list[int]` according to its signature
**Actual behavior:** Decorator transforms return to `dict[str, Any]` (CacheResponse structure)

**Error:**
```
Output validation error: {'ref_id': 'langfuse-calculator:cec5a85ecdd5ddfc', 'value': [2, 3, 5, 7, 11, 13, 17, 19, 23, 29], 'is_complete': True, 'size': 30, 'total_items': 10} is not of type 'array'
```

## Root Cause Analysis

### What We Tried (Didn't Work)

We updated the decorator to modify both `__annotations__` and `__signature__`:

```python
# In cache.py cached() decorator
async_wrapper.__annotations__ = {
    **func.__annotations__,
    "return": dict[str, Any],
}
original_sig = inspect.signature(func)
async_wrapper.__signature__ = original_sig.replace(
    return_annotation=dict[str, Any]
)
```

**Verification that it works at Python level:**
```python
>>> cache = RefCache(name='test')
>>> @cache.cached()
... async def my_tool(x: int) -> list[int]:
...     return [x]
>>> import inspect
>>> sig = inspect.signature(my_tool)
>>> sig.return_annotation
dict[str, typing.Any]  # ✅ Correct!
```

### Why It Still Fails

FastMCP's `@mcp.tool` decorator likely:
1. Follows `__wrapped__` attribute (set by `functools.wraps`) to find the original function
2. Uses the original function's signature for MCP schema generation
3. Validates output against that original schema

The `__wrapped__` attribute points to the **original unwrapped function**, bypassing our signature modifications.

## Investigation Needed

### 1. Check FastMCP's Schema Generation

Look at how FastMCP extracts return type for MCP tool schema:
- Does it use `inspect.signature()`?
- Does it follow `__wrapped__`?
- Does it use `typing.get_type_hints()`?

```bash
# Find FastMCP source
uv run python -c "import fastmcp; print(fastmcp.__file__)"
```

### 2. Check `__wrapped__` Behavior

```python
@cache.cached()
async def my_tool() -> list[int]:
    return [1, 2, 3]

print(my_tool.__wrapped__)  # Original function
print(my_tool.__wrapped__.__annotations__)  # Original annotations
```

### 3. Possible Solutions

#### Option A: Delete or Replace `__wrapped__`

```python
# After functools.wraps
del async_wrapper.__wrapped__
# or
async_wrapper.__wrapped__ = async_wrapper  # Point to itself
```

**Risk:** May break introspection tools that rely on `__wrapped__`

#### Option B: Modify the Original Function's Annotations

```python
# Before wrapping
func.__annotations__["return"] = dict[str, Any]
```

**Risk:** Mutates the original function (side effect)

#### Option C: Custom `wraps` That Doesn't Set `__wrapped__`

```python
def custom_wraps(wrapped):
    """Like functools.wraps but doesn't set __wrapped__."""
    def decorator(wrapper):
        for attr in ('__module__', '__name__', '__qualname__', '__doc__'):
            try:
                value = getattr(wrapped, attr)
                setattr(wrapper, attr, value)
            except AttributeError:
                pass
        wrapper.__dict__.update(wrapped.__dict__)
        # Intentionally NOT setting __wrapped__
        return wrapper
    return decorator
```

#### Option D: Work With FastMCP's Expected Pattern

Check if FastMCP has a recommended way to:
- Override return type for schema generation
- Use a response model (Pydantic)
- Annotate tools with custom schemas

```python
# Maybe something like:
@mcp.tool(response_model=CacheResponse)
@cache.cached()
async def my_tool() -> list[int]:
    ...
```

#### Option E: Modify Both Wrapper AND Original `__wrapped__`

```python
# Update wrapper
async_wrapper.__annotations__["return"] = dict[str, Any]
async_wrapper.__signature__ = new_sig

# Also update what __wrapped__ points to
if hasattr(async_wrapper, "__wrapped__"):
    async_wrapper.__wrapped__.__annotations__["return"] = dict[str, Any]
```

## Files to Modify

- `src/mcp_refcache/cache.py` - The `cached()` decorator
- `examples/langfuse_integration.py` - Test the fix
- `examples/mcp_server.py` - Test the fix
- `tests/test_cache.py` - Add tests for type transformation

## Test Plan

1. **Unit test:** Verify `inspect.signature()` returns correct type
2. **Unit test:** Verify `__wrapped__` handling
3. **Integration test:** Start MCP server, check tool schema
4. **Live test:** Call tool via MCP client, verify no validation error

## Current State

- **Commit:** `d7033c0` - feat: automatic type extension for @cache.cached() decorator
- **Branch:** `main`
- **Tests:** 586 passed, 3 skipped
- **Issue:** MCP output validation still fails despite signature changes

## Session Log

### Session 1 (Current)
- Identified the type mismatch problem
- Attempted fix with `__signature__` update
- Fix works at Python level but not at MCP level
- Root cause: FastMCP follows `__wrapped__` for schema generation
- Created this scratchpad for handoff

## Next Steps

1. Investigate FastMCP source code for schema generation
2. Try Option A (delete `__wrapped__`) first - simplest fix
3. If that breaks things, try Option C (custom wraps)
4. Add comprehensive tests
5. Document the decorator order requirement
```

---

## Handoff Prompt

````
Continue mcp-refcache: Fix Type Extension for @cache.cached() Decorator

## Context
- Working on mcp-refcache library for FastMCP servers
- See `.agent/scratchpad-type-extension.md` for full context and investigation notes
- See `.rules` for coding standards

## Problem
The `@cache.cached()` decorator transforms return type from `list[int]` to `dict[str, Any]` (CacheResponse), but FastMCP still validates output against the original `list[int]` type, causing:

```
Output validation error: {'ref_id': '...', 'value': [...], ...} is not of type 'array'
```

## What Was Done
- Updated decorator to modify `__annotations__` and `__signature__` ✅
- Python-level `inspect.signature()` now returns `dict[str, Any]` ✅
- But MCP validation still fails ❌

## Root Cause Hypothesis
FastMCP's `@mcp.tool` follows `__wrapped__` (set by `functools.wraps`) to get the original function's signature for schema generation, bypassing our modifications.

## Current Task
1. Investigate FastMCP source to confirm how it extracts return type
2. Try deleting/replacing `__wrapped__` in the decorator
3. Test with langfuse-calculator MCP tools (available in chat)
4. If fix works, add tests and document

## Key Files
- `src/mcp_refcache/cache.py` - The `cached()` decorator (lines 440-785)
- `examples/langfuse_integration.py` - Has `generate_fibonacci`, `generate_primes` tools
- `.agent/scratchpad-type-extension.md` - Full investigation notes

## Test Commands
```bash
# Run tests
uv run pytest --tb=short -q

# Test MCP tools directly in chat:
generate_primes(count=10)
generate_fibonacci(count=20)
```

## Guidelines
- Follow `.rules` (TDD, document as you go)
- Run `uv run ruff check . --fix && uv run ruff format .` before committing
- Decorator order: `@mcp.tool` must come BEFORE `@cache.cached()`
````
