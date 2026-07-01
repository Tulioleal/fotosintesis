"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./AppShell.module.scss";

const items = [
  { href: "/home", label: "Home" },
  { href: "/identify", label: "Identificar" },
  { href: "/garden", label: "Mi Jardín" },
  { href: "/light-meter", label: "Luz" },
  { href: "/reminders", label: "Recordatorios" },
  { href: "/assistant", label: "Asistente" },
];

type BottomNavigationProps = {
  variant: "top" | "bottom";
};

export function BottomNavigation({ variant }: BottomNavigationProps) {
  const pathname = usePathname();
  return (
    <ul
      className={
        variant === "top" ? styles.topNavList : styles.bottomNavList
      }
    >
      {items.map((item) => {
        const isActive =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <li
            key={item.href}
            className={
              variant === "top" ? styles.topNavItem : styles.bottomNavItem
            }
          >
            <Link
              href={item.href}
              data-active={isActive}
              aria-current={isActive ? "page" : undefined}
              className={
                variant === "top" ? styles.topNavLink : styles.bottomNavLink
              }
            >
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
