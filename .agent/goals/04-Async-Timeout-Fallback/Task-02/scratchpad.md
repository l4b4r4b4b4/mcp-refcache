# Task-02: Add Task Tracking Infrastructure to RefCache

## Status
- [x] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Add the internal infrastructure to RefCache for tracking active async tasks, including the task registry, lifecycle management, and cleanup mechanisms.

---

## Context
With the async models defined in Task-01, we need infrastructure within RefCache to:
- Track active background tasks
- Store task status and progress
- Clean up completed/failed tasks
- Handle concurrent access safely

This is integrated into RefCache (not a separate TaskRegistry) per design decision.

## Acceptance Criteria
- [ ] `_active_tasks: dict[str, TaskInfo]` added to RefCache
- [ ] `_task_lock: asyncio.Lock` for thread-safe access
- [ ] `register_task(ref_id, task)` method to track a new task
- [ ] `update_task_progress(ref_id, progress)` method
- [ ] `complete_task(ref_id, result)` method
- [ ] `fail_task(ref_id, error)` method
- [ ] `get_task_status(ref_id)` method returns TaskInfo or None
- [ ] `cleanup_tasks(max_age_seconds)` method removes old completed/failed tasks
- [ ] Background cleanup runs periodically (configurable interval)
- [ ] All methods are thread-safe
- [ ] Unit tests for task lifecycle

---

## Approach

### Integration Points in RefCache.__init__()

```python
def __init__(
    self,
    name: str = "default",
    # ... existing params ...
    task_cleanup_interval: float = 60.0,  # NEW: seconds between cleanups
    task_retention_seconds: float = 300.0,  # NEW: keep completed tasks for 5 min
):
    # ... existing init ...

    # Task tracking infrastructure
    self._active_tasks: dict[str, TaskInfo] = {}
    self._task_lock = asyncio.Lock()
    self._task_cleanup_interval = task_cleanup_interval
    self._task_retention_seconds = task_retention_seconds
    self._cleanup_task: asyncio.Task | None = None
```

### New Methods

```python
async def register_task(self, ref_id: str, task: asyncio.Task) -> TaskInfo:
    """Register a new background task for tracking."""

async def update_task_progress(
    self,
    ref_id: str,
    current: int | None = None,
    total: int | None = None,
    message: str | None = None,
) -> None:
    """Update progress for an active task."""

async def complete_task(self, ref_id: str) -> None:
    """Mark a task as complete."""

async def fail_task(self, ref_id: str, error: str) -> None:
    """Mark a task as failed with error message."""

def get_task_status(self, ref_id: str) -> TaskInfo | None:
    """Get current status of a task (sync for polling)."""

async def cleanup_tasks(self, max_age_seconds: float | None = None) -> int:
    """Remove old completed/failed tasks. Returns count removed."""
```

### Files to Modify
1. `src/mcp_refcache/cache.py` - Add task tracking to RefCache
2. `tests/test_task_tracking.py` - New test file for task infrastructure

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-15 | Initial task creation |

### Design Considerations
- Use `asyncio.Lock` not `threading.Lock` since we're in async context
- Sync `get_task_status()` for polling (can't await in sync contexts)
- Cleanup task spawned lazily on first async task registration
- Task retention allows debugging failed tasks before cleanup

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01 models | ⚪ Pending | Need TaskInfo, TaskStatus, TaskProgress |

---

## Commands & Snippets

```bash
# Run task tracking tests
uv run pytest tests/test_task_tracking.py -v

# Run with coverage
uv run pytest tests/test_task_tracking.py --cov=mcp_refcache.cache -v
```

---

## Verification

```bash
# Verify task tracking works
uv run python -c "
import asyncio
from mcp_refcache import RefCache

async def test():
    cache = RefCache()
    # Test will be fleshed out after implementation
    print('Task tracking infrastructure ready')

asyncio.run(test())
"
```

---

## Related
- **Parent Goal:** [04-Async-Timeout-Fallback](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md) (models)
- **Blocks:** [Task-03](../Task-03/scratchpad.md) (decorator implementation)
