import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import styles from "./PlaceholderPage.module.scss";

export function PlaceholderPage({
  title,
  description = "Este acceso ya está protegido y navegable, pero la lógica real queda fuera de este slice.",
}: Readonly<{ title: string; description?: string }>) {
  return (
    <AppShell>
      <section className={styles.placeholder}>
        <div className={styles.panel}>
          <p>Próximamente</p>
          <h1>{title}</h1>
          <p>{description}</p>
          <Link href="/home">Volver al Home</Link>
        </div>
      </section>
    </AppShell>
  );
}
