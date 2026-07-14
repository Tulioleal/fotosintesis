import { beforeEach, describe, expect, it, vi } from "vitest";
import { resolveBackendAuthHeaders } from "./backend-session";

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(),
}));

vi.mock("@auth/core/jwt", () => ({
  getToken: mocks.getToken,
}));

function requestWithUrl(url: string): Request {
  return new Request(url, { headers: { cookie: "" } });
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
    mocks.getToken.mockResolvedValueOnce({ backendCredential: "tok" });

    await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(mocks.getToken).toHaveBeenCalledWith(
      expect.objectContaining({ secureCookie: false }),
    );
  });

  it("uses secure cookies when AUTH_URL is https", async () => {
    setEnv("AUTH_URL", "https://frontend.test");
    mocks.getToken.mockResolvedValueOnce({ backendCredential: "tok" });

    await resolveBackendAuthHeaders(requestWithUrl("https://frontend.test/home"));

    expect(mocks.getToken).toHaveBeenCalledWith(
      expect.objectContaining({ secureCookie: true }),
    );
  });

  it("falls back to NODE_ENV when AUTH_URL is not set", async () => {
    setEnv("NODE_ENV", "production");
    mocks.getToken.mockResolvedValueOnce({ backendCredential: "tok" });

    await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(mocks.getToken).toHaveBeenCalledWith(
      expect.objectContaining({ secureCookie: true }),
    );
  });

  it("returns null when no credential in token", async () => {
    mocks.getToken.mockResolvedValueOnce({});

    const result = await resolveBackendAuthHeaders(requestWithUrl("http://frontend.test/home"));

    expect(result).toBeNull();
  });
});
