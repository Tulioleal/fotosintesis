import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import {
  ENRICHMENT_POLL_INTERVAL_MS,
  ENRICHMENT_STALL_AFTER_MS,
  PlantProfileView,
  candidateEnrichmentQueryKey,
  enrichmentRefetchInterval,
  plantProfileQueryKey,
} from "./PlantProfileView";

const profile = {
  aliases: [{ country: null, language: "es", name: "Helecho", region: null }],
  binomial_name: "Nephrolepis exaltata",
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
    job: { ...jobBase, status, updated_at: new Date().toISOString() },
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
    expect(screen.getByRole("status")).toHaveTextContent("La búsqueda está en espera");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(mocks.getCandidateEnrichment).toHaveBeenCalledTimes(3);
    expect(screen.getByRole("status")).toHaveTextContent("Estamos consultando y validando fuentes");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByRole("status")).toHaveTextContent("La evidencia está lista");
    expect(mocks.getPlantProfile).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/Conservamos la ultima instantanea disponible/)).toBeInTheDocument();
    expect(screen.getByText("Riego moderado")).toBeInTheDocument();

    const terminalRequestCount = mocks.getCandidateEnrichment.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(mocks.getCandidateEnrichment).toHaveBeenCalledTimes(terminalRequestCount);
  });

  it("terminal observation invalidates only the profile query, not the status query", async () => {
    mocks.getCandidateEnrichment
      .mockResolvedValueOnce(enrichment("pending"))
      .mockResolvedValue(enrichment("complete"));
    const { queryClient } = renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await screen.findByText(/La búsqueda está en espera/);

    await queryClient.refetchQueries({
      queryKey: candidateEnrichmentQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
      exact: true,
    });

    await screen.findByText(/La evidencia está lista/);
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(1));
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: plantProfileQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
      exact: true,
    });
    expect(invalidate).not.toHaveBeenCalledWith({
      queryKey: candidateEnrichmentQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
      exact: true,
    });
    expect(screen.getByText("La evidencia encontrada puede tardar unos instantes más en reflejarse en las secciones del perfil.")).toBeInTheDocument();
  });

  it("makes no further status request after a terminal observation", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment
      .mockResolvedValueOnce(enrichment("processing"))
      .mockResolvedValueOnce(enrichment("complete"))
      .mockResolvedValue(enrichment("complete"));

    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(screen.getByText(/Estamos consultando y validando fuentes/)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_POLL_INTERVAL_MS);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText(/La evidencia está lista/)).toBeInTheDocument();

    const callsAfterTerminal = mocks.getCandidateEnrichment.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(mocks.getCandidateEnrichment.mock.calls.length).toBe(callsAfterTerminal);
  });

  it("renders policy, bounded partial coverage and snapshot sources as separate state", async () => {
    mocks.getCandidateEnrichment.mockResolvedValue(partialEnrichment);
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    expect(await screen.findByText(/Encontramos evidencia útil, pero faltan algunos temas · Política v1/)).toBeInTheDocument();
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

  it.each([
    ["retry_exhausted", "Se agotaron los reintentos de ampliar la evidencia."],
    ["workflow_incomplete", "El proceso de ampliacion quedo incompleto."],
    ["indexing_deferred", "La evidencia se guardo pero la indexacion quedo pendiente."],
  ])("renders distinct text for the %s operational limitation", async (limitation, copy) => {
    mocks.getCandidateEnrichment.mockResolvedValue({
      ...enrichment("partial"),
      job: {
        ...jobBase,
        status: "partial" as const,
        result: {
          acquisition_avoided: false,
          covered_aspects: ["light_exposure"],
          covered_count: 1,
          limitations: [limitation],
          missing_aspects: [],
          missing_count: 0,
          outcome: "partial" as const,
          policy_version: 1,
        },
      },
    });
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    expect(await screen.findByText((_, element) =>
      element?.tagName === "P" && element.textContent?.includes(copy) === true,
    )).toBeInTheDocument();
  });

  it("keeps exactly one polite live region for enrichment status", async () => {
    mocks.getCandidateEnrichment.mockResolvedValue(enrichment("processing"));
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    await screen.findByText(/Estamos consultando y validando fuentes/);
    const liveRegions = screen.getAllByRole("status");
    expect(liveRegions).toHaveLength(1);
    expect(liveRegions[0]).toHaveAttribute("aria-live", "polite");
  });

  it("reports polling errors with alert semantics without duplicate status nodes", async () => {
    mocks.getCandidateEnrichment.mockRejectedValue(new Error("Estado temporalmente no disponible."));
    mocks.getPlantProfile.mockResolvedValue({ ...profile, enrichment: enrichment("pending") });
    const { container } = renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Estado temporalmente no disponible.");
    // Exactly one polite status region from the fallback, never duplicated by
    // the polling error, which keeps alert semantics.
    expect(container.querySelectorAll('[aria-live="polite"]')).toHaveLength(1);
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });

  it("resets stalled observation state when the candidate context changes", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment.mockResolvedValue(enrichment("processing"));

    const first = renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + ENRICHMENT_POLL_INTERVAL_MS + 1_000);
    });
    expect(screen.getByText(/Está tardando más de lo esperado/)).toBeInTheDocument();
    first.unmount();

    mocks.getCandidateEnrichment.mockClear().mockResolvedValue(enrichment("pending"));
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-2" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    // The new candidate receives its own bounded window: no stale stall text.
    expect(screen.queryByText(/Está tardando más de lo esperado/)).not.toBeInTheDocument();
    expect(screen.getByText(/La búsqueda está en espera/)).toBeInTheDocument();
  });

  it("issues exactly one request per manual retry and disables the control while checking", async () => {
    vi.useFakeTimers();
    const pending: Array<(value: unknown) => void> = [];
    mocks.getCandidateEnrichment.mockImplementation(
      () => new Promise((resolve) => { pending.push(resolve); }),
    );

    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
      for (const resolve of pending.splice(0)) resolve(enrichment("processing"));
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + ENRICHMENT_POLL_INTERVAL_MS + 1_000);
    });
    const retry = screen.getByRole("button", { name: "Revisar estado" });
    const callsBefore = mocks.getCandidateEnrichment.mock.calls.length;
    fireEvent.click(retry);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(mocks.getCandidateEnrichment.mock.calls.length).toBe(callsBefore + 1);
    expect(screen.getByRole("button", { name: "Revisando estado..." })).toBeDisabled();

    await act(async () => {
      for (const resolve of pending.splice(0)) resolve(enrichment("processing"));
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(screen.getByRole("button", { name: "Revisar estado" })).not.toBeDisabled();
  });

  it("links to the assistant with candidate, binomial and scientific context", async () => {
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    const link = await screen.findByRole("link", { name: "Preguntar al asistente" });
    expect(link).toHaveAttribute(
      "href",
      "/assistant?plant=Helecho&binomial=Nephrolepis%20exaltata&scientific=Nephrolepis%20exaltata&candidate=candidate-1",
    );
  });

  it("renders section status badges for stale and partial sections", async () => {
    mocks.getPlantProfile.mockResolvedValue({
      ...profile,
      section_status: [
        { generated_at: "2026-01-01T00:00:00Z", policy_version: 1, section: "care", status: "stale" },
        { generated_at: "2026-01-01T00:00:00Z", policy_version: 1, section: "description", status: "partial" },
      ],
    });
    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    expect(await screen.findByText("Actualizacion pendiente")).toBeInTheDocument();
    expect(screen.getByText("Evidencia parcial")).toBeInTheDocument();
    expect(screen.getAllByRole("note")).toHaveLength(2);
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

    expect(await screen.findByText(/No pudimos completar la búsqueda de evidencia/)).toBeInTheDocument();
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

  it("stops automatic polling after the stalled threshold", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment.mockResolvedValue(enrichment("processing"));

    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(screen.getByText(/Estamos consultando y validando fuentes/)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + ENRICHMENT_POLL_INTERVAL_MS + 1_000);
    });
    expect(screen.getByText(/Está tardando más de lo esperado/)).toBeInTheDocument();

    const callsBefore = mocks.getCandidateEnrichment.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(mocks.getCandidateEnrichment.mock.calls.length).toBe(callsBefore);
  });

  it("keeps the profile fallback active while status requests fail, but stops polling at the deadline", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment.mockRejectedValue(new Error("Estado temporalmente no disponible."));
    mocks.getPlantProfile.mockResolvedValue({ ...profile, enrichment: enrichment("processing") });

    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    // The profile fallback keeps the active status visible while the status
    // query keeps failing.
    expect(screen.getByRole("status")).toHaveTextContent("Estamos consultando y validando fuentes");
    expect(screen.getByRole("alert")).toHaveTextContent("Estado temporalmente no disponible.");

    // Polling continues through failures but the bounded deadline still stops it.
    const callsBefore = mocks.getCandidateEnrichment.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_POLL_INTERVAL_MS * 3);
    });
    expect(mocks.getCandidateEnrichment.mock.calls.length).toBeGreaterThan(callsBefore);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + 1_000);
    });
    expect(screen.getByText(/Está tardando más de lo esperado/)).toBeInTheDocument();

    const terminalCalls = mocks.getCandidateEnrichment.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(mocks.getCandidateEnrichment.mock.calls.length).toBe(terminalCalls);
  });

  it("clears stalled text immediately when the same candidate moves to a new job", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment.mockResolvedValue(enrichment("processing"));

    const { queryClient } = renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + ENRICHMENT_POLL_INTERVAL_MS + 1_000);
    });
    expect(screen.getByText(/Está tardando más de lo esperado/)).toBeInTheDocument();

    act(() => {
      queryClient.setQueryData(
        candidateEnrichmentQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
        {
          ...enrichment("processing"),
          job: {
            ...jobBase,
            id: "job-2",
            status: "processing",
          },
        },
      );
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(screen.queryByText(/Está tardando más de lo esperado/)).not.toBeInTheDocument();
  });

  it("allows polling again for a new active job after a terminal job", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment.mockResolvedValueOnce(enrichment("complete"));

    const { queryClient } = renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(screen.getByText(/La evidencia está lista/)).toBeInTheDocument();

    const callsAtTerminal = mocks.getCandidateEnrichment.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    // No further requests after the terminal job.
    expect(mocks.getCandidateEnrichment.mock.calls.length).toBe(callsAtTerminal);

    // A brand-new active job for the same candidate resumes polling.
    act(() => {
      queryClient.setQueryData(
        candidateEnrichmentQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
        {
          ...enrichment("processing"),
          job: {
            ...jobBase,
            id: "job-2",
            status: "processing",
          },
        },
      );
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    const callsBeforeNewJob = mocks.getCandidateEnrichment.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_POLL_INTERVAL_MS * 2);
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(mocks.getCandidateEnrichment.mock.calls.length).toBeGreaterThan(callsBeforeNewJob);
  });

  it("does not reset the observation deadline on lease-only updated_at changes", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment.mockResolvedValue(enrichment("processing"));

    const { queryClient } = renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    // Repeated identical active responses with refreshed lease timestamps must
    // not extend the deadline.
    for (const stamp of ["2026-01-01T00:00:01Z", "2026-01-01T00:00:02Z", "2026-01-01T00:00:03Z"]) {
      act(() => {
        queryClient.setQueryData(
          candidateEnrichmentQueryKey("candidate-1", "Nephrolepis exaltata", "en"),
          {
            ...enrichment("processing"),
            job: { ...jobBase, id: "job-1", status: "processing", updated_at: stamp },
          },
        );
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
    }
    expect(screen.queryByText(/Está tardando más de lo esperado/)).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + ENRICHMENT_POLL_INTERVAL_MS + 1_000);
    });
    expect(screen.getByText(/Está tardando más de lo esperado/)).toBeInTheDocument();
  });

  it("remounting does not hide an already stalled job", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment.mockResolvedValue(enrichment("processing"));

    const first = renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + ENRICHMENT_POLL_INTERVAL_MS + 1_000);
    });
    expect(screen.getByText(/Está tardando más de lo esperado/)).toBeInTheDocument();
    first.unmount();

    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + ENRICHMENT_POLL_INTERVAL_MS + 1_000);
    });
    expect(screen.getByText(/Está tardando más de lo esperado/)).toBeInTheDocument();
  });

  it("manual retry performs exactly one immediate refetch", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment.mockResolvedValue(enrichment("processing"));

    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + ENRICHMENT_POLL_INTERVAL_MS + 1_000);
    });
    expect(screen.getByRole("button", { name: "Revisar estado" })).toBeInTheDocument();

    const callsBefore = mocks.getCandidateEnrichment.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Revisar estado" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(mocks.getCandidateEnrichment.mock.calls.length).toBe(callsBefore + 1);
  });

  it("manual retry does not move focus", async () => {
    vi.useFakeTimers();
    mocks.getCandidateEnrichment.mockResolvedValue(enrichment("processing"));

    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ENRICHMENT_STALL_AFTER_MS + ENRICHMENT_POLL_INTERVAL_MS + 1_000);
    });
    const retry = screen.getByRole("button", { name: "Revisar estado" });
    retry.focus();
    expect(retry).toHaveFocus();

    fireEvent.click(retry);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(retry).toHaveFocus();
  });

  it("keeps profile actions keyboard reachable while enrichment runs", async () => {
    mocks.getCandidateEnrichment.mockResolvedValue(enrichment("processing"));

    renderWithQueryClient(
      <PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />,
    );

    expect(await screen.findByText(/Estamos consultando y validando fuentes/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Preguntar al asistente" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Crear recordatorio" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Agregar a Mi Jardin" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar planta confirmada" })).toBeInTheDocument();
  });
});
