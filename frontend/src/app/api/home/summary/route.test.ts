import { describe, expect, it, vi } from "vitest";
import { GET } from "./route";

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

vi.mock("@auth/core/jwt", () => ({
  getToken: mocks.getToken,
}));


describe("GET /api/home/summary", () => {
  it("forwards the HttpOnly cookie to the backend", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      Response.json({ user: { name: "Tuli" }, empty_state: true, access: [] }),
    );

    const response = await GET(
      new Request("http://frontend.test/api/home/summary", {
        headers: { cookie: "fotosintesis_session=opaque" },
      }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/home/summary",
      expect.objectContaining({
        headers: expect.objectContaining({ Cookie: "fotosintesis_session=opaque" }),
      }),
    );
    expect(JSON.stringify(fetchMock.mock.calls[0])).not.toContain("Bearer");
    fetchMock.mockRestore();
  });

  it("uses the server-only Auth.js credential when no backend cookie exists", async () => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockResolvedValueOnce({ backendCredential: "server-only-token" });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      Response.json({ user: { name: "Tuli" }, empty_state: true, access: [] }),
    );

    const response = await GET(new Request("http://frontend.test/api/home/summary"));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/home/summary",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer server-only-token" }),
      }),
    );
    fetchMock.mockRestore();
  });

  it("returns unauthorized without credential details", async () => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockResolvedValueOnce(null);
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await GET(new Request("http://frontend.test/api/home/summary"));

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ detail: "Unauthorized" });
    expect(fetchMock).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  it("returns unauthorized when the login-created credential is stale", async () => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockResolvedValueOnce({ backendCredential: "stale-token" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 401 }));

    const response = await GET(new Request("http://frontend.test/api/home/summary"));

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ detail: "Unauthorized" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/home/summary",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer stale-token" }),
      }),
    );
    fetchMock.mockRestore();
  });
});
