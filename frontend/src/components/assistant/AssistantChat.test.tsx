import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AssistantChat } from "./AssistantChat";

const mocks = vi.hoisted(() => ({
  createReminder: vi.fn(),
  sendAssistantMessage: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: () => null }),
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
    mocks.createReminder.mockResolvedValue({ id: "reminder-1" });
    mocks.sendAssistantMessage.mockResolvedValue({
      conversation_id: "conversation-1",
      message: { role: "assistant", content: "Tengo una sugerencia lista para confirmar." },
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
});
