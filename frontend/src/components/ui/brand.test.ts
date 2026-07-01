import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("Fotosíntesis brand naming", () => {
  it("uses the accented product name in the app root metadata", async () => {
    const layout = await readFile(
      resolve(root, "src/app/layout.tsx"),
      "utf8",
    );
    expect(layout).toMatch(/title:\s*"Fotosíntesis"/);
  });

  it("uses the accented product name in the public landing page eyebrow", async () => {
    const home = await readFile(
      resolve(root, "src/app/page.tsx"),
      "utf8",
    );
    expect(home).toMatch(/eyebrow="Fotosíntesis"/);
  });

  it("uses the accented product name in the auth shell eyebrow", async () => {
    const shell = await readFile(
      resolve(root, "src/components/auth/AuthShell.tsx"),
      "utf8",
    );
    expect(shell).toMatch(/Fotosíntesis/);
    expect(shell).not.toMatch(/Fotosíntesis AI/);
    expect(shell).not.toMatch(/Fotosintesis AI/);
  });

  it("does not ship the PlantCare placeholder in frontend implementation paths", async () => {
    const files = [
      "src/app/layout.tsx",
      "src/app/page.tsx",
      "src/components/auth/AuthShell.tsx",
      "src/components/ui/PlaceholderPage.tsx",
    ];
    const sources = await Promise.all(
      files.map((file) => readFile(resolve(root, file), "utf8")),
    );
    sources.forEach((source, index) => {
      expect(
        source,
        `unexpected PlantCare placeholder in ${files[index]}`,
      ).not.toMatch(/PlantCare/);
    });
  });
});
