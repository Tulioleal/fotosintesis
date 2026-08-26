import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import middleware from "./middleware";

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

vi.mock("next-auth/jwt", () => ({
  getToken: mocks.getToken,
}));

const VALID_TOKEN = {
  sub: "user-1",
  backendCredential: "stale-token",
  sessionExpiresAt: "2099-01-01T00:00:00.000Z",
  email_verified: true,
};

function privateRequest(path: string, cookie?: string) {
  return new NextRequest(`http://frontend.test${path}`, {
    headers: cookie ? { cookie } : undefined,
  });
}

describe("private route middleware", () => {
  beforeEach(() => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockReset();
    vi.restoreAllMocks();
  });

  it("redirects private routes when no backend session credential exists", async () => {
    mocks.getToken.mockResolvedValueOnce(null);
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await middleware(privateRequest("/home?tab=garden"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://frontend.test/login?callbackUrl=%2Fhome%3Ftab%3Dgarden",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("redirects private routes when stale Auth.js state fails backend validation", async () => {
    mocks.getToken.mockResolvedValueOnce(VALID_TOKEN);
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 401 }));

    const response = await middleware(privateRequest("/garden"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://frontend.test/login?callbackUrl=%2Fgarden",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/session",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer stale-token" }),
      }),
    );
  });

  it("allows private routes when backend session validation succeeds", async () => {
    mocks.getToken.mockResolvedValueOnce(VALID_TOKEN);
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({ status: "ok" }));

    const response = await middleware(privateRequest("/assistant"));

    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("redirects private routes when token decoding fails", async () => {
    mocks.getToken.mockRejectedValueOnce(new Error("sentinel-decode-error"));
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await middleware(privateRequest("/home?tab=garden"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://frontend.test/login?callbackUrl=%2Fhome%3Ftab%3Dgarden",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("redirects private routes when backend session validation transport fails", async () => {
    mocks.getToken.mockResolvedValueOnce(VALID_TOKEN);
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("sentinel-transport-error"));

    const response = await middleware(privateRequest("/garden"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://frontend.test/login?callbackUrl=%2Fgarden",
    );
  });

  it("redirects private routes when decoded token state is malformed without calling the backend", async () => {
    mocks.getToken.mockResolvedValueOnce({ backendCredential: "missing-concrete-state" });
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await middleware(privateRequest("/home?tab=garden"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://frontend.test/login?callbackUrl=%2Fhome%3Ftab%3Dgarden",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not validate public routes even when token decoding fails", async () => {
    mocks.getToken.mockRejectedValueOnce(new Error("sentinel-decode-error"));
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await middleware(privateRequest("/login"));

    expect(response.headers.get("x-middleware-next")).toBe("1");
    expect(mocks.getToken).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not validate public routes", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await middleware(privateRequest("/login"));

    expect(response.headers.get("x-middleware-next")).toBe("1");
    expect(mocks.getToken).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
