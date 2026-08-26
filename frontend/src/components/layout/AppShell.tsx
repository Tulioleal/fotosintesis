import type { ReactNode } from "react";
import { BottomNavigation } from "./BottomNavigation";
import { EnrichmentActivityAnnouncer } from "../enrichment/EnrichmentActivityAnnouncer";
import { EnrichmentActivityProvider } from "../enrichment/EnrichmentActivityProvider";
import { LogoutButton } from "./LogoutButton";
import styles from "./AppShell.module.scss";

export function AppShell({
  children,
  fullBleed = false,
}: Readonly<{ children: ReactNode; fullBleed?: boolean }>) {
  const shellClass = fullBleed
    ? `${styles.shell} ${styles.shellFixed}`
    : styles.shell;
  const canvasClass = fullBleed
    ? `${styles.canvas} ${styles.canvasFullBleed} ${styles.canvasBounded}`
    : styles.canvas;
  return (
    <EnrichmentActivityProvider>
      <div className={shellClass}>
        <header className={styles.topBar}>
          <div className={styles.topBarInner}>
            <a className={styles.brand} href="/home">
              Fotosíntesis
            </a>
            <nav
              className={styles.topNav}
              aria-label="Navegación principal de escritorio"
            >
              <BottomNavigation variant="top" />
            </nav>
            <div className={styles.topActions}>
              <LogoutButton />
            </div>
          </div>
        </header>

        <EnrichmentActivityAnnouncer />

        <main className={canvasClass}>{children}</main>

        <nav
          className={styles.bottomNav}
          aria-label="Navegación principal"
        >
          <BottomNavigation variant="bottom" />
        </nav>

        <footer className={styles.footer}>
          <div className={styles.footerInner}>
            <span className={styles.footerBrand}>Fotosíntesis</span>
            <span className={styles.footerCopy}>
              © {new Date().getFullYear()} Fotosíntesis. Todos los derechos reservados.
            </span>
          </div>
        </footer>
      </div>
    </EnrichmentActivityProvider>
  );
}
