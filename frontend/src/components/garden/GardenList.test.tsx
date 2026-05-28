import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { GardenList } from "./GardenList";

const plant = {
  active_reminders: 0,
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
  listGardenPlants: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    listGardenPlants: mocks.listGardenPlants,
  },
}));

describe("GardenList", () => {
  beforeEach(() => {
    mocks.listGardenPlants.mockReset();
    mocks.listGardenPlants.mockResolvedValue([plant]);
  });

  it("renders the loading state while the garden list query is pending", () => {
    mocks.listGardenPlants.mockReturnValue(new Promise(() => undefined));

    renderWithQueryClient(<GardenList />);

    expect(screen.getByText("Cargando plantas...")).toBeInTheDocument();
  });

  it("renders the empty state when the garden list is empty", async () => {
    mocks.listGardenPlants.mockResolvedValue([]);

    renderWithQueryClient(<GardenList />);

    expect(await screen.findByRole("heading", { name: "Tu jardin esta vacio" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Identificar planta" })).toHaveAttribute("href", "/identify");
  });

  it("renders an error state when the garden list query fails", async () => {
    mocks.listGardenPlants.mockRejectedValue(new Error("No pudimos cargar Mi Jardin."));

    renderWithQueryClient(<GardenList />);

    expect(await screen.findByText("No pudimos cargar Mi Jardin.")).toBeInTheDocument();
    expect(screen.queryByText("Helecho")).not.toBeInTheDocument();
  });

  it("renders garden plants returned by the query", async () => {
    renderWithQueryClient(<GardenList />);

    expect(await screen.findByRole("heading", { name: "Helecho" })).toBeInTheDocument();
    expect(screen.getByText("Pulverizar hojas")).toBeInTheDocument();
  });

  it("requests submitted search text through the garden query path", async () => {
    renderWithQueryClient(<GardenList />);

    fireEvent.change(screen.getByPlaceholderText("Buscar planta"), { target: { value: "helecho" } });
    fireEvent.submit(screen.getByRole("button", { name: "Buscar" }).closest("form")!);

    await waitFor(() => {
      expect(mocks.listGardenPlants).toHaveBeenCalledWith("helecho");
    });
  });
});
