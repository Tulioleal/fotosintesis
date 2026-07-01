import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";

export default function AssistantLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return <AppShell fullBleed>{children}</AppShell>;
}
