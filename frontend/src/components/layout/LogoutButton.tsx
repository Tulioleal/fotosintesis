"use client";

import { signOut } from "next-auth/react";
import styles from "./AppShell.module.scss";

export function LogoutButton() {
  async function logout() {
    await fetch("/api/auth/backend-logout", { method: "POST" }).catch(() => undefined);
    await signOut({ callbackUrl: "/login" });
  }

  return (
    <button className={styles.logout} onClick={logout}>
      Cerrar sesión
    </button>
  );
}
