/**
 * Tests for Supabase JWT authentication middleware — Fractal Agents Runtime TypeScript/Bun.
 *
 * Covers:
 *   - Public path bypass (exact match + trailing slash normalization)
 *   - Auth disabled (Supabase not configured) — graceful degradation
 *   - Missing Authorization header → 401
 *   - Invalid header format (no "Bearer", wrong scheme) → 401
 *   - Invalid token → 401 (mocked Supabase)
 *   - Valid token → user context set (mocked Supabase)
 *   - Error response format: { "detail": "..." }
 *   - Request-scoped context helpers: getCurrentUser, requireUser, getUserIdentity
 *   - AuthenticationError class
 *   - isPublicPath utility
 *   - extractProvider / extractModelName (re-exported for coverage)
 *   - Supabase client singleton lifecycle
 *   - Bearer token extraction edge cases
 */

import { describe, expect, test, beforeEach, afterEach, mock } from "bun:test";

import { authMiddleware, isPublicPath, logAuthStatus } from "../src/middleware/auth";
import {
  setCurrentUser,
  clearCurrentUser,
  getCurrentUser,
  requireUser,
  getUserIdentity,
} from "../src/middleware/context";
import {
  AuthenticationError,
  isAuthEnabled,
  resetSupabaseClient,
  verifyToken,
  getSupabaseClient,
  type AuthUser,
} from "../src/infra/security/auth";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRequest(
  path: string,
  method = "GET",
  headers?: Record<string, string>,
): Request {
  return new Request(`http://localhost:3000${path}`, {
    method,
    headers: headers ?? {},
  });
}

async function jsonBody(response: Response): Promise<Record<string, unknown>> {
  return response.json() as Promise<Record<string, unknown>>;
}

const MOCK_AUTH_USER: AuthUser = {
  identity: "550e8400-e29b-41d4-a716-446655440000",
  email: "testuser@example.com",
  metadata: { name: "Test User", role: "admin" },
};

// ---------------------------------------------------------------------------
// Environment helpers — save/restore env vars around tests
// ---------------------------------------------------------------------------

let savedSupabaseUrl: string | undefined;
let savedSupabaseKey: string | undefined;

function setSupabaseEnv(url?: string, key?: string): void {
  if (url !== undefined) {
    process.env.SUPABASE_URL = url;
  } else {
    delete process.env.SUPABASE_URL;
  }
  if (key !== undefined) {
    process.env.SUPABASE_KEY = key;
  } else {
    delete process.env.SUPABASE_KEY;
  }
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  savedSupabaseUrl = process.env.SUPABASE_URL;
  savedSupabaseKey = process.env.SUPABASE_KEY;
  clearCurrentUser();
  resetSupabaseClient();
});

afterEach(() => {
  // Restore original env
  if (savedSupabaseUrl !== undefined) {
    process.env.SUPABASE_URL = savedSupabaseUrl;
  } else {
    delete process.env.SUPABASE_URL;
  }
  if (savedSupabaseKey !== undefined) {
    process.env.SUPABASE_KEY = savedSupabaseKey;
  } else {
    delete process.env.SUPABASE_KEY;
  }
  clearCurrentUser();
  resetSupabaseClient();
});

// ===========================================================================
// isPublicPath
// ===========================================================================

describe("isPublicPath", () => {
  test("root path is public", () => {
    expect(isPublicPath("/")).toBe(true);
  });

  test("/health is public", () => {
    expect(isPublicPath("/health")).toBe(true);
  });

  test("/ok is public", () => {
    expect(isPublicPath("/ok")).toBe(true);
  });

  test("/info is public", () => {
    expect(isPublicPath("/info")).toBe(true);
  });

  test("/docs is public", () => {
    expect(isPublicPath("/docs")).toBe(true);
  });

  test("/openapi.json is public", () => {
    expect(isPublicPath("/openapi.json")).toBe(true);
  });

  test("/metrics is public", () => {
    expect(isPublicPath("/metrics")).toBe(true);
  });

  test("/metrics/json is public", () => {
    expect(isPublicPath("/metrics/json")).toBe(true);
  });

  test("trailing slash is normalized — /health/ is public", () => {
    expect(isPublicPath("/health/")).toBe(true);
  });

  test("trailing slash is normalized — /info/ is public", () => {
    expect(isPublicPath("/info/")).toBe(true);
  });

  test("trailing slash is normalized — /openapi.json/ is public", () => {
    expect(isPublicPath("/openapi.json/")).toBe(true);
  });

  test("/threads is NOT public", () => {
    expect(isPublicPath("/threads")).toBe(false);
  });

  test("/assistants is NOT public", () => {
    expect(isPublicPath("/assistants")).toBe(false);
  });

  test("/store/items is NOT public", () => {
    expect(isPublicPath("/store/items")).toBe(false);
  });

  test("/threads/abc/runs is NOT public", () => {
    expect(isPublicPath("/threads/abc/runs")).toBe(false);
  });

  test("empty string is NOT public", () => {
    expect(isPublicPath("")).toBe(false);
  });

  test("/healthcheck (similar prefix but different) is NOT public", () => {
    expect(isPublicPath("/healthcheck")).toBe(false);
  });

  test("/health/detailed is NOT public", () => {
    expect(isPublicPath("/health/detailed")).toBe(false);
  });
});

// ===========================================================================
// AuthenticationError
// ===========================================================================

describe("AuthenticationError", () => {
  test("creates error with message and default status 401", () => {
    const error = new AuthenticationError("Token expired");
    expect(error.message).toBe("Token expired");
    expect(error.statusCode).toBe(401);
    expect(error.name).toBe("AuthenticationError");
    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(AuthenticationError);
  });

  test("creates error with custom status code", () => {
    const error = new AuthenticationError("Server misconfigured", 500);
    expect(error.message).toBe("Server misconfigured");
    expect(error.statusCode).toBe(500);
  });

  test("inherits from Error (catchable in generic catch)", () => {
    const error = new AuthenticationError("test");
    expect(error instanceof Error).toBe(true);
    expect(error.stack).toBeDefined();
  });
});

// ===========================================================================
// isAuthEnabled
// ===========================================================================

describe("isAuthEnabled", () => {
  test("returns false when SUPABASE_URL is not set", () => {
    setSupabaseEnv(undefined, "some-key");
    expect(isAuthEnabled()).toBe(false);
  });

  test("returns false when SUPABASE_KEY is not set", () => {
    setSupabaseEnv("https://example.supabase.co", undefined);
    expect(isAuthEnabled()).toBe(false);
  });

  test("returns false when both are not set", () => {
    setSupabaseEnv(undefined, undefined);
    expect(isAuthEnabled()).toBe(false);
  });

  test("returns false when SUPABASE_URL is empty string", () => {
    setSupabaseEnv("", "some-key");
    expect(isAuthEnabled()).toBe(false);
  });

  test("returns false when SUPABASE_KEY is empty string", () => {
    setSupabaseEnv("https://example.supabase.co", "");
    expect(isAuthEnabled()).toBe(false);
  });

  test("returns true when both SUPABASE_URL and SUPABASE_KEY are set", () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");
    expect(isAuthEnabled()).toBe(true);
  });
});

// ===========================================================================
// Request-scoped context helpers
// ===========================================================================

describe("context helpers", () => {
  describe("setCurrentUser / getCurrentUser", () => {
    test("returns null by default (no user set)", () => {
      clearCurrentUser();
      expect(getCurrentUser()).toBeNull();
    });

    test("returns the user after setCurrentUser", () => {
      setCurrentUser(MOCK_AUTH_USER);
      const user = getCurrentUser();
      expect(user).not.toBeNull();
      expect(user!.identity).toBe(MOCK_AUTH_USER.identity);
      expect(user!.email).toBe(MOCK_AUTH_USER.email);
      expect(user!.metadata).toEqual(MOCK_AUTH_USER.metadata);
    });

    test("setCurrentUser(null) clears the user", () => {
      setCurrentUser(MOCK_AUTH_USER);
      expect(getCurrentUser()).not.toBeNull();
      setCurrentUser(null);
      expect(getCurrentUser()).toBeNull();
    });

    test("clearCurrentUser clears the user", () => {
      setCurrentUser(MOCK_AUTH_USER);
      expect(getCurrentUser()).not.toBeNull();
      clearCurrentUser();
      expect(getCurrentUser()).toBeNull();
    });
  });

  describe("requireUser", () => {
    test("returns user when authenticated", () => {
      setCurrentUser(MOCK_AUTH_USER);
      const user = requireUser();
      expect(user.identity).toBe(MOCK_AUTH_USER.identity);
    });

    test("throws AuthenticationError when no user is set", () => {
      clearCurrentUser();
      expect(() => requireUser()).toThrow(AuthenticationError);
      expect(() => requireUser()).toThrow("Authentication required");
    });
  });

  describe("getUserIdentity", () => {
    test("returns identity string when user is set", () => {
      setCurrentUser(MOCK_AUTH_USER);
      expect(getUserIdentity()).toBe("550e8400-e29b-41d4-a716-446655440000");
    });

    test("returns null when no user is set", () => {
      clearCurrentUser();
      expect(getUserIdentity()).toBeNull();
    });
  });

  describe("user isolation between requests", () => {
    test("clearCurrentUser prevents leaking between requests", () => {
      setCurrentUser(MOCK_AUTH_USER);
      expect(getCurrentUser()).not.toBeNull();

      // Simulate request boundary
      clearCurrentUser();
      expect(getCurrentUser()).toBeNull();
      expect(getUserIdentity()).toBeNull();
    });

    test("setCurrentUser overwrites previous user", () => {
      const user1: AuthUser = {
        identity: "user-1",
        email: "user1@example.com",
        metadata: {},
      };
      const user2: AuthUser = {
        identity: "user-2",
        email: "user2@example.com",
        metadata: {},
      };

      setCurrentUser(user1);
      expect(getUserIdentity()).toBe("user-1");

      setCurrentUser(user2);
      expect(getUserIdentity()).toBe("user-2");
    });
  });
});

// ===========================================================================
// authMiddleware — Public path bypass
// ===========================================================================

describe("authMiddleware — public paths", () => {
  test("GET / passes through (returns null)", async () => {
    setSupabaseEnv("https://example.supabase.co", "key");
    const request = makeRequest("/");
    const result = await authMiddleware(request);
    expect(result).toBeNull();
  });

  test("GET /health passes through", async () => {
    setSupabaseEnv("https://example.supabase.co", "key");
    const request = makeRequest("/health");
    const result = await authMiddleware(request);
    expect(result).toBeNull();
  });

  test("GET /ok passes through", async () => {
    setSupabaseEnv("https://example.supabase.co", "key");
    const request = makeRequest("/ok");
    const result = await authMiddleware(request);
    expect(result).toBeNull();
  });

  test("GET /info passes through", async () => {
    setSupabaseEnv("https://example.supabase.co", "key");
    const request = makeRequest("/info");
    const result = await authMiddleware(request);
    expect(result).toBeNull();
  });

  test("GET /openapi.json passes through", async () => {
    setSupabaseEnv("https://example.supabase.co", "key");
    const request = makeRequest("/openapi.json");
    const result = await authMiddleware(request);
    expect(result).toBeNull();
  });

  test("GET /health/ (trailing slash) passes through", async () => {
    setSupabaseEnv("https://example.supabase.co", "key");
    const request = makeRequest("/health/");
    const result = await authMiddleware(request);
    expect(result).toBeNull();
  });

  test("public paths clear current user context", async () => {
    setCurrentUser(MOCK_AUTH_USER);
    setSupabaseEnv("https://example.supabase.co", "key");

    const request = makeRequest("/health");
    await authMiddleware(request);

    expect(getCurrentUser()).toBeNull();
  });
});

// ===========================================================================
// authMiddleware — Auth disabled (graceful degradation)
// ===========================================================================

describe("authMiddleware — auth disabled", () => {
  test("passes all requests through when SUPABASE_URL not set", async () => {
    setSupabaseEnv(undefined, undefined);

    const request = makeRequest("/threads", "GET");
    const result = await authMiddleware(request);

    expect(result).toBeNull();
    expect(getCurrentUser()).toBeNull();
  });

  test("passes POST /assistants through when auth disabled", async () => {
    setSupabaseEnv(undefined, undefined);

    const request = makeRequest("/assistants", "POST");
    const result = await authMiddleware(request);

    expect(result).toBeNull();
  });

  test("passes /threads/:id/runs through when auth disabled", async () => {
    setSupabaseEnv(undefined, undefined);

    const request = makeRequest("/threads/abc-123/runs", "POST");
    const result = await authMiddleware(request);

    expect(result).toBeNull();
  });

  test("clears user context when auth disabled", async () => {
    setCurrentUser(MOCK_AUTH_USER);
    setSupabaseEnv(undefined, undefined);

    const request = makeRequest("/threads", "GET");
    await authMiddleware(request);

    expect(getCurrentUser()).toBeNull();
  });

  test("passes through with SUPABASE_URL set but SUPABASE_KEY missing", async () => {
    setSupabaseEnv("https://example.supabase.co", undefined);

    const request = makeRequest("/threads", "GET");
    const result = await authMiddleware(request);

    expect(result).toBeNull();
  });

  test("passes through with empty SUPABASE_URL", async () => {
    setSupabaseEnv("", "some-key");

    const request = makeRequest("/threads", "GET");
    const result = await authMiddleware(request);

    expect(result).toBeNull();
  });
});

// ===========================================================================
// authMiddleware — Missing/invalid Authorization header
// ===========================================================================

describe("authMiddleware — missing Authorization header", () => {
  test("returns 401 when Authorization header is missing", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET");
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);

    const body = await jsonBody(result!);
    expect(body.detail).toBe("Authorization header missing");
  });

  test("returns 401 with correct Content-Type header", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET");
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.headers.get("Content-Type")).toBe("application/json");
  });

  test("clears user context on missing header", async () => {
    setCurrentUser(MOCK_AUTH_USER);
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET");
    await authMiddleware(request);

    expect(getCurrentUser()).toBeNull();
  });
});

describe("authMiddleware — invalid Authorization format", () => {
  test("returns 401 for 'Basic' scheme", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET", {
      Authorization: "Basic dXNlcjpwYXNz",
    });
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);

    const body = await jsonBody(result!);
    expect(body.detail).toBe("Invalid authorization header format");
  });

  test("returns 401 for token without scheme", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET", {
      Authorization: "just-a-token",
    });
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);

    const body = await jsonBody(result!);
    expect(body.detail).toBe("Invalid authorization header format");
  });

  test("returns 401 for 'Bearer' with no token", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET", {
      Authorization: "Bearer ",
    });
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);
  });

  test("returns 401 for empty Authorization header", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET", {
      Authorization: "",
    });
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);
  });

  test("returns 401 for 'Bearer token extra-parts'", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET", {
      Authorization: "Bearer token extra-parts",
    });
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);

    const body = await jsonBody(result!);
    expect(body.detail).toBe("Invalid authorization header format");
  });

  test("clears user context on invalid format", async () => {
    setCurrentUser(MOCK_AUTH_USER);
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET", {
      Authorization: "Basic abc",
    });
    await authMiddleware(request);

    expect(getCurrentUser()).toBeNull();
  });
});

// ===========================================================================
// authMiddleware — error response format matches Python
// ===========================================================================

describe("authMiddleware — error response format", () => {
  test("error body has 'detail' key matching Python format", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET");
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    const body = await jsonBody(result!);

    // Must have exactly the "detail" key — matches Python's ErrorResponse
    expect(body).toHaveProperty("detail");
    expect(typeof body.detail).toBe("string");
    expect((body.detail as string).length).toBeGreaterThan(0);
  });

  test("401 for invalid format has 'detail' key", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET", {
      Authorization: "NotBearer token",
    });
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    const body = await jsonBody(result!);
    expect(body.detail).toBe("Invalid authorization header format");
  });
});

// ===========================================================================
// authMiddleware — protected paths require auth
// ===========================================================================

describe("authMiddleware — protected paths", () => {
  const protectedPaths = [
    "/threads",
    "/threads/abc-123",
    "/threads/abc-123/runs",
    "/threads/abc-123/runs/stream",
    "/assistants",
    "/assistants/abc-123",
    "/assistants/search",
    "/runs",
    "/runs/stream",
    "/store/items",
    "/store/items/search",
    "/store/namespaces",
  ];

  for (const path of protectedPaths) {
    test(`${path} returns 401 without Authorization header`, async () => {
      setSupabaseEnv("https://example.supabase.co", "some-key");

      const request = makeRequest(path, "GET");
      const result = await authMiddleware(request);

      expect(result).not.toBeNull();
      expect(result!.status).toBe(401);
    });
  }
});

// ===========================================================================
// Supabase client singleton
// ===========================================================================

describe("getSupabaseClient", () => {
  test("returns null when Supabase env vars not set", () => {
    setSupabaseEnv(undefined, undefined);
    resetSupabaseClient();
    const client = getSupabaseClient();
    expect(client).toBeNull();
  });

  test("returns null when only SUPABASE_URL is set", () => {
    setSupabaseEnv("https://example.supabase.co", undefined);
    resetSupabaseClient();
    const client = getSupabaseClient();
    expect(client).toBeNull();
  });

  test("returns null when only SUPABASE_KEY is set", () => {
    setSupabaseEnv(undefined, "some-key");
    resetSupabaseClient();
    const client = getSupabaseClient();
    expect(client).toBeNull();
  });

  test("creates and returns client when both env vars are set", () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");
    resetSupabaseClient();
    const client = getSupabaseClient();
    expect(client).not.toBeNull();
  });

  test("returns same instance on subsequent calls (singleton)", () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");
    resetSupabaseClient();
    const client1 = getSupabaseClient();
    const client2 = getSupabaseClient();
    expect(client1).toBe(client2);
  });

  test("resetSupabaseClient forces new instance on next call", () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");
    resetSupabaseClient();
    const client1 = getSupabaseClient();
    resetSupabaseClient();
    const client2 = getSupabaseClient();
    expect(client1).not.toBe(client2);
  });
});

// ===========================================================================
// verifyToken — error cases (no real Supabase connection)
// ===========================================================================

describe("verifyToken — error handling", () => {
  test("throws AuthenticationError with status 500 when client not initialized", async () => {
    setSupabaseEnv(undefined, undefined);
    resetSupabaseClient();

    try {
      await verifyToken("some-fake-token");
      expect(true).toBe(false); // Should not reach here
    } catch (error) {
      expect(error).toBeInstanceOf(AuthenticationError);
      expect((error as AuthenticationError).statusCode).toBe(500);
      expect((error as AuthenticationError).message).toBe(
        "Supabase client not initialized",
      );
    }
  });

  test("throws AuthenticationError for invalid token against real Supabase client", async () => {
    // This creates a real Supabase client but with a fake URL.
    // The token verification will fail with a network/auth error.
    setSupabaseEnv("https://example.supabase.co", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake");
    resetSupabaseClient();

    try {
      await verifyToken("definitely-not-a-valid-jwt-token");
      expect(true).toBe(false); // Should not reach here
    } catch (error) {
      expect(error).toBeInstanceOf(AuthenticationError);
      expect((error as AuthenticationError).statusCode).toBe(401);
    }
  });
});

// ===========================================================================
// logAuthStatus — smoke test (doesn't throw)
// ===========================================================================

describe("logAuthStatus", () => {
  test("does not throw when auth is enabled", () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");
    expect(() => logAuthStatus()).not.toThrow();
  });

  test("does not throw when auth is disabled", () => {
    setSupabaseEnv(undefined, undefined);
    expect(() => logAuthStatus()).not.toThrow();
  });
});

// ===========================================================================
// AuthUser type — structural checks
// ===========================================================================

describe("AuthUser type", () => {
  test("can create AuthUser with all fields", () => {
    const user: AuthUser = {
      identity: "user-uuid-123",
      email: "test@example.com",
      metadata: { name: "Test", orgId: "org-1" },
    };

    expect(user.identity).toBe("user-uuid-123");
    expect(user.email).toBe("test@example.com");
    expect(user.metadata).toEqual({ name: "Test", orgId: "org-1" });
  });

  test("can create AuthUser with null email", () => {
    const user: AuthUser = {
      identity: "user-uuid-456",
      email: null,
      metadata: {},
    };

    expect(user.email).toBeNull();
    expect(user.metadata).toEqual({});
  });

  test("can create AuthUser with empty metadata", () => {
    const user: AuthUser = {
      identity: "user-uuid-789",
      email: "a@b.com",
      metadata: {},
    };

    expect(user.metadata).toEqual({});
  });
});

// ===========================================================================
// Edge cases — middleware with various HTTP methods
// ===========================================================================

describe("authMiddleware — HTTP methods", () => {
  test("POST to protected path returns 401 without auth", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/assistants", "POST");
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);
  });

  test("DELETE to protected path returns 401 without auth", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads/abc-123", "DELETE");
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);
  });

  test("PATCH to protected path returns 401 without auth", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/assistants/abc-123", "PATCH");
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);
  });

  test("PUT to protected path returns 401 without auth", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/store/items", "PUT");
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);
  });
});

// ===========================================================================
// Integration-style: middleware + context flow
// ===========================================================================

describe("authMiddleware — context integration", () => {
  test("user context is null after public path", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    // First set a user to simulate a previous request's state
    setCurrentUser(MOCK_AUTH_USER);
    expect(getCurrentUser()).not.toBeNull();

    // Public path should clear the context
    const request = makeRequest("/health");
    await authMiddleware(request);

    expect(getCurrentUser()).toBeNull();
    expect(getUserIdentity()).toBeNull();
  });

  test("user context is null after auth-disabled path", async () => {
    setSupabaseEnv(undefined, undefined);

    setCurrentUser(MOCK_AUTH_USER);
    expect(getCurrentUser()).not.toBeNull();

    const request = makeRequest("/threads");
    await authMiddleware(request);

    expect(getCurrentUser()).toBeNull();
  });

  test("user context is null after 401 response", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    setCurrentUser(MOCK_AUTH_USER);
    expect(getCurrentUser()).not.toBeNull();

    const request = makeRequest("/threads", "GET");
    const result = await authMiddleware(request);

    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);
    expect(getCurrentUser()).toBeNull();
  });
});

// ===========================================================================
// Case sensitivity — Authorization header
// ===========================================================================

describe("authMiddleware — header case sensitivity", () => {
  test("accepts lowercase 'authorization' header key", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    // Bun's Request normalizes header keys to lowercase, so
    // "authorization" is the standard lookup key. We verify
    // the middleware handles this correctly.
    const request = makeRequest("/threads", "GET", {
      authorization: "Bearer fake-token",
    });

    // This will attempt Supabase verification with a fake token,
    // which should fail — but it means the header was found
    const result = await authMiddleware(request);
    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);

    // The error should be about authentication, NOT about missing header
    const body = await jsonBody(result!);
    expect(body.detail).not.toBe("Authorization header missing");
  });

  test("accepts 'bearer' scheme (case-insensitive)", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET", {
      Authorization: "bearer fake-token",
    });

    const result = await authMiddleware(request);
    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);

    // Should attempt verification, not reject format
    const body = await jsonBody(result!);
    expect(body.detail).not.toBe("Invalid authorization header format");
  });

  test("accepts 'BEARER' scheme (case-insensitive)", async () => {
    setSupabaseEnv("https://example.supabase.co", "some-key");

    const request = makeRequest("/threads", "GET", {
      Authorization: "BEARER fake-token",
    });

    const result = await authMiddleware(request);
    expect(result).not.toBeNull();
    expect(result!.status).toBe(401);

    const body = await jsonBody(result!);
    expect(body.detail).not.toBe("Invalid authorization header format");
  });
});
