import { beforeEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

vi.mock("@auth/core/jwt", () => ({
  getToken: mocks.getToken,
}));

describe("GET /api/identifications/candidates/[candidateId]/enrichment", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mocks.getToken.mockReset();
  });

  it("forwards authenticated candidate-owned status reads without caching", async () => {
    const payload = {
      candidate_id: "00000000-0000-4000-8000-000000000001",
      policy_version: 1,
      job: {
        id: "00000000-0000-4000-8000-000000000002",
        job_type: "enrich_confirmed_plant",
        status: "pending",
        attempt_count: 0,
        max_attempts: 3,
        created_at: "2026-07-22T00:00:00Z",
        updated_at: "2026-07-22T00:00:00Z",
      },
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json(payload));

    const response = await GET(
      new Request("http://frontend.test/api/identifications/candidates/candidate-1/enrichment", {
        headers: { cookie: "fotosintesis_session=opaque" },
      }),
      { params: Promise.resolve({ candidateId: "candidate-1" }) },
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/identifications/candidates/candidate-1/enrichment",
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({ Cookie: "fotosintesis_session=opaque" }),
      }),
    );
  });

  it("returns unauthorized without backend session credentials", async () => {
    process.env.AUTH_SECRET = "test-secret";
    mocks.getToken.mockResolvedValueOnce(null);
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await GET(
      new Request("http://frontend.test/api/identifications/candidates/candidate-1/enrichment"),
      { params: Promise.resolve({ candidateId: "candidate-1" }) },
    );

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ detail: "Unauthorized" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("propagates a backend not-found response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      Response.json({ detail: "Candidate not found" }, { status: 404 }),
    );

    const response = await GET(
      new Request("http://frontend.test/api/identifications/candidates/missing/enrichment", {
        headers: { cookie: "fotosintesis_session=opaque" },
      }),
      { params: Promise.resolve({ candidateId: "missing" }) },
    );

    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ detail: "Candidate not found" });
  });
});
