import { describe, expect, it } from "vitest";
import {
  buildInternalAuthHeaders,
  deriveSourceIdentity,
  extractTrustedClientAddress,
  hasInternalLimiterHeaders,
  trustedForwardedHops,
  verifySourceAssertion,
} from "./source-identity";

function requestWithForwardedFor(value: string | null): Request {
  const headers = new Headers();
  if (value !== null) headers.set("x-forwarded-for", value);
  return new Request("http://frontend.test/api/auth/register", { headers });
}

const GKE_ENV = {
  AUTH_LIMITER_HMAC_SECRET: "sentinel-hmac-secret",
  AUTH_LIMITER_ASSERTION_SECRET: "sentinel-assertion-secret",
  AUTH_LIMITER_HMAC_KEY_VERSION: "1",
  AUTH_LIMITER_TRUSTED_FORWARDED_HOPS: "2",
} as unknown as NodeJS.ProcessEnv;

describe("trustedForwardedHops", () => {
  it("accepts the documented GKE external ALB trust chain of 2 hops", () => {
    expect(trustedForwardedHops(GKE_ENV)).toBe(2);
  });

  it("applies the conservative zero default when no hops are configured", () => {
    expect(trustedForwardedHops({} as NodeJS.ProcessEnv)).toBe(0);
  });

  it("rejects unknown or non-positive hops conservatively", () => {
    expect(
      trustedForwardedHops({ AUTH_LIMITER_TRUSTED_FORWARDED_HOPS: "first" } as never),
    ).toBe(0);
    expect(
      trustedForwardedHops({ AUTH_LIMITER_TRUSTED_FORWARDED_HOPS: "0" } as never),
    ).toBe(0);
  });
});

describe("extractTrustedClientAddress", () => {
  it("uses the first of the platform-appended trailing entries as the client", () => {
    // GKE external ALB appends <client-ip>,<load-balancer-ip>.
    const request = requestWithForwardedFor("198.51.100.7, 198.51.100.9");
    expect(extractTrustedClientAddress(request, GKE_ENV)).toBe("198.51.100.7");
  });

  it("never selects the load-balancer address (final entry) as the client", () => {
    const request = requestWithForwardedFor("203.0.113.55, 198.51.100.9");
    expect(extractTrustedClientAddress(request, GKE_ENV)).toBe("203.0.113.55");
  });

  it("ignores client-supplied earlier entries and never uses them as identity", () => {
    // An attacker prepends their own value; the platform chain is unchanged.
    const request = requestWithForwardedFor("1.2.3.4, 203.0.113.55, 198.51.100.9");
    expect(extractTrustedClientAddress(request, GKE_ENV)).toBe("203.0.113.55");
  });

  it("ignores multiple attacker-prepended entries before the platform chain", () => {
    const request = requestWithForwardedFor("6.6.6.6, 7.7.7.7, 203.0.113.55, 198.51.100.9");
    expect(extractTrustedClientAddress(request, GKE_ENV)).toBe("203.0.113.55");
  });

  it("returns null when the trust chain is not configured", () => {
    const request = requestWithForwardedFor("203.0.113.55, 198.51.100.9");
    expect(extractTrustedClientAddress(request, {} as NodeJS.ProcessEnv)).toBeNull();
  });

  it("returns null when no forwarding header is present", () => {
    expect(extractTrustedClientAddress(requestWithForwardedFor(null), GKE_ENV)).toBeNull();
  });

  it("returns null when the chain has fewer entries than the trusted hops", () => {
    expect(extractTrustedClientAddress(requestWithForwardedFor("198.51.100.9"), GKE_ENV)).toBeNull();
  });

  it("returns null when the platform chain contains a non-IP entry", () => {
    const request = requestWithForwardedFor("203.0.113.55, spoofed.example.com");
    expect(extractTrustedClientAddress(request, GKE_ENV)).toBeNull();
  });

  it("returns null when an attacker supplies a malformed chain", () => {
    expect(extractTrustedClientAddress(requestWithForwardedFor(" , "), GKE_ENV)).toBeNull();
  });

  it("fails conservatively when only a single trailing hop is configured", () => {
    const env = { ...GKE_ENV, AUTH_LIMITER_TRUSTED_FORWARDED_HOPS: "1" };
    // A single trusted trailing entry is the load-balancer address, which must
    // never be used as the client; the chain is rejected conservatively.
    const request = requestWithForwardedFor("203.0.113.55, 198.51.100.9");
    expect(extractTrustedClientAddress(request, env)).toBeNull();
  });
});

describe("deriveSourceIdentity", () => {
  it("produces a trusted opaque source key and a verifiable assertion", () => {
    const request = requestWithForwardedFor("203.0.113.55, 198.51.100.9");
    const identity = deriveSourceIdentity(request, GKE_ENV);
    expect(identity.kind).toBe("trusted");
    if (identity.kind !== "trusted") return;

    expect(identity.sourceKey).toMatch(/^[0-9a-f]{64}$/);
    expect(verifySourceAssertion(GKE_ENV.AUTH_LIMITER_ASSERTION_SECRET!, identity.sourceKey, identity.assertion)).toBe(true);
  });

  it("never forwards the raw source address as the source key", () => {
    const request = requestWithForwardedFor("203.0.113.55, 198.51.100.9");
    const identity = deriveSourceIdentity(request, GKE_ENV);
    if (identity.kind !== "trusted") return;
    expect(identity.sourceKey).not.toContain("203.0.113.55");
  });

  it("produces different source keys for different client addresses", () => {
    const env = GKE_ENV;
    const first = deriveSourceIdentity(
      requestWithForwardedFor("203.0.113.55, 198.51.100.9"),
      env,
    );
    const second = deriveSourceIdentity(
      requestWithForwardedFor("203.0.113.56, 198.51.100.9"),
      env,
    );
    expect(first.kind).toBe("trusted");
    expect(second.kind).toBe("trusted");
    if (first.kind !== "trusted" || second.kind !== "trusted") return;
    expect(first.sourceKey).not.toBe(second.sourceKey);
  });

  it("returns missing when secrets are not configured", () => {
    const request = requestWithForwardedFor("203.0.113.55, 198.51.100.9");
    const env = {
      AUTH_LIMITER_TRUSTED_FORWARDED_HOPS: "2",
    } as unknown as NodeJS.ProcessEnv;
    expect(deriveSourceIdentity(request, env).kind).toBe("missing");
  });

  it("returns missing when the trust chain is absent", () => {
    const request = requestWithForwardedFor("203.0.113.55, 198.51.100.9");
    expect(deriveSourceIdentity(request, {} as NodeJS.ProcessEnv).kind).toBe("missing");
  });
});

describe("internal limiter header handling", () => {
  it("builds an allowlist of content type plus the generated source headers only", () => {
    const source = deriveSourceIdentity(
      requestWithForwardedFor("203.0.113.55, 198.51.100.9"),
      GKE_ENV,
    );
    const headers = buildInternalAuthHeaders(source);
    expect(headers.get("content-type")).toBe("application/json");
    expect(headers.get("x-fotosintesis-source-key")).toMatch(/^[0-9a-f]{64}$/);
    expect(headers.get("x-fotosintesis-source-assertion")).toMatch(/^[0-9a-f]{64}$/);
  });

  it("never forwards cookies, forwarding headers, or forged internal headers", () => {
    const source = deriveSourceIdentity(
      requestWithForwardedFor("203.0.113.55, 198.51.100.9"),
      GKE_ENV,
    );
    const headers = buildInternalAuthHeaders(source);
    expect(headers.has("cookie")).toBe(false);
    expect(headers.has("x-forwarded-for")).toBe(false);
    expect(headers.has("forwarded")).toBe(false);
    expect(headers.has("x-fotosintesis-source-key")).toBe(true);
    expect(headers.get("x-fotosintesis-source-key")).not.toContain("198.51.100.9");
  });

  it("detects client-supplied internal limiter headers", () => {
    const headers = new Headers({ "x-fotosintesis-source-key": "attacker-value" });
    expect(hasInternalLimiterHeaders(headers)).toBe(true);
    expect(hasInternalLimiterHeaders(new Headers())).toBe(false);
  });
});
