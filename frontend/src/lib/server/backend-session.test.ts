import { beforeEach, describe, expect, it, vi } from "vitest";
import { resolveBackendAuthHeaders } from "./backend-session";

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

vi.mock("next-auth/jwt", () => ({
  getToken: mocks.getToken,
}));

const VALID_TOKEN = {
  sub: "user-1",
  backendCredential: "valid-server-only-credential",
  sessionExpiresAt: "2099-01-01T00:00:00.000Z",
  email_verified: true,
};

function requestWithUrl(url: string): Request {
  return new Request(url, { headers: { cookie: "" } });
}

function requestWithCookie(url: string, cookie: string): Request {
  return new Request(url, { headers: { cookie } });
}

function setEnv(key: string, value: string | undefined) {
  if (value === undefined) {
    delete (process.env as Record<string, string | undefined>)[key];
  } else {
    (process.env as Record<string, string>)[key] = value;
  }
}

describe("resolveBackendAuthHeaders", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setEnv("AUTH_SECRET", "test-secret");
    setEnv("AUTH_URL", undefined);
    setEnv("NEXTAUTH_URL", undefined);
    setEnv("NODE_ENV", undefined);
    mocks.getToken.mockReset();
  });

  it("uses non-secure cookies when AUTH_URL is http", async () => {
    setEnv("AUTH_URL", "http://frontend.test");
    mocks.getToken.mockResolvedValueOnce(VALID_TOKEN);

    await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(mocks.getToken).toHaveBeenCalledWith(
      expect.objectContaining({ secureCookie: false }),
    );
  });

  it("uses secure cookies when AUTH_URL is https", async () => {
    setEnv("AUTH_URL", "https://frontend.test");
    mocks.getToken.mockResolvedValueOnce(VALID_TOKEN);

    await resolveBackendAuthHeaders(requestWithUrl("https://frontend.test/home"));

    expect(mocks.getToken).toHaveBeenCalledWith(
      expect.objectContaining({ secureCookie: true }),
    );
  });

  it("falls back to NODE_ENV when AUTH_URL is not set", async () => {
    setEnv("NODE_ENV", "production");
    mocks.getToken.mockResolvedValueOnce(VALID_TOKEN);

    await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(mocks.getToken).toHaveBeenCalledWith(
      expect.objectContaining({ secureCookie: true }),
    );
  });

  it("forwards the concrete validated server-only credential as a bearer token", async () => {
    mocks.getToken.mockResolvedValueOnce(VALID_TOKEN);

    const result = await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(result).toEqual({
      Accept: "application/json",
      Authorization: "Bearer valid-server-only-credential",
    });
  });

  it("returns null when a backend cookie exists but no secret is configured", async () => {
    setEnv("AUTH_SECRET", undefined);
    setEnv("NEXTAUTH_SECRET", undefined);
    const cookie = "fotosintesis_session=sentinel-cookie-value";

    const result = await resolveBackendAuthHeaders(requestWithCookie("http://frontend.test/home", cookie));

    expect(result).toBeNull();
    expect(mocks.getToken).not.toHaveBeenCalled();
  });

  it("preserves the backend cookie path when a valid secret exists without decoding the JWT", async () => {
    const cookie = "fotosintesis_session=sentinel-cookie-value; other=1";

    const result = await resolveBackendAuthHeaders(requestWithCookie("http://frontend.test/home", cookie));

    expect(result).toEqual({
      Accept: "application/json",
      Cookie: cookie,
    });
    expect(mocks.getToken).not.toHaveBeenCalled();
  });

  it("returns null for an invalid AUTH_URL without decoding the JWT", async () => {
    setEnv("AUTH_URL", "not-a-valid-url");
    mocks.getToken.mockResolvedValueOnce(VALID_TOKEN);

    const result = await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(result).toBeNull();
    expect(mocks.getToken).not.toHaveBeenCalled();
  });

  it("returns null when the decoder rejects without exposing exception text", async () => {
    mocks.getToken.mockRejectedValueOnce(new Error("sentinel-decode-exception"));

    const result = await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(result).toBeNull();
  });

  it("returns null when the decoder produces no token", async () => {
    mocks.getToken.mockResolvedValueOnce(null);

    const result = await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(result).toBeNull();
  });

  it.each([
    ["missing sub", { ...VALID_TOKEN, sub: undefined }],
    ["empty sub", { ...VALID_TOKEN, sub: "" }],
    ["non-string sub", { ...VALID_TOKEN, sub: 42 }],
    ["missing backendCredential", { ...VALID_TOKEN, backendCredential: undefined }],
    ["empty backendCredential", { ...VALID_TOKEN, backendCredential: "" }],
    ["non-string backendCredential", { ...VALID_TOKEN, backendCredential: 42 }],
    ["missing sessionExpiresAt", { ...VALID_TOKEN, sessionExpiresAt: undefined }],
    ["invalid sessionExpiresAt", { ...VALID_TOKEN, sessionExpiresAt: "not-a-date" }],
    ["missing email_verified", { ...VALID_TOKEN, email_verified: undefined }],
    ["non-Boolean email_verified", { ...VALID_TOKEN, email_verified: "yes" }],
  ])("returns null for malformed decoded token state (%s)", async (_label, malformedToken) => {
    mocks.getToken.mockResolvedValueOnce(malformedToken);

    const result = await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(result).toBeNull();
  });
});
