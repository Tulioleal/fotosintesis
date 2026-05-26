import { getToken } from "@auth/core/jwt";
import { API_BASE_URL } from "@/lib/api/config";


type BackendAuthHeaders = {
  Accept: string;
  Authorization?: string;
  Cookie?: string;
};

const BACKEND_SESSION_COOKIE = "fotosintesis_session=";

function authSecret() {
  return process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET;
}

export async function resolveBackendAuthHeaders(request: Request): Promise<BackendAuthHeaders | null> {
  const cookie = request.headers.get("cookie") ?? "";
  if (cookie.includes(BACKEND_SESSION_COOKIE)) {
    return { Accept: "application/json", Cookie: cookie };
  }

  const secret = authSecret();
  if (!secret) return null;

  const token = await getToken({
    req: request,
    secret,
    secureCookie: process.env.NODE_ENV === "production",
  });
  const credential = typeof token?.backendCredential === "string" ? token.backendCredential : "";
  if (!credential) return null;

  return { Accept: "application/json", Authorization: `Bearer ${credential}` };
}

export async function validateBackendSession(request: Request): Promise<boolean> {
  const headers = await resolveBackendAuthHeaders(request);
  if (!headers) return false;

  const response = await fetch(`${API_BASE_URL}/auth/session`, {
    headers,
    cache: "no-store",
  });

  return response.ok;
}
