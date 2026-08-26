import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

export async function POST(request: Request) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const upstream = await fetch(`${API_BASE_URL}/assistant/chat/stream`, {
    method: "POST",
    headers: { ...authHeaders, "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });

  if (!upstream.ok && upstream.headers.get("content-type")?.includes("application/json")) {
    const payload = await upstream.json().catch(() => ({ detail: "Stream unavailable" }));
    return NextResponse.json(payload, { status: upstream.status });
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "text/event-stream",
      "cache-control": "private, no-store",
      // Disable intermediary buffering so stage events arrive immediately.
      "x-accel-buffering": "no",
    },
  });
}
