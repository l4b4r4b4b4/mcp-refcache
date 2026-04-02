/**
 * Fractal Agents Runtime — TypeScript/Bun HTTP Server (v0.0.1)
 *
 * Entrypoint for the LangGraph-compatible agent runtime. Uses Bun.serve()
 * with a pattern-matching router and graceful shutdown on SIGTERM/SIGINT.
 *
 * This file:
 *   1. Creates a Router instance.
 *   2. Registers all route modules (system routes, and later assistants,
 *      threads, runs, etc.).
 *   3. Starts the Bun HTTP server.
 *   4. Installs signal handlers for graceful shutdown.
 */

import { Router } from "./router";
import { config, VERSION, SERVICE_NAME } from "./config";
import { registerHealthRoutes } from "./routes/health";
import { registerAssistantRoutes } from "./routes/assistants";
import { registerThreadRoutes } from "./routes/threads";
import { registerRunRoutes } from "./routes/runs";
import { registerStreamRoutes } from "./routes/streams";
import { registerStatelessRunRoutes } from "./routes/runs-stateless";
import { registerStoreRoutes } from "./routes/store";
import { authMiddleware, logAuthStatus } from "./middleware/auth";
import { initializeStorage, shutdownStorage } from "./storage";

// ---------------------------------------------------------------------------
// Router setup
// ---------------------------------------------------------------------------

const router = new Router();

// Authentication middleware — must be registered before any routes.
// Verifies Supabase JWT tokens on protected endpoints.
// When Supabase is not configured, all requests pass through (graceful degradation).
router.use(authMiddleware);

// System routes: GET /, /health, /ok, /info, /openapi.json
registerHealthRoutes(router);

// Assistant routes: POST/GET/PATCH/DELETE /assistants, search, count
registerAssistantRoutes(router);

// Thread routes: POST/GET/PATCH/DELETE /threads, state, history, search, count
registerThreadRoutes(router);

// Run routes: POST/GET/DELETE /threads/:id/runs/*, cancel, join, wait
registerRunRoutes(router);

// Stream routes: POST /threads/:id/runs/stream, GET .../runs/:id/stream
registerStreamRoutes(router);

// Stateless run routes: POST /runs, /runs/stream, /runs/wait
registerStatelessRunRoutes(router);

// Store routes: PUT/GET/DELETE /store/items, POST /store/items/search, GET /store/namespaces
registerStoreRoutes(router);

// ---------------------------------------------------------------------------
// Server
// ---------------------------------------------------------------------------

let server: ReturnType<typeof Bun.serve> | undefined;

/**
 * Start the Bun HTTP server.
 *
 * Only starts when this module is the main entry point (not when imported
 * by tests). Tests can import `router` and call `router.handle()` directly.
 */
if (import.meta.main) {
  // -------------------------------------------------------------------------
  // Storage initialization (must run before serving requests)
  // -------------------------------------------------------------------------
  // Probes Postgres, runs DDL migrations, sets up LangGraph checkpoint tables.
  // Falls back to in-memory storage if DATABASE_URL is not configured.
  await initializeStorage();

  server = Bun.serve({
    port: config.port,
    fetch: (request: Request) => router.handle(request),
  });

  console.log(
    `🧬 ${SERVICE_NAME} v${VERSION} listening on http://localhost:${server.port}`,
  );
  console.log(
    `   Bun runtime:       ${Bun.version}`,
  );
  console.log(
    `   Routes registered: ${router.routeCount}`,
  );

  // Log auth configuration status
  logAuthStatus();

  // -------------------------------------------------------------------------
  // Graceful shutdown
  // -------------------------------------------------------------------------

  async function shutdown(signal: string): Promise<void> {
    console.log(`\n⏹  Received ${signal}, shutting down gracefully...`);
    if (server) {
      server.stop(true); // true = close idle connections immediately
      server = undefined;
    }

    // Close database connections and reset storage singletons
    await shutdownStorage();

    console.log("👋 Server stopped.");
    process.exit(0);
  }

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT", () => shutdown("SIGINT"));
}

// ---------------------------------------------------------------------------
// Exports (for tests and programmatic use)
// ---------------------------------------------------------------------------

export { router, server, config };
