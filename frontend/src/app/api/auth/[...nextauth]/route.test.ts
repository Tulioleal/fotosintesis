import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import { GET, POST } from "./route";

const handlersMock = vi.hoisted(() => ({
  GET: vi.fn(async () => new Response(null, { status: 200 })),
  POST: vi.fn(async () => new Response(null, { status: 200 })),
}));

vi.mock("../../../../../auth", () => ({
  handlers: handlersMock,
}));

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

function authRequest(action: string, { method = "POST" } = {}): Request {
  const url = `http://frontend.test/api/auth${action ? `/${action}` : ""}`;
  return new Request(url, {
    method,
    headers: { "content-type": "application/json" },
    body: method === "POST" ? "{}" : undefined,
  });
}

describe("Auth.js POST wrapper", () => {
  let fetchMock: MockInstance;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    clearLimiterEnv();
    fetchSpy = vi.fn(async () => new Response(null, { status: 200 }));
    fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(fetchSpy as never);
  });

  afterEach(() => {
    fetchMock.mockRestore();
    handlersMock.GET.mockClear();
    handlersMock.POST.mockClear();
  });  it("forwards GET session reads unchanged and never enforces the limiter", async () => {
    const response = await GET(authRequest("session", { method: "GET" }) as never);

    expect(response.status).toBe(200);
    expect(handlersMock.GET).toHaveBeenCalledTimes(1);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("enforces the internal admission endpoint before a relevant callback POST", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    const response = await POST(authRequest("callback/credentials") as never);

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/admit/authjs_post",
      expect.objectContaining({
        method: "POST",
        body: null,
      }),
    );
    // Auth.js still handled the request after admission.
    expect(handlersMock.POST).toHaveBeenCalledTimes(1);
  });

  it("returns the bounded 429 as an Auth.js-compatible error redirect", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Too many requests for authjs_post" }), {
        status: 429,
        headers: { "retry-after": "37", "content-type": "application/json" },
      }),
    );

    const response = await POST(authRequest("callback/credentials") as never);

    expect(response.status).toBe(429);
    const payload = await response.json();
    // The Auth.js client parses `error` and `code` from the `url` field.
    const url = new URL(payload.url);
    expect(url.searchParams.get("error")).toBe("CredentialsSignin");
    expect(url.searchParams.get("code")).toBe("credentials_rate_limited:37");
    // Auth.js must NOT run when admission is rejected.
    expect(handlersMock.POST).not.toHaveBeenCalled();
  });

  it("returns the bounded 503 with the unavailable code without invoking Auth.js", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Temporarily unavailable" }), {
        status: 503,
        headers: { "retry-after": "5", "content-type": "application/json" },
      }),
    );

    const response = await POST(authRequest("callback/credentials") as never);

    expect(response.status).toBe(503);
    const payload = await response.json();
    const url = new URL(payload.url);
    expect(url.searchParams.get("code")).toBe("temporarily_unavailable:5");
    expect(handlersMock.POST).not.toHaveBeenCalled();
  });

  it("classifies an unexpected admission failure as unavailable, not rate limited", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "boom" }), {
        status: 500,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await POST(authRequest("callback/credentials") as never);

    expect(response.status).toBe(500);
    const payload = await response.json();
    const url = new URL(payload.url);
    expect(url.searchParams.get("code")).toBe("temporarily_unavailable:60");
    expect(handlersMock.POST).not.toHaveBeenCalled();
  });

  it("preserves authenticated logout and session-update POSTs unchanged", async () => {
    const signout = await POST(authRequest("signout") as never);
    expect(signout.status).toBe(200);
    expect(fetchMock).not.toHaveBeenCalled();

    const sessionUpdate = await POST(authRequest("session") as never);
    expect(sessionUpdate.status).toBe(200);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards the source assertion when a trusted source is available", async () => {
    process.env.AUTH_LIMITER_HMAC_SECRET = "hmac-secret";
    process.env.AUTH_LIMITER_ASSERTION_SECRET = "assertion-secret";
    process.env.AUTH_LIMITER_TRUSTED_FORWARDED_HOPS = "2";
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    const request = authRequest("callback/credentials");
    request.headers.set("x-forwarded-for", "203.0.113.55, 198.51.100.9");
    await POST(request as never);

    const [, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get("x-fotosintesis-source-key")).toMatch(/^[0-9a-f]{64}$/);
    expect(headers.get("x-fotosintesis-source-assertion")).toMatch(/^[0-9a-f]{64}$/);
    // Allowlist boundary: no cookies or forwarding headers cross to the backend.
    expect(headers.has("cookie")).toBe(false);
    expect(headers.has("x-forwarded-for")).toBe(false);
  });
});
