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
};

const mocks = vi.hoisted(() => ({
  completeReminder: vi.fn(),
  createReminder: vi.fn(),
  deleteReminder: vi.fn(),
  getParam: vi.fn(),
  listGardenPlants: vi.fn(),
  listReminders: vi.fn(),
  updateReminder: vi.fn(),
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
      listGardenPlants: mocks.listGardenPlants,
      listReminders: mocks.listReminders,
      updateReminder: mocks.updateReminder,
    },
  };
});

describe("RemindersManager", () => {
  beforeEach(() => {
    mocks.completeReminder.mockReset();
    mocks.createReminder.mockReset();
    mocks.deleteReminder.mockReset();
    mocks.getParam.mockReset();
    mocks.listGardenPlants.mockReset();
    mocks.listReminders.mockReset();
    mocks.updateReminder.mockReset();

    mocks.getParam.mockReturnValue(null);
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
        time: "09:00",
      });
    });
    expect(await screen.findByText("Recordatorio actualizado.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar recordatorio" })).toBeInTheDocument();
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

  it("reveals suggestions after clicking Generar con IA", async () => {
    renderWithQueryClient(<RemindersManager />);

    await screen.findByRole("option", { name: "Helecho" });
    fireEvent.click(screen.getByRole("button", { name: "Generar con IA" }));
    fireEvent.click(await screen.findByRole("button", { name: "Aceptar sugerencia" }));

    await waitFor(() => {
      expect(mocks.createReminder).toHaveBeenCalledWith({
        action: "Riego",
        date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        garden_plant_id: "garden-1",
        recurrence: "weekly",
        suggestion_justification: expect.stringContaining("Basado en el perfil de Helecho"),
        time: "09:00",
      });
    });
  });

  it("accepts a generated suggestion when plant hint is set", async () => {
    mocks.getParam.mockReturnValue("nephrolepis exaltata");

    renderWithQueryClient(<RemindersManager />);

    await screen.findByRole("option", { name: "Helecho" });
    fireEvent.click(screen.getByRole("button", { name: "Generar con IA" }));
    fireEvent.click(await screen.findByRole("button", { name: "Aceptar sugerencia" }));

    await waitFor(() => {
      expect(mocks.createReminder).toHaveBeenCalledWith({
        action: "Riego",
        date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        garden_plant_id: "garden-1",
        recurrence: "weekly",
        suggestion_justification: expect.stringContaining("Basado en el perfil de Helecho"),
        time: "09:00",
      });
    });
  });

  it("falls back to 'Revisión general' when the care plan has no specific keyword", async () => {
    mocks.listGardenPlants.mockResolvedValueOnce([
      {
        ...plant,
        id: "garden-3",
        profile: { ...plant.profile, sections: { care: ["Inspeccion general del follaje"] } },
      },
    ]);

    renderWithQueryClient(<RemindersManager />);
    await screen.findByRole("option", { name: "Helecho" });
    fireEvent.click(screen.getByRole("button", { name: "Generar con IA" }));
    fireEvent.click(await screen.findByRole("button", { name: "Aceptar sugerencia" }));

    await waitFor(() => {
      expect(mocks.createReminder).toHaveBeenCalledWith(
        expect.objectContaining({ action: "Revisión general" }),
      );
    });
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
