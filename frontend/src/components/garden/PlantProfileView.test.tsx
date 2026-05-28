import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { PlantProfileView } from "./PlantProfileView";

const profile = {
  aliases: [{ country: null, language: "es", name: "Helecho", region: null }],
  common_name: "Helecho",
  confidence: 0.9,
  id: "profile-1",
  limitations: [],
  scientific_name: "Nephrolepis exaltata",
  sections: { care: ["Riego moderado"] },
  selected_alias: "Helecho",
  sources: [],
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
  saveGardenPlant: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    saveGardenPlant: mocks.saveGardenPlant,
  },
}));

describe("PlantProfileView", () => {
  beforeEach(() => {
    mocks.saveGardenPlant.mockReset();
    mocks.saveGardenPlant.mockResolvedValue(savedPlant);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => profile,
      }),
    );
  });

  it("saves a confirmed plant through the garden mutation", async () => {
    const fetchMock = vi.mocked(fetch);
    renderWithQueryClient(<PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />);

    fireEvent.change(await screen.findByPlaceholderText("Nombre personalizado"), { target: { value: "Mi helecho" } });
    fireEvent.change(screen.getByPlaceholderText("Ubicacion en casa"), { target: { value: "Balcon" } });
    fireEvent.change(screen.getByPlaceholderText("Notas propias"), { target: { value: "Cerca de la ventana" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar planta confirmada" }));

    await waitFor(() => {
      expect(mocks.saveGardenPlant).toHaveBeenCalledWith({
        confirmed_candidate_id: "candidate-1",
        location: "Balcon",
        nickname: "Mi helecho",
        notes: "Cerca de la ventana",
      });
    });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("candidateId=candidate-1"));
    expect(await screen.findByText("Guardada en Mi Jardin como Mi helecho.")).toBeInTheDocument();
  });

  it("renders a user-facing error when the garden save mutation fails", async () => {
    mocks.saveGardenPlant.mockRejectedValue(new Error("No pudimos guardar la planta."));

    renderWithQueryClient(<PlantProfileView scientificName="Nephrolepis exaltata" confirmedCandidateId="candidate-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Guardar planta confirmada" }));

    expect(await screen.findByText("No pudimos guardar la planta.")).toBeInTheDocument();
  });

  it("does not request a profile without confirmed candidate context", async () => {
    const fetchMock = vi.mocked(fetch);

    renderWithQueryClient(<PlantProfileView scientificName="Nephrolepis exaltata" />);

    expect(await screen.findByText("Para ver el perfil, confirma primero una candidata validada desde Identificar.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
