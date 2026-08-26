"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useSession } from "next-auth/react";
import type { UseQueryResult } from "@tanstack/react-query";
import type { EnrichmentActivityResponse } from "@/lib/api/client";
import { useEnrichmentActivityQuery } from "@/lib/enrichment-activity";

type EnrichmentActivityContextValue = {
  userId: string;
  query: UseQueryResult<EnrichmentActivityResponse>;
};

const EnrichmentActivityContext =
  createContext<EnrichmentActivityContextValue | null>(null);

export function EnrichmentActivityProvider({
  children,
}: Readonly<{ children: ReactNode }>) {
  const { data: session } = useSession();
  const userId = session?.user?.id;

  // No activity request is issued until the authenticated identity exists;
  // the cache and dedup storage are scoped per user.
  const query = useEnrichmentActivityQuery(userId);

  return (
    <EnrichmentActivityContext.Provider
      value={{ userId: userId ?? "anonymous", query }}
    >
      {children}
    </EnrichmentActivityContext.Provider>
  );
}

export function useEnrichmentActivity(): EnrichmentActivityContextValue {
  const context = useContext(EnrichmentActivityContext);

  if (context === null) {
    throw new Error(
      "useEnrichmentActivity must be used within EnrichmentActivityProvider",
    );
  }

  return context;
}
