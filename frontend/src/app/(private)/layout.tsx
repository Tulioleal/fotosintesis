"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";

const BOUNDED_ROUTES = new Set(["/assistant"]);

export default function PrivateLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  return (
    <AppShell fullBleed={BOUNDED_ROUTES.has(pathname)}>{children}</AppShell>
  );
}
