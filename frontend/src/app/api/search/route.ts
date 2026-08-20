import { NextResponse, type NextRequest } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { searchLocalResponseSchema } from "@/lib/api/generated-contracts";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

export async function GET(request: NextRequest) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const response = await fetch(
    `${API_BASE_URL}/search?${request.nextUrl.searchParams}`,
    { headers: authHeaders, cache: "no-store" },
  );
  const payload: unknown = await response.json().catch(() => null);

  if (response.ok) {
    const parsed = searchLocalResponseSchema.safeParse(payload);
    if (!parsed.success) {
      return NextResponse.json(
        { detail: "Invalid backend response" },
        { status: 502 },
      );
    }
    return NextResponse.json(parsed.data, { status: response.status });
  }

  return NextResponse.json(
    typeof payload === "object" && payload !== null
      ? payload
      : { detail: "Unable to search local plants" },
    { status: response.status },
  );
}
