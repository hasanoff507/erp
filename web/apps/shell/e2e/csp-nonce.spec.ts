import { expect, test, type Page } from "@playwright/test";

/**
 * 24 §4.4 on the production build (`vite preview`): index.html gets a fresh style nonce per response
 * (CSP header + CSP <meta> + `<meta property="csp-nonce">`, Cache-Control: no-store); the modal Radix
 * menu's scroll-lock <style> (react-remove-scroll) carries that nonce via get-nonce → no violation.
 */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["reports.sales.view", "reports.finance.view"],
  scope: ["reports"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

function collectCspViolations(page: Page): string[] {
  const violations: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && /Content Security Policy/i.test(msg.text())) violations.push(msg.text());
  });
  page.on("pageerror", (err) => {
    if (/Content Security Policy/i.test(err.message)) violations.push(err.message);
  });
  return violations;
}

const nonceOf = (csp: string | undefined) => /style-src 'self' 'nonce-([^']+)'/.exec(csp ?? "")?.[1];

test("index.html: fresh nonce per response in header, CSP meta and csp-nonce meta; no-store", async ({
  request,
}) => {
  const seen = new Set<string>();
  for (const path of ["/", "/login", "/app/dashboard", "/index.html"]) {
    const response = await request.get(path, { headers: { Accept: "text/html" } });
    expect(response.status()).toBe(200);
    const headers = response.headers();
    expect(headers["cache-control"]).toBe("no-store");
    const nonce = nonceOf(headers["content-security-policy"]);
    expect(nonce).toMatch(/^[A-Za-z0-9+/]{22}==$/);
    const html = await response.text();
    expect(html).not.toContain("__CSP_NONCE__");
    expect(html).toContain(`<meta property="csp-nonce" content="${nonce}"`);
    expect(html.replaceAll("&#39;", "'")).toContain(`style-src 'self' 'nonce-${nonce}'`);
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
    seen.add(nonce ?? "");
  }
  expect(seen.size).toBe(4);

  // Hashed assets keep the static policy (no nonce) and are cacheable.
  const html = await (await request.get("/login", { headers: { Accept: "text/html" } })).text();
  const script = /<script type="module" crossorigin src="([^"]+)"/.exec(html)?.[1];
  expect(script).toBeTruthy();
  const asset = await request.get(script ?? "");
  expect(asset.headers()["cache-control"] ?? "").not.toBe("no-store");
  expect(asset.headers()["content-security-policy"]).not.toContain("nonce");
});

test("Radix modal menu injects its scroll-lock <style> with the nonce — no CSP violation", async ({
  page,
}) => {
  const violations = collectCspViolations(page);
  await page.route("**/auth/session", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(session) }),
  );
  const response = await page.goto("/app/dashboard");
  const nonce = nonceOf(response?.headers()["content-security-policy"]);
  expect(nonce).toBeTruthy();
  await expect(page.getByText("Xayrli kun, Akmal")).toBeVisible();

  await page.getByRole("button", { name: "Foydalanuvchi menyusi" }).click();
  await expect(page.getByRole("menuitem", { name: "Chiqish" })).toBeVisible();

  // react-remove-scroll-bar locks the body through an injected <style> (react-style-singleton).
  const styles = await page.evaluate(() =>
    Array.from(document.querySelectorAll("style")).map((el) => ({ nonce: el.nonce, css: el.textContent })),
  );
  const scrollLock = styles.filter((s) => s.css?.includes("data-scroll-locked"));
  expect(scrollLock.length).toBeGreaterThan(0);
  for (const style of scrollLock) expect(style.nonce).toBe(nonce);
  await expect(page.locator("body")).toHaveAttribute("data-scroll-locked", /\d+/);

  await page.keyboard.press("Escape");
  await expect(page.getByRole("menuitem", { name: "Chiqish" })).toHaveCount(0);
  expect(violations).toEqual([]);
});
