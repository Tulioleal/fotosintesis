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
    },
  };
});

describe("GardenDetail", () => {
  beforeEach(() => {
    mocks.deleteGardenPlant.mockReset();
    mocks.getGardenPlant.mockReset();
    mocks.push.mockReset();
    mocks.getGardenPlant.mockResolvedValue(plant);
    mocks.deleteGardenPlant.mockResolvedValue({ status: "deleted" });
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

  it("links to the profile with the confirmed candidate context", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    expect(await screen.findByRole("link", { name: "Ver perfil" })).toHaveAttribute(
      "href",
      "/profiles/Nephrolepis%20exaltata?candidateId=candidate-1",
    );
  });

  it("renders reminder confirmation before retrying delete with confirmation", async () => {
    mocks.deleteGardenPlant.mockRejectedValueOnce(new ApiClientError("Tiene recordatorios activos", 409));

    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Eliminar de Mi Jardin" }));

    expect(await screen.findByText("Tiene recordatorios activos")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar eliminacion y afectar recordatorios" }));

    await waitFor(() => {
      expect(mocks.deleteGardenPlant).toHaveBeenLastCalledWith("garden-1", true);
    });
  });

  it("navigates back to Mi Jardin after successful delete", async () => {
    renderWithQueryClient(<GardenDetail gardenId="garden-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Eliminar de Mi Jardin" }));

    await waitFor(() => {
      expect(mocks.push).toHaveBeenCalledWith("/garden");
    });
  });
});
