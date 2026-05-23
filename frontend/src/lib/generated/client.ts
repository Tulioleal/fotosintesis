export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type PublicAuthUser = {
  id: string;
  name: string;
  email: string;
  email_verified: boolean;
};

export type HomeAccessItem = {
  key: string;
  label: string;
  href: string;
  status: "placeholder";
};

export type HomeSummaryResponse = {
  user: PublicAuthUser;
  empty_state: boolean;
  access: HomeAccessItem[];
};

export type RegisterRequest = {
  name: string;
  email: string;
  password: string;
};

export type RecoveryRequest = {
  email: string;
};

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
    request<{ user: PublicAuthUser }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  requestRecovery: (body: RecoveryRequest) =>
    request<{ status: string; message: string }>("/auth/recovery/request", {
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
