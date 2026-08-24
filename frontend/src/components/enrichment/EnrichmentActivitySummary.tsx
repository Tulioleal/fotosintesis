"use client";

import { GearSixIcon, CheckCircleIcon, WarningCircleIcon } from "@phosphor-icons/react";
import { AppLink, Button, Card, Notice } from "@/components/ui";
import type { EnrichmentActivityItem } from "@/lib/api/client";
import {
  MAX_VISIBLE_ACTIVE_ACTIVITY,
  MAX_VISIBLE_TERMINAL_ACTIVITY,
  activeStatuses,
  activityDetailCopy,
  activityDisplayName,
  activityItemsRelatedTo,
  activityPhaseLabel,
  activityProfileHref,
  terminalStatuses,
} from "@/lib/enrichment-activity";
import { useEnrichmentActivity } from "./EnrichmentActivityProvider";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./EnrichmentActivitySummary.module.scss";

type ActivityFilter = {
  candidateIds?: string[];
  speciesKeys?: string[];
  scientificNames?: string[];
};

export function EnrichmentActivitySummary({
  relatedTo,
  variant = "standalone",
}: Readonly<{
  relatedTo?: ActivityFilter;
  /** Inline renders inside pages that own their own live regions and
   * error notices, so it stays silent while loading or failing. */
  variant?: "standalone" | "inline";
}>) {
  const { query: activity } = useEnrichmentActivity();
  const quiet = variant === "inline";

  if (activity.isLoading && !activity.data) {
    if (quiet) return null;
    return (
      <Notice tone="info" role="status">
        Cargando trabajo en segundo plano...
      </Notice>
    );
  }

  if (activity.isError && !activity.data) {
    if (quiet) return null;
    return (
      <Notice tone="warning" role="status">
        No pudimos actualizar el estado del trabajo en segundo plano.{" "}
        <Button variant="ghost" size="sm" onClick={() => activity.refetch()}>
          Reintentar
        </Button>
      </Notice>
    );
  }

  const items = activityItemsRelatedTo(activity.data?.items ?? [], relatedTo);
  const activeItems = items.filter((item) => activeStatuses.has(item.status));
  const terminalItems = items.filter((item) => terminalStatuses.has(item.status));
  // Render a bounded projection: aggregation still walks every page, but the
  // DOM never grows unbounded. The overflow count covers both categories.
  const visibleActiveItems = activeItems.slice(
    0,
    MAX_VISIBLE_ACTIVE_ACTIVITY,
  );
  const visibleTerminalItems = terminalItems.slice(
    0,
    MAX_VISIBLE_TERMINAL_ACTIVITY,
  );
  const hiddenCount =
    activeItems.length - visibleActiveItems.length +
    terminalItems.length - visibleTerminalItems.length;
  const hasTerminalActivity = terminalItems.length > 0;
  const hasActiveWork = activeItems.length > 0;

  if (!hasActiveWork && !hasTerminalActivity) return null;

  return (
    <section
      className={styles.summary}
      aria-label="Estado del trabajo en segundo plano"
    >
      {activity.isError && !quiet ? (
        <Notice tone="warning" role="status">
          Conservamos el estado anterior; no pudimos refrescar el trabajo en
          segundo plano.{" "}
          <Button variant="ghost" size="sm" onClick={() => activity.refetch()}>
            Reintentar
          </Button>
        </Notice>
      ) : null}

      {hasActiveWork ? (
        <Card variant="tonal" padding="md">
          <div className={styles.heading}>
            <GearSixIcon
              aria-hidden="true"
              size="1.1rem"
              className={iconStyles.tonePrimary}
            />
            <h2 className={styles.title}>Trabajo en segundo plano</h2>
          </div>
          <p className={styles.copy}>
            Estamos preparando y actualizando información de tus plantas. Esto
            continúa en segundo plano; podés seguir usando la app.
          </p>
          <ul className={styles.list}>
            {visibleActiveItems.map((item) => (
              <ActivityItemRow key={item.id} item={item} />
            ))}
          </ul>
        </Card>
      ) : null}

      {hasTerminalActivity ? (
        <Card variant="tonal" padding="md">
          <div className={styles.heading}>
            <CheckCircleIcon
              aria-hidden="true"
              size="1.1rem"
              className={iconStyles.tonePrimary}
            />
            <h2 className={styles.title}>Actividad reciente</h2>
          </div>
          <ul className={styles.list}>
            {visibleTerminalItems.map((item) => (
              <ActivityItemRow key={item.id} item={item} />
            ))}
          </ul>
        </Card>
      ) : null}

      {hiddenCount > 0 ? (
        <p className={styles.moreNote}>
          Hay {hiddenCount} actividad{hiddenCount === 1 ? "" : "es"}{" "}
          adicional{hiddenCount === 1 ? "" : "es"}.
        </p>
      ) : null}
    </section>
  );
}

function ActivityItemRow({ item }: Readonly<{ item: EnrichmentActivityItem }>) {
  const href = activityProfileHref(item);
  const icon =
    item.status === "failed" ? (
      <WarningCircleIcon aria-hidden="true" size="1rem" className={iconStyles.toneOnSurfaceVariant} />
    ) : item.status === "complete" ? (
      <CheckCircleIcon aria-hidden="true" size="1rem" className={iconStyles.tonePrimary} />
    ) : (
      <GearSixIcon aria-hidden="true" size="1rem" className={iconStyles.tonePrimary} />
    );

  return (
    <li className={styles.row}>
      <span className={styles.rowIcon} aria-hidden="true">
        {icon}
      </span>
      <span className={styles.rowBody}>
        <span className={styles.rowTitle}>{activityDisplayName(item)}</span>
        <span className={styles.rowCopy}>
          {activityPhaseLabel(item)} · {activityDetailCopy(item)}
        </span>
      </span>
      <AppLink
        href={href}
        variant="subtle"
        aria-label={`Ver perfil de ${activityDisplayName(item)}`}
      >
        Ver perfil
      </AppLink>
    </li>
  );
}