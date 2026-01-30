# Task-08: Async Task System

## Status
- [ ] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Implement the async task execution system with `TaskBackend` protocol and `MemoryTaskBackend` implementation. This enables long-running MCP tool operations to return immediately with a reference, while computation continues in the background with polling support.

---

## Context
Long-running MCP operations (like document analysis, semantic search, large data processing) can exceed client timeouts, causing failures. The async task system solves this by:

1. Starting computation in background when timeout is exceeded
2. Returning an `AsyncTaskResponse` immediately with status and ref_id
3. Client polls using the ref_id until completion
4. Completed result is stored in cache, accessible via normal `get()`/`resolve()`

The Python implementation (v0.2.0 feature) adds:
- `TaskBackend` protocol for pluggable execution backends
- `MemoryTaskBackend` using ThreadPoolExecutor
- `async_timeout` parameter on `@cache.cached()` decorator
- Task tracking with progress callbacks and ETA estimation

## Acceptance Criteria
- [ ] `TaskBackend` interface defined
- [ ] `TaskInfo` tracking with status, progress, timestamps
- [ ] `MemoryTaskBackend` using worker threads
- [ ] `AsyncTaskResponse` for in-flight task polling
- [ ] Integration with RefCache for async_timeout support
- [ ] Progress callback protocol
- [ ] ETA estimation based on progress
- [ ] Task cleanup after completion
- [ ] Retry mechanism for failed tasks
- [ ] Cancellation support
- [ ] Unit tests for task lifecycle
- [ ] JSDoc documentation

---

## Approach
Port the Python async task system while leveraging JavaScript's native async/await and worker threads. For the MVP, use a simple task queue with Promise-based execution rather than a full ThreadPoolExecutor equivalent.

### Steps

1. **Define TaskBackend interface**
   - `submit()` - Submit task for execution
   - `getStatus()` - Get task status and progress
   - `cancel()` - Request cancellation
   - `cleanup()` - Remove completed tasks

2. **Define task tracking types**
   - Extend `TaskInfo`, `TaskStatus`, `TaskProgress` from Task-02
   - Add `TaskResult` for completion data
   - Add progress callback signature

3. **Implement MemoryTaskBackend**
   - Use `Promise` with internal tracking
   - Support concurrent task limit
   - Progress reporting via callbacks
   - Automatic cleanup after configurable delay

4. **Integrate with RefCache**
   - Add `taskBackend` option to RefCache
   - Modify `@cached()` decorator to support `async_timeout`
   - Return `AsyncTaskResponse` when timeout exceeded
   - Store completed results in cache

5. **Add polling support to RefCache.get()**
   - Detect in-flight tasks by ref_id
   - Return `AsyncTaskResponse` with current status
   - Calculate ETA from progress

6. **Write comprehensive tests**

---

## Interface Design

### TaskBackend Interface
```typescript
// src/backends/task-base.ts

import type { TaskInfo, TaskProgress, TaskStatus } from '../models/task';

export interface TaskSubmission<T = unknown> {
  /** Unique task ID */
  taskId: string;
  /** Reference ID for the result */
  refId: string;
  /** The async function to execute */
  execute: () => Promise<T>;
  /** Optional progress callback */
  onProgress?: (progress: TaskProgress) => void;
  /** Optional timeout in milliseconds */
  timeoutMs?: number;
  /** Maximum retry attempts */
  maxRetries?: number;
}

export interface TaskResult<T = unknown> {
  /** The task ID */
  taskId: string;
  /** The reference ID */
  refId: string;
  /** Task status */
  status: TaskStatus;
  /** Result value if completed */
  value?: T;
  /** Error message if failed */
  error?: string;
  /** Final progress */
  progress?: TaskProgress;
  /** Completion timestamp */
  completedAt?: Date;
}

export interface TaskBackend {
  /**
   * Submit a task for execution.
   * Returns immediately with task info.
   */
  submit<T>(submission: TaskSubmission<T>): Promise<TaskInfo>;

  /**
   * Get the current status of a task.
   */
  getStatus(taskId: string): Promise<TaskInfo | null>;

  /**
   * Get status by reference ID.
   */
  getStatusByRefId(refId: string): Promise<TaskInfo | null>;

  /**
   * Request cancellation of a task.
   */
  cancel(taskId: string): Promise<boolean>;

  /**
   * Get the result of a completed task.
   */
  getResult<T>(taskId: string): Promise<TaskResult<T> | null>;

  /**
   * Clean up completed/failed tasks older than maxAge.
   */
  cleanup(maxAgeMs?: number): Promise<number>;

  /**
   * Shut down the backend gracefully.
   */
  close(): Promise<void>;
}
```

### MemoryTaskBackend
```typescript
// src/backends/task-memory.ts

import type { TaskBackend, TaskSubmission, TaskResult } from './task-base';
import type { TaskInfo, TaskProgress, TaskStatus } from '../models/task';
import { nanoid } from 'nanoid';

export interface MemoryTaskBackendOptions {
  /** Maximum concurrent tasks (default: 4) */
  maxConcurrent?: number;
  /** Cleanup delay after completion in ms (default: 300000 = 5 min) */
  cleanupDelayMs?: number;
  /** Default timeout per task in ms (default: 600000 = 10 min) */
  defaultTimeoutMs?: number;
}

interface InternalTask {
  info: TaskInfo;
  submission: TaskSubmission;
  result?: TaskResult;
  abortController: AbortController;
  promise: Promise<unknown>;
}

export class MemoryTaskBackend implements TaskBackend {
  private tasks: Map<string, InternalTask> = new Map();
  private tasksByRefId: Map<string, string> = new Map(); // refId -> taskId
  private runningCount = 0;
  private queue: TaskSubmission[] = [];

  constructor(private options: MemoryTaskBackendOptions = {}) {
    this.options = {
      maxConcurrent: 4,
      cleanupDelayMs: 300000,
      defaultTimeoutMs: 600000,
      ...options,
    };
  }

  async submit<T>(submission: TaskSubmission<T>): Promise<TaskInfo> {
    const taskId = submission.taskId || nanoid();
    const now = new Date();

    const info: TaskInfo = {
      taskId,
      refId: submission.refId,
      status: 'pending',
      progress: { progress: 0 },
      createdAt: now,
      retryCount: 0,
    };

    const abortController = new AbortController();

    const internalTask: InternalTask = {
      info,
      submission: { ...submission, taskId },
      abortController,
      promise: Promise.resolve(), // Will be replaced
    };

    this.tasks.set(taskId, internalTask);
    this.tasksByRefId.set(submission.refId, taskId);

    // Start or queue
    if (this.runningCount < (this.options.maxConcurrent ?? 4)) {
      this.startTask(internalTask);
    } else {
      this.queue.push(submission);
    }

    return info;
  }

  private async startTask(task: InternalTask): Promise<void> {
    this.runningCount++;
    task.info.status = 'running';
    task.info.startedAt = new Date();

    const timeoutMs = task.submission.timeoutMs ?? this.options.defaultTimeoutMs;

    task.promise = this.executeWithTimeout(task, timeoutMs!)
      .then(value => {
        task.info.status = 'complete';
        task.info.completedAt = new Date();
        task.result = {
          taskId: task.info.taskId,
          refId: task.info.refId,
          status: 'complete',
          value,
          completedAt: task.info.completedAt,
        };
      })
      .catch(error => {
        if (task.abortController.signal.aborted) {
          task.info.status = 'cancelled';
        } else {
          task.info.status = 'failed';
          task.info.error = error instanceof Error ? error.message : String(error);
        }
        task.info.completedAt = new Date();
        task.result = {
          taskId: task.info.taskId,
          refId: task.info.refId,
          status: task.info.status,
          error: task.info.error,
          completedAt: task.info.completedAt,
        };
      })
      .finally(() => {
        this.runningCount--;
        this.processQueue();
        this.scheduleCleanup(task.info.taskId);
      });
  }

  private async executeWithTimeout(task: InternalTask, timeoutMs: number): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        task.abortController.abort();
        reject(new Error(`Task timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      task.abortController.signal.addEventListener('abort', () => {
        clearTimeout(timeout);
        reject(new Error('Task was cancelled'));
      });

      task.submission.execute()
        .then(result => {
          clearTimeout(timeout);
          resolve(result);
        })
        .catch(error => {
          clearTimeout(timeout);
          reject(error);
        });
    });
  }

  private processQueue(): void {
    while (
      this.queue.length > 0 &&
      this.runningCount < (this.options.maxConcurrent ?? 4)
    ) {
      const submission = this.queue.shift()!;
      const task = this.tasks.get(submission.taskId!);
      if (task) {
        this.startTask(task);
      }
    }
  }

  private scheduleCleanup(taskId: string): void {
    setTimeout(() => {
      const task = this.tasks.get(taskId);
      if (task && (task.info.status === 'complete' || task.info.status === 'failed' || task.info.status === 'cancelled')) {
        this.tasks.delete(taskId);
        this.tasksByRefId.delete(task.info.refId);
      }
    }, this.options.cleanupDelayMs);
  }

  async getStatus(taskId: string): Promise<TaskInfo | null> {
    const task = this.tasks.get(taskId);
    return task?.info ?? null;
  }

  async getStatusByRefId(refId: string): Promise<TaskInfo | null> {
    const taskId = this.tasksByRefId.get(refId);
    if (!taskId) return null;
    return this.getStatus(taskId);
  }

  async cancel(taskId: string): Promise<boolean> {
    const task = this.tasks.get(taskId);
    if (!task || task.info.status !== 'running') return false;

    task.abortController.abort();
    return true;
  }

  async getResult<T>(taskId: string): Promise<TaskResult<T> | null> {
    const task = this.tasks.get(taskId);
    return (task?.result as TaskResult<T>) ?? null;
  }

  async cleanup(maxAgeMs = 3600000): Promise<number> {
    const now = Date.now();
    let count = 0;

    for (const [taskId, task] of this.tasks) {
      if (task.info.completedAt) {
        const age = now - task.info.completedAt.getTime();
        if (age > maxAgeMs) {
          this.tasks.delete(taskId);
          this.tasksByRefId.delete(task.info.refId);
          count++;
        }
      }
    }

    return count;
  }

  async close(): Promise<void> {
    // Cancel all running tasks
    for (const task of this.tasks.values()) {
      if (task.info.status === 'running') {
        task.abortController.abort();
      }
    }

    // Wait for all to complete
    await Promise.allSettled(
      Array.from(this.tasks.values()).map(t => t.promise)
    );

    this.tasks.clear();
    this.tasksByRefId.clear();
    this.queue = [];
  }
}
```

---

## RefCache Integration

```typescript
// In RefCache class

async executeWithTimeout<T>(
  fn: () => Promise<T>,
  refId: string,
  timeoutMs: number
): Promise<T | AsyncTaskResponse> {
  if (!this.taskBackend) {
    // No task backend, just execute directly
    return fn();
  }

  // Race between execution and timeout
  const result = await Promise.race([
    fn().then(value => ({ type: 'success' as const, value })),
    sleep(timeoutMs).then(() => ({ type: 'timeout' as const })),
  ]);

  if (result.type === 'success') {
    return result.value;
  }

  // Timeout exceeded, submit to task backend
  const taskInfo = await this.taskBackend.submit({
    taskId: nanoid(),
    refId,
    execute: fn,
  });

  return this.buildAsyncTaskResponse(taskInfo);
}

private buildAsyncTaskResponse(info: TaskInfo): AsyncTaskResponse {
  return {
    status: info.status,
    refId: info.refId,
    progress: info.progress,
    eta: this.calculateEta(info),
  };
}

private calculateEta(info: TaskInfo): number | undefined {
  if (!info.progress?.progress || !info.progress?.total || !info.startedAt) {
    return undefined;
  }

  const elapsed = Date.now() - info.startedAt.getTime();
  const rate = info.progress.progress / elapsed;
  const remaining = info.progress.total - info.progress.progress;

  return Math.round(remaining / rate / 1000); // seconds
}
```

---

## Notes & Discoveries
_Running log of findings, decisions, and observations._

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-30 | Task created with interface and implementation design |

### Design Decisions

1. **Promise-based instead of ThreadPoolExecutor**: JavaScript's async model is inherently non-blocking. Using Promises with AbortController provides cancellation without true threads.

2. **Task queue with concurrency limit**: Prevents overwhelming the system while allowing multiple concurrent tasks.

3. **Automatic cleanup**: Completed tasks are automatically removed after a configurable delay to prevent memory leaks.

4. **ETA calculation**: Simple linear estimation based on progress rate. Can be improved with more sophisticated algorithms.

5. **Integration via executeWithTimeout**: RefCache method that races execution against timeout, falling back to task backend when needed.

---

## Blockers & Dependencies
_What's preventing progress or what must be completed first._

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01: Project Setup | Required | Project structure needed |
| Task-02: Models & Schemas | Required | TaskInfo, TaskStatus types |
| Task-03: Backend Protocol | Required | CacheBackend for storing results |
| Task-04: RefCache Core | Required | Integration point |

---

## Verification
_How to confirm this task is complete._

```bash
# Run task system tests
bun test tests/backends/task-memory.test.ts

# Test async timeout behavior
bun run -e "
import { MemoryTaskBackend } from './src/backends/task-memory';

const backend = new MemoryTaskBackend({ maxConcurrent: 2 });

const info = await backend.submit({
  taskId: 'test-1',
  refId: 'ref-1',
  execute: async () => {
    await new Promise(r => setTimeout(r, 2000));
    return 'done';
  },
});

console.log('Submitted:', info);

// Poll for completion
const interval = setInterval(async () => {
  const status = await backend.getStatus('test-1');
  console.log('Status:', status?.status);

  if (status?.status === 'complete') {
    const result = await backend.getResult('test-1');
    console.log('Result:', result);
    clearInterval(interval);
    await backend.close();
  }
}, 500);
"
```

### Test Examples
```typescript
// tests/backends/task-memory.test.ts
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { MemoryTaskBackend } from '../../src/backends/task-memory';

describe('MemoryTaskBackend', () => {
  let backend: MemoryTaskBackend;

  beforeEach(() => {
    backend = new MemoryTaskBackend({
      maxConcurrent: 2,
      cleanupDelayMs: 100,
    });
  });

  afterEach(async () => {
    await backend.close();
  });

  it('executes task and tracks status', async () => {
    const info = await backend.submit({
      taskId: 'task-1',
      refId: 'ref-1',
      execute: async () => {
        await new Promise(r => setTimeout(r, 50));
        return 'result';
      },
    });

    expect(info.status).toBe('running');

    // Wait for completion
    await new Promise(r => setTimeout(r, 100));

    const status = await backend.getStatus('task-1');
    expect(status?.status).toBe('complete');

    const result = await backend.getResult('task-1');
    expect(result?.value).toBe('result');
  });

  it('respects concurrency limit', async () => {
    let running = 0;
    let maxRunning = 0;

    const tasks = Array.from({ length: 5 }, (_, i) =>
      backend.submit({
        taskId: `task-${i}`,
        refId: `ref-${i}`,
        execute: async () => {
          running++;
          maxRunning = Math.max(maxRunning, running);
          await new Promise(r => setTimeout(r, 50));
          running--;
        },
      })
    );

    await Promise.all(tasks);
    await new Promise(r => setTimeout(r, 300));

    expect(maxRunning).toBeLessThanOrEqual(2);
  });

  it('handles task cancellation', async () => {
    const info = await backend.submit({
      taskId: 'cancel-me',
      refId: 'ref-cancel',
      execute: async () => {
        await new Promise(r => setTimeout(r, 5000));
        return 'should not complete';
      },
    });

    await new Promise(r => setTimeout(r, 50));
    const cancelled = await backend.cancel('cancel-me');
    expect(cancelled).toBe(true);

    await new Promise(r => setTimeout(r, 50));
    const status = await backend.getStatus('cancel-me');
    expect(status?.status).toBe('cancelled');
  });

  it('handles task failure', async () => {
    await backend.submit({
      taskId: 'fail-task',
      refId: 'ref-fail',
      execute: async () => {
        throw new Error('Task failed!');
      },
    });

    await new Promise(r => setTimeout(r, 50));

    const status = await backend.getStatus('fail-task');
    expect(status?.status).toBe('failed');
    expect(status?.error).toContain('Task failed!');
  });

  it('cleans up old completed tasks', async () => {
    await backend.submit({
      taskId: 'cleanup-task',
      refId: 'ref-cleanup',
      execute: async () => 'done',
    });

    await new Promise(r => setTimeout(r, 50));
    expect(await backend.getStatus('cleanup-task')).not.toBeNull();

    // Wait for cleanup delay
    await new Promise(r => setTimeout(r, 150));
    expect(await backend.getStatus('cleanup-task')).toBeNull();
  });
});
```

---

## File Structure
```
src/backends/
├── task-base.ts      # TaskBackend interface
└── task-memory.ts    # MemoryTaskBackend implementation
```

---

## Related
- **Parent Goal:** [06-TypeScript-RefCache](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-02](../Task-02/scratchpad.md), [Task-03](../Task-03/scratchpad.md), [Task-04](../Task-04/scratchpad.md)
- **Blocks:** Task-09 (FastMCP Integration - async_timeout decorator support)
- **External Links:**
  - [Python mcp-refcache backends/task_base.py](https://github.com/l4b4r4b4b4/mcp-refcache/blob/main/src/mcp_refcache/backends/task_base.py)
  - [Python mcp-refcache backends/task_memory.py](https://github.com/l4b4r4b4b4/mcp-refcache/blob/main/src/mcp_refcache/backends/task_memory.py)
  - [AbortController MDN](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
