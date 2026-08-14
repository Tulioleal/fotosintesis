import { describe, expect, it, vi } from "vitest";
import { POST } from "./route";

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

vi.mock("next-auth/jwt", () => ({
  getToken: mocks.getToken,
}));


describe("POST /api/auth/backend-logout", () => {
  it("invalidates the backend session through the server boundary", async () => {
    process.env.AUTH_SECRET = "test-secret";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ status: "ok" }));

    const response = await POST(
      new Request("http://frontend.test/api/auth/backend-logout", {
        method: "POST",
        headers: { cookie: "fotosintesis_session=opaque" },
      }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/logout",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Cookie: "fotosintesis_session=opaque" }),
      }),
    );
    expect(JSON.stringify(fetchMock.mock.calls[0])).not.toContain("Bearer");
    fetchMock.mockRestore();
  });

  it("invalidates using the server-only Auth.js credential when no backend cookie exists", async () => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockResolvedValueOnce({
      sub: "user-1",
      backendCredential: "server-only-token",
      sessionExpiresAt: "2099-01-01T00:00:00.000Z",
      email_verified: true,
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ status: "ok" }));

    const response = await POST(
      new Request("http://frontend.test/api/auth/backend-logout", { method: "POST" }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/logout",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer server-only-token" }),
      }),
    );
    fetchMock.mockRestore();
  });

  it("returns unauthorized when backend invalidation rejects a stale credential", async () => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockResolvedValueOnce({
      sub: "user-1",
      backendCredential: "stale-token",
      sessionExpiresAt: "2099-01-01T00:00:00.000Z",
      email_verified: true,
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 401 }));

    const response = await POST(
      new Request("http://frontend.test/api/auth/backend-logout", { method: "POST" }),
    );

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ detail: "Unauthorized" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/logout",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer stale-token" }),
      }),
    );
    fetchMock.mockRestore();
  });

  it("does not expose the backend credential or decoder exception text in failure responses", async () => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockRejectedValueOnce(new Error("sentinel-decode-exception"));
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await POST(
      new Request("http://frontend.test/api/auth/backend-logout", { method: "POST" }),
    );

    const body = JSON.stringify(await response.json());
    expect(response.status).toBe(401);
    expect(body).toEqual(JSON.stringify({ detail: "Unauthorized" }));
    expect(body).not.toContain("sentinel");
    expect(body).not.toContain("Bearer");
    expect(fetchMock).not.toHaveBeenCalled();
    fetchMock.mockRestore();
  });

  it("does not expose the backend credential when the backend logout fails", async () => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockResolvedValueOnce({
      sub: "user-1",
      backendCredential: "sentinel-server-only-token",
      sessionExpiresAt: "2099-01-01T00:00:00.000Z",
      email_verified: true,
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("sentinel-backend-body", { status: 500 }));

    const response = await POST(
      new Request("http://frontend.test/api/auth/backend-logout", { method: "POST" }),
    );

    const body = JSON.stringify(await response.json());
    expect(response.status).toBe(500);
    expect(body).not.toContain("sentinel-server-only-token");
    expect(body).not.toContain("sentinel-backend-body");
    expect(body).not.toContain("Bearer");
    fetchMock.mockRestore();
  });
});
