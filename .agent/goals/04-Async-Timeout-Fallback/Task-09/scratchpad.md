# Task-09: Update Documentation (README, Docstrings)

## Status
- [x] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Update all documentation to reflect the new async timeout fallback feature, including README examples, API reference, docstrings, and migration notes.

---

## Context
With the async timeout fallback feature complete, users need clear documentation to:
- Understand when and why to use async_timeout
- Learn the polling workflow for long-running tasks
- Configure retry and cancellation behavior
- Implement progress reporting in their tools

Good documentation is critical for feature adoption.

## Acceptance Criteria
- [ ] README.md updated with async timeout section
- [ ] Quick Start example for long-running operations
- [ ] API Reference section for new parameters and methods
- [ ] Usage examples for all major scenarios
- [ ] Docstrings complete for all new/modified public methods
- [ ] Migration notes for users upgrading from v0.1.x
- [ ] CHANGELOG updated with v0.2.0 changes
- [ ] Roadmap updated (move completed items, add future enhancements)

---

## Approach

### README Sections to Add/Update

1. **New Section: "Async Timeout for Long-Running Operations"**
   - Problem statement
   - Solution overview
   - Basic usage example
   - Polling workflow diagram

2. **New Section: "Progress Reporting"**
   - ProgressCallback protocol
   - Example with progress_callback parameter
   - ETA estimation behavior

3. **New Section: "Retry Mechanism"**
   - Configuration options (max_retries, retry_delay, backoff)
   - Automatic vs manual retry
   - can_retry flag in responses

4. **New Section: "Task Cancellation"**
   - cancel_task() API
   - When to use cancellation
   - Cleanup behavior

5. **Update: API Reference**
   - cached() decorator new parameters
   - get_task_status() method
   - retry_task() method
   - cancel_task() method
   - New models (TaskStatus, TaskProgress, etc.)

6. **Update: Roadmap**
   - Mark v0.2.0 features as complete
   - Add v0.3.0 planned features

### Documentation Examples

```python
# Basic async timeout usage
@cache.cached(async_timeout=5.0)
async def index_videos(channel_id: str) -> dict:
    """Index all videos from a channel (takes 1-2 minutes)."""
    ...

# With progress reporting
@cache.cached(async_timeout=5.0, progress_enabled=True)
async def index_videos(
    channel_id: str,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Index all videos from a channel with progress updates."""
    videos = await get_channel_videos(channel_id)
    for i, video in enumerate(videos):
        if progress_callback:
            progress_callback(i, len(videos), f"Indexing {video.title}")
        await index_video(video)
    return {"indexed": len(videos)}

# Client polling workflow
result = await index_videos("channel123")
if result.get("status") == "processing":
    ref_id = result["ref_id"]
    while True:
        status = cache.get(ref_id)
        if status.status == "complete":
            print(f"Done! Result: {status.value}")
            break
        elif status.status == "failed":
            if status.can_retry:
                await cache.retry_task(ref_id)
            else:
                print(f"Failed: {status.error}")
                break
        else:
            print(f"Progress: {status.progress}")
            await asyncio.sleep(1)
```

### Files to Modify
1. `README.md` - Major update with new sections
2. `CHANGELOG.md` - v0.2.0 release notes
3. `src/mcp_refcache/cache.py` - Ensure all docstrings are complete
4. `src/mcp_refcache/models.py` - Ensure all docstrings are complete

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-15 | Initial task creation |

### Documentation Guidelines
- Use concrete examples, not abstract descriptions
- Show error handling, not just happy path
- Include type hints in all examples
- Explain WHY, not just WHAT
- Keep examples copy-paste ready

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01 through Task-07 | ⚪ Pending | Need implementation complete to document accurately |
| Task-08 tests | ⚪ Pending | Tests verify examples work |

---

## Commands & Snippets

```bash
# Build and view docs locally (if using mkdocs/sphinx)
uv run mkdocs serve

# Verify README examples are valid Python
uv run python -c "import ast; ast.parse(open('README.md').read())"

# Check for broken links in README
uv run markdown-link-check README.md
```

---

## Verification

```bash
# Verify all new public symbols are documented
uv run python -c "
from mcp_refcache import (
    TaskStatus, TaskProgress, TaskInfo, AsyncTaskResponse,
    RefCache,
)

# Check docstrings exist
assert TaskStatus.__doc__, 'TaskStatus needs docstring'
assert TaskProgress.__doc__, 'TaskProgress needs docstring'
assert AsyncTaskResponse.__doc__, 'AsyncTaskResponse needs docstring'
assert RefCache.cancel_task.__doc__, 'cancel_task needs docstring'
assert RefCache.retry_task.__doc__, 'retry_task needs docstring'

print('All public APIs documented!')
"

# Verify README examples are syntactically valid
uv run python -c "
import re
readme = open('README.md').read()
code_blocks = re.findall(r'\`\`\`python\n(.*?)\`\`\`', readme, re.DOTALL)
for i, block in enumerate(code_blocks):
    try:
        compile(block, f'<readme-block-{i}>', 'exec')
    except SyntaxError as e:
        print(f'Block {i} has syntax error: {e}')
        exit(1)
print(f'All {len(code_blocks)} code blocks are valid Python!')
"
```

---

## Changelog Draft

```markdown
## [0.2.0] - 2025-01-XX

### Added
- **Async Timeout Fallback**: New `async_timeout` parameter for `@cache.cached()` decorator
  enables returning immediately with a reference when computations exceed the timeout,
  with the computation continuing in the background.
- **Progress Reporting**: New `progress_enabled` parameter and `ProgressCallback` protocol
  for tools to report progress during long-running operations.
- **Task Status Tracking**: New `TaskStatus`, `TaskProgress`, `TaskInfo`, and
  `AsyncTaskResponse` models for tracking background task state.
- **Retry Mechanism**: Configurable automatic retry with exponential backoff via
  `max_retries`, `retry_delay`, and `retry_backoff_factor` parameters.
- **Manual Retry**: New `retry_task(ref_id)` method for manually retrying failed tasks.
- **Cancellation API**: New `cancel_task(ref_id)` method for cancelling in-flight tasks.
- **ETA Estimation**: Automatic ETA calculation based on progress rate.

### Changed
- `RefCache.get()` now returns `CacheResponse | AsyncTaskResponse` to support
  polling for in-flight task status.

### Fixed
- None

### Deprecated
- None
```

---

## Related
- **Parent Goal:** [04-Async-Timeout-Fallback](../scratchpad.md)
- **Depends On:** All other tasks (Task-01 through Task-08)
- **Related Tasks:** None
