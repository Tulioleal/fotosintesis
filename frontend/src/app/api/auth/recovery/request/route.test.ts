import { beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

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

describe("POST /api/auth/recovery/request", () => {
  beforeEach(() => {
    clearLimiterEnv();
  });

  it("routes recovery initiation through the frontend boundary", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json(
          { status: "ok", message: "If an account with that email exists, we will send you instructions to recover access." },
          { status: 200 },
        ),
      );

    const response = await POST(
      new Request("http://frontend.test/api/auth/recovery/request", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: "tuli@example.com" }),
      }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/recovery/request",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
      }),
    );
    fetchMock.mockRestore();
  });

  it("forwards a trusted source assertion and never forwards client-supplied headers", async () => {
    process.env.AUTH_LIMITER_HMAC_SECRET = "hmac-secret";
    process.env.AUTH_LIMITER_ASSERTION_SECRET = "assertion-secret";
    process.env.AUTH_LIMITER_TRUSTED_FORWARDED_HOPS = "2";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json({ status: "ok", message: "neutral" }, { status: 200 }),
      );

    const response = await POST(
      new Request("http://frontend.test/api/auth/recovery/request", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-forwarded-for": TRUSTED_CHAIN,
          "x-forwarded-proto": "https",
          cookie: "session=attacker-session",
          "x-fotosintesis-source-key": "attacker-key",
          "x-fotosintesis-source-assertion": "attacker-assertion",
        },
        body: JSON.stringify({ email: "tuli@example.com" }),
      }),
    );

    expect(response.status).toBe(200);
    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers as HeadersInit);
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

  it("preserves the neutral recovery body and bounded retry metadata on 429", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ status: "ok", message: "If an account with that email exists, we will send you instructions to recover access." }),
          {
            status: 429,
            headers: { "retry-after": "37", "content-type": "application/json" },
          },
        ),
      );

    const response = await POST(
      new Request("http://frontend.test/api/auth/recovery/request", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: "tuli@example.com" }),
      }),
    );

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("37");
    const payload = await response.json();
    expect(payload.message).toContain("If an account with that email exists");
    fetchMock.mockRestore();
  });
});
