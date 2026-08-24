import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { EnrichmentActivityProvider } from "@/components/enrichment/EnrichmentActivityProvider";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      mutations: {
        retry: false,
      },
      queries: {
        gcTime: 0,
        retry: false,
      },
    },
  });
}

export function renderWithQueryClient(ui: ReactElement, client?: QueryClient) {
  const queryClient = client ?? createTestQueryClient();

  function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return { ...render(ui, { wrapper: Wrapper }), queryClient };
}

/**
 * Renders a standalone activity consumer inside the shared app-shell
 * activity observer so it can consume the provider context exactly as it
 * does inside AppShell.
 */
export function renderWithActivityProvider(
  ui: ReactElement,
  client?: QueryClient,
) {
  return renderWithQueryClient(
    <EnrichmentActivityProvider>{ui}</EnrichmentActivityProvider>,
    client,
  );
}
