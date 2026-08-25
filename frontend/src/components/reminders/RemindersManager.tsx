"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ApiClientError,
  apiClient,
  type GardenPlant,
  type Reminder,
  type ReminderCreate,
  type ReminderSuggestionOutcome,
  type ReminderSuggestionResult,
} from "@/lib/api/client";
import { resolveImageUrl } from "@/lib/images";
import { TIMEZONE_OPTIONS } from "@/lib/timezones";
import {
  BellIcon,
  DotsThreeVerticalIcon,
  PlantIcon,
} from "@phosphor-icons/react";
import {
  Button,
  Card,
  Chip,
  Field,
  Notice,
  PageHeader,
  SelectField,
} from "@/components/ui";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./RemindersManager.module.scss";
import Image from "next/image";

type FormState = {
  garden_plant_id: string;
  taskType: string;
  date: string;
  time: string;
  recurrence: ReminderCreate["recurrence"];
};

type FormErrors = Partial<Record<keyof FormState, string>>;

const TASK_TYPES = [
  "Riego",
  "Fertilizante",
  "Poda",
  "Trasplante",
  "Limpieza",
  "Revisión general",
] as const;
export type TaskType = (typeof TASK_TYPES)[number];

const recurrenceLabels: Record<string, string> = {
  none: "Personalizado",
  daily: "Diario",
  weekly: "Semanal",
  monthly: "Mensual",
};

const recurrenceOptions: Array<{
  value: ReminderCreate["recurrence"];
  label: string;
}> = [
  { value: "daily", label: "Diario" },
  { value: "weekly", label: "Semanal" },
  { value: "monthly", label: "Mensual" },
  { value: "none", label: "Personalizado" },
];

function TaskIcon() {
  return (
    <span className={styles.listTaskIcon} aria-hidden="true">
      <BellIcon
        aria-hidden="true"
        size="1.1rem"
        className={iconStyles.tonePrimary}
      />
    </span>
  );
}

function formatReminderDate(iso: string, timezone?: string | null): { primary: string; meta?: string } {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return { primary: iso };
  }
  const timeZone = timezone || undefined;
  const now = new Date();
  const nowInTz = new Date(
    new Intl.DateTimeFormat("en-US", {
      timeZone: timeZone || undefined,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(now),
  );
  const tomorrow = new Date(nowInTz);
  tomorrow.setDate(nowInTz.getDate() + 1);
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
  const time = date.toLocaleTimeString("es-AR", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
  });
  if (sameDay(date, tomorrow)) {
    return { primary: `Mañana, ${time}` };
  }
  const dayMonth = date
    .toLocaleDateString("es-AR", { timeZone, day: "2-digit", month: "short" })
    .replace(".", "");
  return { primary: `${dayMonth}, ${time}` };
}

function formatDateTime(value: string, timezone?: string | null) {
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: timezone || undefined,
  }).format(new Date(value));
}

function toLocalDateInput(value: string, timezone?: string | null): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone || undefined,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function toLocalTimeInput(value: string, timezone?: string | null): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(11, 16);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone || undefined,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("hour")}:${get("minute")}`;
}

export function RemindersManager() {
  const searchParams = useSearchParams();
  const plantHint = searchParams.get("plant")?.toLowerCase() ?? "";
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>({
    garden_plant_id: "",
    taskType: "",
    date: "",
    time: "",
    recurrence: "none",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [editing, setEditing] = useState<Reminder | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [permissionNotice, setPermissionNotice] = useState<string | null>(null);
  const [suggestionsVisible, setSuggestionsVisible] = useState(false);
  const [suggestionResult, setSuggestionResult] =
    useState<ReminderSuggestionOutcome | null>(null);
  const [suggestionPending, setSuggestionPending] = useState(false);
  const [suggestionError, setSuggestionError] = useState<string | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [userTimezone, setUserTimezone] = useState<string>("");
  const [timezoneNotice, setTimezoneNotice] = useState<string | null>(null);
  const [suggestionRequest, setSuggestionRequest] = useState("");
  const [timezoneDetected, setTimezoneDetected] = useState(false);

  // Keep off-list IANA zones (device-detected or legacy stored values)
  // selectable instead of silently rendering an empty select.
  const timezoneChoices = (() => {
    const known = new Set(TIMEZONE_OPTIONS.map((option) => option.value));
    const extras = Array.from(
      new Set([userTimezone].filter((value): value is string => Boolean(value) && !known.has(value))),
    ).map((value) => ({ value, label: `${value} (detectada)` }));
    return extras.length ? [...extras, ...TIMEZONE_OPTIONS] : TIMEZONE_OPTIONS;
  })();

  const garden = useQuery({
    queryKey: ["garden", "list", ""],
    queryFn: () => apiClient.listGardenPlants(),
  });
  const reminders = useQuery({
    queryKey: ["reminders", "list"],
    queryFn: () => apiClient.listReminders(),
  });
  const currentUser = useQuery({
    queryKey: ["user", "me"],
    queryFn: () => apiClient.getCurrentUser(),
  });
  const plants = useMemo(() => garden.data ?? [], [garden.data]);
  const plantById = useMemo(() => {
    const map = new Map<string, GardenPlant>();
    plants.forEach((plant) => map.set(plant.id, plant));
    return map;
  }, [plants]);

  useEffect(() => {
    if (form.garden_plant_id || !plants.length) return;
    const hinted = plants.find(
      (plant) => plant.profile.scientific_name.toLowerCase() === plantHint,
    );
    setForm((current) => ({
      ...current,
      garden_plant_id: hinted?.id ?? plants[0].id,
    }));
  }, [form.garden_plant_id, plantHint, plants]);

  useEffect(() => {
    if (!currentUser.isSuccess) return;
    const tz = currentUser.data?.timezone ?? "";
    if (tz) {
      setUserTimezone(tz);
      setTimezoneDetected(false);
      return;
    }
    // No stored preference: adopt the device-detected IANA zone as default.
    const detected = Intl.DateTimeFormat().resolvedOptions().timeZone ?? "";
    if (detected) {
      setUserTimezone(detected);
      setTimezoneDetected(true);
    }
  }, [currentUser.data, currentUser.isSuccess]);

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
    mutationFn: ({ id, payload }: { id: string; payload: ReminderCreate }) =>
      apiClient.updateReminder(id, payload),
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
      setOpenMenuId(null);
      setNotice(
        reminder.next_occurrence_at
          ? `Completado. Próximo recordatorio: ${formatDateTime(reminder.next_occurrence_at, reminder.timezone)}.`
          : "Recordatorio completado.",
      );
    },
    onError: handleMutationError,
  });

  const deleteReminder = useMutation({
    mutationFn: (id: string) => apiClient.deleteReminder(id),
    onSuccess: async () => {
      await afterReminderChange();
      setOpenMenuId(null);
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
    setNotice(
      caught instanceof ApiClientError
        ? caught.message
        : caught.message || "No pudimos guardar el recordatorio.",
    );
  }

  function setField<Key extends keyof FormState>(
    key: Key,
    value: FormState[Key],
  ) {
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
      action: form.taskType,
      date: form.date,
      time: form.time,
      recurrence: form.recurrence,
      suggestion_justification: editing?.suggestion_justification ?? null,
      timezone: userTimezone || null,
    };
    if (editing) updateReminder.mutate({ id: editing.id, payload });
    else createReminder.mutate(payload);
  }

  function editReminder(reminder: Reminder) {
    setEditing(reminder);
    setOpenMenuId(null);
    setForm({
      garden_plant_id: reminder.garden_plant_id,
      taskType: reminder.action,
      date: toLocalDateInput(reminder.due_at, reminder.timezone),
      time: toLocalTimeInput(reminder.due_at, reminder.timezone),
      recurrence: reminder.recurrence,
    });
    setNotice(null);
  }

  function cancelEdit() {
    setEditing(null);
    setOpenMenuId(null);
    setErrors({});
    setForm((current) => ({
      garden_plant_id: current.garden_plant_id || plants[0]?.id || "",
      taskType: "",
      date: "",
      time: "",
      recurrence: "none",
    }));
  }

  function resetForm() {
    setEditing(null);
    setErrors({});
    setForm((current) => ({
      garden_plant_id: current.garden_plant_id || plants[0]?.id || "",
      taskType: "",
      date: "",
      time: "",
      recurrence: "none",
    }));
  }

  async function generateSuggestions() {
    const gardenPlantId =
      form.garden_plant_id || plantHint || plants[0]?.id || "";
    if (!gardenPlantId) return;
    setSuggestionsVisible(true);
    setSuggestionError(null);
    setSuggestionResult(null);
    setSuggestionPending(true);
    try {
      const outcome = await apiClient.suggestReminder({
        garden_plant_id: gardenPlantId,
        request: suggestionRequest.trim(),
      });
      setSuggestionResult(outcome);
    } catch (caught) {
      setSuggestionError(
        caught instanceof ApiClientError
          ? caught.message
          : "No pudimos generar una sugerencia.",
      );
    } finally {
      setSuggestionPending(false);
    }
  }

  function acceptSuggestion(suggestion: ReminderSuggestionResult) {
    const next = {
      garden_plant_id: suggestion.garden_plant_id,
      action: suggestion.action,
      date: suggestion.date,
      time: suggestion.time,
      recurrence: suggestion.recurrence,
      suggestion_justification: suggestion.justification,
      timezone: suggestion.timezone || userTimezone || null,
    } satisfies ReminderCreate;
    createReminder.mutate(next, {
      onSuccess: () => recordSuggestionMetric("accepted"),
    });
  }

  function dismissSuggestion() {
    recordSuggestionMetric("rejected");
    setSuggestionsVisible(false);
    setSuggestionResult(null);
  }

  function editSuggestionBeforeSave(suggestion: ReminderSuggestionResult) {
    recordSuggestionMetric("edited");
    setForm({
      garden_plant_id: suggestion.garden_plant_id,
      taskType: matchTaskType(suggestion.action),
      date: suggestion.date,
      time: suggestion.time.slice(0, 5),
      recurrence: suggestion.recurrence,
    });
    setEditing(null);
    setErrors({});
    setSuggestionsVisible(false);
    setSuggestionResult(null);
  }

  function matchTaskType(action: string): string {
    const normalized = action.trim().toLowerCase();
    return (
      TASK_TYPES.find((task) => task.toLowerCase() === normalized) ??
      normalizeReminderAction(action)
    );
  }

  async function saveTimezonePreference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTimezoneNotice(null);
    try {
      const updated = await apiClient.updateTimezone(userTimezone || null);
      setUserTimezone(updated.timezone ?? "");
      setTimezoneNotice("Zona horaria guardada.");
      await queryClient.invalidateQueries({ queryKey: ["user", "me"] });
    } catch (caught) {
      setTimezoneNotice(
        caught instanceof ApiClientError
          ? caught.message
          : "No pudimos guardar la zona horaria.",
      );
    }
  }

  async function requestNotificationPermission() {
    if (!("Notification" in window)) {
      setPermissionNotice(
        "Tu navegador no soporta notificaciones; el recordatorio queda guardado igualmente.",
      );
      return;
    }
    if (Notification.permission === "granted") {
      setPermissionNotice("Las notificaciones están habilitadas.");
      return;
    }
    if (Notification.permission === "denied") {
      setPermissionNotice(
        "No se enviarán notificaciones porque el permiso fue rechazado; el recordatorio sigue guardado.",
      );
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setPermissionNotice(
        "No se enviarán notificaciones porque el permiso fue rechazado; el recordatorio sigue guardado.",
      );
    } else {
      setPermissionNotice("Las notificaciones están habilitadas.");
    }
  }

  const pending = createReminder.isPending || updateReminder.isPending;
  const activeCount = (reminders.data ?? []).filter(
    (reminder) => reminder.status === "pending",
  ).length;
  const showEmptyGarden = !garden.isLoading && !plants.length;
  const showRemindersLoading = reminders.isLoading;
  const showRemindersError = reminders.isError;
  const showRemindersEmpty =
    !reminders.isLoading &&
    !reminders.isError &&
    (reminders.data ?? []).length === 0;
  const submitLabel = pending
    ? "Guardando..."
    : editing
      ? "Actualizar recordatorio"
      : "Guardar recordatorio";

  return (
    <section className={styles.page}>
      <PageHeader eyebrow="Cuidados" heading="Recordatorios" />

      <div className={styles.layout}>
        <div className={styles.aside}>
          <Card
            variant="tonal"
            padding="md"
            className={styles.formCard}
            aria-labelledby="ai-suggestion-heading"
          >
            <h2 id="ai-suggestion-heading" className={styles.formHeading}>
              Sugerir con IA
            </h2>
            <p className={styles.recurrenceLabel}>
              Elegi la planta y dejamos que la IA proponga fecha, hora y frecuencia. Siempre podes editarlas antes de guardar.
            </p>
            <form
              className={styles.form}
              onSubmit={(event) => {
                event.preventDefault();
                generateSuggestions();
              }}
              noValidate
            >
              <Field
                label="Contexto (opcional)"
                placeholder="p. ej., riego semanal en el balcon"
                value={suggestionRequest}
                onChange={(event) => setSuggestionRequest(event.target.value)}
              />
              <div className={styles.formActions}>
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  fullWidth
                  disabled={!plants.length || suggestionPending}
                >
                  {suggestionPending ? "Generando sugerencia..." : "Sugerir recordatorio"}
                </Button>
              </div>
            </form>
            {suggestionsVisible ? suggestionResult ? (
              <SuggestionOutcomeCard
                outcome={suggestionResult}
                onAccept={acceptSuggestion}
                onEdit={editSuggestionBeforeSave}
                onDismiss={dismissSuggestion}
                pending={createReminder.isPending}
              />
            ) : null : null}
            {suggestionError ? (
              <Notice tone="error" role="alert">{suggestionError}</Notice>
            ) : null}
          </Card>

          <Card
            variant="tonal"
            padding="md"
            className={styles.formCard}
            aria-labelledby="reminders-form-heading"
          >
            <h2 id="reminders-form-heading" className={styles.formHeading}>
              Crear manualmente
            </h2>
            <form className={styles.form} onSubmit={submit} noValidate>
              <SelectField
                kind="select"
                label="Planta"
                value={form.garden_plant_id}
                onChange={(event) =>
                  setField("garden_plant_id", event.target.value)
                }
                error={errors.garden_plant_id}
                required
                disabled={showEmptyGarden}
              >
                <option value="">Seleccionar Planta</option>
                {plants.map((plant) => (
                  <option key={plant.id} value={plant.id}>
                    {plantLabel(plant)}
                  </option>
                ))}
              </SelectField>

              <SelectField
                kind="select"
                label="Tipo de Tarea"
                value={form.taskType}
                onChange={(event) => setField("taskType", event.target.value)}
                error={errors.taskType}
                required
              >
                <option value="">Seleccionar Tarea</option>
                {TASK_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </SelectField>

              <div className={styles.formRow}>
                <Field
                  label="Fecha"
                  type="date"
                  value={form.date}
                  onChange={(event) => setField("date", event.target.value)}
                  error={errors.date}
                  required
                />
                <Field
                  label="Hora"
                  type="time"
                  value={form.time}
                  onChange={(event) => setField("time", event.target.value)}
                  error={errors.time}
                  required
                />
              </div>

              <div className={styles.recurrenceGroup}>
                <p id="recurrence-label" className={styles.recurrenceLabel}>
                  Frecuencia
                </p>
                <div
                  className={styles.recurrenceOptions}
                  role="radiogroup"
                  aria-labelledby="recurrence-label"
                >
                  {recurrenceOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      role="radio"
                      aria-checked={form.recurrence === option.value}
                      aria-pressed={form.recurrence === option.value}
                      className={styles.recurrenceOption}
                      onClick={() => setField("recurrence", option.value)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                {errors.recurrence ? (
                  <p
                    className={styles.recurrenceLabel}
                    role="alert"
                    style={{ color: "var(--color-error, #ba1a1a)" }}
                  >
                    {errors.recurrence}
                  </p>
                ) : null}
              </div>

              <div className={styles.formActions}>
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  fullWidth
                  className={styles.formSubmit}
                  disabled={pending || showEmptyGarden}
                >
                  {submitLabel}
                </Button>
              </div>
            </form>
          </Card>

          <Card
            variant="tonal"
            padding="md"
            className={styles.formCard}
            aria-labelledby="timezone-preference-heading"
          >
            <h2 id="timezone-preference-heading" className={styles.formHeading}>
              Mi Zona Horaria
            </h2>
            <p className={styles.recurrenceLabel}>
              Se usa como zona por defecto para tus recordatorios.
              {timezoneDetected ? " Detectada de tu dispositivo." : ""}
            </p>
            <form className={styles.form} onSubmit={saveTimezonePreference} noValidate>
              <SelectField
                kind="select"
                label="Zona horaria"
                value={userTimezone}
                onChange={(event) => setUserTimezone(event.target.value)}
                optionalLabel="opcional"
              >
                <option value="">Sin definir</option>
                {timezoneChoices.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </SelectField>
              <div className={styles.formActions}>
                <Button
                  type="submit"
                  variant="secondary"
                  size="md"
                  fullWidth
                  className={styles.formSubmit}
                >
                  Guardar zona horaria
                </Button>
              </div>
              {timezoneNotice ? (
                <p className={styles.recurrenceLabel} role="status">
                  {timezoneNotice}
                </p>
              ) : null}
            </form>
          </Card>

                  </div>

        <div className={styles.listColumn}>
          {notice ? (
            <Notice tone="success" role="status">
              {notice}
            </Notice>
          ) : null}
          {permissionNotice ? (
            <Notice tone="info" role="status">
              {permissionNotice}
            </Notice>
          ) : null}
          {garden.isError ? (
            <Notice tone="error">
              {garden.error.message || "No pudimos cargar tus plantas."}
            </Notice>
          ) : null}
          {showEmptyGarden ? (
            <Notice tone="warning">
              Guarda una planta en Mi Jardín antes de crear recordatorios.
            </Notice>
          ) : null}
          {showRemindersError ? (
            <Notice tone="error">
              {reminders.error.message || "No pudimos cargar recordatorios."}
            </Notice>
          ) : null}

          <article
            className={styles.listCard}
            aria-labelledby="reminders-list-heading"
          >
            <header className={styles.listHeader}>
              <h2
                id="reminders-list-heading"
                className={styles.listHeaderTitle}
              >
                Lista de Recordatorios Actuales
              </h2>
              <Chip tone="success">
                {activeCount} {activeCount === 1 ? "activo" : "activos"}
              </Chip>
            </header>

            <div className={styles.listColumns} aria-hidden="true">
              <p className={styles.listColumnHeading}>PLANTA</p>
              <p className={styles.listColumnHeading}>TAREA</p>
              <p className={styles.listColumnHeading}>PRÓXIMA FECHA</p>
              <p className={styles.listColumnHeadingRight}>ACCIÓN</p>
            </div>

            {showRemindersLoading ? (
              <span role="status" className={styles.srOnly}>
                Cargando recordatorios...
              </span>
            ) : null}

            <div className={styles.listRows} aria-live="polite">
              {showRemindersLoading ? <ReminderSkeletonRows /> : null}

              {!showRemindersLoading && showRemindersEmpty ? (
                <div className={styles.emptyState}>
                  <strong>Todavía no tenés recordatorios.</strong>
                  <span>
                    Creá uno desde el formulario o generá una sugerencia con IA.
                  </span>
                </div>
              ) : null}

              {!showRemindersLoading && !showRemindersEmpty
                ? (reminders.data ?? []).map((reminder) => (
                    <ReminderRow
                      key={reminder.id}
                      reminder={reminder}
                      plant={plantById.get(reminder.garden_plant_id)}
                      isOpen={openMenuId === reminder.id}
                      isEditing={editing?.id === reminder.id}
                      onToggleMenu={() =>
                        setOpenMenuId((current) =>
                          current === reminder.id ? null : reminder.id,
                        )
                      }
                      onCloseMenu={() => setOpenMenuId(null)}
                      onEdit={editReminder}
                      onCancelEdit={cancelEdit}
                      onComplete={(id) => completeReminder.mutate(id)}
                      onDelete={(id) => deleteReminder.mutate(id)}
                      completePending={completeReminder.isPending}
                      deletePending={deleteReminder.isPending}
                    />
                  ))
                : null}
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}

type ReminderRowProps = {
  reminder: Reminder;
  plant: GardenPlant | undefined;
  isOpen: boolean;
  isEditing: boolean;
  onToggleMenu: () => void;
  onCloseMenu: () => void;
  onEdit: (reminder: Reminder) => void;
  onCancelEdit: () => void;
  onComplete: (id: string) => void;
  onDelete: (id: string) => void;
  completePending: boolean;
  deletePending: boolean;
};

function ReminderRow({
  reminder,
  plant,
  isOpen,
  isEditing,
  onToggleMenu,
  onCloseMenu,
  onEdit,
  onCancelEdit,
  onComplete,
  onDelete,
  completePending,
  deletePending,
}: ReminderRowProps) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isPending = reminder.status === "pending";
  const plantImage = resolveImageUrl(plant?.image_path ?? null);
  const dateInfo = formatReminderDate(reminder.due_at, reminder.timezone);

  useEffect(() => {
    if (!isOpen) return;
    function handlePointerDown(event: PointerEvent) {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(event.target as Node)) {
        onCloseMenu();
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onCloseMenu();
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen, onCloseMenu]);

  return (
    <div className={styles.listRow} data-status={reminder.status}>
      <div className={styles.listPlant}>
        <span className={styles.listPlantAvatar} aria-hidden="true">
          {plantImage ? (
            <Image
              className={styles.listPlantImage}
              src={plantImage}
              alt=""
              layout="fill"
            />
          ) : (
            <PlantIcon
              aria-hidden="true"
              size="1rem"
              className={iconStyles.tonePrimary}
            />
          )}
        </span>
        <span className={styles.listPlantName}>{reminder.plant_name}</span>
      </div>

      <div className={styles.listTask} aria-label="Tarea">
        <TaskIcon />
        <span>{reminder.action}</span>
      </div>

      <div className={styles.listDate}>
        <span className={styles.listDatePrimary}>{dateInfo.primary}</span>
        {reminder.next_occurrence_at ? (
          <span className={styles.listDateMeta}>
            Próxima:{" "}
            {formatReminderDate(reminder.next_occurrence_at, reminder.timezone).primary}
          </span>
        ) : null}
      </div>

      <div className={styles.listActionsCell} ref={menuRef}>
        <button
          type="button"
          className={styles.listActionsTrigger}
          aria-label="Abrir acciones del recordatorio"
          aria-haspopup="menu"
          aria-expanded={isOpen}
          data-open={isOpen ? "true" : "false"}
          onClick={onToggleMenu}
        >
          <DotsThreeVerticalIcon
            aria-hidden="true"
            size="1.25rem"
            className={iconStyles.toneMuted}
          />
        </button>
        {isOpen ? (
          <div role="menu" className={styles.rowActionsMenu}>
            <button
              type="button"
              role="menuitem"
              className={styles.rowActionsItem}
              onClick={() => onEdit(reminder)}
              disabled={!isPending || isEditing}
            >
              {isEditing ? "Editando..." : "Editar"}
            </button>
            <button
              type="button"
              role="menuitem"
              className={styles.rowActionsItem}
              onClick={() => onComplete(reminder.id)}
              disabled={!isPending || completePending}
            >
              {completePending ? "Completando..." : "Completar"}
            </button>
            {isEditing ? (
              <button
                type="button"
                role="menuitem"
                className={styles.rowActionsItem}
                onClick={onCancelEdit}
              >
                Cancelar edición
              </button>
            ) : null}
            <button
              type="button"
              role="menuitem"
              className={`${styles.rowActionsItem} ${styles.rowActionsItemDanger}`}
              onClick={() => onDelete(reminder.id)}
              disabled={deletePending}
            >
              {deletePending ? "Eliminando..." : "Eliminar"}
            </button>
          </div>
        ) : null}
      </div>

      <div className={styles.listRowMobileMeta}>
        <span>
          {recurrenceLabels[reminder.recurrence] ?? reminder.recurrence}
        </span>
        {reminder.suggestion_justification ? (
          <span>{reminder.suggestion_justification}</span>
        ) : null}
      </div>
    </div>
  );
}

function ReminderSkeletonRows() {
  return (
    <>
      <div className={styles.skeletonRow} aria-hidden="true">
        <div className={styles.skeletonCircle} />
        <span className={styles.skeletonLine} style={{ width: "60%" }} />
      </div>
      <div className={styles.skeletonRow} aria-hidden="true">
        <div className={styles.skeletonCircle} />
        <span className={styles.skeletonLine} style={{ width: "45%" }} />
      </div>
    </>
  );
}

function validateForm(form: FormState): FormErrors {
  const nextErrors: FormErrors = {};
  if (!form.garden_plant_id)
    nextErrors.garden_plant_id = "Selecciona una planta.";
  if (!form.taskType) nextErrors.taskType = "Selecciona un tipo de tarea.";
  if (!form.date) nextErrors.date = "Indica una fecha.";
  if (!form.time) nextErrors.time = "Indica una hora.";
  if (!Object.keys(recurrenceLabels).includes(form.recurrence))
    nextErrors.recurrence = "Selecciona una recurrencia válida.";
  if (
    form.date &&
    form.time &&
    new Date(`${form.date}T${form.time}`) <= new Date()
  ) {
    nextErrors.date = "La fecha y hora deben ser futuras.";
  }
  return nextErrors;
}

export function normalizeReminderAction(action: string): TaskType {
  const lower = action.toLowerCase();
  if (/riego|agua|regar/.test(lower)) return "Riego";
  if (/fertiliz|abono|nutrien/.test(lower)) return "Fertilizante";
  if (/podar|cortar/.test(lower)) return "Poda";
  if (/trasplante|maceta/.test(lower)) return "Trasplante";
  if (/limpiez|limpia|polvo/.test(lower)) return "Limpieza";
  return "Revisión general";
}

function plantLabel(plant: GardenPlant) {
  return (
    plant.nickname ??
    plant.profile.selected_alias ??
    plant.profile.common_name ??
    plant.profile.scientific_name
  );
}

function recordSuggestionMetric(outcome: "accepted" | "edited" | "rejected") {
  apiClient.recordSuggestionMetric({ outcome }).catch(() => undefined);
}

type SuggestionOutcomeCardProps = {
  outcome: ReminderSuggestionOutcome;
  onAccept: (suggestion: ReminderSuggestionResult) => void;
  onEdit: (suggestion: ReminderSuggestionResult) => void;
  onDismiss: () => void;
  pending: boolean;
};

const suggestionRecurrenceLabels: Record<string, string> = {
  none: "Personalizado",
  daily: "Diario",
  weekly: "Semanal",
  monthly: "Mensual",
};

function formatSuggestionWhen(
  suggestion: ReminderSuggestionResult,
  timezone?: string | null,
) {
  const date = new Date(
    `${suggestion.date}T${suggestion.time}`,
  );
  if (Number.isNaN(date.getTime())) {
    return `${suggestion.date} ${suggestion.time}`;
  }
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: timezone || undefined,
  }).format(date);
}

function suggestionEvidenceSummary(
  evidence: ReminderSuggestionResult["evidence"],
): string {
  const parts = [evidence.taxonomy, evidence.location, evidence.light_context].filter(
    (value): value is string => Boolean(value),
  );
  if (evidence.active_reminders > 0) {
    parts.push(
      `${evidence.active_reminders} recordatorio${evidence.active_reminders === 1 ? "" : "s"} activo${evidence.active_reminders === 1 ? "" : "s"}`,
    );
  }
  return parts.length ? parts.join(" · ") : "datos del perfil de la planta";
}

function SuggestionOutcomeCard({
  outcome,
  onAccept,
  onEdit,
  onDismiss,
  pending,
}: SuggestionOutcomeCardProps) {
  if (outcome.kind === "clarification") {
    const fields = outcome.missing_fields.length
      ? outcome.missing_fields.join(", ")
      : "fecha, hora, zona horaria o recurrencia";
    return (
      <>
        <p className={styles.suggestionBody}>
          Para generar una sugerencia concreta necesitamos que completes:{" "}
          {fields}.
        </p>
        <div className={styles.suggestionActions}>
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={onDismiss}
          >
            Cerrar
          </Button>
        </div>
      </>
    );
  }

  if (outcome.kind === "duplicate") {
    return (
      <>
        <p className={styles.suggestionBody}>
          Ya existe un recordatorio equivalente para esta planta y horario.
        </p>
        <div className={styles.suggestionActions}>
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={onDismiss}
          >
            Cerrar
          </Button>
        </div>
      </>
    );
  }

  return (
    <ul
      className={styles.suggestionList}
      aria-label="Sugerencias generadas"
      style={{ padding: "0" }}
    >
      <li className={styles.suggestionItem}>
        <h3 className={styles.suggestionItemTitle}>{outcome.action}</h3>
        <p className={styles.suggestionItemMeta}>
          {outcome.plant_name} &middot;{" "}
          {formatSuggestionWhen(outcome, outcome.timezone)} &middot;{" "}
          {suggestionRecurrenceLabels[outcome.recurrence] ?? outcome.recurrence}
        </p>
        <p className={styles.suggestionItemCopy}>{outcome.justification}</p>
        <p className={styles.suggestionEvidenceLine}>
          Confianza: {Math.round(outcome.confidence * 100)}% &middot;{" "}
          {suggestionEvidenceSummary(outcome.evidence)}
        </p>
        {outcome.limitations?.length ? (
          <p className={styles.suggestionLimitations}>
            Limitaciones: {outcome.limitations.join(" · ")}
          </p>
        ) : null}
        <div className={styles.suggestionActions}>
          <Button
            type="button"
            variant="primary"
            size="md"
            onClick={() => onAccept(outcome)}
            disabled={pending}
          >
            Aceptar sugerencia
          </Button>
          {outcome.kind === "suggestion" ? (
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => onEdit(outcome)}
              disabled={pending}
            >
              Editar antes de guardar
            </Button>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="md"
            onClick={onDismiss}
            disabled={pending}
          >
            Descartar
          </Button>
        </div>
      </li>
    </ul>
  );
}
