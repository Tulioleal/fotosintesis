"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftIcon,
  BellIcon,
  CameraIcon,
  ChatTextIcon,
  MapPinIcon,
  PlantIcon,
  PlusCircleIcon,
  SunIcon,
  TrashIcon,
} from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  ApiClientError,
  apiClient,
  type LightClassification,
  type LightMeasurement,
} from "@/lib/api/client";
import { buildAssistantHref } from "@/lib/assistant";
import { resolveImageUrl } from "@/lib/images";
import { AppLink, Button, Card, Chip, Notice } from "@/components/ui";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./GardenDetail.module.scss";
import Image from "next/image";

const classificationLabel: Record<LightClassification, string> = {
  baja: "Baja",
  media: "Media",
  alta: "Alta",
  directa: "Directa",
};

const classificationToWidth: Record<LightClassification, string> = {
  baja: "25%",
  media: "50%",
  alta: "75%",
  directa: "100%",
};

const measurementDateFormatter = new Intl.DateTimeFormat("es", {
  day: "2-digit",
  month: "short",
});

function formatMeasurementDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return measurementDateFormatter.format(date).replace(".", "");
}

export function GardenDetail({ gardenId }: Readonly<{ gardenId: string }>) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [requiresReminderConfirm, setRequiresReminderConfirm] = useState(false);
  const garden = useQuery({
    queryKey: ["garden", "detail", gardenId],
    queryFn: () => apiClient.getGardenPlant(gardenId),
  });
  const plant = garden.data;

  const deletePlant = useMutation({
    mutationFn: (confirmReminders: boolean) =>
      apiClient.deleteGardenPlant(gardenId, confirmReminders),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["garden", "list"] }),
        queryClient.invalidateQueries({
          queryKey: ["garden", "detail", gardenId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["light-measurements", gardenId],
        }),
      ]);
      router.push("/garden");
    },
    onError: (err: Error) => {
      if (err instanceof ApiClientError && err.status === 409) {
        setRequiresReminderConfirm(true);
        setError(err.message);
        return;
      }
      setError(err.message || "No pudimos eliminar la planta.");
    },
  });

  const lightMeasurements = useQuery({
    queryKey: ["light-measurements", gardenId],
    queryFn: () => apiClient.listLightMeasurements(gardenId, 5),
    enabled: !!gardenId,
  });

  async function remove(confirmReminders = false) {
    setError(null);
    deletePlant.mutate(confirmReminders);
  }

  if (garden.isError && !plant) {
    return (
      <Notice tone="error" role="alert">
        {garden.error.message || "No pudimos cargar la planta."}
      </Notice>
    );
  }
  if (garden.isLoading || !plant) {
    return (
      <Notice tone="info" role="status">
        Cargando detalle...
      </Notice>
    );
  }

  const binomialName = profileBinomialName(plant.profile);
  const displayName =
    plant.profile.selected_alias ??
    plant.profile.common_name ??
    plant.profile.scientific_name;
  const nickname = plant.nickname ? `"${plant.nickname}"` : null;
  const imageSrc = resolveImageUrl(plant.image_path);
  const location = plant.location ?? "Sin ubicacion";
  const notes = plant.notes ?? "Todavia no agregaste notas personalizadas.";
  const reminderLabel =
    plant.active_reminders > 0
      ? `${plant.active_reminders} recordatorio${plant.active_reminders === 1 ? "" : "s"} activo${plant.active_reminders === 1 ? "" : "s"}`
      : "Sin recordatorios";
  const assistantHref = buildAssistantHref({
    plant: plant.nickname ?? displayName,
    binomial: binomialName,
    scientific: plant.profile.scientific_name,
  });
  const lightMeterHref = `/light-meter?plant=${encodeURIComponent(plant.profile.scientific_name)}`;
  const reminderHref = `/reminders?plant=${encodeURIComponent(plant.profile.scientific_name)}`;
  const chatSubject = plant.nickname ?? displayName;
  const readings: LightMeasurement[] = lightMeasurements.data ?? [];

  return (
    <section className={styles.detail} aria-label={`Detalle de ${displayName}`}>
      <AppLink
        href="/garden"
        variant="back"
        leadingIcon={
          <ArrowLeftIcon aria-hidden="true" size="1rem" weight="regular" />
        }
      >
        Volver a Mi Jardin
      </AppLink>

      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>{displayName}</h1>
          {nickname ? <p className={styles.nickname}>{nickname}</p> : null}
        </div>

        <div className={styles.chips} aria-label="Resumen de cuidados">
          <Chip
            tone="neutral"
            icon={
              <BellIcon
                aria-hidden="true"
                size="1rem"
                className={iconStyles.toneOnSurfaceVariant}
              />
            }
          >
            {reminderLabel}
          </Chip>
          <Chip
            tone="primary"
            icon={
              <SunIcon
                aria-hidden="true"
                size="1rem"
                className={iconStyles.toneOnPrimary}
              />
            }
          >
            Luz Indirecta
          </Chip>
        </div>
      </header>

      <div className={styles.mainGrid}>
        <div className={styles.imageFrame}>
          {imageSrc ? (
            <Image src={imageSrc} alt={displayName} layout="fill" />
          ) : (
            <div className={styles.imageFallback} aria-hidden="true">
              <PlantIcon size="3rem" weight="regular" />
            </div>
          )}
        </div>

        <aside className={styles.sideColumn}>
          <Card variant="tonal" padding="md">
            <div className={styles.cardHeading}>
              <SunIcon
                aria-hidden="true"
                size="1.25rem"
                className={iconStyles.tonePrimary}
              />
              <h2>Medicion de Luz</h2>
            </div>
            <p className={styles.cardCopy}>
              Usa la camara para verificar si {plant.nickname ?? displayName}{" "}
              recibe luz adecuada.
            </p>
            <AppLink
              href={lightMeterHref}
              variant="button"
              buttonVariant="primary"
              leadingIcon={
                <CameraIcon
                  aria-hidden="true"
                  size="1rem"
                  weight="regular"
                  className={iconStyles.toneOnPrimary}
                />
              }
            >
              Iniciar Medicion
            </AppLink>
            {readings.length > 0 ? (
              <div className={styles.readings} aria-label="Ultimas lecturas">
                <span className={styles.readingsTitle}>Ultimas lecturas</span>
                <ul className={styles.readingsList}>
                  {readings.map((reading) => (
                    <li key={reading.id} className={styles.readingItem}>
                      <div className={styles.readingMeta}>
                        <span className={styles.readingDate}>
                          {formatMeasurementDate(reading.measured_at)}
                        </span>
                        <span className={styles.readingLabel}>
                          {classificationLabel[reading.classification]}
                        </span>
                      </div>
                      <div
                        className={styles.readingBar}
                        role="presentation"
                        style={
                          {
                            "--reading-width":
                              classificationToWidth[reading.classification],
                          } as React.CSSProperties
                        }
                      >
                        <span
                          style={{
                            width:
                              classificationToWidth[reading.classification],
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </Card>

          <Card variant="tonal" padding="md">
            <span className={styles.kicker}>Acciones</span>
            <AppLink
              href={assistantHref}
              variant="button"
              buttonVariant="outline"
              leadingIcon={
                <ChatTextIcon
                  aria-hidden="true"
                  size="1rem"
                  weight="regular"
                  className={iconStyles.tonePrimary}
                />
              }
            >
              Iniciar Chat sobre {chatSubject}
            </AppLink>
            <AppLink
              href={reminderHref}
              variant="button"
              buttonVariant="outline"
              leadingIcon={
                <PlusCircleIcon
                  aria-hidden="true"
                  size="1rem"
                  weight="regular"
                  className={iconStyles.tonePrimary}
                />
              }
            >
              Crear Recordatorio
            </AppLink>
          </Card>
        </aside>
      </div>

      <div className={styles.detailGrid}>
        <Card variant="tonal" padding="md" className={styles.infoCard}>
          <div className={styles.infoColumns}>
            <div>
              <span className={styles.kicker}>Nombre Cientifico</span>
              <p className={styles.scientific}>
                <em>{plant.profile.scientific_name}</em>
              </p>
            </div>
            <div>
              <span className={styles.kicker}>Ubicacion</span>
              <p className={styles.location}>
                <MapPinIcon
                  aria-hidden="true"
                  size="1rem"
                  className={iconStyles.tonePrimary}
                />
                {location}
              </p>
            </div>
          </div>

          <div className={styles.notes}>
            <span className={styles.kicker}>Notas de Usuario</span>
            <p>{notes}</p>
          </div>
        </Card>

        <div className={styles.dangerColumn}>
          {error ? (
            <Notice tone="error" role="alert">
              {error}
            </Notice>
          ) : null}
          {requiresReminderConfirm ? (
            <Button
              variant="destructive"
              onClick={() => remove(true)}
              fullWidth
            >
              {deletePlant.isPending
                ? "Eliminando..."
                : "Confirmar eliminacion y afectar recordatorios"}
            </Button>
          ) : (
            <Button
              variant="destructive"
              onClick={() => remove(false)}
              fullWidth
              leadingIcon={
                <TrashIcon aria-hidden="true" size="1rem" weight="regular" />
              }
            >
              {deletePlant.isPending ? "Eliminando..." : "Eliminar Planta"}
            </Button>
          )}
        </div>
      </div>
    </section>
  );
}

function profileBinomialName(
  profile: { scientific_name: string } & { binomial_name?: string | null },
) {
  return profile.binomial_name ?? null;
}
