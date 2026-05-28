import type { components } from "@/lib/generated/openapi";
import type { operations } from "@/lib/generated/openapi";
import { API_BASE_URL } from "./config";

export type PublicAuthUser = components["schemas"]["PublicAuthUser"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type RegisterResponse = components["schemas"]["RegisterResponse"];
export type RecoveryRequest = components["schemas"]["RecoveryRequest"];
export type RecoveryResponse = components["schemas"]["RecoveryResponse"];
export type HomeSummaryResponse = components["schemas"]["HomeSummaryResponse"];
export type GardenPlant = operations["get_garden_plant_garden__garden_id__get"]["responses"][200]["content"]["application/json"];
export type GardenPlantCreate = operations["save_garden_plant_garden_post"]["requestBody"]["content"]["application/json"];
export type GardenDeleteResponse = operations["delete_garden_plant_garden__garden_id__delete"]["responses"][200]["content"]["application/json"];
export type GardenPlantList = operations["list_garden_plants_garden_get"]["responses"][200]["content"]["application/json"];
export type AssistantSource = {
  title?: string | null;
  url: string;
  domain?: string | null;
  confidence?: number | null;
};
export type AssistantChatRequest = {
  message: string;
  conversation_id?: string | null;
  plant?: string | null;
};
export type AssistantChatResponse = {
  conversation_id: string;
  message: { role: string; content: string; created_at?: string | null };
  sources: AssistantSource[];
  requires_confirmation: boolean;
  tool_failures: string[];
};

type ErrorPayload = {
  detail?: string;
};

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

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

async function frontendRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init.headers,
    },
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = typeof (payload as ErrorPayload | null)?.detail === "string" ? (payload as ErrorPayload).detail : null;
    throw new ApiClientError(detail ?? `Request failed with status ${response.status}`, response.status);
  }

  return payload as T;
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
  listGardenPlants(search = "") {
    const params = new URLSearchParams();
    if (search) params.set("q", search);
    const query = params.toString();
    return frontendRequest<GardenPlantList>(`/api/garden${query ? `?${query}` : ""}`);
  },
  getGardenPlant(gardenId: string) {
    return frontendRequest<GardenPlant>(`/api/garden/${encodeURIComponent(gardenId)}`);
  },
  saveGardenPlant(body: GardenPlantCreate) {
    return frontendRequest<GardenPlant>("/api/garden", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
  deleteGardenPlant(gardenId: string, confirmReminders = false) {
    return frontendRequest<GardenDeleteResponse>(
      `/api/garden/${encodeURIComponent(gardenId)}?confirm_reminders=${confirmReminders}`,
      { method: "DELETE" },
    );
  },
  sendAssistantMessage(body: AssistantChatRequest) {
    return frontendRequest<AssistantChatResponse>("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
};
