import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IdentifyFlow } from "./IdentifyFlow";

const identificationPayload = {
  id: "identification-1",
  status: "needs_confirmation",
  sad_path: null,
  message: "Confirmá una candidata validada antes de continuar.",
  candidates: [
    {
      id: "candidate-1",
      common_name: "Pata de oso",
      suggested_scientific_name: "Cotyledon tomentosa",
      confidence_label: "high",
      visible_traits: ["hojas carnosas"],
      possible_match_copy: "Coincide con una suculenta compacta.",
      accepted_scientific_name: "Cotyledon tomentosa",
      validation_status: "validated",
      gbif_key: 123,
      genus: "Cotyledon",
      family: "Crassulaceae",
      species: "Cotyledon tomentosa",
      synonyms: ["Cotyledon ladismithiensis"],
      confirmed_at: null,
    },
  ],
};

describe("IdentifyFlow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:preview") });
  });

  it("falls back to upload when camera access is unavailable", async () => {
    vi.stubGlobal("navigator", { mediaDevices: undefined });
    render(<IdentifyFlow />);

    fireEvent.click(screen.getByRole("button", { name: "Tomar foto" }));

    expect(await screen.findByText("Tu navegador no permite abrir la camara desde esta pantalla. Usa subir imagen.")).toBeInTheDocument();
  });

  it("renders validated candidates and links to the profile after confirmation", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => identificationPayload })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ candidate: { confirmed_at: "2026-01-01T00:00:00Z" } }) }));
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector('input[accept="image/jpeg,image/png,image/webp"]') as HTMLInputElement;

    fireEvent.change(upload, { target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] } });

    expect(await screen.findByRole("heading", { name: "Pata de oso" })).toBeInTheDocument();
    expect(screen.getByText(/GBIF validado #123/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Confirmar candidata validada" }));

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Ver perfil y agregar a Mi Jardin" })).toHaveAttribute(
        "href",
        "/profiles/Cotyledon%20tomentosa?candidateId=candidate-1",
      );
    });
  });

  it("blocks confirmation for candidates without GBIF validation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...identificationPayload,
        sad_path: "no_gbif_match",
        message: "No encontramos coincidencia GBIF.",
        candidates: [{ ...identificationPayload.candidates[0], validation_status: "no_gbif_match", gbif_key: null }],
      }),
    }));
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector('input[accept="image/jpeg,image/png,image/webp"]') as HTMLInputElement;

    fireEvent.change(upload, { target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] } });

    expect(await screen.findByText("Sin coincidencia GBIF: usa busqueda manual o reintenta con otra foto.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirmar candidata validada" })).toBeDisabled();
  });
});
