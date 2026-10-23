/**
 * CardTerminalPanel / CardManualConfirm (07 POS-03, 08 §7.2) — component level of QT-M01-35 (the Playwright e2e
 * runs on the POS-03 screen in wave 2): steps, chip, «terminaldan keladi», button states, timer, and no input
 * that could accept card data anywhere (PCI, 15 §9.3).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";

import { initI18n } from "@shared/i18n";
import type { CardResult } from "@shared/lib/card-terminal";
import type { Money } from "@shared/lib/money";

import { IDLE, type CardAttemptState } from "../model/types/index.ts";
import { CardManualConfirm } from "./CardManualConfirm.tsx";
import { CardTerminalPanel } from "./CardTerminalPanel.tsx";

beforeAll(async () => {
  await initI18n("uz").changeLanguage("uz");
});

const noop = () => undefined;
const terminal = {
  id: "t-1",
  name: "Kassa 1 — Sunmi P3",
  adapter: "agent_ecr" as const,
  driver: "rahmat_lan",
  local_id: "term-1",
  tid: "T0000001",
};
const pending: CardAttemptState = {
  ...IDLE,
  phase: "pending",
  amount: "12000.00" as Money,
  attemptId: "a-1",
  terminal,
  terminalStatus: "online",
  sentAt: 0,
};
const approvedResult: CardResult = {
  attempt_id: "a-1",
  card_terminal_id: "t-1",
  kind: "purchase",
  original_attempt_id: null,
  status: "approved",
  amount: "12000.00" as Money,
  approval_code: "A1B2C3",
  rrn: "612345678901",
  stan: null,
  card_mask: "8600****1234",
  card_scheme: "uzcard",
  card_type: "unknown",
  card_type_source: "bin_table",
  entry_mode: "chip",
  tid: "T0000001",
  mid: null,
  acquirer: null,
  tx_at: null,
  resolved_by: "auto",
  decline_code: null,
  decline_message: null,
  slip_text: null,
};

const render = (attempt: CardAttemptState, elapsedS = 18) =>
  renderToStaticMarkup(
    <CardTerminalPanel
      attempt={attempt}
      elapsedS={elapsedS}
      onCancel={noop}
      onRetry={noop}
      onCheckStatus={noop}
      onManagerResolve={noop}
      onManual={noop}
    />,
  );

function button(html: string, label: string): string {
  const m = new RegExp(`<button[^>]*>(?:(?!</button>).)*${label}`).exec(html);
  if (!m) throw new Error(`button ${label} not found`);
  return m[0];
}

describe("CardTerminalPanel — POS-03 card waiting state (test_qt_m01_35 component level)", () => {
  it("waiting: chip, steps ① done ② active, fields «terminaldan keladi», cancel on / retry off, timer", () => {
    const html = render(pending);
    expect(html).toContain("Wi-Fi · ulangan");
    expect(html).toContain("Summa terminalga yuborildi");
    expect(html).toMatch(/data-state="done"[^>]*>.*Summa yuborildi/);
    expect(html).toMatch(/aria-current="step" data-state="active"[^>]*>.*Mijoz kartani tegizadi/);
    expect(html.match(/terminaldan keladi/g)).toHaveLength(2);
    expect(html).toContain("terminal / BIN jadvalidan");
    expect(button(html, "Terminalda bekor qilish")).not.toContain(' disabled=""');
    expect(button(html, "Qayta yuborish")).toContain(' disabled=""');
    expect(html).toContain("Kutish: 00:18 / 02:00");
    expect(html).toContain("Simsiz tarmoq orqali · Do&#x27;kon agenti");
    expect(html).not.toMatch(/<input|<textarea|contenteditable/i); // PCI: no card input
  });

  it("approved: ③ done, fields filled from the terminal, card type label", () => {
    const html = render({ ...pending, phase: "approved", result: approvedResult });
    expect(html).toContain("To&#x27;lov tasdiqlandi");
    expect(html).toContain("8600****1234");
    expect(html).toContain("612345678901 / A1B2C3");
    expect(html).toContain("Noma&#x27;lum");
    expect(html).toMatch(/data-state="done"[^>]*>.*Bank javobi/);
    expect(html).not.toMatch(/<input/i);
  });

  it("declined: reason shown, retry on; unknown: check / manager buttons, retry off", () => {
    const declined = render({
      ...pending,
      phase: "declined",
      errorCode: "CARD_DECLINED",
      result: {
        ...approvedResult,
        status: "declined",
        decline_message: "Mablag' yetarli emas",
        rrn: null,
        card_mask: null,
      },
    });
    expect(declined).toContain("Mablag&#x27; yetarli emas");
    expect(button(declined, "Qayta yuborish")).not.toContain(' disabled=""');
    const unknown = render({
      ...pending,
      phase: "unknown",
      errorCode: "CARD_OUTCOME_UNKNOWN",
      terminalStatus: "unknown",
    });
    expect(unknown).toContain("Terminal javobini tekshiring");
    expect(unknown).toContain("Tekshirilmoqda");
    expect(unknown).toContain("Menejer tasdig&#x27;i bilan yopish");
    expect(button(unknown, "Qayta yuborish")).toContain(' disabled=""');
    expect(button(unknown, "Terminalda bekor qilish")).toContain(' disabled=""');
  });

  it("unavailable terminal offers the manual card, mismatch / void failed texts come from the catalog", () => {
    const html = render({
      ...pending,
      phase: "unavailable",
      errorCode: "CARD_TERMINAL_UNREACHABLE",
      terminalStatus: "offline",
    });
    expect(html).toContain("Ulanmagan");
    expect(html).toContain("Karta terminalsiz");
    expect(render({ ...pending, phase: "declined", errorCode: "CARD_AMOUNT_MISMATCH" })).toContain(
      "mos emas",
    );
    expect(
      render({ ...pending, phase: "approved", errorCode: "CARD_VOID_FAILED", result: approvedResult }),
    ).toContain("bekor qilib bo");
  });
});

describe("CardManualConfirm — terminalsiz karta has no card fields (qaror #64)", () => {
  it("only amount, reason and one confirm button", () => {
    const html = renderToStaticMarkup(
      <CardManualConfirm
        amount={"12000.00" as Money}
        manualReason="terminal_offline"
        requiresApproval
        errorCode={null}
        onConfirm={noop}
      />,
    );
    expect(html).toContain("Karta terminalsiz qabul qilindi");
    expect(html).toContain("Terminal ulanmagan");
    expect(html).toContain("Menejer tasdig&#x27;i kerak");
    expect(html).not.toMatch(/<input|<select|<textarea/i);
    expect(html.match(/<button/g)).toHaveLength(1);
  });
});
