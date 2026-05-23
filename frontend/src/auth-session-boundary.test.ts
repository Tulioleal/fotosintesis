import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";


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
});
