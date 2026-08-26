import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { buildInternalAuthHeaders, deriveSourceIdentity } from "@/lib/server/source-identity";

export async function POST(request: Request) {
  const source = deriveSourceIdentity(request);
  const response = await fetch(`${API_BASE_URL}/auth/recovery/confirm`, {
    method: "POST",
    headers: buildInternalAuthHeaders(source),
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Unable to reset password" }));
  const next = NextResponse.json(payload, { status: response.status });
  const retryAfter = response.headers.get("retry-after");
  if (retryAfter) {
    next.headers.set("retry-after", retryAfter);
  }
  return next;
}
