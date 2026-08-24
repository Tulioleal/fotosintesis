import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EnrichmentActivityItem } from "@/lib/api/client";
import { renderWithActivityProvider as renderWithQueryClient } from "@/test/renderWithQueryClient";
import { EnrichmentActivitySummary } from "./EnrichmentActivitySummary";

const mocks = vi.hoisted(() => ({
  getEnrichmentActivity: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    getEnrichmentActivity: mocks.getEnrichmentActivity,
  },
}));

const item = (
  overrides: Partial<EnrichmentActivityItem> = {},
): EnrichmentActivityItem => ({
  id: "11111111-1111-4111-8111-111111111111",
  job_type: "enrich_confirmed_plant",
  phase: "evidence",
  status: "processing",
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

describe("EnrichmentActivitySummary", () => {
  beforeEach(() => {
    mocks.getEnrichmentActivity.mockReset();
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [],
      has_more: false,
    });
  });

  it("renders nothing when there is no active or recent terminal work", async () => {
    const { container } = renderWithQueryClient(
      <EnrichmentActivitySummary />,
    );

    await waitFor(() => {
      expect(mocks.getEnrichmentActivity).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(container.textContent).toBe("");
    });
  });

  it("keeps stale activity visible with a retry action while a refetch fails", async () => {
    mocks.getEnrichmentActivity
      .mockResolvedValueOnce({
        items: [item({ status: "processing" })],
        has_more: false,
      })
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({
        items: [item({ status: "complete" })],
        has_more: false,
      });

    const { queryClient } = renderWithQueryClient(
      <EnrichmentActivitySummary />,
    );

    // Initial success renders the active row.
    expect(await screen.findByText("Monstera")).toBeInTheDocument();

    // A failing background refetch keeps the previous data and adds a
    // non-blocking warning with a retry action.
    await act(async () => {
      await queryClient.refetchQueries();
    });
    expect(
      await screen.findByText(/Conservamos el estado anterior/),
    ).toBeInTheDocument();
    expect(screen.getByText("Monstera")).toBeInTheDocument();

    // Retry succeeds and the row updates to the new state.
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await screen.findByText(/La evidencia está lista/);
    expect(
      screen.queryByText(/Conservamos el estado anterior/),
    ).not.toBeInTheDocument();
  });

  it("shows a compact active-work indicator with plant context and a profile link", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [item({ status: "processing" })],
    });

    renderWithQueryClient(<EnrichmentActivitySummary />);

    expect(
      await screen.findByRole("heading", { name: "Trabajo en segundo plano" }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/continúa en segundo plano/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Monstera")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Ver perfil de Monstera/ }),
    ).toHaveAttribute(
      "href",
      "/profiles/Monstera%20deliciosa?candidateId=candidate-1",
    );
  });

  it("lists recent terminal outcomes with distinct evidence copy", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        item({
          status: "complete",
          completed_at: "2026-08-01T00:00:00Z",
          result: {
            outcome: "complete",
            covered_count: 3,
            missing_count: 0,
            regenerated_section_count: 0,
            stale_section_count: 0,
            limitations: [],
          },
        }),
      ],
    });

    renderWithQueryClient(<EnrichmentActivitySummary />);

    expect(
      await screen.findByRole("heading", { name: "Actividad reciente" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/La evidencia está lista/)).toBeInTheDocument();
    expect(screen.getByText(/3 temas cubiertos/)).toBeInTheDocument();
  });

  it("never claims the profile is updated from evidence completion alone", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        item({
          status: "complete",
          completed_at: "2026-08-01T00:00:00Z",
          result: {
            outcome: "complete",
            covered_count: 1,
            missing_count: 0,
            regenerated_section_count: 0,
            stale_section_count: 0,
            limitations: [],
          },
        }),
        item({
          id: "22222222-2222-4222-8222-222222222222",
          job_type: "refresh_profile",
          phase: "profile_refresh",
          status: "processing",
          common_name: null,
        }),
      ],
    });

    renderWithQueryClient(<EnrichmentActivitySummary />);

    await screen.findByRole("heading", { name: "Trabajo en segundo plano" });
    expect(
      screen.getByText(/Actualizando las secciones del perfil/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/el perfil se actualizó/)).not.toBeInTheDocument();
  });

  it("renders a non-blocking error with a retry action", async () => {
    mocks.getEnrichmentActivity.mockRejectedValue(new Error("boom"));

    renderWithQueryClient(<EnrichmentActivitySummary />);

    expect(
      await screen.findByText(/No pudimos actualizar el estado del trabajo/),
    ).toBeInTheDocument();
    const retry = screen.getByRole("button", { name: "Reintentar" });
    const callsBefore = mocks.getEnrichmentActivity.mock.calls.length;
    fireEvent.click(retry);
    await waitFor(() => {
      expect(mocks.getEnrichmentActivity.mock.calls.length).toBeGreaterThan(
        callsBefore,
      );
    });
  });

  it("shows a loading placeholder before the first response", () => {
    mocks.getEnrichmentActivity.mockReturnValue(new Promise(() => undefined));

    renderWithQueryClient(<EnrichmentActivitySummary />);

    expect(
      screen.getByText("Cargando trabajo en segundo plano..."),
    ).toBeInTheDocument();
  });

  it("reports hidden active rows even when no terminal activity exists", async () => {
    const active = Array.from({ length: 7 }, (_, index) =>
      item({
        id: `44444444-4444-4444-8444-${String(index).padStart(12, "0")}`,
        status: "processing",
        updated_at: `2026-08-01T00:0${index}:00Z`,
      }),
    );
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: active,
      has_more: false,
    });

    renderWithQueryClient(<EnrichmentActivitySummary />);
    await screen.findByRole("heading", { name: "Trabajo en segundo plano" });

    expect(screen.getAllByRole("listitem")).toHaveLength(5);
    expect(screen.getByText(/Hay 2 actividades adicionales/)).toBeInTheDocument();
    expect(screen.queryByText("Actividad reciente")).not.toBeInTheDocument();
  });

  it("renders at most five rows per category with an accurate overflow count", async () => {
    const many = Array.from({ length: 7 }, (_, index) =>
      item({
        id: `22222222-2222-4222-8222-${String(index).padStart(12, "0")}`,
        status: "processing",
        updated_at: `2026-08-01T00:0${index}:00Z`,
      }),
    );
    const terminal = Array.from({ length: 7 }, (_, index) =>
      item({
        id: `33333333-3333-4333-8333-${String(index).padStart(12, "0")}`,
        status: "complete",
        updated_at: `2026-08-02T00:0${index}:00Z`,
      }),
    );
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [...many, ...terminal],
      has_more: false,
    });

    renderWithQueryClient(<EnrichmentActivitySummary />);

    await screen.findByRole("heading", { name: "Trabajo en segundo plano" });
    // Exactly five rows per category render (the intro copy also mentions
    // background work, so count list items, not text matches).
    expect(screen.getAllByRole("listitem")).toHaveLength(10);
    expect(screen.getByText("Actividad reciente")).toBeInTheDocument();
    expect(
      screen.getByText(/Hay 4 actividades adicionales/),
    ).toBeInTheDocument();
  });

  it("filters activity to the given plant context", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        item(),
        item({
          id: "33333333-3333-4333-8333-333333333333",
          scientific_name: "Ficus elastica",
          common_name: null,
          candidate_id: "candidate-2",
          species_key: "gbif:1|binomial:Ficus elastica",
        }),
      ],
    });

    renderWithQueryClient(
      <EnrichmentActivitySummary
        relatedTo={{ candidateIds: ["candidate-1"] }}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Trabajo en segundo plano" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Monstera")).toBeInTheDocument();
    expect(screen.queryByText("Ficus elastica")).not.toBeInTheDocument();
  });
});