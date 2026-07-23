import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import {
  candidateEnrichmentQueryKey,
  enrichmentRefetchInterval,
  plantProfileQueryKey,
  PlantProfileView,
} from "./PlantProfileView";

const profile = {
  aliases: [{ country: null, language: "es", name: "Helecho", region: null }],
  common_name: "Helecho",
  confidence: 0.9,
  id: "profile-1",
  limitations: [],
  scientific_name: "Nephrolepis exaltata",
  sections: { care: ["Riego moderado"] },
  selected_alias: "Helecho",
  sources: [{ confidence: 0.9, domain: "example.org", title: "Guia original", url: "https://example.org/guia" }],
};

const jobBase = {
  attempt_count: 0,
  completed_at: null,
  created_at: "2026-01-01T00:00:00Z",
  id: "job-1",
  job_type: "enrich_confirmed_plant" as const,
  last_error: null,
  max_attempts: 3,
  result: null,
  updated_at: "2026-01-01T00:00:00Z",
};

function enrichment(status: "pending" | "processing" | "complete" | "partial" | "failed") {
  return {
    candidate_id: "candidate-1",
    policy_version: 1,
    job: { ...jobBase, status },
  };
}

const partialEnrichment = {
  ...enrichment("partial"),
  job: {
    ...jobBase,
    status: "partial" as const,
    result: {
      acquisition_avoided: false,
      covered_aspects: ["light_exposure", "future_aspect"],
      covered_count: 2,
      limitations: ["missing_required_aspects" as const],
      missing_aspects: ["toxicity_pet_safety"],
      missing_count: 1,
      outcome: "partial" as const,
      policy_version: 1,
    },
  },
};

const savedPlant = {
  active_reminders: 0,
  confirmed_candidate_id: "candidate-1",
  created_at: "2026-01-01T00:00:00Z",
  custom_data: {},
  id: "garden-1",
  image_path: null,
  location: "Balcon",
  nickname: "Mi helecho",
  notes: "Cerca de la ventana",
  profile,
};

const mocks = vi.hoisted(() => ({
  getCandidateEnrichment: vi.fn(),
  getPlantProfile: vi.fn(),
  saveGardenPlant: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    getCandidateEnrichment: mocks.getCandidateEnrichment,
    getPlantProfile: mocks.getPlantProfile,
    saveGardenPlant: mocks.saveGardenPlant,
  },
}));

describe("PlantProfileView", () => {
  beforeEach(() => {
    mocks.getCandidateEnrichment.mockReset().mockResolvedValue(enrichment("pending"));
    mocks.getPlantProfile.mockReset().mockResolvedValue(profile);
    mocks.saveGardenPlant.mockReset().mockResolvedValue(savedPlant);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("uses candidate, scientific name and language scoped query keys and polls pending/processing only", async () => {
    const { queryClient } = renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await screen.findByText("Riego moderado");

    const queries = queryClient.getQueryCache().getAll();
    expect(queries.map((query) => query.queryKey)).toEqual(expect.arrayContaining([
      plantProfileQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
      candidateEnrichmentQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
    ]));
    expect(enrichmentRefetchInterval({ state: { data: enrichment("pending") } } as never)).toBe(3_000);
    expect(enrichmentRefetchInterval({ state: { data: enrichment("processing") } } as never)).toBe(3_000);
    expect(enrichmentRefetchInterval({ state: { data: enrichment("complete") } } as never)).toBe(false);
    expect(enrichmentRefetchInterval({ state: { data: enrichment("partial") } } as never)).toBe(false);
    expect(enrichmentRefetchInterval({ state: { data: enrichment("failed") } } as never)).toBe(false);
    expect(enrichmentRefetchInterval({ state: { data: undefined } } as never, enrichment("processing"))).toBe(3_000);
    expect(enrichmentRefetchInterval(
      { state: { data: enrichment("complete"), status: "error" } },
      enrichment("pending"),
    )).toBe(false);
  });

  it("recovers status polling from the profile fallback, retains the snapshot after terminal refetch failure, and stops", async () => {
    vi.useFakeTimers();
    mocks.getPlantProfile
      .mockResolvedValueOnce({ ...profile, enrichment: enrichment("pending") })
      .mockRejectedValueOnce(new Error("Perfil temporalmente no disponible."));
    mocks.getCandidateEnrichment
      .mockRejectedValueOnce(new Error("Estado temporalmente no disponible."))
      .mockResolvedValueOnce(enrichment("pending"))
      .mockResolvedValueOnce(enrichment("processing"))
      .mockResolvedValue(enrichment("complete"));

    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(screen.getByText("Riego moderado")).toBeInTheDocument();
    expect(screen.getByText("Estado temporalmente no disponible.")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(mocks.getCandidateEnrichment).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("status")).toHaveTextContent("En espera");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(mocks.getCandidateEnrichment).toHaveBeenCalledTimes(3);
    expect(screen.getByRole("status")).toHaveTextContent("Buscando evidencia");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByRole("status")).toHaveTextContent("Evidencia completa");
    expect(mocks.getPlantProfile).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/Conservamos la ultima instantanea disponible/)).toBeInTheDocument();
    expect(screen.getByText("Riego moderado")).toBeInTheDocument();

    const terminalRequestCount = mocks.getCandidateEnrichment.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(mocks.getCandidateEnrichment).toHaveBeenCalledTimes(terminalRequestCount);
  });

  it("stops at a newly observed terminal state and invalidates status and snapshot metadata once", async () => {
    mocks.getCandidateEnrichment
      .mockResolvedValueOnce(enrichment("pending"))
      .mockResolvedValue(enrichment("complete"));
    const { queryClient } = renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await screen.findByText(/En espera/);

    await queryClient.refetchQueries({
      queryKey: candidateEnrichmentQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
      exact: true,
    });

    await screen.findByText(/Evidencia completa/);
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(2));
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: candidateEnrichmentQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
      exact: true,
    });
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: plantProfileQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
      exact: true,
    });
    expect(screen.getByText("Este estado no regenera las secciones del perfil guardado.")).toBeInTheDocument();
  });

  it("renders policy, bounded partial coverage and snapshot sources as separate state", async () => {
    mocks.getCandidateEnrichment.mockResolvedValue(partialEnrichment);
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    expect(await screen.findByText(/Evidencia parcial · Politica v1/)).toBeInTheDocument();
    expect(screen.getByText((_, element) =>
      element?.tagName === "P" && element.textContent?.includes("Aspectos cubiertos (2): Luz, future_aspect") === true,
    )).toBeInTheDocument();
    expect(screen.getByText((_, element) =>
      element?.tagName === "P" && element.textContent?.includes("Aspectos pendientes (1): Seguridad para mascotas") === true,
    )).toBeInTheDocument();
    expect(screen.getByText("Riego moderado")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fuentes de esta instantanea guardada" })).toBeInTheDocument();
    expect(screen.getByText(/La evidencia nueva se informa por separado/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Guia original" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Agregar a Mi Jardin" })).toBeInTheDocument();
  });

  it("keeps the persisted profile and actions available after failed enrichment", async () => {
    mocks.getCandidateEnrichment.mockResolvedValue({
      ...enrichment("failed"),
      job: {
        ...jobBase,
        status: "failed",
        last_error: { category: "insufficient_evidence", retryable: false },
      },
    });
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    expect(await screen.findByText(/No se pudo ampliar la evidencia/)).toBeInTheDocument();
    expect(screen.getByText(/No se encontro evidencia suficiente/)).toBeInTheDocument();
    expect(screen.getByText("Riego moderado")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Preguntar al asistente" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar planta confirmada" })).toBeInTheDocument();
  });

  it("saves a confirmed plant and reports save failures without replacing the profile", async () => {
    mocks.saveGardenPlant.mockRejectedValue(new Error("No pudimos guardar la planta."));
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    fireEvent.change(await screen.findByPlaceholderText("Nombre personalizado"), { target: { value: "Mi helecho" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar planta confirmada" }));

    expect(await screen.findByText("No pudimos guardar la planta.")).toBeInTheDocument();
    expect(screen.getByText("Riego moderado")).toBeInTheDocument();
  });

  it("reports enrichment status errors separately from a readable profile", async () => {
    mocks.getCandidateEnrichment.mockRejectedValue(new Error("Estado temporalmente no disponible."));
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    expect(await screen.findByText("Estado temporalmente no disponible.")).toBeInTheDocument();
    expect(screen.getByText("Riego moderado")).toBeInTheDocument();
  });

  it("renders a fatal profile error when no snapshot was retained", async () => {
    mocks.getPlantProfile.mockRejectedValue(new Error("No pudimos cargar el perfil."));
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar el perfil.");
    expect(screen.queryByText("Riego moderado")).not.toBeInTheDocument();
  });

  it("does not request profile or status without confirmed candidate context", () => {
    renderWithQueryClient(<PlantProfileView scientificName="Nephrolepis exaltata" />);

    expect(screen.getByText("Para ver el perfil, confirma primero una candidata validada desde Identificar.")).toBeInTheDocument();
    expect(mocks.getPlantProfile).not.toHaveBeenCalled();
    expect(mocks.getCandidateEnrichment).not.toHaveBeenCalled();
  });
});
