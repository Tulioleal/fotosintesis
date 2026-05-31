import { NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api/config";


export async function POST(request: Request) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Unable to register" }));
  return NextResponse.json(payload, { status: response.status });
}
