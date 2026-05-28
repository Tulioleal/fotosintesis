"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { apiClient } from "@/lib/api/client";
import styles from "./PlantProfileView.module.scss";

export function GardenList() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const garden = useQuery({
    queryKey: ["garden", "list", submittedQuery],
    queryFn: () => apiClient.listGardenPlants(submittedQuery),
  });
  const plants = garden.isError ? [] : (garden.data ?? []);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmittedQuery(query);
  }

  return (
    <section className={styles.profile}>
      <div className={styles.hero}>
        <p className={styles.eyebrow}>Mi Jardin</p>
        <h1>Tus plantas guardadas.</h1>
        <p>Busca por nombre comun, alias, nombre cientifico o apodo.</p>
      </div>
      <form className={styles.search} onSubmit={search}>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar planta" />
        <button type="submit">Buscar</button>
      </form>
      {garden.isError ? <p className={styles.error}>{garden.error.message || "No pudimos cargar Mi Jardin."}</p> : null}
      {garden.isLoading ? <p className={styles.notice}>Cargando plantas...</p> : null}
      {!garden.isLoading && !garden.isError && !plants.length ? (
        <article className={styles.card}>
          <h2>Tu jardin esta vacio</h2>
          <p>Confirma una candidata validada desde Identificar y guardala desde su perfil.</p>
          <Link href="/identify">Identificar planta</Link>
        </article>
      ) : null}
      <div className={styles.sections}>
        {plants.map((plant) => (
          <article className={styles.card} key={plant.id}>
            <p className={styles.eyebrow}>{plant.location ?? "Sin ubicacion"}</p>
            <h2>{plant.nickname ?? plant.profile.selected_alias ?? plant.profile.scientific_name}</h2>
            <p><em>{plant.profile.scientific_name}</em></p>
            <p>{plant.notes ?? "Sin notas personalizadas."}</p>
            <Link href={`/garden/${plant.id}`}>Ver detalle</Link>
          </article>
        ))}
      </div>
    </section>
  );
}
