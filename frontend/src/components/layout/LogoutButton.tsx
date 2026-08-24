"use client";

import { useQueryClient } from "@tanstack/react-query";
import { signOut } from "next-auth/react";
import styles from "./AppShell.module.scss";

export function LogoutButton() {
  const queryClient = useQueryClient();

  async function logout() {
    await fetch("/api/auth/backend-logout", { method: "POST" }).catch(
      () => undefined,
    );

    // Every cached query is owner-scoped or public and refetchable, so drop
    // the whole cache before the full-page redirect. In-place account
    // switching is not a supported flow (middleware redirects unauthenticated
    // requests), so this also covers any unkeyed owner data.
    queryClient.clear();

    await signOut({ redirectTo: "/login" });
  }

  return (
    <button type="button" className={styles.logout} onClick={logout}>
      Cerrar sesión
    </button>
  );
}
