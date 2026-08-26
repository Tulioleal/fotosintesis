import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { handlers } from "../../../../../auth";
import { API_BASE_URL } from "@/lib/api/config";
import {
  AUTH_DEFAULT_UNAVAILABLE_SECONDS,
  encodeRetryCode,
  encodeUnavailableCode,
  parseRetryAfter,
} from "@/lib/server/auth-rate-limit";
import { buildInternalAuthHeaders, deriveSourceIdentity } from "@/lib/server/source-identity";

/**
 * Relevant unauthenticated Auth.js POST actions that are source-aware abuse
 * surfaces: the credentials sign-in callback and CSRF token issuance. Session
 * reads (GET), authenticated session updates, and sign-out are never limited.
 */
const RELEVANT_AUTHJS_POST_ACTIONS = new Set(["callback", "csrf", "signin"]);

function actionFromRequest(request: Request): string | null {
  const segments = new URL(request.url).pathname.split("/").filter(Boolean);
  // /api/auth/<action>[/...]
  const actionIndex = segments.indexOf("auth");
  if (actionIndex === -1 || actionIndex + 1 >= segments.length) return null;
  return segments[actionIndex + 1];
}

function authErrorResponse(request: Request, status: number, code: string): NextResponse {
  // The Auth.js client parses `error` and `code` from the `url` field of the
  // POST response body. Emit the same contract Auth.js uses on a rejected
  // callback so the browser surfaces the bounded error code.
  const origin = new URL(request.url).origin;
  const url = new URL(`${origin}/api/auth/signin`);
  url.searchParams.set("error", "CredentialsSignin");
  url.searchParams.set("code", code);
  return NextResponse.json({ url: url.toString() }, { status });
}

export async function GET(request: NextRequest) {
  return handlers.GET(request);
}

export async function POST(request: NextRequest) {
  const action = actionFromRequest(request);
  if (action !== null && RELEVANT_AUTHJS_POST_ACTIONS.has(action)) {
    const source = deriveSourceIdentity(request);
    const response = await fetch(`${API_BASE_URL}/auth/admit/authjs_post`, {
      method: "POST",
      headers: buildInternalAuthHeaders(source),
      body: null,
      cache: "no-store",
    });
    if (response.status === 429) {
      const retryAfter = parseRetryAfter(response.headers.get("retry-after")) ?? 1;
      return authErrorResponse(request, 429, encodeRetryCode(retryAfter));
    }
    if (response.status === 503) {
      // Storage failure: a distinct bounded unavailable code so the form shows
      // generic temporary-unavailability feedback instead of a rate limit.
      const retryAfter =
        parseRetryAfter(response.headers.get("retry-after")) ??
        AUTH_DEFAULT_UNAVAILABLE_SECONDS;
      return authErrorResponse(request, 503, encodeUnavailableCode(retryAfter));
    }
    if (!response.ok) {
      // Unexpected admission failure: classify as unavailable, never as a
      // rate limit.
      return authErrorResponse(
        request,
        response.status,
        encodeUnavailableCode(AUTH_DEFAULT_UNAVAILABLE_SECONDS),
      );
    }
  }
  return handlers.POST(request);
}
