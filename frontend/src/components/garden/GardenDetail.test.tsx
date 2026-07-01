import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClientError } from "@/lib/api/client";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { GardenDetail } from "./GardenDetail";

const plant = {
  active_reminders: 2,
  confirmed_candidate_id: "candidate-1",
  created_at: "2026-01-01T00:00:00Z",
  custom_data: {},
  id: "garden-1",
  image_path: null,
  location: "Balcon",
  nickname: "Helecho",
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
      listLightMeasurements: mocks.listLightMeasurements,
    },
  };
});

describe("GardenDetail", () => {
  beforeEach(() => {
    mocks.deleteGardenPlant.mockReset();
    mocks.getGardenPlant.mockReset();
    mocks.listLightMeasurements.mockReset();
    mocks.push.mockReset();
    mocks.getGardenPlant.mockResolvedValue(plant);
    mocks.deleteGardenPlant.mockResolvedValue({ status: "deleted" });
    mocks.listLightMeasurements.mockResolvedValue([]);
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
      "/assistant?plant=Helecho&binomial=Nephrolepis%20exaltata&scientific=Nephrolepis%20exaltata",
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
    expect(screen.getByText("Media")).toBeInTheDocument();
    expect(screen.getByText("Alta")).toBeInTheDocument();
  });

  it("hides the readings section when there are no prior measurements", async () => {
    mocks.listLightMeasurements.mockResolvedValue([]);

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    await screen.findByRole("heading", { name: "Helecho" });
    expect(screen.queryByText("Ultimas lecturas")).not.toBeInTheDocument();
  });
});
