/**
 * Storage interface types for the Fractal Agents Runtime — TypeScript/Bun.
 *
 * These interfaces define the contract for all storage operations. The
 * in-memory implementation lives in `./memory.ts`. The Postgres
 * implementation lives in `./postgres.ts`.
 *
 * Design decisions:
 *   - v0.0.1: No `owner_id` — authentication deferred to Goal 25.
 *   - v0.0.2: `StoreStorage` added for cross-thread key-value memory.
 *   - Delete returns `boolean` at the storage level; the HTTP route
 *     translates `true` → 200 `{}`, `false` → 404.
 *   - Search/count accept the request body types from `../models/`.
 *   - All async to allow drop-in replacement with Postgres later.
 *
 * Reference: apps/python/src/server/storage.py
 */

import type { Assistant, AssistantCreate, AssistantPatch, AssistantSearchRequest, AssistantCountRequest } from "../models/assistant";
import type { Thread, ThreadCreate, ThreadPatch, ThreadSearchRequest, ThreadCountRequest, ThreadState } from "../models/thread";
import type { Run, RunStatus } from "../models/run";
import type { StoreItem } from "../models/store";

// ---------------------------------------------------------------------------
// Assistant Store
// ---------------------------------------------------------------------------

/**
 * Storage interface for Assistant resources.
 *
 * Mirrors Python's `AssistantStore` (minus `owner_id`).
 */
export interface AssistantStore {
  /**
   * Create a new assistant.
   *
   * @param data - Creation payload (graph_id required, assistant_id optional).
   * @returns The created Assistant.
   * @throws Error if `graph_id` is missing.
   */
  create(data: AssistantCreate): Promise<Assistant>;

  /**
   * Get an assistant by ID.
   *
   * @param assistantId - UUID of the assistant.
   * @returns The Assistant if found, `null` otherwise.
   */
  get(assistantId: string): Promise<Assistant | null>;

  /**
   * Search assistants with filtering, sorting, and pagination.
   *
   * @param request - Search parameters (metadata, graph_id, name, limit, offset, sort).
   * @returns Array of matching assistants.
   */
  search(request: AssistantSearchRequest): Promise<Assistant[]>;

  /**
   * Update an assistant (partial update).
   *
   * Increments `version` on every successful update.
   *
   * @param assistantId - UUID of the assistant to update.
   * @param data - Fields to update.
   * @returns The updated Assistant if found, `null` otherwise.
   */
  update(assistantId: string, data: AssistantPatch): Promise<Assistant | null>;

  /**
   * Delete an assistant by ID.
   *
   * @param assistantId - UUID of the assistant to delete.
   * @returns `true` if deleted, `false` if not found.
   */
  delete(assistantId: string): Promise<boolean>;

  /**
   * Count assistants matching the given filters.
   *
   * @param request - Optional filter parameters (metadata, graph_id, name).
   * @returns The count of matching assistants.
   */
  count(request?: AssistantCountRequest): Promise<number>;

  /**
   * Clear all assistant data (for testing only).
   */
  clear(): Promise<void>;
}

// ---------------------------------------------------------------------------
// Thread Store
// ---------------------------------------------------------------------------

/**
 * Storage interface for Thread resources with state history tracking.
 *
 * Mirrors Python's `ThreadStore` (minus `owner_id`).
 */
export interface ThreadStore {
  /**
   * Create a new thread.
   *
   * Initialises the thread with status "idle" and an empty state history.
   *
   * @param data - Creation payload (thread_id optional).
   * @returns The created Thread.
   */
  create(data: ThreadCreate): Promise<Thread>;

  /**
   * Get a thread by ID.
   *
   * @param threadId - UUID of the thread.
   * @returns The Thread if found, `null` otherwise.
   */
  get(threadId: string): Promise<Thread | null>;

  /**
   * Search threads with filtering, sorting, and pagination.
   *
   * @param request - Search parameters (ids, metadata, values, status, limit, offset, sort).
   * @returns Array of matching threads.
   */
  search(request: ThreadSearchRequest): Promise<Thread[]>;

  /**
   * Update a thread (partial update — currently only metadata).
   *
   * @param threadId - UUID of the thread to update.
   * @param data - Fields to update.
   * @returns The updated Thread if found, `null` otherwise.
   */
  update(threadId: string, data: ThreadPatch): Promise<Thread | null>;

  /**
   * Delete a thread and its state history.
   *
   * @param threadId - UUID of the thread to delete.
   * @returns `true` if deleted, `false` if not found.
   */
  delete(threadId: string): Promise<boolean>;

  /**
   * Count threads matching the given filters.
   *
   * @param request - Optional filter parameters (metadata, values, status).
   * @returns The count of matching threads.
   */
  count(request?: ThreadCountRequest): Promise<number>;

  /**
   * Get the current state of a thread.
   *
   * Builds a `ThreadState` snapshot from the thread's current values,
   * metadata, and checkpoint information.
   *
   * @param threadId - UUID of the thread.
   * @returns ThreadState if the thread exists, `null` otherwise.
   */
  getState(threadId: string): Promise<ThreadState | null>;

  /**
   * Add a state snapshot to the thread's history.
   *
   * Also updates the thread's current `values` and `updated_at`.
   *
   * @param threadId - UUID of the thread.
   * @param state - State snapshot to record.
   * @returns `true` if added, `false` if thread not found.
   */
  addStateSnapshot(threadId: string, state: Record<string, unknown>): Promise<boolean>;

  /**
   * Get state history for a thread.
   *
   * Returns snapshots in reverse chronological order (most recent first).
   *
   * @param threadId - UUID of the thread.
   * @param limit - Maximum number of states to return (default 10).
   * @param before - Return states before this checkpoint ID (optional).
   * @returns Array of ThreadState if thread exists, `null` otherwise.
   */
  getHistory(
    threadId: string,
    limit?: number,
    before?: string,
  ): Promise<ThreadState[] | null>;

  /**
   * Clear all thread data including history (for testing only).
   */
  clear(): Promise<void>;
}

// ---------------------------------------------------------------------------
// Run Store
// ---------------------------------------------------------------------------

/**
 * Storage interface for Run resources with thread-scoped operations.
 *
 * Mirrors Python's `RunStore` (minus `owner_id`).
 * Runs are always scoped to a thread, so most operations take `threadId`.
 */
export interface RunStore {
  /**
   * Create a new run.
   *
   * @param data - Run data with required `thread_id` and `assistant_id`.
   * @returns The created Run.
   * @throws Error if `thread_id` or `assistant_id` is missing.
   */
  create(data: {
    thread_id: string;
    assistant_id: string;
    status?: RunStatus;
    metadata?: Record<string, unknown>;
    kwargs?: Record<string, unknown>;
    multitask_strategy?: string;
  }): Promise<Run>;

  /**
   * Get a run by its ID (not thread-scoped).
   *
   * @param runId - UUID of the run.
   * @returns The Run if found, `null` otherwise.
   */
  get(runId: string): Promise<Run | null>;

  /**
   * List runs for a specific thread with pagination and optional status filter.
   *
   * Returns runs sorted by `created_at` descending (most recent first).
   *
   * @param threadId - Thread ID to filter by.
   * @param limit - Maximum number of runs to return (default 10).
   * @param offset - Number of runs to skip (default 0).
   * @param status - Optional status filter.
   * @returns Array of matching runs.
   */
  listByThread(
    threadId: string,
    limit?: number,
    offset?: number,
    status?: RunStatus,
  ): Promise<Run[]>;

  /**
   * Get a specific run by thread ID and run ID.
   *
   * Returns `null` if the run doesn't exist or doesn't belong to the thread.
   *
   * @param threadId - Thread ID the run should belong to.
   * @param runId - Run ID to fetch.
   * @returns The Run if found and belongs to the thread, `null` otherwise.
   */
  getByThread(threadId: string, runId: string): Promise<Run | null>;

  /**
   * Delete a run by thread ID and run ID.
   *
   * @param threadId - Thread ID the run belongs to.
   * @param runId - Run ID to delete.
   * @returns `true` if deleted, `false` if not found or wrong thread.
   */
  deleteByThread(threadId: string, runId: string): Promise<boolean>;

  /**
   * Get the currently active (pending or running) run for a thread.
   *
   * @param threadId - Thread ID to check.
   * @returns The active Run if one exists, `null` otherwise.
   */
  getActiveRun(threadId: string): Promise<Run | null>;

  /**
   * Update a run's status.
   *
   * @param runId - Run ID to update.
   * @param status - New status value.
   * @returns The updated Run if found, `null` otherwise.
   */
  updateStatus(runId: string, status: RunStatus): Promise<Run | null>;

  /**
   * Count runs for a specific thread.
   *
   * @param threadId - Thread ID to count runs for.
   * @returns Number of runs for the thread.
   */
  countByThread(threadId: string): Promise<number>;

  /**
   * Clear all run data (for testing only).
   */
  clear(): Promise<void>;
}

// ---------------------------------------------------------------------------
// Store Storage (cross-thread key-value memory)
// ---------------------------------------------------------------------------

/**
 * Storage interface for the cross-thread key-value Store API.
 *
 * Items are organized by `(namespace, key)` and scoped per-user via
 * `ownerId`. This provides long-term memory that persists across
 * threads and conversations.
 *
 * Mirrors Python's `StoreStorage` class.
 *
 * Reference: apps/python/src/server/storage.py → StoreStorage
 */
export interface StoreStorage {
  /**
   * Store or update an item (upsert).
   *
   * If an item with the same `(namespace, key, ownerId)` exists, its
   * `value` and `updated_at` are overwritten. If `metadata` is provided,
   * it replaces the existing metadata.
   *
   * @param namespace - Namespace for logical grouping.
   * @param key - Unique key within the namespace.
   * @param value - JSON-serializable value to store.
   * @param ownerId - Owner ID for per-user isolation.
   * @param metadata - Optional metadata to associate with the item.
   * @returns The stored (or updated) StoreItem.
   */
  put(
    namespace: string,
    key: string,
    value: Record<string, unknown>,
    ownerId: string,
    metadata?: Record<string, unknown>,
  ): Promise<StoreItem>;

  /**
   * Get an item by namespace and key.
   *
   * @param namespace - Namespace for the item.
   * @param key - Key within the namespace.
   * @param ownerId - Owner ID for per-user isolation.
   * @returns The StoreItem if found, `null` otherwise.
   */
  get(
    namespace: string,
    key: string,
    ownerId: string,
  ): Promise<StoreItem | null>;

  /**
   * Delete an item by namespace and key.
   *
   * @param namespace - Namespace for the item.
   * @param key - Key within the namespace.
   * @param ownerId - Owner ID for per-user isolation.
   * @returns `true` if deleted, `false` if not found.
   */
  delete(
    namespace: string,
    key: string,
    ownerId: string,
  ): Promise<boolean>;

  /**
   * Search items within a namespace.
   *
   * Results are sorted by key for consistent ordering and paginated
   * via `limit` and `offset`.
   *
   * @param namespace - Namespace to search within.
   * @param ownerId - Owner ID for per-user isolation.
   * @param prefix - Optional key prefix filter.
   * @param limit - Maximum number of results (default 10).
   * @param offset - Number of results to skip (default 0).
   * @returns Array of matching StoreItems.
   */
  search(
    namespace: string,
    ownerId: string,
    prefix?: string,
    limit?: number,
    offset?: number,
  ): Promise<StoreItem[]>;

  /**
   * List all namespaces for an owner.
   *
   * @param ownerId - Owner ID for per-user isolation.
   * @returns Array of namespace strings.
   */
  listNamespaces(ownerId: string): Promise<string[]>;

  /**
   * Clear all store items (for testing only).
   */
  clear(): Promise<void>;
}

// ---------------------------------------------------------------------------
// Storage Container
// ---------------------------------------------------------------------------

/**
 * Container for all resource stores.
 *
 * Provides a single access point for all storage operations.
 * Mirrors Python's `Storage` class.
 */
export interface Storage {
  /** Assistant resource store. */
  readonly assistants: AssistantStore;

  /** Thread resource store (with state history). */
  readonly threads: ThreadStore;

  /** Run resource store (thread-scoped). */
  readonly runs: RunStore;

  /** Cross-thread key-value store (long-term memory). */
  readonly store: StoreStorage;

  /**
   * Clear all stores (for testing only).
   */
  clearAll(): Promise<void>;
}
