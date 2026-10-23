import { fork } from "effector";
import { Provider } from "effector-react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";
import { initI18n } from "@shared/i18n";

import { $approveErrors, $now, type ApprovalRequest } from "../../model/index.ts";
import { pinError } from "./errors.ts";
import { RequestCard } from "./RequestCard.tsx";

const NOW = Date.parse("2026-10-17T10:00:00Z");

const pending: ApprovalRequest = {
  id: "r-1",
  branch_id: "b-1",
  kind: "cash_withdrawal_over_limit",
  permission_code: "cash.withdraw",
  requested_value: "336000.0000",
  context: { amount: "336000.00", reason: "other", cash_register_id: "cr-1", shift_id: "s-1" },
  linked_doc_type: "cash_movements",
  linked_doc_id: "m-1",
  device_id: null,
  status: "pending",
  requested_by: "u-2",
  requested_by_name: "Dilnoza R.",
  requested_at: "2026-10-17T09:50:00Z",
  expires_at: "2026-10-17T10:04:00Z",
  resolved_by: null,
  resolved_at: null,
  reject_reason: null,
  consumed_at: null,
};

beforeAll(async () => {
  await initI18n("uz").changeLanguage("uz");
});

function render(request: ApprovalRequest, own = false, errors: Record<string, ApiError> = {}) {
  const scope = fork({
    values: [
      [$now, NOW],
      [$approveErrors, errors],
    ],
  });
  return renderToStaticMarkup(
    <Provider value={scope}>
      <RequestCard request={request} branchName="Chilonzor-3" own={own} online />
    </Provider>,
  );
}

describe("BO-16 request card", () => {
  it("pending request of someone else: details, time left, PIN + approve/reject; no raw ids", () => {
    const html = render(pending);
    expect(html).toContain("Pul olish — 336");
    expect(html).toContain("Dilnoza R. · Chilonzor-3");
    expect(html).toContain("4 daq qoldi");
    expect(html).toContain("Kassa pul harakati");
    expect(html).toContain("Boshqa");
    expect(html).toContain('type="password"');
    expect(html).toContain("Tasdiqlash");
    expect(html).toContain("Rad etish");
    expect(html).not.toContain("cr-1");
    expect(html).not.toContain("s-1");
  });

  it("own request: no decision controls (QT-PERM-06)", () => {
    const html = render(pending, true);
    expect(html).toContain("Bu sizning so&#x27;rovingiz");
    expect(html).not.toContain('type="password"');
  });

  it("PIN errors: invalid / must change / locked with minutes", () => {
    const html = render(pending, false, {
      "r-1": new ApiError({ status: 400, code: "PIN_INVALID", messageKey: "errors.pin_invalid" }),
    });
    expect(html).toContain("PIN noto&#x27;g&#x27;ri");
    expect(html).toContain('aria-invalid="true"');
    expect(
      pinError(
        new ApiError({
          status: 400,
          code: "PIN_INVALID",
          messageKey: "x",
          params: { reason: "must_change_pin" },
        }),
      ),
    ).toEqual({ kind: "mustChange" });
    expect(
      pinError(
        new ApiError({
          status: 423,
          code: "ACCOUNT_LOCKED",
          messageKey: "x",
          params: { retry_after_s: 290 },
        }),
      ),
    ).toEqual({ kind: "locked", minutes: 5 });
    expect(pinError(new ApiError({ status: 423, code: "ACCOUNT_LOCKED", messageKey: "x" }))).toEqual({
      kind: "locked",
      minutes: null,
    });
    expect(pinError(new ApiError({ status: 409, code: "APPROVAL_INVALID", messageKey: "x" }))).toBeNull();
  });

  it("a resolved request shows its result, not the controls", () => {
    const html = render({
      ...pending,
      status: "rejected",
      resolved_at: "2026-10-17T09:58:00Z",
      reject_reason: "Bank orqali to'lansin",
    });
    expect(html).toContain("Rad etildi");
    expect(html).toContain("Bank orqali to");
    expect(html).not.toContain('type="password"');
  });
});
