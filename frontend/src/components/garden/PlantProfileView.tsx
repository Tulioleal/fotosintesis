"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  AppLink,
  Button,
  Card,
  Field,
  Notice,
  PageHeader,
  TextareaField,
} from "@/components/ui";
import iconStyles from "@/components/ui/Icons.module.scss";
import { apiClient } from "@/lib/api/client";
import type { CandidateEnrichmentStatus } from "@/lib/api/client";
import { buildAssistantHref } from "@/lib/assistant";
import { candidateEnrichmentQueryKey } from "@/lib/enrichment";
import { activityItemsRelatedTo, claimRefreshReconciliation, outcomeVersion, terminalStatuses as activityTerminalStatuses } from "@/lib/enrichment-activity";
import { useEnrichmentActivity } from "../enrichment/EnrichmentActivityProvider";
import { EnrichmentActivitySummary } from "../enrichment/EnrichmentActivitySummary";
import { ChatTextIcon, PlusCircleIcon, SunIcon } from "@phosphor-icons/react";
import styles from "./PlantProfileView.module.scss";

const sectionLabels: Record<string, string> = {
  description: "Descripcion",
  characteristics: "Caracteristicas",
  conditions: "Condiciones",
  care: "Cuidados",
  pests: "Plagas",
  diseases: "Enfermedades",
  recommendations: "Recomendaciones",
};

const lifecycleCopy = {
  pending: "La búsqueda está en espera",
  processing: "Estamos consultando y validando fuentes",
  complete: "La evidencia está lista",
  partial: "Encontramos evidencia útil, pero faltan algunos temas",
  failed: "No pudimos completar la búsqueda de evidencia",
} as const;

const limitationCopy: Record<string, string> = {
  missing_required_aspects: "Faltan aspectos requeridos.",
  safety_evidence_rejected: "La evidencia de seguridad no alcanzo el umbral requerido.",
  insufficient_evidence: "No se encontro evidencia suficiente.",
  retry_exhausted: "Se agotaron los reintentos de ampliar la evidencia.",
  workflow_incomplete: "El proceso de ampliacion quedo incompleto.",
  indexing_deferred: "La evidencia se guardo pero la indexacion quedo pendiente.",
};

const sectionStatusCopy: Record<string, string> = {
  stale: "Actualizacion pendiente",
  refreshing: "Actualizando...",
  partial: "Evidencia parcial",
};

const aspectCopy: Record<string, string> = {
  general_care_summary: "Cuidados generales",
  light_exposure: "Luz",
  soil_drainage: "Drenaje del sustrato",
  climate_temperature_range: "Temperatura",
  humidity_preference: "Humedad",
  watering_frequency_or_trigger: "Frecuencia de riego",
  watering_amount: "Cantidad de riego",
  nutrition_feeding_schedule: "Frecuencia de fertilizacion",
  nutrition_fertilizer_type: "Tipo de fertilizante",
  pest_identification: "Identificacion de plagas",
  pest_prevention_steps: "Prevencion de plagas",
  disease_identification: "Identificacion de enfermedades",
  disease_prevention_steps: "Prevencion de enfermedades",
  toxicity_pet_safety: "Seguridad para mascotas",
  toxicity_human_edibility: "Consumo humano",
  toxicity_child_safety: "Seguridad infantil",
  toxicity_handling_precautions: "Precauciones de manipulacion",
};

const terminalStatuses = new Set(["complete", "partial", "failed"]);
const activeStatuses = new Set(["pending", "processing"]);

export const ENRICHMENT_POLL_INTERVAL_MS = 3_000;
export const ENRICHMENT_STALL_AFTER_MS = 300_000;

export const plantProfileQueryKey = (
  userId: string,
  candidateId: string,
  scientificName: string,
  language: string,
) =>
  ["plant-profile", userId, candidateId, scientificName, language] as const;

export { candidateEnrichmentQueryKey } from "@/lib/enrichment";

export function enrichmentRefetchInterval(
  query: { state: { data?: CandidateEnrichmentStatus; status?: string } },
  fallback?: CandidateEnrichmentStatus | null,
  terminalObserved = false,
  stalled = false,
) {
  if (terminalObserved) return false;

  const enrichment = query.state.data ?? fallback;
  const status = enrichment?.job.status ?? "";
  if (!activeStatuses.has(status)) return false;
  if (stalled) return false;
  return ENRICHMENT_POLL_INTERVAL_MS;
}

function optionalText(value: FormDataEntryValue | null) {
  return typeof value === "string" && value ? value : null;
}

export function PlantProfileView({
  scientificName,
  confirmedCandidateId,
}: Readonly<{ scientificName: string; confirmedCandidateId?: string }>) {
  const queryClient = useQueryClient();
  const { userId, query: activity } = useEnrichmentActivity();
  const [language] = useState(() => typeof navigator === "undefined" ? "es" : navigator.language?.split("-")[0] ?? "es");
  const [message, setMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [enrichmentStalled, setEnrichmentStalled] = useState(false);
  const [enrichmentRefreshing, setEnrichmentRefreshing] = useState(false);
  const invalidatedTerminal = useRef<string | null>(null);
  const terminalObservation = useRef<string | null>(null);
  // Client observation window scoped by candidate and job id. Identical active
  // responses and lease-renewal timestamp changes never reset it; only a
  // candidate or job change starts a fresh bounded window.
  const observationWindow = useRef<{ key: string; startedAt: number } | null>(null);
  const profileQuery = useQuery({
    queryKey: plantProfileQueryKey(
      userId,
      confirmedCandidateId ?? "",
      scientificName,
      language,
    ),
    queryFn: () => apiClient.getPlantProfile(scientificName, confirmedCandidateId!, language),
    enabled: Boolean(confirmedCandidateId) && userId !== "anonymous",
  });
  const terminalObservedFor = (
    enrichment: CandidateEnrichmentStatus | null | undefined,
  ) =>
    terminalObservation.current !== null &&
    enrichment !== undefined &&
    enrichment !== null &&
    terminalObservation.current === `${confirmedCandidateId}:${enrichment.job.id}`;
  const enrichmentQuery = useQuery({
    queryKey: candidateEnrichmentQueryKey(
      userId,
      confirmedCandidateId ?? "",
      scientificName,
      language,
    ),
    queryFn: () => apiClient.getCandidateEnrichment(confirmedCandidateId!),
    enabled: Boolean(confirmedCandidateId) && userId !== "anonymous",
    refetchInterval: (query) =>
      enrichmentRefetchInterval(
        query,
        profileQuery.data?.enrichment,
        terminalObservedFor(query.state.data ?? profileQuery.data?.enrichment),
        enrichmentStalled,
      ),
  });
  const observedEnrichment =
    enrichmentQuery.data ?? profileQuery.data?.enrichment;

  useEffect(() => {
    const status = observedEnrichment?.job.status;
    const jobId = observedEnrichment?.job.id;
    if (!activeStatuses.has(status ?? "")) {
      observationWindow.current = null;
      setEnrichmentStalled(false);
      return;
    }
    if (!confirmedCandidateId || !jobId) return;
    const key = `${confirmedCandidateId}:${jobId}`;
    if (observationWindow.current === null || observationWindow.current.key !== key) {
      observationWindow.current = { key, startedAt: Date.now() };
      terminalObservation.current = null;
      setEnrichmentStalled(false);
    }
  }, [confirmedCandidateId, observedEnrichment?.job.id, observedEnrichment?.job.status]);

  useEffect(() => {
    if (!confirmedCandidateId) return;
    const check = () => {
      const window = observationWindow.current;
      if (window === null) {
        setEnrichmentStalled(false);
        return;
      }
      setEnrichmentStalled(
        Date.now() - window.startedAt >= ENRICHMENT_STALL_AFTER_MS,
      );
    };
    const timer = window.setInterval(check, ENRICHMENT_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [confirmedCandidateId]);
  const saveMutation = useMutation({
    mutationFn: (body: Parameters<typeof apiClient.saveGardenPlant>[0]) => apiClient.saveGardenPlant(body),
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["garden", "list"] });
      setMessage(`Guardada en Mi Jardin como ${payload.nickname ?? payload.profile.selected_alias ?? payload.profile.scientific_name}.`);
    },
    onError: (err: Error) => setSaveError(err.message || "No pudimos guardar la planta."),
  });

  useEffect(() => {
    terminalObservation.current = null;
    observationWindow.current = null;
    setEnrichmentStalled(false);
    setEnrichmentRefreshing(false);
  }, [confirmedCandidateId, scientificName, language]);

  useEffect(() => {
    const enrichment = enrichmentQuery.data;
    const status = enrichment?.job.status;
    if (!confirmedCandidateId || !status || !terminalStatuses.has(status)) return;

    const observation = `${confirmedCandidateId}:${enrichment.policy_version}:${enrichment.job.id}:${status}`;
    terminalObservation.current = `${confirmedCandidateId}:${enrichment.job.id}`;

    if (invalidatedTerminal.current === observation) return;
    invalidatedTerminal.current = observation;
    void queryClient.invalidateQueries({
      queryKey: plantProfileQueryKey(
        userId,
        confirmedCandidateId,
        scientificName,
        language,
      ),
      exact: true,
    });
  }, [confirmedCandidateId, enrichmentQuery.data, language, queryClient, scientificName, userId]);

  // Shared refresh awareness: a terminal profile-refresh phase invalidates
  // the exact profile query once per outcome version across the whole
  // session (remount-safe via the shared claim helper). Evidence-phase
  // terminal states never claim that the profile sections were updated.
  useEffect(() => {
    const profile = profileQuery.data;
    if (!profile || !confirmedCandidateId) return;

    const relatedActivity = activityItemsRelatedTo(
      activity.data?.items ?? [],
      {
        candidateIds: [confirmedCandidateId],
        speciesKeys: profile.canonical_species_key
          ? [profile.canonical_species_key]
          : [],
        scientificNames: [profile.scientific_name, scientificName],
      },
    );
    const terminalRefreshes = relatedActivity.filter(
      (item) =>
        item.phase === "profile_refresh" &&
        activityTerminalStatuses.has(item.status),
    );

    for (const item of terminalRefreshes) {
      const version = outcomeVersion(item);
      const profileKey = plantProfileQueryKey(
        userId,
        confirmedCandidateId,
        scientificName,
        language,
      );

      if (
        !version ||
        !claimRefreshReconciliation(userId, version, profileKey)
      ) {
        continue;
      }

      void queryClient.invalidateQueries({
        queryKey: profileKey,
        exact: true,
      });
    }
  }, [
    activity.data,
    confirmedCandidateId,
    language,
    profileQuery.data,
    queryClient,
    scientificName,
    userId,
  ]);

  async function savePlant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmedCandidateId) return;
    const formData = new FormData(event.currentTarget);
    setSaveError(null);
    setMessage(null);
    saveMutation.mutate({
      confirmed_candidate_id: confirmedCandidateId,
      nickname: optionalText(formData.get("nickname")),
      location: optionalText(formData.get("location")),
      notes: optionalText(formData.get("notes")),
      image_path: profileQuery.data?.confirmed_candidate_image_path ?? null,
    });
  }

  if (!confirmedCandidateId) {
    return <Notice tone="error" role="alert">Para ver el perfil, confirma primero una candidata validada desde Identificar.</Notice>;
  }
  if (profileQuery.isError && !profileQuery.data) {
    return <Notice tone="error" role="alert">{profileQuery.error.message || "No pudimos cargar el perfil."}</Notice>;
  }
  if (!profileQuery.data) return <Notice tone="info" role="status">Cargando el perfil guardado...</Notice>;
  const profile = profileQuery.data;
  const enrichment = enrichmentQuery.data ?? profile.enrichment;
  const aliases = profile.aliases ?? [];
  const limitations = profile.limitations ?? [];
  const sections = profile.sections ?? {};
  const sources = profile.sources ?? [];
  const sectionStatusByKey: Record<string, string> = {};
  for (const entry of profile.section_status ?? []) {
    sectionStatusByKey[entry.section] = entry.status;
  }
  const binomialName = profile.binomial_name ?? null;
  const assistantHref = buildAssistantHref({
    plant: profile.selected_alias ?? profile.common_name ?? profile.scientific_name,
    binomial: binomialName,
    scientific: profile.scientific_name,
    candidate: confirmedCandidateId ?? null,
  });
  const reminderHref = `/reminders?plant=${encodeURIComponent(profile.scientific_name)}`;
  const lightMeterHref = `/light-meter?plant=${encodeURIComponent(profile.scientific_name)}`;

  return (
    <section className={styles.profile}>
      <PageHeader
        eyebrow="Perfil botanico guardado"
        heading={profile.selected_alias ?? profile.common_name ?? profile.scientific_name}
        description={profile.scientific_name}
      />

      {enrichment ? (
        <EnrichmentSummary
          enrichment={enrichment}
          stalled={enrichmentStalled}
          refreshing={enrichmentRefreshing}
          onRetry={() => {
            if (enrichmentRefreshing) return;
            setEnrichmentRefreshing(true);
            void enrichmentQuery.refetch().finally(() => {
              setEnrichmentRefreshing(false);
            });
          }}
        />
      ) : null}
      <EnrichmentActivitySummary
        variant="inline"
        relatedTo={{
          candidateIds: confirmedCandidateId ? [confirmedCandidateId] : [],
          speciesKeys: profile.canonical_species_key
            ? [profile.canonical_species_key]
            : [],
          scientificNames: [profile.scientific_name],
        }}
      />
      {profileQuery.isError ? (
        <Notice tone="warning" role="note" heading="No pudimos actualizar el perfil">
          Conservamos la ultima instantanea disponible. {profileQuery.error.message}
        </Notice>
      ) : null}
      {enrichmentQuery.isError ? (
        <Notice tone="warning" role="alert" heading="Estado de evidencia no disponible">
          {enrichmentQuery.error.message || "No pudimos actualizar el estado de enriquecimiento."}
        </Notice>
      ) : null}

      {limitations.length ? (
        <Notice tone="warning" role="note" heading="Limitaciones de la evidencia">
          {limitations.map((item) => <p key={item}>{item}</p>)}
        </Notice>
      ) : null}

      <Card variant="tonal" padding="md">
        <p className={styles.eyebrow}>
          Confianza de evidencia: {Math.round(profile.confidence * 100)}%
        </p>
        {aliases.length ? (
          <p className={styles.aliases}>
            Alias: {aliases.map((alias) => alias.name).join(", ")}
          </p>
        ) : null}
        <div className={styles.ctas}>
          <AppLink href="#save" variant="button" buttonVariant="primary" leadingIcon={<PlusCircleIcon aria-hidden="true" size="1rem" className={iconStyles.toneOnPrimary} />}>
            Agregar a Mi Jardin
          </AppLink>
          <AppLink href={assistantHref} variant="button" buttonVariant="outline" leadingIcon={<ChatTextIcon aria-hidden="true" size="1rem" className={iconStyles.tonePrimary} />}>
            Preguntar al asistente
          </AppLink>
          <AppLink href={reminderHref} variant="button" buttonVariant="outline" leadingIcon={<PlusCircleIcon aria-hidden="true" size="1rem" className={iconStyles.tonePrimary} />}>
            Crear recordatorio
          </AppLink>
          <AppLink href={lightMeterHref} variant="button" buttonVariant="outline" leadingIcon={<SunIcon aria-hidden="true" size="1rem" className={iconStyles.tonePrimary} />}>
            Medir luz
          </AppLink>
        </div>
      </Card>

      <div className={styles.sections}>
        {Object.entries(sectionLabels).map(([key, label]) => {
          const status = sectionStatusByKey[key];
          return (
            <Card key={key} variant="tonal" padding="md">
              <div className={styles.sectionHeader}>
                <h2 className={styles.sectionTitle}>{label}</h2>
                {status && status !== "current" ? (
                  <span className={styles.sectionStatusBadge} role="note">
                    {sectionStatusCopy[status] ?? status}
                  </span>
                ) : null}
              </div>
              {(sections[key] ?? []).map((text: string) => (
                <p key={text} className={styles.sectionCopy}>{text}</p>
              ))}
            </Card>
          );
        })}
      </div>

      <Card id="save" variant="tonal" padding="md">
        <h2 className={styles.sectionTitle}>Guardar en Mi Jardin</h2>
        {confirmedCandidateId ? (
          <form className={styles.form} onSubmit={savePlant}>
            <Field name="nickname" label="Nombre personalizado" placeholder="Nombre personalizado" />
            <Field name="location" label="Ubicacion en casa" placeholder="Ubicacion en casa" />
            <TextareaField kind="textarea" name="notes" label="Notas propias" placeholder="Notas propias" />
            <div className={styles.formActions}>
              <Button type="submit" variant="primary" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? "Guardando..." : "Guardar planta confirmada"}
              </Button>
            </div>
          </form>
        ) : (
          <Notice tone="info" role="status">
            Para guardar esta planta, confirmala primero desde Identificar.
          </Notice>
        )}
        {message ? <Notice tone="success" role="status">{message}</Notice> : null}
        {saveError ? <Notice tone="error" role="alert">{saveError}</Notice> : null}
      </Card>

      <Card variant="tonal" padding="md">
        <h2 className={styles.sectionTitle}>Fuentes de esta instantanea guardada</h2>
        <p className={styles.sectionCopy}>
          Estas fuentes respaldan solo las secciones de la instantanea. La evidencia nueva se informa por separado y no cambia este contenido automaticamente.
        </p>
        {sources.length ? (
          <ul className={styles.sourcesList}>
            {sources.map((source) => (
              <li key={source.url} className={styles.sourcesItem}>
                <AppLink href={source.url} external variant="default">
                  {source.title || source.domain}
                </AppLink>
                <span className={styles.sourceConfidence}>
                  Confianza: {Math.round(source.confidence * 100)}%
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.sectionCopy}>
            No hay fuentes suficientes todavia; el perfil muestra limitaciones explicitas.
          </p>
        )}
      </Card>
    </section>
  );
}

function EnrichmentSummary({
  enrichment,
  stalled,
  refreshing,
  onRetry,
}: Readonly<{
  enrichment: CandidateEnrichmentStatus;
  stalled: boolean;
  refreshing: boolean;
  onRetry: () => void;
}>) {
  const { job, policy_version: policyVersion } = enrichment;
  const result = enrichmentResult(enrichment);
  const limitations = result?.limitations ?? (job.last_error ? [job.last_error.category] : []);
  const status = lifecycleCopy[job.status];

  return (
    <Card variant="tonal" padding="md">
      <h2 className={styles.sectionTitle}>Estado de la evidencia</h2>
      <div role="status" aria-live="polite">
          <p className={styles.sectionCopy}>
            {status} · Política v{policyVersion}
          </p>
          {job.status === "pending" || job.status === "processing" ? (
            <p className={styles.sectionCopy}>
              Estamos ampliando este perfil en segundo plano con información de fuentes confiables.
              Puedes seguir usando Fotosíntesis; el perfil se actualizará automáticamente.
            </p>
          ) : null}
          {job.status === "complete" ? (
            <p className={styles.sectionCopy}>
              La búsqueda terminó y el perfil ya puede mostrar la información encontrada.
            </p>
          ) : null}
          {stalled ? (
            <p className={styles.sectionCopy}>
              Está tardando más de lo esperado, pero continúa en segundo plano. Puedes seguir usando el perfil.
          </p>
        ) : null}
      </div>
      {stalled ? (
        <Button
          variant="outline"
          onClick={onRetry}
          disabled={refreshing}
          aria-busy={refreshing}
        >
          {refreshing ? "Revisando estado..." : "Revisar estado"}
        </Button>
      ) : null}
      {result ? (
        <div className={styles.evidenceSummary}>
          <AspectSummary label="Aspectos cubiertos" aspects={result.covered_aspects} count={result.covered_count} />
          <AspectSummary label="Aspectos pendientes" aspects={result.missing_aspects} count={result.missing_count} />
        </div>
      ) : null}
      {limitations.length ? (
        <p className={styles.sectionCopy}>
          Limitacion: {limitations.map((item) => limitationCopy[item] ?? "La ampliacion de evidencia quedo limitada.").join(" ")}
        </p>
      ) : null}
      <p className={styles.snapshotNote}>
        La evidencia encontrada puede tardar unos instantes más en reflejarse en las secciones del perfil.
      </p>
    </Card>
  );
}

function AspectSummary({ label, aspects, count }: Readonly<{ label: string; aspects: string[]; count: number }>) {
  const visibleAspects = aspects.slice(0, 8);
  return (
    <p className={styles.sectionCopy}>
      <strong>{label} ({count}):</strong>{" "}
      {visibleAspects.length ? visibleAspects.map(aspectLabel).join(", ") : "ninguno"}
      {count > visibleAspects.length ? ` y ${count - visibleAspects.length} mas` : ""}.
    </p>
  );
}

function aspectLabel(aspect: string) {
  return aspectCopy[aspect] ?? aspect;
}

function enrichmentResult(enrichment: CandidateEnrichmentStatus) {
  const result = enrichment.job.result;
  return result && "covered_aspects" in result ? result : null;
}
