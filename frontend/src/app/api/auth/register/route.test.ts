import { beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import { POST } from "./route";
import { hmacSha256Hex } from "@/lib/server/source-identity";

function clearLimiterEnv() {
  for (const key of [
    "AUTH_LIMITER_HMAC_SECRET",
    "AUTH_LIMITER_ASSERTION_SECRET",
    "AUTH_LIMITER_HMAC_KEY_VERSION",
    "AUTH_LIMITER_TRUSTED_FORWARDED_HOPS",
  ]) {
    delete process.env[key];
  }
}

const TRUSTED_CHAIN = "203.0.113.55, 198.51.100.9";

function enableTrustedProxyEnv() {
  process.env.AUTH_LIMITER_HMAC_SECRET = "hmac-secret";
  process.env.AUTH_LIMITER_ASSERTION_SECRET = "assertion-secret";
  process.env.AUTH_LIMITER_HMAC_KEY_VERSION = "1";
  process.env.AUTH_LIMITER_TRUSTED_FORWARDED_HOPS = "2";
}

function capturedFetchHeaders(fetchMock: MockInstance): Headers {
  const [, init] = fetchMock.mock.calls[0];
  return new Headers((init as RequestInit | undefined)?.headers as HeadersInit);
}

describe("POST /api/auth/register", () => {
  beforeEach(() => {
    clearLimiterEnv();
  });

  it("forwards the registration payload through the frontend boundary", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ user: { id: "u-1" } }, { status: 201 }));

    const response = await POST(
      new Request("http://frontend.test/api/auth/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: "Tuli", email: "tuli@example.com", password: "password123" }),
      }),
    );

    expect(response.status).toBe(201);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/register",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
      }),
    );
    fetchMock.mockRestore();
  });

  it("forwards a trusted source assertion and never forwards client-supplied headers", async () => {
    enableTrustedProxyEnv();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ user: { id: "u-1" } }, { status: 201 }));

    const response = await POST(
      new Request("http://frontend.test/api/auth/register", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-forwarded-for": TRUSTED_CHAIN,
          "x-forwarded-proto": "https",
          cookie: "session=attacker-session",
          "x-fotosintesis-source-key": "attacker-key",
          "x-fotosintesis-source-assertion": "attacker-assertion",
        },
        body: JSON.stringify({ name: "Tuli", email: "tuli@example.com", password: "password123" }),
      }),
    );

    expect(response.status).toBe(201);
    const headers = capturedFetchHeaders(fetchMock);
    expect(headers.get("x-fotosintesis-source-key")).toMatch(/^[0-9a-f]{64}$/);
    expect(headers.get("x-fotosintesis-source-assertion")).toMatch(/^[0-9a-f]{64}$/);
    expect(headers.get("x-fotosintesis-source-key")).not.toBe("attacker-key");
    expect(headers.get("x-fotosintesis-source-assertion")).not.toBe("attacker-assertion");
    // Allowlist boundary: cookies, forwarding headers, and unrelated client
    // headers never reach FastAPI.
    expect(headers.has("cookie")).toBe(false);
    expect(headers.has("x-forwarded-for")).toBe(false);
    expect(headers.has("x-forwarded-proto")).toBe(false);
    expect(headers.get("content-type")).toBe("application/json");
    fetchMock.mockRestore();
  });

  it("derives the source key from the trusted client, ignoring attacker and load-balancer entries", async () => {
    enableTrustedProxyEnv();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ user: { id: "u-1" } }, { status: 201 }));

    // Attacker-prepended forwarding entry, then the trusted client, then the
    // load-balancer address: only the trusted client may become limiter
    // identity. This is contract-level integration evidence based on the
    // Google external Application Load Balancer forwarding contract, not a
    // live GKE deployment spoofing test.
    const response = await POST(
      new Request("http://frontend.test/api/auth/register", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-forwarded-for": "6.6.6.6, 203.0.113.55, 198.51.100.9",
          cookie: "session=attacker-session",
        },
        body: JSON.stringify({ name: "Tuli", email: "tuli@example.com", password: "password123" }),
      }),
    );

    expect(response.status).toBe(201);
    const headers = capturedFetchHeaders(fetchMock);
    const expectedSourceKey = hmacSha256Hex(
      "hmac-secret",
      ["1", "source", "203.0.113.55"].join("\u0000"),
    );
    expect(headers.get("x-fotosintesis-source-key")).toBe(expectedSourceKey);
    // Neither the attacker prefix nor the load-balancer address is identity.
    expect(headers.get("x-fotosintesis-source-key")).not.toContain("198.51.100.9");
    expect(headers.get("x-fotosintesis-source-key")).not.toContain("6.6.6.6");
    expect(headers.get("x-fotosintesis-source-assertion")).toBe(
      hmacSha256Hex("assertion-secret", expectedSourceKey),
    );
    // Raw forwarding headers and cookies remain absent.
    expect(headers.has("cookie")).toBe(false);
    expect(headers.has("x-forwarded-for")).toBe(false);
    fetchMock.mockRestore();
  });

  it("forwards no trusted assertion when the platform suffix is malformed", async () => {
    enableTrustedProxyEnv();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ user: { id: "u-1" } }, { status: 201 }));

    // A non-IP entry inside the trusted suffix invalidates the whole platform
    // chain: the frontend must not fabricate a trusted assertion and the
    // backend applies the conservative missing-source policy.
    const response = await POST(
      new Request("http://frontend.test/api/auth/register", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-forwarded-for": "6.6.6.6, spoofed.example.com, 198.51.100.9",
        },
        body: JSON.stringify({ name: "Tuli", email: "tuli@example.com", password: "password123" }),
      }),
    );

    expect(response.status).toBe(201);
    const headers = capturedFetchHeaders(fetchMock);
    expect(headers.has("x-fotosintesis-source-key")).toBe(false);
    expect(headers.has("x-fotosintesis-source-assertion")).toBe(false);
    expect(headers.get("content-type")).toBe("application/json");
    fetchMock.mockRestore();
  });

  it("forwards a 429 with the Retry-After header from the backend", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Too many requests for registration" }), {
          status: 429,
          headers: { "retry-after": "42", "content-type": "application/json" },
        }),
      );

    const response = await POST(
      new Request("http://frontend.test/api/auth/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: "Tuli", email: "tuli@example.com", password: "password123" }),
      }),
    );

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("42");
    expect(await response.json()).toEqual({ detail: "Too many requests for registration" });
    fetchMock.mockRestore();
  });
});
