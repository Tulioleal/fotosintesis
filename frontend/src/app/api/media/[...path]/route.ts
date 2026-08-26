import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";
import { resolveBackendAuthHeaders } from "@/lib/server/backend-session";

const ALLOWED_MEDIA_PREFIXES = ["identifications/", "garden-plants/"];

export async function GET(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const authHeaders = await resolveBackendAuthHeaders(request);
  if (!authHeaders) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { path: rawSegments } = await params;
  const segments = rawSegments.map((segment) => encodeURIComponent(segment));
  const relativePath = segments.join("/");
  if (!ALLOWED_MEDIA_PREFIXES.some((prefix) => relativePath.startsWith(prefix))) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  const response = await fetch(`${API_BASE_URL}/${relativePath}`, {
    headers: authHeaders,
    cache: "no-store",
  });

  const headers = new Headers();
  const contentType = response.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("cache-control", "private, no-store");

  return new NextResponse(response.body, {
    status: response.status,
    headers,
  });
}
