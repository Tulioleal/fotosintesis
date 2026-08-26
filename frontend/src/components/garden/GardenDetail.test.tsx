import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClientError } from "@/lib/api/client";
import { renderWithActivityProvider as renderWithQueryClient } from "@/test/renderWithQueryClient";
import { GardenDetail } from "./GardenDetail";

const plant = {
  active_reminders: 2,
  confirmed_candidate_id: "candidate-1",
  created_at: "2026-01-01T00:00:00Z",
  custom_data: {},
  id: "garden-1",
  image_path: null,
  light_summary: null,
  location: "Balcon",
  nickname: "Helecho",
  next_reminder: null,
  notes: "Pulverizar hojas",
  profile: {
    aliases: [],
    common_name: "Helecho",
    binomial_name: "Nephrolepis exaltata",
    confidence: 0.9,
    id: "profile-1",
    limitations: [],
    scientific_name: "Nephrolepis exaltata",
    sections: {},
    selected_alias: null,
    sources: [],
  },
};

const mocks = vi.hoisted(() => ({
  deleteGardenPlant: vi.fn(),
  getGardenPlant: vi.fn(),
  getEnrichmentActivity: vi.fn(),
  listLightMeasurements: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    apiClient: {
      deleteGardenPlant: mocks.deleteGardenPlant,
      getGardenPlant: mocks.getGardenPlant,
      getEnrichmentActivity: mocks.getEnrichmentActivity,
      listLightMeasurements: mocks.listLightMeasurements,
    },
  };
});

describe("GardenDetail", () => {
  beforeEach(() => {
    mocks.deleteGardenPlant.mockReset();
    mocks.getGardenPlant.mockReset();
    mocks.getEnrichmentActivity.mockReset();
    mocks.listLightMeasurements.mockReset();
    mocks.push.mockReset();
    mocks.getGardenPlant.mockResolvedValue(plant);
    mocks.deleteGardenPlant.mockResolvedValue({ status: "deleted" });
    mocks.listLightMeasurements.mockResolvedValue([]);
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [],
      has_more: false,
    });
  });

  it("renders the loading state while the garden detail query is pending", () => {
    mocks.getGardenPlant.mockReturnValue(new Promise(() => undefined));

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(screen.getByText("Cargando detalle...")).toBeInTheDocument();
  });

  it("renders an error state when the garden detail query fails", async () => {
    mocks.getGardenPlant.mockRejectedValue(new Error("No pudimos cargar la planta."));

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByText("No pudimos cargar la planta.")).toBeInTheDocument();
  });

  it("renders the back link to Mi Jardin", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByRole("link", { name: /Volver a Mi Jardin/i })).toHaveAttribute("href", "/garden");
  });

  it("renders the plant display name and quoted nickname in the header", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByRole("heading", { name: "Helecho" })).toBeInTheDocument();
    expect(screen.getByText('"Helecho"')).toBeInTheDocument();
  });

  it("renders the light measurement tool card linking to the light meter", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByRole("link", { name: /Iniciar Medicion/i })).toHaveAttribute(
      "href",
      "/light-meter?plant=Nephrolepis%20exaltata",
    );
  });

  it("links to the assistant with garden display, binomial and scientific context", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByRole("link", { name: /Iniciar Chat sobre Helecho/i })).toHaveAttribute(
      "href",
      "/assistant?plant=Helecho&binomial=Nephrolepis%20exaltata&scientific=Nephrolepis%20exaltata&candidate=candidate-1",
    );
  });

  it("renders the create reminder link preloaded with the plant context", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByRole("link", { name: /Crear Recordatorio/i })).toHaveAttribute(
      "href",
      "/reminders?plant=Nephrolepis%20exaltata",
    );
  });

  it("renders the delete plant action", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByRole("button", { name: /Eliminar Planta/i })).toBeInTheDocument();
  });

  it("renders reminder confirmation before retrying delete with confirmation", async () => {
    mocks.deleteGardenPlant.mockRejectedValueOnce(new ApiClientError("Tiene recordatorios activos", 409));

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    fireEvent.click(await screen.findByRole("button", { name: /Eliminar Planta/i }));

    expect(await screen.findByText("Tiene recordatorios activos")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar eliminacion y afectar recordatorios" }));

    await waitFor(() => {
      expect(mocks.deleteGardenPlant).toHaveBeenLastCalledWith("garden-1", true);
    });
  });

  it("navigates back to Mi Jardin after successful delete", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    fireEvent.click(await screen.findByRole("button", { name: /Eliminar Planta/i }));

    await waitFor(() => {
      expect(mocks.push).toHaveBeenCalledWith("/garden");
    });
  });

  it("renders up to five recent light measurements when available", async () => {
    mocks.listLightMeasurements.mockResolvedValue([
      {
        classification: "media",
        garden_plant_id: "garden-1",
        id: "measurement-1",
        lux: 320,
        measured_at: "2026-06-08T12:00:00Z",
        metadata: {},
        reliability: "high",
        source: "sensor",
        user_id: "user-1",
      },
      {
        classification: "alta",
        garden_plant_id: "garden-1",
        id: "measurement-2",
        lux: 850,
        measured_at: "2026-06-01T12:00:00Z",
        metadata: {},
        reliability: "medium",
        source: "camera",
        user_id: "user-1",
      },
    ]);

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByText("Ultimas lecturas")).toBeInTheDocument();
    expect(screen.getByText(/Media · sensor/)).toBeInTheDocument();
    expect(screen.getByText(/Alta \(aprox\.\) · cámara/)).toBeInTheDocument();
  });

  it("hides the readings section when there are no prior measurements", async () => {
    mocks.listLightMeasurements.mockResolvedValue([]);

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    await screen.findByRole("heading", { name: "Helecho" });
    expect(screen.queryByText("Ultimas lecturas")).not.toBeInTheDocument();
  });

  it("renders a grounded next reminder with timezone-aware due date", async () => {
    mocks.getGardenPlant.mockResolvedValue({
      ...plant,
      next_reminder: {
        id: "reminder-1",
        action: "Regar",
        due_at: "2026-06-10T12:00:00Z",
        timezone: "America/Argentina/Buenos_Aires",
      },
    });

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByText(/Regar/)).toBeInTheDocument();
    expect(screen.queryByText(/Luz Indirecta/)).not.toBeInTheDocument();
  });

  it("renders a grounded light summary chip with source label", async () => {
    mocks.getGardenPlant.mockResolvedValue({
      ...plant,
      light_summary: {
        id: "measurement-1",
        classification: "alta",
        lux: 850,
        reliability: "medium",
        source: "sensor",
        measured_at: "2026-06-08T12:00:00Z",
      },
    });

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByText(/Alta · sensor/)).toBeInTheDocument();
  });

  it("renders a missing-data light state instead of a static label", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByText("Sin datos de luz")).toBeInTheDocument();
    expect(screen.queryByText("Luz Indirecta")).not.toBeInTheDocument();
  });

  it("marks camera readings as approximate in text and labels the source", async () => {
    mocks.listLightMeasurements.mockResolvedValue([
      {
        classification: "alta",
        garden_plant_id: "garden-1",
        id: "measurement-2",
        lux: 850,
        measured_at: "2026-06-01T12:00:00Z",
        metadata: {},
        reliability: "medium",
        source: "camera",
        user_id: "user-1",
      },
    ]);

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByText(/Alta \(aprox\.\) · cámara/)).toBeInTheDocument();
  });

  it("renders profile recommendation labeled with confidence", async () => {
    mocks.getGardenPlant.mockResolvedValue({
      ...plant,
      profile: {
        ...plant.profile,
        confidence: 0.85,
        sections: {
          care: ["Regar semanalmente sin encharcar."],
          recommendations: ["Ubicar en luz indirecta brillante."],
        },
      },
    });

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByText(/Recomendación del perfil/)).toBeInTheDocument();
    expect(screen.getByText(/confianza 85%/)).toBeInTheDocument();
    expect(screen.getByText("Regar semanalmente sin encharcar.")).toBeInTheDocument();
  });
});

const activityItem = (
  overrides: Record<string, unknown> = {},
): Record<string, unknown> => ({
  id: "33333333-3333-4333-8333-333333333333",
  job_type: "enrich_confirmed_plant",
  phase: "evidence",
  status: "processing",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  completed_at: null,
  species_key: null,
  scientific_name: "Nephrolepis exaltata",
  common_name: null,
  candidate_id: "candidate-1",
  result: null,
  last_error: null,
  ...overrides,
});

describe("GardenDetail enrichment activity", () => {
  beforeEach(() => {
    mocks.deleteGardenPlant.mockReset().mockResolvedValue({ status: "deleted" });
    mocks.getGardenPlant.mockReset().mockResolvedValue(plant);
    mocks.getEnrichmentActivity
      .mockReset()
      .mockResolvedValue({ items: [], has_more: false });
    mocks.listLightMeasurements.mockReset().mockResolvedValue([]);
    mocks.push.mockReset();
  });

  it("shows related candidate activity", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [activityItem()],
      has_more: false,
    });

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(
      await screen.findByRole("heading", { name: "Trabajo en segundo plano" }),
    ).toBeVisible();
    const activitySection = screen.getByRole("region", {
      name: "Estado del trabajo en segundo plano",
    });
    expect(activitySection).toHaveTextContent(/Nephrolepis exaltata/);
  });

  it("hides unrelated candidate activity", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [
        activityItem({
          id: "44444444-4444-4444-8444-444444444444",
          scientific_name: "Ficus elastica",
          common_name: null,
          candidate_id: "candidate-999",
        }),
      ],
      has_more: false,
    });

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    await screen.findByText("Helecho");
    expect(
      screen.queryByRole("heading", { name: "Trabajo en segundo plano" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Ficus elastica/)).not.toBeInTheDocument();
  });

  it("shows related refresh activity by candidate context with distinct copy", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [
        activityItem({
          id: "55555555-5555-4555-8555-555555555555",
          job_type: "refresh_profile",
          phase: "profile_refresh",
        }),
      ],
      has_more: false,
    });

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(
      await screen.findByText(/Actualizando las secciones del perfil/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Actualización del perfil/),
    ).toBeInTheDocument();
  });
});

describe("GardenDetail activity resilience", () => {
  beforeEach(() => {
    mocks.deleteGardenPlant.mockReset().mockResolvedValue({ status: "deleted" });
    mocks.getGardenPlant.mockReset().mockResolvedValue(plant);
    mocks.getEnrichmentActivity
      .mockReset()
      .mockResolvedValue({ items: [], has_more: false });
    mocks.listLightMeasurements.mockReset().mockResolvedValue([]);
    mocks.push.mockReset();
  });

  it("keeps primary actions usable when the activity request fails", async () => {
    mocks.getEnrichmentActivity.mockRejectedValue(new Error("offline"));

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    const retry = await screen.findByRole("button", { name: "Reintentar" });
    // Primary actions remain available.
    expect(screen.getByText("Acciones")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Iniciar Chat sobre/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Crear Recordatorio/ }),
    ).toBeInTheDocument();

    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [
        {
          id: "33333333-3333-4333-8333-333333333333",
          job_type: "enrich_confirmed_plant",
          phase: "evidence",
          status: "processing",
          created_at: "2026-08-01T00:00:00Z",
          updated_at: "2026-08-01T00:00:00Z",
          completed_at: null,
          species_key: null,
          scientific_name: "Nephrolepis exaltata",
          common_name: null,
          candidate_id: "candidate-1",
          result: null,
          last_error: null,
        },
      ],
      has_more: false,
      next_cursor: null,
    });
    fireEvent.click(retry);

    await waitFor(() => {
      expect(
        screen.getByText(/Nephrolepis exaltata/),
      ).toBeInTheDocument();
    });
  });
});
