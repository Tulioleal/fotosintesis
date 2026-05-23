import { getToken } from "@auth/core/jwt";


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
