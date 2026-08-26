import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { enrichmentActivityResponseSchema } from "@/lib/api/generated-contracts";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

// Owner-scoped responses must never be stored by any cache layer, and
// backend error bodies are never forwarded: only a bounded, app-owned
// detail string travels with the preserved status code.
const privateHeaders = {
  "Cache-Control": "private, no-store",
  Pragma: "no-cache",
};

function safeErrorDetail(status: number): string {
  if (status === 401) return "Unauthorized";
  if (status === 422) return "Invalid activity request";
  return "Unable to load enrichment activity";
}

export async function GET(request: Request) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) {
    return NextResponse.json(
      { detail: "Unauthorized" },
      { status: 401, headers: privateHeaders },
    );
  }

  const { searchParams } = new URL(request.url);
  // Forward supplied values as-is and let the backend contract decide: a
  // malformed limit or cursor must surface the backend's 422, never be
  // silently converted into a successful first-page request.
  const forwardParams = new URLSearchParams();
  for (const name of ["limit", "cursor"] as const) {
    const value = searchParams.get(name);
    if (value !== null) {
      forwardParams.set(name, value);
    }
  }
  const query = forwardParams.toString();

  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/jobs/enrichment-activity${query ? `?${query}` : ""}`,
      { headers: authHeaders, cache: "no-store" },
    );
  } catch {
    // Unreachable backend: sanitized status, no provider diagnostics.
    return NextResponse.json(
      { detail: "Unable to load enrichment activity" },
      { status: 502, headers: privateHeaders },
    );
  }
  const payload: unknown = await response.json().catch(() => null);

  if (response.ok) {
    const parsed = enrichmentActivityResponseSchema.safeParse(payload);

    if (!parsed.success) {
      return NextResponse.json(
        { detail: "Invalid backend response" },
        { status: 502, headers: privateHeaders },
      );
    }

    return NextResponse.json(parsed.data, {
      status: response.status,
      headers: privateHeaders,
    });
  }

  return NextResponse.json(
    { detail: safeErrorDetail(response.status) },
    { status: response.status, headers: privateHeaders },
  );
}
