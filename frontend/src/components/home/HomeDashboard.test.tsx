import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HomeDashboard } from "./HomeDashboard";

const homeSummary = {
  user: { id: "1", name: "Tuli", email: "t@example.com", email_verified: false },
  empty_state: true,
  access: [
    { key: "identify", label: "Identificar planta", href: "/identify", status: "placeholder" },
    { key: "garden", label: "Mi Jardín", href: "/garden", status: "placeholder" },
  ],
};

const mocks = vi.hoisted(() => ({
  getHomeSummary: vi.fn(),
  useSession: vi.fn(),
}));

vi.mock("next-auth/react", () => ({
  useSession: mocks.useSession,
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    getHomeSummary: mocks.getHomeSummary,
  },
}));

function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: {
              gcTime: 0,
            },
          },
        })
      }
    >
      {children}
    </QueryClientProvider>
  );
}

describe("HomeDashboard", () => {
  beforeEach(() => {
    mocks.getHomeSummary.mockReset();
    mocks.getHomeSummary.mockResolvedValue(homeSummary);
    mocks.useSession.mockReset();
    mocks.useSession.mockReturnValue({
      status: "authenticated",
      data: { user: { id: "1", name: "Tuli", email: "t@example.com" } },
    });
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

  it("renders the Home loading skeleton while session data loads", () => {
    mocks.useSession.mockReturnValue({ status: "loading", data: null });

    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(screen.getByLabelText("Cargando Home")).toBeInTheDocument();
    expect(mocks.getHomeSummary).not.toHaveBeenCalled();
  });

  it("renders a Home error state with a retry action", async () => {
    mocks.getHomeSummary.mockRejectedValue(new Error("Home failed"));

    render(<HomeDashboard />, { wrapper: Wrapper });

    expect(
      await screen.findByRole(
        "heading",
        { name: "No pudimos actualizar tu Home" },
        { timeout: 3_000 },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("La base de la app sigue disponible. Intentá cargar los datos nuevamente.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeEnabled();
  });

  it("retries the Home summary request when retry is clicked", async () => {
    mocks.getHomeSummary.mockRejectedValue(new Error("Home failed"));

    render(<HomeDashboard />, { wrapper: Wrapper });

    const retry = await screen.findByRole(
      "button",
      { name: "Reintentar" },
      { timeout: 3_000 },
    );
    const callsBeforeRetry = mocks.getHomeSummary.mock.calls.length;

    fireEvent.click(retry);

    await waitFor(() => {
      expect(mocks.getHomeSummary.mock.calls.length).toBeGreaterThan(callsBeforeRetry);
    });
  });
});
