import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";


export async function GET(request: Request) {
  const headers = await resolveBackendAuthHeaders(request);
  if (!headers) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const response = await fetch(`${API_BASE_URL}/home/summary`, {
    headers,
    cache: "no-store",
  });

  if (response.status === 401) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  if (!response.ok) {
    return NextResponse.json({ detail: "Unable to load Home summary" }, { status: response.status });
  }

  return NextResponse.json(await response.json());
}
