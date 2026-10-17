/**
 * One BO-16 request card (07 BO-16, mockup Bo16Tasdiqlash): kind chip + time left, title with the
 * requested value, who asked (name, branch, time), linked document, the `context` details; for a pending
 * request of someone else — PIN + «Tasdiqlash» (Enter) and «Rad etish» (reason required).
 * The PIN lives in this component only (never in a store, never logged) and is cleared after sending.
 */
import { useUnit } from "effector-react";
import { Check, Clock, X } from "lucide-react";
import { useId, useState } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney, formatPercent } from "@shared/lib/format";
import { Button, Card, Icon, Input, StatusChip, Textarea, cn, type Tone } from "@shared/ui";

import {
  $approveErrors,
  $busy,
  $now,
  $rejectErrors,
  approveSubmitted,
  contextLines,
  docTypeKey,
  isDue,
  isPinValid,
  isReasonValid,
  minutesLeft,
  pinErrorCleared,
  rejectSubmitted,
  requestedValue,
  type ApprovalRequest,
  type ContextLine,
} from "../../model/index.ts";
import { pinError, type PinError } from "./errors.ts";

const STATUS_TONE: Readonly<Record<string, Tone>> = {
  pending: "awaiting-approval",
  approved: "success",
  consumed: "success",
  rejected: "destructive",
  expired: "neutral",
};

export interface RequestCardProps {
  request: ApprovalRequest;
  branchName: string | null;
  /** The viewer asked for it themselves — no decision (QT-PERM-06). */
  own: boolean;
  online: boolean;
}

export function RequestCard({ request: r, branchName, own, online }: RequestCardProps) {
  const { t } = useTranslation("settings");
  const [now, busyIds, approveErrors, rejectErrors] = useUnit([$now, $busy, $approveErrors, $rejectErrors]);
  const [approve, reject, clearPinError] = useUnit([approveSubmitted, rejectSubmitted, pinErrorCleared]);
  const [pin, setPin] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [reasonTouched, setReasonTouched] = useState(false);
  const ids = useId();

  const busy = busyIds.includes(r.id);
  const pending = r.status === "pending" && !isDue(r, now);
  const value = requestedValue(r);
  const kind = t(`approvals.kinds.${r.kind}`);
  const valueText = value ? ("pct" in value ? formatPercent(value.pct) : formatMoney(value.amount)) : null;
  const approveError = approveErrors[r.id];
  const rejectError = rejectErrors[r.id];
  const pinText = (e: PinError): string => {
    if (e.kind === "invalid") return t("approvals.pinInvalid");
    if (e.kind === "mustChange") return t("approvals.pinMustChange");
    return e.minutes === null
      ? t("approvals.pinLocked")
      : t("approvals.pinLockedFor", { minutes: e.minutes });
  };
  const known = approveError ? pinError(approveError) : null;
  const pinErrorText = approveError ? (known ? pinText(known) : serverErrorText(approveError)) : null;
  const left = minutesLeft(r.expires_at, now);
  const canDecide = pending && !own;
  const docType = r.linked_doc_type;

  const lineText = (line: ContextLine): string => {
    switch (line.key) {
      case "reason":
        return t(`approvals.enum.reason.${line.value}`);
      case "manualReason":
        return t(`approvals.enum.manualReason.${line.value}`);
      case "lines":
        return t("approvals.linesCount", { count: line.count });
      default:
        return `«${line.value}»`;
    }
  };

  const submitApprove = () => {
    if (!online || busy || !isPinValid(pin)) return;
    approve({ id: r.id, pin });
    setPin("");
  };
  const submitReject = () => {
    setReasonTouched(true);
    if (!online || busy || !isReasonValid(reason)) return;
    reject({ id: r.id, reason });
  };
  const cancelReject = () => {
    setRejecting(false);
    setReason("");
    setReasonTouched(false);
  };

  return (
    <Card
      role="article"
      aria-labelledby={`${ids}-title`}
      className={cn("flex flex-col gap-3", pinErrorText && "border-destructive-border")}
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip tone="info">{kind}</StatusChip>
        {r.status === "pending" ? (
          <StatusChip tone={left <= 5 ? "destructive" : "warning"} icon={Clock}>
            {left > 0 ? t("approvals.minutesLeft", { count: left }) : t("approvals.due")}
          </StatusChip>
        ) : (
          <StatusChip tone={STATUS_TONE[r.status] ?? "neutral"} dot>
            {t(`approvals.status.${r.status}`)}
          </StatusChip>
        )}
        <div className="grow" />
        <span className="text-[12px] tabular-nums text-muted-foreground">
          {formatDateTime(r.requested_at)}
        </span>
      </div>

      <div>
        <h3 id={`${ids}-title`} className="text-[15px] font-bold">
          {valueText ? t("approvals.titleWithValue", { kind, value: valueText }) : kind}
        </h3>
        <p className="text-small text-foreground-secondary">
          {t("approvals.requestedBy", {
            name: r.requested_by_name ?? t("approvals.unknownUser"),
            branch: branchName ?? t("approvals.unknownBranch"),
          })}
        </p>
      </div>

      <dl className="grid gap-x-4 gap-y-1 text-[13px] sm:grid-cols-[max-content_1fr]">
        {valueText ? (
          <>
            <dt className="text-foreground-secondary">{t("approvals.requested")}</dt>
            <dd className="font-bold tabular-nums">{valueText}</dd>
          </>
        ) : null}
        {docType ? (
          <>
            <dt className="text-foreground-secondary">{t("approvals.document")}</dt>
            <dd>{t(`approvals.docTypes.${docTypeKey(docType)}`)}</dd>
          </>
        ) : null}
        {contextLines(r).map((line) => (
          <div key={line.key} className="contents">
            <dt className="text-foreground-secondary">{t(`approvals.context.${line.key}`)}</dt>
            <dd className="break-words">{lineText(line)}</dd>
          </div>
        ))}
        {r.resolved_at ? (
          <>
            <dt className="text-foreground-secondary">{t("approvals.resolvedAt")}</dt>
            <dd className="tabular-nums">{formatDateTime(r.resolved_at)}</dd>
          </>
        ) : null}
        {r.reject_reason ? (
          <>
            <dt className="text-foreground-secondary">{t("approvals.rejectReason")}</dt>
            <dd className="break-words">«{r.reject_reason}»</dd>
          </>
        ) : null}
      </dl>

      {pending && own ? (
        <p className="text-small text-muted-foreground">{t("approvals.ownRequest")}</p>
      ) : null}

      {canDecide && !rejecting ? (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            submitApprove();
          }}
        >
          <label className="flex flex-col gap-1 text-[12px] font-semibold text-foreground-secondary">
            {t("approvals.pin")}
            <Input
              type="password"
              inputMode="numeric"
              autoComplete="off"
              maxLength={6}
              value={pin}
              aria-invalid={pinErrorText ? true : undefined}
              aria-describedby={pinErrorText ? `${ids}-pin-error` : undefined}
              disabled={!online || busy}
              className="w-32 tracking-[0.3em]"
              onChange={(e) => {
                setPin(e.target.value.replace(/[^0-9]/g, "").slice(0, 6));
                if (approveError) clearPinError(r.id);
              }}
            />
          </label>
          <Button type="submit" disabled={!online || busy || !isPinValid(pin)} aria-busy={busy || undefined}>
            <Icon as={Check} size="sm" />
            {t("approvals.approve")}
          </Button>
          <Button
            type="button"
            variant="destructive-outline"
            disabled={!online || busy}
            onClick={() => setRejecting(true)}
          >
            <Icon as={X} size="sm" />
            {t("approvals.reject")}
          </Button>
          {pinErrorText ? (
            <p
              id={`${ids}-pin-error`}
              role="alert"
              className="basis-full text-small font-semibold text-destructive"
            >
              {pinErrorText}
            </p>
          ) : null}
        </form>
      ) : null}

      {canDecide && rejecting ? (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            submitReject();
          }}
        >
          <label className="flex flex-col gap-1 text-[12px] font-semibold text-foreground-secondary">
            {t("approvals.rejectReasonLabel")}
            <Textarea
              value={reason}
              maxLength={1000}
              rows={2}
              aria-invalid={reasonTouched && !isReasonValid(reason) ? true : undefined}
              disabled={!online || busy}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          {reasonTouched && !isReasonValid(reason) ? (
            <p role="alert" className="text-small font-semibold text-destructive">
              {t("approvals.rejectReasonRequired")}
            </p>
          ) : null}
          {rejectError ? (
            <p role="alert" className="text-small font-semibold text-destructive">
              {serverErrorText(rejectError)}
            </p>
          ) : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="secondary" disabled={busy} onClick={cancelReject}>
              {t("approvals.cancelReject")}
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={!online || busy}
              aria-busy={busy || undefined}
            >
              {t("approvals.sendReject")}
            </Button>
          </div>
        </form>
      ) : null}
    </Card>
  );
}
