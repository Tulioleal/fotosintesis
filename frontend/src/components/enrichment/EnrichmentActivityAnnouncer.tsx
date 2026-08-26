"use client";

import { XIcon } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";
import { AppLink, Button, Notice } from "@/components/ui";
import type { EnrichmentActivityItem } from "@/lib/api/client";
import {
  activityDetailCopy,
  activityDisplayName,
  activityProfileHref,
  compareActivityDescending,
  loadAnnouncedOutcomes,
  outcomeVersion,
  rememberAnnouncedOutcome,
  terminalStatuses,
} from "@/lib/enrichment-activity";
import { useEnrichmentActivity } from "./EnrichmentActivityProvider";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./EnrichmentActivityAnnouncer.module.scss";

export function EnrichmentActivityAnnouncer() {
  const { userId } = useEnrichmentActivity();

  // Remounting per identity resets queue/dedup state synchronously and
  // reloads announced versions from the new user's storage namespace; a
  // prior owner's announcement can never survive an identity change.
  return <AnnouncerForUser key={userId} userId={userId} />;
}

function AnnouncerForUser({ userId }: Readonly<{ userId: string }>) {
  const { query: activity } = useEnrichmentActivity();
  const [queue, setQueue] = useState<EnrichmentActivityItem[]>([]);
  const announcement = queue[0] ?? null;
  const queuedVersions = useRef(new Set<string>());
  const announcedVersions = useRef(loadAnnouncedOutcomes(userId));

  // Enqueue unseen terminal outcomes, newest first, without duplicates.
  // The item currently being displayed stays fixed; waiting items merge
  // and re-sort so a newer arrival overtakes older queued ones.
  useEffect(() => {
    const unseen = (activity.data?.items ?? [])
      .filter((item) => terminalStatuses.has(item.status))
      .sort(compareActivityDescending)
      .filter((item) => {
        const version = outcomeVersion(item);

        return (
          version !== null &&
          !announcedVersions.current.has(version) &&
          !queuedVersions.current.has(version)
        );
      });

    if (!unseen.length) return;

    for (const item of unseen) {
      const version = outcomeVersion(item);
      if (version) queuedVersions.current.add(version);
    }

    setQueue((current) => {
      if (current.length === 0) {
        return [...unseen].sort(compareActivityDescending);
      }

      const [displayed, ...waiting] = current;

      return [
        displayed,
        ...[...waiting, ...unseen].sort(compareActivityDescending),
      ];
    });
  }, [activity.data]);

  // Persist only versions actually displayed to the user.
  useEffect(() => {
    if (!announcement) return;

    const version = outcomeVersion(announcement);
    if (!version || announcedVersions.current.has(version)) return;

    announcedVersions.current.add(version);
    rememberAnnouncedOutcome(userId, version);
  }, [announcement, userId]);

  function dismissAnnouncement() {
    setQueue((current) => {
      const [dismissed, ...remaining] = current;
      const version = dismissed ? outcomeVersion(dismissed) : null;

      if (version) queuedVersions.current.delete(version);

      return remaining;
    });
  }

  if (!announcement) {
    return <div data-testid="announcer-settled" hidden />;
  }

  const href = activityProfileHref(announcement);
  const tone =
    announcement.status === "failed"
      ? "error"
      : announcement.status === "partial"
        ? "warning"
        : "success";

  return (
    <div
      className={styles.wrap}
      data-terminal-announcement={announcement.status}
      data-testid="announcer-settled"
    >
      <Notice tone={tone} heading={activityDetailCopy(announcement)}>
        <AppLink href={href} variant="subtle">
          Ver perfil de {activityDisplayName(announcement)}
        </AppLink>
      </Notice>
      <Button
        variant="ghost"
        size="sm"
        onClick={dismissAnnouncement}
        leadingIcon={
          <XIcon aria-hidden="true" size="1rem" className={iconStyles.tonePrimary} />
        }
      >
        Cerrar
      </Button>
    </div>
  );
}
