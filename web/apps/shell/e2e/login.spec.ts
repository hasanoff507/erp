import { expect, test, type Page } from "@playwright/test";

/**
 * Smoke: BO-01 on the production build (strict CSP active). Login follows 14 §2.1 — the SPA has no
 * password form; «Kirish» navigates the browser to /auth/login/start. The backend is stubbed.
 */
async function stubAnonymousBackend(page: Page) {
  await page.route("**/auth/session", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "UNAUTHORIZED", message_key: "errors.unauthorized", details: [], request_id: "e2e" },
      }),
    }),
  );
}

function collectCspViolations(page: Page): string[] {
  const violations: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && /Content Security Policy/i.test(msg.text())) violations.push(msg.text());
  });
  return violations;
}

test("login page renders in Uzbek by default", async ({ page }) => {
  const violations = collectCspViolations(page);
  await stubAnonymousBackend(page);
  await page.goto("/login");

  await expect(page.locator("html")).toHaveAttribute("lang", "uz");
  await expect(page.getByRole("heading", { level: 1, name: "Tizimga kirish" })).toBeVisible();
  const start = page.getByRole("link", { name: /^Kirish/ });
  // No `next` → back to `/`, which lands on the first screen the user may open.
  await expect(start).toHaveAttribute("href", "/auth/login/start?return_to=%2F");
  // No credential fields in the SPA (password only on the AS page, 14 §2.1).
  await expect(page.locator("input[type=password]")).toHaveCount(0);
  // Default runtime config (googleEnabled false): no Google button; no dead #export / #terms links.
  await expect(page.getByRole("link", { name: /Google bilan kirish/ })).toHaveCount(0);
  await expect(page.locator('a[href="#terms"], a[href="#privacy"], a[href="#export"]')).toHaveCount(0);
  await expect(page.getByRole("button", { name: "UZ" })).toHaveAttribute("aria-pressed", "true");
  await expect(page).toHaveTitle(/Kirish/);
  // Money display is uz-formatted regardless of the browser's ICU data (NBSP grouping, 08 §8).
  await expect(page.getByText("99 000 so'm")).toBeVisible();

  const csp = await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute("content");
  expect(csp).toContain("default-src 'self'");
  expect(violations).toEqual([]);
});

test("login page switches to Russian and remembers it", async ({ page }) => {
  await stubAnonymousBackend(page);
  await page.goto("/login");

  await page.getByRole("button", { name: "RU" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page.getByRole("heading", { level: 1, name: "Вход в систему" })).toBeVisible();
  await expect(page.getByRole("link", { name: /^Войти(?! через Google)/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "RU" })).toHaveAttribute("aria-pressed", "true");

  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Вход в систему" })).toBeVisible();
});

test("«Kirish» is a full-page navigation to the BFF login start", async ({ page }) => {
  await stubAnonymousBackend(page);
  let navigation: { url: string; isNavigation: boolean } | null = null;
  await page.route("**/auth/login/start**", async (route) => {
    navigation = { url: route.request().url(), isNavigation: route.request().isNavigationRequest() };
    await route.fulfill({ status: 200, contentType: "text/html", body: "<title>AS</title>" });
  });

  const tenant = "0192a0f0-0000-7000-8000-0000000000aa";
  await page.goto(`/login?next=%2Fapp%2Fdebts&tenant_id=${tenant}`);
  await page.getByRole("link", { name: /^Kirish/ }).click();
  await expect(page).toHaveTitle("AS");
  expect(navigation).toEqual({
    url: `http://localhost:4173/auth/login/start?return_to=%2Fapp%2Fdebts&tenant_id=${tenant}`,
    isNavigation: true,
  });
});

test("crafted next / tenant_id never reach /auth/login/start", async ({ page }) => {
  await stubAnonymousBackend(page);
  const start = page.getByRole("link", { name: /^Kirish/ });

  await page.goto("/login?next=%2F%2Fevil.example&tenant_id=t-1");
  await expect(start).toHaveAttribute("href", "/auth/login/start?return_to=%2F");

  await page.goto(`/login?next=%2F${"a".repeat(2048)}`);
  await expect(start).toHaveAttribute("href", "/auth/login/start?return_to=%2F");

  await page.goto("/login?next=%2Fapp%2Fdebts&tenant_id=0192a0f0-0000-7000-8000-0000000000aa%26x%3D1");
  await expect(start).toHaveAttribute("href", "/auth/login/start?return_to=%2Fapp%2Fdebts");
});

test("callback errors are translated; unknown reasons never leak", async ({ page }) => {
  await stubAnonymousBackend(page);
  await page.goto("/login?error=state_mismatch");
  await expect(page.getByText("Kirish so'rovi tasdiqlanmadi. Qayta urinib ko'ring.")).toBeVisible();

  await page.goto("/login?error=weird_reason_xyz");
  await expect(page.getByText("Kirish amalga oshmadi. Qayta urinib ko'ring.")).toBeVisible();
  await expect(page.getByText("weird_reason_xyz")).toHaveCount(0);

  await page.goto("/login?error=subscription_restricted");
  await expect(page.getByText("Obuna muddati tugagan.", { exact: false })).toBeVisible();
  // The data-export link waits for the B6 export flow (no dead #export link).
  await expect(page.getByText("Ma'lumotlarimni yuklab olish")).toHaveCount(0);
});

test("terms / privacy links come from GET /auth/terms (text_url)", async ({ page }) => {
  await stubAnonymousBackend(page);
  await page.route("**/auth/terms", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            kind: "terms",
            version: "1.2",
            text_url: "/legal/terms-1.2.html",
            text_sha256: "a".repeat(64),
            effective_from: "2026-10-01",
          },
          {
            kind: "privacy",
            version: "1.0",
            text_url: "/legal/privacy.html",
            text_sha256: "b".repeat(64),
            effective_from: "2026-10-01",
          },
        ],
      }),
    }),
  );
  await page.goto("/login");
  await expect(page.getByRole("link", { name: "Foydalanish shartlari" })).toHaveAttribute(
    "href",
    "/legal/terms-1.2.html",
  );
  await expect(
    page.getByRole("link", { name: "Shaxsiy ma'lumotlarni qayta ishlash siyosati" }),
  ).toHaveAttribute("href", "/legal/privacy.html");
});

test("Manrope is self-hosted and the protected area redirects to login", async ({ page }) => {
  const fontRequests: string[] = [];
  page.on("request", (req) => {
    if (req.resourceType() === "font") fontRequests.push(req.url());
  });
  await stubAnonymousBackend(page);
  await page.goto("/app/dashboard");
  await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fdashboard/);
  await page.evaluate(() => document.fonts.ready);
  expect(fontRequests.length).toBeGreaterThan(0);
  for (const url of fontRequests) expect(new URL(url).origin).toBe("http://localhost:4173");
  expect(await page.evaluate(() => document.fonts.check("700 16px 'Manrope Variable'"))).toBe(true);
});
