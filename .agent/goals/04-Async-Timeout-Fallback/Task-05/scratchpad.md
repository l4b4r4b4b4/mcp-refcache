# Task-05: Add Progress Callback Protocol

## Status
- [x] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Implement a progress callback protocol that allows tools to report progress during long-running computations, enabling clients to see meaningful progress updates while polling.

---

## Context
When a computation exceeds `async_timeout` and runs in the background, clients polling with `get_cached_result()` should see progress updates, not just "processing" status. Tools need a way to report their progress.

The decorator should optionally inject a `progress_callback` parameter that tools can call to report progress. This is opt-in - tools that don't accept the callback work normally.

## Acceptance Criteria
- [ ] `ProgressCallback` Protocol defined: `Callable[[int, int, str | None], None]`
- [ ] `progress_enabled: bool = False` parameter added to `cached()` decorator
- [ ] When enabled, decorator injects `progress_callback` if function accepts it
- [ ] Progress callback updates `TaskInfo.progress` via `update_task_progress()`
- [ ] Tools without `progress_callback` parameter work normally (no injection)
- [ ] ETA estimation calculated from progress rate (optional)
- [ ] Unit tests for progress reporting
- [ ] Documentation with usage examples

---

## Approach

### Protocol Definition

```python
from typing import Protocol

class ProgressCallback(Protocol):
    """Protocol for progress reporting callbacks."""

    def __call__(
        self,
        current: int,
        total: int,
        message: str | None = None,
    ) -> None:
        """Report progress on a long-running task.

        Args:
            current: Current item/step number (0-indexed or 1-indexed)
            total: Total items/steps expected
            message: Optional human-readable progress message
        """
        ...
```

### Decorator Enhancement

```python
def cached(
    self,
    # ... existing params ...
    async_timeout: float | None = None,
    progress_enabled: bool = False,  # NEW
):
```

### Callback Injection Logic

```python
# Inside async_wrapper
if progress_enabled:
    # Check if function accepts progress_callback parameter
    sig = inspect.signature(func)
    if 'progress_callback' in sig.parameters:
        # Create callback that updates task progress
        def progress_callback(current: int, total: int, message: str | None = None):
            asyncio.create_task(
                self.update_task_progress(ref_id, current, total, message)
            )

        # Inject into kwargs
        resolved_kwargs['progress_callback'] = progress_callback
```

### Example Usage

```python
@cache.cached(async_timeout=5.0, progress_enabled=True)
async def index_videos(
    video_ids: list[str],
    progress_callback: ProgressCallback | None = None,
) -> dict:
    results = []
    for i, video_id in enumerate(video_ids):
        if progress_callback:
            progress_callback(i, len(video_ids), f"Indexing {video_id}")

        result = await index_single_video(video_id)
        results.append(result)

    if progress_callback:
        progress_callback(len(video_ids), len(video_ids), "Complete")

    return {"indexed": results}
```

### Files to Modify
1. `src/mcp_refcache/models.py` - Add ProgressCallback Protocol
2. `src/mcp_refcache/cache.py` - Add progress_enabled param and injection logic
3. `tests/test_progress_callback.py` - New test file

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-15 | Initial task creation |

### Design Considerations
- Callback is fire-and-forget (don't await progress updates)
- Use `asyncio.create_task()` for non-blocking progress updates
- Progress callback is optional parameter with default `None`
- ETA = (elapsed_time / current) * (total - current) if current > 0
- Rate limiting: don't update more than once per 100ms to avoid flooding

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-02 task tracking | ⚪ Pending | Need update_task_progress method |
| Task-03 async_timeout | ⚪ Pending | Need ref_id available for progress updates |
| Task-04 polling | ⚪ Pending | Need polling to return progress info |

---

## Commands & Snippets

```bash
# Run progress callback tests
uv run pytest tests/test_progress_callback.py -v

# Test progress with timing
uv run pytest tests/test_progress_callback.py -v --durations=10
```

---

## Verification

```bash
# Integration test with progress
uv run python -c "
import asyncio
from mcp_refcache import RefCache

cache = RefCache()

@cache.cached(async_timeout=0.5, progress_enabled=True)
async def process_items(items: list[str], progress_callback=None):
    for i, item in enumerate(items):
        if progress_callback:
            progress_callback(i, len(items), f'Processing {item}')
        await asyncio.sleep(0.2)
    return {'processed': len(items)}

async def test():
    # Start long-running task
    result = await process_items(['a', 'b', 'c', 'd', 'e'])
    print(f'Initial: {result}')

    if result.get('status') == 'processing':
        await asyncio.sleep(0.3)
        status = cache.get_task_status(result['ref_id'])
        print(f'Progress: {status.progress if status else None}')

asyncio.run(test())
"
```

---

## Related
- **Parent Goal:** [04-Async-Timeout-Fallback](../scratchpad.md)
- **Depends On:** [Task-02](../Task-02/scratchpad.md), [Task-03](../Task-03/scratchpad.md), [Task-04](../Task-04/scratchpad.md)
- **Related Tasks:** None
