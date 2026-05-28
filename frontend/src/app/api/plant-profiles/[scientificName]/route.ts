import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

type RouteContext = {
  params: Promise<{ scientificName: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { scientificName } = await context.params;
  const searchParams = new URL(request.url).searchParams;
  const response = await fetch(
    `${API_BASE_URL}/plant-profiles/${encodeURIComponent(scientificName)}?${searchParams}`,
    { headers: authHeaders, cache: "no-store" },
  );
  const payload = await response.json().catch(() => ({ detail: "Unable to load plant profile" }));
  return NextResponse.json(payload, { status: response.status });
}
