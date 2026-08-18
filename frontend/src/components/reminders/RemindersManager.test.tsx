import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClientError } from "@/lib/api/client";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";
import { RemindersManager } from "./RemindersManager";

const plant = {
  active_reminders: 0,
  confirmed_candidate_id: "candidate-1",
  created_at: "2026-01-01T00:00:00Z",
  custom_data: {},
  id: "garden-1",
  image_path: null,
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
    sections: { care: ["Riego moderado"] },
    selected_alias: null,
    sources: [],
  },
};

const reminder = {
  action: "Riego",
  due_at: "2999-01-10T09:00:00Z",
  garden_plant_id: "garden-1",
  id: "reminder-1",
  plant_name: "Helecho",
  recurrence: "weekly" as const,
  status: "pending" as const,
  suggestion_justification: null,
  timezone: "America/Argentina/Buenos_Aires",
};

const defaultSuggestion = {
  kind: "suggestion" as const,
  garden_plant_id: "garden-1",
  plant_name: "Helecho",
  action: "Riego",
  date: "2999-01-10",
  time: "09:00:00",
  timezone: "America/Argentina/Buenos_Aires",
  recurrence: "weekly" as const,
  evidence: {
    taxonomy: "Nephrolepis exaltata",
    location: "Balcón",
    notes: null,
    profile_sections: ["Riego moderado"],
    active_reminders: 0,
    light_context: null,
  },
  confidence: 0.9,
  limitations: [],
  justification: "Basado en el perfil de Helecho y su contexto guardado.",
};

const mocks = vi.hoisted(() => ({
  completeReminder: vi.fn(),
  createReminder: vi.fn(),
  deleteReminder: vi.fn(),
  getCurrentUser: vi.fn(),
  getParam: vi.fn(),
  listGardenPlants: vi.fn(),
  listReminders: vi.fn(),
  recordSuggestionMetric: vi.fn(),
  suggestReminder: vi.fn(),
  updateReminder: vi.fn(),
  updateTimezone: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: mocks.getParam }),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    apiClient: {
      completeReminder: mocks.completeReminder,
      createReminder: mocks.createReminder,
      deleteReminder: mocks.deleteReminder,
      getCurrentUser: mocks.getCurrentUser,
      listGardenPlants: mocks.listGardenPlants,
      listReminders: mocks.listReminders,
      recordSuggestionMetric: mocks.recordSuggestionMetric,
      suggestReminder: mocks.suggestReminder,
      updateReminder: mocks.updateReminder,
      updateTimezone: mocks.updateTimezone,
    },
  };
});

describe("RemindersManager", () => {
  beforeEach(() => {
    mocks.completeReminder.mockReset();
    mocks.createReminder.mockReset();
    mocks.deleteReminder.mockReset();
    mocks.getCurrentUser.mockReset();
    mocks.getParam.mockReset();
    mocks.listGardenPlants.mockReset();
    mocks.listReminders.mockReset();
    mocks.recordSuggestionMetric.mockReset();
    mocks.suggestReminder.mockReset();
    mocks.updateReminder.mockReset();
    mocks.updateTimezone.mockReset();

    mocks.getParam.mockReturnValue(null);
    mocks.getCurrentUser.mockResolvedValue({
      id: "user-1",
      name: "Ada",
      email: "ada@example.com",
      email_verified: true,
      timezone: "America/Argentina/Buenos_Aires",
    });
    mocks.listGardenPlants.mockResolvedValue([plant]);
    mocks.listReminders.mockResolvedValue([reminder]);
    mocks.createReminder.mockResolvedValue(reminder);
    mocks.updateReminder.mockResolvedValue({ ...reminder, action: "Fertilizante" });
    mocks.completeReminder.mockResolvedValue({
      ...reminder,
      next_occurrence_at: "2999-01-17T09:00:00Z",
      status: "completed",
    });
    mocks.deleteReminder.mockResolvedValue({ status: "deleted" });
    mocks.recordSuggestionMetric.mockResolvedValue({ status: "recorded" });
    mocks.suggestReminder.mockResolvedValue(defaultSuggestion);
    vi.stubGlobal("Notification", { permission: "granted", requestPermission: vi.fn() });
  });

  it("renders loading and empty garden states", async () => {
    mocks.listGardenPlants.mockReturnValueOnce(new Promise(() => undefined));
    mocks.listReminders.mockReturnValueOnce(new Promise(() => undefined));

    const { unmount } = renderWithQueryClient(<RemindersManager />);

    expect(screen.getByText("Cargando recordatorios...")).toBeInTheDocument();
    unmount();

    mocks.listGardenPlants.mockResolvedValueOnce([]);
    mocks.listReminders.mockResolvedValueOnce([]);
    renderWithQueryClient(<RemindersManager />);

    expect(await screen.findByText("Guarda una planta en Mi Jardín antes de crear recordatorios.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar recordatorio" })).toBeDisabled();
  });

  it("prevents invalid submissions", async () => {
    renderWithQueryClient(<RemindersManager />);

    fireEvent.submit(screen.getByRole("button", { name: "Guardar recordatorio" }).closest("form")!);

    expect(await screen.findByText("Selecciona un tipo de tarea.")).toBeInTheDocument();
    expect(screen.getByText("Indica una fecha.")).toBeInTheDocument();
    expect(screen.getByText("Indica una hora.")).toBeInTheDocument();
    expect(mocks.createReminder).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/^Tipo de Tarea/), { target: { value: "Riego" } });
    fireEvent.change(screen.getByLabelText(/^Fecha/), { target: { value: "2000-01-01" } });
    fireEvent.change(screen.getByLabelText(/^Hora/), { target: { value: "09:00" } });
    fireEvent.submit(screen.getByRole("button", { name: "Guardar recordatorio" }).closest("form")!);

    expect(await screen.findByText("La fecha y hora deben ser futuras.")).toBeInTheDocument();
    expect(mocks.createReminder).not.toHaveBeenCalled();
  });

  it("creates a reminder and invalidates reminder and garden queries", async () => {
    const { queryClient } = renderWithQueryClient(<RemindersManager />);
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    await fillReminderForm("Riego", "2999-01-10", "09:00", "weekly");
    fireEvent.submit(screen.getByRole("button", { name: "Guardar recordatorio" }).closest("form")!);

    await waitFor(() => {
      expect(mocks.createReminder).toHaveBeenCalledWith({
        action: "Riego",
        date: "2999-01-10",
        garden_plant_id: "garden-1",
        recurrence: "weekly",
        suggestion_justification: null,
        time: "09:00",
        timezone: "America/Argentina/Buenos_Aires",
      });
    });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["reminders", "list"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["garden", "list"] });
    expect(await screen.findByText("Recordatorio guardado.")).toBeInTheDocument();
    expect(screen.getByText("Las notificaciones están habilitadas.")).toBeInTheDocument();
  });

  it("updates an existing reminder from the popover", async () => {
    renderWithQueryClient(<RemindersManager />);

    fireEvent.click(await screen.findByRole("button", { name: "Abrir acciones del recordatorio" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Editar" }));

    fireEvent.change(screen.getByLabelText(/^Tipo de Tarea/), { target: { value: "Fertilizante" } });
    fireEvent.submit(screen.getByRole("button", { name: "Actualizar recordatorio" }).closest("form")!);

    await waitFor(() => {
      expect(mocks.updateReminder).toHaveBeenCalledWith("reminder-1", {
        action: "Fertilizante",
        date: "2999-01-10",
        garden_plant_id: "garden-1",
        recurrence: "weekly",
        suggestion_justification: null,
        time: "06:00",
        timezone: "America/Argentina/Buenos_Aires",
      });
    });
    expect(await screen.findByText("Recordatorio actualizado.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar recordatorio" })).toBeInTheDocument();
  });

  it("prefills the edit form with the reminder's local date and time, not UTC", async () => {
    mocks.listReminders.mockResolvedValue([
      {
        ...reminder,
        due_at: "2999-01-10T09:00:00Z",
        timezone: "America/Argentina/Buenos_Aires",
      },
    ]);
    renderWithQueryClient(<RemindersManager />);

    fireEvent.click(await screen.findByRole("button", { name: "Abrir acciones del recordatorio" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Editar" }));

    expect(screen.getByLabelText(/^Fecha/)).toHaveValue("2999-01-10");
    expect(screen.getByLabelText(/^Hora/)).toHaveValue("06:00");
  });

  it("completes and deletes reminders from the popover", async () => {
    renderWithQueryClient(<RemindersManager />);

    fireEvent.click(await screen.findByRole("button", { name: "Abrir acciones del recordatorio" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Completar" }));

    await waitFor(() => {
      expect(mocks.completeReminder).toHaveBeenCalledWith("reminder-1");
    });
    expect(await screen.findByText(/Completado\. Próximo recordatorio:/)).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: "Abrir acciones del recordatorio" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Eliminar" }));

    await waitFor(() => {
      expect(mocks.deleteReminder).toHaveBeenCalledWith("reminder-1");
    });
    expect(await screen.findByText("Recordatorio eliminado.")).toBeInTheDocument();
  });

  it("renders a backend suggestion and accepts it with the backend justification", async () => {
    renderWithQueryClient(<RemindersManager />);

    await screen.findByRole("option", { name: "Helecho" });
    fireEvent.click(screen.getByRole("button", { name: "Generar con IA" }));

    expect(
      await screen.findByText(defaultSuggestion.justification),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Aceptar sugerencia" }));

    await waitFor(() => {
      expect(mocks.suggestReminder).toHaveBeenCalledWith({
        garden_plant_id: "garden-1",
        request: "",
      });
      expect(mocks.createReminder).toHaveBeenCalledWith({
        action: "Riego",
        date: "2999-01-10",
        garden_plant_id: "garden-1",
        recurrence: "weekly",
        suggestion_justification: defaultSuggestion.justification,
        time: "09:00:00",
        timezone: "America/Argentina/Buenos_Aires",
      });
    });
    await waitFor(() => {
      expect(mocks.recordSuggestionMetric).toHaveBeenCalledWith({
        outcome: "accepted",
      });
    });
  });

  it("renders a clarification outcome with the missing fields", async () => {
    mocks.suggestReminder.mockResolvedValueOnce({
      kind: "clarification",
      missing_fields: ["date", "time"],
    });

    renderWithQueryClient(<RemindersManager />);

    await screen.findByRole("option", { name: "Helecho" });
    fireEvent.click(screen.getByRole("button", { name: "Generar con IA" }));

    expect(
      await screen.findByText(/necesitamos que completes:/),
    ).toBeInTheDocument();
    expect(screen.getByText(/date, time/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Aceptar sugerencia" }),
    ).not.toBeInTheDocument();
  });

  it("renders a duplicate outcome referencing an existing reminder", async () => {
    mocks.suggestReminder.mockResolvedValueOnce({
      kind: "duplicate",
      existing_reminder_id: "reminder-1",
    });

    renderWithQueryClient(<RemindersManager />);

    await screen.findByRole("option", { name: "Helecho" });
    fireEvent.click(screen.getByRole("button", { name: "Generar con IA" }));

    expect(
      await screen.findByText(/Ya existe un recordatorio equivalente/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Aceptar sugerencia" }),
    ).not.toBeInTheDocument();
  });

  it("renders query and mutation failures", async () => {
    mocks.listReminders.mockRejectedValueOnce(new Error("No pudimos cargar recordatorios."));

    renderWithQueryClient(<RemindersManager />);

    expect(await screen.findByText("No pudimos cargar recordatorios.")).toBeInTheDocument();

    mocks.createReminder.mockRejectedValueOnce(new ApiClientError("Fecha inválida", 422));
    await fillReminderForm("Riego", "2999-01-10", "09:00", "none");
    fireEvent.submit(screen.getByRole("button", { name: "Guardar recordatorio" }).closest("form")!);

    expect(await screen.findByText("Fecha inválida")).toBeInTheDocument();
  });
});

async function fillReminderForm(taskType: string, date: string, time: string, recurrence: string) {
  await screen.findByRole("option", { name: "Helecho" });
  fireEvent.change(screen.getByLabelText(/^Tipo de Tarea/), { target: { value: taskType } });
  fireEvent.change(screen.getByLabelText(/^Fecha/), { target: { value: date } });
  fireEvent.change(screen.getByLabelText(/^Hora/), { target: { value: time } });
  fireEvent.click(screen.getByRole("radio", { name: labelForRecurrence(recurrence) }));
}

function labelForRecurrence(value: string) {
  switch (value) {
    case "daily":
      return "Diario";
    case "weekly":
      return "Semanal";
    case "monthly":
      return "Mensual";
    case "none":
    default:
      return "Personalizado";
  }
}
