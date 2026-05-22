"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { apiClient } from "@/lib/generated/client";
import styles from "./HomeDashboard.module.scss";

export function HomeDashboard() {
  const session = useSession();
  const token = session.data?.backendSessionToken ?? "";
  const summary = useQuery({
    queryKey: ["home-summary"],
    enabled: Boolean(token),
    queryFn: () => apiClient.getHomeSummary(token),
    retry: 1,
  });

  if (session.status === "loading" || summary.isLoading) {
    return <div className={styles.skeleton} aria-label="Cargando Home" />;
  }

  if (summary.isError || !summary.data) {
    return (
      <section className={styles.error}>
        <h1>No pudimos actualizar tu Home</h1>
        <p>
          La base de la app sigue disponible. Intentá cargar los datos
          nuevamente.
        </p>
        <button onClick={() => summary.refetch()}>Reintentar</button>
      </section>
    );
  }

  const access = summary.data.access;

  return (
    <>
      <header className={styles.header}>
        <p className={styles.eyebrow}>Hola, {summary.data.user.name}</p>
        <h1>¿Qué necesita tu planta hoy?</h1>
        <Link className={styles.search} href="/search">
          Buscar plantas, cuidados o síntomas
        </Link>
      </header>

      {summary.data.empty_state && (
        <section className={styles.empty}>
          <strong>Tu jardín está listo para empezar.</strong>
          <p>
            Identificá una planta o buscá una especie para crear tu primera
            ficha.
          </p>
        </section>
      )}

      <Link className={styles.primaryCta} href="/identify">
        <span>Acción principal</span>
        <strong>Identificar planta</strong>
        <span>Subí o tomá una foto cuando el flujo esté disponible.</span>
      </Link>

      <section className={styles.grid} aria-label="Accesos principales">
        {access
          .filter((item) => item.key !== "identify")
          .map((item) => (
            <Link className={styles.card} href={item.href} key={item.key}>
              <strong>{item.label}</strong>
              <span>Próximamente</span>
            </Link>
          ))}
      </section>
    </>
  );
}
