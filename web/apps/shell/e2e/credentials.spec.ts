import { expect, test, type Page } from "@playwright/test";

/**
 * `/recover` and `/invite` (linked from the AS login page, backend auth/api/login_page.py):
 * phone → POST /auth/otp/request (recovery) → POST /auth/otp/verify → credential_token →
 * POST /auth/credentials → 204 → «Tizimga kirish». An invite link carries `?challenge_id=` and starts
 * at the code. Backend stubbed (OtpRequestOut / OtpVerifyOut / CredentialsIn shapes).
 */
const CHALLENGE = "0192a0f0-0000-7000-8000-0000000000d1";
const TOKEN = "cred-token-0123456789abcdef";

const envelope = (code: string, key: string, details: { field: string; message_key: string }[] = []) =>
  JSON.stringify({ error: { code, message_key: key, details, request_id: "e2e" } });

interface Calls {
  otp: unknown[];
  verify: unknown[];
  credentials: unknown[];
}

async function stub(
  page: Page,
  kinds: ("password" | "pin")[],
  credentials: () => { status: number; body?: string } = () => ({ status: 204 }),
): Promise<Calls> {
  const calls: Calls = { otp: [], verify: [], credentials: [] };
  await page.route("**/auth/session", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: envelope("UNAUTHORIZED", "errors.unauthorized"),
    }),
  );
  await page.route("**/auth/otp/request", (route) => {
    calls.otp.push(route.request().postDataJSON());
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        challenge_id: CHALLENGE,
        channel_used: "sms",
        expires_at: "2026-10-17T10:05:00Z",
        warnings: [],
      }),
    });
  });
  await page.route("**/auth/otp/verify", (route) => {
    const body = route.request().postDataJSON() as { code: string };
    calls.verify.push(body);
    if (body.code !== "123456") {
      return route.fulfill({
        status: 400,
        contentType: "application/json",
        body: envelope("OTP_EXPIRED", "errors.otp_expired"),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        challenge_id: CHALLENGE,
        purpose: kinds.includes("pin") ? "invite" : "recovery",
        verified: true,
        credential_token: TOKEN,
        credential_token_expires_in: 600,
        credential_kinds: kinds,
      }),
    });
  });
  await page.route("**/auth/credentials", (route) => {
    calls.credentials.push(route.request().postDataJSON());
    const answer = credentials();
    return route.fulfill({ status: answer.status, contentType: "application/json", body: answer.body ?? "" });
  });
  return calls;
}

const codeBoxes = (page: Page) => page.getByRole("group", { name: "Tasdiqlash kodi" }).getByRole("textbox");

test("/recover: phone → code → new password → login", async ({ page }) => {
  const calls = await stub(page, ["password"]);
  await page.goto("/recover");
  await expect(page.getByRole("heading", { level: 1, name: "Parolni tiklash" })).toBeVisible();

  await page.getByLabel("Telefon").fill("901234567");
  await page.getByLabel("Telefon").press("Enter");
  await expect(page.getByText(/kod \+998 90 123 45 67 raqamiga SMS orqali yuboriladi/)).toBeVisible();
  expect(calls.otp).toEqual([{ phone: "+998901234567", purpose: "recovery" }]);

  await codeBoxes(page).first().fill("999999");
  await expect(page.getByText("Tasdiqlash kodi muddati o'tgan, qayta so'rang")).toBeVisible();
  await codeBoxes(page).first().fill("123456");

  await expect(page.getByRole("textbox", { name: "Yangi parol" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "PIN kod" })).toHaveCount(0);
  await page.getByRole("textbox", { name: "Yangi parol" }).fill("New-secret-1");
  await page.getByRole("textbox", { name: "Parolni takrorlang" }).fill("New-secret-2");
  await page.getByRole("button", { name: "Saqlash" }).click();
  await expect(page.getByText("Parollar mos kelmadi")).toBeVisible();
  await page.getByRole("textbox", { name: "Parolni takrorlang" }).fill("New-secret-1");
  await page.getByRole("button", { name: "Saqlash" }).click();

  await expect(page.getByText(/Yangi parol o'rnatildi/)).toBeVisible();
  expect(calls.credentials).toEqual([{ credential_token: TOKEN, password: "New-secret-1" }]);
  await expect(page.getByRole("link", { name: "Tizimga kirish" })).toHaveAttribute(
    "href",
    "/auth/login/start?return_to=%2F",
  );
});

test("/recover: an expired credential session starts over", async ({ page }) => {
  await stub(page, ["password"], () => ({
    status: 401,
    body: envelope("UNAUTHORIZED", "errors.unauthorized"),
  }));
  await page.goto("/recover");
  await page.getByLabel("Telefon").fill("901234567");
  await page.getByRole("button", { name: "Kod olish" }).click();
  await codeBoxes(page).first().fill("123456");
  await page.getByRole("textbox", { name: "Yangi parol" }).fill("New-secret-1");
  await page.getByRole("textbox", { name: "Parolni takrorlang" }).fill("New-secret-1");
  await page.getByRole("button", { name: "Saqlash" }).click();
  await expect(page.getByText(/Tasdiqlash muddati tugadi/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Kod olish" })).toBeVisible();
});

test("/invite link: code → password and PIN", async ({ page }) => {
  const calls = await stub(page, ["password", "pin"]);
  await page.goto(`/invite?challenge_id=${CHALLENGE}`);
  await expect(page.getByRole("heading", { level: 1, name: "Taklif kodi" })).toBeVisible();
  await expect(page.getByText("Taklif xabaridagi 6 raqamli kodni kiriting.")).toBeVisible();
  expect(calls.otp).toEqual([]);

  await codeBoxes(page).first().fill("123456");
  await expect(page.getByRole("textbox", { name: "PIN kod" })).toBeVisible();
  expect(calls.verify).toEqual([{ challenge_id: CHALLENGE, code: "123456" }]);
  await page.getByRole("textbox", { name: "PIN kod" }).fill("12");
  await page.getByRole("button", { name: "Saqlash" }).click();
  await expect(page.getByText("PIN 4–6 raqamdan iborat bo'lsin")).toBeVisible();
  await page.getByRole("textbox", { name: "PIN kod" }).fill("2468");
  await page.getByRole("button", { name: "Saqlash" }).click();
  await expect(page.getByText(/Kirish ma'lumotlaringiz saqlandi/)).toBeVisible();
  expect(calls.credentials).toEqual([{ credential_token: TOKEN, pin: "2468" }]);
});

test("/invite: phone + code type + code → verify by phone/purpose → PIN only", async ({ page }) => {
  const calls = await stub(page, ["pin"]);
  await page.goto("/invite?challenge_id=not-a-uuid");
  await expect(page.getByText(/6 raqamli kodni kiriting/)).toBeVisible();
  await expect(page.getByRole("link", { name: /Yangi kod olish/ })).toHaveAttribute("href", "/recover");

  await page.getByLabel("Telefon").fill("901234567");
  await page.getByRole("combobox", { name: "Kod turi" }).click();
  await page.getByRole("option", { name: "PIN tiklash kodi (Egasidan)" }).click();
  await codeBoxes(page).first().fill("123456");

  await expect(page.getByRole("textbox", { name: "PIN kod" })).toBeVisible();
  expect(calls.otp).toEqual([]);
  expect(calls.verify).toEqual([{ phone: "+998901234567", purpose: "pin_reset", code: "123456" }]);
  await expect(page.getByRole("textbox", { name: "Yangi parol" })).toHaveCount(0);
  await page.getByRole("textbox", { name: "PIN kod" }).fill("1357");
  await page.getByRole("button", { name: "Saqlash" }).click();
  await expect(page.getByText(/Kirish ma'lumotlaringiz saqlandi/)).toBeVisible();
  expect(calls.credentials).toEqual([{ credential_token: TOKEN, pin: "1357" }]);
});

test("/invite: unknown phone or wrong code type → OTP_EXPIRED message, default type is invite", async ({
  page,
}) => {
  const calls = await stub(page, ["password"]);
  await page.goto("/invite");
  await page.getByLabel("Telefon").fill("901234567");
  await codeBoxes(page).first().fill("999999");
  await expect(page.getByText("Tasdiqlash kodi muddati o'tgan, qayta so'rang")).toBeVisible();
  expect(calls.verify).toEqual([{ phone: "+998901234567", purpose: "invite", code: "999999" }]);
});

test("/invite for an existing user: invite accepted → sign in with the existing password", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: envelope("UNAUTHORIZED", "errors.unauthorized"),
    }),
  );
  const verify: unknown[] = [];
  let attempts = 0;
  await page.route("**/auth/otp/verify", (route) => {
    verify.push(route.request().postDataJSON());
    attempts += 1;
    if (attempts === 1) {
      return route.fulfill({
        status: 429,
        contentType: "application/json",
        headers: { "Retry-After": "120" },
        body: JSON.stringify({
          error: {
            code: "RATE_LIMITED",
            message_key: "errors.rate_limited",
            params: { retry_after_s: 120, scope: "otp_verify_ip" },
            details: [],
            request_id: "e2e",
          },
        }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        challenge_id: CHALLENGE,
        purpose: "invite",
        verified: true,
        credential_token: null,
        credential_token_expires_in: null,
        credential_kinds: null,
        invite_accepted: true,
      }),
    });
  });
  const credentials: unknown[] = [];
  await page.route("**/auth/credentials", (route) => {
    credentials.push(route.request().postDataJSON());
    return route.fulfill({ status: 204 });
  });

  await page.goto("/invite");
  await page.getByLabel("Telefon").fill("901234567");
  await codeBoxes(page).first().fill("123456");
  await expect(page.getByText("Juda ko'p urinish. 2 daqiqadan keyin qayta urinib ko'ring")).toBeVisible();

  await page.getByRole("button", { name: "Tasdiqlash" }).click();
  await expect(page.getByText("Taklif qabul qilindi — mavjud parolingiz bilan kiring.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Tizimga kirish" })).toHaveAttribute(
    "href",
    "/auth/login/start?return_to=%2F",
  );
  await expect(page.getByRole("textbox", { name: "Yangi parol" })).toHaveCount(0);
  expect(verify).toEqual([
    { phone: "+998901234567", purpose: "invite", code: "123456" },
    { phone: "+998901234567", purpose: "invite", code: "123456" },
  ]);
  expect(credentials).toEqual([]);
});
