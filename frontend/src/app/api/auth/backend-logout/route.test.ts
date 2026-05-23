import { describe, expect, it, vi } from "vitest";
import { POST } from "./route";

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

vi.mock("@auth/core/jwt", () => ({
  getToken: mocks.getToken,
}));


describe("POST /api/auth/backend-logout", () => {
  it("invalidates the backend session through the server boundary", async () => {
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
    mocks.getToken.mockResolvedValueOnce({ backendCredential: "server-only-token" });
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
});
