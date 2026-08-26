import { getToken } from "next-auth/jwt";
import { API_BASE_URL } from "@/lib/api/config";
import { authTokenSchema } from "./auth-token";


type BackendAuthHeaders = {
  Accept: string;
  Authorization?: string;
  Cookie?: string;
};

const BACKEND_SESSION_COOKIE = "fotosintesis_session=";

function authSecret() {
  return process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET;
}

function usesSecureCookies(): boolean {
  const authUrl = process.env.AUTH_URL ?? process.env.NEXTAUTH_URL;
  if (authUrl) {
    return new URL(authUrl).protocol === "https:";
  }
  return process.env.NODE_ENV === "production";
}

export async function resolveBackendAuthHeaders(request: Request): Promise<BackendAuthHeaders | null> {
  const secret = authSecret();
  if (!secret) return null;

  let secureCookie: boolean;
  try {
    secureCookie = usesSecureCookies();
  } catch {
    return null;
  }

  const cookie = request.headers.get("cookie") ?? "";
  if (cookie.includes(BACKEND_SESSION_COOKIE)) {
    return { Accept: "application/json", Cookie: cookie };
  }

  try {
    const token = await getToken({
      req: request,
      secret,
      secureCookie,
    });
    const validated = authTokenSchema.safeParse(token);
    if (!validated.success) return null;

    return { Accept: "application/json", Authorization: `Bearer ${validated.data.backendCredential}` };
  } catch {
    return null;
  }
}

export async function validateBackendSession(request: Request): Promise<boolean> {
  const headers = await resolveBackendAuthHeaders(request);
  if (!headers) return false;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/session`, {
      headers,
      cache: "no-store",
    });

    return response.ok;
  } catch {
    return false;
  }
}
