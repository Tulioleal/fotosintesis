import { useQuery } from "@tanstack/react-query";
import {
  apiClient,
  type EnrichmentActivityItem,
  type EnrichmentActivityResponse,
} from "@/lib/api/client";

export const ACTIVITY_QUERY_KEY = ["enrichment-activity"] as const;
export const ACTIVITY_POLL_INTERVAL_MS = 5_000;

/** Per-user query key so cached activity can never leak across accounts. */
export function activityQueryKey(userId: string) {
  return [...ACTIVITY_QUERY_KEY, userId] as const;
}

export const MAX_VISIBLE_ACTIVE_ACTIVITY = 5;
export const MAX_VISIBLE_TERMINAL_ACTIVITY = 5;
export const MAX_STORED_OUTCOME_VERSIONS = 200;

export const terminalStatuses = new Set(["complete", "partial", "failed"]);
export const activeStatuses = new Set(["pending", "processing"]);

function terminalOutcomeStorageKey(userId: string): string {
  return `fotosintesis:enrichment-terminal-outcomes:v2:${userId}`;
}

function reconciledRefreshStorageKey(userId: string): string {
  return `fotosintesis:reconciled-profile-refresh:v2:${userId}`;
}

// Live-instance claim set: claims are atomic within the tab even before
// storage round-trips complete. Keys are user-scoped claim payloads.
const liveClaims = new Set<string>();

/**
 * Upper bound of backend retention (ENRICHMENT_ACTIVITY_TERMINAL_RETENTION_HOURS
 * le=720). Prune only claims older than this so nothing still visible server-side
 * can be re-announced or re-reconciled.
 */
const RETENTION_PRUNE_MS = 720 * 60 * 60 * 1000;

/** Extract the trailing ISO timestamp from an "<id>:<status>:<updated_at>" version. */
function versionTimestamp(version: string): number | null {
  const match = /(\d{4}-\d{2}-\d{2}T.*)$/.exec(version);
  if (!match) return null;
  const parsed = Date.parse(match[1]);
  return Number.isNaN(parsed) ? null : parsed;
}

/** Reconciliation claims are JSON; try JSON first, else the raw version. */
function entryTimestamp(entry: string): number | null {
  try {
    const obj = JSON.parse(entry) as { version?: string };
    if (typeof obj.version === "string") return versionTimestamp(obj.version);
  } catch {
    // not JSON
  }
  return versionTimestamp(entry);
}

function pruneExpired(versions: string[]): string[] {
  const cutoff = Date.now() - RETENTION_PRUNE_MS;
  return versions.filter((version) => {
    const ts = entryTimestamp(version);
    return ts === null || ts >= cutoff; // unparseable entries are kept (safe)
  });
}

function loadStoredVersions(storageKey: string): Set<string> {
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw) return new Set();
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    const versions = pruneExpired(
      parsed.filter((entry): entry is string => typeof entry === "string"),
    );
    const bounded = versions.slice(-MAX_STORED_OUTCOME_VERSIONS);
    // Rewrite so oversized/stale payloads shrink immediately, not lazily.
    if (bounded.length !== parsed.length) {
      try {
        window.sessionStorage.setItem(storageKey, JSON.stringify(bounded));
      } catch {
        // Best-effort shrink: storage may be unavailable.
      }
    }
    return new Set(bounded);
  } catch {
    return new Set();
  }
}

function storeVersions(storageKey: string, versions: Set<string>): void {
  try {
    const bounded = pruneExpired([...versions]).slice(-MAX_STORED_OUTCOME_VERSIONS);
    window.sessionStorage.setItem(storageKey, JSON.stringify(bounded));
  } catch {
    // Storage may be unavailable (private mode, SSR); dedup still holds for
    // the live instance.
  }
}

/**
 * Atomically claim one refresh reconciliation for an exact profile query:
 * user + outcome version + candidate + scientific name + language. Remounts
 * and parallel consumers observe exactly one successful claim per payload;
 * a different candidate, language, or user claims independently.
 */
export function claimRefreshReconciliation(
  userId: string,
  version: string,
  profileQueryKey: readonly unknown[],
): boolean {
  const claim = JSON.stringify({ userId, version, profileQueryKey });
  if (liveClaims.has(claim)) return false;

  const persisted = loadStoredVersions(reconciledRefreshStorageKey(userId));
  if (persisted.has(claim)) {
    liveClaims.add(claim);
    return false;
  }

  liveClaims.add(claim);
  persisted.add(claim);
  storeVersions(reconciledRefreshStorageKey(userId), persisted);
  return true;
}

/** Test isolation only: clears the in-memory reconciliation claims. */
export function resetRefreshReconciliationClaimsForTests(): void {
  liveClaims.clear();
}

export function activityHasActiveWork(
  items: EnrichmentActivityItem[] | undefined,
): boolean {
  return (items ?? []).some((item) => activeStatuses.has(item.status));
}

export function activityRefetchInterval(query: {
  state: { data?: EnrichmentActivityResponse | undefined };
}): number | false {
  const items = query.state.data?.items;
  return activityHasActiveWork(items) ? ACTIVITY_POLL_INTERVAL_MS : false;
}

export function compareActivityDescending(
  a: EnrichmentActivityItem,
  b: EnrichmentActivityItem,
): number {
  const delta = Date.parse(b.updated_at) - Date.parse(a.updated_at);
  if (delta !== 0) return delta;
  return b.id.localeCompare(a.id);
}

/**
 * Walk every page of owner-scoped activity inside the single observer so
 * hidden active work on later pages can never stop polling. Duplicate job
 * ids across pages keep their newest version; a repeated or missing cursor
 * aborts instead of looping forever.
 */
export async function loadEnrichmentActivity(): Promise<EnrichmentActivityResponse> {
  let pagesFetched = 0;

  const collect = async (): Promise<EnrichmentActivityResponse> => {
    const items = new Map<string, EnrichmentActivityItem>();
    const seenCursors = new Set<string>();
    let cursor: string | undefined;

    while (true) {
      pagesFetched += 1;
      const page = await apiClient.getEnrichmentActivity({
        limit: 100,
        cursor,
      });

      for (const item of page.items ?? []) {
        const existing = items.get(item.id);
        if (!existing || compareActivityDescending(item, existing) < 0) {
          items.set(item.id, item);
        }
      }

      if (!page.has_more) break;

      if (!page.next_cursor || seenCursors.has(page.next_cursor)) {
        throw new Error("Invalid activity pagination sequence");
      }

      seenCursors.add(page.next_cursor);
      cursor = page.next_cursor;
    }

    return {
      items: [...items.values()].sort(compareActivityDescending),
      has_more: false,
      next_cursor: null,
    };
  };

  let result = await collect();

  if (pagesFetched > 1 && !activityHasActiveWork(result.items)) {
    // Keyset movement may have skipped a job that jumped ahead of the cursor
    // mid-traversal; one fresh pass guarantees the documented re-scan.
    result = await collect();
  }

  return result;
}

export function useEnrichmentActivityQuery(userId: string | undefined) {
  return useQuery({
    queryKey: activityQueryKey(userId ?? "anonymous"),
    queryFn: loadEnrichmentActivity,
    enabled: Boolean(userId),
    refetchInterval: activityRefetchInterval,
    refetchOnWindowFocus: false,
    staleTime: 15_000,
  });
}

function isTerminalStatus(status: string): boolean {
  return terminalStatuses.has(status);
}

export function outcomeVersion(
  item: EnrichmentActivityItem,
): string | null {
  if (!isTerminalStatus(item.status)) return null;
  return `${item.id}:${item.status}:${item.updated_at}`;
}

export function loadAnnouncedOutcomes(userId: string): Set<string> {
  return loadStoredVersions(terminalOutcomeStorageKey(userId));
}

export function rememberAnnouncedOutcome(
  userId: string,
  version: string,
): void {
  const next = loadAnnouncedOutcomes(userId);
  next.add(version);
  storeVersions(terminalOutcomeStorageKey(userId), next);
}

function binomialFromSpeciesKey(speciesKey: string | null | undefined): string | null {
  if (!speciesKey) return null;
  const marker = "binomial:";
  const index = speciesKey.indexOf(marker);
  if (index === -1) return null;
  const binomial = speciesKey.slice(index + marker.length);
  return binomial || null;
}

export function activityDisplayName(item: EnrichmentActivityItem): string {
  return (
    item.common_name ??
    item.scientific_name ??
    binomialFromSpeciesKey(item.species_key) ??
    "Planta confirmada"
  );
}

export function activityProfileHref(
  item: EnrichmentActivityItem,
): string {
  return `/profiles/${encodeURIComponent(
    item.scientific_name,
  )}?candidateId=${encodeURIComponent(item.candidate_id)}`;
}

const evidenceCopy = {
  pending: "Preparando la búsqueda de evidencia",
  processing: "Reuniendo evidencia en segundo plano",
  complete: "La evidencia está lista",
  partial: "Encontramos evidencia útil; faltan algunos temas",
  failed: "No pudimos ampliar la evidencia",
} as const;

const refreshCopy = {
  pending: "La actualización del perfil está en espera",
  processing: "Actualizando las secciones del perfil",
  complete: "El perfil se actualizó",
  partial: "El perfil se actualizó parcialmente",
  failed: "No pudimos actualizar el perfil",
} as const;

const backgroundExplanation =
  "Esto continúa en segundo plano; podés seguir usando la app.";

export function activityPhaseLabel(item: EnrichmentActivityItem): string {
  return item.phase === "profile_refresh"
    ? "Actualización del perfil"
    : "Ampliación de evidencia";
}

export function activityStatusCopy(item: EnrichmentActivityItem): string {
  if (item.phase === "profile_refresh") {
    if (item.status === "complete" && item.result?.outcome === "noop") {
      return "El perfil ya estaba al día";
    }
    return refreshCopy[item.status as keyof typeof refreshCopy] ?? refreshCopy.pending;
  }
  return evidenceCopy[item.status as keyof typeof evidenceCopy] ?? evidenceCopy.pending;
}

export function activityDetailCopy(item: EnrichmentActivityItem): string {
  if (activeStatuses.has(item.status)) {
    return `${activityStatusCopy(item)}. ${backgroundExplanation}`;
  }
  if (item.status === "failed") {
    if (item.phase === "profile_refresh") {
      return `${activityStatusCopy(item)}. El perfil sigue disponible; podés volver a intentar la actualización más tarde.`;
    }

    return `${activityStatusCopy(item)}. El perfil sigue disponible con la evidencia actual; vamos a volver a intentarlo más adelante.`;
  }
  if (item.phase === "evidence" && item.result) {
    const parts: string[] = [];
    if (item.result.covered_count > 0) {
      parts.push(`${item.result.covered_count} tema${item.result.covered_count === 1 ? "" : "s"} cubierto${item.result.covered_count === 1 ? "" : "s"}`);
    }
    if (item.result.missing_count > 0) {
      parts.push(`${item.result.missing_count} pendiente${item.result.missing_count === 1 ? "" : "s"}`);
    }
    return parts.length ? `${activityStatusCopy(item)}: ${parts.join(" · ")}.` : activityStatusCopy(item);
  }
  return activityStatusCopy(item);
}

export function activityTone(
  item: EnrichmentActivityItem,
): "neutral" | "primary" | "success" | "warning" | "error" {
  if (activeStatuses.has(item.status)) {
    return item.phase === "profile_refresh" ? "primary" : "neutral";
  }
  if (item.status === "complete") return "success";
  if (item.status === "partial") return "warning";
  return "error";
}

export function activityItemsRelatedTo(
  items: EnrichmentActivityItem[],
  options: {
    candidateIds?: string[];
    speciesKeys?: string[];
    scientificNames?: string[];
  } = {},
): EnrichmentActivityItem[] {
  const candidateIds = new Set(options.candidateIds ?? []);
  const speciesKeys = new Set(options.speciesKeys ?? []);
  const scientificNames = new Set(
    (options.scientificNames ?? []).map((name) => name.trim().toLowerCase()),
  );
  if (!candidateIds.size && !speciesKeys.size && !scientificNames.size) {
    return items;
  }
  return items.filter((item) => {
    if (item.candidate_id && candidateIds.has(item.candidate_id)) return true;
    if (item.species_key && speciesKeys.has(item.species_key)) return true;
    const name = item.scientific_name?.trim().toLowerCase();
    return Boolean(name && scientificNames.has(name));
  });
}