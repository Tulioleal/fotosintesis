import { describe, expect, it, vi } from "vitest";
import { GET } from "./route";

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

vi.mock("@auth/core/jwt", () => ({
  getToken: mocks.getToken,
}));

describe("GET /api/plant-profiles/[scientificName]", () => {
  it("forwards auth headers and candidate context to the backend", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      Response.json({ scientific_name: "Nephrolepis exaltata" }),
    );

    const response = await GET(
      new Request("http://frontend.test/api/plant-profiles/Nephrolepis%20exaltata?candidateId=candidate-1&language=es", {
        headers: { cookie: "fotosintesis_session=opaque" },
      }),
      { params: Promise.resolve({ scientificName: "Nephrolepis exaltata" }) },
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/plant-profiles/Nephrolepis%20exaltata?candidateId=candidate-1&language=es",
      expect.objectContaining({
        headers: expect.objectContaining({ Cookie: "fotosintesis_session=opaque" }),
      }),
    );
    fetchMock.mockRestore();
  });

  it("returns unauthorized without backend session credentials", async () => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockResolvedValueOnce(null);
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await GET(
      new Request("http://frontend.test/api/plant-profiles/Nephrolepis%20exaltata?candidateId=candidate-1"),
      { params: Promise.resolve({ scientificName: "Nephrolepis exaltata" }) },
    );

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ detail: "Unauthorized" });
    expect(fetchMock).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });
});
