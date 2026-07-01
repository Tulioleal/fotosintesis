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
      confidence_score: 0.95,
      visible_traits: ["hojas carnosas"],
      possible_match_copy: "Coincide con una suculenta compacta.",
      accepted_scientific_name: "Cotyledon tomentosa",
      binomial_name: "Cotyledon tomentosa",
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

    fireEvent.click(screen.getByRole("button", { name: "Abrir Cámara" }));

    expect(
      await screen.findByText(
        "Tu navegador no permite abrir la camara desde esta pantalla. Usa subir imagen.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the reference identification header and initial drop zone", () => {
    render(<IdentifyFlow />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Identificar Planta",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Sube o toma una foto para identificar tu planta."),
    ).toBeInTheDocument();
    expect(screen.getByText("o arrastra y suelta aquí")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Subir Foto" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Abrir Cámara" }),
    ).toBeInTheDocument();
  });

  it("shows an analyzing state with skeleton cards and progress while the image is being submitted", async () => {
    const pendingResponse = new Promise<Response>(() => {});
    vi.stubGlobal(
      "fetch",
      vi.fn(() => pendingResponse),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    expect(await screen.findByText("Analizando imagen...")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Analizando imagen" })).toBeInTheDocument();
    expect(screen.getByText("Buscando...")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Posibles Coincidencias" }),
    ).toBeInTheDocument();
  });

  it("exposes a reset action while the image is being analyzed", async () => {
    const pendingResponse = new Promise<Response>(() => {});
    vi.stubGlobal(
      "fetch",
      vi.fn(() => pendingResponse),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    const resetButton = await screen.findByRole("button", { name: "Eliminar y repetir" });
    expect(resetButton).toBeInTheDocument();
  });

  it("renders validated candidates and links to the profile after confirmation", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({ ok: true, json: async () => identificationPayload })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ candidate: { confirmed_at: "2026-01-01T00:00:00Z" } }),
        }),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    expect(
      await screen.findByRole("heading", { name: "Pata de oso" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Confianza: Alta (95%)")).toBeInTheDocument();
    expect(screen.getByText("1 resultado")).toBeInTheDocument();
    expect(
      screen.getByText("Imagen analizada con éxito"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Seleccionar esta planta" }));

    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: "Ver perfil y agregar a Mi Jardin" }),
      ).toHaveAttribute(
        "href",
        "/profiles/Cotyledon%20tomentosa?candidateId=candidate-1",
      );
      expect(
        screen.getByRole("link", { name: "Preguntar al asistente" }),
      ).toHaveAttribute(
        "href",
        "/assistant?plant=Pata%20de%20oso&binomial=Cotyledon%20tomentosa&scientific=Cotyledon%20tomentosa",
      );
    });
  });

  it("renders the binomial name as primary text when common name is absent", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            ...identificationPayload,
            candidates: [
              {
                ...identificationPayload.candidates[0],
                common_name: null,
                suggested_scientific_name: "Solanum lycopersicum var. cerasiforme",
                accepted_scientific_name: "Solanum lycopersicum var. cerasiforme",
                binomial_name: "Solanum lycopersicum",
              },
            ],
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ candidate: { confirmed_at: "2026-01-01T00:00:00Z" } }),
        }),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    expect(
      await screen.findByRole("heading", { name: "Solanum lycopersicum" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Seleccionar esta planta" }));

    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: "Preguntar al asistente" }),
      ).toHaveAttribute(
        "href",
        "/assistant?plant=Solanum%20lycopersicum&binomial=Solanum%20lycopersicum&scientific=Solanum%20lycopersicum%20var.%20cerasiforme",
      );
    });
  });

  it("falls back to the scientific name when binomial name is absent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...identificationPayload,
          candidates: [
            {
              ...identificationPayload.candidates[0],
              common_name: null,
              accepted_scientific_name: "Cotyledon tomentosa L.",
              binomial_name: null,
            },
          ],
        }),
      }),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    expect(
      await screen.findByRole("heading", { name: "Cotyledon tomentosa L." }),
    ).toBeInTheDocument();
  });

  it("blocks confirmation for candidates without GBIF validation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...identificationPayload,
          candidates: [
            {
              ...identificationPayload.candidates[0],
              validation_status: "no_gbif_match",
              gbif_key: null,
            },
          ],
        }),
      }),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    expect(
      await screen.findByText("Sin coincidencia GBIF"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Seleccionar esta planta" }),
    ).toBeDisabled();
  });

  it("hides candidate cards and the result count when the identification is a sad path", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...identificationPayload,
          sad_path: "retry_needed",
          message: "No pudimos identificar la planta. Proba con otra foto.",
          status: "retry_needed",
        }),
      }),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    expect(
      await screen.findByText("Necesitamos otra foto"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Posibles Coincidencias" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Seleccionar esta planta" }),
    ).not.toBeInTheDocument();
    expect(container.querySelector("hr")).not.toBeInTheDocument();
  });

  it("does not expose PlantCare placeholder copy on the redesigned identification flow", () => {
    const { container } = render(<IdentifyFlow />);
    expect(container.textContent).not.toMatch(/PlantCare/);
  });

  it("resets the flow when the user clicks Eliminar y repetir from the analyzed photo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => identificationPayload,
      }),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    expect(await screen.findByText("Imagen analizada con éxito")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Eliminar y repetir" }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Subir Foto" }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("Imagen analizada con éxito")).not.toBeInTheDocument();
  });

  it("uses a placeholder image frame in the result cards instead of the uploaded preview", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => identificationPayload,
      }),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    await screen.findByRole("heading", { name: "Pata de oso" });

    const capturedPanel = Array.from(container.querySelectorAll("section")).find(
      (section) => section.textContent?.includes("Imagen analizada con éxito"),
    );
    expect(capturedPanel).toBeDefined();
    const candidateGrid = container.querySelector(
      "ul[role='list']:not([aria-hidden='true'])",
    );
    expect(candidateGrid).toBeTruthy();
    expect(candidateGrid?.querySelectorAll("img").length ?? 0).toBe(0);
  });

  it("places the Posibles Coincidencias header below the divider in the post-identification view", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => identificationPayload,
      }),
    );
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    await screen.findByRole("heading", { name: "Pata de oso" });

    const divider = container.querySelector("hr");
    expect(divider).toBeTruthy();
    const resultsHeading = Array.from(container.querySelectorAll("h2")).find(
      (heading) => heading.textContent === "Posibles Coincidencias",
    );
    expect(resultsHeading).toBeDefined();
    const comparison = divider!.compareDocumentPosition(resultsHeading!);
    expect(
      Boolean(comparison & Node.DOCUMENT_POSITION_FOLLOWING),
    ).toBe(true);
  });
});
