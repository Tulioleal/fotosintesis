import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

type RouteContext = {
  params: Promise<{ gardenId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { gardenId } = await context.params;
  const response = await fetch(`${API_BASE_URL}/garden/${gardenId}`, {
    headers: authHeaders,
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Unable to load garden plant" }));
  return NextResponse.json(payload, { status: response.status });
}

export async function DELETE(request: Request, context: RouteContext) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { gardenId } = await context.params;
  const url = new URL(request.url);
  const response = await fetch(
    `${API_BASE_URL}/garden/${gardenId}?confirm_reminders=${url.searchParams.get("confirm_reminders") === "true"}`,
    { method: "DELETE", headers: authHeaders, cache: "no-store" },
  );
  const payload = await response.json().catch(() => ({ detail: "Unable to delete garden plant" }));
  return NextResponse.json(payload, { status: response.status });
}
