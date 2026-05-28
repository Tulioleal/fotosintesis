"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./AppShell.module.scss";

const items = [
  { href: "/home", label: "Home" },
  { href: "/identify", label: "Identificar" },
  { href: "/garden", label: "Mi Jardín" },
  { href: "/reminders", label: "Recordatorios" },
  { href: "/assistant", label: "Asistente" },
];

export function BottomNavigation() {
  const pathname = usePathname();
  return (
    <nav className={styles.nav} aria-label="Navegación principal">
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          data-active={pathname === item.href || pathname.startsWith(`${item.href}/`)}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
