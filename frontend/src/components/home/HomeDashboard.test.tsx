import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HomeDashboard } from "./HomeDashboard";

const mocks = vi.hoisted(() => ({
  getHomeSummary: vi.fn(async () => ({
    user: { id: "1", name: "Tuli", email: "t@example.com", email_verified: false },
    empty_state: true,
    access: [
      { key: "identify", label: "Identificar planta", href: "/identify", status: "placeholder" },
      { key: "garden", label: "Mi Jardín", href: "/garden", status: "placeholder" },
    ],
  })),
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({
    status: "authenticated",
    data: { user: { id: "1", name: "Tuli", email: "t@example.com" } },
  }),
}));

vi.mock("@/lib/generated/client", () => ({
  apiClient: {
    getHomeSummary: mocks.getHomeSummary,
  },
}));

function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
}

describe("HomeDashboard", () => {
  beforeEach(() => {
    mocks.getHomeSummary.mockClear();
  });

  it("renders authenticated Home empty state", async () => {
    render(<HomeDashboard />, { wrapper: Wrapper });
    expect(await screen.findByText("Tu jardín está listo para empezar.")).toBeInTheDocument();
  });

  it("loads Home through the frontend boundary without a bearer token", async () => {
    render(<HomeDashboard />, { wrapper: Wrapper });
    expect(await screen.findByText("Tu jardín está listo para empezar.")).toBeInTheDocument();
    expect(mocks.getHomeSummary).toHaveBeenCalledWith();
  });
});
