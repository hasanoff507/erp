import { expect, test, type Page, type Request } from "@playwright/test";

/**
 * BO-21 signup wizard (07, 14 §20) on the production build (strict CSP). The backend is stubbed:
 * phone → OTP (signup) → password + name → store + terms → POST /auth/signup (sets the session) →
 * ③–⑥ → «Yakunlash» → BO-02. Responses follow the generated models (OtpRequestOut, OtpVerifyOut,
 * TermsListOut, SignupOut, SessionInfo).
 */
const CHALLENGE = "0192a0f0-0000-7000-8000-0000000000c1";

const ownerSession = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Asosiy filial" }],
  roles: ["owner"],
  permissions: ["reports.sales.view", "reports.finance.view", "catalog.manage"],
  scope: ["reports", "catalog"],
  client_id: "web-bff",
  sub_status: "trial",
  access_expires_at: 0,
};

const envelope = (code: string, key: string, details: { field: string; message_key: string }[] = []) =>
  JSON.stringify({ error: { code, message_key: key, details, request_id: "e2e" } });

interface Backend {
  signedUp: boolean;
  signupBodies: Record<string, unknown>[];
  otpBodies: Record<string, unknown>[];
  csrfRequests: number;
  writeHeaders: Record<string, string>[];
}

function collectCspViolations(page: Page): string[] {
  const violations: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && /Content Security Policy/i.test(msg.text())) violations.push(msg.text());
  });
  return violations;
}

/** Runtime config of a deployment with Google sign-in (`googleEnabled`, 24 §3); the default hides it. */
async function enableGoogle(page: Page) {
  await page.route("**/config.js", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/javascript",
      body: 'window.__ERP_CONFIG__ = { apiBaseUrl: "", environment: "test", googleEnabled: true };',
    }),
  );
}

const json = (body: unknown, status = 200) => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

async function stubBackend(
  page: Page,
  options: { signup?: (body: Record<string, unknown>) => { status: number; body: string } } = {},
): Promise<Backend> {
  const backend: Backend = {
    signedUp: false,
    signupBodies: [],
    otpBodies: [],
    csrfRequests: 0,
    writeHeaders: [],
  };
  const remember = (request: Request) => backend.writeHeaders.push(request.headers());

  await page.route("**/auth/session", (route) =>
    backend.signedUp
      ? route.fulfill(json(ownerSession))
      : route.fulfill({
          status: 401,
          contentType: "application/json",
          body: envelope("UNAUTHORIZED", "errors.unauthorized"),
        }),
  );
  await page.route("**/api/v1/auth/csrf", (route) => {
    backend.csrfRequests += 1;
    return route.fulfill({
      status: 401,
      contentType: "application/json",
      body: envelope("UNAUTHORIZED", "errors.unauthorized"),
    });
  });
  await page.route("**/auth/terms", (route) =>
    route.fulfill(
      json({
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
          {
            kind: "ai_cross_border",
            version: "1.0",
            text_url: "/legal/ai.html",
            text_sha256: "c".repeat(64),
            effective_from: "2026-10-01",
          },
        ],
      }),
    ),
  );
  await page.route("**/auth/otp/request", (route) => {
    remember(route.request());
    backend.otpBodies.push(route.request().postDataJSON() as Record<string, unknown>);
    return route.fulfill(
      json({
        challenge_id: CHALLENGE,
        channel_used: "telegram",
        expires_at: "2026-10-17T10:05:00Z",
        warnings: [],
      }),
    );
  });
  await page.route("**/auth/otp/verify", (route) => {
    remember(route.request());
    const body = route.request().postDataJSON() as { code: string };
    return body.code === "123456"
      ? route.fulfill(json({ challenge_id: CHALLENGE, purpose: "signup", verified: true }))
      : route.fulfill({
          status: 400,
          contentType: "application/json",
          body: envelope("OTP_INVALID", "errors.otp_invalid"),
        });
  });
  await page.route("**/auth/signup", (route) => {
    remember(route.request());
    const body = route.request().postDataJSON() as Record<string, unknown>;
    backend.signupBodies.push(body);
    const answer = options.signup?.(body);
    if (answer) return route.fulfill({ ...answer, contentType: "application/json" });
    backend.signedUp = true;
    return route.fulfill(
      json(
        { tenant_id: "t-1", user_id: "u-1", sub_status: "trial", trial_ends_at: "2026-11-16T09:00:00Z" },
        201,
      ),
    );
  });
  return backend;
}

const next = (page: Page) => page.getByRole("button", { name: "Davom", exact: true });

async function verifyPhone(page: Page, code = "123456") {
  await page.getByLabel("Telefon").fill("901234567");
  await page.getByRole("button", { name: "Kod olish" }).click();
  await expect(page.getByText("Kod Telegram bot orqali +998 90 123 45 67 raqamiga yuborildi.")).toBeVisible();
  await page.getByRole("group", { name: "Tasdiqlash kodi" }).getByRole("textbox").first().fill(code);
}

test("signup: phone → code → store → tenant created → ③–⑥ → dashboard", async ({ page }) => {
  const violations = collectCspViolations(page);
  const backend = await stubBackend(page);
  await page.goto("/onboarding");

  await expect(page.getByRole("heading", { level: 1, name: "Hisob yaratish" })).toBeVisible();
  await expect(page.getByText("1-bosqich / 6")).toBeVisible();
  await expect(page.getByText("30 kunlik bepul sinov", { exact: true })).toBeVisible();
  const steps = page.getByRole("list", { name: "Bosqichlar" });
  await expect(steps.getByRole("listitem")).toHaveCount(6);

  // ① — the code is verified as soon as six digits are typed.
  await verifyPhone(page, "000000");
  await expect(page.getByText("Tasdiqlash kodi noto'g'ri")).toBeVisible();
  await page.getByRole("group", { name: "Tasdiqlash kodi" }).getByRole("textbox").first().fill("123456");
  await expect(page.getByText("Raqam tasdiqlandi")).toBeVisible();
  expect(backend.otpBodies).toEqual([{ phone: "+998901234567", purpose: "signup" }]);

  await page.getByRole("textbox", { name: "Parol", exact: true }).fill("short");
  await page.getByLabel("Ism").fill("Akmal Karimov");
  await page.getByLabel("Ism").press("Enter");
  await expect(page.getByText("Parol kamida 8 ta belgidan iborat bo'lsin")).toBeVisible();
  await page.getByRole("textbox", { name: "Parol", exact: true }).fill("Secret-pass-1");
  await page.getByLabel("Ism").press("Enter"); // Enter = next (07 «Klaviatura»)

  // ② — summary of ①, terms gate «Davom».
  await expect(page.getByRole("heading", { level: 1, name: "Do'kon" })).toBeVisible();
  await expect(page.getByText("2-bosqich / 6")).toBeVisible();
  await expect(page.getByText("1-bosqich bajarildi:")).toBeVisible();
  await page.getByLabel("Do'kon nomi").fill("Baraka do'koni");
  await page.getByRole("radio", { name: /Yakka tadbirkor/ }).click();
  await expect(page.getByRole("link", { name: "Foydalanish shartlari (v1.2, 01.10.2026)" })).toHaveAttribute(
    "href",
    "/legal/terms-1.2.html",
  );
  await expect(page.getByText(/30 kunlik sinov boshlanadi/)).toBeVisible();
  await expect(next(page)).toBeDisabled();
  await page.getByRole("checkbox", { name: /Foydalanish shartlariga roziman/ }).click();
  await page.getByRole("checkbox", { name: /AI xizmatiga/ }).click();
  await next(page).click();

  // POST /auth/signup — no CSRF fetch before a session exists (same-origin check server-side).
  await expect(page.getByRole("heading", { level: 1, name: "Tovarlar" })).toBeVisible();
  expect(backend.signupBodies).toEqual([
    {
      otp_challenge_id: CHALLENGE,
      password: "Secret-pass-1",
      owner_name: "Akmal Karimov",
      store_name: "Baraka do'koni",
      business_type: "retail",
      legal_form: "sole_proprietor",
      accepted_terms_version: "1.2",
      ai_cross_border_consent: true,
    },
  ]);
  expect(backend.csrfRequests).toBe(0);
  for (const headers of backend.writeHeaders) {
    expect(headers["x-csrf-token"]).toBeUndefined();
    expect(headers["accept-language"]).toBe("uz");
  }
  await expect(page.getByText("Do'kon yaratildi:")).toBeVisible();
  await expect(page.getByText(/sinov 16\.11\.2026 gacha/)).toBeVisible();

  // ③ Excel/CSV embeds the catalog import flow; Foto (AI) is not available yet.
  await expect(page.getByRole("button", { name: /Foto \(AI\)/ })).toBeDisabled();
  await page.getByRole("button", { name: /Excel \/ CSV/ }).click();
  await expect(page.getByRole("button", { name: /Excel \/ CSV/ })).toHaveAttribute("aria-pressed", "true");
  await next(page).click();

  // ④ skip, ⑤ next, ⑥ install guide (embedded), «Yakunlash».
  await expect(page.getByRole("heading", { level: 1, name: "Boshlang'ich qarzlar" })).toBeVisible();
  await page.getByRole("button", { name: "O'tkazib yuborish" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "OFD va e-faktura" })).toBeVisible();
  await page.getByText("Hozir ulashni istaysizmi?").click();
  await expect(page.getByText("Ulash tartibi")).toBeVisible();
  await next(page).click();
  await expect(page.getByRole("heading", { level: 1, name: "Qurilmani o'rnatish" })).toBeVisible();
  await expect(page.getByText("6-bosqich / 6")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bulut printer" })).toBeVisible();
  await page.getByRole("button", { name: "Yakunlash" }).click();

  await expect(page).toHaveURL(/\/app\/dashboard$/);
  await expect(page.getByText("Xayrli kun, Akmal")).toBeVisible();
  expect(violations).toEqual([]);
});

test("signup: phone already registered → back to ① with login / recovery links", async ({ page }) => {
  await stubBackend(page, {
    signup: () => ({
      status: 422,
      body: envelope("VALIDATION_ERROR", "errors.validation", [
        { field: "phone", message_key: "validation.phone_taken" },
      ]),
    }),
  });
  await page.goto("/onboarding");
  await verifyPhone(page);
  await page.getByRole("textbox", { name: "Parol", exact: true }).fill("Secret-pass-1");
  await page.getByLabel("Ism").fill("Akmal");
  await next(page).click();
  await page.getByLabel("Do'kon nomi").fill("Baraka");
  await page.getByRole("checkbox", { name: /Foydalanish shartlariga roziman/ }).click();
  await next(page).click();

  await expect(page.getByRole("heading", { level: 1, name: "Hisob yaratish" })).toBeVisible();
  await expect(
    page.getByText("Bu raqam allaqachon ro'yxatdan o'tgan. Tizimga kiring yoki parolni tiklang."),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Parolni tiklash" })).toHaveAttribute("href", "/recover");
  // A new code is needed for a different number.
  await expect(page.getByRole("button", { name: "Kod olish" })).toBeVisible();
});

test("signup: Google path asks phone + name only and sends no password", async ({ page }) => {
  const backend = await stubBackend(page);
  await enableGoogle(page);
  await page.goto("/onboarding");
  await expect(page.getByRole("link", { name: /Google bilan kirish/ })).toHaveAttribute(
    "href",
    "/auth/google/start?return_to=%2F",
  );

  await page.goto("/onboarding?method=google");
  await expect(page.getByText(/Google hisobingiz tasdiqlandi/)).toBeVisible();
  await verifyPhone(page);
  await expect(page.getByRole("textbox", { name: "Parol", exact: true })).toHaveCount(0);
  await page.getByLabel("Ism").fill("Akmal");
  await next(page).click();
  await page.getByLabel("Do'kon nomi").fill("Baraka");
  await page.getByRole("checkbox", { name: /Foydalanish shartlariga roziman/ }).click();
  await next(page).click();
  await expect(page.getByRole("heading", { level: 1, name: "Tovarlar" })).toBeVisible();
  expect(backend.signupBodies[0]).not.toHaveProperty("password");
  expect(backend.signupBodies[0]).toMatchObject({ owner_name: "Akmal", ai_cross_border_consent: false });
});

test("signup page in Russian", async ({ page }) => {
  await stubBackend(page);
  await page.goto("/onboarding");
  await page.getByRole("button", { name: "RU" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Создание аккаунта" })).toBeVisible();
  await expect(page.getByText("30 дней бесплатно", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Получить код" })).toBeVisible();
});

test("login page: Google button, recovery / invite links, Google callback errors", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: envelope("UNAUTHORIZED", "errors.unauthorized"),
    }),
  );
  await enableGoogle(page);
  await page.goto("/login?next=%2Fapp%2Fdebts");
  await expect(page.getByRole("link", { name: /Google bilan kirish/ })).toHaveAttribute(
    "href",
    "/auth/google/start?return_to=%2Fapp%2Fdebts",
  );
  await expect(page.getByRole("link", { name: "Parolni unutdim" })).toHaveAttribute("href", "/recover");
  await expect(page.getByRole("link", { name: "Taklif kodi bor" })).toHaveAttribute("href", "/invite");
  await expect(page.getByRole("link", { name: "Ro'yxatdan o'ting" })).toHaveAttribute("href", "/onboarding");

  // Google not configured on the backend (or the exchange failed) → /login?error=google_auth_failed.
  await page.goto("/login?error=google_auth_failed");
  await expect(page.getByText(/Google orqali kirish amalga oshmadi yoki hozircha mavjud emas/)).toBeVisible();
  await page.goto("/login?error=google_email_not_verified");
  await expect(page.getByText(/email manzili tasdiqlanmagan/)).toBeVisible();
  await page.goto("/login?error=tenant_required");
  await expect(page.getByText(/bir nechta do'konga a'zosiz/)).toBeVisible();
});
