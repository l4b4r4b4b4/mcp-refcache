# Task-08: Write Comprehensive Tests

## Status
- [x] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Write comprehensive test coverage for all async timeout fallback functionality, ensuring ≥80% coverage and testing all edge cases, race conditions, and integration scenarios.

---

## Context
Testing async timeout behavior is notoriously tricky due to timing dependencies and race conditions. This task ensures we have robust, deterministic tests that validate:
- Correct behavior when computation completes within timeout
- Correct behavior when computation exceeds timeout
- Polling workflow from start to completion
- Progress reporting accuracy
- Retry mechanism correctness
- Cancellation safety
- Concurrent task handling
- Error propagation and recovery

Tests must be reliable in CI (no flaky tests) while exercising real async behavior.

## Acceptance Criteria
- [ ] Test file: `tests/test_async_timeout.py` - Core timeout functionality
- [ ] Test file: `tests/test_task_tracking.py` - Task registry/lifecycle
- [ ] Test file: `tests/test_polling.py` - Polling workflow
- [ ] Test file: `tests/test_progress_callback.py` - Progress reporting
- [ ] Test file: `tests/test_retry.py` - Retry mechanism
- [ ] Test file: `tests/test_cancellation.py` - Cancellation API
- [ ] Test file: `tests/test_async_integration.py` - End-to-end scenarios
- [ ] All tests pass with `pytest -v`
- [ ] Coverage ≥80% for new async code
- [ ] No flaky tests (deterministic timing)
- [ ] Tests run in <60 seconds total

---

## Approach

### Test Categories

#### 1. Unit Tests (Isolated, Fast)
- Model validation and serialization
- TaskInfo state transitions
- Progress calculation (ETA, percentage)
- Retry delay calculation

#### 2. Behavioral Tests (Async, Controlled)
- Computation completes before timeout
- Computation exceeds timeout
- Multiple concurrent tasks
- Task cleanup after completion/failure

#### 3. Integration Tests (Full Workflow)
- Start task → poll → receive result
- Start task → poll → cancel → verify stopped
- Start task → fail → retry → succeed
- Progress updates visible in polling

### Test Utilities

```python
# tests/conftest.py additions

import asyncio
import pytest
from mcp_refcache import RefCache

@pytest.fixture
def async_cache():
    """RefCache configured for async timeout testing."""
    return RefCache(
        name="async-test",
        task_cleanup_interval=1.0,  # Fast cleanup for tests
        task_retention_seconds=5.0,
    )

@pytest.fixture
def controlled_event():
    """Event for controlling when async tasks complete."""
    return asyncio.Event()

async def wait_for_status(cache, ref_id, expected_status, timeout=5.0):
    """Poll until task reaches expected status or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        status = cache.get_task_status(ref_id)
        if status and status.status == expected_status:
            return status
        await asyncio.sleep(0.05)
    raise TimeoutError(f"Task {ref_id} did not reach {expected_status}")
```

### Test Scenarios

#### test_async_timeout.py
1. `test_completes_within_timeout` - Returns normal result
2. `test_exceeds_timeout_returns_processing` - Returns processing status
3. `test_async_timeout_none_blocks` - Default behavior preserved
4. `test_sync_function_with_async_timeout_raises` - Error for sync functions
5. `test_timeout_zero_returns_immediately` - Edge case for timeout=0
6. `test_result_cached_after_background_completion` - Cache populated after bg task

#### test_task_tracking.py
1. `test_register_task_creates_entry` - TaskInfo created
2. `test_task_status_transitions` - PENDING → PROCESSING → COMPLETE
3. `test_complete_task_updates_status` - complete_task() works
4. `test_fail_task_stores_error` - Error message captured
5. `test_cleanup_removes_old_tasks` - Cleanup respects retention
6. `test_concurrent_task_registration` - Thread safety

#### test_polling.py
1. `test_poll_processing_returns_status` - In-flight task status
2. `test_poll_complete_returns_result` - Completed task returns value
3. `test_poll_failed_returns_error` - Failed task error info
4. `test_eta_calculation` - ETA based on progress
5. `test_poll_nonexistent_raises` - Unknown ref_id error

#### test_progress_callback.py
1. `test_progress_callback_injected` - Callback added to kwargs
2. `test_progress_updates_task_info` - Updates visible in TaskInfo
3. `test_function_without_callback_works` - Opt-in behavior
4. `test_percentage_calculated_correctly` - Math is right
5. `test_progress_message_stored` - Messages captured

#### test_retry.py
1. `test_automatic_retry_on_failure` - Retries happen automatically
2. `test_retry_respects_max_retries` - Stops after max
3. `test_exponential_backoff` - Delays increase correctly
4. `test_manual_retry_resets_task` - retry_task() works
5. `test_cannot_retry_complete_task` - Error for complete tasks
6. `test_retry_history_tracked` - All attempts recorded

#### test_cancellation.py
1. `test_cancel_processing_task` - Cancellation stops task
2. `test_cancel_idempotent` - Double cancel is safe
3. `test_cancel_nonexistent_returns_false` - Unknown ref_id
4. `test_cancel_complete_task_returns_false` - Can't cancel done task
5. `test_cancelled_task_status` - Status shows CANCELLED
6. `test_cancelled_task_cleanup` - Cleaned up by cleanup task

#### test_async_integration.py
1. `test_full_workflow_with_progress` - End-to-end with progress
2. `test_concurrent_tasks_isolation` - Multiple tasks don't interfere
3. `test_retry_then_cancel` - Cancel during retry
4. `test_cleanup_while_polling` - Cleanup doesn't break active polls
5. `test_cache_hit_for_repeated_call` - Cached result used on retry

### Files to Create
1. `tests/test_async_timeout.py`
2. `tests/test_task_tracking.py`
3. `tests/test_polling.py`
4. `tests/test_progress_callback.py`
5. `tests/test_retry.py`
6. `tests/test_cancellation.py`
7. `tests/test_async_integration.py`

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-15 | Initial task creation |

### Testing Strategies for Async
- Use `asyncio.Event` to control when tasks complete
- Mock `asyncio.sleep` for timing tests
- Use short timeouts (0.1s) for speed
- Test cleanup separately from main functionality
- Use `pytest-asyncio` with `auto` mode

### Avoiding Flaky Tests
- Never depend on wall-clock timing
- Use events/locks for synchronization
- Set generous timeouts for CI
- Test one thing per test function
- Clean up state between tests

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01 to Task-07 | ⚪ Pending | Need implementations to test |

---

## Commands & Snippets

```bash
# Run all async tests
uv run pytest tests/test_async*.py tests/test_task*.py tests/test_poll*.py tests/test_progress*.py tests/test_retry.py tests/test_cancellation.py -v

# Run with coverage
uv run pytest tests/test_async*.py --cov=mcp_refcache --cov-report=term-missing --cov-report=html

# Run specific test file
uv run pytest tests/test_async_timeout.py -v

# Run with timing info
uv run pytest tests/test_async*.py -v --durations=20

# Check for flaky tests (run 3 times)
uv run pytest tests/test_async*.py -v --count=3
```

---

## Verification

```bash
# Full test suite including new async tests
uv run pytest -v

# Coverage check (should be ≥80% for new code)
uv run pytest --cov=mcp_refcache --cov-fail-under=80

# Ensure no flaky tests
uv run pytest tests/test_async*.py --count=5 -x

# Performance check (should complete in <60s)
time uv run pytest tests/test_async*.py
```

---

## Related
- **Parent Goal:** [04-Async-Timeout-Fallback](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md) through [Task-07](../Task-07/scratchpad.md)
- **Related Tasks:** None
