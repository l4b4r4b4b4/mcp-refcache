# Task-01: Add TaskStatus, TaskProgress, AsyncTaskResponse Models

## Status
- [ ] Not Started
- [x] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Define the Pydantic models needed for async task tracking: status enum, progress information, and the response structure for in-flight computations.

---

## Context
Before implementing async timeout functionality, we need data structures to represent:
- The current state of a background task (pending, processing, complete, failed)
- Progress information that tools can report (current/total items, messages)
- The response format returned when a computation is still in progress

These models form the foundation for all subsequent async timeout work.

## Acceptance Criteria
- [ ] `TaskStatus` enum with values: PENDING, PROCESSING, COMPLETE, FAILED
- [ ] `TaskProgress` model with: current, total, message, percentage fields
- [ ] `TaskInfo` model for internal tracking: task reference, status, progress, timing, error info
- [ ] `AsyncTaskResponse` model for API responses: ref_id, status, progress, started_at, eta_seconds, error
- [ ] All models have proper Field descriptions for documentation
- [ ] Models are exported from `__init__.py`
- [ ] Unit tests for model validation and serialization

---

## Approach
Add new models to `mcp_refcache/models.py` following existing patterns (Pydantic BaseModel with Field descriptions).

### Files to Modify
1. `src/mcp_refcache/models.py` - Add new models
2. `src/mcp_refcache/__init__.py` - Export new models
3. `tests/test_models.py` or new `tests/test_async_models.py` - Tests

### Model Specifications

```python
class TaskStatus(str, Enum):
    """Status of an async computation."""
    PENDING = "pending"        # Task created but not started
    PROCESSING = "processing"  # Task is running
    COMPLETE = "complete"      # Task finished successfully
    FAILED = "failed"          # Task failed with error

class TaskProgress(BaseModel):
    """Progress information for long-running tasks."""
    current: int | None = Field(default=None, description="Current item/step number")
    total: int | None = Field(default=None, description="Total items/steps expected")
    message: str | None = Field(default=None, description="Human-readable progress message")
    percentage: float | None = Field(default=None, ge=0, le=100, description="Completion percentage")

class TaskInfo(BaseModel):
    """Internal tracking information for an async task."""
    ref_id: str = Field(description="Reference ID for the cached result")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current task status")
    progress: TaskProgress | None = Field(default=None, description="Progress information")
    started_at: float = Field(description="Unix timestamp when task started")
    completed_at: float | None = Field(default=None, description="Unix timestamp when task completed")
    error: str | None = Field(default=None, description="Error message if task failed")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts allowed")

class AsyncTaskResponse(BaseModel):
    """Response format for in-flight async computations."""
    ref_id: str = Field(description="Reference ID for polling results")
    status: TaskStatus = Field(description="Current task status")
    progress: TaskProgress | None = Field(default=None, description="Progress if available")
    started_at: str = Field(description="ISO 8601 timestamp when task started")
    eta_seconds: float | None = Field(default=None, ge=0, description="Estimated seconds until completion")
    error: str | None = Field(default=None, description="Error message if status is FAILED")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts so far")
    can_retry: bool = Field(default=True, description="Whether the task can be retried")
```

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-15 | Initial task creation, model specifications drafted |

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| None | - | - |

---

## Commands & Snippets

```bash
# Run tests for models
uv run pytest tests/test_async_models.py -v

# Check types
uv run mypy src/mcp_refcache/models.py

# Lint
uv run ruff check src/mcp_refcache/models.py
```

---

## Verification

```bash
# Verify models are importable and properly typed
uv run python -c "from mcp_refcache import TaskStatus, TaskProgress, TaskInfo, AsyncTaskResponse; print('OK')"

# Run full test suite
uv run pytest
```

---

## Related
- **Parent Goal:** [04-Async-Timeout-Fallback](../scratchpad.md)
- **Related Tasks:** Task-02 (uses these models for task tracking)
- **External Links:** [Pydantic docs](https://docs.pydantic.dev/)
