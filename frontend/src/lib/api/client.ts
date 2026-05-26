import type { components } from "@/lib/generated/openapi";
import { API_BASE_URL } from "./config";

export type PublicAuthUser = components["schemas"]["PublicAuthUser"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type RegisterResponse = components["schemas"]["RegisterResponse"];
export type RecoveryRequest = components["schemas"]["RecoveryRequest"];
export type RecoveryResponse = components["schemas"]["RecoveryResponse"];
export type HomeSummaryResponse = components["schemas"]["HomeSummaryResponse"];

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`Backend request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  register: (body: RegisterRequest) =>
    request<RegisterResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  requestRecovery: (body: RecoveryRequest) =>
    request<RecoveryResponse>("/auth/recovery/request", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  async getHomeSummary() {
    const response = await fetch("/api/home/summary", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(`Home summary request failed with status ${response.status}`);
    }
    return response.json() as Promise<HomeSummaryResponse>;
  },
};
