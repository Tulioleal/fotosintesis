import { readdir, readFile, stat } from "node:fs/promises";
import { join, resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  signOut: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/home",
}));

vi.mock("next-auth/react", () => ({
  signOut: mocks.signOut,
}));

vi.mock("@/lib/server/backend-session", () => ({}));

import { AppShell } from "./AppShell";
import PrivateLayout from "../../app/(private)/layout";

const projectRoot = process.cwd();
const privatePagesRoot = resolve(
  projectRoot,
  "src/app/(private)",
);

async function collectPrivatePageFiles(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectPrivatePageFiles(fullPath)));
      continue;
    }
    if (entry.isFile() && entry.name === "page.tsx") {
      files.push(fullPath);
    }
  }
  return files;
}

describe("AppShell (private route chrome)", () => {
  beforeEach(() => {
    mocks.signOut.mockReset();
  });

  it("renders the desktop top bar with brand, primary navigation, and account affordance", () => {
    render(
      <AppShell>
        <p>private content</p>
      </AppShell>,
    );

    expect(
      screen.getByRole("link", { name: "Fotosíntesis" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", {
        name: "Navegación principal de escritorio",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cerrar sesión" }),
    ).toBeInTheDocument();
  });

  it("renders the mobile bottom navigation and the page canvas for child content", () => {
    render(
      <AppShell>
        <p>private content</p>
      </AppShell>,
    );

    expect(
      screen.getByRole("navigation", { name: "Navegación principal" }),
    ).toBeInTheDocument();
    expect(screen.getByText("private content")).toBeInTheDocument();
  });

  it("exposes stable accessible names for the primary private sections", () => {
    render(
      <AppShell>
        <p>private content</p>
      </AppShell>,
    );

    for (const label of [
      "Home",
      "Identificar",
      "Mi Jardín",
      "Luz",
      "Recordatorios",
      "Asistente",
    ]) {
      expect(
        screen.getAllByRole("link", { name: label }).length,
      ).toBeGreaterThan(0);
    }
  });

  it("marks the active private section with aria-current on the navigation link", () => {
    render(
      <AppShell>
        <p>private content</p>
      </AppShell>,
    );

    const activeLinks = screen
      .getAllByRole("link", { name: "Home" })
      .filter((link) => link.getAttribute("aria-current") === "page");
    expect(activeLinks.length).toBeGreaterThan(0);
  });

  it("renders the private layout as a thin wrapper around AppShell", () => {
    render(
      <PrivateLayout>
        <p>route body</p>
      </PrivateLayout>,
    );

    expect(
      screen.getByRole("link", { name: "Fotosíntesis" }),
    ).toBeInTheDocument();
    expect(screen.getByText("route body")).toBeInTheDocument();
  });

  it("applies the full-bleed canvas variant when the fullBleed prop is set", () => {
    const { container } = render(
      <AppShell fullBleed>
        <p>full bleed body</p>
      </AppShell>,
    );

    const main = container.querySelector("main");
    expect(main).not.toBeNull();
    const className = main?.className ?? "";
    expect(className).toMatch(/canvasFullBleed/);
    expect(screen.getByText("full bleed body")).toBeInTheDocument();
  });

  it("does not apply the full-bleed canvas variant by default", () => {
    const { container } = render(
      <AppShell>
        <p>default body</p>
      </AppShell>,
    );

    const main = container.querySelector("main");
    expect(main).not.toBeNull();
    const className = main?.className ?? "";
    expect(className).not.toMatch(/canvasFullBleed/);
  });

  it("does not double-wrap private pages with AppShell (no manual shell in page modules)", async () => {
    const rootInfo = await stat(privatePagesRoot);
    expect(rootInfo.isDirectory()).toBe(true);

    const pageFiles = await collectPrivatePageFiles(privatePagesRoot);
    expect(pageFiles.length).toBeGreaterThan(0);

    const offenders: string[] = [];
    for (const file of pageFiles) {
      const source = await readFile(file, "utf8");
      const hasShellImport =
        /from\s+["'][^"']*components\/layout\/AppShell["']/.test(source);
      const hasShellUsage = /<AppShell\b/.test(source);
      if (hasShellImport || hasShellUsage) {
        offenders.push(file);
      }
    }

    expect(
      offenders,
      `Private page modules must not import or wrap with AppShell; the (private) layout owns the shell. Offending files:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });
});
