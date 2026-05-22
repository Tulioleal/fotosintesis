import type { ReactNode } from "react";
import { BottomNavigation } from "./BottomNavigation";
import { LogoutButton } from "./LogoutButton";
import styles from "./AppShell.module.scss";

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <main className={styles.shell}>
      <section className={styles.content}>
        <LogoutButton />
        {children}
      </section>
      <BottomNavigation />
    </main>
  );
}
