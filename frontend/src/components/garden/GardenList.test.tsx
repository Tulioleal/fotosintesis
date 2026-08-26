import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithActivityProvider as renderWithQueryClient } from "@/test/renderWithQueryClient";
import { GardenList } from "./GardenList";

const plant = {
  active_reminders: 0,
  confirmed_candidate_id: "candidate-1",
  created_at: "2026-01-01T00:00:00Z",
  custom_data: {},
  id: "garden-1",
  image_path: "garden-plants/helecho.jpg",
  location: "Balcón",
  light_summary: null,
  nickname: "Helecho",
  next_reminder: null,
  notes: "Pulverizar hojas",
  profile: {
    aliases: [],
    common_name: "Helecho",
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
  listGardenPlants: vi.fn(),
  getEnrichmentActivity: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    listGardenPlants: mocks.listGardenPlants,
    getEnrichmentActivity: mocks.getEnrichmentActivity,
  },
}));

describe("GardenList", () => {
  beforeEach(() => {
    mocks.listGardenPlants.mockReset();
    mocks.listGardenPlants.mockResolvedValue([plant]);
    mocks.getEnrichmentActivity.mockReset();
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [],
      has_more: false,
    });
  });

  it("renders the loading state while the garden list query is pending", () => {
    mocks.listGardenPlants.mockReturnValue(new Promise(() => undefined));

    renderWithQueryClient(<GardenList />);

    expect(screen.getByText("Cargando plantas...")).toBeInTheDocument();
  });

  it("renders the empty state when the garden list is empty", async () => {
    mocks.listGardenPlants.mockResolvedValue([]);

    renderWithQueryClient(<GardenList />);

    expect(
      await screen.findByRole("heading", { name: "Tu jardín está vacío" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Identificar planta" })).toHaveAttribute("href", "/identify");
  });

  it("renders an error state when the garden list query fails", async () => {
    mocks.listGardenPlants.mockRejectedValue(new Error("No pudimos cargar Mi Jardín."));

    renderWithQueryClient(<GardenList />);

    expect(await screen.findByText("No pudimos cargar Mi Jardín.")).toBeInTheDocument();
    expect(screen.queryByText("Helecho")).not.toBeInTheDocument();
  });

  it("renders the reference header with title, subtitle and register CTA", () => {
    renderWithQueryClient(<GardenList />);

    expect(
      screen.getByRole("heading", { name: "Mi Jardín", level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Monitorea y gestiona el cuidado de tus plantas."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Registrar Planta/i })).toHaveAttribute(
      "href",
      "/identify",
    );
  });

  it("renders garden plants as image-first cards linked to the plant detail", async () => {
    renderWithQueryClient(<GardenList />);

    const heading = await screen.findByRole("heading", { name: "Helecho" });
    const card = heading.closest("a");
    expect(card).not.toBeNull();
    expect(card).toHaveAttribute("href", "/garden/garden-1");

    const image = screen.getByRole("img", { name: "Helecho" });
    expect(image).toBeInTheDocument();
    expect(image).toHaveAttribute(
      "src",
      expect.stringContaining("garden-plants/helecho.jpg"),
    );

    expect(screen.getByText("Balcón")).toBeInTheDocument();
    expect(screen.queryByText("Luz indirecta")).not.toBeInTheDocument();
    expect(screen.queryByText("Último riego")).not.toBeInTheDocument();
  });

  it("renders a no-care state on cards without a pending reminder", async () => {
    renderWithQueryClient(<GardenList />);

    const noCare = await screen.findByText("Sin cuidados pendientes");
    expect(noCare).toBeInTheDocument();
    expect(noCare.closest("a")).toHaveAttribute("href", "/garden/garden-1");
  });

  it("renders the next pending reminder action and timezone-aware due date", async () => {
    mocks.listGardenPlants.mockResolvedValue([
      {
        ...plant,
        next_reminder: {
          id: "reminder-1",
          action: "Regar",
          due_at: "2026-06-10T12:00:00Z",
          timezone: "America/Argentina/Buenos_Aires",
        },
      },
    ]);

    renderWithQueryClient(<GardenList />);

    expect(await screen.findByText(/Regar/)).toBeInTheDocument();
    expect(screen.queryByText("Sin cuidados pendientes")).not.toBeInTheDocument();
  });

  it("renders the plant icon fallback when no image is available", async () => {
    mocks.listGardenPlants.mockResolvedValue([
      { ...plant, id: "garden-2", nickname: "Sin foto", image_path: null },
    ]);

    renderWithQueryClient(<GardenList />);

    const heading = await screen.findByRole("heading", { name: "Sin foto" });
    const card = heading.closest("a");
    expect(card).not.toBeNull();
    expect(card).toHaveAttribute("href", "/garden/garden-2");
    expect(screen.queryByRole("img", { name: "Sin foto" })).not.toBeInTheDocument();
  });
});

const activityItem = (
  overrides: Record<string, unknown> = {},
): Record<string, unknown> => ({
  id: "22222222-2222-4222-8222-222222222222",
  job_type: "enrich_confirmed_plant",
  phase: "evidence",
  status: "processing",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  completed_at: null,
  species_key: "gbif:1|binomial:Nephrolepis exaltata",
  scientific_name: "Nephrolepis exaltata",
  common_name: null,
  candidate_id: "candidate-1",
  result: null,
  last_error: null,
  ...overrides,
});

describe("GardenList enrichment activity", () => {
  beforeEach(() => {
    mocks.listGardenPlants.mockReset().mockResolvedValue([plant]);
    mocks.getEnrichmentActivity
      .mockReset()
      .mockResolvedValue({ items: [], has_more: false });
  });

  it("shows processing evidence activity with a valid profile link", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [activityItem()],
      has_more: false,
    });

    renderWithQueryClient(<GardenList />);

    expect(
      await screen.findByRole("heading", { name: "Trabajo en segundo plano" }),
    ).toBeVisible();
    expect(screen.getAllByText(/continúa en segundo plano/i).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: /Ver perfil de Nephrolepis exaltata/ }),
    ).toHaveAttribute(
      "href",
      "/profiles/Nephrolepis%20exaltata?candidateId=candidate-1",
    );
  });

  it("retains partial evidence activity in the recent list", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [
        activityItem({
          status: "partial",
          completed_at: "2026-08-01T00:05:00Z",
          result: {
            outcome: "partial",
            covered_count: 2,
            missing_count: 1,
            regenerated_section_count: 0,
            stale_section_count: 0,
            limitations: ["missing_required_aspects"],
          },
        }),
      ],
      has_more: false,
    });

    renderWithQueryClient(<GardenList />);

    expect(
      await screen.findByRole("heading", { name: "Actividad reciente" }),
    ).toBeVisible();
    expect(
      screen.getByText(/Encontramos evidencia útil/),
    ).toBeInTheDocument();
  });

  it("shows failed activity with recovery guidance", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [
        activityItem({
          status: "failed",
          completed_at: "2026-08-01T00:05:00Z",
          last_error: { category: "attempts_exhausted", retryable: false },
        }),
      ],
      has_more: false,
    });

    renderWithQueryClient(<GardenList />);

    expect(
      await screen.findByText(/No pudimos ampliar la evidencia/),
    ).toBeVisible();
    expect(
      screen.getByText(/volver a intentarlo más adelante/),
    ).toBeInTheDocument();
  });

  it("keeps the garden usable when the activity request fails and retries", async () => {
    mocks.getEnrichmentActivity.mockRejectedValue(new Error("offline"));

    renderWithQueryClient(<GardenList />);

    const retry = await screen.findByRole("button", { name: "Reintentar" });
    expect(
      screen.getByText(/No pudimos actualizar el estado del trabajo/),
    ).toBeInTheDocument();
    // The garden cards remain rendered and usable.
    expect(screen.getByText("Helecho")).toBeInTheDocument();

    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [activityItem()],
      has_more: false,
    });
    fireEvent.click(retry);
    expect(
      await screen.findByRole("heading", { name: "Trabajo en segundo plano" }),
    ).toBeInTheDocument();
  });
});
