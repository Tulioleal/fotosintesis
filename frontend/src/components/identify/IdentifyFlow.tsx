"use client";

import { ChangeEvent, useRef, useState } from "react";
import {
  CameraIcon,
  CheckCircleIcon,
  PlantIcon,
  QuestionIcon,
  UploadSimpleIcon,
  WarningIcon,
} from "@phosphor-icons/react";
import {
  AppLink,
  Button,
  Card,
  Chip,
  ImageCard,
  Notice,
  PageHeader,
} from "@/components/ui";
import iconStyles from "@/components/ui/Icons.module.scss";
import { buildAssistantHref } from "@/lib/assistant";
import styles from "./IdentifyFlow.module.scss";
import Image from "next/image";

type Candidate = {
  id: string;
  common_name: string | null;
  suggested_scientific_name: string;
  confidence_label: string;
  confidence_score?: number | null;
  visible_traits: string[];
  possible_match_copy: string;
  accepted_scientific_name: string | null;
  binomial_name: string | null;
  validation_status: "validated" | "no_gbif_match";
  gbif_key: number | null;
  genus: string | null;
  family: string | null;
  species: string | null;
  synonyms: string[];
  image_url?: string | null;
  confirmed_at: string | null;
};

type Identification = {
  id: string;
  status: "needs_confirmation" | "retry_needed" | "no_reliable_candidate";
  sad_path: string | null;
  message: string;
  candidates: Candidate[];
};

const defaultFileName = "foto_planta_capturada.jpg";

const confidenceCopy: Record<string, string> = {
  high: "Confianza: Alta",
  medium: "Confianza: Media",
  low: "Confianza: Baja",
  inconclusive: "Confianza: Inconclusa",
};

const confidenceTone: Record<string, "primary" | "secondary" | "warning"> = {
  high: "primary",
  medium: "secondary",
  low: "warning",
  inconclusive: "warning",
};

const validationChipCopy: Record<"validated" | "no_gbif_match", string> = {
  validated: "GBIF validado",
  no_gbif_match: "Sin coincidencia GBIF",
};

export function IdentifyFlow() {
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const [identification, setIdentification] = useState<Identification | null>(
    null,
  );
  const [preview, setPreview] = useState<string | null>(null);
  const [previewName, setPreviewName] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cameraNotice, setCameraNotice] = useState<string | null>(null);

  function resetFlow() {
    setIdentification(null);
    setPreview(null);
    setPreviewName(null);
    setIsSubmitting(false);
    setError(null);
    setCameraNotice(null);
    if (cameraInputRef.current) cameraInputRef.current.value = "";
    if (uploadInputRef.current) uploadInputRef.current.value = "";
  }

  async function requestCamera() {
    setCameraNotice(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraNotice(
        "Tu navegador no permite abrir la camara desde esta pantalla. Usa subir imagen.",
      );
      uploadInputRef.current?.click();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      stream.getTracks().forEach((track) => track.stop());
      cameraInputRef.current?.click();
    } catch {
      setCameraNotice(
        "No tenemos permiso de camara. Podes subir una foto desde tu dispositivo.",
      );
      uploadInputRef.current?.click();
    }
  }

  async function submitImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsSubmitting(true);
    setError(null);
    setIdentification(null);
    setPreview(URL.createObjectURL(file));
    setPreviewName(file.name);

    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("/api/identifications", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    setIsSubmitting(false);

    if (!response.ok) {
      setError(
        payload.detail ?? "No pudimos analizar la imagen. Proba nuevamente.",
      );
      return;
    }
    setIdentification(payload as Identification);
  }

  async function confirmCandidate(candidate: Candidate) {
    if (!identification || candidate.validation_status !== "validated") return;
    const response = await fetch(
      `/api/identifications/${identification.id}/candidates/${candidate.id}/confirm`,
      { method: "POST" },
    );
    const payload = await response.json();
    if (!response.ok) {
      setError(
        payload.detail ?? "Solo podes confirmar candidatas validadas por GBIF.",
      );
      return;
    }

    setIdentification({
      ...identification,
      candidates: identification.candidates.map((item) =>
        item.id === candidate.id
          ? { ...item, confirmed_at: payload.candidate.confirmed_at }
          : { ...item, confirmed_at: null },
      ),
    });
  }

  const showResults = Boolean(identification);
  const showUploadPanel = !isSubmitting && !showResults;
  const showAnalyzingHeader = isSubmitting;
  const shouldShowCandidates =
    showResults &&
    identification !== null &&
    !identification.sad_path &&
    identification.status === "needs_confirmation" &&
    identification.candidates.length > 0;

  return (
    <section className={styles.flow}>
      <PageHeader
        heading="Identificar Planta"
        description="Sube o toma una foto para identificar tu planta."
      />

      {showUploadPanel ? (
        <section className={styles.analysisPanel}>
          <div className={styles.dropZone}>
            <div className={styles.dropIcon} aria-hidden="true">
              <PlantIcon size="2.5rem" className={iconStyles.tonePrimary} />
            </div>
            <div className={styles.dropActions}>
              <Button
                variant="primary"
                onClick={() => uploadInputRef.current?.click()}
                leadingIcon={
                  <UploadSimpleIcon
                    aria-hidden="true"
                    size="1.25rem"
                    weight="regular"
                  />
                }
              >
                Subir Foto
              </Button>
              <Button
                variant="outline"
                onClick={requestCamera}
                leadingIcon={
                  <CameraIcon
                    aria-hidden="true"
                    size="1.25rem"
                    weight="regular"
                  />
                }
              >
                Abrir Cámara
              </Button>
            </div>
            <p className={styles.dropHint}>o arrastra y suelta aquí</p>
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={submitImage}
              hidden
            />
            <input
              ref={uploadInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={submitImage}
              hidden
            />
          </div>
        </section>
      ) : null}

      {cameraNotice ? (
        <Notice
          tone="warning"
          heading="Camara no disponible"
          icon={
            <CameraIcon
              aria-hidden="true"
              size="1.25rem"
              className={iconStyles.toneSecondary}
            />
          }
        >
          {cameraNotice}
        </Notice>
      ) : null}

      {error ? (
        <Notice
          tone="error"
          heading="No pudimos analizar la imagen"
          role="alert"
        >
          {error}
        </Notice>
      ) : null}

      {isSubmitting && preview ? (
        <section className={styles.analysisPanel}>
          <div className={`${styles.previewFrame} ${styles.previewBorder}`}>
            <Image
              className={styles.previewImageAnalyzing}
              src={preview}
              alt=""
              layout="fill"
            />
            <div className={styles.scanOverlay} />
          </div>
          <div className={styles.analysisStatus}>
            <p className={styles.fileName}>{previewName ?? defaultFileName}</p>
            <p className={styles.statusCopy}>Analizando imagen...</p>
            <div
              className={styles.progress}
              role="progressbar"
              aria-label="Analizando imagen"
              aria-valuetext="Analizando imagen"
            >
              <span className={styles.progressBar} />
            </div>
            <Button variant="ghost" size="sm" onClick={resetFlow}>
              Eliminar y repetir
            </Button>
          </div>
        </section>
      ) : null}

      {showAnalyzingHeader ? (
        <header className={styles.resultsHeader}>
          <h2 className={styles.resultsHeading}>Posibles Coincidencias</h2>
          <Chip tone="neutral">
            <span className={styles.searchPulse} aria-hidden="true" />
            Buscando...
          </Chip>
        </header>
      ) : null}

      {isSubmitting ? (
        <ul className={styles.resultGrid} role="list" aria-hidden="true">
          {[0, 1, 2].map((index) => (
            <li key={index} className={styles.skeletonCard}>
              <div className={styles.skeletonImage} />
              <div className={styles.skeletonLines}>
                <div
                  className={styles.skeletonLine}
                  style={{
                    width: index === 0 ? "66%" : index === 1 ? "74%" : "50%",
                  }}
                />
                <div className={styles.skeletonLineTertiary} />
                <div
                  className={styles.skeletonLineTertiary}
                  style={{
                    width: index === 0 ? "100%" : index === 1 ? "85%" : "100%",
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {showResults && identification ? (
        <div className={styles.resultsSection}>
          {preview ? (
            <Card variant="tonal" padding="md" className={styles.analysisPanel}>
              <div className={styles.previewFrame}>
                <Image
                  className={styles.previewImage}
                  src={preview}
                  alt={previewName ?? "Foto capturada para identificar"}
                  layout="fill"
                />
              </div>
              <div className={styles.analysisStatus}>
                <h2 className={styles.fileNameHeading}>
                  {previewName ?? defaultFileName}
                </h2>
                <p className={styles.statusCopy}>Imagen analizada con éxito</p>
                <Button variant="ghost" size="sm" onClick={resetFlow}>
                  Eliminar y repetir
                </Button>
              </div>
            </Card>
          ) : null}

          {identification.sad_path ? (
            <Notice
              tone="warning"
              heading="Necesitamos otra foto"
              role="status"
            >
              {identification.message}
            </Notice>
          ) : null}

          {shouldShowCandidates && identification ? (
            <>
              <hr className={styles.resultsDivider} />

              <header className={styles.resultsHeader}>
                <h2 className={styles.resultsHeading}>
                  Posibles Coincidencias
                </h2>
                <Chip tone="neutral">
                  {identification.candidates.length}{" "}
                  {identification.candidates.length === 1
                    ? "resultado"
                    : "resultados"}
                </Chip>
              </header>

              <ul className={styles.resultGrid} role="list">
                {identification.candidates.map((candidate) => {
                  const isValidated =
                    candidate.validation_status === "validated";
                  const isConfirmed = Boolean(candidate.confirmed_at);
                  return (
                    <li key={candidate.id}>
                      <ImageCard
                        variant="result"
                        className={styles.resultCard}
                        fallback={
                          <PlantIcon
                            size="2.5rem"
                            className={iconStyles.toneMuted}
                          />
                        }
                        title={candidateDisplayName(candidate)}
                        description={candidate.possible_match_copy}
                        meta={
                          <>
                            <p className={styles.confidenceLine}>
                              <span
                                className={styles.confidenceIcon}
                                aria-hidden="true"
                              >
                                {confidenceIconFor(candidate.confidence_label)}
                              </span>
                              {formatConfidence(candidate)}
                            </p>
                            <Button
                              type="button"
                              variant={isValidated ? "primary" : "outline"}
                              fullWidth
                              disabled={!isValidated || isConfirmed}
                              onClick={() => confirmCandidate(candidate)}
                            >
                              {isConfirmed
                                ? "Planta seleccionada"
                                : "Seleccionar esta planta"}
                            </Button>
                            {isConfirmed ? (
                              <div className={styles.candidateLinks}>
                                <AppLink
                                  href={`/profiles/${encodeURIComponent(
                                    candidate.accepted_scientific_name ??
                                      candidate.suggested_scientific_name,
                                  )}?candidateId=${candidate.id}`}
                                  variant="button"
                                  buttonVariant="outline"
                                  buttonSize="sm"
                                  fullWidth
                                >
                                  Ver perfil y agregar a Mi Jardin
                                </AppLink>
                                <AppLink
                                  href={assistantHrefForCandidate(candidate)}
                                  variant="button"
                                  buttonVariant="outline"
                                  buttonSize="sm"
                                  fullWidth
                                >
                                  Preguntar al asistente
                                </AppLink>
                              </div>
                            ) : null}
                            {!isValidated ? (
                              <p className={styles.confidenceLine}>
                                {
                                  validationChipCopy[
                                    candidate.validation_status
                                  ]
                                }
                              </p>
                            ) : null}
                          </>
                        }
                      />
                    </li>
                  );
                })}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function confidenceIconFor(label: string) {
  const tone = confidenceTone[label] ?? "warning";
  if (tone === "primary") {
    return (
      <CheckCircleIcon
        size="1rem"
        weight="regular"
        className={iconStyles.tonePrimary}
      />
    );
  }
  if (tone === "secondary") {
    return (
      <QuestionIcon
        size="1rem"
        weight="regular"
        className={iconStyles.toneSecondary}
      />
    );
  }
  return (
    <WarningIcon
      size="1rem"
      weight="regular"
      className={iconStyles.toneMuted}
    />
  );
}

function formatConfidence(candidate: Candidate) {
  const label =
    confidenceCopy[candidate.confidence_label] ?? candidate.confidence_label;
  if (typeof candidate.confidence_score === "number") {
    return `${label} (${Math.round(candidate.confidence_score * 100)}%)`;
  }
  return label;
}

function assistantHrefForCandidate(candidate: Candidate) {
  const scientific =
    candidate.accepted_scientific_name ?? candidate.suggested_scientific_name;
  return buildAssistantHref({
    plant: candidateDisplayName(candidate),
    binomial: candidate.binomial_name,
    scientific,
  });
}

function candidateDisplayName(candidate: Candidate) {
  return (
    candidate.common_name ??
    candidate.binomial_name ??
    candidateScientificName(candidate)
  );
}

function candidateScientificName(candidate: Candidate) {
  return (
    candidate.accepted_scientific_name ?? candidate.suggested_scientific_name
  );
}
