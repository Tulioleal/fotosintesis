import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test.describe.configure({
  mode: "serial",
  timeout: 90_000,
});

test.beforeEach(async ({ page }) => {
  const email = `enrich-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Nombre").fill("Enrich E2E");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  const registration = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/auth/register") &&
      response.request().method() === "POST",
  );

  await page.getByRole("button", { name: "Crear cuenta" }).click();

  const registrationResponse = await registration;
  expect(
    registrationResponse.status(),
    await registrationResponse.text(),
  ).toBe(201);

  await expect(page).toHaveURL(/\/login\?registered=1$/);
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/home$/);
});

// A real 1x1 JPEG: the backend validates that uploads are actually decodable
// before scheduling identification.
const TINY_JPEG = Buffer.from(
  "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof" +
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB" +
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q==",
  "base64",
);

type ConfirmedProfile = {
  candidateId: string;
  scientificName: string;
};

async function openConfirmedProfile(
  page: Page,
  beforeConfirmation?: (confirmed: ConfirmedProfile) => Promise<void>,
): Promise<ConfirmedProfile> {
  await page.goto("/identify");

  // Capture the candidate id and accepted name from the identification POST
  // (issued on upload) so activity routes can be installed before
  // confirmation schedules background work.
  const identificationResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/identifications") &&
      response.request().method() === "POST",
  );
  await page.setInputFiles('input[accept="image/jpeg,image/png,image/webp"]', {
    name: "plant.jpg",
    mimeType: "image/jpeg",
    buffer: TINY_JPEG,
  });
  const payload = await (await identificationResponse).json();
  const candidate = payload.candidates[0];
  const confirmed: ConfirmedProfile = {
    candidateId: candidate.id,
    scientificName:
      candidate.accepted_scientific_name ?? candidate.suggested_scientific_name,
  };
  expect(confirmed.candidateId).toBeTruthy();
  expect(confirmed.scientificName).toBeTruthy();

  await expect(page.getByRole("heading", { name: "Pata de oso" })).toBeVisible();

  await beforeConfirmation?.(confirmed);

  await page.getByRole("button", { name: "Seleccionar esta planta" }).click();
  await expect(page).toHaveURL(/\/profiles\/.*\?candidateId=/);
  expect(new URL(page.url()).searchParams.get("candidateId")).toBe(
    confirmed.candidateId,
  );

  await expect(page.getByText("Perfil botanico guardado")).toBeVisible();
  await expect(page.getByText(/Estado de la evidencia/i)).toBeVisible({ timeout: 15000 });
  return confirmed;
}

function activityItem(
  candidateId: string,
  scientificName: string,
  status: string,
  updatedAt: string,
) {
  return {
    id: "00000000-0000-4000-8000-000000000010",
    job_type: "enrich_confirmed_plant",
    phase: "evidence",
    status,
    created_at: "2026-08-13T00:00:00Z",
    updated_at: updatedAt,
    completed_at: status === "processing" ? null : updatedAt,
    species_key: `binomial:${scientificName}`,
    scientific_name: scientificName,
    common_name: null,
    candidate_id: candidateId,
    result:
      status === "complete"
        ? {
            outcome: "complete",
            covered_count: 1,
            missing_count: 0,
            regenerated_section_count: 0,
            stale_section_count: 0,
            limitations: [],
          }
        : null,
    last_error: null,
  };
}

function activityFixture(items: object[] | ((requestIndex: number) => object[])) {
  let requests = 0;
  const seenCursors: (string | null)[] = [];

  return {
    async install(page: Page) {
      await page.route("**/api/jobs/enrichment-activity*", async (route) => {
        requests += 1;
        const url = new URL(route.request().url());
        seenCursors.push(url.searchParams.get("cursor"));
        const body =
          typeof items === "function" ? items(requests) : items;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ items: body, has_more: false, next_cursor: null }),
        });
      });
    },
    requestCount: () => requests,
    seenCursors,
  };
}

async function mockActivity(page: Page, items: object[]) {
  await page.route("**/api/jobs/enrichment-activity*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, has_more: false, next_cursor: null }),
    });
  });
}

function profileHref(scientificName: string, candidateId: string): string {
  return `/profiles/${encodeURIComponent(scientificName)}?candidateId=${candidateId}`;
}

test("confirmed plant schedules enrichment and profile remains navigable", async ({ page }) => {
  await openConfirmedProfile(page);

  await expect(page.getByRole("status")).toContainText(
    /La evidencia está lista|Encontramos evidencia útil|No pudimos completar la búsqueda de evidencia/,
    { timeout: 60000 },
  );

  await expect(page.getByText("Perfil botanico guardado")).toBeVisible();
});

test("the assistant link is keyboard reachable and carries full plant context", async ({ page }) => {
  await openConfirmedProfile(page);

  const assistantLink = page.getByRole("link", {
    name: "Preguntar al asistente",
  });

  const href = await assistantLink.getAttribute("href");
  expect(href).not.toBeNull();

  const assistantUrl = new URL(href!, page.url());
  expect(assistantUrl.searchParams.get("plant")).toBeTruthy();
  expect(assistantUrl.searchParams.get("binomial")).toBeTruthy();
  expect(assistantUrl.searchParams.get("scientific")).toBeTruthy();
  expect(assistantUrl.searchParams.get("candidate")).toBeTruthy();

  await assistantLink.focus();
  await expect(assistantLink).toBeFocused();
  await assistantLink.press("Enter");

  await expect(page).toHaveURL(/\/assistant\?/);
});

test("the active enrichment profile has no serious or critical automated accessibility violations", async ({ page }) => {
  // Deterministically arrange the pending/processing state so the scanned
  // DOM is stable, regardless of how fast the real backend job advances.
  // Terminal states (complete, partial, failed, stalled) are covered by
  // dedicated component tests and are not claimed to be scanned here.
  await page.route(
    "**/api/identifications/candidates/*/enrichment",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          candidate_id: "00000000-0000-4000-8000-000000000001",
          policy_version: 1,
          job: {
            id: "00000000-0000-4000-8000-000000000002",
            job_type: "enrich_confirmed_plant",
            status: "processing",
            attempt_count: 1,
            max_attempts: 3,
            created_at: "2026-08-13T00:00:00Z",
            updated_at: "2026-08-13T00:00:00Z",
            completed_at: null,
            result: null,
            last_error: null,
          },
        }),
      });
    },
  );

  await openConfirmedProfile(page);

  await expect(page.getByRole("status")).toContainText(
    "Estamos consultando y validando fuentes",
  );
  await expect(page.getByText("Perfil botanico guardado")).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  const seriousOrCritical = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(seriousOrCritical).toEqual([]);
});

test("navigating away from the profile keeps background work visible on Home", async ({ page }) => {
  let fixture: ReturnType<typeof activityFixture> | undefined;
  // The fixture pairs the REAL candidate id with its REAL accepted name so
  // its link authorizes an existing profile context.
  const confirmed = await openConfirmedProfile(page, async ({ candidateId, scientificName }) => {
    fixture = activityFixture([
      activityItem(candidateId, scientificName, "processing", "2026-08-13T00:00:01Z"),
    ]);
    await fixture.install(page);
  });
  const { candidateId, scientificName } = confirmed;
  expect(fixture!.requestCount()).toBeGreaterThanOrEqual(0);

  // The durable job keeps running after the user leaves the profile. Home
  // reflects that active work through the shared activity endpoint.
  await page.getByRole("link", { name: "Home" }).first().click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(
    page.getByRole("heading", { name: "Trabajo en segundo plano" }),
  ).toBeVisible();
  await expect(page.getByText(/continúa en segundo plano/).first()).toBeVisible();
  const profileLink = page.getByRole("link", {
    name: `Ver perfil de ${scientificName}`,
  });
  await expect(profileLink).toHaveAttribute(
    "href",
    profileHref(scientificName, candidateId),
  );
  expect(fixture!.requestCount()).toBeGreaterThanOrEqual(1);

  // The activity link navigates to the authorized candidate-scoped profile.
  await profileLink.click();
  await expect(page).toHaveURL(new RegExp(`candidateId=${candidateId}`));
  await expect(page.getByText(/Estado de la evidencia/i)).toBeVisible({
    timeout: 15000,
  });

  // The dashboard itself remains fully usable.
  await page.getByRole("link", { name: "Home" }).first().click();
  await expect(page.getByRole("heading", { name: /Hola,/ })).toBeVisible();
});

test("empty activity stays idle and confirmation wakes the tracker", async ({ page }) => {
  const fixture = activityFixture([]);
  await fixture.install(page);

  // Load Home with an empty activity response: no active work exists.
  await page.goto("/home");
  await expect(page.getByRole("heading", { name: /Hola,/ })).toBeVisible();
  await expect
    .poll(() => fixture.requestCount(), { timeout: 10_000 })
    .toBeGreaterThanOrEqual(1);
  const callsAfterIdle = fixture.requestCount();

  // Confirmation must wake the shared tracker with a fresh request.
  await openConfirmedProfile(page);
  await expect
    .poll(() => fixture.requestCount(), { timeout: 15_000 })
    .toBeGreaterThan(callsAfterIdle);
});

test("the pagination walker consumes every cursor page and keeps polling", async ({ page }) => {
  let fixture: ReturnType<typeof activityFixtureFromPages> | undefined;
  await openConfirmedProfile(page, async ({ candidateId, scientificName }) => {
    fixture = activityFixtureFromPages(candidateId, scientificName);
    await fixture.install(page);
  });

  await page.getByRole("link", { name: "Home" }).first().click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(
    page.getByRole("heading", { name: "Trabajo en segundo plano" }),
  ).toBeVisible();

  // Exactly one traversal sequence: two pages, cursor forwarded.
  await expect
    .poll(() => fixture!.requestCount(), { timeout: 10_000 })
    .toBe(2);
  expect(fixture!.seenCursors).toEqual([null, "cursor-2"]);

  // The active item on the second page keeps polling alive.
  const countAtRest = fixture!.requestCount();
  await expect
    .poll(() => fixture!.requestCount(), { timeout: 15_000 })
    .toBeGreaterThan(countAtRest);
});

function activityFixtureFromPages(candidateId: string, scientificName: string) {
  let requests = 0;
  const seenCursors: (string | null)[] = [];
  return {
    async install(page: Page) {
      await page.route("**/api/jobs/enrichment-activity*", async (route) => {
        requests += 1;
        const url = new URL(route.request().url());
        seenCursors.push(url.searchParams.get("cursor"));
        const body =
          requests === 1
            ? { items: [], has_more: true, next_cursor: "cursor-2" }
            : {
                items: [
                  activityItem(candidateId, scientificName, "processing", "2026-08-13T00:00:01Z"),
                ],
                has_more: false,
                next_cursor: null,
              };
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(body),
        });
      });
    },
    requestCount: () => requests,
    seenCursors,
  };
}

test("a terminal outcome is announced once and linked to the profile later", async ({ page }) => {
  const { candidateId, scientificName } = await openConfirmedProfile(page);

  // Start with active work, then let it reach a terminal state on a later
  // poll. The session-scoped deduplication must announce it exactly once.
  let terminal = false;
  await page.route("**/api/jobs/enrichment-activity*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          activityItem(
            candidateId,
            scientificName,
            terminal ? "complete" : "processing",
            terminal ? "2026-08-13T00:00:05Z" : "2026-08-13T00:00:01Z",
          ),
        ],
        has_more: false,
        next_cursor: null,
      }),
    });
  });

  await page.goto("/home");
  await expect(
    page.getByRole("heading", { name: "Trabajo en segundo plano" }),
  ).toBeVisible();

  terminal = true;
  const announcement = page.locator('[data-terminal-announcement="complete"]');
  await expect(announcement).toContainText("La evidencia está lista", {
    timeout: 20000,
  });
  await expect(
    announcement.getByRole("link", {
      name: `Ver perfil de ${scientificName}`,
    }),
  ).toHaveAttribute("href", profileHref(scientificName, candidateId));

  // Dismiss the announcement, then leave and come back: the same outcome
  // must not be announced again, while remaining discoverable as recent
  // retained activity.
  await announcement.getByRole("button", { name: "Cerrar" }).click();
  await page.getByRole("link", { name: "Mi Jardín" }).first().click();
  await expect(page).toHaveURL(/\/garden$/);
  await page.getByRole("link", { name: "Home" }).first().click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(page.locator("[data-terminal-announcement]")).toHaveCount(0);
  // The terminal outcome stays discoverable as recent activity.
  await expect(
    page.getByRole("heading", { name: "Actividad reciente" }),
  ).toBeVisible();
});

test("multiple terminal outcomes are announced one at a time", async ({ page }) => {
  const { candidateId, scientificName } = await openConfirmedProfile(page);

  let poll = 0;
  await page.route("**/api/jobs/enrichment-activity*", async (route) => {
    poll += 1;
    // First response must hold active work or polling stops before the
    // terminal outcomes ever arrive.
    const items =
      poll === 1
        ? [activityItem(candidateId, scientificName, "processing", "2026-08-13T00:00:09Z")]
        : [
            activityItem(candidateId, scientificName, "complete", "2026-08-13T00:00:01Z"),
            {
              ...activityItem(candidateId, scientificName, "failed", "2026-08-13T00:00:02Z"),
              id: "00000000-0000-4000-8000-000000000020",
            },
          ];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, has_more: false, next_cursor: null }),
    });
  });

  await page.goto("/home");

  // Newest first.
  const failedAnnouncement = page.locator('[data-terminal-announcement="failed"]');
  await expect(failedAnnouncement).toContainText(/No pudimos ampliar la evidencia/, {
    timeout: 20000,
  });
  await failedAnnouncement.getByRole("button", { name: "Cerrar" }).click();

  const completeAnnouncement = page.locator('[data-terminal-announcement="complete"]');
  await expect(completeAnnouncement).toContainText("La evidencia está lista");
  await completeAnnouncement.getByRole("button", { name: "Cerrar" }).click();

  await expect(page.locator("[data-terminal-announcement]")).toHaveCount(0);
});

test("garden list surfaces activity while garden detail hides unrelated work", async ({ page }) => {
  const { candidateId, scientificName } = await openConfirmedProfile(page);

  // Save the confirmed plant so the garden has a card to open.
  await page.getByLabel("Nombre personalizado").fill("Helecho");
  await page
    .getByRole("button", { name: "Guardar planta confirmada" })
    .click();
  await expect(page.getByText(/Guardada en Mi Jardin/)).toBeVisible();

  await mockActivity(page, [
    activityItem(candidateId, scientificName, "processing", "2026-08-13T00:00:01Z"),
    // The unrelated row intentionally tests filtering; it still carries a
    // valid UUID candidate context.
    {
      ...activityItem(
        "00000000-0000-4000-8000-000000000042",
        "Ficus elastica",
        "processing",
        "2026-08-13T00:00:02Z",
      ),
      id: "00000000-0000-4000-8000-000000000099",
    },
  ]);

  await page.getByRole("link", { name: "Home" }).first().click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(
    page.getByRole("heading", { name: "Trabajo en segundo plano" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Mi Jardín" }).first().click();
  await expect(page).toHaveURL(/\/garden$/);
  await expect(
    page.getByRole("heading", { name: "Trabajo en segundo plano" }),
  ).toBeVisible();

  const plantCard = page.locator('a[href^="/garden/"]').first();
  await expect(plantCard).toBeVisible();
  await expect(plantCard).toContainText("Helecho");
  await plantCard.click();
  await expect(page).toHaveURL(/\/garden\//);
  await expect(
    page.getByRole("heading", { name: "Trabajo en segundo plano" }),
  ).toBeVisible();
  await expect(page.getByText(/Ficus elastica/)).toHaveCount(0);
});

test("a partial evidence outcome is announced with bounded missing counts", async ({ page }) => {
  const { candidateId, scientificName } = await openConfirmedProfile(page);

  let poll = 0;
  await page.route("**/api/jobs/enrichment-activity*", async (route) => {
    poll += 1;
    // First response must hold active work or polling stops before the
    // terminal outcome arrives.
    const items: object[] =
      poll === 1
        ? [activityItem(candidateId, scientificName, "processing", "2026-08-13T00:00:09Z")]
        : [
            {
              ...activityItem(candidateId, scientificName, "partial", "2026-08-13T00:00:02Z"),
              result: {
                outcome: "partial",
                covered_count: 1,
                missing_count: 2,
                regenerated_section_count: 0,
                stale_section_count: 0,
                limitations: ["missing_required_aspects"],
              },
            },
          ];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, has_more: false, next_cursor: null }),
    });
  });

  await page.getByRole("link", { name: "Home" }).first().click();
  const announcement = page.locator('[data-terminal-announcement="partial"]');
  await expect(announcement).toContainText(/Encontramos evidencia útil/, {
    timeout: 20000,
  });
  await expect(announcement).toContainText(/2 pendientes/);
  // Partial copy never claims the profile sections were rewritten.
  await expect(announcement).not.toContainText(/perfil se actualizó$/);

  await announcement.getByRole("button", { name: "Cerrar" }).click();
});

test("refresh-phase activity is distinct from evidence activity", async ({ page }) => {
  const { candidateId, scientificName } = await openConfirmedProfile(page);

  let poll = 0;
  await page.route("**/api/jobs/enrichment-activity*", async (route) => {
    poll += 1;
    // First response must hold active work or polling stops before the
    // refresh outcome ever arrives.
    const items =
      poll === 1
        ? [activityItem(candidateId, scientificName, "processing", "2026-08-13T00:00:09Z")]
        : [
            {
              ...activityItem(candidateId, scientificName, "complete", "2026-08-13T00:00:03Z"),
              id: "00000000-0000-4000-8000-000000000030",
              job_type: "refresh_profile",
              phase: "profile_refresh",
              result: {
                outcome: "noop",
                covered_count: 0,
                missing_count: 0,
                regenerated_section_count: 0,
                stale_section_count: 0,
                limitations: [],
              },
            },
          ];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, has_more: false, next_cursor: null }),
    });
  });

  await page.goto("/home");
  await expect(
    page.getByRole("heading", { name: "Actividad reciente" }),
  ).toBeVisible({ timeout: 20000 });
  await expect(page.getByText(/Actualización del perfil · El perfil ya estaba al día/)).toBeVisible();
});

test("announcements, recent rows, and the stale-data warning pass accessibility scans", async ({ page }) => {
  const { candidateId, scientificName } = await openConfirmedProfile(page);

  let poll = 0;
  let failFutureRequests = false;
  await page.route("**/api/jobs/enrichment-activity*", async (route) => {
    if (failFutureRequests) {
      await route.abort("failed");
      return;
    }
    poll += 1;
    const items: object[] =
      poll === 1
        ? [activityItem(candidateId, scientificName, "processing", "2026-08-13T00:00:09Z")]
        : [
            // Keep active work in every response so polling continues and a
            // later aborted request can surface the stale-data warning.
            activityItem(candidateId, scientificName, "processing", "2026-08-13T00:00:09Z"),
            {
              ...activityItem(candidateId, scientificName, "partial", "2026-08-13T00:00:02Z"),
              // Distinct id from the processing row (...0010): the aggregator
              // keeps the newest version per id, so a shared id would discard
              // the partial announcement before it renders.
              id: "00000000-0000-4000-8000-000000000020",
              result: {
                outcome: "partial",
                covered_count: 1,
                missing_count: 2,
                regenerated_section_count: 0,
                stale_section_count: 0,
                limitations: ["missing_required_aspects"],
              },
            },
            {
              ...activityItem(candidateId, scientificName, "failed", "2026-08-13T00:00:03Z"),
              id: "00000000-0000-4000-8000-000000000021",
              result: null,
              last_error: { category: "attempts_exhausted", retryable: false },
            },
          ];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, has_more: false, next_cursor: null }),
    });
  });

  await page.getByRole("link", { name: "Home" }).first().click();

  async function expectNoSeriousViolations() {
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const seriousOrCritical = results.violations.filter((violation) =>
      ["serious", "critical"].includes(violation.impact ?? ""),
    );
    expect(seriousOrCritical).toEqual([]);
  }

  // Failed announcement (newest outcome) keeps focus usable and passes the
  // scan.
  const failed = page.locator('[data-terminal-announcement="failed"]');
  await expect(failed).toContainText(/No pudimos ampliar la evidencia/, { timeout: 20000 });
  await expectNoSeriousViolations();
  await failed.getByRole("button", { name: "Cerrar" }).click();

  // Partial announcement passes the scan too.
  const partial = page.locator('[data-terminal-announcement="partial"]');
  await expect(partial).toContainText(/Encontramos evidencia útil/, { timeout: 20000 });
  await expectNoSeriousViolations();
  await partial.getByRole("button", { name: "Cerrar" }).click();
  await expect(page.locator("[data-terminal-announcement]")).toHaveCount(0);

  // Multiple recent-activity rows render with accessible names. Partial and
  // failed belong to the same plant, so identical labels are correct; assert
  // presence and non-emptiness only.
  await expect(
    page.getByRole("heading", { name: "Actividad reciente" }),
  ).toBeVisible();
  const links = page.getByRole("link", { name: /Ver perfil de/ });
  const names = await links.evaluateAll((elements) =>
    elements.map((element) => element.getAttribute("aria-label")),
  );
  expect(names.length).toBeGreaterThan(0);
  expect(names.every((name) => name && name.length > 0)).toBe(true);
  await expectNoSeriousViolations();

  // Fail every future activity request WITHOUT reloading: the in-memory
  // cache must survive and surface the stale-data warning while the
  // retained rows stay visible.
  failFutureRequests = true;

  // The tracker polls every 5s while active work remains in cache; the
  // aborted background refresh surfaces the warning within ~10s.
  await expect(
    page.getByText(/Conservamos el estado anterior/),
  ).toBeVisible({ timeout: 15000 });
  await expect(
    page.getByRole("heading", { name: "Actividad reciente" }),
  ).toBeVisible();
  await expectNoSeriousViolations();
});
