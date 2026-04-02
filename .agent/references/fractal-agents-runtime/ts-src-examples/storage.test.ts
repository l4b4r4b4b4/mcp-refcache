/**
 * Tests for in-memory storage implementations.
 *
 * Covers:
 *   - InMemoryAssistantStore: CRUD, search, count, pagination, sort, versioning, if_exists
 *   - InMemoryThreadStore: CRUD, search, count, state, history, if_exists, delete cascades history
 *   - InMemoryRunStore: CRUD, listByThread, getByThread, deleteByThread, activeRun, updateStatus, countByThread
 *   - InMemoryStorage container: clearAll
 *   - getStorage / resetStorage singleton factory
 */

import { describe, test, expect, beforeEach } from "bun:test";

import {
  InMemoryAssistantStore,
  InMemoryThreadStore,
  InMemoryRunStore,
  InMemoryStorage,
} from "../src/storage/memory";
import { getStorage, resetStorage } from "../src/storage/index";
import type { AssistantCreate, AssistantPatch } from "../src/models/assistant";
import type { ThreadCreate, ThreadPatch } from "../src/models/thread";
import type { RunStatus } from "../src/models/run";

// ===========================================================================
// InMemoryAssistantStore
// ===========================================================================

describe("InMemoryAssistantStore", () => {
  let store: InMemoryAssistantStore;

  beforeEach(() => {
    store = new InMemoryAssistantStore();
  });

  // -------------------------------------------------------------------------
  // create
  // -------------------------------------------------------------------------

  describe("create", () => {
    test("creates an assistant with required fields", async () => {
      const assistant = await store.create({ graph_id: "agent" });

      expect(assistant.assistant_id).toBeDefined();
      expect(assistant.assistant_id.length).toBeGreaterThan(0);
      expect(assistant.graph_id).toBe("agent");
      expect(assistant.config).toEqual({});
      expect(assistant.metadata).toEqual({});
      expect(assistant.version).toBe(1);
      expect(assistant.created_at).toBeDefined();
      expect(assistant.updated_at).toBeDefined();
      expect(assistant.created_at).toBe(assistant.updated_at);
    });

    test("creates with explicit assistant_id", async () => {
      const explicitId = crypto.randomUUID();
      const assistant = await store.create({
        graph_id: "agent",
        assistant_id: explicitId,
      });
      expect(assistant.assistant_id).toBe(explicitId);
    });

    test("creates with all optional fields", async () => {
      const assistant = await store.create({
        graph_id: "agent",
        config: { tags: ["test"], recursion_limit: 50 },
        context: { system: "hello" },
        metadata: { env: "test" },
        name: "My Assistant",
        description: "A test assistant",
      });

      expect(assistant.graph_id).toBe("agent");
      expect(assistant.config).toEqual({ tags: ["test"], recursion_limit: 50 });
      expect(assistant.context).toEqual({ system: "hello" });
      expect(assistant.metadata).toEqual({ env: "test" });
      expect(assistant.name).toBe("My Assistant");
      expect(assistant.description).toBe("A test assistant");
    });

    test("generates unique IDs for different assistants", async () => {
      const first = await store.create({ graph_id: "agent" });
      const second = await store.create({ graph_id: "agent" });
      expect(first.assistant_id).not.toBe(second.assistant_id);
    });

    test("throws if graph_id is missing", async () => {
      await expect(store.create({ graph_id: "" })).rejects.toThrow(
        "graph_id is required",
      );
    });

    test("throws on duplicate assistant_id with if_exists=raise (default)", async () => {
      const id = crypto.randomUUID();
      await store.create({ graph_id: "agent", assistant_id: id });
      await expect(
        store.create({ graph_id: "agent", assistant_id: id }),
      ).rejects.toThrow(`Assistant ${id} already exists`);
    });

    test("returns existing on duplicate with if_exists=do_nothing", async () => {
      const id = crypto.randomUUID();
      const original = await store.create({
        graph_id: "agent",
        assistant_id: id,
        name: "Original",
      });
      const duplicate = await store.create({
        graph_id: "agent",
        assistant_id: id,
        name: "Duplicate",
        if_exists: "do_nothing",
      });

      expect(duplicate.assistant_id).toBe(original.assistant_id);
      expect(duplicate.name).toBe("Original"); // unchanged
    });

    test("version starts at 1", async () => {
      const assistant = await store.create({ graph_id: "agent" });
      expect(assistant.version).toBe(1);
    });

    test("created_at is a valid ISO 8601 string ending in Z", async () => {
      const assistant = await store.create({ graph_id: "agent" });
      expect(assistant.created_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}Z$/);
    });
  });

  // -------------------------------------------------------------------------
  // get
  // -------------------------------------------------------------------------

  describe("get", () => {
    test("returns assistant by ID", async () => {
      const created = await store.create({
        graph_id: "agent",
        name: "Getter",
      });
      const fetched = await store.get(created.assistant_id);
      expect(fetched).not.toBeNull();
      expect(fetched!.assistant_id).toBe(created.assistant_id);
      expect(fetched!.name).toBe("Getter");
    });

    test("returns null for non-existent ID", async () => {
      const result = await store.get(crypto.randomUUID());
      expect(result).toBeNull();
    });
  });

  // -------------------------------------------------------------------------
  // update
  // -------------------------------------------------------------------------

  describe("update", () => {
    test("updates simple fields", async () => {
      const assistant = await store.create({
        graph_id: "agent",
        name: "Before",
      });
      const updated = await store.update(assistant.assistant_id, {
        name: "After",
        graph_id: "research_agent",
      });

      expect(updated).not.toBeNull();
      expect(updated!.name).toBe("After");
      expect(updated!.graph_id).toBe("research_agent");
    });

    test("increments version on each update", async () => {
      const assistant = await store.create({ graph_id: "agent" });
      expect(assistant.version).toBe(1);

      const v2 = await store.update(assistant.assistant_id, { name: "v2" });
      expect(v2!.version).toBe(2);

      const v3 = await store.update(assistant.assistant_id, { name: "v3" });
      expect(v3!.version).toBe(3);
    });

    test("shallow-merges metadata", async () => {
      const assistant = await store.create({
        graph_id: "agent",
        metadata: { a: 1, b: 2 },
      });
      const updated = await store.update(assistant.assistant_id, {
        metadata: { b: 99, c: 3 },
      });

      expect(updated!.metadata).toEqual({ a: 1, b: 99, c: 3 });
    });

    test("updates updated_at timestamp", async () => {
      const assistant = await store.create({ graph_id: "agent" });
      // Small delay to ensure different timestamp
      await Bun.sleep(5);
      const updated = await store.update(assistant.assistant_id, {
        name: "Updated",
      });

      expect(updated!.updated_at).not.toBe(assistant.created_at);
    });

    test("returns null for non-existent ID", async () => {
      const result = await store.update(crypto.randomUUID(), {
        name: "nope",
      });
      expect(result).toBeNull();
    });

    test("does not change assistant_id or created_at", async () => {
      const assistant = await store.create({ graph_id: "agent" });
      const updated = await store.update(assistant.assistant_id, {
        name: "Changed",
      });
      expect(updated!.assistant_id).toBe(assistant.assistant_id);
      expect(updated!.created_at).toBe(assistant.created_at);
    });

    test("skips undefined fields (partial update)", async () => {
      const assistant = await store.create({
        graph_id: "agent",
        name: "Original",
        description: "Keep me",
      });
      const updated = await store.update(assistant.assistant_id, {
        name: "Changed",
        // description is NOT in the patch → should stay "Keep me"
      });

      expect(updated!.name).toBe("Changed");
      expect(updated!.description).toBe("Keep me");
    });
  });

  // -------------------------------------------------------------------------
  // delete
  // -------------------------------------------------------------------------

  describe("delete", () => {
    test("deletes an existing assistant", async () => {
      const assistant = await store.create({ graph_id: "agent" });
      const deleted = await store.delete(assistant.assistant_id);
      expect(deleted).toBe(true);

      const fetched = await store.get(assistant.assistant_id);
      expect(fetched).toBeNull();
    });

    test("returns false for non-existent ID", async () => {
      const deleted = await store.delete(crypto.randomUUID());
      expect(deleted).toBe(false);
    });
  });

  // -------------------------------------------------------------------------
  // search
  // -------------------------------------------------------------------------

  describe("search", () => {
    beforeEach(async () => {
      await store.create({
        graph_id: "agent",
        name: "Alpha",
        metadata: { env: "prod", tier: "premium" },
      });
      await store.create({
        graph_id: "agent",
        name: "Beta",
        metadata: { env: "staging" },
      });
      await store.create({
        graph_id: "research_agent",
        name: "Gamma Research",
        metadata: { env: "prod" },
      });
    });

    test("returns all with empty request", async () => {
      const results = await store.search({});
      expect(results.length).toBe(3);
    });

    test("filters by graph_id", async () => {
      const results = await store.search({ graph_id: "research_agent" });
      expect(results.length).toBe(1);
      expect(results[0].name).toBe("Gamma Research");
    });

    test("filters by metadata", async () => {
      const results = await store.search({
        metadata: { env: "prod" },
      });
      expect(results.length).toBe(2);
    });

    test("filters by metadata with multiple keys", async () => {
      const results = await store.search({
        metadata: { env: "prod", tier: "premium" },
      });
      expect(results.length).toBe(1);
      expect(results[0].name).toBe("Alpha");
    });

    test("filters by name (case-insensitive partial match)", async () => {
      const results = await store.search({ name: "alpha" });
      expect(results.length).toBe(1);
      expect(results[0].name).toBe("Alpha");
    });

    test("filters by name partial match", async () => {
      const results = await store.search({ name: "Research" });
      expect(results.length).toBe(1);
      expect(results[0].name).toBe("Gamma Research");
    });

    test("combines multiple filters", async () => {
      const results = await store.search({
        graph_id: "agent",
        metadata: { env: "prod" },
      });
      expect(results.length).toBe(1);
      expect(results[0].name).toBe("Alpha");
    });

    test("applies limit", async () => {
      const results = await store.search({ limit: 2 });
      expect(results.length).toBe(2);
    });

    test("applies offset", async () => {
      const all = await store.search({ sort_by: "name", sort_order: "asc" });
      const offset = await store.search({
        sort_by: "name",
        sort_order: "asc",
        offset: 1,
      });
      expect(offset.length).toBe(2);
      expect(offset[0].name).toBe(all[1].name);
    });

    test("applies limit + offset together", async () => {
      const results = await store.search({
        sort_by: "name",
        sort_order: "asc",
        limit: 1,
        offset: 1,
      });
      expect(results.length).toBe(1);
      expect(results[0].name).toBe("Beta");
    });

    test("sorts by name ascending", async () => {
      const results = await store.search({
        sort_by: "name",
        sort_order: "asc",
      });
      expect(results[0].name).toBe("Alpha");
      expect(results[1].name).toBe("Beta");
      expect(results[2].name).toBe("Gamma Research");
    });

    test("sorts by name descending", async () => {
      const results = await store.search({
        sort_by: "name",
        sort_order: "desc",
      });
      expect(results[0].name).toBe("Gamma Research");
      expect(results[1].name).toBe("Beta");
      expect(results[2].name).toBe("Alpha");
    });

    test("default sort is created_at descending (non-increasing order)", async () => {
      const results = await store.search({});
      // Verify created_at is in non-increasing order (descending)
      for (let i = 0; i < results.length - 1; i++) {
        expect(results[i].created_at >= results[i + 1].created_at).toBe(true);
      }
    });

    test("returns empty array when no matches", async () => {
      const results = await store.search({ graph_id: "nonexistent" });
      expect(results).toEqual([]);
    });

    test("default limit is 10", async () => {
      // Create 15 assistants total (3 already from beforeEach)
      for (let i = 0; i < 12; i++) {
        await store.create({ graph_id: "agent", name: `Extra-${i}` });
      }
      const results = await store.search({});
      expect(results.length).toBe(10);
    });
  });

  // -------------------------------------------------------------------------
  // count
  // -------------------------------------------------------------------------

  describe("count", () => {
    beforeEach(async () => {
      await store.create({
        graph_id: "agent",
        name: "One",
        metadata: { env: "prod" },
      });
      await store.create({
        graph_id: "agent",
        name: "Two",
        metadata: { env: "staging" },
      });
      await store.create({
        graph_id: "research_agent",
        name: "Three",
        metadata: { env: "prod" },
      });
    });

    test("counts all with no filters", async () => {
      expect(await store.count()).toBe(3);
    });

    test("counts with graph_id filter", async () => {
      expect(await store.count({ graph_id: "agent" })).toBe(2);
    });

    test("counts with metadata filter", async () => {
      expect(await store.count({ metadata: { env: "prod" } })).toBe(2);
    });

    test("counts with name filter", async () => {
      expect(await store.count({ name: "Two" })).toBe(1);
    });

    test("returns 0 for no matches", async () => {
      expect(await store.count({ graph_id: "nonexistent" })).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // clear
  // -------------------------------------------------------------------------

  describe("clear", () => {
    test("removes all assistants", async () => {
      await store.create({ graph_id: "agent" });
      await store.create({ graph_id: "agent" });
      expect(await store.count()).toBe(2);

      await store.clear();
      expect(await store.count()).toBe(0);
    });
  });
});

// ===========================================================================
// InMemoryThreadStore
// ===========================================================================

describe("InMemoryThreadStore", () => {
  let store: InMemoryThreadStore;

  beforeEach(() => {
    store = new InMemoryThreadStore();
  });

  // -------------------------------------------------------------------------
  // create
  // -------------------------------------------------------------------------

  describe("create", () => {
    test("creates a thread with defaults", async () => {
      const thread = await store.create({});

      expect(thread.thread_id).toBeDefined();
      expect(thread.thread_id.length).toBeGreaterThan(0);
      expect(thread.status).toBe("idle");
      expect(thread.metadata).toEqual({});
      expect(thread.created_at).toBeDefined();
      expect(thread.updated_at).toBeDefined();
    });

    test("creates with explicit thread_id", async () => {
      const id = crypto.randomUUID();
      const thread = await store.create({ thread_id: id });
      expect(thread.thread_id).toBe(id);
    });

    test("creates with metadata", async () => {
      const thread = await store.create({
        metadata: { session: "abc" },
      });
      expect(thread.metadata).toEqual({ session: "abc" });
    });

    test("throws on duplicate with if_exists=raise (default)", async () => {
      const id = crypto.randomUUID();
      await store.create({ thread_id: id });
      await expect(store.create({ thread_id: id })).rejects.toThrow(
        `Thread ${id} already exists`,
      );
    });

    test("returns existing on duplicate with if_exists=do_nothing", async () => {
      const id = crypto.randomUUID();
      const original = await store.create({
        thread_id: id,
        metadata: { original: true },
      });
      const duplicate = await store.create({
        thread_id: id,
        metadata: { duplicate: true },
        if_exists: "do_nothing",
      });
      expect(duplicate.metadata).toEqual({ original: true });
    });

    test("created_at is a valid ISO 8601 string ending in Z", async () => {
      const thread = await store.create({});
      expect(thread.created_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}Z$/);
    });
  });

  // -------------------------------------------------------------------------
  // get
  // -------------------------------------------------------------------------

  describe("get", () => {
    test("returns thread by ID", async () => {
      const created = await store.create({ metadata: { key: "value" } });
      const fetched = await store.get(created.thread_id);
      expect(fetched).not.toBeNull();
      expect(fetched!.thread_id).toBe(created.thread_id);
      expect(fetched!.metadata).toEqual({ key: "value" });
    });

    test("returns null for non-existent ID", async () => {
      expect(await store.get(crypto.randomUUID())).toBeNull();
    });
  });

  // -------------------------------------------------------------------------
  // update
  // -------------------------------------------------------------------------

  describe("update", () => {
    test("shallow-merges metadata", async () => {
      const thread = await store.create({
        metadata: { a: 1, b: 2 },
      });
      const updated = await store.update(thread.thread_id, {
        metadata: { b: 99, c: 3 },
      });
      expect(updated!.metadata).toEqual({ a: 1, b: 99, c: 3 });
    });

    test("updates updated_at timestamp", async () => {
      const thread = await store.create({});
      await Bun.sleep(5);
      const updated = await store.update(thread.thread_id, {
        metadata: { updated: true },
      });
      expect(updated!.updated_at).not.toBe(thread.created_at);
    });

    test("returns null for non-existent ID", async () => {
      expect(
        await store.update(crypto.randomUUID(), { metadata: {} }),
      ).toBeNull();
    });

    test("preserves other fields when updating metadata", async () => {
      const thread = await store.create({ metadata: { x: 1 } });
      const updated = await store.update(thread.thread_id, {
        metadata: { y: 2 },
      });
      expect(updated!.status).toBe("idle");
      expect(updated!.thread_id).toBe(thread.thread_id);
      expect(updated!.created_at).toBe(thread.created_at);
    });
  });

  // -------------------------------------------------------------------------
  // delete
  // -------------------------------------------------------------------------

  describe("delete", () => {
    test("deletes an existing thread", async () => {
      const thread = await store.create({});
      expect(await store.delete(thread.thread_id)).toBe(true);
      expect(await store.get(thread.thread_id)).toBeNull();
    });

    test("returns false for non-existent ID", async () => {
      expect(await store.delete(crypto.randomUUID())).toBe(false);
    });

    test("also removes state history", async () => {
      const thread = await store.create({});
      await store.addStateSnapshot(thread.thread_id, {
        values: { messages: ["hello"] },
      });

      expect(await store.delete(thread.thread_id)).toBe(true);

      // History should be gone — getHistory returns null because thread doesn't exist
      expect(await store.getHistory(thread.thread_id)).toBeNull();
    });
  });

  // -------------------------------------------------------------------------
  // search
  // -------------------------------------------------------------------------

  describe("search", () => {
    let threadIdA: string;
    let threadIdB: string;
    let threadIdC: string;

    beforeEach(async () => {
      const a = await store.create({ metadata: { env: "prod", role: "chat" } });
      const b = await store.create({ metadata: { env: "staging" } });
      const c = await store.create({ metadata: { env: "prod" } });
      threadIdA = a.thread_id;
      threadIdB = b.thread_id;
      threadIdC = c.thread_id;
    });

    test("returns all with empty request", async () => {
      const results = await store.search({});
      expect(results.length).toBe(3);
    });

    test("filters by metadata", async () => {
      const results = await store.search({
        metadata: { env: "prod" },
      });
      expect(results.length).toBe(2);
    });

    test("filters by IDs", async () => {
      const results = await store.search({
        ids: [threadIdA, threadIdC],
      });
      expect(results.length).toBe(2);
    });

    test("filters by status", async () => {
      const results = await store.search({ status: "idle" });
      expect(results.length).toBe(3);

      const results2 = await store.search({ status: "busy" });
      expect(results2.length).toBe(0);
    });

    test("applies limit and offset", async () => {
      const page1 = await store.search({ limit: 2, offset: 0 });
      expect(page1.length).toBe(2);

      const page2 = await store.search({ limit: 2, offset: 2 });
      expect(page2.length).toBe(1);
    });

    test("sorts by created_at ascending", async () => {
      const results = await store.search({
        sort_by: "created_at",
        sort_order: "asc",
      });
      expect(results[0].thread_id).toBe(threadIdA);
    });

    test("default sort is created_at descending (non-increasing order)", async () => {
      const results = await store.search({});
      // Verify created_at is in non-increasing order (descending)
      for (let i = 0; i < results.length - 1; i++) {
        expect(results[i].created_at >= results[i + 1].created_at).toBe(true);
      }
    });

    test("returns empty array when no matches", async () => {
      expect(
        await store.search({ metadata: { nonexistent: true } }),
      ).toEqual([]);
    });
  });

  // -------------------------------------------------------------------------
  // count
  // -------------------------------------------------------------------------

  describe("count", () => {
    beforeEach(async () => {
      await store.create({ metadata: { env: "prod" } });
      await store.create({ metadata: { env: "staging" } });
      await store.create({ metadata: { env: "prod" } });
    });

    test("counts all with no filters", async () => {
      expect(await store.count()).toBe(3);
    });

    test("counts with metadata filter", async () => {
      expect(await store.count({ metadata: { env: "prod" } })).toBe(2);
    });

    test("counts with status filter", async () => {
      expect(await store.count({ status: "idle" })).toBe(3);
      expect(await store.count({ status: "busy" })).toBe(0);
    });

    test("returns 0 for no matches", async () => {
      expect(await store.count({ metadata: { x: 1 } })).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // getState
  // -------------------------------------------------------------------------

  describe("getState", () => {
    test("returns state for an existing thread", async () => {
      const thread = await store.create({});
      const state = await store.getState(thread.thread_id);

      expect(state).not.toBeNull();
      expect(state!.values).toEqual({});
      expect(state!.next).toEqual([]);
      expect(state!.tasks).toEqual([]);
      expect(state!.checkpoint).toBeDefined();
      expect(state!.checkpoint!.thread_id).toBe(thread.thread_id);
      expect(state!.checkpoint!.checkpoint_ns).toBe("");
      expect(state!.checkpoint!.checkpoint_id).toBeDefined();
      expect(state!.metadata).toEqual({});
      expect(state!.created_at).toBeDefined();
      expect(state!.interrupts).toEqual([]);
    });

    test("returns null for non-existent thread", async () => {
      expect(await store.getState(crypto.randomUUID())).toBeNull();
    });

    test("reflects current values after state snapshot", async () => {
      const thread = await store.create({});
      await store.addStateSnapshot(thread.thread_id, {
        values: { messages: [{ role: "user", content: "hi" }] },
      });

      const state = await store.getState(thread.thread_id);
      expect(state!.values).toEqual({
        messages: [{ role: "user", content: "hi" }],
      });
    });
  });

  // -------------------------------------------------------------------------
  // addStateSnapshot
  // -------------------------------------------------------------------------

  describe("addStateSnapshot", () => {
    test("adds a snapshot and returns true", async () => {
      const thread = await store.create({});
      const result = await store.addStateSnapshot(thread.thread_id, {
        values: { count: 1 },
      });
      expect(result).toBe(true);
    });

    test("returns false for non-existent thread", async () => {
      const result = await store.addStateSnapshot(crypto.randomUUID(), {
        values: { count: 1 },
      });
      expect(result).toBe(false);
    });

    test("updates thread values and updated_at", async () => {
      const thread = await store.create({});
      await Bun.sleep(5);
      await store.addStateSnapshot(thread.thread_id, {
        values: { count: 42 },
      });

      const updated = await store.get(thread.thread_id);
      expect(updated!.values).toEqual({ count: 42 });
      // updated_at should be later than created_at
      expect(new Date(updated!.updated_at).getTime()).toBeGreaterThanOrEqual(
        new Date(thread.created_at).getTime(),
      );
    });

    test("assigns a checkpoint_id to each snapshot", async () => {
      const thread = await store.create({});
      await store.addStateSnapshot(thread.thread_id, { values: { step: 1 } });
      await store.addStateSnapshot(thread.thread_id, { values: { step: 2 } });

      const history = await store.getHistory(thread.thread_id);
      expect(history!.length).toBe(2);
      expect(history![0].checkpoint!.checkpoint_id).toBeDefined();
      expect(history![1].checkpoint!.checkpoint_id).toBeDefined();
      expect(history![0].checkpoint!.checkpoint_id).not.toBe(
        history![1].checkpoint!.checkpoint_id,
      );
    });
  });

  // -------------------------------------------------------------------------
  // getHistory
  // -------------------------------------------------------------------------

  describe("getHistory", () => {
    test("returns null for non-existent thread", async () => {
      expect(await store.getHistory(crypto.randomUUID())).toBeNull();
    });

    test("returns empty array for thread with no snapshots", async () => {
      const thread = await store.create({});
      const history = await store.getHistory(thread.thread_id);
      expect(history).toEqual([]);
    });

    test("returns snapshots in reverse chronological order", async () => {
      const thread = await store.create({});
      await store.addStateSnapshot(thread.thread_id, { values: { step: 1 } });
      await store.addStateSnapshot(thread.thread_id, { values: { step: 2 } });
      await store.addStateSnapshot(thread.thread_id, { values: { step: 3 } });

      const history = await store.getHistory(thread.thread_id);
      expect(history!.length).toBe(3);
      expect(history![0].values).toEqual({ step: 3 }); // most recent first
      expect(history![1].values).toEqual({ step: 2 });
      expect(history![2].values).toEqual({ step: 1 });
    });

    test("respects limit parameter", async () => {
      const thread = await store.create({});
      for (let i = 1; i <= 5; i++) {
        await store.addStateSnapshot(thread.thread_id, { values: { step: i } });
      }

      const history = await store.getHistory(thread.thread_id, 2);
      expect(history!.length).toBe(2);
      expect(history![0].values).toEqual({ step: 5 });
      expect(history![1].values).toEqual({ step: 4 });
    });

    test("default limit is 10", async () => {
      const thread = await store.create({});
      for (let i = 1; i <= 15; i++) {
        await store.addStateSnapshot(thread.thread_id, { values: { step: i } });
      }

      const history = await store.getHistory(thread.thread_id);
      expect(history!.length).toBe(10);
    });

    test("filters with before parameter", async () => {
      const thread = await store.create({});
      await store.addStateSnapshot(thread.thread_id, { values: { step: 1 } });
      await store.addStateSnapshot(thread.thread_id, { values: { step: 2 } });
      await store.addStateSnapshot(thread.thread_id, { values: { step: 3 } });

      // Get the checkpoint_id of step 3 (most recent)
      const allHistory = await store.getHistory(thread.thread_id);
      const step3CheckpointId = allHistory![0].checkpoint!.checkpoint_id as string;

      // Get history before step 3
      const history = await store.getHistory(
        thread.thread_id,
        10,
        step3CheckpointId,
      );
      expect(history!.length).toBe(2);
      expect(history![0].values).toEqual({ step: 2 });
      expect(history![1].values).toEqual({ step: 1 });
    });

    test("snapshots have ThreadState shape", async () => {
      const thread = await store.create({});
      await store.addStateSnapshot(thread.thread_id, {
        values: { messages: ["hi"] },
        next: ["agent"],
        tasks: [{ id: "t1" }],
        metadata: { custom: true },
        interrupts: [{ type: "human" }],
      });

      const history = await store.getHistory(thread.thread_id);
      const snapshot = history![0];

      expect(snapshot.values).toEqual({ messages: ["hi"] });
      expect(snapshot.next).toEqual(["agent"]);
      expect(snapshot.tasks).toEqual([{ id: "t1" }]);
      expect(snapshot.metadata).toEqual({ custom: true });
      expect(snapshot.interrupts).toEqual([{ type: "human" }]);
      expect(snapshot.checkpoint).toBeDefined();
      expect(snapshot.checkpoint!.thread_id).toBe(thread.thread_id);
      expect(snapshot.created_at).toBeDefined();
    });
  });

  // -------------------------------------------------------------------------
  // clear
  // -------------------------------------------------------------------------

  describe("clear", () => {
    test("removes all threads and history", async () => {
      const thread = await store.create({});
      await store.addStateSnapshot(thread.thread_id, { values: { x: 1 } });

      await store.clear();

      expect(await store.count()).toBe(0);
      expect(await store.getHistory(thread.thread_id)).toBeNull();
    });
  });
});

// ===========================================================================
// InMemoryRunStore
// ===========================================================================

describe("InMemoryRunStore", () => {
  let store: InMemoryRunStore;
  const threadId = "thread-001";
  const assistantId = "assistant-001";

  beforeEach(() => {
    store = new InMemoryRunStore();
  });

  // -------------------------------------------------------------------------
  // create
  // -------------------------------------------------------------------------

  describe("create", () => {
    test("creates a run with required fields", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });

      expect(run.run_id).toBeDefined();
      expect(run.thread_id).toBe(threadId);
      expect(run.assistant_id).toBe(assistantId);
      expect(run.status).toBe("pending");
      expect(run.metadata).toEqual({});
      expect(run.created_at).toBeDefined();
      expect(run.updated_at).toBeDefined();
    });

    test("creates with explicit status", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "running",
      });
      expect(run.status).toBe("running");
    });

    test("creates with metadata and kwargs", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        metadata: { source: "api" },
        kwargs: { input: { message: "hi" } },
      });
      expect(run.metadata).toEqual({ source: "api" });
      expect(run.kwargs).toEqual({ input: { message: "hi" } });
    });

    test("creates with multitask_strategy", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        multitask_strategy: "enqueue",
      });
      expect(run.multitask_strategy).toBe("enqueue");
    });

    test("default multitask_strategy is reject", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      expect(run.multitask_strategy).toBe("reject");
    });

    test("throws if thread_id is missing", async () => {
      await expect(
        store.create({ thread_id: "", assistant_id: assistantId }),
      ).rejects.toThrow("thread_id is required");
    });

    test("throws if assistant_id is missing", async () => {
      await expect(
        store.create({ thread_id: threadId, assistant_id: "" }),
      ).rejects.toThrow("assistant_id is required");
    });

    test("generates unique run IDs", async () => {
      const run1 = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      const run2 = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      expect(run1.run_id).not.toBe(run2.run_id);
    });

    test("created_at is a valid ISO 8601 string", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      expect(run.created_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}Z$/);
    });
  });

  // -------------------------------------------------------------------------
  // get
  // -------------------------------------------------------------------------

  describe("get", () => {
    test("returns run by ID", async () => {
      const created = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      const fetched = await store.get(created.run_id);
      expect(fetched).not.toBeNull();
      expect(fetched!.run_id).toBe(created.run_id);
    });

    test("returns null for non-existent ID", async () => {
      expect(await store.get(crypto.randomUUID())).toBeNull();
    });
  });

  // -------------------------------------------------------------------------
  // listByThread
  // -------------------------------------------------------------------------

  describe("listByThread", () => {
    const threadId2 = "thread-002";

    beforeEach(async () => {
      // Create runs on two different threads with slight delays so created_at differs
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "success",
        metadata: { order: 1 },
      });
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "pending",
        metadata: { order: 2 },
      });
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "error",
        metadata: { order: 3 },
      });
      // Different thread
      await store.create({
        thread_id: threadId2,
        assistant_id: assistantId,
      });
    });

    test("returns only runs for the specified thread", async () => {
      const runs = await store.listByThread(threadId);
      expect(runs.length).toBe(3);
      for (const run of runs) {
        expect(run.thread_id).toBe(threadId);
      }
    });

    test("returns runs sorted by created_at descending", async () => {
      const runs = await store.listByThread(threadId, 10);
      // Most recent first — the last created should have the latest created_at
      for (let i = 0; i < runs.length - 1; i++) {
        expect(runs[i].created_at >= runs[i + 1].created_at).toBe(true);
      }
    });

    test("filters by status", async () => {
      const pending = await store.listByThread(threadId, 10, 0, "pending");
      expect(pending.length).toBe(1);
      expect(pending[0].status).toBe("pending");

      const errors = await store.listByThread(threadId, 10, 0, "error");
      expect(errors.length).toBe(1);
    });

    test("applies limit", async () => {
      const runs = await store.listByThread(threadId, 2);
      expect(runs.length).toBe(2);
    });

    test("applies offset", async () => {
      const all = await store.listByThread(threadId, 10);
      const offset = await store.listByThread(threadId, 10, 1);
      expect(offset.length).toBe(2);
      expect(offset[0].run_id).toBe(all[1].run_id);
    });

    test("returns empty array for thread with no runs", async () => {
      const runs = await store.listByThread("nonexistent-thread");
      expect(runs).toEqual([]);
    });
  });

  // -------------------------------------------------------------------------
  // getByThread
  // -------------------------------------------------------------------------

  describe("getByThread", () => {
    test("returns run if it belongs to the thread", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      const fetched = await store.getByThread(threadId, run.run_id);
      expect(fetched).not.toBeNull();
      expect(fetched!.run_id).toBe(run.run_id);
    });

    test("returns null if run belongs to different thread", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      const fetched = await store.getByThread("other-thread", run.run_id);
      expect(fetched).toBeNull();
    });

    test("returns null for non-existent run", async () => {
      expect(
        await store.getByThread(threadId, crypto.randomUUID()),
      ).toBeNull();
    });
  });

  // -------------------------------------------------------------------------
  // deleteByThread
  // -------------------------------------------------------------------------

  describe("deleteByThread", () => {
    test("deletes run that belongs to the thread", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      expect(await store.deleteByThread(threadId, run.run_id)).toBe(true);
      expect(await store.get(run.run_id)).toBeNull();
    });

    test("refuses to delete run from different thread", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      expect(await store.deleteByThread("other-thread", run.run_id)).toBe(
        false,
      );
      // Run still exists
      expect(await store.get(run.run_id)).not.toBeNull();
    });

    test("returns false for non-existent run", async () => {
      expect(
        await store.deleteByThread(threadId, crypto.randomUUID()),
      ).toBe(false);
    });
  });

  // -------------------------------------------------------------------------
  // getActiveRun
  // -------------------------------------------------------------------------

  describe("getActiveRun", () => {
    test("returns pending run", async () => {
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "pending",
      });
      const active = await store.getActiveRun(threadId);
      expect(active).not.toBeNull();
      expect(active!.status).toBe("pending");
    });

    test("returns running run", async () => {
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "running",
      });
      const active = await store.getActiveRun(threadId);
      expect(active).not.toBeNull();
      expect(active!.status).toBe("running");
    });

    test("does not return completed runs", async () => {
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "success",
      });
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "error",
      });
      expect(await store.getActiveRun(threadId)).toBeNull();
    });

    test("returns null for thread with no runs", async () => {
      expect(await store.getActiveRun(threadId)).toBeNull();
    });

    test("returns first active run found (pending takes priority if iterated first)", async () => {
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "success",
      });
      const pendingRun = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
        status: "pending",
      });
      const active = await store.getActiveRun(threadId);
      expect(active).not.toBeNull();
      expect(active!.run_id).toBe(pendingRun.run_id);
    });
  });

  // -------------------------------------------------------------------------
  // updateStatus
  // -------------------------------------------------------------------------

  describe("updateStatus", () => {
    test("updates run status", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      expect(run.status).toBe("pending");

      const updated = await store.updateStatus(run.run_id, "running");
      expect(updated).not.toBeNull();
      expect(updated!.status).toBe("running");
    });

    test("updates updated_at timestamp", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      await Bun.sleep(5);
      const updated = await store.updateStatus(run.run_id, "success");
      expect(updated!.updated_at).not.toBe(run.created_at);
    });

    test("returns null for non-existent run", async () => {
      expect(
        await store.updateStatus(crypto.randomUUID(), "success"),
      ).toBeNull();
    });

    test("transitions through all valid statuses", async () => {
      const run = await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });

      const statuses: RunStatus[] = [
        "running",
        "success",
        "error",
        "timeout",
        "interrupted",
      ];
      for (const status of statuses) {
        const updated = await store.updateStatus(run.run_id, status);
        expect(updated!.status).toBe(status);
      }
    });
  });

  // -------------------------------------------------------------------------
  // countByThread
  // -------------------------------------------------------------------------

  describe("countByThread", () => {
    test("counts runs for a specific thread", async () => {
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      await store.create({
        thread_id: "other-thread",
        assistant_id: assistantId,
      });

      expect(await store.countByThread(threadId)).toBe(2);
      expect(await store.countByThread("other-thread")).toBe(1);
      expect(await store.countByThread("nonexistent")).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // clear
  // -------------------------------------------------------------------------

  describe("clear", () => {
    test("removes all runs", async () => {
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });
      await store.create({
        thread_id: threadId,
        assistant_id: assistantId,
      });

      await store.clear();
      expect(await store.countByThread(threadId)).toBe(0);
    });
  });
});

// ===========================================================================
// InMemoryStorage (container)
// ===========================================================================

describe("InMemoryStorage", () => {
  test("exposes all three stores", () => {
    const storage = new InMemoryStorage();
    expect(storage.assistants).toBeDefined();
    expect(storage.threads).toBeDefined();
    expect(storage.runs).toBeDefined();
  });

  test("clearAll empties all stores", async () => {
    const storage = new InMemoryStorage();

    await storage.assistants.create({ graph_id: "agent" });
    await storage.threads.create({});
    await storage.runs.create({
      thread_id: "t1",
      assistant_id: "a1",
    });

    expect(await storage.assistants.count()).toBe(1);
    expect(await storage.threads.count()).toBe(1);
    expect(await storage.runs.countByThread("t1")).toBe(1);

    await storage.clearAll();

    expect(await storage.assistants.count()).toBe(0);
    expect(await storage.threads.count()).toBe(0);
    expect(await storage.runs.countByThread("t1")).toBe(0);
  });

  test("stores are independent instances", async () => {
    const storage = new InMemoryStorage();
    await storage.assistants.create({ graph_id: "agent" });
    expect(await storage.assistants.count()).toBe(1);
    expect(await storage.threads.count()).toBe(0);
  });
});

// ===========================================================================
// getStorage / resetStorage singleton
// ===========================================================================

describe("getStorage / resetStorage", () => {
  beforeEach(() => {
    resetStorage();
  });

  test("returns a Storage instance", () => {
    const storage = getStorage();
    expect(storage).toBeDefined();
    expect(storage.assistants).toBeDefined();
    expect(storage.threads).toBeDefined();
    expect(storage.runs).toBeDefined();
  });

  test("returns the same instance on repeated calls (singleton)", () => {
    const first = getStorage();
    const second = getStorage();
    expect(first).toBe(second);
  });

  test("resetStorage causes a new instance on next call", () => {
    const first = getStorage();
    resetStorage();
    const second = getStorage();
    expect(first).not.toBe(second);
  });

  test("new instance after reset has empty stores", async () => {
    const storage = getStorage();
    await storage.assistants.create({ graph_id: "agent" });
    expect(await storage.assistants.count()).toBe(1);

    resetStorage();
    const fresh = getStorage();
    expect(await fresh.assistants.count()).toBe(0);
  });

  test("old reference retains data after reset", async () => {
    const old = getStorage();
    await old.assistants.create({ graph_id: "agent" });

    resetStorage();

    // Old ref still has its data
    expect(await old.assistants.count()).toBe(1);
    // New instance is empty
    expect(await getStorage().assistants.count()).toBe(0);
  });
});

// ===========================================================================
// Edge cases & cross-cutting concerns
// ===========================================================================

describe("cross-cutting edge cases", () => {
  test("UUID format: assistant IDs contain dashes", async () => {
    const store = new InMemoryAssistantStore();
    const assistant = await store.create({ graph_id: "agent" });
    // crypto.randomUUID() produces "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    expect(assistant.assistant_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
  });

  test("UUID format: thread IDs contain dashes", async () => {
    const store = new InMemoryThreadStore();
    const thread = await store.create({});
    expect(thread.thread_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
  });

  test("UUID format: run IDs contain dashes", async () => {
    const store = new InMemoryRunStore();
    const run = await store.create({
      thread_id: "t",
      assistant_id: "a",
    });
    expect(run.run_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
  });

  test("metadata with nested objects is compared correctly", async () => {
    const store = new InMemoryAssistantStore();
    await store.create({
      graph_id: "agent",
      metadata: { nested: { key: "value" } },
    });
    await store.create({
      graph_id: "agent",
      metadata: { nested: { key: "other" } },
    });

    const results = await store.search({
      metadata: { nested: { key: "value" } },
    });
    expect(results.length).toBe(1);
  });

  test("empty search returns results respecting default limit", async () => {
    const store = new InMemoryAssistantStore();
    for (let i = 0; i < 12; i++) {
      await store.create({ graph_id: "agent", name: `A-${i}` });
    }
    const results = await store.search({});
    expect(results.length).toBe(10); // default limit
  });

  test("search with offset beyond data returns empty", async () => {
    const store = new InMemoryAssistantStore();
    await store.create({ graph_id: "agent" });
    const results = await store.search({ offset: 100 });
    expect(results).toEqual([]);
  });

  test("search with limit 0 returns empty", async () => {
    const store = new InMemoryAssistantStore();
    await store.create({ graph_id: "agent" });
    const results = await store.search({ limit: 0 });
    expect(results).toEqual([]);
  });

  test("thread values filter works in search", async () => {
    const store = new InMemoryThreadStore();
    const t1 = await store.create({});
    const t2 = await store.create({});

    // Manually add state to update values
    await store.addStateSnapshot(t1.thread_id, {
      values: { topic: "science" },
    });
    await store.addStateSnapshot(t2.thread_id, {
      values: { topic: "art" },
    });

    const results = await store.search({
      values: { topic: "science" },
    });
    expect(results.length).toBe(1);
    expect(results[0].thread_id).toBe(t1.thread_id);
  });

  test("multiple rapid creates have monotonically non-decreasing timestamps", async () => {
    const store = new InMemoryAssistantStore();
    const assistants = [];
    for (let i = 0; i < 10; i++) {
      assistants.push(await store.create({ graph_id: "agent" }));
    }
    for (let i = 1; i < assistants.length; i++) {
      expect(
        new Date(assistants[i].created_at).getTime(),
      ).toBeGreaterThanOrEqual(
        new Date(assistants[i - 1].created_at).getTime(),
      );
    }
  });
});
