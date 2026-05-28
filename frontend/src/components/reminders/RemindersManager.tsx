"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ApiClientError, apiClient, type GardenPlant, type Reminder, type ReminderCreate } from "@/lib/api/client";
import styles from "@/components/garden/PlantProfileView.module.scss";

type FormState = {
  garden_plant_id: string;
  action: string;
  date: string;
  time: string;
  recurrence: ReminderCreate["recurrence"];
};

type FormErrors = Partial<Record<keyof FormState, string>>;

const recurrenceLabels: Record<string, string> = {
  none: "No repetir",
  daily: "Diario",
  weekly: "Semanal",
  monthly: "Mensual",
};

export function RemindersManager() {
  const searchParams = useSearchParams();
  const plantHint = searchParams.get("plant")?.toLowerCase() ?? "";
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>({
    garden_plant_id: "",
    action: "",
    date: "",
    time: "",
    recurrence: "none",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [editing, setEditing] = useState<Reminder | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [permissionNotice, setPermissionNotice] = useState<string | null>(null);

  const garden = useQuery({ queryKey: ["garden", "list", ""], queryFn: () => apiClient.listGardenPlants() });
  const reminders = useQuery({ queryKey: ["reminders", "list"], queryFn: () => apiClient.listReminders() });
  const plants = garden.data ?? [];

  useEffect(() => {
    if (form.garden_plant_id || !plants.length) return;
    const hinted = plants.find((plant) => plant.profile.scientific_name.toLowerCase() === plantHint);
    setForm((current) => ({ ...current, garden_plant_id: hinted?.id ?? plants[0].id }));
  }, [form.garden_plant_id, plantHint, plants]);

  const createReminder = useMutation({
    mutationFn: (payload: ReminderCreate) => apiClient.createReminder(payload),
    onSuccess: async () => {
      await afterReminderChange();
      resetForm();
      await requestNotificationPermission();
      setNotice("Recordatorio guardado.");
    },
    onError: handleMutationError,
  });

  const updateReminder = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ReminderCreate }) => apiClient.updateReminder(id, payload),
    onSuccess: async () => {
      await afterReminderChange();
      resetForm();
      setNotice("Recordatorio actualizado.");
    },
    onError: handleMutationError,
  });

  const completeReminder = useMutation({
    mutationFn: (id: string) => apiClient.completeReminder(id),
    onSuccess: async (reminder) => {
      await afterReminderChange();
      setNotice(
        reminder.next_occurrence_at
          ? `Completado. Proximo recordatorio: ${formatDateTime(reminder.next_occurrence_at)}.`
          : "Recordatorio completado.",
      );
    },
    onError: handleMutationError,
  });

  const deleteReminder = useMutation({
    mutationFn: (id: string) => apiClient.deleteReminder(id),
    onSuccess: async () => {
      await afterReminderChange();
      setNotice("Recordatorio eliminado.");
    },
    onError: handleMutationError,
  });

  async function afterReminderChange() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["reminders", "list"] }),
      queryClient.invalidateQueries({ queryKey: ["garden", "list"] }),
    ]);
  }

  function handleMutationError(caught: Error) {
    setNotice(caught instanceof ApiClientError ? caught.message : caught.message || "No pudimos guardar el recordatorio.");
  }

  function setField<Key extends keyof FormState>(key: Key, value: FormState[Key]) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice(null);
    const nextErrors = validateForm(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    const payload: ReminderCreate = {
      garden_plant_id: form.garden_plant_id,
      action: form.action.trim(),
      date: form.date,
      time: form.time,
      recurrence: form.recurrence,
      suggestion_justification: editing?.suggestion_justification ?? null,
    };
    if (editing) updateReminder.mutate({ id: editing.id, payload });
    else createReminder.mutate(payload);
  }

  function editReminder(reminder: Reminder) {
    setEditing(reminder);
    setForm({
      garden_plant_id: reminder.garden_plant_id,
      action: reminder.action,
      date: reminder.due_at.slice(0, 10),
      time: reminder.due_at.slice(11, 16),
      recurrence: reminder.recurrence,
    });
    setNotice(null);
  }

  function resetForm() {
    setEditing(null);
    setErrors({});
    setForm({
      garden_plant_id: form.garden_plant_id || plants[0]?.id || "",
      action: "",
      date: "",
      time: "",
      recurrence: "none",
    });
  }

  async function acceptSuggestion(suggestion: SuggestedReminder) {
    const next = {
      garden_plant_id: suggestion.garden_plant_id,
      action: suggestion.action,
      date: suggestion.date,
      time: suggestion.time,
      recurrence: suggestion.recurrence,
      suggestion_justification: suggestion.justification,
    } satisfies ReminderCreate;
    createReminder.mutate(next);
  }

  async function requestNotificationPermission() {
    if (!("Notification" in window)) {
      setPermissionNotice("Tu navegador no soporta notificaciones; el recordatorio queda guardado igualmente.");
      return;
    }
    if (Notification.permission === "granted") {
      setPermissionNotice("Las notificaciones estan habilitadas.");
      return;
    }
    if (Notification.permission === "denied") {
      setPermissionNotice("No se enviaran notificaciones porque el permiso fue rechazado; el recordatorio sigue guardado.");
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setPermissionNotice("No se enviaran notificaciones porque el permiso fue rechazado; el recordatorio sigue guardado.");
    } else {
      setPermissionNotice("Las notificaciones estan habilitadas.");
    }
  }

  const suggestions = buildSuggestions(plants, plantHint);
  const pending = createReminder.isPending || updateReminder.isPending;

  return (
    <section className={styles.profile}>
      <div className={styles.hero}>
        <p className={styles.eyebrow}>Recordatorios</p>
        <h1>Cuidados con fecha.</h1>
        <p>Crea recordatorios manuales, acepta sugerencias IA y completa tareas recurrentes sin perder el proximo cuidado.</p>
      </div>

      <form className={styles.form} onSubmit={submit} noValidate>
        <label>
          Planta
          <select value={form.garden_plant_id} onChange={(event) => setField("garden_plant_id", event.target.value)}>
            <option value="">Selecciona una planta</option>
            {plants.map((plant) => (
              <option key={plant.id} value={plant.id}>{plantLabel(plant)}</option>
            ))}
          </select>
        </label>
        {errors.garden_plant_id ? <p className={styles.error}>{errors.garden_plant_id}</p> : null}

        <label>
          Accion
          <input value={form.action} onChange={(event) => setField("action", event.target.value)} placeholder="Ej: regar" />
        </label>
        {errors.action ? <p className={styles.error}>{errors.action}</p> : null}

        <label>
          Fecha
          <input type="date" value={form.date} onChange={(event) => setField("date", event.target.value)} />
        </label>
        {errors.date ? <p className={styles.error}>{errors.date}</p> : null}

        <label>
          Hora
          <input type="time" value={form.time} onChange={(event) => setField("time", event.target.value)} />
        </label>
        {errors.time ? <p className={styles.error}>{errors.time}</p> : null}

        <label>
          Recurrencia
          <select value={form.recurrence} onChange={(event) => setField("recurrence", event.target.value as FormState["recurrence"])}>
            {Object.entries(recurrenceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        {errors.recurrence ? <p className={styles.error}>{errors.recurrence}</p> : null}

        <button type="submit" disabled={pending || !plants.length}>{pending ? "Guardando..." : editing ? "Actualizar" : "Crear recordatorio"}</button>
        {editing ? <button type="button" onClick={resetForm}>Cancelar edicion</button> : null}
      </form>

      {notice ? <p className={styles.notice}>{notice}</p> : null}
      {permissionNotice ? <p className={styles.warning}>{permissionNotice}</p> : null}
      {garden.isError ? <p className={styles.error}>{garden.error.message || "No pudimos cargar tus plantas."}</p> : null}
      {!garden.isLoading && !plants.length ? <p className={styles.warning}>Guarda una planta en Mi Jardin antes de crear recordatorios.</p> : null}

      <section className={styles.sections}>
        {suggestions.map((suggestion) => (
          <article className={styles.card} key={`${suggestion.garden_plant_id}-${suggestion.action}`}>
            <p className={styles.eyebrow}>Sugerencia IA</p>
            <h2>{suggestion.action}</h2>
            <p>{suggestion.justification}</p>
            <button type="button" onClick={() => acceptSuggestion(suggestion)} disabled={createReminder.isPending}>Aceptar sugerencia</button>
          </article>
        ))}
      </section>

      <section className={styles.sections} aria-live="polite">
        {reminders.isLoading ? <p className={styles.notice}>Cargando recordatorios...</p> : null}
        {reminders.isError ? <p className={styles.error}>{reminders.error.message || "No pudimos cargar recordatorios."}</p> : null}
        {(reminders.data ?? []).map((reminder) => (
          <article className={styles.card} key={reminder.id}>
            <p className={styles.eyebrow}>{reminder.status === "pending" ? "Pendiente" : "Completado"}</p>
            <h2>{reminder.action}</h2>
            <p>{reminder.plant_name} · {formatDateTime(reminder.due_at)} · {recurrenceLabels[reminder.recurrence]}</p>
            {reminder.suggestion_justification ? <p>{reminder.suggestion_justification}</p> : null}
            {reminder.next_occurrence_at ? <p>Proximo: {formatDateTime(reminder.next_occurrence_at)}</p> : null}
            <div className={styles.ctas}>
              <button type="button" onClick={() => editReminder(reminder)} disabled={reminder.status !== "pending"}>Editar</button>
              <button type="button" onClick={() => completeReminder.mutate(reminder.id)} disabled={reminder.status !== "pending" || completeReminder.isPending}>Completar</button>
              <button type="button" onClick={() => deleteReminder.mutate(reminder.id)} disabled={deleteReminder.isPending}>Eliminar</button>
            </div>
          </article>
        ))}
      </section>
    </section>
  );
}

type SuggestedReminder = ReminderCreate & { justification: string };

function validateForm(form: FormState): FormErrors {
  const nextErrors: FormErrors = {};
  if (!form.garden_plant_id) nextErrors.garden_plant_id = "Selecciona una planta.";
  if (!form.action.trim()) nextErrors.action = "Indica una accion de cuidado.";
  if (!form.date) nextErrors.date = "Indica una fecha.";
  if (!form.time) nextErrors.time = "Indica una hora.";
  if (!Object.keys(recurrenceLabels).includes(form.recurrence)) nextErrors.recurrence = "Selecciona una recurrencia valida.";
  if (form.date && form.time && new Date(`${form.date}T${form.time}`) <= new Date()) {
    nextErrors.date = "La fecha y hora deben ser futuras.";
  }
  return nextErrors;
}

function buildSuggestions(plants: GardenPlant[], plantHint: string): SuggestedReminder[] {
  const selectedPlants = plantHint
    ? plants.filter((plant) => plant.profile.scientific_name.toLowerCase() === plantHint)
    : plants.slice(0, 2);
  const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
  const date = tomorrow.toISOString().slice(0, 10);
  return selectedPlants.map((plant) => ({
    garden_plant_id: plant.id,
    action: plant.profile.sections?.care?.[0]?.toLowerCase().includes("riego") ? "Revisar riego" : "Revisar estado general",
    date,
    time: "09:00",
    recurrence: "weekly",
    suggestion_justification: "Sugerido por el perfil de la planta y el contexto de Mi Jardin.",
    justification: `Basado en el perfil de ${plantLabel(plant)} y su contexto guardado. Requiere confirmacion antes de crearse.`,
  }));
}

function plantLabel(plant: GardenPlant) {
  return plant.nickname ?? plant.profile.selected_alias ?? plant.profile.common_name ?? plant.profile.scientific_name;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
