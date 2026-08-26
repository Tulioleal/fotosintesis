import { beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

function clearLimiterEnv() {
  for (const key of [
    "AUTH_LIMITER_HMAC_SECRET",
    "AUTH_LIMITER_ASSERTION_SECRET",
    "AUTH_LIMITER_HMAC_KEY_VERSION",
    "AUTH_LIMITER_TRUSTED_FORWARDED_HOPS",
  ]) {
    delete process.env[key];
  }
}

describe("POST /api/auth/recovery/confirm", () => {
  beforeEach(() => {
    clearLimiterEnv();
  });

  it("routes recovery confirmation through the frontend boundary", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json({ status: "ok" }, { status: 200 }),
      );

    const response = await POST(
      new Request("http://frontend.test/api/auth/recovery/confirm", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token: "a".repeat(32), password: "newpassword123" }),
      }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/recovery/confirm",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
      }),
    );
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init?.body as string) ?? "{}");
    expect(body.token).toBe("a".repeat(32));
    expect(body.password).toBe("newpassword123");
    fetchMock.mockRestore();
  });

  it("preserves the neutral body and bounded retry metadata on 429", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 429,
          headers: { "retry-after": "45", "content-type": "application/json" },
        }),
      );

    const response = await POST(
      new Request("http://frontend.test/api/auth/recovery/confirm", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token: "b".repeat(32), password: "newpassword123" }),
      }),
    );

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("45");
    fetchMock.mockRestore();
  });
});
