import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AssistantChat, AssistantMessageContent } from "./AssistantChat";

const mocks = vi.hoisted(() => ({
  createReminder: vi.fn(),
  sendAssistantMessage: vi.fn(),
  searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => mocks.searchParams,
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    createReminder: mocks.createReminder,
    sendAssistantMessage: mocks.sendAssistantMessage,
  },
}));

describe("AssistantChat", () => {
  beforeEach(() => {
    mocks.createReminder.mockReset();
    mocks.sendAssistantMessage.mockReset();
    mocks.searchParams = new URLSearchParams();
    mocks.createReminder.mockResolvedValue({ id: "reminder-1" });
    mocks.sendAssistantMessage.mockResolvedValue({
      conversation_id: "conversation-1",
      message: {
        role: "assistant",
        content: "Tengo una sugerencia lista para confirmar.",
        content_format: "plain_text",
      },
      sources: [],
      requires_confirmation: true,
      reminder_suggestion: {
        garden_plant_id: "garden-1",
        plant_name: "Pata",
        action: "regar",
        due_at: "2026-06-01T10:30:00Z",
        recurrence: "weekly",
        suggestion_justification: "Sugerido por el asistente desde la conversacion.",
      },
      tool_failures: [],
    });
  });

  it("renders an assistant reminder suggestion confirmation card", async () => {
    render(<AssistantChat />);

    fireEvent.change(screen.getByPlaceholderText("Ej: Como ajusto el riego de mi Monstera?"), {
      target: { value: "Sugerime un recordatorio para Pata" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Recordatorio sugerido")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "regar" })).toBeInTheDocument();
    expect(screen.getByText(/Pata .* Semanal/)).toBeInTheDocument();
    expect(screen.getByText("Sugerido por el asistente desde la conversacion.")).toBeInTheDocument();
  });

  it("creates an accepted assistant reminder suggestion once", async () => {
    render(<AssistantChat />);

    fireEvent.change(screen.getByPlaceholderText("Ej: Como ajusto el riego de mi Monstera?"), {
      target: { value: "Sugerime un recordatorio para Pata" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    const accept = await screen.findByRole("button", { name: "Aceptar sugerencia" });
    fireEvent.click(accept);

    await waitFor(() => {
      expect(mocks.createReminder).toHaveBeenCalledTimes(1);
    });
    expect(mocks.createReminder).toHaveBeenCalledWith({
      garden_plant_id: "garden-1",
      action: "regar",
      date: "2026-06-01",
      time: "10:30",
      recurrence: "weekly",
      suggestion_justification: "Sugerido por el asistente desde la conversacion.",
    });
    expect(await screen.findByRole("button", { name: "Recordatorio creado" })).toBeDisabled();
  });

  it("maps assistant taxonomy query parameters to the chat payload", async () => {
    mocks.searchParams = new URLSearchParams({
      plant: "Tomato",
      binomial: "Solanum lycopersicum",
      scientific: "Solanum lycopersicum var. cerasiforme",
    });

    render(<AssistantChat />);

    expect(screen.getByText("Contexto inicial: Tomato")).toBeInTheDocument();
    expect(screen.getByText("Solanum lycopersicum")).toBeInTheDocument();
    expect(screen.queryByText("Solanum lycopersicum var. cerasiforme")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() => {
      expect(mocks.sendAssistantMessage).toHaveBeenCalledWith({
        message: "Tengo una consulta sobre Tomato:",
        conversation_id: null,
        plant: "Tomato",
        plant_binomial_name: "Solanum lycopersicum",
        plant_scientific_name: "Solanum lycopersicum var. cerasiforme",
      });
    });
  });

  it("keeps plant-only assistant requests compatible", async () => {
    mocks.searchParams = new URLSearchParams({ plant: "Pata" });

    render(<AssistantChat />);

    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() => {
      expect(mocks.sendAssistantMessage).toHaveBeenCalledWith({
        message: "Tengo una consulta sobre Pata:",
        conversation_id: null,
        plant: "Pata",
        plant_binomial_name: null,
        plant_scientific_name: null,
      });
    });
  });

  it("renders assistant plain text with newline characters preserved in content", async () => {
    mocks.sendAssistantMessage.mockResolvedValue({
      conversation_id: "conversation-1",
      message: { role: "assistant", content: "Linea uno\nLinea dos", content_format: "plain_text" },
      sources: [],
      requires_confirmation: false,
      reminder_suggestion: null,
      tool_failures: [],
    });

    render(<AssistantChat />);

    fireEvent.change(screen.getByPlaceholderText("Ej: Como ajusto el riego de mi Monstera?"), {
      target: { value: "Como riego?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    const content = await screen.findByText(
      (_, element) => element?.tagName === "SPAN" && element.textContent === "Linea uno\nLinea dos",
    );

    expect(content).toBeInTheDocument();
    expect(content.className).toContain("messageContent");
  });

  it("renders markdown format as raw text without parsing", async () => {
    mocks.sendAssistantMessage.mockResolvedValue({
      conversation_id: "conversation-1",
      message: { role: "assistant", content: "**No parsear**", content_format: "markdown" },
      sources: [],
      requires_confirmation: false,
      reminder_suggestion: null,
      tool_failures: [],
    });

    render(<AssistantChat />);

    fireEvent.change(screen.getByPlaceholderText("Ej: Como ajusto el riego de mi Monstera?"), {
      target: { value: "Como riego?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("**No parsear**")).toBeInTheDocument();
    expect(screen.queryByText("No parsear", { selector: "strong" })).not.toBeInTheDocument();
  });

  it("renders missing and unsupported content formats as raw text", () => {
    const { rerender } = render(<AssistantMessageContent content="Sin formato" />);

    expect(screen.getByText("Sin formato")).toBeInTheDocument();

    rerender(<AssistantMessageContent content="Formato futuro" contentFormat={"future" as never} />);

    expect(screen.getByText("Formato futuro")).toBeInTheDocument();
  });

  it("shows retryable error without appending assistant message bubble", async () => {
    mocks.sendAssistantMessage.mockResolvedValue({
      retryable: true,
      error_type: "total_generation_failure",
      detail: "No model-generated assistant response could be produced. Please retry.",
      failure_category: "all_providers_failed",
      provider_failures: [{
        provider: "gemini",
        role: "model",
        operation: "generate_text",
        failure_category: "service_unavailable",
        retryable: false,
        transient: false,
        status_code: null,
        cause_type: null,
        attempt_index: 0,
      }],
      conversation_id: "conversation-retry-1",
    });

    render(<AssistantChat />);

    fireEvent.change(screen.getByPlaceholderText("Ej: Como ajusto el riego de mi Monstera?"), {
      target: { value: "Cada cuanto riego mi Pata?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Cada cuanto riego mi Pata?")).toBeInTheDocument();
    expect(screen.getByText("No model-generated assistant response could be produced. Please retry.")).toBeInTheDocument();
    expect(screen.queryByText("Tengo una sugerencia lista para confirmar.")).not.toBeInTheDocument();
  });
});
