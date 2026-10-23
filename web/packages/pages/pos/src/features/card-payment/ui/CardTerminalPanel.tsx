/**
 * CardTerminalPanel (07 POS-03, 08 §7.2; qaror #71): header + hint + TerminalStatusChip, terminal line,
 * 4-step StepIndicator, read-only result fields («terminaldan keladi» until the answer), «Terminalda bekor
 * qilish» / «Qayta yuborish», countdown «Kutish: mm:ss / 02:00» and the PCI note. Purely presentational —
 * there is NO input of any kind in this component (PCI: card data is never typed in).
 */
import { CircleAlert, Clock, CreditCard, Info, RefreshCw, ShieldCheck } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { Banner, Button, Icon, cn } from "@shared/ui";

import { clock } from "../model/lib/index.ts";
import { PURCHASE_LIMIT_S, type CardAttemptState } from "../model/types/index.ts";
import { StepIndicator, type Step, type StepState } from "./StepIndicator.tsx";
import { TerminalStatusChip } from "./TerminalStatusChip.tsx";
import { codeText, dyn, type DynamicT } from "./i18n.ts";

export interface CardTerminalPanelProps {
  attempt: CardAttemptState;
  elapsedS: number;
  onCancel: () => void;
  onRetry: () => void;
  onCheckStatus: () => void;
  onManagerResolve: () => void;
  onManual: () => void;
  /** SYNC-03 (phase `dangling`): attach to the current receipt — only when the amounts match */
  attachable?: boolean;
  onAttach?: () => void;
  onVoidDangling?: () => void;
}

function steps(s: CardAttemptState, t: DynamicT, sentLabel: string): Step[] {
  const p = s.phase;
  const state = (done: boolean, active: boolean, error = false): StepState =>
    error ? "error" : done ? "done" : active ? "active" : "next";
  const sent = p !== "idle" && p !== "checking" && p !== "unavailable";
  const answered =
    p === "approved" || p === "declined" || p === "voided" || p === "void_failed" || p === "voiding";
  const failed = p === "declined" || p === "void_failed" || p === "voiding";
  return [
    { title: t("cardPayment.steps.sent"), sub: sentLabel, state: state(sent, p === "checking") },
    {
      title: t("cardPayment.steps.tap"),
      sub: t("cardPayment.steps.tapSub"),
      state: state(answered || p === "unknown", p === "pending"),
    },
    {
      title: t("cardPayment.steps.bank"),
      sub: t("cardPayment.steps.bankSub"),
      state: state(p === "approved" || p === "dangling", p === "unknown", failed),
    },
    {
      title: t("cardPayment.steps.fiscal"),
      sub: t("cardPayment.steps.fiscalSub"),
      state: state(false, p === "approved"),
    },
  ];
}

const HEADER: Partial<Record<CardAttemptState["phase"], string>> = {
  checking: "checking",
  pending: "pending",
  approved: "approved",
  declined: "declined",
  unknown: "unknown",
  voiding: "voiding",
  voided: "voided",
  void_failed: "voidFailed",
  unavailable: "unavailable",
  resolved_manual: "resolvedManual",
  dangling: "dangling",
};

export function CardTerminalPanel(props: CardTerminalPanelProps) {
  const { attempt: s, elapsedS } = props;
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const r = s.result;
  const answered =
    r !== null && (r.status === "approved" || s.phase === "approved" || s.phase === "dangling");
  const headerKey = HEADER[s.phase] ?? "checking";
  const hintKey =
    s.phase === "pending" || s.phase === "checking"
      ? "pending"
      : s.phase === "unknown"
        ? "unknown"
        : s.phase === "approved"
          ? "approved"
          : s.phase === "void_failed"
            ? "voidFailed"
            : s.phase === "unavailable"
              ? "unavailable"
              : s.phase === "resolved_manual"
                ? "resolvedManual"
                : s.phase === "dangling"
                  ? "dangling"
                  : null;
  const sentLabel = s.amount ? formatMoney(s.amount) : "";
  const errorText =
    s.errorCode === "CARD_DECLINED"
      ? codeText("CARD_DECLINED", { decline_message: r?.decline_message ?? r?.decline_code ?? "" })
      : s.errorCode === "AGENT_NOT_PAIRED"
        ? t("cardPayment.errors.unpaired")
        : s.errorCode === "FISCAL_OFFLINE_48H_BLOCKED"
          ? t("cardPayment.errors.FISCAL_OFFLINE_48H_BLOCKED")
          : s.errorCode && s.errorCode !== "CARD_OUTCOME_UNKNOWN"
            ? codeText(s.errorCode)
            : null;
  const field = (label: string, value: string | null, placeholder: string, testId: string) => (
    <div
      className={cn(
        "min-w-0 rounded-lg border bg-card px-3 py-2",
        value ? "border-border" : "border-dashed border-input",
      )}
    >
      <div className="text-[12px] text-muted-foreground">{label}</div>
      <div
        data-testid={testId}
        className={cn(
          "truncate text-[13px] font-bold",
          value ? "text-foreground" : "text-foreground-secondary",
        )}
      >
        {value ?? placeholder}
      </div>
    </div>
  );
  const terminal = s.terminal;
  const limit = clock(PURCHASE_LIMIT_S);

  return (
    <section
      aria-labelledby="card-panel-title"
      data-testid="card-terminal-panel"
      data-phase={s.phase}
      className="flex flex-col gap-2.5 rounded-xl border border-border bg-muted/40 p-4"
    >
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary-strong">
          <Icon as={CreditCard} />
        </span>
        <div className="min-w-0 grow">
          <h2 id="card-panel-title" className="text-[17px] font-extrabold">
            {t(`cardPayment.header.${headerKey}`)}
          </h2>
          {hintKey ? (
            <p className="text-[13px] text-foreground-secondary">{t(`cardPayment.hint.${hintKey}`)}</p>
          ) : null}
        </div>
        <TerminalStatusChip status={s.terminalStatus} />
      </div>

      {terminal ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-[13px]">
          <span className="text-foreground-secondary">
            {t("cardPayment.terminalLine", { name: terminal.name, tid: terminal.tid ?? "—" })}
          </span>
          <span className="text-muted-foreground">{t(`cardPayment.transport.${terminal.adapter}`)}</span>
        </div>
      ) : null}

      <StepIndicator steps={steps(s, t, sentLabel)} label={t("cardPayment.steps.label")} />

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {field(
          t("cardPayment.fields.mask"),
          answered ? (r?.card_mask ?? null) : null,
          t("cardPayment.fields.fromTerminal"),
          "card-field-mask",
        )}
        {field(
          t("cardPayment.fields.rrn"),
          answered && r?.rrn ? `${r.rrn}${r.approval_code ? ` / ${r.approval_code}` : ""}` : null,
          t("cardPayment.fields.fromTerminal"),
          "card-field-rrn",
        )}
        {field(
          t("cardPayment.fields.type"),
          answered && r?.card_type ? t(`cardPayment.cardType.${r.card_type}`) : null,
          t("cardPayment.fields.fromTerminalOrBin"),
          "card-field-type",
        )}
      </div>

      {errorText ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          {errorText}
        </Banner>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="destructive-outline"
          size="lg"
          disabled={s.phase !== "pending"}
          onClick={props.onCancel}
        >
          {t("cardPayment.actions.cancelOnTerminal")}
        </Button>
        <Button
          variant="secondary"
          size="lg"
          disabled={s.phase !== "declined" || s.terminal === null}
          onClick={props.onRetry}
          className="flex-col gap-0 leading-tight"
        >
          {t("cardPayment.actions.retry")}
          <span className="text-[11px] font-semibold text-muted-foreground">
            {t("cardPayment.actions.retryHint")}
          </span>
        </Button>
        {s.phase === "dangling" ? (
          <>
            <Button
              size="lg"
              disabled={!props.attachable}
              onClick={props.onAttach}
              data-testid="card-dangling-attach"
            >
              {t("cardPayment.actions.attach")}
            </Button>
            <Button
              variant="destructive-outline"
              size="lg"
              onClick={props.onVoidDangling}
              data-testid="card-dangling-void"
            >
              {t("cardPayment.actions.voidDangling")}
            </Button>
          </>
        ) : null}
        {s.phase === "unknown" ? (
          <>
            <Button variant="secondary" size="lg" onClick={props.onCheckStatus}>
              <Icon as={RefreshCw} size="sm" />
              {t("cardPayment.actions.checkStatus")}
            </Button>
            <Button variant="warning" size="lg" onClick={props.onManagerResolve}>
              <Icon as={ShieldCheck} size="sm" />
              {t("cardPayment.actions.managerResolve")}
            </Button>
          </>
        ) : null}
        {s.phase === "unavailable" || s.phase === "declined" ? (
          <Button variant="dashed" size="lg" onClick={props.onManual}>
            {t("cardPayment.actions.manual")}
          </Button>
        ) : null}
        <div className="grow" />
        <span
          role="timer"
          aria-label={t("cardPayment.timerAria", { seconds: elapsedS })}
          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-border bg-card px-3 py-1.5 text-[13px] font-bold tabular-nums"
        >
          <Icon as={Clock} size="sm" />
          <span data-testid="card-timer">{t("cardPayment.timer", { elapsed: clock(elapsedS), limit })}</span>
        </span>
      </div>

      <p
        role="note"
        className="flex items-start gap-2 rounded-lg bg-info-soft px-3.5 py-2 text-[12px] font-semibold text-info-strong"
      >
        <Icon as={Info} size="sm" className="mt-0.5 shrink-0" />
        <span>{t("cardPayment.note")}</span>
      </p>
    </section>
  );
}
