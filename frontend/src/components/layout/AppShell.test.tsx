import { readdir, readFile, stat } from "node:fs/promises";
import { join, resolve } from "node:path";
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQueryClient } from "@/test/renderWithQueryClient";

const mocks = vi.hoisted(() => ({
  signOut: vi.fn(),
  getEnrichmentActivity: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/home",
}));

import * as sessionState from "@/test/mock-session";

vi.mock("next-auth/react", () => ({
  signOut: mocks.signOut,
  useSession: () => sessionState.mockSessionState,
}));

vi.mock("@/lib/server/backend-session", () => ({}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    getEnrichmentActivity: mocks.getEnrichmentActivity,
  },
}));

import { AppShell } from "./AppShell";
import { EnrichmentActivitySummary } from "../enrichment/EnrichmentActivitySummary";
import { ACTIVITY_POLL_INTERVAL_MS } from "@/lib/enrichment-activity";
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
    mocks.getEnrichmentActivity.mockReset();
    mocks.getEnrichmentActivity.mockResolvedValue({
      items: [],
      has_more: false,
    });
  });

  it("renders the desktop top bar with brand, primary navigation, and account affordance", () => {
    renderWithQueryClient(
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
    renderWithQueryClient(
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
    renderWithQueryClient(
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
    renderWithQueryClient(
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
    renderWithQueryClient(
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
    const { container } = renderWithQueryClient(
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
    const { container } = renderWithQueryClient(
      <AppShell>
        <p>default body</p>
      </AppShell>,
    );

    const main = container.querySelector("main");
    expect(main).not.toBeNull();
    const className = main?.className ?? "";
    expect(className).not.toMatch(/canvasFullBleed/);
  });

  it("does not double-wrap private pages with AppShell (no manual shell in page modules)", async () => {    const rootInfo = await stat(privatePagesRoot);
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

  it("mounts exactly one activity observer for the shell and its children", async () => {
    vi.useFakeTimers();
    try {
      const active = {
        id: "11111111-1111-4111-8111-111111111111",
        job_type: "enrich_confirmed_plant",
        phase: "evidence",
        status: "processing",
        created_at: "2026-08-01T00:00:00Z",
        updated_at: "2026-08-01T00:00:00Z",
        completed_at: null,
        species_key: "gbif:2878688|binomial:Monstera deliciosa",
        scientific_name: "Monstera deliciosa",
        common_name: null,
        candidate_id: "candidate-1",
        result: null,
        last_error: null,
      };
      mocks.getEnrichmentActivity
        .mockResolvedValueOnce({ items: [active], has_more: false })
        .mockResolvedValueOnce({ items: [active], has_more: false })
        .mockResolvedValue({ items: [], has_more: false });

      renderWithQueryClient(
        <AppShell>
          <EnrichmentActivitySummary />
        </AppShell>,
      );

      // One initial request shared by the announcer and the summary child.
      await vi.advanceTimersByTimeAsync(0);
      expect(mocks.getEnrichmentActivity).toHaveBeenCalledTimes(1);
      expect(
        screen.getByRole("heading", { name: "Trabajo en segundo plano" }),
      ).toBeInTheDocument();

      // Exactly one request per poll interval while work is active.
      await vi.advanceTimersByTimeAsync(ACTIVITY_POLL_INTERVAL_MS);
      expect(mocks.getEnrichmentActivity).toHaveBeenCalledTimes(2);

      // This third response has no active jobs, so polling stops.
      await vi.advanceTimersByTimeAsync(ACTIVITY_POLL_INTERVAL_MS);
      expect(mocks.getEnrichmentActivity).toHaveBeenCalledTimes(3);

      // Idle advances prove no further requests fire and the UI settles
      // without any active-work card.
      await vi.advanceTimersByTimeAsync(ACTIVITY_POLL_INTERVAL_MS);
      await vi.advanceTimersByTimeAsync(ACTIVITY_POLL_INTERVAL_MS);
      expect(mocks.getEnrichmentActivity).toHaveBeenCalledTimes(3);
      expect(
        screen.queryByRole("heading", { name: "Trabajo en segundo plano" }),
      ).not.toBeInTheDocument();

      await vi.advanceTimersByTimeAsync(ACTIVITY_POLL_INTERVAL_MS * 3);
      expect(mocks.getEnrichmentActivity).toHaveBeenCalledTimes(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it("runs one full pagination sequence per interval, never parallel observers", async () => {
    vi.useFakeTimers();
    try {
      const active = {
        id: "22222222-2222-4222-8222-222222222222",
        job_type: "enrich_confirmed_plant",
        phase: "evidence",
        status: "processing",
        created_at: "2026-08-01T00:00:00Z",
        updated_at: "2026-08-01T00:00:00Z",
        completed_at: null,
        species_key: null,
        scientific_name: "Monstera deliciosa",
        common_name: null,
        candidate_id: "candidate-1",
        result: null,
        last_error: null,
      };
      // Sequence 1: two pages; only the second holds active work.
      mocks.getEnrichmentActivity
        .mockResolvedValueOnce({
          items: [],
          has_more: true,
          next_cursor: "cursor-page-2",
        })
        .mockResolvedValueOnce({
          items: [active],
          has_more: false,
          next_cursor: null,
        })
        // Sequence 2+: single settled pages.
        .mockResolvedValue({ items: [], has_more: false, next_cursor: null });

      renderWithQueryClient(
        <AppShell>
          <EnrichmentActivitySummary />
        </AppShell>,
      );

      await vi.advanceTimersByTimeAsync(0);
      expect(mocks.getEnrichmentActivity).toHaveBeenCalledTimes(2);
      expect(
        screen.getByRole("heading", { name: "Trabajo en segundo plano" }),
      ).toBeInTheDocument();

      await vi.advanceTimersByTimeAsync(ACTIVITY_POLL_INTERVAL_MS);
      // Exactly one new sequence of exactly one call; its empty result
      // stops polling entirely.
      expect(mocks.getEnrichmentActivity).toHaveBeenCalledTimes(3);

      await vi.advanceTimersByTimeAsync(ACTIVITY_POLL_INTERVAL_MS * 4);
      expect(mocks.getEnrichmentActivity).toHaveBeenCalledTimes(3);
    } finally {
      vi.useRealTimers();
    }
  });
});
