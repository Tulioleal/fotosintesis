import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { AUTHENTICATION_ERROR, createBrowserSession, createJwtToken } from "../auth";

const boundaryMocks = vi.hoisted(() => {
  class MockAuthError extends Error {}
  return {
    CredentialsSignin: class extends MockAuthError {
      code = "credentials";
    },
  };
});

vi.mock("next-auth", () => ({
  default: () => ({ handlers: {}, signIn: () => {}, signOut: () => {}, auth: () => {} }),
  CredentialsSignin: boundaryMocks.CredentialsSignin,
}));

vi.mock("next-auth/providers/credentials", () => ({
  default: (options: unknown) => options,
}));

const root = process.cwd();

describe("browser-visible auth session boundary", () => {
  it("does not expose backend bearer credentials in session data or client components", async () => {
    const files = await Promise.all([
      readFile(resolve(root, "auth.ts"), "utf8"),
      readFile(resolve(root, "types/next-auth.d.ts"), "utf8"),
      readFile(resolve(root, "src/components/home/HomeDashboard.tsx"), "utf8"),
      readFile(resolve(root, "src/components/layout/LogoutButton.tsx"), "utf8"),
    ]);
    const browserVisibleCode = files.join("\n");

    expect(browserVisibleCode).not.toContain("backendSessionToken");
    expect(browserVisibleCode).not.toContain("Authorization: `Bearer");
    expect(browserVisibleCode).not.toContain("sessionToken =");
    expect(browserVisibleCode).not.toContain("backendCredential?:");
  });

  it("does not put the backend credential into the browser-readable session callback output", () => {
    const session = createBrowserSession(
      {
        user: { id: "", email_verified: false, name: "Sentinel Name", email: "sentinel@example.com" },
        expires: "2099-01-01T00:00:00.000Z",
      },
      {
        sub: "sentinel-sub",
        backendCredential: "sentinel-server-only-credential",
        sessionExpiresAt: "2099-01-01T00:00:00.000Z",
        email_verified: true,
      },
    );

    const serialized = JSON.stringify(session);
    expect(session.user.id).toBe("sentinel-sub");
    expect(session.user.email_verified).toBe(true);
    expect(serialized).not.toContain("backendCredential");
    expect(serialized).not.toContain("sentinel-server-only-credential");
    expect(serialized).not.toContain("sessionExpiresAt");
  });

  it("projects a browser session that strips forbidden input fields at both levels", () => {
    const session = createBrowserSession(
      {
        expires: "2099-01-01T00:00:00.000Z",
        backendCredential: "sentinel-top-level",
        sessionExpiresAt: "sentinel-expiration",
        user: {
          id: "orig-id",
          email_verified: false,
          name: "Sentinel Name",
          email: "sentinel@example.com",
          image: null,
          backendCredential: "sentinel-user-level",
          sessionExpiresAt: "sentinel-user-expiration",
        },
      } as never,
      {
        sub: "sentinel-sub",
        backendCredential: "sentinel-server-only-credential",
        sessionExpiresAt: "2099-01-01T00:00:00.000Z",
        email_verified: true,
      },
    );

    const serialized = JSON.stringify(session);
    expect(session.user.id).toBe("sentinel-sub");
    expect(session.user.name).toBe("Sentinel Name");
    expect(session.user.email).toBe("sentinel@example.com");
    expect(session.user.email_verified).toBe(true);
    expect(session.expires).toBe("2099-01-01T00:00:00.000Z");
    expect(serialized).not.toContain("backendCredential");
    expect(serialized).not.toContain("sessionExpiresAt");
    expect(serialized).not.toContain("sentinel-top-level");
    expect(serialized).not.toContain("sentinel-user-level");
    expect(serialized).not.toContain("sentinel-expiration");
    expect(serialized).not.toContain("sentinel-user-expiration");
    expect(serialized).not.toContain("orig-id");
  });

  it("uses a generic value-free application-owned callback error", () => {
    let thrown: unknown;
    try {
      createJwtToken({ sub: "sentinel-sub" }, { id: "", name: "", email: "sentinel@example.com" });
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(Error);
    expect((thrown as Error).message).toBe(AUTHENTICATION_ERROR);
    expect((thrown as Error).message).not.toContain("sentinel");
    expect((thrown as Error).message).not.toContain("credential");
    expect((thrown as Error).message).not.toContain("token");
  });
});
