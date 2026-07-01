"use client";

import { useQuery } from "@tanstack/react-query";
import { PlantIcon, PlusIcon } from "@phosphor-icons/react";
import { apiClient, type GardenPlant } from "@/lib/api/client";
import { resolveImageUrl } from "@/lib/images";
import { AppLink, Card, ImageCard, Notice, PageHeader } from "@/components/ui";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./GardenList.module.scss";
import Image from "next/image";

function displayPlantName(plant: GardenPlant): string {
  return (
    plant.nickname ??
    plant.profile?.selected_alias ??
    plant.profile?.common_name ??
    plant.profile?.scientific_name ??
    "Planta"
  );
}

function formatCareStatus(plant: GardenPlant): string {
  if (plant.active_reminders && plant.active_reminders > 0) {
    return `${plant.active_reminders} recordatorio${plant.active_reminders === 1 ? "" : "s"} activo${plant.active_reminders === 1 ? "" : "s"}`;
  }
  return "Último riego: Sin registros";
}

export function GardenList() {
  const garden = useQuery({
    queryKey: ["garden", "list"],
    queryFn: () => apiClient.listGardenPlants(""),
  });
  const plants = garden.isError ? [] : (garden.data ?? []);

  return (
    <section className={styles.garden}>
      <PageHeader
        heading="Mi Jardín"
        description="Monitorea y gestiona el cuidado de tus plantas."
        actions={
          <AppLink
            href="/identify"
            variant="button"
            buttonVariant="primary"
            leadingIcon={
              <PlusIcon
                aria-hidden="true"
                size="1rem"
                weight="bold"
                className={iconStyles.toneOnPrimary}
              />
            }
          >
            Registrar Planta
          </AppLink>
        }
      />

      {garden.isError ? (
        <Notice tone="error" role="alert">
          {garden.error.message || "No pudimos cargar Mi Jardín."}
        </Notice>
      ) : null}
      {garden.isLoading ? (
        <Notice tone="info" role="status">
          Cargando plantas...
        </Notice>
      ) : null}
      {!garden.isLoading && !garden.isError && !plants.length ? (
        <Card variant="tonal" padding="md" className={styles.empty}>
          <h2 className={styles.emptyTitle}>Tu jardín está vacío</h2>
          <p>
            Confirma una candidata validada desde Identificar y guárdala desde
            su perfil.
          </p>
          <AppLink href="/identify" variant="button" buttonVariant="primary">
            Identificar planta
          </AppLink>
        </Card>
      ) : null}

      <div className={styles.grid}>
        {plants.map((plant) => {
          const imageSrc = resolveImageUrl(plant.image_path);
          const name = displayPlantName(plant);
          const location = plant.location ?? "Sin ubicación";
          const care = "Luz indirecta";

          return (
            <AppLink
              key={plant.id}
              href={`/garden/${plant.id}`}
              variant="plain"
              className={styles.cardLink}
            >
              <ImageCard
                variant="result"
                image={
                  imageSrc ? (
                    <Image src={imageSrc} alt={name} layout="fill" />
                  ) : undefined
                }
                imageAlt={name}
                fallback={
                  <PlantIcon
                    size="3rem"
                    weight="regular"
                    className={iconStyles.tonePrimary}
                  />
                }
                title={name}
                description={`${location} • ${care}`}
                meta={
                  <span className={styles.cardFooter}>
                    {formatCareStatus(plant)}
                  </span>
                }
              />
            </AppLink>
          );
        })}
      </div>
    </section>
  );
}
