import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { isIP } from "node:net";

/**
 * Trusted source identity for the authentication abuse boundary.
 *
 * Google Cloud external Application Load Balancers (the platform behind GKE
 * Ingress) append exactly two addresses to `X-Forwarded-For`, in this order:
 *
 *   X-Forwarded-For: <existing-value>,<client-ip>,<load-balancer-ip>
 *
 * The load balancer's own forwarding-rule address is the FINAL entry and is
 * never the client. Every entry before `<client-ip>,<load-balancer-ip>` is
 * supplied by the client, is NOT verified by the platform, and is never used
 * as limiter identity.
 *
 * The trusted-hop policy is therefore: take the trailing ``hops`` entries
 * appended by the trusted platform (``2`` for the external Application Load
 * Balancer), require every trailing entry to be a valid IP address, and use
 * the first of those trailing entries as the client. A malformed or missing
 * chain returns no trusted source, which the backend treats conservatively.
 *
 * Reference: https://cloud.google.com/load-balancing/docs/https
 * (External Application Load Balancer overview, X-Forwarded-For header).
 */

const LIMITER_HMAC_SECRET_ENV = "AUTH_LIMITER_HMAC_SECRET";
const LIMITER_ASSERTION_SECRET_ENV = "AUTH_LIMITER_ASSERTION_SECRET";
const LIMITER_HMAC_KEY_VERSION_ENV = "AUTH_LIMITER_HMAC_KEY_VERSION";
const TRUSTED_FORWARDED_HOPS_ENV = "AUTH_LIMITER_TRUSTED_FORWARDED_HOPS";

export const INTERNAL_SOURCE_KEY_HEADER = "x-fotosintesis-source-key";
export const INTERNAL_SOURCE_ASSERTION_HEADER = "x-fotosintesis-source-assertion";
export const INTERNAL_LIMITER_HEADERS = [
  INTERNAL_SOURCE_KEY_HEADER,
  INTERNAL_SOURCE_ASSERTION_HEADER,
];

export type SourceIdentity =
  | { kind: "missing" }
  | { kind: "trusted"; sourceKey: string; assertion: string };

export function trustedForwardedHops(env: NodeJS.ProcessEnv = process.env): number {
  const value = (env[TRUSTED_FORWARDED_HOPS_ENV] ?? "").trim();
  if (value === "") return 0;
  const parsed = Number.parseInt(value, 10);
  // Conservative default: do not trust any forwarding header unless the
  // deployment explicitly documents the GKE trust chain.
  if (!Number.isInteger(parsed) || parsed <= 0) return 0;
  return parsed;
}

export function extractTrustedClientAddress(
  request: Request,
  env: NodeJS.ProcessEnv = process.env,
): string | null {
  const hops = trustedForwardedHops(env);
  // The external Application Load Balancer always appends two entries
  // (`<client-ip>,<load-balancer-ip>`), so a single trusted trailing entry
  // would be the load-balancer address and must never be treated as a client.
  if (hops < 2) return null;

  const forwardedFor = request.headers.get("x-forwarded-for");
  if (!forwardedFor) return null;

  const entries = forwardedFor
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
  if (entries.length < hops) return null;

  // Only the trailing `hops` entries were appended by the trusted platform;
  // everything before them is client-controlled and must be ignored.
  const trustedSuffix = entries.slice(entries.length - hops);
  // A well-formed platform chain consists only of IP addresses. The load
  // balancer address is the final entry and is never selected as the client.
  if (trustedSuffix.some((entry) => isIP(entry) === 0)) return null;
  return trustedSuffix[0];
}

export function hmacSha256Hex(key: string, data: string): string {
  return createHmac("sha256", key).update(data, "utf8").digest("hex");
}

export function signSourceAssertion(secret: string, sourceKey: string): string {
  return hmacSha256Hex(secret, sourceKey);
}

export function verifySourceAssertion(secret: string, sourceKey: string, assertion: string): boolean {
  const expected = signSourceAssertion(secret, sourceKey);
  const left = Buffer.from(expected, "utf8");
  const right = Buffer.from(assertion, "utf8");
  return left.length === right.length && timingSafeEqual(left, right);
}

export function deriveSourceIdentity(
  request: Request,
  env: NodeJS.ProcessEnv = process.env,
): SourceIdentity {
  const address = extractTrustedClientAddress(request, env);
  if (!address) return { kind: "missing" };

  const hmacSecret = env[LIMITER_HMAC_SECRET_ENV];
  const assertionSecret = env[LIMITER_ASSERTION_SECRET_ENV];
  if (!hmacSecret || !assertionSecret) return { kind: "missing" };

  const version = env[LIMITER_HMAC_KEY_VERSION_ENV] ?? "1";
  // Matches the backend KeyedDigest scheme: hmac(secret, version\0dimension\0identifier)
  const sourceKey = hmacSha256Hex(
    hmacSecret,
    [version, "source", address].join("\u0000"),
  );
  const assertion = signSourceAssertion(assertionSecret, sourceKey);
  return { kind: "trusted", sourceKey, assertion };
}

export function buildInternalAuthHeaders(source: SourceIdentity): Headers {
  // Internal requests are built from an explicit allowlist: only the required
  // content type plus the generated opaque source key and assertion. Raw
  // forwarding headers, cookies, and any client-supplied internal limiter
  // headers never cross the boundary.
  const headers = new Headers({ "Content-Type": "application/json" });
  if (source.kind === "trusted") {
    headers.set(INTERNAL_SOURCE_KEY_HEADER, source.sourceKey);
    headers.set(INTERNAL_SOURCE_ASSERTION_HEADER, source.assertion);
  }
  return headers;
}

export function hasInternalLimiterHeaders(headers: Headers): boolean {
  return INTERNAL_LIMITER_HEADERS.some((name) => headers.has(name));
}

export function digestForPrivacyProbe(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}
