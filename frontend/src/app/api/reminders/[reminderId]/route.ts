import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

type RouteContext = {
  params: Promise<{ reminderId: string }>;
};

export async function PATCH(request: Request, context: RouteContext) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { reminderId } = await context.params;
  const response = await fetch(`${API_BASE_URL}/reminders/${reminderId}`, {
    method: "PATCH",
    headers: { ...authHeaders, "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Unable to update reminder" }));
  return NextResponse.json(payload, { status: response.status });
}

export async function DELETE(request: Request, context: RouteContext) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { reminderId } = await context.params;
  const response = await fetch(`${API_BASE_URL}/reminders/${reminderId}`, {
    method: "DELETE",
    headers: authHeaders,
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Unable to delete reminder" }));
  return NextResponse.json(payload, { status: response.status });
}
