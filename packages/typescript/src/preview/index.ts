/**
 * Preview barrel — re-exports all generator interfaces, implementations,
 * and factory functions.
 *
 * @module
 */

// ── Interface ────────────────────────────────────────────────────────
export type { PreviewGenerator } from "./types.js";

// ── Implementations ──────────────────────────────────────────────────
export {
  getDefaultGenerator,
  PaginateGenerator,
  SampleGenerator,
  TruncateGenerator,
} from "./generators.js";
