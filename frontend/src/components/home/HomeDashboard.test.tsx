import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HomeDashboard } from "./HomeDashboard";
import { EnrichmentActivityProvider } from "@/components/enrichment/EnrichmentActivityProvider";

const recentPlant = {
  id: "11111111-1111-4111-8111-111111111111",
  scientific_name: "Monstera deliciosa",
  common_name: "Monstera Deliciosa",
  nickname: "Lobby monstera",
  image_path: "garden-plants/monstera.jpg",
  location: "Sala",
  active_reminders: 2,
  created_at: "2026-06-01T00:00:00Z",
};

const homeSummary = {
  user: { id: "1", name: "Tuli", email: "t@example.com", email_verified: false },
  empty_state: false,
  access: [
    { key: "identify", label: "Identify plant", href: "/identify", status: "placeholder" },
    { key: "garden", label: "My Garden", href: "/garden", status: "placeholder" },
    { key: "reminders", label: "Reminders", href: "/reminders", status: "placeholder" },
  ],
  garden_count: 3,
  recent_garden_plants: [recentPlant],
};

const mocks = vi.hoisted(() => ({
  getHomeSummary: vi.fn(),
  getEnrichmentActivity: vi.fn(),
  useSession: vi.fn(),
}));

vi.mock("next-auth/react", () => ({
  useSession: mocks.useSession,
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    getHomeSummary: mocks.getHomeSummary,
    getEnrichmentActivity: mocks.getEnrichmentActivity,
  },
}));

function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: {
              gcTime: 0,
            },
          },
        })
      }
    >
      <EnrichmentActivityProvider>{children}</EnrichmentActivityProvider>
    </QueryClientProvider>
  );
}

describe("HomeDashboard", () => {
  beforeEach(() => {
    mocks.getHomeSummary.mockReset();
    mocks.getHomeSummary.mockResolvedValue(homeSummary);
    mocks.getEnrichmentActivity.mockReset();
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [],
      has_more: false,
    });
    mocks.useSession.mockReset();
    mocks.useSession.mockReturnValue({
      status: "authenticated",
      data: { user: { id: "1", name: "Tuli", email: "t@example.com" } },
    });
  });

  it("renders the welcome heading and lead copy for an authenticated user", async () => {
    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole("heading", { name: /Hola, Tuli/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Bienvenido de vuelta a tu espacio verde."),
    ).toBeInTheDocument();
  });

  it("loads Home through the frontend boundary without a bearer token", async () => {
    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole("heading", { name: /Hola, Tuli/ }),
    ).toBeInTheDocument();
    expect(mocks.getHomeSummary).toHaveBeenCalledWith();
  });

  it("renders the Home loading skeleton while session data loads", () => {
    mocks.useSession.mockReturnValue({ status: "loading", data: null });

    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(screen.getByLabelText("Cargando Home")).toBeInTheDocument();
    expect(mocks.getHomeSummary).not.toHaveBeenCalled();
  });

  it("renders a Home error state with a retry action", async () => {
    mocks.getHomeSummary.mockRejectedValue(new Error("Home failed"));

    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole(
        "heading",
        { name: "No pudimos actualizar tu Home" },
        { timeout: 3_000 },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("La base de la app sigue disponible. Intentá cargar los datos nuevamente.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeEnabled();
  });

  it("retries the Home summary request when retry is clicked", async () => {
    mocks.getHomeSummary.mockRejectedValue(new Error("Home failed"));

    render(<HomeDashboard />, { wrapper: Wrapper });

    const retry = await screen.findByRole(
      "button",
      { name: "Reintentar" },
      { timeout: 3_000 },
    );
    const callsBeforeRetry = mocks.getHomeSummary.mock.calls.length;

    fireEvent.click(retry);

    await waitFor(() => {
      expect(mocks.getHomeSummary.mock.calls.length).toBeGreaterThan(callsBeforeRetry);
    });
  });

  it("renders the quick access section with the three required cards and the live garden count", async () => {
    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole("heading", { name: "Acceso rápido" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Mi Jardín/ }),
    ).toHaveAttribute("href", "/garden");
    expect(
      screen.getByRole("link", { name: /Identificar Planta/ }),
    ).toHaveAttribute("href", "/identify");
    expect(
      screen.getByRole("link", { name: /Recordatorios/ }),
    ).toHaveAttribute("href", "/reminders");
    expect(screen.getByText("3 Plantas")).toBeInTheDocument();
  });

  it("uses the singular label when the garden holds a single plant", async () => {
    mocks.getHomeSummary.mockResolvedValue({
      ...homeSummary,
      garden_count: 1,
    });

    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(await screen.findByText("1 Planta")).toBeInTheDocument();
  });

  it("renders the user's recent garden plants with backend-driven data", async () => {
    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole("heading", { name: "Tu jardín" }),
    ).toBeInTheDocument();

    const card = screen.getByRole("link", {
      name: /Lobby monstera/,
    });
    expect(card).toHaveAttribute("href", `/garden/${recentPlant.id}`);

    const image = screen.getByRole("img", { name: "Lobby monstera" });
    expect(image).toHaveAttribute("src", "/api/media/garden-plants/monstera.jpg");

    expect(screen.getByText("Sala • 2 recordatorios")).toBeInTheDocument();

    const viewAll = screen.getByRole("link", { name: "Ver todas" });
    expect(viewAll).toHaveAttribute("href", "/garden");
  });

  it("falls back to the scientific name and renders a placeholder when no image is set", async () => {
    mocks.getHomeSummary.mockResolvedValue({
      ...homeSummary,
      recent_garden_plants: [
        {
          ...recentPlant,
          common_name: null,
          nickname: null,
          image_path: null,
          active_reminders: 0,
        },
      ],
    });

    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole("heading", { name: "Tu jardín" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Monstera deliciosa")).toBeInTheDocument();
    expect(screen.getByText("Sala")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Monstera deliciosa" })).toBeNull();
  });

  it("hides the recent garden plants section when the user has no plants", async () => {
    mocks.getHomeSummary.mockResolvedValue({
      ...homeSummary,
      recent_garden_plants: [],
    });

    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole("heading", { name: "Acceso rápido" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Tu jardín" }),
    ).not.toBeInTheDocument();
  });

  it("does not expose PlantCare placeholder copy on the redesigned Home", async () => {
    const { container } = render(<HomeDashboard />, { wrapper: Wrapper });

    await screen.findByRole("heading", { name: /Hola, Tuli/ });
    expect(container.textContent).not.toMatch(/PlantCare/);
  });

  it("shows a compact background-work indicator with plant context and a profile link", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      has_more: false,
      items: [
        {
          id: "22222222-2222-4222-8222-222222222222",
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
        },
      ],
    });

    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole("heading", { name: "Trabajo en segundo plano" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Monstera")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Ver perfil de Monstera/ }),
    ).toHaveAttribute(
      "href",
      "/profiles/Monstera%20deliciosa?candidateId=candidate-1",
    );
  });
});

describe("HomeDashboard activity states", () => {
  beforeEach(() => {
    mocks.getHomeSummary.mockReset().mockResolvedValue(homeSummary);
    mocks.getEnrichmentActivity
      .mockReset()
      .mockResolvedValue({ items: [], has_more: false });
    mocks.useSession.mockReset();
    mocks.useSession.mockReturnValue({
      status: "authenticated",
      data: { user: { id: "1", name: "Tuli", email: "t@example.com" } },
    });
  });

  it("renders nothing for activity when the list is empty", async () => {
    render(<HomeDashboard />, { wrapper: Wrapper });
    await screen.findByRole("heading", { name: /Hola, Tuli/ });
    expect(
      screen.queryByRole("heading", { name: "Trabajo en segundo plano" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Actividad reciente" }),
    ).not.toBeInTheDocument();
  });

  it("surfaces retained terminal outcomes on Home", async () => {
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [
        {
          id: "11111111-1111-4111-8111-111111111111",
          job_type: "enrich_confirmed_plant",
          phase: "evidence",
          status: "complete",
          created_at: "2026-08-01T00:00:00Z",
          updated_at: "2026-08-01T00:01:00Z",
          completed_at: "2026-08-01T00:01:00Z",
          species_key: null,
          scientific_name: "Monstera deliciosa",
          common_name: null,
          candidate_id: "00000000-0000-4000-8000-000000000011",
          result: {
            outcome: "complete",
            covered_count: 2,
            missing_count: 0,
            regenerated_section_count: 0,
            stale_section_count: 0,
            limitations: [],
          },
          last_error: null,
        },
      ],
      has_more: false,
      next_cursor: null,
    });

    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole("heading", { name: "Actividad reciente" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/La evidencia está lista/)).toBeInTheDocument();
  });
});
