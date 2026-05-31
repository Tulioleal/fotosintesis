import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { LightMeter } from "./LightMeter";

const mocks = vi.hoisted(() => ({
  createLightMeasurement: vi.fn(),
  listGardenPlants: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    createLightMeasurement: mocks.createLightMeasurement,
    listGardenPlants: mocks.listGardenPlants,
  },
}));

describe("LightMeter", () => {
  beforeEach(() => {
    mocks.createLightMeasurement.mockReset();
    mocks.listGardenPlants.mockReset();
    mocks.createLightMeasurement.mockResolvedValue({ id: "measurement-1" });
    mocks.listGardenPlants.mockResolvedValue([
      {
        id: "garden-1",
        nickname: "Helecho",
        profile: { common_name: "Helecho", scientific_name: "Nephrolepis exaltata" },
      },
    ]);
    vi.stubGlobal("navigator", { mediaDevices: undefined });
  });

  it("falls back to manual guidance when automatic sensors are unavailable", async () => {
    renderWithQueryClient(<LightMeter />);

    fireEvent.click(screen.getByRole("button", { name: "Medir luz" }));

    expect(await screen.findByText("Tu navegador no permite usar camara desde esta pantalla. Usa registro manual.")).toBeInTheDocument();
  });

  it("creates and saves a manual low-reliability reading without requiring a plant", async () => {
    renderWithQueryClient(<LightMeter />);

    fireEvent.change(screen.getByLabelText("Condicion observada"), { target: { value: "alta" } });
    fireEvent.submit(screen.getByRole("button", { name: "Usar registro manual" }).closest("form")!);

    expect(screen.getByRole("heading", { name: "Luz alta" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Guardar medicion" }));

    await waitFor(() => {
      expect(mocks.createLightMeasurement).toHaveBeenCalledWith({
        garden_plant_id: null,
        classification: "alta",
        lux: null,
        reliability: "low",
        source: "manual",
        metadata: { manualLabel: "Alta" },
      });
    });
    expect(await screen.findByText("Medicion guardada correctamente.")).toBeInTheDocument();
  });
});
