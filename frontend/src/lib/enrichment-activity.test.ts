import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EnrichmentActivityItem } from "@/lib/api/client";

const mocks = vi.hoisted(() => ({
  getEnrichmentActivity: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    getEnrichmentActivity: mocks.getEnrichmentActivity,
  },
}));
import {
  ACTIVITY_POLL_INTERVAL_MS,
  MAX_STORED_OUTCOME_VERSIONS,
  activityQueryKey,
  compareActivityDescending,
  loadEnrichmentActivity,
  activityDetailCopy,
  activityHasActiveWork,
  activityItemsRelatedTo,
  activityProfileHref,
  activityRefetchInterval,
  activityStatusCopy,
  claimRefreshReconciliation,
  loadAnnouncedOutcomes,
  outcomeVersion,
  rememberAnnouncedOutcome,
  resetRefreshReconciliationClaimsForTests,
} from "./enrichment-activity";

const evidenceItem = (
  overrides: Partial<EnrichmentActivityItem> = {},
): EnrichmentActivityItem => ({
  id: "11111111-1111-4111-8111-111111111111",
  job_type: "enrich_confirmed_plant",
  phase: "evidence",
  status: "pending",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  completed_at: null,
  species_key: "gbif:2878688|binomial:Monstera deliciosa",
  scientific_name: "Monstera deliciosa",
  common_name: "Monstera",
  candidate_id: "candidate-1",
  result: null,
  last_error: null,
  ...overrides,
});

describe("activityHasActiveWork", () => {
  it("returns true only when a job is pending or processing", () => {
    expect(activityHasActiveWork([evidenceItem({ status: "pending" })])).toBe(
      true,
    );
    expect(
      activityHasActiveWork([evidenceItem({ status: "processing" })]),
    ).toBe(true);
    expect(activityHasActiveWork([evidenceItem({ status: "complete" })])).toBe(
      false,
    );
    expect(activityHasActiveWork([])).toBe(false);
    expect(activityHasActiveWork(undefined)).toBe(false);
  });
});

describe("activityRefetchInterval", () => {
  it("polls only while active work exists and stops at a terminal state", () => {
    const pending = activityRefetchInterval({
      state: { data: { items: [evidenceItem({ status: "pending" })], has_more: false } },
    });
    expect(pending).toBe(ACTIVITY_POLL_INTERVAL_MS);

    const terminal = activityRefetchInterval({
      state: { data: { items: [evidenceItem({ status: "complete" })], has_more: false } },
    });
    expect(terminal).toBe(false);
  });
});

describe("outcomeVersion", () => {
  it("keys a terminal outcome by job, status, and updated_at version", () => {
    const item = evidenceItem({
      status: "partial",
      updated_at: "2026-08-01T00:00:00Z",
    });
    expect(outcomeVersion(item)).toBe(
      "11111111-1111-4111-8111-111111111111:partial:2026-08-01T00:00:00Z",
    );
    expect(outcomeVersion(evidenceItem({ status: "processing" }))).toBeNull();
  });
});

describe("activityProfileHref", () => {
  it("builds the authorized profile link including the candidate id", () => {
    const href = activityProfileHref(evidenceItem());
    expect(href).toBe(
      "/profiles/Monstera%20deliciosa?candidateId=candidate-1",
    );
  });

  it("always builds an authorized link for refresh items", () => {
    const href = activityProfileHref(
      evidenceItem({
        phase: "profile_refresh",
        job_type: "refresh_profile",
      }),
    );
    expect(href).toBe(
      "/profiles/Monstera%20deliciosa?candidateId=candidate-1",
    );
  });

  it("returns a string for every valid item", () => {
    expect(typeof activityProfileHref(evidenceItem())).toBe("string");
  });

  it("uses the accepted scientific name over the normalized binomial for refresh links", () => {
    const href = activityProfileHref(
      evidenceItem({
        phase: "profile_refresh",
        job_type: "refresh_profile",
        scientific_name: "Monstera adansonii",
        species_key: "gbif:2878688|binomial:Monstera deliciosa",
        candidate_id: "candidate-123",
      }),
    );
    expect(href).toBe(
      "/profiles/Monstera%20adansonii?candidateId=candidate-123",
    );
  });
});

describe("activityStatusCopy", () => {
  it("distinguishes evidence and profile-refresh phases and terminal outcomes", () => {
    expect(
      activityStatusCopy(evidenceItem({ phase: "evidence", status: "processing" })),
    ).toBe("Reuniendo evidencia en segundo plano");
    expect(
      activityStatusCopy(evidenceItem({ phase: "evidence", status: "complete" })),
    ).toBe("La evidencia está lista");
    expect(
      activityStatusCopy(evidenceItem({ phase: "evidence", status: "failed" })),
    ).toBe("No pudimos ampliar la evidencia");
    expect(
      activityStatusCopy(
        evidenceItem({ phase: "profile_refresh", job_type: "refresh_profile", status: "processing" }),
      ),
    ).toBe("Actualizando las secciones del perfil");
    expect(
      activityStatusCopy(
        evidenceItem({
          phase: "profile_refresh",
          job_type: "refresh_profile",
          status: "complete",
          result: {
            outcome: "noop",
            covered_count: 0,
            missing_count: 0,
            regenerated_section_count: 0,
            stale_section_count: 0,
            limitations: [],
          },
        }),
      ),
    ).toBe("El perfil ya estaba al día");
  });

  it("never claims the profile is updated solely from evidence completion", () => {
    const evidenceReady = activityDetailCopy(
      evidenceItem({
        phase: "evidence",
        status: "complete",
        result: {
          outcome: "complete",
          covered_count: 1,
          missing_count: 0,
          regenerated_section_count: 0,
          stale_section_count: 0,
          limitations: [],
        },
      }),
    );
    expect(evidenceReady).not.toMatch(/perfil se actualiz/);
  });

  it("provides sanitized recovery guidance on failure", () => {
    const failed = activityDetailCopy(
      evidenceItem({ status: "failed", last_error: { category: "attempts_exhausted", retryable: false } }),
    );
    expect(failed).toMatch(/El perfil sigue disponible/);
    expect(failed).not.toMatch(/intentar ampliar la evidencia nuevamente/);
  });
});

describe("activityItemsRelatedTo", () => {
  const refresh = evidenceItem({
    id: "22222222-2222-4222-8222-222222222222",
    phase: "profile_refresh",
    job_type: "refresh_profile",
    candidate_id: "candidate-1",
  });

  it("matches evidence by candidate id and refresh by species key", () => {
    const matches = activityItemsRelatedTo([evidenceItem(), refresh], {
      candidateIds: ["candidate-1"],
      speciesKeys: ["gbif:2878688|binomial:Monstera deliciosa"],
    });
    expect(matches.map((item) => item.id)).toEqual([
      evidenceItem().id,
      refresh.id,
    ]);
  });

  it("returns everything when no filter is provided", () => {
    const items = activityItemsRelatedTo([evidenceItem(), refresh]);
    expect(items).toHaveLength(2);
  });

  it("matches by scientific name case-insensitively", () => {
    const matches = activityItemsRelatedTo([evidenceItem(), refresh], {
      scientificNames: ["monstera deliciosa"],
    });
    expect(matches).toHaveLength(2);
  });
});

describe("user-scoped activity state", () => {
  const userA = "user-aaaaaaaa";
  const userB = "user-bbbbbbbb";

  beforeEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
    resetRefreshReconciliationClaimsForTests();
  });

  it("scopes announced outcomes by user", () => {
    rememberAnnouncedOutcome(userA, "job:complete:2026");
    expect(loadAnnouncedOutcomes(userA).has("job:complete:2026")).toBe(true);
    expect(loadAnnouncedOutcomes(userB).has("job:complete:2026")).toBe(false);
  });

  it("keeps at most the newest bounded versions in storage", () => {
    for (let index = 0; index < MAX_STORED_OUTCOME_VERSIONS + 25; index += 1) {
      rememberAnnouncedOutcome(userA, `version-${index}`);
    }

    const stored = loadAnnouncedOutcomes(userA);
    expect(stored.size).toBe(MAX_STORED_OUTCOME_VERSIONS);
    expect(stored.has(`version-${MAX_STORED_OUTCOME_VERSIONS - 1}`)).toBe(
      true,
    );
    expect(stored.has("version-0")).toBe(false);
  });

  it("treats malformed stored data as empty", () => {
    window.sessionStorage.setItem(
      `fotosintesis:enrichment-terminal-outcomes:v2:${userA}`,
      "{not json",
    );
    expect(loadAnnouncedOutcomes(userA).size).toBe(0);
  });

  it("prunes entries older than backend retention regardless of count", () => {
    const now = Date.now();
    const oldVersion = (index: number) =>
      `job-${index}:complete:${new Date(now - 800 * 60 * 60 * 1000).toISOString()}`;
    const freshVersion = (index: number) =>
      `job-${index}:complete:${new Date(now).toISOString()}`;

    for (let index = 0; index < 250; index += 1) {
      rememberAnnouncedOutcome(userA, oldVersion(index));
    }
    for (let index = 0; index < 10; index += 1) {
      rememberAnnouncedOutcome(userA, freshVersion(index));
    }

    const stored = loadAnnouncedOutcomes(userA);
    expect(stored.size).toBe(10);
    expect([...stored].every((version) => version.includes(":complete:"))).toBe(
      true,
    );
  });

  it("keeps a fresh reconciliation claim past many expired inserts", () => {
    const now = Date.now();
    const profileKey = ["plant-profile", "candidate-1", "Monstera", "en"];

    // Seed many expired claims (older than retention) in the same namespace;
    // the fresh claim must survive retention pruning and the count cap.
    for (let index = 0; index < 201; index += 1) {
      const expiredVersion = `job-${index}:complete:${new Date(now - 800 * 60 * 60 * 1000).toISOString()}`;
      expect(
        claimRefreshReconciliation(
          userA,
          expiredVersion,
          ["plant-profile", `candidate-${index}`, "Monstera", "en"],
        ),
      ).toBe(true);
    }

    const freshVersion = `job-fresh:complete:${new Date(now).toISOString()}`;
    expect(claimRefreshReconciliation(userA, freshVersion, profileKey)).toBe(
      true,
    );
    // Still persisted (not evicted by the count cap): the same claim is
    // reconciled only once.
    expect(claimRefreshReconciliation(userA, freshVersion, profileKey)).toBe(
      false,
    );
  });

  it("claims refresh reconciliation once per exact profile query", () => {
    const profileKey = ["plant-profile", "candidate-1", "Monstera", "en"];

    expect(
      claimRefreshReconciliation(userA, "v1", profileKey),
    ).toBe(true);
    // Identical rerender and remount of the same key are suppressed.
    expect(claimRefreshReconciliation(userA, "v1", profileKey)).toBe(false);
    // A different language or candidate claims independently.
    expect(
      claimRefreshReconciliation(userA, "v1", [
        "plant-profile",
        "candidate-1",
        "Monstera",
        "es",
      ]),
    ).toBe(true);
    expect(
      claimRefreshReconciliation(userA, "v1", [
        "plant-profile",
        "candidate-2",
        "Monstera",
        "en",
      ]),
    ).toBe(true);
    // Another owner claims independently even for an identical key.
    expect(claimRefreshReconciliation(userB, "v1", profileKey)).toBe(true);
    // Remount after a successful claim stays suppressed via storage.
    resetRefreshReconciliationClaimsForTests();
    expect(claimRefreshReconciliation(userA, "v1", profileKey)).toBe(false);
  });
});

describe("activityQueryKey", () => {
  it("namespaces the shared prefix per user", () => {
    expect(activityQueryKey("u1")).toEqual(["enrichment-activity", "u1"]);
    expect(activityQueryKey("u2")).not.toEqual(activityQueryKey("u1"));
  });
});

describe("loadEnrichmentActivity pagination walker", () => {
  beforeEach(() => {
    mocks.getEnrichmentActivity.mockReset();
  });
  const pageItem = (
    id: string,
    status: EnrichmentActivityItem["status"],
    updatedAt: string,
  ): EnrichmentActivityItem => ({
    ...evidenceItem({ id, status, updated_at: updatedAt }),
  });

  it("aggregates all pages and sorts the merged list", async () => {
    const mock = mocks.getEnrichmentActivity;
    mock.mockReset();
    mock
      .mockResolvedValueOnce({
        items: [
          pageItem("b", "processing", "2026-08-02T00:00:00Z"),
          pageItem("a", "complete", "2026-08-01T00:00:00Z"),
        ],
        has_more: true,
        next_cursor: "cursor-2",
      })
      .mockResolvedValueOnce({
        items: [
          pageItem("c", "pending", "2026-08-03T00:00:00Z"),
        ],
        has_more: false,
        next_cursor: null,
      });

    const result = await loadEnrichmentActivity();

    expect(mock).toHaveBeenCalledTimes(2);
    expect(mock).toHaveBeenNthCalledWith(1, { limit: 100, cursor: undefined });
    expect(mock).toHaveBeenNthCalledWith(2, { limit: 100, cursor: "cursor-2" });
    expect((result.items ?? []).map((item) => item.id)).toEqual(["c", "b", "a"]);
    expect(result.has_more).toBe(false);
    expect(result.next_cursor).toBeNull();
  });

  it("keeps polling alive when only a later page holds active work", () => {
    // The interval function sees the aggregated list, not one page.
    const aggregated: { items: EnrichmentActivityItem[] } = {
      items: [
        pageItem("a", "complete", "2026-08-01T00:00:00Z"),
        pageItem("c", "processing", "2026-08-03T00:00:00Z"),
      ],
    };
    expect(activityHasActiveWork(aggregated.items)).toBe(true);
  });

  it("keeps the newest version of duplicate job ids across pages", async () => {
    const mock = mocks.getEnrichmentActivity;
    mock.mockReset();
    mock
      .mockResolvedValueOnce({
        items: [pageItem("a", "processing", "2026-08-01T00:00:00Z")],
        has_more: true,
        next_cursor: "cursor-2",
      })
      .mockResolvedValueOnce({
        items: [pageItem("a", "complete", "2026-08-01T01:00:00Z")],
        has_more: false,
        next_cursor: null,
      })
      // A terminal-only multi-page walk triggers one rescan (Phase 6), which
      // re-reads the same visible rows.
      .mockResolvedValueOnce({
        items: [pageItem("a", "complete", "2026-08-01T01:00:00Z")],
        has_more: false,
        next_cursor: null,
      });

    const result = await loadEnrichmentActivity();

    expect(result.items).toHaveLength(1);
    expect(result.items?.[0]?.status).toBe("complete");
  });

  it("throws on a repeated cursor instead of looping forever", async () => {
    const mock = mocks.getEnrichmentActivity;
    mock.mockReset();
    mock.mockResolvedValue({
      items: [],
      has_more: true,
      next_cursor: "same-cursor",
    });

    await expect(loadEnrichmentActivity()).rejects.toThrow(
      /Invalid activity pagination sequence/,
    );
    expect(mock).toHaveBeenCalledTimes(2);
  });

  it("fails when has_more is true without a next cursor", async () => {
    const mock = mocks.getEnrichmentActivity;
    mock.mockReset();
    mock.mockResolvedValue({
      items: [pageItem("a", "processing", "2026-08-01T00:00:00Z")],
      has_more: true,
      next_cursor: null,
    });

    await expect(loadEnrichmentActivity()).rejects.toThrow(
      /Invalid activity pagination sequence/,
    );
  });

  it("keeps the newest-instant duplicate id across offset timestamps", async () => {
    // First page instant (00:00:00Z) is newer than the second page's
    // (01:00:00+03:00 == 22:00:00Z), even though the literal string is larger.
    const mock = mocks.getEnrichmentActivity;
    mock.mockReset();
    mock
      .mockResolvedValueOnce({
        items: [
          pageItem("a", "processing", "2026-08-01T00:00:00+00:00"),
        ],
        has_more: true,
        next_cursor: "cursor-2",
      })
      .mockResolvedValueOnce({
        items: [
          pageItem("a", "complete", "2026-08-01T01:00:00+03:00"),
        ],
        has_more: false,
        next_cursor: null,
      });

    const result = await loadEnrichmentActivity();

    expect(result.items).toHaveLength(1);
    expect(result.items?.[0]?.status).toBe("processing");
  });

  it("rescans once when a multi-page walk found no active work", async () => {
    // Walk 1 has two pages, terminal-only; the rescan surfaces active work.
    const mock = mocks.getEnrichmentActivity;
    mock.mockReset();
    mock
      .mockResolvedValueOnce({
        items: [pageItem("a", "complete", "2026-08-01T00:00:00Z")],
        has_more: true,
        next_cursor: "cursor-2",
      })
      .mockResolvedValueOnce({
        items: [],
        has_more: false,
        next_cursor: null,
      })
      .mockResolvedValueOnce({
        items: [pageItem("c", "processing", "2026-08-01T00:00:00Z")],
        has_more: false,
        next_cursor: null,
      });

    const result = await loadEnrichmentActivity();

    expect(mock).toHaveBeenCalledTimes(3);
    expect(activityHasActiveWork(result.items)).toBe(true);
  });
});

describe("compareActivityDescending", () => {
  it("orders by absolute instant ahead of the literal timestamp string", () => {
    const itemNew = evidenceItem({
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      updated_at: "2026-08-01T00:00:00+00:00",
    });
    const itemOld = evidenceItem({
      id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      updated_at: "2026-08-01T01:00:00+03:00", // == 2026-07-31T22:00:00Z, earlier instant
    });

    expect(compareActivityDescending(itemNew, itemOld)).toBeLessThan(0);
    const sorted = [itemOld, itemNew].sort(compareActivityDescending);
    expect(sorted[0].id).toBe(itemNew.id);
  });

  it("breaks ties on descending id", () => {
    const first = evidenceItem({ id: "a", updated_at: "2026-08-01T00:00:00Z" });
    const second = evidenceItem({ id: "b", updated_at: "2026-08-01T00:00:00Z" });
    expect(compareActivityDescending(first, second)).toBeGreaterThan(0);
  });
});
