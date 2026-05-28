"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiClientError, apiClient } from "@/lib/api/client";
import styles from "./PlantProfileView.module.scss";

export function GardenDetail({ gardenId }: Readonly<{ gardenId: string }>) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [requiresReminderConfirm, setRequiresReminderConfirm] = useState(false);
  const garden = useQuery({
    queryKey: ["garden", "detail", gardenId],
    queryFn: () => apiClient.getGardenPlant(gardenId),
  });
  const plant = garden.data;

  const deletePlant = useMutation({
    mutationFn: (confirmReminders: boolean) => apiClient.deleteGardenPlant(gardenId, confirmReminders),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["garden", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["garden", "detail", gardenId] }),
      ]);
      router.push("/garden");
    },
    onError: (err: Error) => {
      if (err instanceof ApiClientError && err.status === 409) {
        setRequiresReminderConfirm(true);
        setError(err.message);
        return;
      }
      setError(err.message || "No pudimos eliminar la planta.");
    },
  });

  async function remove(confirmReminders = false) {
    setError(null);
    deletePlant.mutate(confirmReminders);
  }

  if (garden.isError && !plant) return <p className={styles.error}>{garden.error.message || "No pudimos cargar la planta."}</p>;
  if (garden.isLoading || !plant) return <p className={styles.notice}>Cargando detalle...</p>;

  const profilePath = `/profiles/${encodeURIComponent(plant.profile.scientific_name)}`;
  const profileHref = plant.confirmed_candidate_id
    ? `${profilePath}?candidateId=${encodeURIComponent(plant.confirmed_candidate_id)}`
    : profilePath;

  return (
    <section className={styles.profile}>
      <article className={styles.hero}>
        <p className={styles.eyebrow}>Detalle de Mi Jardin</p>
        <h1>{plant.nickname ?? plant.profile.selected_alias ?? plant.profile.scientific_name}</h1>
        <p><em>{plant.profile.scientific_name}</em></p>
        <p>{plant.location ?? "Sin ubicacion"}</p>
      </article>
      <article className={styles.card}>
        <h2>Notas</h2>
        <p>{plant.notes ?? "Todavia no agregaste notas personalizadas."}</p>
        <p>Recordatorios activos: {plant.active_reminders}</p>
      </article>
      <div className={styles.ctas}>
        <Link href={profileHref}>Ver perfil</Link>
        <Link href={`/assistant?plant=${encodeURIComponent(plant.profile.scientific_name)}`}>Preguntar al asistente</Link>
        <Link href={`/reminders?plant=${encodeURIComponent(plant.profile.scientific_name)}`}>Crear recordatorio</Link>
        <Link href={`/light-meter?plant=${encodeURIComponent(plant.profile.scientific_name)}`}>Medir luz</Link>
      </div>
      {error ? <p className={styles.error}>{error}</p> : null}
      {requiresReminderConfirm ? (
        <button className={styles.danger} type="button" onClick={() => remove(true)}>
          {deletePlant.isPending ? "Eliminando..." : "Confirmar eliminacion y afectar recordatorios"}
        </button>
      ) : (
        <button className={styles.danger} type="button" onClick={() => remove(false)}>
          {deletePlant.isPending ? "Eliminando..." : "Eliminar de Mi Jardin"}
        </button>
      )}
    </section>
  );
}
