import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  AUTHENTICATION_ERROR,
  createBrowserSession,
  createJwtToken,
  mapVerifyCredentialsResult,
  verifyCredentials,
} from "./auth";

const authMocks = vi.hoisted(() => {
  class MockAuthError extends Error {}
  return {
    MockAuthError,
    CredentialsSignin: class extends MockAuthError {
      code = "credentials";
    },
  };
});

vi.mock("next-auth", () => ({
  default: () => ({ handlers: {}, signIn: () => {}, signOut: () => {}, auth: () => {} }),
  CredentialsSignin: authMocks.CredentialsSignin,
}));

vi.mock("next-auth/providers/credentials", () => ({
  default: (options: unknown) => options,
}));

const VALID_VERIFY_RESPONSE = {
  user: {
    id: "sentinel-user-id",
    name: "Sentinel Name",
    email: "sentinel@example.com",
    email_verified: true,
  },
  session_token: "sentinel-session-token",
  session_expires_at: "2099-01-01T00:00:00.000Z",
};

const VALID_USER = {
  id: "sentinel-user-id",
  name: "Sentinel Name",
  email: "sentinel@example.com",
  backendCredential: "sentinel-session-token",
  sessionExpiresAt: "2099-01-01T00:00:00.000Z",
  email_verified: true,
};

const VALID_CREDENTIALS = { email: "sentinel@example.com", password: "sentinel-password" };

function mockFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function mockValidVerifyResponse() {
  return mockFetch(
    Response.json(VALID_VERIFY_RESPONSE, { status: 200, headers: { "content-type": "application/json" } }),
  );
}

function mockInvalidJson() {
  return mockFetch(new Response("not-json", { status: 200 }));
}

describe("verifyCredentials", () => {
  beforeEach(() => {
    mockValidVerifyResponse();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("accepts a complete valid credentials response and returns the concrete server-only state", async () => {
    const result = await verifyCredentials(VALID_CREDENTIALS);

    expect(result).toEqual({ status: "ok", user: VALID_USER });
  });

  it("returns invalid for invalid JSON without creating partial authenticated state", async () => {
    mockInvalidJson();

    expect(await verifyCredentials(VALID_CREDENTIALS)).toEqual({ status: "invalid" });
  });

  it.each([
    ["missing user id", { ...VALID_VERIFY_RESPONSE, user: { ...VALID_VERIFY_RESPONSE.user, id: "" } }],
    ["missing user name", { ...VALID_VERIFY_RESPONSE, user: { ...VALID_VERIFY_RESPONSE.user, name: "" } }],
    ["invalid user email", { ...VALID_VERIFY_RESPONSE, user: { ...VALID_VERIFY_RESPONSE.user, email: "not-an-email" } }],
    ["non-Boolean email_verified", { ...VALID_VERIFY_RESPONSE, user: { ...VALID_VERIFY_RESPONSE.user, email_verified: "yes" } }],
    ["missing session_token", { ...VALID_VERIFY_RESPONSE, session_token: "" }],
    ["invalid session_expires_at", { ...VALID_VERIFY_RESPONSE, session_expires_at: "not-a-date" }],
  ])("denies a successful response with %s", async (_label, malformedResponse) => {
    mockFetch(Response.json(malformedResponse, { status: 200 }));

    expect(await verifyCredentials(VALID_CREDENTIALS)).toEqual({ status: "invalid" });
  });

  type JsonObject = Record<string, unknown>;
  function withoutFields(response: JsonObject, path: string[]): JsonObject {
    const clone = JSON.parse(JSON.stringify(response)) as JsonObject;
    let target = clone as JsonObject;
    for (const key of path.slice(0, -1)) {
      target = target[key] as JsonObject;
    }
    delete target[path[path.length - 1]];
    return clone;
  }

  it.each([
    ["absent user", ["user"]],
    ["absent user.id", ["user", "id"]],
    ["absent user.name", ["user", "name"]],
    ["absent user.email", ["user", "email"]],
    ["absent user.email_verified", ["user", "email_verified"]],
    ["absent session_token", ["session_token"]],
    ["absent session_expires_at", ["session_expires_at"]],
  ])("denies a successful response with a genuinely %s field", async (_label, path) => {
    const malformedResponse = withoutFields(VALID_VERIFY_RESPONSE, path);
    mockFetch(Response.json(malformedResponse, { status: 200 }));

    expect(await verifyCredentials(VALID_CREDENTIALS)).toEqual({ status: "invalid" });
  });

  it("returns invalid when the backend does not respond ok", async () => {
    mockFetch(new Response(null, { status: 401 }));

    expect(await verifyCredentials(VALID_CREDENTIALS)).toEqual({ status: "invalid" });
  });

  it("returns rate_limited with the bounded retry delay when the backend returns 429", async () => {
    mockFetch(new Response(null, { status: 429, headers: { "retry-after": "42" } }));

    expect(await verifyCredentials(VALID_CREDENTIALS)).toEqual({
      status: "rate_limited",
      retryAfterSeconds: 42,
    });
  });

  it("returns unavailable when the backend fails closed on limiter storage", async () => {
    mockFetch(new Response(null, { status: 503 }));

    expect(await verifyCredentials(VALID_CREDENTIALS)).toEqual({ status: "unavailable" });
  });

  it("returns unavailable with a bounded retry delay when the backend emits one", async () => {
    mockFetch(new Response(null, { status: 503, headers: { "retry-after": "30" } }));

    expect(await verifyCredentials(VALID_CREDENTIALS)).toEqual({
      status: "unavailable",
      retryAfterSeconds: 30,
    });
  });

  it("returns invalid for invalid credentials input", async () => {
    expect(await verifyCredentials({ email: "not-an-email", password: "" })).toEqual({
      status: "invalid",
    });
  });

  it("propagates network transport failures to Auth.js error handling", async () => {
    const sentinelError = new Error("sentinel-network-error");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(sentinelError));

    await expect(verifyCredentials(VALID_CREDENTIALS)).rejects.toThrow("sentinel-network-error");
  });
});

describe("mapVerifyCredentialsResult", () => {
  it("maps a successful result to the concrete server-only user state", () => {
    expect(mapVerifyCredentialsResult({ status: "ok", user: VALID_USER })).toEqual(VALID_USER);
  });

  it("maps invalid credentials to the neutral null without an error code", () => {
    expect(mapVerifyCredentialsResult({ status: "invalid" })).toBeNull();
  });

  it("traverses the real CredentialsRateLimited path with the bounded retry code", () => {
    expect(() => mapVerifyCredentialsResult({ status: "rate_limited", retryAfterSeconds: 42 })).toThrowError(
      expect.objectContaining({
        code: "credentials_rate_limited:42",
        retryAfterSeconds: 42,
      }),
    );
  });

  it("traverses the CredentialsUnavailable path with the bounded unavailable code", () => {
    expect(() => mapVerifyCredentialsResult({ status: "unavailable", retryAfterSeconds: 30 })).toThrowError(
      expect.objectContaining({
        code: "temporarily_unavailable:30",
      }),
    );
  });

  it("throws a bounded unavailable code even when the backend omits a retry delay", () => {
    expect(() => mapVerifyCredentialsResult({ status: "unavailable" })).toThrowError(
      expect.objectContaining({
        code: expect.stringMatching(/^temporarily_unavailable:\d+$/),
      }),
    );
  });
});

describe("createJwtToken", () => {
  it("copies concrete validated user state into the token and sets sub from the user ID", () => {
    const token = createJwtToken({ sub: "sentinel-sub", email: "kept@example.com" }, VALID_USER);

    expect(token.sub).toBe("sentinel-user-id");
    expect(token.backendCredential).toBe("sentinel-session-token");
    expect(token.sessionExpiresAt).toBe("2099-01-01T00:00:00.000Z");
    expect(token.email_verified).toBe(true);
    expect(token.email).toBe("kept@example.com");
  });

  it.each([
    ["missing user id", { ...VALID_USER, id: "" }],
    ["missing user name", { ...VALID_USER, name: "" }],
    ["invalid user email", { ...VALID_USER, email: "not-an-email" }],
    ["missing backend credential", { ...VALID_USER, backendCredential: "" }],
    ["invalid session expiration", { ...VALID_USER, sessionExpiresAt: "not-a-date" }],
    ["non-Boolean verification state", { ...VALID_USER, email_verified: "yes" }],
  ])("fails malformed callback state (%s) with one generic value-free error", (_label, malformedUser) => {
    let thrown: unknown;
    try {
      createJwtToken({ sub: "sentinel-sub" }, malformedUser);
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(Error);
    expect((thrown as Error).message).toBe(AUTHENTICATION_ERROR);
    expect((thrown as Error).message).not.toContain("sentinel");
    expect((thrown as Error).message).not.toContain("credential");
    expect((thrown as Error).message).not.toContain("token");
  });
});

describe("createBrowserSession", () => {
  const VALID_CALLBACK_TOKEN = {
    sub: "sentinel-sub",
    backendCredential: "sentinel-server-only-credential",
    sessionExpiresAt: "2099-01-01T00:00:00.000Z",
    email_verified: true,
  };
  const VALID_BROWSER_SESSION = {
    user: { id: "", email_verified: false, name: "Sentinel Name", email: "sentinel@example.com" },
    expires: "2099-01-01T00:00:00.000Z",
  };

  it("maps the validated token identity into the browser session and exposes only safe identity fields", () => {
    const session = createBrowserSession(VALID_BROWSER_SESSION, VALID_CALLBACK_TOKEN);

    expect(session.user.id).toBe("sentinel-sub");
    expect(session.user.email_verified).toBe(true);

    const serialized = JSON.stringify(session);
    expect(serialized).not.toContain("backendCredential");
    expect(serialized).not.toContain("sentinel-server-only-credential");
    expect(serialized).not.toContain("sessionExpiresAt");
  });

  it("projects a new session that strips forbidden input fields at both levels", () => {
    const session = createBrowserSession(
      {
        expires: "2099-01-01T00:00:00.000Z",
        backendCredential: "sentinel-top-level",
        sessionExpiresAt: "sentinel-expiration",
        user: {
          id: "orig-id",
          email_verified: false,
          name: "Sentinel Name",
          email: "sentinel@example.com",
          image: null,
          backendCredential: "sentinel-user-level",
          sessionExpiresAt: "sentinel-user-expiration",
        },
      } as never,
      VALID_CALLBACK_TOKEN,
    );

    expect(session.expires).toBe("2099-01-01T00:00:00.000Z");
    expect(session.user.id).toBe("sentinel-sub");
    expect(session.user.name).toBe("Sentinel Name");
    expect(session.user.email).toBe("sentinel@example.com");
    expect(session.user.image).toBeNull();
    expect(session.user.email_verified).toBe(true);

    const serialized = JSON.stringify(session);
    expect(serialized).not.toContain("backendCredential");
    expect(serialized).not.toContain("sessionExpiresAt");
    expect(serialized).not.toContain("sentinel-top-level");
    expect(serialized).not.toContain("sentinel-user-level");
    expect(serialized).not.toContain("sentinel-expiration");
    expect(serialized).not.toContain("sentinel-user-expiration");
    expect(serialized).not.toContain("orig-id");
  });

  function withoutTokenFields(token: Record<string, unknown>, keys: string[]): Record<string, unknown> {
    const clone = { ...token };
    for (const key of keys) delete clone[key];
    return clone;
  }

  function expectCallbackDenial(token: Record<string, unknown>) {
    let thrown: unknown;
    try {
      createBrowserSession(VALID_BROWSER_SESSION, token);
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(Error);
    expect((thrown as Error).message).toBe(AUTHENTICATION_ERROR);
    expect((thrown as Error).message).not.toContain("sentinel");
    expect((thrown as Error).message).not.toContain("credential");
    expect((thrown as Error).message).not.toContain("token");
    expect((thrown as Error).message).not.toContain("expiration");
  }

  it("rejects an absent sub", () => {
    expectCallbackDenial(withoutTokenFields(VALID_CALLBACK_TOKEN, ["sub"]));
  });

  it("rejects an empty sub", () => {
    expectCallbackDenial({ ...VALID_CALLBACK_TOKEN, sub: "" });
  });

  it("rejects a non-string sub", () => {
    expectCallbackDenial({ ...VALID_CALLBACK_TOKEN, sub: 42 });
  });

  it("rejects an absent backendCredential", () => {
    expectCallbackDenial(withoutTokenFields(VALID_CALLBACK_TOKEN, ["backendCredential"]));
  });

  it("rejects an empty backendCredential", () => {
    expectCallbackDenial({ ...VALID_CALLBACK_TOKEN, backendCredential: "" });
  });

  it("rejects a non-string backendCredential", () => {
    expectCallbackDenial({ ...VALID_CALLBACK_TOKEN, backendCredential: 42 });
  });

  it("rejects an absent sessionExpiresAt", () => {
    expectCallbackDenial(withoutTokenFields(VALID_CALLBACK_TOKEN, ["sessionExpiresAt"]));
  });

  it("rejects an empty sessionExpiresAt", () => {
    expectCallbackDenial({ ...VALID_CALLBACK_TOKEN, sessionExpiresAt: "" });
  });

  it("rejects an invalid sessionExpiresAt", () => {
    expectCallbackDenial({ ...VALID_CALLBACK_TOKEN, sessionExpiresAt: "not-a-date" });
  });

  it("rejects a non-string sessionExpiresAt", () => {
    expectCallbackDenial({ ...VALID_CALLBACK_TOKEN, sessionExpiresAt: 42 });
  });

  it("rejects an absent email_verified", () => {
    expectCallbackDenial(withoutTokenFields(VALID_CALLBACK_TOKEN, ["email_verified"]));
  });

  it("rejects an empty email_verified", () => {
    expectCallbackDenial({ ...VALID_CALLBACK_TOKEN, email_verified: "" });
  });

  it("rejects a non-Boolean email_verified", () => {
    expectCallbackDenial({ ...VALID_CALLBACK_TOKEN, email_verified: "yes" });
  });

  it("rejects an absent session.user without returning a browser session", () => {
    let thrown: unknown;
    try {
      createBrowserSession({ expires: "2099-01-01T00:00:00.000Z" } as never, VALID_CALLBACK_TOKEN);
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(Error);
    expect((thrown as Error).message).toBe(AUTHENTICATION_ERROR);
    expect((thrown as Error).message).not.toContain("sentinel");
  });
});
