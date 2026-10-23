import { expect, test, type Page } from "@playwright/test";

/**
 * UX-INSTALL (07): `/install` is public; platform auto-detect + manual switch, iOS steps + data-loss
 * warning, cloud printer section (#cloud-print). UX-INSTALL (b): on iOS outside the installed app
 * `/pos/*` redirects to `/install?platform=ios`, the back-office only shows a banner.
 */
const IPHONE_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";

const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["reports.sales.view", "reports.finance.view", "sales.create"],
  scope: ["reports", "sales"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

async function anonymous(page: Page) {
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

test("/install is public and detects the desktop platform (Windows)", async ({ page }) => {
  await anonymous(page);
  await page.goto("/install");
  await expect(page).toHaveURL(/\/install$/);
  await expect(page.getByRole("heading", { level: 1, name: "Qurilmani o'rnatish" })).toBeVisible();
  const platforms = page.getByRole("group", { name: "Qurilma turi" });
  await expect(platforms.getByRole("button", { name: "Windows — Aniqlandi" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByText("Do'kon agenti", { exact: true })).toBeVisible();

  await platforms.getByRole("button", { name: "Android" }).click();
  await expect(page.getByText(/Chrome menyusi/)).toBeVisible();

  await expect(page.locator("#cloud-print")).toContainText("Bulut printer");
  await expect(page.locator("#cloud-print")).toContainText("http://localhost:4173/print/cloudprnt");
  await expect(page.getByRole("button", { name: "Sinov cheki" })).toBeDisabled();
});

test("/install?platform=ios shows the 3 steps and the data-loss warning; RU", async ({ page }) => {
  await anonymous(page);
  await page.goto("/install?platform=ios#cloud-print");
  const ios = page.getByTestId("install-ios");
  await expect(ios.getByRole("listitem")).toHaveCount(3);
  await expect(ios.getByText(/ma'lumotlar o'chib ketishi mumkin/)).toBeVisible();
  await expect(page.locator("#cloud-print")).toBeInViewport();

  await page.getByRole("button", { name: "RU" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Установка на устройство" })).toBeVisible();
  await expect(ios.getByText(/данные могут быть удалены/)).toBeVisible();
});

test.describe("iOS Safari tab (not installed)", () => {
  test.use({ userAgent: IPHONE_UA, viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("POS is blocked → /install?platform=ios; back-office shows only a banner", async ({ page }) => {
    await page.route("**/auth/session", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(session) }),
    );
    await page.goto("/pos/login");
    await expect(page).toHaveURL(/\/install\?platform=ios$/);
    await expect(page.getByTestId("install-ios")).toBeVisible();
    await expect(
      page
        .getByRole("group", { name: "Qurilma turi" })
        .getByRole("button", { name: "iPhone / iPad — Aniqlandi" }),
    ).toHaveAttribute("aria-pressed", "true");

    await page.goto("/app/dashboard");
    await expect(page.getByText("Xayrli kun, Akmal")).toBeVisible();
    await expect(page.getByText(/iPhone\/iPad'da ilovani Home ekranga o'rnating/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Qanday o'rnatiladi" })).toHaveAttribute(
      "href",
      "/install?platform=ios",
    );
  });
});
