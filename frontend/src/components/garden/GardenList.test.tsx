import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { GardenList } from "./GardenList";

const plant = {
  active_reminders: 0,
  confirmed_candidate_id: "candidate-1",
  created_at: "2026-01-01T00:00:00Z",
  custom_data: {},
  id: "garden-1",
  image_path: "garden-plants/helecho.jpg",
  location: "Balcón",
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

    expect(screen.getByText("Balcón • Luz indirecta")).toBeInTheDocument();
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
