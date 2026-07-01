"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import Link from "next/link";
import {
  BellIcon,
  CameraIcon,
  LeafIcon,
  PlantIcon,
  type IconProps,
} from "@phosphor-icons/react";
import { apiClient } from "@/lib/api/client";
import { resolveImageUrl } from "@/lib/images";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./HomeDashboard.module.scss";
import { AppLink, ImageCard } from "../ui";
import Image from "next/image";

type RecentGardenPlant = NonNullable<
  Awaited<ReturnType<typeof apiClient.getHomeSummary>>["recent_garden_plants"]
>[number];

const accessIcons: Record<string, React.ComponentType<IconProps>> = {
  garden: PlantIcon,
  identify: CameraIcon,
  reminders: BellIcon,
};

const quickAccessContent: Record<
  string,
  {
    label: string;
    description: string;
    illustration: "garden" | "identify" | "reminders";
  }
> = {
  garden: {
    label: "Mi Jardín",
    description: "Gestiona tus plantas actuales.",
    illustration: "garden",
  },
  identify: {
    label: "Identificar Planta",
    description: "Usa la cámara para descubrir especies.",
    illustration: "identify",
  },
  reminders: {
    label: "Recordatorios",
    description: "Gestiona las tareas de riego.",
    illustration: "reminders",
  },
};

function formatGardenCount(count: number): string {
  if (count === 0) return "0 Plantas";
  if (count === 1) return "1 Planta";
  return `${count} Plantas`;
}

function displayName(plant: RecentGardenPlant): string {
  return plant.nickname ?? plant.common_name ?? plant.scientific_name;
}

function formatPlantDetail(plant: RecentGardenPlant): string {
  const parts: string[] = [];
  if (plant.location) parts.push(plant.location);
  if (plant.active_reminders > 0) {
    parts.push(
      plant.active_reminders === 1
        ? "1 recordatorio"
        : `${plant.active_reminders} recordatorios`,
    );
  }
  if (parts.length === 0) return "Sin recordatorios";
  return parts.join(" • ");
}

export function HomeDashboard() {
  const session = useSession();
  const summary = useQuery({
    queryKey: ["home-summary"],
    enabled: session.status === "authenticated",
    queryFn: () => apiClient.getHomeSummary(),
    retry: 1,
  });

  if (session.status === "loading" || summary.isLoading) {
    return <div className={styles.skeleton} aria-label="Cargando Home" />;
  }

  if (summary.isError || !summary.data) {
    return (
      <section className={styles.error} aria-labelledby="home-error-title">
        <h1 id="home-error-title">No pudimos actualizar tu Home</h1>
        <p>
          La base de la app sigue disponible. Intentá cargar los datos
          nuevamente.
        </p>
        <button type="button" onClick={() => summary.refetch()}>
          Reintentar
        </button>
      </section>
    );
  }

  const accessByKey = new Map(
    summary.data.access.map((item) => [item.key, item]),
  );

  const quickAccessItems = ["garden", "identify", "reminders"]
    .map((key) => accessByKey.get(key))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  const gardenCount = summary.data.garden_count;
  const recentPlants = summary.data.recent_garden_plants ?? [];

  return (
    <>
      <header className={styles.welcome}>
        <h1 className={styles.title}>
          Hola, <span>{summary.data.user.name || "Usuario"}</span>
        </h1>
        <p className={styles.lead}>Bienvenido de vuelta a tu espacio verde.</p>
      </header>

      <section className={styles.mosaic} aria-label="Acceso rápido">
        <h2 className={styles.sectionHeading}>Acceso rápido</h2>
        <div className={styles.mosaicGrid}>
          {quickAccessItems.map((item) => {
            const content = quickAccessContent[item.key];
            if (!content) return null;

            const Icon = accessIcons[item.key] ?? LeafIcon;
            const isGarden = item.key === "garden";

            return (
              <Link
                className={`${styles.mosaicCard} ${
                  isGarden ? styles.mosaicCardPrimary : ""
                }`}
                data-illustration={content.illustration}
                href={item.href}
                key={item.key}
              >
                <div className={styles.mosaicTop}>
                  {isGarden ? (
                    <span className={styles.plantBadge}>
                      {formatGardenCount(gardenCount)}
                    </span>
                  ) : (
                    <span className={styles.mosaicIcon}>
                      <Icon
                        aria-hidden="true"
                        size="1.25rem"
                        className={iconStyles.tonePrimary}
                      />
                    </span>
                  )}
                </div>

                <div className={styles.mosaicBody}>
                  <strong className={styles.mosaicTitle}>
                    {content.label}
                  </strong>
                  <p className={styles.mosaicCopy}>{content.description}</p>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {recentPlants.length > 0 ? (
        <section className={styles.featured} aria-labelledby="tu-jardin-title">
          <div className={styles.featuredHeader}>
            <h2 id="tu-jardin-title" className={styles.sectionHeading}>
              Tu jardín
            </h2>
            <AppLink href="/garden">Ver todas</AppLink>
          </div>

          <div className={styles.featuredGrid}>
            {recentPlants.map((plant) => {
              const imageSrc = resolveImageUrl(plant.image_path);
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
                        <Image
                          src={imageSrc}
                          alt={displayName(plant)}
                          layout="fill"
                        />
                      ) : undefined
                    }
                    imageAlt={displayName(plant)}
                    fallback={
                      <PlantIcon
                        size="3rem"
                        weight="regular"
                        className={iconStyles.tonePrimary}
                      />
                    }
                    title={displayName(plant)}
                    description={formatPlantDetail(plant)}
                  />
                </AppLink>
              );
            })}
          </div>
        </section>
      ) : null}
    </>
  );
}
