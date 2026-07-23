import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IdentifyFlow } from "./IdentifyFlow";

const mocks = vi.hoisted(() => ({
  confirmCandidate: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: { confirmCandidate: mocks.confirmCandidate },
}));

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
    mocks.confirmCandidate.mockReset().mockResolvedValue({
      candidate: { confirmed_at: "2026-01-01T00:00:00Z" },
      enrichment: { candidate_id: "candidate-1", policy_version: 1, job: { id: "job-1", status: "pending" } },
      status: "confirmed",
    });
    mocks.push.mockReset();
    URL.createObjectURL = vi.fn(() => "blob:preview");
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

  it("uses typed confirmation and navigates to the profile immediately", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({ ok: true, json: async () => identificationPayload }),
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

    await waitFor(() => expect(mocks.confirmCandidate).toHaveBeenCalledWith("identification-1", "candidate-1"));
    expect(mocks.push).toHaveBeenCalledWith(
      "/profiles/Cotyledon%20tomentosa?candidateId=candidate-1",
    );
  });

  it("allows only one pending confirmation, shows progress, and does not navigate after a 503", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({ ok: true, json: async () => identificationPayload }),
    );
    let rejectConfirmation!: (reason: Error) => void;
    mocks.confirmCandidate.mockReturnValueOnce(new Promise((_, reject) => {
      rejectConfirmation = reject;
    }));
    const { container } = render(<IdentifyFlow />);
    const upload = container.querySelector(
      'input[accept="image/jpeg,image/png,image/webp"]',
    ) as HTMLInputElement;

    fireEvent.change(upload, {
      target: { files: [new File(["image"], "plant.jpg", { type: "image/jpeg" })] },
    });

    const confirmButton = await screen.findByRole("button", { name: "Seleccionar esta planta" });
    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);

    expect(mocks.confirmCandidate).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Confirmando planta..." })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Confirmando la planta y preparando su perfil...");
    expect(mocks.push).not.toHaveBeenCalled();

    await act(async () => {
      rejectConfirmation(new Error("Servicio temporalmente no disponible (503)."));
    });

    expect(await screen.findByText("Servicio temporalmente no disponible (503).")).toBeInTheDocument();
    expect(mocks.push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Seleccionar esta planta" })).toBeEnabled();
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
      expect(mocks.push).toHaveBeenCalledWith(
        "/profiles/Solanum%20lycopersicum%20var.%20cerasiforme?candidateId=candidate-1",
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
