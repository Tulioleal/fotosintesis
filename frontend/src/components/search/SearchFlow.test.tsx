import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SearchFlow } from "./SearchFlow";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

const mocks = vi.hoisted(() => ({
  searchPlants: vi.fn(),
  searchGbif: vi.fn(),
  createManualCandidate: vi.fn(),
  confirmManualCandidate: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    searchPlants: mocks.searchPlants,
    searchGbif: mocks.searchGbif,
    createManualCandidate: mocks.createManualCandidate,
    confirmManualCandidate: mocks.confirmManualCandidate,
  },
}));

async function typeAndSearch(value: string) {
  renderWithQueryClient(<SearchFlow />);
  fireEvent.change(screen.getByLabelText("Nombre de la planta"), {
    target: { value },
  });
  fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
}

describe("SearchFlow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mocks.searchPlants.mockReset();
    mocks.searchGbif.mockReset();
    mocks.createManualCandidate.mockReset();
    mocks.confirmManualCandidate.mockReset();
  });

  it("shows local results and labels them as local", async () => {
    mocks.searchPlants.mockResolvedValue({
      results: [
        {
          profile_id: "profile-1",
          scientific_name: "Monstera deliciosa",
          common_name: "Costilla de Adán",
          binomial_name: "Monstera deliciosa",
          matched_field: "scientific_name",
          matched_value: "Monstera",
          has_evidence: true,
        },
      ],
    });

    await typeAndSearch("Monstera");

    await waitFor(() => {
      expect(screen.getByText("Monstera deliciosa")).toBeInTheDocument();
    });
    expect(screen.getByText("Registro local")).toBeInTheDocument();
    expect(screen.getByText("Resultados locales")).toBeInTheDocument();
  });

  it("expands to GBIF when local results are empty", async () => {
    mocks.searchPlants.mockResolvedValue({ results: [] });
    mocks.searchGbif.mockResolvedValue({
      candidates: [
        {
          key: 1,
          accepted_key: 100,
          accepted_scientific_name: "Monstera deliciosa",
          binomial_name: "Monstera deliciosa",
          rank: "SPECIES",
          taxonomic_status: "ACCEPTED",
          genus: "Monstera",
          family: "Araceae",
        },
      ],
    });

    await typeAndSearch("Monstera");

    await waitFor(() => {
      expect(screen.getByText("Candidatas externas (GBIF)")).toBeInTheDocument();
      expect(screen.getByText("Candidata externa")).toBeInTheDocument();
    });
    expect(mocks.searchGbif).toHaveBeenCalledWith("Monstera");
  });

  it("shows an empty state when nothing matches anywhere", async () => {
    mocks.searchPlants.mockResolvedValue({ results: [] });
    mocks.searchGbif.mockResolvedValue({ candidates: [] });

    await typeAndSearch("zzz");

    await waitFor(() => {
      expect(screen.getByText("Sin resultados")).toBeInTheDocument();
    });
  });

  it("shows an error state when local search fails", async () => {
    mocks.searchPlants.mockRejectedValue(new Error("boom"));

    await typeAndSearch("Monstera");

    await waitFor(() => {
      expect(
        screen.getByText(
          "No pudimos buscar plantas locales. Reintentá en unos segundos.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("creates and confirms a selected manual candidate", async () => {
    mocks.searchPlants.mockResolvedValue({ results: [] });
    mocks.searchGbif.mockResolvedValue({
      candidates: [
        {
          key: 1,
          accepted_key: 100,
          accepted_scientific_name: "Monstera deliciosa",
          binomial_name: "Monstera deliciosa",
          rank: "SPECIES",
          taxonomic_status: "ACCEPTED",
        },
      ],
    });
    mocks.createManualCandidate.mockResolvedValue({
      id: "candidate-1",
      suggested_scientific_name: "Monstera deliciosa",
      binomial_name: "Monstera deliciosa",
      accepted_scientific_name: "Monstera deliciosa",
      validation_status: "validated",
      confidence_label: "manual",
    });
    mocks.confirmManualCandidate.mockResolvedValue({
      status: "confirmed",
      candidate: {
        id: "candidate-1",
        accepted_scientific_name: "Monstera deliciosa",
        suggested_scientific_name: "Monstera deliciosa",
      },
    });

    renderWithQueryClient(<SearchFlow />);
    fireEvent.change(screen.getByLabelText("Nombre de la planta"), {
      target: { value: "Monstera" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));

    await waitFor(() => {
      expect(screen.getByText("Candidatas externas (GBIF)")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Seleccionar" }));
    fireEvent.click(screen.getByRole("button", { name: "Crear candidata" }));

    await waitFor(() => {
      expect(mocks.createManualCandidate).toHaveBeenCalledWith({
        query: "Monstera",
        gbif: expect.objectContaining({ accepted_key: 100 }),
      });
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Confirmar y ver perfil" }),
    );

    await waitFor(() => {
      expect(mocks.confirmManualCandidate).toHaveBeenCalledWith("candidate-1");
    });
  });

  it("provides keyboard-operable controls and a live region", async () => {
    mocks.searchPlants.mockResolvedValue({ results: [] });
    mocks.searchGbif.mockResolvedValue({ candidates: [] });

    renderWithQueryClient(<SearchFlow />);

    const input = screen.getByLabelText("Nombre de la planta");
    expect(input).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(input.getAttribute("autocomplete")).toBe("off");
  });
});
