import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { HomeDashboard } from "./HomeDashboard";

vi.mock("next-auth/react", () => ({
  useSession: () => ({ status: "authenticated", data: { backendSessionToken: "token" } }),
}));

vi.mock("@/lib/generated/client", () => ({
  apiClient: {
    getHomeSummary: async () => ({
      user: { id: "1", name: "Tuli", email: "t@example.com", email_verified: false },
      empty_state: true,
      access: [
        { key: "identify", label: "Identificar planta", href: "/identify", status: "placeholder" },
        { key: "garden", label: "Mi Jardín", href: "/garden", status: "placeholder" },
      ],
    }),
  },
}));

function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
}

describe("HomeDashboard", () => {
  it("renders authenticated Home empty state", async () => {
    render(<HomeDashboard />, { wrapper: Wrapper });
    expect(await screen.findByText("Tu jardín está listo para empezar.")).toBeInTheDocument();
  });
});
