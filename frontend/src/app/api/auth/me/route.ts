import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

export async function GET(request: Request) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: authHeaders,
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Unable to load profile" }));
  return NextResponse.json(payload, { status: response.status });
}
