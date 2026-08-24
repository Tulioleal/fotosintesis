import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(),
  authHeaders: vi.fn(),
}));

vi.mock("@/lib/server/backend-session", () => ({
  resolveBackendAuthHeaders: mocks.authHeaders,
}));
vi.mock("@/lib/api/config", () => ({
  API_BASE_URL: "http://backend.test",
}));

import { GET } from "./route";

function request(url: string): Request {
  return new Request(`http://frontend.test${url}`);
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const validItem = {
  id: "00000000-0000-4000-8000-000000000010",
  job_type: "enrich_confirmed_plant",
  phase: "evidence",
  status: "processing",
  created_at: "2026-08-13T00:00:00Z",
  updated_at: "2026-08-13T00:00:00Z",
  candidate_id: "00000000-0000-4000-8000-000000000011",
  scientific_name: "Monstera deliciosa",
};

async function headersOf(response: Response): Promise<string> {
  return response.headers.get("Cache-Control") ?? "";
}

describe("enrichment-activity proxy route", () => {
  beforeEach(() => {
    mocks.fetch.mockReset();
    mocks.authHeaders.mockReset();
    globalThis.fetch = mocks.fetch as unknown as typeof fetch;
    mocks.authHeaders.mockResolvedValue({ Accept: "application/json" });
  });

  it("returns 401 with private headers and never calls the backend", async () => {
    mocks.authHeaders.mockResolvedValue(null);

    const response = await GET(request("/api/jobs/enrichment-activity"));

    expect(response.status).toBe(401);
    expect(await headersOf(response)).toBe("private, no-store");
    expect(mocks.fetch).not.toHaveBeenCalled();
  });

  it("forwards valid limit and cursor and marks success private", async () => {
    mocks.fetch.mockResolvedValue(
      jsonResponse({ items: [], has_more: false, next_cursor: null }),
    );

    const response = await GET(
      request("/api/jobs/enrichment-activity?limit=50&cursor=abc-_123"),
    );

    expect(response.status).toBe(200);
    expect(await headersOf(response)).toBe("private, no-store");
    const calledUrl = String(mocks.fetch.mock.calls[0][0]);
    expect(calledUrl).toContain("limit=50");
    expect(calledUrl).toContain("cursor=abc-_123");
  });

  it("preserves backend 422s instead of silently dropping bad params", async () => {
    for (const query of [
      "?limit=not-a-number",
      "?cursor=",
      `?cursor=${"A".repeat(513)}`,
    ]) {
      mocks.fetch.mockResolvedValue(jsonResponse({ detail: "x" }, 422));

      const response = await GET(
        request(`/api/jobs/enrichment-activity${query}`),
      );

      expect(response.status).toBe(422);
      // The raw value was forwarded, not dropped.
      expect(String(mocks.fetch.mock.calls.at(-1)?.[0])).toContain(
        query.slice(1),
      );
    }
  });

  it("keeps backend statuses but replaces arbitrary error bodies", async () => {
    for (const status of [401, 422, 500]) {
      mocks.fetch.mockResolvedValue(
        jsonResponse(
          { detail: "boom", stack: "secret", internal_field: 1 },
          status,
        ),
      );

      const response = await GET(request("/api/jobs/enrichment-activity"));
      const body = await response.json().then((data) => JSON.stringify(data));

      expect(response.status).toBe(status);
      expect(await headersOf(response)).toBe("private, no-store");
      expect(body).not.toContain("secret");
      expect(body).not.toContain("internal_field");
      expect(typeof JSON.parse(body).detail).toBe("string");
    }
  });

  it("returns a sanitized 502 when the backend is unreachable", async () => {
    mocks.fetch.mockRejectedValueOnce(new Error("ECONNREFUSED"));

    const response = await GET(
      request("/api/jobs/enrichment-activity"),
    );

    expect(response.status).toBe(502);
    expect(response.headers.get("Cache-Control")).toBe("private, no-store");
    const body = await response.json();
    expect(body).toEqual({ detail: "Unable to load enrichment activity" });
  });

  it("returns 502 for a successful payload violating runtime bounds and strips unknown success fields", async () => {
    // Oversized count violates the runtime bound.
    mocks.fetch.mockResolvedValue(
      jsonResponse({
        items: [
          {
            ...validItem,
            result: {
              outcome: "complete",
              covered_count: 99_999,
              missing_count: 0,
              regenerated_section_count: 0,
              stale_section_count: 0,
              limitations: [],
            },
          },
        ],
        has_more: false,
        next_cursor: null,
      }),
    );

    const oversized = await GET(request("/api/jobs/enrichment-activity"));
    expect(oversized.status).toBe(502);

    // A payload leaking raw evidence-like fields fails validation.
    mocks.fetch.mockResolvedValue(
      jsonResponse({
        items: [{ ...validItem, secret_payload_marker: "leak" }],
        has_more: false,
        next_cursor: null,
      }),
    );

    const leaky = await GET(request("/api/jobs/enrichment-activity"));
    expect(leaky.status).toBe(200);
    expect(JSON.stringify(await leaky.json())).not.toContain("secret_payload_marker");
  });

  it("rejects contract-inconsistent rows: naive timestamps and terminal-only results", async () => {
    mocks.fetch.mockResolvedValue(
      jsonResponse({
        items: [{ ...validItem, created_at: "2026-08-13T00:00:00" }],
        has_more: false,
        next_cursor: null,
      }),
    );
    const naive = await GET(request("/api/jobs/enrichment-activity"));
    expect(naive.status).toBe(502);

    mocks.fetch.mockResolvedValue(
      jsonResponse({
        items: [
          {
            ...validItem,
            status: "failed",
            result: {
              outcome: "complete",
              covered_count: 1,
              missing_count: 0,
              regenerated_section_count: 0,
              stale_section_count: 0,
              limitations: [],
            },
          },
        ],
        has_more: false,
        next_cursor: null,
      }),
    );
    const contradictory = await GET(request("/api/jobs/enrichment-activity"));
    expect(contradictory.status).toBe(502);
  });

  it("rejects an evidence complete outcome that contradicts the lifecycle map", async () => {
    mocks.fetch.mockResolvedValue(
      jsonResponse({
        items: [
          {
            ...validItem,
            status: "complete",
            updated_at: "2026-08-13T00:00:00Z",
            completed_at: "2026-08-13T00:00:00Z",
            result: {
              outcome: "partial",
              covered_count: 1,
              missing_count: 2,
              regenerated_section_count: 0,
              stale_section_count: 0,
              limitations: [],
            },
          },
        ],
        has_more: false,
        next_cursor: null,
      }),
    );

    const response = await GET(request("/api/jobs/enrichment-activity"));
    expect(response.status).toBe(502);
  });

  it("accepts a refresh noop outcome on a complete refresh row", async () => {
    mocks.fetch.mockResolvedValue(
      jsonResponse({
        items: [
          {
            ...validItem,
            job_type: "refresh_profile",
            phase: "profile_refresh",
            status: "complete",
            updated_at: "2026-08-13T00:00:00Z",
            completed_at: "2026-08-13T00:00:00Z",
            result: {
              outcome: "noop",
              covered_count: 0,
              missing_count: 0,
              regenerated_section_count: 0,
              stale_section_count: 0,
              limitations: [],
            },
          },
        ],
        has_more: false,
        next_cursor: null,
      }),
    );

    const response = await GET(request("/api/jobs/enrichment-activity"));
    expect(response.status).toBe(200);
  });
});
