import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { confirmationResponseSchema } from "@/lib/api/generated-contracts";
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
    `${API_BASE_URL}/identifications/${encodeURIComponent(identificationId)}/candidates/${encodeURIComponent(candidateId)}/confirm`,
    {
      method: "POST",
      headers: authHeaders,
      cache: "no-store",
    },
  );

  const payload: unknown = await response.json().catch(() => null);

  if (response.ok) {
    const parsed = confirmationResponseSchema.safeParse(payload);

    if (!parsed.success) {
      return NextResponse.json(
        { detail: "Invalid backend response" },
        { status: 502 },
      );
    }

    return NextResponse.json(parsed.data, {
      status: response.status,
    });
  }

  return NextResponse.json(
    typeof payload === "object" && payload !== null ? payload : { detail: "Unable to confirm candidate" },
    { status: response.status },
  );
}
