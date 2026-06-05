"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import type { PlantProfile } from "./types";
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

function optionalText(value: FormDataEntryValue | null) {
  return typeof value === "string" && value ? value : null;
}

export function PlantProfileView({
  scientificName,
  confirmedCandidateId,
}: Readonly<{ scientificName: string; confirmedCandidateId?: string }>) {
  const queryClient = useQueryClient();
  const [profile, setProfile] = useState<PlantProfile | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const saveMutation = useMutation({
    mutationFn: (body: Parameters<typeof apiClient.saveGardenPlant>[0]) => apiClient.saveGardenPlant(body),
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["garden", "list"] });
      setMessage(`Guardada en Mi Jardin como ${payload.nickname ?? payload.profile.selected_alias ?? payload.profile.scientific_name}.`);
    },
    onError: (err: Error) => setError(err.message || "No pudimos guardar la planta."),
  });

  useEffect(() => {
    setProfile(null);
    setError(null);
    if (!confirmedCandidateId) {
      setError("Para ver el perfil, confirma primero una candidata validada desde Identificar.");
      return;
    }
    const language = navigator.language?.split("-")[0] ?? "es";
    const params = new URLSearchParams({ language, candidateId: confirmedCandidateId });
    fetch(`/api/plant-profiles/${encodeURIComponent(scientificName)}?${params}`)
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail ?? "No pudimos cargar el perfil.");
        setProfile(payload as PlantProfile);
      })
      .catch((err: Error) => setError(err.message));
  }, [scientificName, confirmedCandidateId]);

  async function savePlant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmedCandidateId) return;
    const formData = new FormData(event.currentTarget);
    setError(null);
    setMessage(null);
    saveMutation.mutate({
        confirmed_candidate_id: confirmedCandidateId,
        nickname: optionalText(formData.get("nickname")),
        location: optionalText(formData.get("location")),
        notes: optionalText(formData.get("notes")),
    });
  }

  if (error) return <p className={styles.error}>{error}</p>;
  if (!profile) return <p className={styles.notice}>Armando perfil con evidencia RAG...</p>;
  const aliases = profile.aliases ?? [];
  const limitations = profile.limitations ?? [];
  const sections = profile.sections ?? {};
  const sources = profile.sources ?? [];
  const binomialName = profileBinomialName(profile);
  const assistantHref = buildAssistantHref({
    plant: profile.selected_alias ?? profile.common_name ?? profile.scientific_name,
    binomial: binomialName,
    scientific: profile.scientific_name,
  });

  return (
    <section className={styles.profile}>
      <article className={styles.hero}>
        <p className={styles.eyebrow}>Perfil botanico trazable</p>
        <h1>{profile.selected_alias ?? profile.common_name ?? profile.scientific_name}</h1>
        <p><em>{profile.scientific_name}</em></p>
        <p>Confianza de evidencia: {Math.round(profile.confidence * 100)}%</p>
        {aliases.length ? <p>Alias: {aliases.map((alias) => alias.name).join(", ")}</p> : null}
      </article>

      {limitations.length ? (
        <div className={styles.warning}>{limitations.map((item) => <p key={item}>{item}</p>)}</div>
      ) : null}

      <div className={styles.ctas}>
        <a href="#save">Agregar a Mi Jardin</a>
        <Link href={assistantHref}>Preguntar al asistente</Link>
        <Link href={`/reminders?plant=${encodeURIComponent(profile.scientific_name)}`}>Crear recordatorio</Link>
        <Link href={`/light-meter?plant=${encodeURIComponent(profile.scientific_name)}`}>Medir luz</Link>
      </div>

      <div className={styles.sections}>
        {Object.entries(sectionLabels).map(([key, label]) => (
          <article className={styles.card} key={key}>
            <h2>{label}</h2>
            {(sections[key] ?? []).map((text) => <p key={text}>{text}</p>)}
          </article>
        ))}
      </div>

      <article id="save" className={styles.card}>
        <h2>Guardar en Mi Jardin</h2>
        {confirmedCandidateId ? (
          <form className={styles.form} onSubmit={savePlant}>
            <input name="nickname" placeholder="Nombre personalizado" />
            <input name="location" placeholder="Ubicacion en casa" />
            <textarea name="notes" placeholder="Notas propias" />
            <button type="submit" disabled={saveMutation.isPending}>{saveMutation.isPending ? "Guardando..." : "Guardar planta confirmada"}</button>
          </form>
        ) : (
          <p>Para guardar esta planta, confirmala primero desde Identificar.</p>
        )}
        {message ? <p className={styles.notice}>{message}</p> : null}
      </article>

      <article className={styles.card}>
        <h2>Fuentes</h2>
        {sources.length ? (
          <ul>
            {sources.map((source) => (
              <li key={source.url}>
                <a href={source.url} target="_blank" rel="noreferrer">{source.title || source.domain}</a>
                <span> confianza {Math.round(source.confidence * 100)}%</span>
              </li>
            ))}
          </ul>
        ) : (
          <p>No hay fuentes suficientes todavia; el perfil muestra limitaciones explicitas.</p>
        )}
      </article>
    </section>
  );
}

function profileBinomialName(profile: PlantProfile) {
  return (profile as PlantProfile & { binomial_name?: string | null }).binomial_name ?? null;
}

function buildAssistantHref(values: { plant?: string | null; binomial?: string | null; scientific?: string | null }) {
  const params = Object.entries(values)
    .filter((entry): entry is [string, string] => typeof entry[1] === "string" && entry[1].length > 0)
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join("&");
  return `/assistant${params ? `?${params}` : ""}`;
}
