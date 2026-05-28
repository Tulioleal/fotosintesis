"use client";

import { ChangeEvent, useRef, useState } from "react";
import Link from "next/link";
import styles from "./IdentifyFlow.module.scss";

type Candidate = {
  id: string;
  common_name: string | null;
  suggested_scientific_name: string;
  confidence_label: string;
  visible_traits: string[];
  possible_match_copy: string;
  accepted_scientific_name: string | null;
  validation_status: "validated" | "no_gbif_match";
  gbif_key: number | null;
  genus: string | null;
  family: string | null;
  species: string | null;
  synonyms: string[];
  confirmed_at: string | null;
};

type Identification = {
  id: string;
  status: "needs_confirmation" | "retry_needed" | "no_reliable_candidate";
  sad_path: string | null;
  message: string;
  candidates: Candidate[];
};

const confidenceCopy: Record<string, string> = {
  high: "confianza alta",
  medium: "confianza media",
  low: "confianza baja",
  inconclusive: "inconclusa",
};

export function IdentifyFlow() {
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const [identification, setIdentification] = useState<Identification | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cameraNotice, setCameraNotice] = useState<string | null>(null);

  async function requestCamera() {
    setCameraNotice(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraNotice("Tu navegador no permite abrir la camara desde esta pantalla. Usa subir imagen.");
      uploadInputRef.current?.click();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      stream.getTracks().forEach((track) => track.stop());
      cameraInputRef.current?.click();
    } catch {
      setCameraNotice("No tenemos permiso de camara. Podes subir una foto desde tu dispositivo.");
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

    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("/api/identifications", { method: "POST", body: formData });
    const payload = await response.json();
    setIsSubmitting(false);

    if (!response.ok) {
      setError(payload.detail ?? "No pudimos analizar la imagen. Proba nuevamente.");
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
      setError(payload.detail ?? "Solo podes confirmar candidatas validadas por GBIF.");
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

  return (
    <section className={styles.flow}>
      <div className={styles.hero}>
        <p className={styles.eyebrow}>Identificacion asistida</p>
        <h1>Subi una foto clara antes de guardar o crear recordatorios.</h1>
        <p>
          Mostramos posibles coincidencias, validamos nombres con GBIF y bloqueamos acciones
          definitivas hasta que confirmes una candidata validada.
        </p>
      </div>

      <div className={styles.actions}>
        <button type="button" onClick={requestCamera}>Tomar foto</button>
        <button type="button" className={styles.secondary} onClick={() => uploadInputRef.current?.click()}>
          Subir imagen
        </button>
        <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={submitImage} hidden />
        <input ref={uploadInputRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={submitImage} hidden />
      </div>

      {cameraNotice ? <p className={styles.notice}>{cameraNotice}</p> : null}
      {error ? <p className={styles.error}>{error}</p> : null}
      {preview ? <img className={styles.preview} src={preview} alt="Vista previa de la planta" /> : null}
      {isSubmitting ? <p className={styles.notice}>Analizando imagen y validando taxonomia...</p> : null}

      {identification ? (
        <div className={styles.results}>
          <p className={identification.sad_path ? styles.warning : styles.notice}>{identification.message}</p>
          {identification.candidates.map((candidate) => (
            <article className={styles.card} key={candidate.id}>
              <div>
                <p className={styles.eyebrow}>{confidenceCopy[candidate.confidence_label] ?? candidate.confidence_label}</p>
                <h2>{candidate.common_name ?? candidate.suggested_scientific_name}</h2>
                <p><em>{candidate.accepted_scientific_name ?? candidate.suggested_scientific_name}</em></p>
              </div>
              <p>{candidate.possible_match_copy}</p>
              <ul>
                {candidate.visible_traits.map((trait) => <li key={trait}>{trait}</li>)}
              </ul>
              <p>
                {candidate.validation_status === "validated"
                  ? `GBIF validado${candidate.gbif_key ? ` #${candidate.gbif_key}` : ""}. ${[candidate.family, candidate.genus, candidate.species].filter(Boolean).join(" / ")}`
                  : "Sin coincidencia GBIF: usa busqueda manual o reintenta con otra foto."}
              </p>
              {candidate.synonyms.length ? <p>Sinonimos: {candidate.synonyms.join(", ")}</p> : null}
              <button
                type="button"
                disabled={candidate.validation_status !== "validated" || Boolean(candidate.confirmed_at)}
                onClick={() => confirmCandidate(candidate)}
              >
                {candidate.confirmed_at ? "Candidata confirmada" : "Confirmar candidata validada"}
              </button>
              {candidate.confirmed_at ? (
                <Link
                  className={styles.profileLink}
                  href={`/profiles/${encodeURIComponent(candidate.accepted_scientific_name ?? candidate.suggested_scientific_name)}?candidateId=${candidate.id}`}
                >
                  Ver perfil y agregar a Mi Jardin
                </Link>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
