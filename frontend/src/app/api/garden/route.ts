import { NextResponse, type NextRequest } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

export async function GET(request: NextRequest) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const response = await fetch(`${API_BASE_URL}/garden?${request.nextUrl.searchParams}`, {
    headers: authHeaders,
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Unable to load garden" }));
  return NextResponse.json(payload, { status: response.status });
}

export async function POST(request: Request) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const response = await fetch(`${API_BASE_URL}/garden`, {
    method: "POST",
    headers: { ...authHeaders, "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Unable to save garden plant" }));
  return NextResponse.json(payload, { status: response.status });
}
