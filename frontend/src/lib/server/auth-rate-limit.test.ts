import { describe, expect, it } from "vitest";
import {
  AUTH_RATE_LIMITED_CODE,
  AUTH_RETRY_AFTER_MAX_SECONDS,
  AUTH_UNAVAILABLE_CODE,
  clampRetryAfter,
  encodeRetryCode,
  encodeUnavailableCode,
  isRateLimitedCode,
  isUnavailableCode,
  parseRetryAfter,
  parseRetryCode,
  parseUnavailableCode,
} from "./auth-rate-limit";

describe("parseRetryAfter", () => {
  it("parses a whole-second header value", () => {
    expect(parseRetryAfter("37")).toBe(37);
    expect(parseRetryAfter("1")).toBe(1);
  });

  it("parses the maximum value", () => {
    expect(parseRetryAfter(String(AUTH_RETRY_AFTER_MAX_SECONDS))).toBe(AUTH_RETRY_AFTER_MAX_SECONDS);
  });

  it("returns null for a missing header", () => {
    expect(parseRetryAfter(null)).toBeNull();
  });

  it("returns null for a malformed header", () => {
    expect(parseRetryAfter("abc")).toBeNull();
    expect(parseRetryAfter("1.5")).toBeNull();
    expect(parseRetryAfter("-3")).toBeNull();
    expect(parseRetryAfter("")).toBeNull();
  });
});

describe("clampRetryAfter", () => {
  it("preserves values inside the bound", () => {
    expect(clampRetryAfter(37, 3600)).toBe(37);
  });

  it("clamps values above the maximum", () => {
    expect(clampRetryAfter(7200, 3600)).toBe(3600);
  });

  it("never returns below zero", () => {
    expect(clampRetryAfter(-5, 3600)).toBe(0);
  });
});

describe("bounded retry error-code mechanism", () => {
  it("encodes a clamped whole-second delay into the closed code", () => {
    expect(encodeRetryCode(37)).toBe(`${AUTH_RATE_LIMITED_CODE}:37`);
    expect(encodeRetryCode(1)).toBe(`${AUTH_RATE_LIMITED_CODE}:1`);
  });

  it("clamps the encoded delay to the maximum", () => {
    expect(encodeRetryCode(7200)).toBe(
      `${AUTH_RATE_LIMITED_CODE}:${AUTH_RETRY_AFTER_MAX_SECONDS}`,
    );
  });

  it("never encodes a zero delay for an active rejection", () => {
    expect(encodeRetryCode(0)).toBe(`${AUTH_RATE_LIMITED_CODE}:1`);
  });

  it("parses the retry duration back from the code", () => {
    expect(parseRetryCode(`${AUTH_RATE_LIMITED_CODE}:37`)).toBe(37);
    expect(parseRetryCode(`${AUTH_RATE_LIMITED_CODE}:1`)).toBe(1);
    expect(parseRetryCode(`${AUTH_RATE_LIMITED_CODE}:${AUTH_RETRY_AFTER_MAX_SECONDS}`)).toBe(
      AUTH_RETRY_AFTER_MAX_SECONDS,
    );
  });

  it("clamps an over-limit code back to the maximum", () => {
    expect(parseRetryCode(`${AUTH_RATE_LIMITED_CODE}:7200`)).toBe(AUTH_RETRY_AFTER_MAX_SECONDS);
  });

  it("returns null for a missing, bare, or malformed code", () => {
    expect(parseRetryCode(null)).toBeNull();
    expect(parseRetryCode(undefined)).toBeNull();
    expect(parseRetryCode(AUTH_RATE_LIMITED_CODE)).toBeNull();
    expect(parseRetryCode(`${AUTH_RATE_LIMITED_CODE}:abc`)).toBeNull();
    expect(parseRetryCode("some-other-code")).toBeNull();
    expect(parseRetryCode(`${AUTH_RATE_LIMITED_CODE}:0`)).toBeNull();
    expect(parseRetryCode(`${AUTH_RATE_LIMITED_CODE}:-3`)).toBeNull();
  });
});

describe("bounded unavailable error-code mechanism", () => {
  it("encodes a clamped whole-second delay into the closed unavailable code", () => {
    expect(encodeUnavailableCode(37)).toBe(`${AUTH_UNAVAILABLE_CODE}:37`);
    expect(encodeUnavailableCode(1)).toBe(`${AUTH_UNAVAILABLE_CODE}:1`);
  });

  it("clamps the encoded delay to the maximum and never encodes zero", () => {
    expect(encodeUnavailableCode(7200)).toBe(
      `${AUTH_UNAVAILABLE_CODE}:${AUTH_RETRY_AFTER_MAX_SECONDS}`,
    );
    expect(encodeUnavailableCode(0)).toBe(`${AUTH_UNAVAILABLE_CODE}:1`);
  });

  it("parses the unavailable duration back from the code", () => {
    expect(parseUnavailableCode(`${AUTH_UNAVAILABLE_CODE}:37`)).toBe(37);
    expect(parseUnavailableCode(`${AUTH_UNAVAILABLE_CODE}:1`)).toBe(1);
  });

  it("returns null for a missing, bare, malformed, or unrelated code", () => {
    expect(parseUnavailableCode(null)).toBeNull();
    expect(parseUnavailableCode(undefined)).toBeNull();
    expect(parseUnavailableCode(AUTH_UNAVAILABLE_CODE)).toBeNull();
    expect(parseUnavailableCode(`${AUTH_UNAVAILABLE_CODE}:abc`)).toBeNull();
    expect(parseUnavailableCode(`${AUTH_UNAVAILABLE_CODE}:0`)).toBeNull();
    expect(parseUnavailableCode(`${AUTH_UNAVAILABLE_CODE}:-3`)).toBeNull();
    expect(parseUnavailableCode(`${AUTH_UNAVAILABLE_CODE}:7200`)).toBe(AUTH_RETRY_AFTER_MAX_SECONDS);
    expect(parseUnavailableCode("some-other-code")).toBeNull();
    expect(parseUnavailableCode(`${AUTH_RATE_LIMITED_CODE}:37`)).toBeNull();
  });
});

describe("strict code classification", () => {
  it("classifies only exact rate-limited codes as rate limited", () => {
    expect(isRateLimitedCode(`${AUTH_RATE_LIMITED_CODE}:37`)).toBe(true);
    expect(isRateLimitedCode(`${AUTH_UNAVAILABLE_CODE}:37`)).toBe(false);
    expect(isRateLimitedCode(AUTH_RATE_LIMITED_CODE)).toBe(false);
    expect(isRateLimitedCode(`${AUTH_RATE_LIMITED_CODE}:0`)).toBe(false);
    expect(isRateLimitedCode(`${AUTH_RATE_LIMITED_CODE}:evil`)).toBe(false);
    expect(isRateLimitedCode(`${AUTH_RATE_LIMITED_CODE}:37:extra`)).toBe(false);
    expect(isRateLimitedCode(`x${AUTH_RATE_LIMITED_CODE}:37`)).toBe(false);
    expect(isRateLimitedCode(null)).toBe(false);
    expect(isRateLimitedCode(undefined)).toBe(false);
  });

  it("classifies only exact unavailable codes as unavailable", () => {
    expect(isUnavailableCode(`${AUTH_UNAVAILABLE_CODE}:37`)).toBe(true);
    expect(isUnavailableCode(`${AUTH_RATE_LIMITED_CODE}:37`)).toBe(false);
    expect(isUnavailableCode(AUTH_UNAVAILABLE_CODE)).toBe(false);
    expect(isUnavailableCode(`${AUTH_UNAVAILABLE_CODE}:0`)).toBe(false);
    expect(isUnavailableCode(`${AUTH_UNAVAILABLE_CODE}:evil`)).toBe(false);
    expect(isUnavailableCode(`x${AUTH_UNAVAILABLE_CODE}:37`)).toBe(false);
    expect(isUnavailableCode(null)).toBe(false);
    expect(isUnavailableCode(undefined)).toBe(false);
  });
});
