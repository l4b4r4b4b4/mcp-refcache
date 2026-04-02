/**
 * Backends barrel — re-exports all backend interfaces and implementations.
 *
 * @module
 */

// ── Interface ────────────────────────────────────────────────────────
export type { CacheBackend } from "./types.js";

// ── Implementations ──────────────────────────────────────────────────
export { MemoryBackend } from "./memory.js";
