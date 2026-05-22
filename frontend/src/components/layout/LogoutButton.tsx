"use client";

import { signOut, useSession } from "next-auth/react";
import styles from "./AppShell.module.scss";

export function LogoutButton() {
  const session = useSession();

  async function logout() {
    if (session.data?.backendSessionToken) {
      await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/auth/logout`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.data.backendSessionToken}`,
          },
        },
      ).catch(() => undefined);
    }
    await signOut({ callbackUrl: "/login" });
  }

  return (
    <button className={styles.logout} onClick={logout}>
      Cerrar sesión
    </button>
  );
}
