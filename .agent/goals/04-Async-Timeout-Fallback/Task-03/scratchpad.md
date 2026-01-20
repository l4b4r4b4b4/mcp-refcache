# Task-03: Implement async_timeout in cached() Decorator

## Status
- [x] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Extend the `@cache.cached()` decorator to support an `async_timeout` parameter that returns a reference immediately if computation exceeds the specified threshold, with the computation continuing in the background.

---

## Context
This is the core feature implementation. The decorator currently blocks until function completion. With `async_timeout`, we need to:
1. Start the computation
2. Wait up to `async_timeout` seconds
3. If complete → return result normally
4. If not complete → spawn background task, return "processing" status immediately

This enables clients to avoid timeout errors for long-running operations.

## Acceptance Criteria
- [ ] `async_timeout: float | None` parameter added to `cached()` decorator
- [ ] `None` (default) means no timeout (current behavior preserved)
- [ ] Timeout triggers background task creation via `asyncio.create_task()`
- [ ] Returns `AsyncTaskResponse` with status="processing" when timeout exceeded
- [ ] Background task caches result on completion
- [ ] Background task updates task status on completion/failure
- [ ] Works correctly with existing parameters (namespace, ttl, policy, etc.)
- [ ] Only applies to async functions (sync functions raise error if async_timeout set)
- [ ] Docstring updated to document new parameter
- [ ] Unit tests for timeout scenarios

---

## Approach

### Decorator Signature Extension

```python
def cached(
    self,
    namespace: str = "public",
    policy: AccessPolicy | None = None,
    ttl: float | None = None,
    max_size: int | None = None,
    resolve_refs: bool = True,
    actor: ActorLike = "agent",
    namespace_template: str | None = None,
    owner_template: str | None = None,
    session_scoped: bool = False,
    # NEW PARAMETERS
    async_timeout: float | None = None,  # Return early if computation exceeds this
) -> Callable[[Callable[P, R]], Callable[P, dict[str, Any]]]:
```

### Implementation Logic

```python
async def async_wrapper(*args, **kwargs) -> dict[str, Any]:
    # ... existing steps 0-3 (context, resolve, cache key, check cache) ...

    if async_timeout is None:
        # Current behavior - wait for completion
        result = await func(*resolved_args, **resolved_kwargs)
        ref = self.set(cache_key, result, ...)
        return _build_response(ref.ref_id, result)
    else:
        # New behavior - timeout with background task
        ref_id = self._generate_ref_id(cache_key, effective_namespace)

        async def background_computation():
            try:
                result = await func(*resolved_args, **resolved_kwargs)
                ref = self.set(cache_key, result, ...)
                await self.complete_task(ref_id)
            except Exception as e:
                await self.fail_task(ref_id, str(e))
                raise

        # Create task but don't await it
        task = asyncio.create_task(background_computation())
        await self.register_task(ref_id, task)

        try:
            # Wait with timeout
            await asyncio.wait_for(asyncio.shield(task), timeout=async_timeout)
            # Completed in time - return normal response
            return _build_response(ref_id, task.result())
        except asyncio.TimeoutError:
            # Still running - return processing status
            return self._build_async_response(ref_id)
```

### Files to Modify
1. `src/mcp_refcache/cache.py` - Extend `cached()` decorator
2. `tests/test_async_timeout.py` - New test file

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-15 | Initial task creation |

### Key Considerations
- Use `asyncio.shield()` to prevent task cancellation on timeout
- Pre-generate ref_id before starting task (for registration)
- Background task must handle its own exception capture
- Consider what happens if same function called twice while first is processing

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01 models | ⚪ Pending | Need AsyncTaskResponse |
| Task-02 task tracking | ⚪ Pending | Need register_task, complete_task, fail_task |

---

## Commands & Snippets

```bash
# Run async timeout tests
uv run pytest tests/test_async_timeout.py -v

# Run with verbose async debugging
uv run pytest tests/test_async_timeout.py -v --tb=long
```

---

## Verification

```bash
# Integration test
uv run python -c "
import asyncio
from mcp_refcache import RefCache

cache = RefCache()

@cache.cached(async_timeout=0.1)
async def slow_function():
    await asyncio.sleep(1.0)
    return {'data': 'result'}

async def test():
    result = await slow_function()
    print(f'Status: {result.get(\"status\")}')
    assert result['status'] == 'processing'
    print('Async timeout working!')

asyncio.run(test())
"
```

---

## Related
- **Parent Goal:** [04-Async-Timeout-Fallback](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-02](../Task-02/scratchpad.md)
- **Blocks:** [Task-04](../Task-04/scratchpad.md) (polling support)
