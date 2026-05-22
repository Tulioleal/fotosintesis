export type ID = string;

export type UserDto = {
  id: ID;
  email: string;
  name: string;
  region?: string | null;
  createdAt: string;
};

export type PlantDto = {
  id: ID;
  scientificName: string;
  commonName?: string | null;
  gbifKey?: string | null;
  family?: string | null;
  genus?: string | null;
  species?: string | null;
};

export type GardenPlantDto = {
  id: ID;
  userId: ID;
  plantId: ID;
  nickname?: string | null;
  imageUrl?: string | null;
  createdAt: string;
};

export type ReminderDto = {
  id: ID;
  gardenPlantId: ID;
  action: string;
  dueAt: string;
  recurrence?: string | null;
  status: "pending" | "completed" | "cancelled";
  suggestionJustification?: string | null;
};

export type LightMeasurementDto = {
  id: ID;
  userId: ID;
  gardenPlantId?: ID | null;
  classification: "baja" | "media" | "alta" | "directa";
  lux?: number | null;
  reliability: "high" | "medium" | "low";
  measuredAt: string;
};

export type ConversationDto = {
  id: ID;
  userId: ID;
  title?: string | null;
  createdAt: string;
};

export type ConversationMessageDto = {
  id: ID;
  conversationId: ID;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  createdAt: string;
};

export type EvaluationRunDto = {
  id: ID;
  status: "pending" | "running" | "completed" | "failed";
  startedAt: string;
  completedAt?: string | null;
};
