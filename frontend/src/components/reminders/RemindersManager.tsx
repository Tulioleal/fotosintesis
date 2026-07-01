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
} from "@/lib/api/client";
import { resolveImageUrl } from "@/lib/images";
import {
  BellIcon,
  DotsThreeVerticalIcon,
  PlantIcon,
  SparkleIcon,
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

function formatReminderDate(iso: string): { primary: string; meta?: string } {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return { primary: iso };
  }
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
  const time = date.toLocaleTimeString("es-AR", {
    hour: "2-digit",
    minute: "2-digit",
  });
  if (sameDay(date, tomorrow)) {
    return { primary: `Mañana, ${time}` };
  }
  const dayMonth = date
    .toLocaleDateString("es-AR", { day: "2-digit", month: "short" })
    .replace(".", "");
  return { primary: `${dayMonth}, ${time}` };
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
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
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const garden = useQuery({
    queryKey: ["garden", "list", ""],
    queryFn: () => apiClient.listGardenPlants(),
  });
  const reminders = useQuery({
    queryKey: ["reminders", "list"],
    queryFn: () => apiClient.listReminders(),
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
          ? `Completado. Próximo recordatorio: ${formatDateTime(reminder.next_occurrence_at)}.`
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
      date: reminder.due_at.slice(0, 10),
      time: reminder.due_at.slice(11, 16),
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

  const suggestions = useMemo(
    () => buildSuggestions(plants, plantHint),
    [plants, plantHint],
  );
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
            aria-labelledby="reminders-form-heading"
          >
            <h2 id="reminders-form-heading" className={styles.formHeading}>
              Nuevo Recordatorio
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
            variant="callout"
            padding="md"
            className={styles.suggestionCard}
            heading="Sugerencias con IA"
            description="Optimiza el cuidado de tu jardín con inteligencia artificial."
          >
            {suggestionsVisible ? (
              suggestions.length ? (
                <ul
                  className={styles.suggestionList}
                  aria-label="Sugerencias generadas"
                  style={{
                    padding: "0",
                  }}
                >
                  {suggestions.map((suggestion) => (
                    <li
                      key={`${suggestion.garden_plant_id}-${suggestion.action}`}
                      className={styles.suggestionItem}
                    >
                      <h3 className={styles.suggestionItemTitle}>
                        {suggestion.action}
                      </h3>
                      <p className={styles.suggestionItemCopy}>
                        {suggestion.justification}
                      </p>
                      <div className={styles.suggestionActions}>
                        <Button
                          type="button"
                          variant="secondary"
                          size="md"
                          onClick={() => acceptSuggestion(suggestion)}
                          disabled={createReminder.isPending}
                        >
                          Aceptar sugerencia
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className={styles.suggestionBody}>
                  Añade plantas a tu jardín para empezar a generar sugerencias.
                </p>
              )
            ) : (
              <>
                <Button
                  type="button"
                  variant="secondary"
                  size="md"
                  fullWidth
                  className={styles.suggestionTrigger}
                  onClick={() => setSuggestionsVisible(true)}
                  disabled={!plants.length}
                >
                  Generar con IA &nbsp;
                  <SparkleIcon aria-hidden="true" size="1rem" />
                </Button>
              </>
            )}
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
  const dateInfo = formatReminderDate(reminder.due_at);

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
            Próxima: {formatReminderDate(reminder.next_occurrence_at).primary}
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

type SuggestedReminder = ReminderCreate & { justification: string };

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

function buildSuggestions(
  plants: GardenPlant[],
  plantHint: string,
): SuggestedReminder[] {
  const selectedPlants = plantHint
    ? plants.filter(
        (plant) => plant.profile.scientific_name.toLowerCase() === plantHint,
      )
    : plants.slice(0, 2);
  const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
  const date = tomorrow.toISOString().slice(0, 10);
  return selectedPlants.map((plant) => ({
    garden_plant_id: plant.id,
    action: suggestActionFor(plant),
    date,
    time: "09:00",
    recurrence: "weekly",
    suggestion_justification:
      "Sugerido por el perfil de la planta y el contexto de Mi Jardín.",
    justification: `Basado en el perfil de ${plantLabel(plant)} y su contexto guardado. Requiere confirmación antes de crearse.`,
  }));
}

function suggestActionFor(plant: GardenPlant): TaskType {
  const lines = (plant.profile.sections?.care ?? []).map((line) =>
    line.toLowerCase(),
  );
  if (lines.some((line) => /riego|agua/.test(line))) return "Riego";
  if (lines.some((line) => /fertiliz|abono|nutrien/.test(line)))
    return "Fertilizante";
  if (lines.some((line) => /podar|cortar/.test(line))) return "Poda";
  if (lines.some((line) => /trasplante|maceta/.test(line))) return "Trasplante";
  if (lines.some((line) => /limpiez|limpia|polvo/.test(line)))
    return "Limpieza";
  return "Revisión general";
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
