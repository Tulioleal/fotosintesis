import { z } from "zod";

/**
 * Bounded authentication rate-limit contract shared by the Auth.js boundary
 * and the authentication forms.
 *
 * Only a closed error code and a clamped integer retry delay are ever
 * surfaced; backend details, limiter keys, and account state are never
 * exposed to the browser.
 *
 * The bounded error-code mechanism: the Auth.js ``code`` is a closed string
 * plus an optional clamped whole-second delay appended with a colon, e.g.
 * ``credentials_rate_limited:37``. The delay is clamped to
 * ``AUTH_RETRY_AFTER_MAX_SECONDS`` so the code is bounded and parseable
 * without leaking server details.
 */

export const AUTH_RATE_LIMITED_CODE = "credentials_rate_limited";
export const AUTH_UNAVAILABLE_CODE = "temporarily_unavailable";
export const AUTH_RETRY_AFTER_MAX_SECONDS = 3600;
export const AUTH_DEFAULT_UNAVAILABLE_SECONDS = 60;

const retryAfterSchema = z.coerce.number().int().nonnegative();
const retryCodeSchema = z
  .string()
  .regex(new RegExp(`^${AUTH_RATE_LIMITED_CODE}:\\d+$`));
const unavailableCodeSchema = z
  .string()
  .regex(new RegExp(`^${AUTH_UNAVAILABLE_CODE}:\\d+$`));

export function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const parsed = retryAfterSchema.safeParse(value);
  if (!parsed.success) return null;
  return parsed.data;
}

export function clampRetryAfter(value: number, max: number): number {
  return Math.max(0, Math.min(value, max));
}

export function encodeRetryCode(seconds: number): string {
  const clamped = Math.max(1, clampRetryAfter(seconds, AUTH_RETRY_AFTER_MAX_SECONDS));
  return `${AUTH_RATE_LIMITED_CODE}:${clamped}`;
}

export function parseRetryCode(code: string | null | undefined): number | null {
  if (!code) return null;
  if (code === AUTH_RATE_LIMITED_CODE) {
    // Legacy bare code without an explicit delay; treat as an unknown window.
    return null;
  }
  if (!retryCodeSchema.safeParse(code).success) return null;
  const seconds = Number.parseInt(code.slice(AUTH_RATE_LIMITED_CODE.length + 1), 10);
  if (!Number.isInteger(seconds) || seconds < 1) return null;
  return clampRetryAfter(seconds, AUTH_RETRY_AFTER_MAX_SECONDS);
}

/**
 * The unavailable code is a closed string plus a clamped whole-second delay,
 * mirroring the rate-limited mechanism so the form can briefly block
 * resubmission while displaying generic temporary-unavailability feedback.
 */
export function encodeUnavailableCode(seconds: number): string {
  const clamped = Math.max(1, clampRetryAfter(seconds, AUTH_RETRY_AFTER_MAX_SECONDS));
  return `${AUTH_UNAVAILABLE_CODE}:${clamped}`;
}

export function parseUnavailableCode(code: string | null | undefined): number | null {
  if (!code) return null;
  if (code === AUTH_UNAVAILABLE_CODE) {
    // Legacy bare code without an explicit delay; treat as an unknown window.
    return null;
  }
  if (!unavailableCodeSchema.safeParse(code).success) return null;
  const seconds = Number.parseInt(code.slice(AUTH_UNAVAILABLE_CODE.length + 1), 10);
  if (!Number.isInteger(seconds) || seconds < 1) return null;
  return clampRetryAfter(seconds, AUTH_RETRY_AFTER_MAX_SECONDS);
}

/** Strict exact classification: unrelated strings are never limiter codes. */
export function isRateLimitedCode(code: string | null | undefined): boolean {
  return parseRetryCode(code) !== null;
}

export function isUnavailableCode(code: string | null | undefined): boolean {
  return parseUnavailableCode(code) !== null;
}
