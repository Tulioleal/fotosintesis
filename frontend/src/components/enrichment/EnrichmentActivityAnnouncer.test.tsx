import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EnrichmentActivityItem } from "@/lib/api/client";
import {
  activityQueryKey,
  loadAnnouncedOutcomes,
  rememberAnnouncedOutcome,
} from "@/lib/enrichment-activity";
import { TEST_USER_ID, setMockSessionUser } from "@/test/mock-session";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { EnrichmentActivityProvider } from "./EnrichmentActivityProvider";
import { EnrichmentActivityAnnouncer } from "./EnrichmentActivityAnnouncer";

const mocks = vi.hoisted(() => ({
  getEnrichmentActivity: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    getEnrichmentActivity: mocks.getEnrichmentActivity,
  },
}));

const terminalItem = (
  overrides: Partial<EnrichmentActivityItem> = {},
): EnrichmentActivityItem => ({
  id: "11111111-1111-4111-8111-111111111111",
  job_type: "enrich_confirmed_plant",
  phase: "evidence",
  status: "complete",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  completed_at: "2026-08-01T00:00:00Z",
  species_key: "gbif:2878688|binomial:Monstera deliciosa",
  scientific_name: "Monstera deliciosa",
  common_name: "Monstera",
  candidate_id: "candidate-1",
  result: {
    outcome: "complete",
    covered_count: 1,
    missing_count: 0,
    regenerated_section_count: 0,
    stale_section_count: 0,
    limitations: [],
  },
  last_error: null,
  ...overrides,
});

const viewCleanup: Array<() => void> = [];

afterEach(() => {
  viewCleanup.splice(0).forEach((fn) => fn());
});

describe("EnrichmentActivityAnnouncer", () => {
  beforeEach(() => {
    setMockSessionUser(TEST_USER_ID);
    window.sessionStorage.clear();
    mocks.getEnrichmentActivity.mockReset();
  });

  it("announces a newly observed complete outcome with a profile link", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [terminalItem()],
      has_more: false,
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);

    expect(
      await screen.findByText(/La evidencia está lista/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Ver perfil de Monstera/ }),
    ).toHaveAttribute(
      "href",
      "/profiles/Monstera%20deliciosa?candidateId=candidate-1",
    );
  });

  it("announces partial with bounded missing counts and never claims a full profile", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        terminalItem({
          status: "partial",
          result: {
            outcome: "partial",
            covered_count: 1,
            missing_count: 2,
            regenerated_section_count: 0,
            stale_section_count: 0,
            limitations: ["missing_required_aspects"],
          },
        }),
      ],
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);

    expect(
      await screen.findByText(/Encontramos evidencia útil/),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 tema cubierto/)).toBeInTheDocument();
    expect(screen.getByText(/2 pendientes/)).toBeInTheDocument();
  });

  it("announces evidence failure with evidence-specific recovery guidance", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        terminalItem({
          status: "failed",
          result: null,
          last_error: { category: "attempts_exhausted", retryable: false },
        }),
      ],
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);

    expect(
      await screen.findByText(/No pudimos ampliar la evidencia/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/volver a intentarlo más adelante/),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("uses refresh-specific guidance for refresh failures", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        terminalItem({
          job_type: "refresh_profile",
          phase: "profile_refresh",
          status: "failed",
          result: null,
          last_error: { category: "provider_transient", retryable: true },
        }),
      ],
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);

    expect(
      await screen.findByText(/No pudimos actualizar el perfil/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/El perfil sigue disponible/),
    ).toBeInTheDocument();
  });

  it("shows the newest outcome first when several arrive together and advances through every queued item on dismissal", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        terminalItem({
          id: "aaaaaaaa-1111-4111-8111-111111111111",
          status: "complete",
          updated_at: "2026-08-01T00:01:00Z",
        }),
        terminalItem({
          id: "bbbbbbbb-2222-4222-8222-222222222222",
          status: "partial",
          updated_at: "2026-08-01T00:02:00Z",
          result: {
            outcome: "partial",
            covered_count: 1,
            missing_count: 1,
            regenerated_section_count: 0,
            stale_section_count: 0,
            limitations: [],
          },
        }),
        terminalItem({
          id: "cccccccc-3333-4333-8333-333333333333",
          status: "failed",
          updated_at: "2026-08-01T00:03:00Z",
          result: null,
          last_error: { category: "attempts_exhausted", retryable: false },
        }),
      ],
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);

    // Newest first.
    expect(
      await screen.findByText(/No pudimos ampliar la evidencia/),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(
      await screen.findByText(/Encontramos evidencia útil/),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(
      await screen.findByText(/La evidencia está lista/),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not duplicate queue items when the same response rerenders", async () => {
    const payload = {
      has_more: false,
      items: [terminalItem()],
    };
    mocks.getEnrichmentActivity.mockResolvedValue(payload);

    const view = renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);
    await screen.findByText(/La evidencia está lista/);

    // Force rerenders while the identical data object stays cached.
    view.rerender(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);
    view.rerender(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);

    expect(
      screen.getAllByText(/La evidencia está lista/).length,
    ).toBe(1);
  });

  it("does not announce an outcome already announced this session", async () => {
    rememberAnnouncedOutcome(
      TEST_USER_ID,
      "11111111-1111-4111-8111-111111111111:complete:2026-08-01T00:00:00Z",
    );
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [terminalItem()],
      has_more: false,
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);

    await screen.findByTestId("announcer-settled");
    expect(screen.queryByText(/La evidencia está lista/)).not.toBeInTheDocument();
  });

  it("does not let one owner's announcements suppress another owner's", async () => {
    // Owner A already saw this exact outcome version.
    rememberAnnouncedOutcome(
      "user-aaaaaaaa",
      "11111111-1111-4111-8111-111111111111:complete:2026-08-01T00:00:00Z",
    );

    // Owner B signs in on the same browser session.
    setMockSessionUser("user-bbbbbbbb");
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [terminalItem()],
      has_more: false,
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);

    expect(await screen.findByText(/La evidencia está lista/)).toBeInTheDocument();
  });

  it("clears prior-owner announcements when the session identity changes", async () => {
    setMockSessionUser("user-aaaaaaaa");
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [terminalItem()],
      has_more: false,
    });

    const view = renderWithQueryClient(
      <EnrichmentActivityProvider>
        <EnrichmentActivityAnnouncer />
      </EnrichmentActivityProvider>,
    );
    expect(await screen.findByText(/La evidencia está lista/)).toBeInTheDocument();

    // Same mounted tree, identity flips to B.
    setMockSessionUser("user-bbbbbbbb");
    view.rerender(
      <EnrichmentActivityProvider>
        <EnrichmentActivityAnnouncer />
      </EnrichmentActivityProvider>,
    );

    await waitFor(() => {
      expect(screen.queryByText(/La evidencia está lista/)).not.toBeInTheDocument();
    });
    // B's storage namespace must not contain A's version.
    expect(loadAnnouncedOutcomes("user-bbbbbbbb").size).toBe(0);
  });

  it("loads the signed-in namespace when transitioning from anonymous", async () => {
    const version = "11111111-1111-4111-8111-111111111111:complete:2026-08-01T00:00:00Z";
    rememberAnnouncedOutcome(TEST_USER_ID, version);

    setMockSessionUser(undefined);
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [terminalItem()],
      has_more: false,
    });
    const view = renderWithQueryClient(
      <EnrichmentActivityProvider>
        <EnrichmentActivityAnnouncer />
      </EnrichmentActivityProvider>,
    );
    await screen.findByTestId("announcer-settled");
    expect(screen.queryByText(/La evidencia está lista/)).not.toBeInTheDocument();

    // Identity arrives; the pre-seeded outcome must not reannounce.
    setMockSessionUser(TEST_USER_ID);
    view.rerender(
      <EnrichmentActivityProvider>
        <EnrichmentActivityAnnouncer />
      </EnrichmentActivityProvider>,
    );
    await screen.findByTestId("announcer-settled");
    expect(screen.queryByText(/La evidencia está lista/)).not.toBeInTheDocument();
  });

  it("issues no activity request before an authenticated identity exists", async () => {
    setMockSessionUser(undefined);
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [],
      has_more: false,
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);
    await screen.findByTestId("announcer-settled");

    expect(mocks.getEnrichmentActivity).not.toHaveBeenCalled();
  });

  it("persists only versions that were actually displayed", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        terminalItem({
          id: "aaaaaaaa-1111-4111-8111-111111111111",
          status: "complete",
          updated_at: "2026-08-01T00:01:00Z",
        }),
        terminalItem({
          id: "cccccccc-3333-4333-8333-333333333333",
          status: "failed",
          updated_at: "2026-08-01T00:03:00Z",
          result: null,
          last_error: { category: "attempts_exhausted", retryable: false },
        }),
      ],
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);
    await screen.findByText(/No pudimos ampliar la evidencia/);

    // The displayed version persists once the effect has flushed.
    await vi.waitFor(() => {
      expect(loadAnnouncedOutcomes(TEST_USER_ID).has(
        "cccccccc-3333-4333-8333-333333333333:failed:2026-08-01T00:03:00Z",
      )).toBe(true);
    });
    expect(loadAnnouncedOutcomes(TEST_USER_ID).has(
      "aaaaaaaa-1111-4111-8111-111111111111:complete:2026-08-01T00:01:00Z",
    )).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    await screen.findByText(/La evidencia está lista/);

    await vi.waitFor(() => {
      expect(loadAnnouncedOutcomes(TEST_USER_ID).has(
        "aaaaaaaa-1111-4111-8111-111111111111:complete:2026-08-01T00:01:00Z",
      )).toBe(true);
    });
  });

  it("breaks equal-timestamp ties by descending job id", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        terminalItem({
          id: "11111111-1111-4111-8111-111111111111",
          common_name: "Alpha plant",
          updated_at: "2026-08-01T00:05:00Z",
        }),
        terminalItem({
          id: "22222222-2222-4222-8222-222222222222",
          status: "partial",
          scientific_name: "Beta speciosa",
          common_name: null,
          updated_at: "2026-08-01T00:05:00Z",
          result: {
            outcome: "partial",
            covered_count: 1,
            missing_count: 1,
            regenerated_section_count: 0,
            stale_section_count: 0,
            limitations: [],
          },
        }),
      ],
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);

    // Higher id first.
    expect(
      await screen.findByText(/Encontramos evidencia útil/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Beta speciosa/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(await screen.findByText(/La evidencia está lista/))
      .toBeInTheDocument();
  });

  it("keeps every announcement accessible with a profile link", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        terminalItem({
          id: "cccccccc-3333-4333-8333-333333333333",
          status: "failed",
          updated_at: "2026-08-01T00:03:00Z",
          result: null,
          last_error: { category: "attempts_exhausted", retryable: false },
        }),
      ],
    });

    renderWithQueryClient(<EnrichmentActivityProvider><EnrichmentActivityAnnouncer /></EnrichmentActivityProvider>);
    await screen.findByRole("alert");
    expect(
      screen.getByRole("link", { name: /Ver perfil de Monstera/ }),
    ).toHaveAttribute(
      "href",
      "/profiles/Monstera%20deliciosa?candidateId=candidate-1",
    );
  });
});

describe("EnrichmentActivityAnnouncer queue ordering and boundaries", () => {
  beforeEach(() => {
    setMockSessionUser(TEST_USER_ID);
    window.sessionStorage.clear();
    mocks.getEnrichmentActivity.mockReset();
  });

  function renderedItem(
    id: string,
    status: EnrichmentActivityItem["status"],
    updatedAt: string,
    overrides: Partial<EnrichmentActivityItem> = {},
  ): EnrichmentActivityItem {
    return terminalItem({ id, status, updated_at: updatedAt, ...overrides });
  }

  it("keeps the displayed item fixed while newer arrivals overtake older queued ones", async () => {
    const { QueryClient } = await import("@tanstack/react-query");

    const A = renderedItem(
      "11111111-1111-4111-8111-111111111111",
      "complete",
      "2026-08-01T00:01:00Z",
      { common_name: "Plant A" },
    );
    const B = renderedItem(
      "22222222-2222-4222-8222-222222222222",
      "partial",
      "2026-08-01T00:02:00Z",
      { common_name: "Plant B" },
    );
    const C = renderedItem(
      "33333333-3333-4333-8333-333333333333",
      "failed",
      "2026-08-01T00:05:00Z",
      { common_name: "Plant C" },
    );

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    renderWithQueryClient(
      <EnrichmentActivityProvider>
        <EnrichmentActivityAnnouncer />
      </EnrichmentActivityProvider>,
      queryClient,
    );

    queryClient.setQueryData(activityQueryKey(TEST_USER_ID), {
      items: [A],
      has_more: false,
      next_cursor: null,
    });
    expect(await screen.findByText(/La evidencia está lista/)).toBeInTheDocument();

    // B waits behind A; then C arrives newer than B.
    queryClient.setQueryData(activityQueryKey(TEST_USER_ID), {
      items: [A, B],
      has_more: false,
      next_cursor: null,
    });
    queryClient.setQueryData(activityQueryKey(TEST_USER_ID), {
      items: [A, B, C],
      has_more: false,
      next_cursor: null,
    });

    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(await screen.findByText(/No pudimos ampliar la evidencia/))
      .toBeInTheDocument(); // C before B
    expect(screen.getByText(/Plant C/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(await screen.findByText(/Encontramos evidencia útil/))
      .toBeInTheDocument(); // B last
  });

  it("never invalidates any queries for any announcement", async () => {
    const { QueryClient } = await import("@tanstack/react-query");

    for (const status of [
      "complete",
      "partial",
      "failed",
    ] as EnrichmentActivityItem["status"][]) {
      window.sessionStorage.clear();
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
      });
      const invalidate = vi.spyOn(queryClient, "invalidateQueries");
      mocks.getEnrichmentActivity.mockResolvedValue({
        items: [
          renderedItem(
            "44444444-4444-4444-8444-444444444444",
            status,
            "2026-08-02T00:00:00Z",
          ),
        ],
        has_more: false,
        next_cursor: null,
      });

      viewCleanup.push(
        renderWithQueryClient(
          <EnrichmentActivityProvider>
            <EnrichmentActivityAnnouncer />
          </EnrichmentActivityProvider>,
          queryClient,
        ).unmount,
      );

      await screen.findByText(
        status === "complete"
          ? /La evidencia está lista/
          : status === "partial"
            ? /Encontramos evidencia útil/
            : /No pudimos ampliar la evidencia/,
      );
      expect(invalidate).not.toHaveBeenCalled();
    }
  });
});
