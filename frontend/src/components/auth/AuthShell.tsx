import type { ReactNode } from "react";
import styles from "./AuthShell.module.scss";

export interface AuthShellProps {
  title: string;
  description?: string;
  eyebrow?: string;
  supporting?: ReactNode;
  footerNote?: ReactNode;
  children: ReactNode;
}

export function AuthShell({
  title,
  description,
  eyebrow = "Fotosíntesis",
  supporting,
  footerNote,
  children,
}: Readonly<AuthShellProps>) {
  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#auth-main">
        Saltar al contenido
      </a>
      <header className={styles.brandBar}>
        <a className={styles.brand} href="/welcome">
          {eyebrow}
        </a>
      </header>

      <main id="auth-main" className={styles.canvas} tabIndex={-1}>
        <section className={styles.card}>
          <p className={styles.eyebrow}>{eyebrow}</p>
          <h1 className={styles.title}>{title}</h1>
          {description ? <p className={styles.description}>{description}</p> : null}
          <div className={styles.body}>{children}</div>
          {supporting ? <div className={styles.supporting}>{supporting}</div> : null}
        </section>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <span className={styles.footerBrand}>{eyebrow}</span>
          <span className={styles.footerNote}>
            {footerNote ?? `© ${new Date().getFullYear()} ${eyebrow}. Todos los derechos reservados.`}
          </span>
        </div>
      </footer>
    </div>
  );
}

export { styles as authStyles };
