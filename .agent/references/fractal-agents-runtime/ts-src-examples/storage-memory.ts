/**
 * In-memory storage implementations for the Fractal Agents Runtime — TypeScript/Bun.
 *
 * Each store uses a `Map<string, T>` for O(1) lookups by ID. Search, count,
 * and list operations iterate the map values and apply filters in memory.
 *
 * Design decisions (v0.0.1):
 *   - No `owner_id` — authentication deferred to Goal 25.
 *   - IDs via `crypto.randomUUID()` (standard UUID with dashes, matches OpenAPI `format: uuid`).
 *   - ISO 8601 timestamps with "Z" suffix (UTC).
 *   - Assistant `version` starts at 1, incremented on every PATCH (Critical Finding #7).
 *   - Metadata merge on update (shallow merge, matching Python behaviour).
 *   - Delete returns `boolean`; the HTTP route translates to `{}` or 404.
 *   - Thread state history stored in a separate `Map<string, snapshot[]>`.
 *
 * Reference: apps/python/src/server/storage.py
 */

import type {
  Assistant,
  AssistantCreate,
  AssistantPatch,
  AssistantSearchRequest,
  AssistantCountRequest,
  Config,
} from "../models/assistant";
import type {
  Thread,
  ThreadCreate,
  ThreadPatch,
  ThreadSearchRequest,
  ThreadCountRequest,
  ThreadState,
  ThreadStatus,
} from "../models/thread";
import type { Run, RunStatus } from "../models/run";
import type {
  AssistantStore,
  ThreadStore,
  RunStore,
  StoreStorage,
  Storage,
} from "./types";
import type { StoreItem } from "../models/store";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Generate a UUID (with dashes — matches OpenAPI `format: uuid`). */
function generateId(): string {
  return crypto.randomUUID();
}

/** Current UTC time as ISO 8601 string with Z suffix. */
function utcNow(): string {
  return new Date().toISOString(); // e.g. "2025-07-15T12:34:56.789Z"
}

/**
 * Shallow-check whether `target` contains all key-value pairs from `filter`.
 *
 * Used for metadata filtering: every key in the filter object must exist in
 * the target with a strictly equal (`===`) value. Nested objects are compared
 * by reference, matching Python's in-memory behaviour.
 */
function metadataMatches(
  target: Record<string, unknown>,
  filter: Record<string, unknown>,
): boolean {
  for (const [key, value] of Object.entries(filter)) {
    if (target[key] !== value) {
      // Fall back to JSON comparison for nested objects/arrays
      if (
        typeof value === "object" &&
        value !== null &&
        JSON.stringify(target[key]) === JSON.stringify(value)
      ) {
        continue;
      }
      return false;
    }
  }
  return true;
}

/**
 * Generic sort comparator for a given field name and order.
 *
 * Supports string (lexicographic) and number comparisons. Falls back to
 * string comparison via `String()` for other types.
 */
function sortComparator(
  sortBy: string,
  sortOrder: "asc" | "desc",
): (a: Record<string, unknown>, b: Record<string, unknown>) => number {
  const direction = sortOrder === "asc" ? 1 : -1;
  return (a, b) => {
    const valueA = a[sortBy];
    const valueB = b[sortBy];
    if (valueA === valueB) return 0;
    if (valueA === undefined || valueA === null) return direction;
    if (valueB === undefined || valueB === null) return -direction;
    if (typeof valueA === "number" && typeof valueB === "number") {
      return (valueA - valueB) * direction;
    }
    return String(valueA).localeCompare(String(valueB)) * direction;
  };
}

// ---------------------------------------------------------------------------
// In-Memory Assistant Store
// ---------------------------------------------------------------------------

export class InMemoryAssistantStore implements AssistantStore {
  private readonly data = new Map<string, Record<string, unknown>>();

  async create(data: AssistantCreate): Promise<Assistant> {
    if (!data.graph_id) {
      throw new Error("graph_id is required");
    }

    const assistantId = data.assistant_id ?? generateId();

    // Handle if_exists
    if (this.data.has(assistantId)) {
      const strategy = data.if_exists ?? "raise";
      if (strategy === "do_nothing") {
        return this.toModel(this.data.get(assistantId)!);
      }
      throw new Error(`Assistant ${assistantId} already exists`);
    }

    const now = utcNow();
    const record: Record<string, unknown> = {
      assistant_id: assistantId,
      graph_id: data.graph_id,
      config: data.config ?? {},
      context: data.context ?? {},
      metadata: data.metadata ?? {},
      name: data.name ?? undefined,
      description: data.description ?? undefined,
      version: 1,
      created_at: now,
      updated_at: now,
    };

    this.data.set(assistantId, record);
    return this.toModel(record);
  }

  async get(assistantId: string): Promise<Assistant | null> {
    const record = this.data.get(assistantId);
    if (!record) return null;
    return this.toModel(record);
  }

  async search(request: AssistantSearchRequest): Promise<Assistant[]> {
    const limit = request.limit ?? 10;
    const offset = request.offset ?? 0;
    const sortBy = request.sort_by ?? "created_at";
    const sortOrder = request.sort_order ?? "desc";

    let results: Record<string, unknown>[] = [];

    for (const record of this.data.values()) {
      // Filter by metadata
      if (request.metadata && !metadataMatches(record.metadata as Record<string, unknown>, request.metadata)) {
        continue;
      }
      // Filter by graph_id
      if (request.graph_id !== undefined && record.graph_id !== request.graph_id) {
        continue;
      }
      // Filter by name (case-insensitive partial match, matching Python behaviour)
      if (request.name !== undefined) {
        const recordName = record.name as string | undefined;
        if (!recordName || !recordName.toLowerCase().includes(request.name.toLowerCase())) {
          continue;
        }
      }
      results.push(record);
    }

    // Sort
    results.sort(sortComparator(sortBy, sortOrder));

    // Paginate
    results = results.slice(offset, offset + limit);

    return results.map((record) => this.toModel(record));
  }

  async update(assistantId: string, data: AssistantPatch): Promise<Assistant | null> {
    const record = this.data.get(assistantId);
    if (!record) return null;

    const now = utcNow();

    // Update simple fields (skip undefined to avoid overwriting with nothing)
    if (data.graph_id !== undefined) record.graph_id = data.graph_id;
    if (data.config !== undefined) record.config = data.config;
    if (data.context !== undefined) record.context = data.context;
    if (data.name !== undefined) record.name = data.name;
    if (data.description !== undefined) record.description = data.description;

    // Metadata: shallow merge (matching Python behaviour)
    if (data.metadata !== undefined) {
      const currentMetadata = (record.metadata ?? {}) as Record<string, unknown>;
      record.metadata = { ...currentMetadata, ...data.metadata };
    }

    // Increment version (Critical Finding #7)
    const currentVersion = (record.version as number) ?? 1;
    record.version = currentVersion + 1;

    record.updated_at = now;
    this.data.set(assistantId, record);

    return this.toModel(record);
  }

  async delete(assistantId: string): Promise<boolean> {
    return this.data.delete(assistantId);
  }

  async count(request?: AssistantCountRequest): Promise<number> {
    if (!request) return this.data.size;

    let count = 0;
    for (const record of this.data.values()) {
      if (request.metadata && !metadataMatches(record.metadata as Record<string, unknown>, request.metadata)) {
        continue;
      }
      if (request.graph_id !== undefined && record.graph_id !== request.graph_id) {
        continue;
      }
      if (request.name !== undefined) {
        const recordName = record.name as string | undefined;
        if (!recordName || !recordName.toLowerCase().includes(request.name.toLowerCase())) {
          continue;
        }
      }
      count++;
    }
    return count;
  }

  async clear(): Promise<void> {
    this.data.clear();
  }

  // -------------------------------------------------------------------------
  // Internal
  // -------------------------------------------------------------------------

  private toModel(data: Record<string, unknown>): Assistant {
    const configData = (data.config ?? {}) as Record<string, unknown>;
    const config: Config = {
      tags: (configData.tags as string[] | undefined) ?? undefined,
      recursion_limit: (configData.recursion_limit as number | undefined) ?? undefined,
      configurable: (configData.configurable as Record<string, unknown> | undefined) ?? undefined,
    };

    return {
      assistant_id: data.assistant_id as string,
      graph_id: data.graph_id as string,
      config,
      context: (data.context as Record<string, unknown> | undefined) ?? undefined,
      metadata: (data.metadata as Record<string, unknown>) ?? {},
      name: data.name as string | undefined,
      description: data.description as string | null | undefined,
      version: (data.version as number | undefined) ?? 1,
      created_at: data.created_at as string,
      updated_at: data.updated_at as string,
    };
  }
}

// ---------------------------------------------------------------------------
// In-Memory Thread Store
// ---------------------------------------------------------------------------

/** Internal shape of a state history snapshot. */
interface StateSnapshot {
  values: Record<string, unknown>;
  next: string[];
  tasks: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
  checkpoint_id: string;
  parent_checkpoint: Record<string, unknown> | null;
  interrupts: Array<Record<string, unknown>>;
  created_at: string;
}

export class InMemoryThreadStore implements ThreadStore {
  private readonly data = new Map<string, Record<string, unknown>>();
  private readonly history = new Map<string, StateSnapshot[]>();

  async create(data: ThreadCreate): Promise<Thread> {
    const threadId = data.thread_id ?? generateId();

    // Handle if_exists
    if (this.data.has(threadId)) {
      const strategy = data.if_exists ?? "raise";
      if (strategy === "do_nothing") {
        return this.toModel(this.data.get(threadId)!);
      }
      throw new Error(`Thread ${threadId} already exists`);
    }

    const now = utcNow();
    const record: Record<string, unknown> = {
      thread_id: threadId,
      metadata: data.metadata ?? {},
      config: {},
      status: "idle" as ThreadStatus,
      values: {},
      interrupts: {},
      created_at: now,
      updated_at: now,
    };

    this.data.set(threadId, record);
    this.history.set(threadId, []);

    return this.toModel(record);
  }

  async get(threadId: string): Promise<Thread | null> {
    const record = this.data.get(threadId);
    if (!record) return null;
    return this.toModel(record);
  }

  async search(request: ThreadSearchRequest): Promise<Thread[]> {
    const limit = request.limit ?? 10;
    const offset = request.offset ?? 0;
    const sortBy = request.sort_by ?? "created_at";
    const sortOrder = request.sort_order ?? "desc";

    let results: Record<string, unknown>[] = [];

    for (const record of this.data.values()) {
      // Filter by IDs
      if (request.ids && request.ids.length > 0) {
        if (!request.ids.includes(record.thread_id as string)) {
          continue;
        }
      }
      // Filter by metadata
      if (request.metadata && !metadataMatches(record.metadata as Record<string, unknown>, request.metadata)) {
        continue;
      }
      // Filter by values
      if (request.values && !metadataMatches(record.values as Record<string, unknown>, request.values)) {
        continue;
      }
      // Filter by status
      if (request.status !== undefined && record.status !== request.status) {
        continue;
      }
      results.push(record);
    }

    // Sort
    results.sort(sortComparator(sortBy, sortOrder));

    // Paginate
    results = results.slice(offset, offset + limit);

    return results.map((record) => this.toModel(record));
  }

  async update(threadId: string, data: ThreadPatch): Promise<Thread | null> {
    const record = this.data.get(threadId);
    if (!record) return null;

    // Metadata: shallow merge
    if (data.metadata !== undefined) {
      const currentMetadata = (record.metadata ?? {}) as Record<string, unknown>;
      record.metadata = { ...currentMetadata, ...data.metadata };
    }

    // Status: replace (used internally by runs system)
    if (data.status !== undefined) {
      record.status = data.status;
    }

    // Values: replace (used internally by runs system to persist agent output)
    if (data.values !== undefined) {
      record.values = data.values;
    }

    record.updated_at = utcNow();
    this.data.set(threadId, record);

    return this.toModel(record);
  }

  async delete(threadId: string): Promise<boolean> {
    const deleted = this.data.delete(threadId);
    if (deleted) {
      this.history.delete(threadId);
    }
    return deleted;
  }

  async count(request?: ThreadCountRequest): Promise<number> {
    if (!request) return this.data.size;

    let count = 0;
    for (const record of this.data.values()) {
      if (request.metadata && !metadataMatches(record.metadata as Record<string, unknown>, request.metadata)) {
        continue;
      }
      if (request.values && !metadataMatches(record.values as Record<string, unknown>, request.values)) {
        continue;
      }
      if (request.status !== undefined && record.status !== request.status) {
        continue;
      }
      count++;
    }
    return count;
  }

  async getState(threadId: string): Promise<ThreadState | null> {
    const record = this.data.get(threadId);
    if (!record) return null;

    const now = utcNow();
    return {
      values: (record.values as Record<string, unknown>) ?? {},
      next: [],
      tasks: [],
      checkpoint: {
        thread_id: threadId,
        checkpoint_ns: "",
        checkpoint_id: (record.checkpoint_id as string) ?? generateId(),
      },
      metadata: (record.metadata as Record<string, unknown>) ?? {},
      created_at: now,
      parent_checkpoint: undefined,
      interrupts: [],
    };
  }

  async addStateSnapshot(threadId: string, state: Record<string, unknown>): Promise<boolean> {
    const record = this.data.get(threadId);
    if (!record) return false;

    const snapshots = this.history.get(threadId) ?? [];

    // Resolve snapshot values defensively.
    // Expected shape: { values: { messages: [...] }, ... }
    // Fallback: if `state.values` is missing, treat `state` itself as the
    // values dict (caller passed raw values without wrapping). This mirrors
    // the Python fix in `postgres_storage.py`.
    let snapshotValues: Record<string, unknown>;
    if (state.values !== undefined && typeof state.values === "object" && state.values !== null) {
      snapshotValues = state.values as Record<string, unknown>;
    } else if (state.messages !== undefined) {
      // Caller passed { messages: [...] } directly — use it as values
      console.warn(
        `[storage] addStateSnapshot called without "values" key for thread ${threadId}. ` +
          `Using state directly as values. Callers should pass { values: {...} }.`,
      );
      snapshotValues = state;
    } else {
      snapshotValues = {};
    }

    const snapshot: StateSnapshot = {
      values: snapshotValues,
      next: (state.next as string[]) ?? [],
      tasks: (state.tasks as Array<Record<string, unknown>>) ?? [],
      metadata: (state.metadata as Record<string, unknown>) ?? {},
      checkpoint_id: generateId(),
      parent_checkpoint: (state.parent_checkpoint as Record<string, unknown> | null) ?? null,
      interrupts: (state.interrupts as Array<Record<string, unknown>>) ?? [],
      created_at: utcNow(),
    };

    snapshots.push(snapshot);
    this.history.set(threadId, snapshots);

    // Update thread's current values and timestamp
    record.values = snapshot.values;
    record.updated_at = utcNow();
    this.data.set(threadId, record);

    return true;
  }

  async getHistory(
    threadId: string,
    limit = 10,
    before?: string,
  ): Promise<ThreadState[] | null> {
    const record = this.data.get(threadId);
    if (!record) return null;

    let snapshots = this.history.get(threadId) ?? [];

    // If before is specified, take only snapshots before that checkpoint
    if (before) {
      const filtered: StateSnapshot[] = [];
      for (const snapshot of snapshots) {
        if (snapshot.checkpoint_id === before) {
          break;
        }
        filtered.push(snapshot);
      }
      snapshots = filtered;
    }

    // Reverse (most recent first) and limit
    const recent = [...snapshots].reverse().slice(0, limit);

    // Convert to ThreadState objects
    return recent.map((snapshot) => ({
      values: snapshot.values,
      next: snapshot.next,
      tasks: snapshot.tasks,
      checkpoint: {
        thread_id: threadId,
        checkpoint_ns: "",
        checkpoint_id: snapshot.checkpoint_id,
      },
      metadata: snapshot.metadata,
      created_at: snapshot.created_at,
      parent_checkpoint: snapshot.parent_checkpoint ?? undefined,
      interrupts: snapshot.interrupts,
    }));
  }

  async clear(): Promise<void> {
    this.data.clear();
    this.history.clear();
  }

  // -------------------------------------------------------------------------
  // Internal
  // -------------------------------------------------------------------------

  private toModel(data: Record<string, unknown>): Thread {
    return {
      thread_id: data.thread_id as string,
      metadata: (data.metadata as Record<string, unknown>) ?? {},
      config: (data.config as Record<string, unknown> | undefined) ?? undefined,
      status: (data.status as ThreadStatus) ?? "idle",
      values: (data.values as Record<string, unknown> | undefined) ?? undefined,
      interrupts: (data.interrupts as Record<string, unknown> | undefined) ?? undefined,
      created_at: data.created_at as string,
      updated_at: data.updated_at as string,
    };
  }
}

// ---------------------------------------------------------------------------
// In-Memory Run Store
// ---------------------------------------------------------------------------

export class InMemoryRunStore implements RunStore {
  private readonly data = new Map<string, Record<string, unknown>>();

  async create(data: {
    thread_id: string;
    assistant_id: string;
    status?: RunStatus;
    metadata?: Record<string, unknown>;
    kwargs?: Record<string, unknown>;
    multitask_strategy?: string;
  }): Promise<Run> {
    if (!data.thread_id) {
      throw new Error("thread_id is required");
    }
    if (!data.assistant_id) {
      throw new Error("assistant_id is required");
    }

    const runId = generateId();
    const now = utcNow();

    const record: Record<string, unknown> = {
      run_id: runId,
      thread_id: data.thread_id,
      assistant_id: data.assistant_id,
      status: data.status ?? "pending",
      metadata: data.metadata ?? {},
      kwargs: data.kwargs ?? {},
      multitask_strategy: data.multitask_strategy ?? "reject",
      created_at: now,
      updated_at: now,
    };

    this.data.set(runId, record);
    return this.toModel(record);
  }

  async get(runId: string): Promise<Run | null> {
    const record = this.data.get(runId);
    if (!record) return null;
    return this.toModel(record);
  }

  async listByThread(
    threadId: string,
    limit = 10,
    offset = 0,
    status?: RunStatus,
  ): Promise<Run[]> {
    const results: Record<string, unknown>[] = [];

    for (const record of this.data.values()) {
      if (record.thread_id !== threadId) continue;
      if (status !== undefined && record.status !== status) continue;
      results.push(record);
    }

    // Sort by created_at descending (most recent first)
    results.sort(sortComparator("created_at", "desc"));

    // Paginate
    return results.slice(offset, offset + limit).map((record) => this.toModel(record));
  }

  async getByThread(threadId: string, runId: string): Promise<Run | null> {
    const record = this.data.get(runId);
    if (!record) return null;
    if (record.thread_id !== threadId) return null;
    return this.toModel(record);
  }

  async deleteByThread(threadId: string, runId: string): Promise<boolean> {
    const record = this.data.get(runId);
    if (!record) return false;
    if (record.thread_id !== threadId) return false;
    return this.data.delete(runId);
  }

  async getActiveRun(threadId: string): Promise<Run | null> {
    for (const record of this.data.values()) {
      if (record.thread_id !== threadId) continue;
      const status = record.status as string;
      if (status === "pending" || status === "running") {
        return this.toModel(record);
      }
    }
    return null;
  }

  async updateStatus(runId: string, status: RunStatus): Promise<Run | null> {
    const record = this.data.get(runId);
    if (!record) return null;

    record.status = status;
    record.updated_at = utcNow();
    this.data.set(runId, record);

    return this.toModel(record);
  }

  async countByThread(threadId: string): Promise<number> {
    let count = 0;
    for (const record of this.data.values()) {
      if (record.thread_id === threadId) count++;
    }
    return count;
  }

  async clear(): Promise<void> {
    this.data.clear();
  }

  // -------------------------------------------------------------------------
  // Internal
  // -------------------------------------------------------------------------

  private toModel(data: Record<string, unknown>): Run {
    return {
      run_id: data.run_id as string,
      thread_id: data.thread_id as string,
      assistant_id: data.assistant_id as string,
      status: (data.status as RunStatus) ?? "pending",
      metadata: (data.metadata as Record<string, unknown>) ?? {},
      kwargs: (data.kwargs as Record<string, unknown> | undefined) ?? undefined,
      multitask_strategy: data.multitask_strategy as Run["multitask_strategy"],
      created_at: data.created_at as string,
      updated_at: data.updated_at as string,
    };
  }
}

// ---------------------------------------------------------------------------
// In-Memory Store Storage (cross-thread key-value memory)
// ---------------------------------------------------------------------------

/**
 * Internal record for an in-memory store item.
 *
 * Holds the mutable fields that `put()` can update. Converted to a
 * `StoreItem` model object via `toModel()` before returning to callers.
 */
interface StoreRecord {
  namespace: string;
  key: string;
  value: Record<string, unknown>;
  ownerId: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/**
 * In-memory implementation of `StoreStorage`.
 *
 * Items are stored in a nested `Map` structure:
 *   `ownerId → namespace → key → StoreRecord`
 *
 * This mirrors Python's `StoreStorage._items` dict structure:
 *   `{owner_id: {namespace: {key: StoreItem}}}`
 *
 * All operations are O(1) for put/get/delete. Search and
 * listNamespaces iterate the owner's namespace map.
 *
 * Reference: apps/python/src/server/storage.py → StoreStorage
 */
export class InMemoryStoreStorage implements StoreStorage {
  /** Structure: ownerId → namespace → key → StoreRecord */
  private readonly data: Map<string, Map<string, Map<string, StoreRecord>>> =
    new Map();

  async put(
    namespace: string,
    key: string,
    value: Record<string, unknown>,
    ownerId: string,
    metadata?: Record<string, unknown>,
  ): Promise<StoreItem> {
    // Ensure owner map exists
    if (!this.data.has(ownerId)) {
      this.data.set(ownerId, new Map());
    }
    const ownerStore = this.data.get(ownerId)!;

    // Ensure namespace map exists
    if (!ownerStore.has(namespace)) {
      ownerStore.set(namespace, new Map());
    }
    const namespaceStore = ownerStore.get(namespace)!;

    const existing = namespaceStore.get(key);
    if (existing) {
      // Update existing item
      existing.value = value;
      existing.updated_at = utcNow();
      if (metadata !== undefined) {
        existing.metadata = metadata;
      }
      return this.toModel(existing);
    }

    // Create new item
    const now = utcNow();
    const record: StoreRecord = {
      namespace,
      key,
      value,
      ownerId,
      metadata: metadata ?? {},
      created_at: now,
      updated_at: now,
    };
    namespaceStore.set(key, record);
    return this.toModel(record);
  }

  async get(
    namespace: string,
    key: string,
    ownerId: string,
  ): Promise<StoreItem | null> {
    const ownerStore = this.data.get(ownerId);
    if (!ownerStore) return null;

    const namespaceStore = ownerStore.get(namespace);
    if (!namespaceStore) return null;

    const record = namespaceStore.get(key);
    return record ? this.toModel(record) : null;
  }

  async delete(
    namespace: string,
    key: string,
    ownerId: string,
  ): Promise<boolean> {
    const ownerStore = this.data.get(ownerId);
    if (!ownerStore) return false;

    const namespaceStore = ownerStore.get(namespace);
    if (!namespaceStore) return false;

    return namespaceStore.delete(key);
  }

  async search(
    namespace: string,
    ownerId: string,
    prefix?: string,
    limit: number = 10,
    offset: number = 0,
  ): Promise<StoreItem[]> {
    const ownerStore = this.data.get(ownerId);
    if (!ownerStore) return [];

    const namespaceStore = ownerStore.get(namespace);
    if (!namespaceStore) return [];

    let items = Array.from(namespaceStore.values());

    // Apply prefix filter
    if (prefix) {
      items = items.filter((record) => record.key.startsWith(prefix));
    }

    // Sort by key for consistent ordering (matches Python)
    items.sort((recordA, recordB) => recordA.key.localeCompare(recordB.key));

    // Apply pagination
    const paginated = items.slice(offset, offset + limit);
    return paginated.map((record) => this.toModel(record));
  }

  async listNamespaces(ownerId: string): Promise<string[]> {
    const ownerStore = this.data.get(ownerId);
    if (!ownerStore) return [];

    return Array.from(ownerStore.keys());
  }

  async clear(): Promise<void> {
    this.data.clear();
  }

  // -------------------------------------------------------------------------
  // Internal
  // -------------------------------------------------------------------------

  private toModel(record: StoreRecord): StoreItem {
    return {
      namespace: record.namespace,
      key: record.key,
      value: record.value,
      metadata: record.metadata,
      created_at: record.created_at,
      updated_at: record.updated_at,
    };
  }
}

// ---------------------------------------------------------------------------
// In-Memory Storage Container
// ---------------------------------------------------------------------------

/**
 * Bundles all in-memory stores into a single `Storage` instance.
 *
 * Mirrors Python's `Storage` class.
 */
export class InMemoryStorage implements Storage {
  readonly assistants: InMemoryAssistantStore;
  readonly threads: InMemoryThreadStore;
  readonly runs: InMemoryRunStore;
  readonly store: InMemoryStoreStorage;

  constructor() {
    this.assistants = new InMemoryAssistantStore();
    this.threads = new InMemoryThreadStore();
    this.runs = new InMemoryRunStore();
    this.store = new InMemoryStoreStorage();
  }

  async clearAll(): Promise<void> {
    await this.assistants.clear();
    await this.threads.clear();
    await this.runs.clear();
    await this.store.clear();
  }
}
