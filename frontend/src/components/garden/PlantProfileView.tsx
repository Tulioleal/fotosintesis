"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
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
import { buildAssistantHref } from "@/lib/assistant";
import { ChatTextIcon, PlusCircleIcon, SunIcon } from "@phosphor-icons/react";
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

  if (error) return <Notice tone="error" role="alert">{error}</Notice>;
  if (!profile) return <Notice tone="info" role="status">Armando perfil con evidencia RAG...</Notice>;
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
  const reminderHref = `/reminders?plant=${encodeURIComponent(profile.scientific_name)}`;
  const lightMeterHref = `/light-meter?plant=${encodeURIComponent(profile.scientific_name)}`;

  return (
    <section className={styles.profile}>
      <PageHeader
        eyebrow="Perfil botanico trazable"
        heading={profile.selected_alias ?? profile.common_name ?? profile.scientific_name}
        description={profile.scientific_name}
      />

      {limitations.length ? (
        <Notice tone="warning" heading="Limitaciones de la evidencia">
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
        {Object.entries(sectionLabels).map(([key, label]) => (
          <Card key={key} variant="tonal" padding="md">
            <h2 className={styles.sectionTitle}>{label}</h2>
            {(sections[key] ?? []).map((text: string) => (
              <p key={text} className={styles.sectionCopy}>{text}</p>
            ))}
          </Card>
        ))}
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
      </Card>

      <Card variant="tonal" padding="md">
        <h2 className={styles.sectionTitle}>Fuentes</h2>
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

function profileBinomialName(profile: PlantProfile) {
  return (profile as PlantProfile & { binomial_name?: string | null }).binomial_name ?? null;
}
