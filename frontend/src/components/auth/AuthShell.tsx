import type { ReactNode } from "react";
import styles from "./AuthShell.module.scss";

export function AuthShell({
  title,
  description,
  children,
}: Readonly<{ title: string; description: string; children: ReactNode }>) {
  return (
    <main className={styles.screen}>
      <section className={styles.card}>
        <p className={styles.eyebrow}>Fotosíntesis AI</p>
        <h1>{title}</h1>
        <p className={styles.description}>{description}</p>
        {children}
      </section>
    </main>
  );
}

export { styles as authStyles };
