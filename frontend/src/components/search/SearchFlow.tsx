"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  GlobeHemisphereWestIcon,
  MagnifyingGlassIcon,
  PlantIcon,
  SpinnerGapIcon,
} from "@phosphor-icons/react";
import {
  Button,
  Card,
  Chip,
  Field,
  Notice,
  PageHeader,
} from "@/components/ui";
import iconStyles from "@/components/ui/Icons.module.scss";
import {
  apiClient,
  type GbifCandidate,
  type SearchLocalResponse,
} from "@/lib/api/client";
import styles from "./SearchFlow.module.scss";

type LocalResult = NonNullable<SearchLocalResponse["results"]>[number];

export function SearchFlow() {
  const inputId = useId();
  const resultsLiveRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [expandExternal, setExpandExternal] = useState(false);
  const [selectedCandidate, setSelectedCandidate] =
    useState<GbifCandidate | null>(null);
  const [createdCandidateId, setCreatedCandidateId] = useState<string | null>(
    null,
  );
  const [announcement, setAnnouncement] = useState<string | null>(null);

  const localQuery = useQuery({
    queryKey: ["search", "local", submitted],
    queryFn: () => apiClient.searchPlants(submitted),
    enabled: submitted.trim().length > 0,
  });

  const localResults: LocalResult[] = localQuery.data?.results ?? [];

  // External expansion runs when the user asks for it OR local results are
  // empty, so a name with no local profile still offers GBIF candidates.
  const shouldExpand =
    expandExternal ||
    (submitted.trim().length > 0 &&
      !localQuery.isLoading &&
      !localQuery.isError &&
      localResults.length === 0);

  const gbifQuery = useQuery({
    queryKey: ["search", "gbif", submitted],
    queryFn: () => apiClient.searchGbif(submitted),
    enabled: shouldExpand,
  });

  const gbifCandidates: GbifCandidate[] = gbifQuery.data?.candidates ?? [];

  const createCandidate = useMutation({
    mutationFn: () =>
      apiClient.createManualCandidate({
        query: submitted,
        gbif: selectedCandidate!,
      }),
    onSuccess: (candidate) => {
      setCreatedCandidateId(candidate.id);
      setAnnouncement(
        `Candidata "${candidate.binomial_name ?? candidate.suggested_scientific_name}" creada. Confirmala para preparar su perfil.`,
      );
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (candidateId: string) =>
      apiClient.confirmManualCandidate(candidateId),
    onSuccess: (response) => {
      const scientific =
        response.candidate.accepted_scientific_name ??
        response.candidate.suggested_scientific_name;
      window.location.href = `/profiles/${encodeURIComponent(scientific)}?candidateId=${encodeURIComponent(response.candidate.id)}`;
    },
  });

  useEffect(() => {
    if (!announcement) return;
    const timer = window.setTimeout(() => setAnnouncement(null), 4000);
    return () => window.clearTimeout(timer);
  }, [announcement]);

  function runSearch(event?: React.FormEvent) {
    event?.preventDefault();
    const term = query.trim();
    if (!term) return;
    setSubmitted(term);
    setExpandExternal(false);
    setSelectedCandidate(null);
    setCreatedCandidateId(null);
    setAnnouncement(null);
  }

  function selectCandidate(candidate: GbifCandidate) {
    setSelectedCandidate(candidate);
    setCreatedCandidateId(null);
    setAnnouncement(null);
    createCandidate.reset();
    confirmMutation.reset();
  }

  const showLoading = localQuery.isLoading;
  const showLocalError = localQuery.isError;
  const showEmpty =
    !localQuery.isLoading &&
    !localQuery.isError &&
    submitted.trim().length > 0 &&
    localResults.length === 0 &&
    gbifCandidates.length === 0 &&
    !gbifQuery.isLoading &&
    !gbifQuery.isError;

  return (
    <section className={styles.search}>
      <PageHeader
        heading="Buscar Plantas"
        description="Encontrá una planta por su nombre científico, común o regional."
      />

      <form className={styles.searchForm} onSubmit={runSearch} role="search">
        <Field
          kind="input"
          id={inputId}
          label="Nombre de la planta"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ej.: Monstera, Costilla de Adán, tomate…"
          autoComplete="off"
        />
        <Button
          type="submit"
          variant="primary"
          leadingIcon={
            <MagnifyingGlassIcon aria-hidden="true" size="1.25rem" />
          }
        >
          Buscar
        </Button>
      </form>

      <div
        className={styles.liveRegion}
        ref={resultsLiveRef}
        role="status"
        aria-live="polite"
      >
        {announcement}
      </div>

      {showLoading ? (
        <Notice tone="info" role="status">
          <SpinnerGapIcon
            aria-hidden="true"
            className={styles.spinner}
            size="1.25rem"
          />
          Buscando plantas…
        </Notice>
      ) : null}

      {showLocalError ? (
        <Notice tone="error" role="alert">
          No pudimos buscar plantas locales. Reintentá en unos segundos.
          <Button
            variant="ghost"
            size="sm"
            onClick={() => localQuery.refetch()}
          >
            Reintentar
          </Button>
        </Notice>
      ) : null}

      {showEmpty ? (
        <Card variant="tonal" padding="md" className={styles.empty}>
          <h2 className={styles.emptyTitle}>Sin resultados</h2>
          <p className={styles.emptyBody}>
            No encontramos “{submitted}”. Probá con otro nombre o expandí la
            búsqueda a GBIF.
          </p>
        </Card>
      ) : null}

      {submitted.trim().length > 0 && !localQuery.isLoading ? (
        <>
          <header className={styles.sectionHeader}>
            <h2 className={styles.sectionHeading}>Resultados locales</h2>
            <Chip tone="neutral">{localResults.length} registros</Chip>
          </header>

          {localResults.length > 0 ? (
            <ul className={styles.resultGrid} role="list">
              {localResults.map((result) => (
                <li key={result.profile_id}>
                  <Card variant="outlined" padding="md" className={styles.localCard}>
                    <div className={styles.localCardBody}>
                      <Chip tone="primary">Registro local</Chip>
                      <h3 className={styles.resultTitle}>
                        {result.scientific_name}
                      </h3>
                      {result.common_name ? (
                        <p className={styles.resultCommon}>
                          {result.common_name}
                        </p>
                      ) : null}
                      <p className={styles.resultMeta}>
                        Coincide por {matchLabel(result.matched_field)} ·{" "}
                        {result.has_evidence
                          ? "con perfil disponible"
                          : "sin perfil aún"}
                      </p>
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.sectionHint}>
              No hay registros locales para este nombre.
            </p>
          )}

          {gbifQuery.isLoading ? (
            <Notice tone="info" role="status">
              Buscando en GBIF…
            </Notice>
          ) : null}

          {gbifQuery.isError ? (
            <Notice tone="warning" role="status">
              No pudimos consultar GBIF. Podés reintentar la expansión externa.
              <Button
                variant="ghost"
                size="sm"
                onClick={() => gbifQuery.refetch()}
              >
                Reintentar
              </Button>
            </Notice>
          ) : null}

          {gbifCandidates.length > 0 ? (
            <section className={styles.externalSection}>
              <header className={styles.sectionHeader}>
                <h2 className={styles.sectionHeading}>
                  Candidatas externas (GBIF)
                </h2>
                <Chip tone="secondary">
                  <GlobeHemisphereWestIcon
                    aria-hidden="true"
                    size="1rem"
                  />
                  Sin confirmar
                </Chip>
              </header>
              <p className={styles.externalHint}>
                Estas son candidatas taxonómicas. Seleccioná una para crear tu
                candidata y confirmarla después.
              </p>
              <ul className={styles.resultGrid} role="list">
                {gbifCandidates.map((candidate) => (
                  <li key={gbifKey(candidate)}>
                    <Card
                      variant="outlined"
                      padding="md"
                      className={styles.gbifCard}
                    >
                      <Chip tone="secondary">Candidata externa</Chip>
                      <h3 className={styles.resultTitle}>
                        {candidate.accepted_scientific_name ??
                          candidate.binomial_name}
                      </h3>
                      {candidate.rank ? (
                        <p className={styles.resultMeta}>
                          Rango: {candidate.rank}
                        </p>
                      ) : null}
                      {candidate.family || candidate.genus ? (
                        <p className={styles.resultMeta}>
                          {candidate.family ?? ""}
                          {candidate.family && candidate.genus ? " · " : ""}
                          {candidate.genus ?? ""}
                        </p>
                      ) : null}
                      <div className={styles.cardActions}>
                        <Button
                          type="button"
                          variant={
                            selectedCandidate &&
                            gbifKey(selectedCandidate) === gbifKey(candidate)
                              ? "primary"
                              : "outline"
                          }
                          size="sm"
                          onClick={() => selectCandidate(candidate)}
                        >
                          {selectedCandidate &&
                          gbifKey(selectedCandidate) === gbifKey(candidate)
                            ? "Seleccionada"
                            : "Seleccionar"}
                        </Button>
                      </div>
                    </Card>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {selectedCandidate ? (
            <Card variant="callout" padding="md" className={styles.confirmPanel}>
              <h3 className={styles.confirmTitle}>Confirmar candidata</h3>
              <p className={styles.confirmBody}>
                {createdCandidateId
                  ? "Tu candidata se creó. Confirmala para preparar su perfil."
                  : `Crear y confirmar “${
                      selectedCandidate.accepted_scientific_name ??
                      selectedCandidate.binomial_name
                    }” como candidata manual.`}
              </p>
              {createCandidate.isError ? (
                <Notice tone="error" role="alert">
                  No pudimos crear la candidata. Reintentá.
                </Notice>
              ) : null}
              {confirmMutation.isError ? (
                <Notice tone="error" role="alert">
                  No pudimos confirmar la candidata. Reintentá.
                </Notice>
              ) : null}
              <div className={styles.cardActions}>
                {!createdCandidateId ? (
                  <Button
                    type="button"
                    variant="primary"
                    onClick={() => createCandidate.mutate()}
                    disabled={createCandidate.isPending}
                  >
                    {createCandidate.isPending
                      ? "Creando candidata…"
                      : "Crear candidata"}
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="primary"
                    onClick={() => confirmMutation.mutate(createdCandidateId)}
                    disabled={confirmMutation.isPending}
                  >
                    {confirmMutation.isPending
                      ? "Confirmando y preparando perfil…"
                      : "Confirmar y ver perfil"}
                  </Button>
                )}
              </div>
            </Card>
          ) : null}
        </>
      ) : null}

      {!submitted.trim() ? (
        <Card variant="tonal" padding="md" className={styles.empty}>
          <div className={styles.emptyIcon} aria-hidden="true">
            <PlantIcon size="2rem" className={iconStyles.tonePrimary} />
          </div>
          <p className={styles.emptyBody}>
            Escribí un nombre para encontrar tu planta. Podés usar el nombre
            científico, común o un alias regional.
          </p>
        </Card>
      ) : null}
    </section>
  );
}

function matchLabel(field: LocalResult["matched_field"]): string {
  switch (field) {
    case "scientific_name":
      return "nombre científico";
    case "binomial_name":
      return "nombre binomial";
    case "common_name":
      return "nombre común";
    case "alias":
      return "alias regional";
    default:
      return field;
  }
}

function gbifKey(candidate: GbifCandidate): string {
  return String(candidate.accepted_key ?? candidate.key ?? "");
}
