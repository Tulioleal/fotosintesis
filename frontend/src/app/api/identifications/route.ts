import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";


export async function POST(request: Request) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const formData = await request.formData();
  const response = await fetch(`${API_BASE_URL}/identifications`, {
    method: "POST",
    headers: authHeaders,
    body: formData,
    cache: "no-store",
  });

  const payload = await response.json().catch(() => ({ detail: "Unable to identify plant" }));
  return NextResponse.json(payload, { status: response.status });
}
