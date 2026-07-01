import type { components } from "@/lib/generated/openapi";
import type { operations } from "@/lib/generated/openapi";
import { API_BASE_URL } from "./config";

export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type RegisterResponse = components["schemas"]["RegisterResponse"];
export type RecoveryRequest = components["schemas"]["RecoveryRequest"];
export type RecoveryResponse = components["schemas"]["RecoveryResponse"];
export type HomeSummaryResponse = components["schemas"]["HomeSummaryResponse"];
export type GardenPlantCard = components["schemas"]["GardenPlantCard"];
export type GardenPlant = operations["get_garden_plant_garden__garden_id__get"]["responses"][200]["content"]["application/json"];
export type GardenPlantCreate = operations["save_garden_plant_garden_post"]["requestBody"]["content"]["application/json"];
export type GardenDeleteResponse = operations["delete_garden_plant_garden__garden_id__delete"]["responses"][200]["content"]["application/json"];
export type GardenPlantList = operations["list_garden_plants_garden_get"]["responses"][200]["content"]["application/json"];
export type Reminder = components["schemas"]["ReminderDto"];
export type ReminderCreate = components["schemas"]["ReminderCreate"];
export type ReminderUpdate = components["schemas"]["ReminderUpdate"];
export type ReminderDeleteResponse = components["schemas"]["ReminderDeleteResponse"];
export type LightClassification = components["schemas"]["LightClassification"];
export type MeasurementReliability = components["schemas"]["MeasurementReliability"];
export type MeasurementSource = components["schemas"]["MeasurementSource"];
export type LightMeasurementCreate = components["schemas"]["LightMeasurementCreate"];
export type LightMeasurement = components["schemas"]["LightMeasurementDto"];
export type AssistantSource = components["schemas"]["AssistantSource"];
export type AssistantMessage = components["schemas"]["AssistantMessage"];
export type AssistantReminderSuggestion = components["schemas"]["AssistantReminderSuggestion"];
export type AssistantChatRequest = components["schemas"]["AssistantChatRequest"];
export type AssistantChatResponse = components["schemas"]["AssistantChatResponse"];
export type AssistantRetryableError = components["schemas"]["AssistantRetryableError"];

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
    frontendRequest<RegisterResponse>("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
    return frontendRequest<AssistantChatResponse | AssistantRetryableError>("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
  listReminders(gardenPlantId?: string) {
    const params = new URLSearchParams();
    if (gardenPlantId) params.set("garden_plant_id", gardenPlantId);
    const query = params.toString();
    return frontendRequest<Reminder[]>(`/api/reminders${query ? `?${query}` : ""}`);
  },
  createReminder(body: ReminderCreate) {
    return frontendRequest<Reminder>("/api/reminders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
  updateReminder(reminderId: string, body: ReminderUpdate) {
    return frontendRequest<Reminder>(`/api/reminders/${encodeURIComponent(reminderId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
  completeReminder(reminderId: string) {
    return frontendRequest<Reminder>(`/api/reminders/${encodeURIComponent(reminderId)}/complete`, {
      method: "POST",
    });
  },
  deleteReminder(reminderId: string) {
    return frontendRequest<ReminderDeleteResponse>(`/api/reminders/${encodeURIComponent(reminderId)}`, {
      method: "DELETE",
    });
  },
  createLightMeasurement(body: LightMeasurementCreate) {
    return frontendRequest<LightMeasurement>("/api/light-measurements", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
  listLightMeasurements(gardenPlantId: string, limit = 5) {
    const params = new URLSearchParams();
    params.set("garden_plant_id", gardenPlantId);
    params.set("limit", String(limit));
    return frontendRequest<LightMeasurement[]>(`/api/light-measurements?${params.toString()}`);
  },
};
