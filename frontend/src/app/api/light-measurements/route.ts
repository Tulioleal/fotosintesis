import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

export async function POST(request: Request) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const response = await fetch(`${API_BASE_URL}/light-measurements`, {
    method: "POST",
    headers: { ...authHeaders, "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Unable to save light measurement" }));
  return NextResponse.json(payload, { status: response.status });
}
