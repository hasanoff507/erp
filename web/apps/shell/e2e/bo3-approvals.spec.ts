import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-16 «Tasdiqlash navbati» (B3-SCR-BO-16, B3-T15 web; 18 §9.3–§9.5) and the WEB-12 pending badge on
 * the sidebar item, on the production build: approve with the approver's PIN (step-up — PIN_INVALID,
 * ACCOUNT_LOCKED), reject with a mandatory reason, Idempotency-Key + CSRF on decisions, own request
 * without controls. Backend stubbed per test.
 */
const session = {
  user: { id: "u-mgr", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["manager"],
  permissions: ["discount.approve", "cash.withdraw", "returns.approve"],
  scope: ["discount", "cash", "returns"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

type Body = Record<string, unknown>;

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function minutesFromNow(m: number): string {
  return new Date(Date.now() + m * 60_000).toISOString();
}

function request(id: string, patch: Body = {}): Body {
  return {
    id,
    branch_id: "b-1",
    kind: "discount_over_limit",
    permission_code: "discount.approve",
    requested_value: "8.0000",
    context: { requested_pct: "8.00", amount: "38880.00" },
    linked_doc_type: "sales",
    linked_doc_id: "s-1",
    device_id: "d-1",
    status: "pending",
    requested_by: "u-cashier",
    requested_by_name: "Dilnoza Rahimova",
    requested_at: new Date().toISOString(),
    expires_at: minutesFromNow(12),
    resolved_by: null,
    resolved_at: null,
    reject_reason: null,
    consumed_at: null,
    ...patch,
  };
}

interface Decision {
  id: string;
  body: Body;
  idempotencyKey: string | undefined;
  csrf: string | undefined;
}

async function stubBackend(page: Page, { approveAnswers = [] as { status: number; body: Body }[] } = {}) {
  let queue: Body[] = [
    request("r-1"),
    request("r-2", {
      kind: "cash_withdrawal_over_limit",
      permission_code: "cash.withdraw",
      requested_value: "336000.0000",
      context: { amount: "336000.00", reason: "other", cash_register_id: "cr-1" },
      linked_doc_type: "cash_movements",
    }),
    request("r-3", { requested_by: "u-mgr", requested_by_name: "Akmal Karimov" }),
  ];
  const resolved: Body[] = [];
  const approvals: Decision[] = [];
  const rejections: Decision[] = [];
  const answers = [...approveAnswers];

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/approval-requests" && method === "GET") {
      const status = url.searchParams.get("status");
      if (status === "pending") return json(route, 200, { items: queue, next_cursor: null });
      return json(route, 200, { items: resolved.filter((r) => r.status === status), next_cursor: null });
    }
    const decide = /^\/api\/v1\/approval-requests\/(r-\d)\/(approve|reject)$/.exec(path);
    if (decide && method === "POST") {
      const id = decide[1] ?? "";
      const decision: Decision = {
        id,
        body: req.postDataJSON() as Body,
        idempotencyKey: req.headers()["idempotency-key"],
        csrf: req.headers()["x-csrf-token"],
      };
      if (decide[2] === "approve") {
        approvals.push(decision);
        const answer = answers.shift();
        if (answer) return json(route, answer.status, answer.body);
        const done = { id, status: "approved", resolved_by: "u-mgr", resolved_at: new Date().toISOString() };
        const original = queue.find((r) => r.id === id) ?? {};
        resolved.push({ ...original, ...done });
        queue = queue.filter((r) => r.id !== id);
        return json(route, 200, done);
      }
      rejections.push(decision);
      const original = queue.find((r) => r.id === id) ?? {};
      resolved.push({
        ...original,
        status: "rejected",
        resolved_at: new Date().toISOString(),
        reject_reason: decision.body.reason,
      });
      queue = queue.filter((r) => r.id !== id);
      return json(route, 200, { id, status: "rejected" });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });
  return { approvals, rejections };
}

const pinInvalid = {
  status: 400,
  body: { error: { code: "PIN_INVALID", message_key: "errors.pin_invalid", details: [] } },
};
const locked = {
  status: 423,
  body: {
    error: {
      code: "ACCOUNT_LOCKED",
      message_key: "errors.account_locked",
      params: { retry_after_s: 290 },
      details: [],
    },
  },
};

test("B3-T15 BO-16: pending queue, PIN_INVALID then approve with the right PIN (Idempotency-Key + CSRF)", async ({
  page,
}) => {
  const backend = await stubBackend(page, { approveAnswers: [pinInvalid] });
  await page.goto("/app/approvals");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Tasdiqlash navbati" })).toBeVisible();

  // WEB-12: the sidebar item carries the pending count.
  await expect(
    page.getByRole("navigation", { name: "Asosiy menyu" }).getByText("Kutilayotgan so'rovlar: 3"),
  ).toBeAttached();

  const discount = page
    .getByRole("article")
    .filter({ hasText: "Chegirma — 8%" })
    .filter({ hasText: "Dilnoza Rahimova" });
  await expect(discount).toContainText("Dilnoza Rahimova · Chilonzor-3");
  await expect(discount).toContainText("Sotuv (chek)");
  await expect(discount).toContainText(/1[12] daq qoldi/);
  await expect(page.getByRole("tab", { name: "Kutilmoqda (3)" })).toBeVisible();

  // Own request: no PIN, no buttons (QT-PERM-06).
  const own = page.getByRole("article").filter({ hasText: "Akmal Karimov" });
  await expect(own).toContainText("Bu sizning so'rovingiz");
  await expect(own.getByLabel("PIN")).toHaveCount(0);

  const pin = discount.getByLabel("PIN");
  await expect(discount.getByRole("button", { name: "Tasdiqlash" })).toBeDisabled();
  await pin.fill("9999");
  await pin.press("Enter");
  await expect(discount.getByRole("alert")).toHaveText("PIN noto'g'ri");
  await expect(pin).toHaveValue("");

  await pin.fill("1234");
  await discount.getByRole("button", { name: "Tasdiqlash" }).click();
  await expect(discount).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Bugun hal qilinganlar" })).toContainText("Tasdiqlandi");

  expect(backend.approvals.map((a) => a.body)).toEqual([{ pin: "9999" }, { pin: "1234" }]);
  expect(backend.approvals[1]?.idempotencyKey).toBeTruthy();
  expect(backend.approvals[1]?.csrf).toBe("csrf-e2e");
});

test("BO-16: too many wrong PINs → ACCOUNT_LOCKED with minutes", async ({ page }) => {
  await stubBackend(page, { approveAnswers: [locked] });
  await page.goto("/app/approvals");
  const card = page.getByRole("article").filter({ hasText: "Chegirma — 8%" }).filter({ hasText: "Dilnoza" });
  await card.getByLabel("PIN").fill("0000");
  await card.getByRole("button", { name: "Tasdiqlash" }).click();
  await expect(card.getByRole("alert")).toHaveText(
    "PIN urinishlari tugadi — 5 daqiqadan keyin qayta urinib ko'ring",
  );
});

test("BO-16: reject requires a reason; kind chip filters the queue", async ({ page }) => {
  const backend = await stubBackend(page);
  await page.goto("/app/approvals");

  await page
    .getByRole("group", { name: "So'rov turi" })
    .getByRole("button", { name: /Pul olish/ })
    .click();
  await expect(page.getByRole("article")).toHaveCount(1);
  const card = page.getByRole("article").filter({ hasText: "Pul olish — 336" });
  await expect(card).toContainText("Kassa pul harakati");
  await expect(card).not.toContainText("cr-1");

  await card.getByRole("button", { name: "Rad etish" }).click();
  await card.getByRole("button", { name: "Rad etishni yuborish" }).click();
  await expect(card.getByText("Rad etish sababini yozing")).toBeVisible();
  expect(backend.rejections).toHaveLength(0);

  await card.getByLabel("Rad etish sababi (majburiy)").fill("Bank orqali to'lansin");
  await card.getByRole("button", { name: "Rad etishni yuborish" }).click();
  await expect(page.getByRole("article").filter({ hasText: "Pul olish — 336" })).toHaveCount(0);
  expect(backend.rejections.map((r) => r.body)).toEqual([{ reason: "Bank orqali to'lansin" }]);
  expect(backend.rejections[0]?.idempotencyKey).toBeTruthy();

  await page.getByRole("tab", { name: "Rad etilgan" }).click();
  // UX-14: the pending tab keeps its count on the other tabs (3 − 1 rejected).
  await expect(page.getByRole("tab", { name: "Kutilmoqda (2)" })).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "Bank orqali to'lansin" })).toBeVisible();
});

test("BO-16: a user without any approver right gets no menu item and no access", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    json(route, 200, { ...session, permissions: ["sales.create"], scope: ["sales"] }),
  );
  await page.route("**/api/v1/**", (route) => json(route, 200, { items: [], next_cursor: null }));
  await page.goto("/app/approvals");
  await expect(page.getByText("Sizda bu bo'limga kirish huquqi yo'q")).toBeVisible();
  await expect(page.getByRole("link", { name: "Tasdiqlash navbati" })).toHaveCount(0);
});
