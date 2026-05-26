import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";


type RouteContext = {
  params: Promise<{
    identificationId: string;
    candidateId: string;
  }>;
};

export async function POST(request: Request, context: RouteContext) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { identificationId, candidateId } = await context.params;
  const response = await fetch(
    `${API_BASE_URL}/identifications/${identificationId}/candidates/${candidateId}/confirm`,
    {
      method: "POST",
      headers: authHeaders,
      cache: "no-store",
    },
  );

  const payload = await response.json().catch(() => ({ detail: "Unable to confirm candidate" }));
  return NextResponse.json(payload, { status: response.status });
}
