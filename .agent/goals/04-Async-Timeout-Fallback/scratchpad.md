# Goal: Async Task Execution with Pluggable Backends

> **Status**: 🟡 In Progress
> **Priority**: P1 (High)
> **Created**: 2025-01-15
> **Updated**: 2025-01-20

## Overview

Add async task execution to `mcp-refcache` with pluggable backends, enabling:
1. `async_timeout` parameter on `@cache.cached()` for timeout-based async fallback
2. `TaskBackend` protocol for swappable execution backends
3. Built-in `MemoryTaskBackend` (ThreadPoolExecutor) for MVP
4. Optional `HatchetTaskBackend` for production distributed execution

This is the **main feature for v0.2.0** - a general-purpose solution for any MCP server with long-running operations.

## Success Criteria

- [x] `TaskBackend` protocol defined with pluggable implementations
- [x] `MemoryTaskBackend` using ThreadPoolExecutor (like document-mcp's JobManager)
- [x] `async_timeout` parameter added to `@cache.cached()` decorator
- [x] `async_response_format` parameter for response detail level (minimal/standard/full)
- [x] Agent can override format at call time with `_async_response_format`
- [x] Expected schema extraction for FULL format responses
- [ ] Computations completing within timeout return normally
- [ ] Computations exceeding timeout return reference with "processing" status
- [ ] `get_cached_result()` returns status for in-flight computations
- [ ] Progress callback protocol for tools to report progress
- [ ] Failed tasks are retryable with configurable defaults
- [ ] Cancellation API
- [ ] Comprehensive test coverage (≥80%)
- [ ] Documentation updated (README, docstrings)
- [x] All existing tests continue to pass (697 passed)
- [ ] (Future) `HatchetTaskBackend` for distributed execution

## Context & Background

**Problem**: Long-running computations (e.g., OCR processing, semantic indexing) cause MCP client timeouts. The current decorator waits for full completion before returning.

**Motivation**:
- Originated from yt-api-mcp semantic search feature
- document-mcp has its own `JobManager` with ThreadPoolExecutor
- General-purpose solution applicable to any MCP server

**Current Behavior**:
1. Client calls tool
2. Server blocks until computation completes
3. Server returns result
4. If computation takes too long → client times out → lost work

**Desired Behavior**:
1. Client calls tool with `async_timeout` configured
2. If computation exceeds timeout → return reference with status "processing"
3. Background task continues via TaskBackend
4. Client polls `get_cached_result(ref_id)` to check status
5. When complete → result is cached and returned

## Hatchet Research (2026-01-19)

Cloned Hatchet SDK to `.agent/goals/04-Async-Timeout-Fallback/hatchet-reference/`

### Key Hatchet Patterns

**Decorator-based task definition:**
```python
from hatchet_sdk import Hatchet, Context
hatchet = Hatchet()

@hatchet.task(name="my-task", input_validator=MyInput)
def my_task(input: MyInput, ctx: Context) -> MyOutput:
    return MyOutput(result="done")
```

**Worker-based execution:**
```python
worker = hatchet.worker("my-worker", workflows=[my_task])
worker.start()  # Long-running process that pulls tasks
```

**Key Features:**
- `@hatchet.task()` - standalone task decorator
- `@hatchet.durable_task()` - durable execution with checkpointing
- `input_validator` - Pydantic model for input validation
- `execution_timeout` - per-task timeout (default: 60s)
- `retries` - retry count with backoff
- `rate_limits` - rate limiting configuration
- `concurrency` - concurrency control expressions
- `Context` - provides task_output(), logging, cancellation checks

**Workflow DAGs:**
```python
dag = hatchet.workflow(name="MyDAG")

@dag.task()
def step1(input, ctx): ...

@dag.task(parents=[step1])
def step2(input, ctx):
    result = ctx.task_output(step1)  # Access parent output
```

**Run Triggering:**
```python
# Async trigger - returns immediately
run = await my_task.run(MyInput(message="hello"))

# Get result later
result = await run.result()
```

### Implications for mcp-refcache

1. **We don't need Hatchet's full complexity** - We're wrapping existing MCP tools, not defining new workflows

2. **TaskBackend abstraction is the right approach**:
   - `MemoryTaskBackend` - in-process ThreadPoolExecutor (MVP)
   - `HatchetTaskBackend` - wraps Hatchet SDK for distributed execution

3. **Key differences from Hatchet**:
   - Hatchet requires separate worker process
   - We want in-process execution for simple cases
   - We integrate with RefCache for result storage

4. **What to adopt from Hatchet**:
   - Progress callback pattern
   - Retry with exponential backoff
   - Cancellation token pattern
   - Input validation (already have via Pydantic)

## Architecture

### TaskBackend Protocol

```python
from typing import Protocol, Callable, Any
from mcp_refcache.models import TaskInfo, TaskProgress

class TaskBackend(Protocol):
    """Protocol for async task execution backends."""

    def submit(
        self,
        task_id: str,
        func: Callable[..., Any],
        args: tuple,
        kwargs: dict,
        on_progress: Callable[[TaskProgress], None] | None = None,
    ) -> TaskInfo:
        """Submit a task for background execution. Returns immediately."""
        ...

    def get_status(self, task_id: str) -> TaskInfo | None:
        """Get current task status and progress."""
        ...

    def get_result(self, task_id: str) -> Any:
        """Get completed task result. Raises if not complete."""
        ...

    def cancel(self, task_id: str) -> bool:
        """Request task cancellation. Returns success."""
        ...

    def cleanup(self, max_age_seconds: int) -> int:
        """Remove old completed/failed tasks. Returns count removed."""
        ...
```

### Backend Implementations

**MemoryTaskBackend** (MVP):
- ThreadPoolExecutor for CPU-bound work
- In-memory task tracking (dict)
- Progress callbacks via queue
- No persistence (tasks lost on restart)

**HatchetTaskBackend** (Future):
- Wraps `hatchet_sdk.Hatchet` client
- Requires separate worker process
- Durable, distributed execution
- Persistence via Hatchet server

### Integration with RefCache

```python
class RefCache:
    def __init__(
        self,
        ...,
        task_backend: TaskBackend | None = None,
    ):
        self._task_backend = task_backend or MemoryTaskBackend()
        self._active_tasks: dict[str, TaskInfo] = {}
```

### Decorator Enhancement

```python
@mcp.tool
@cache.cached(
    namespace="jobs",
    async_timeout=5.0,  # Return after 5s if not complete
    max_retries=3,
    retry_backoff=1.0,
)
async def long_running_task(input: str) -> dict:
    # If this takes >5s, returns {"status": "processing", "ref_id": "..."}
    # Client polls get_cached_result(ref_id) for completion
    ...
```

## Existing Models (Already Implemented)

From `src/mcp_refcache/models.py`:

- ✅ `TaskStatus` enum: pending, processing, complete, failed, cancelled
- ✅ `TaskProgress` model: current, total, message, percentage
- ✅ `TaskInfo` model: ref_id, status, progress, timing, retry info
- ✅ `AsyncTaskResponse` model: API response for polling
- ✅ `RetryInfo` model: retry attempt tracking

## Tasks

| Task ID | Description | Status | Depends On |
|---------|-------------|--------|------------|
| Task-01 | Define TaskBackend protocol | 🟢 | - |
| Task-02 | Implement MemoryTaskBackend | 🟢 | Task-01 |
| Task-03 | Add task_backend to RefCache.__init__ | 🟢 | Task-02 |
| Task-04 | Implement async_timeout in cached() decorator | 🟢 | Task-03 |
| Task-04b | Add async_response_format (minimal/standard/full) | 🟢 | Task-04 |
| Task-04c | Add _async_response_format agent override | 🟢 | Task-04b |
| Task-04d | Add ExpectedSchema extraction for FULL format | 🟢 | Task-04b |
| Task-05 | Implement polling support in get_cached_result | 🟢 | Task-04 |
| Task-06 | Add progress callback protocol | ⚪ | Task-04 |
| Task-07 | Implement retry mechanism | ⚪ | Task-04 |
| Task-08 | Add cancellation API | ⚪ | Task-04 |
| Task-09 | Write comprehensive tests for async tasks | 🟢 | Task-01-08 |
| Task-10 | Update documentation | ⚪ | Task-01-08 |
| Task-11 | (Future) HatchetTaskBackend | ⚪ | Task-01-10 |

## Implementation Progress (2025-01-20)

### Completed Files

1. **`src/mcp_refcache/backends/task_base.py`** - TaskBackend protocol
   - `submit()`, `get_status()`, `get_result()`, `cancel()`, `is_cancelled()`, `cleanup()`, `shutdown()`, `get_stats()`
   - `ProgressCallback` type alias

2. **`src/mcp_refcache/backends/task_memory.py`** - MemoryTaskBackend
   - ThreadPoolExecutor-based implementation
   - Thread-safe with `threading.Lock`
   - Progress callback support
   - Cancellation support (cooperative)
   - Auto-cleanup of old tasks

3. **`src/mcp_refcache/models.py`** - New models
   - `AsyncResponseFormat` enum (MINIMAL, STANDARD, FULL)
   - `ExpectedSchema` model for return type info
   - Updated `AsyncTaskResponse.from_task_info()` with format support
   - Added `AsyncTaskResponse.to_dict()` for format-aware serialization

4. **`src/mcp_refcache/cache.py`** - RefCache updates
   - Added `task_backend` parameter to `__init__`
   - Added `_active_tasks` dict for tracking
   - Added `async_timeout` and `async_response_format` to `cached()`
   - Added `_async_response_format` agent override support
   - Added `_execute_with_async_timeout()` for async functions
   - Added `_execute_sync_with_async_timeout()` for sync functions
   - Added `_execute_and_cache_background_task()` for background execution
   - Added `_extract_expected_schema()` for return type introspection
   - Added `get_task_status()` public method

5. **`src/mcp_refcache/backends/__init__.py`** - Updated exports
   - Added `TaskBackend`, `MemoryTaskBackend`, `ProgressCallback`

6. **Task-05 Complete (2025-01-20)** - Polling support in `get_cached_result`
   - Updated `RefCache.get()` to check `_active_tasks` before cache lookup
   - Returns `AsyncTaskResponse` for in-flight tasks (PENDING/PROCESSING/FAILED)
   - Returns `CacheResponse` for cached/completed entries
   - Added `_build_async_task_response()` helper method
   - Added `_calculate_eta()` for progress-based time estimation
   - Cleans up tracking for completed tasks
   - Updated return type: `CacheResponse | AsyncTaskResponse`
   - Created manual test: `examples/async_timeout/test_polling.py`
   - Manual test verifies: timeout → background task → polling → completion → retrieve
   - All 697 tests still passing

7. **Task-09 Complete (2025-01-20)** - Comprehensive async task tests
   - Created `tests/test_async_timeout.py` with 21 tests
   - Test classes:
     - `TestAsyncTimeout`: Timeout behavior, background execution, sync/async functions
     - `TestPolling`: RefCache.get() returning AsyncTaskResponse/CacheResponse
     - `TestETACalculation`: ETA calculation with progress info
     - `TestTaskCleanup`: Task removal from _active_tasks after completion
     - `TestErrorHandling`: Failed task status, error propagation
     - `TestAsyncResponseFormat`: minimal/standard/full format levels
     - `TestConcurrentAccess`: Multiple coroutines polling same task
   - All 718 tests passing (697 + 21 new)

### All Tests Pass
- 718 passed, 39 skipped (Redis/transformers not installed)

## Sequence Flow

```
┌─────────┐           ┌─────────┐           ┌───────────┐           ┌──────────┐
│  Client │           │ RefCache │           │TaskBackend│           │  Worker  │
└────┬────┘           └────┬────┘           └─────┬─────┘           └────┬─────┘
     │                     │                      │                      │
     │  tool(timeout=5s)   │                      │                      │
     │────────────────────>│                      │                      │
     │                     │                      │                      │
     │                     │  submit(task_id, fn) │                      │
     │                     │─────────────────────>│                      │
     │                     │                      │   execute(fn)        │
     │                     │                      │─────────────────────>│
     │                     │  TaskInfo(pending)   │                      │
     │                     │<─────────────────────│                      │
     │                     │                      │                      │
     │   [5s timeout]      │                      │                      │
     │                     │                      │                      │
     │  {status:processing}│                      │                      │
     │<────────────────────│                      │                      │
     │                     │                      │                      │
     │  poll(ref_id)       │                      │                      │
     │────────────────────>│                      │                      │
     │                     │  get_status(task_id) │                      │
     │                     │─────────────────────>│                      │
     │                     │  TaskInfo(processing)│                      │
     │                     │<─────────────────────│                      │
     │  {status:processing}│                      │                      │
     │<────────────────────│                      │                      │
     │                     │                      │     [done]           │
     │                     │                      │<─────────────────────│
     │                     │                      │                      │
     │  poll(ref_id)       │                      │                      │
     │────────────────────>│                      │                      │
     │                     │  get_result(task_id) │                      │
     │                     │─────────────────────>│                      │
     │                     │  result              │                      │
     │                     │<─────────────────────│                      │
     │                     │                      │                      │
     │                     │  cache.set(result)   │                      │
     │                     │                      │                      │
     │  {status:complete,  │                      │                      │
     │   value: result}    │                      │                      │
     │<────────────────────│                      │                      │
```

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Memory pressure from in-flight results | Medium | Medium | TTL for task records, cleanup on completion |
| Flaky timing-based tests | Low | High | Use deterministic mocks, avoid real delays |
| Lost tasks on server restart | Medium | High | Document limitation, HatchetBackend for durability |
| Race conditions in task tracking | High | Medium | Thread-safe TaskBackend, comprehensive tests |
| Breaking existing API | High | Low | Additive changes only, all params optional |

## Dependencies

- **Upstream**: None (self-contained feature)
- **Downstream**:
  - document-mcp (replace JobManager with mcp-refcache TaskBackend)
  - yt-api-mcp semantic search

## Notes & Decisions

### Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-01-15 | Integrate into RefCache vs separate TaskRegistry | Simpler API, single coordination point |
| 2025-01-15 | In-process execution for MVP | Simplicity, external queue via Protocol later |
| 2025-01-15 | Retryable failed tasks with defaults | Improves robustness |
| 2026-01-19 | TaskBackend protocol for pluggable backends | Enables Hatchet integration without breaking MVP |
| 2026-01-19 | MemoryTaskBackend uses ThreadPoolExecutor | Matches document-mcp's JobManager pattern |
| 2026-01-19 | HatchetTaskBackend as future enhancement | Hatchet requires worker process, adds complexity |

### Open Questions

- [x] Integrate into RefCache or separate TaskRegistry? → Integrate
- [x] Support retry for failed tasks? → Yes, with good defaults
- [x] Pluggable backends? → Yes, via TaskBackend protocol
- [x] Response format configurable? → Yes, AsyncResponseFormat enum
- [x] Agent can override format? → Yes, via `_async_response_format` kwarg
- [ ] Default max_retries? (Suggest: 3)
- [ ] Default retry_backoff? (Suggest: exponential, 1s base)
- [ ] Task cleanup TTL? (Suggest: 24 hours)
- [ ] Should HatchetBackend be optional dependency? (Suggest: yes, `mcp-refcache[hatchet]`)

## Next Steps

1. **Task-10**: Update README with async timeout documentation
   - Add "Async Timeout for Long-Running Operations" section
   - Add polling workflow example
   - Document response formats (minimal/standard/full)
2. **Task-06**: Add progress callback protocol (optional enhancement)
3. **Task-07**: Implement retry mechanism (optional enhancement)
4. **Task-08**: Add cancellation API (optional enhancement)

## References

- [Hatchet Python SDK](./hatchet-reference/sdks/python/) - cloned reference
- [Hatchet @task decorator](./hatchet-reference/sdks/python/hatchet_sdk/hatchet.py#L378-501)
- [document-mcp JobManager](../../examples/document-mcp/app/services/job_manager.py)
- [Current cached() decorator](../../../src/mcp_refcache/cache.py#L442-784)
- [Existing task models](../../../src/mcp_refcache/models.py)
