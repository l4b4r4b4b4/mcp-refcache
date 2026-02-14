/**
 * Typed environment configuration for Fractal Agents Runtime — TypeScript/Bun.
 *
 * All configuration is read from environment variables with sensible defaults.
 * Secrets (like API keys) are never logged or exposed in error messages.
 */

/** Current runtime version. Bump on each release. */
export const VERSION = "0.0.1";

/** Service identifier used in root/info responses and logging. */
export const SERVICE_NAME = "fractal-agents-runtime-ts";

/** Runtime identifier. Always "bun" for the TypeScript runtime. */
export const RUNTIME = "bun";

/**
 * Parsed and validated environment configuration.
 *
 * Fields are read once at import time. To override in tests,
 * set environment variables before importing this module.
 */
export interface AppConfig {
  /** HTTP server port. */
  port: number;

  /** OpenAI API key. Required for agent execution, optional at startup. */
  openaiApiKey: string | undefined;

  /** Anthropic API key. Required for `anthropic:*` models. */
  anthropicApiKey: string | undefined;

  /** Google API key. Required for `google:*` models. */
  googleApiKey: string | undefined;

  /** Custom endpoint API key. Used for `custom:` models (e.g., vLLM, Ollama). */
  customApiKey: string | undefined;

  /** Default LLM model name for the ReAct agent. */
  modelName: string;

  /** PostgreSQL connection string. Enables persistent storage when set. */
  databaseUrl: string | undefined;

  /** Minimum number of connections in the database pool (default: 2). */
  databasePoolMinSize: number;

  /** Maximum number of connections in the database pool (default: 10). */
  databasePoolMaxSize: number;

  /** Database pool acquire timeout in seconds (default: 30). */
  databasePoolTimeout: number;

  /** Supabase project URL. Enables JWT authentication when set. */
  supabaseUrl: string | undefined;

  /** Supabase anon (publishable) key. Required alongside `supabaseUrl`. */
  supabaseKey: string | undefined;

  /** Supabase JWT secret for local token verification (optional — not used in v0.0.2). */
  supabaseJwtSecret: string | undefined;

  /** Git commit SHA for build metadata (set at build/deploy time). */
  buildCommit: string;

  /** Build date ISO string (set at build/deploy time). */
  buildDate: string;
}

function parsePort(raw: string | undefined, fallback: number): number {
  if (raw === undefined || raw === "") {
    return fallback;
  }
  const parsed = parseInt(raw, 10);
  if (Number.isNaN(parsed) || parsed < 0 || parsed > 65535) {
    console.warn(
      `⚠️  Invalid PORT "${raw}", falling back to ${fallback}`,
    );
    return fallback;
  }
  return parsed;
}

/**
 * Load configuration from environment variables.
 *
 * This is a function (not a top-level const) so tests can call it
 * after modifying `process.env` / `Bun.env`.
 */
export function loadConfig(): AppConfig {
  return {
    port: parsePort(process.env.PORT, 3000),
    openaiApiKey: process.env.OPENAI_API_KEY || undefined,
    anthropicApiKey: process.env.ANTHROPIC_API_KEY || undefined,
    googleApiKey: process.env.GOOGLE_API_KEY || undefined,
    customApiKey: process.env.CUSTOM_API_KEY || undefined,
    modelName: process.env.MODEL_NAME || "gpt-4o-mini",
    databaseUrl: process.env.DATABASE_URL || undefined,
    databasePoolMinSize: parsePort(process.env.DATABASE_POOL_MIN_SIZE, 2),
    databasePoolMaxSize: parsePort(process.env.DATABASE_POOL_MAX_SIZE, 10),
    databasePoolTimeout: parsePort(process.env.DATABASE_POOL_TIMEOUT, 30),
    supabaseUrl: process.env.SUPABASE_URL || undefined,
    supabaseKey: process.env.SUPABASE_KEY || undefined,
    supabaseJwtSecret: process.env.SUPABASE_JWT_SECRET || undefined,
    buildCommit: process.env.BUILD_COMMIT || "dev",
    buildDate: process.env.BUILD_DATE || new Date().toISOString(),
  };
}

/** Singleton config instance — loaded once at module init. */
export const config: AppConfig = loadConfig();

/**
 * Check whether the LLM provider is configured (API key present).
 * Used by the `/info` endpoint to report configuration status.
 */
export function isLlmConfigured(): boolean {
  return (
    (config.openaiApiKey !== undefined && config.openaiApiKey.length > 0) ||
    (config.anthropicApiKey !== undefined && config.anthropicApiKey.length > 0) ||
    (config.googleApiKey !== undefined && config.googleApiKey.length > 0)
  );
}

/**
 * Check whether Supabase is configured.
 *
 * Returns `true` when both `SUPABASE_URL` and `SUPABASE_KEY` are set,
 * indicating that JWT authentication can be enabled.
 */
export function isSupabaseConfigured(): boolean {
  return (
    config.supabaseUrl !== undefined &&
    config.supabaseUrl.length > 0 &&
    config.supabaseKey !== undefined &&
    config.supabaseKey.length > 0
  );
}

/**
 * Check whether a PostgreSQL database is configured.
 *
 * Returns `true` when `DATABASE_URL` is set, indicating that Postgres
 * persistence can be enabled.
 */
export function isDatabaseConfigured(): boolean {
  return config.databaseUrl !== undefined && config.databaseUrl.length > 0;
}

/**
 * Report current runtime capabilities.
 * Capabilities evolve across versions as features are added.
 */
export function getCapabilities(): Record<string, boolean> {
  return {
    streaming: true,
    store: false,
    crons: false,
    a2a: false,
    mcp: false,
    metrics: false,
  };
}

/**
 * Report feature tiers.
 *
 * - tier1: Core LangGraph API (assistants, threads, runs) — true in v0.0.1
 * - tier2: Auth, persistence, store, multi-provider — false until Goal 25
 * - tier3: Status string describing advanced features (MCP, A2A, tracing)
 */
export function getTiers(): { tier1: boolean; tier2: boolean; tier3: string } {
  return {
    tier1: true,
    tier2: false,
    tier3: "not_started",
  };
}
