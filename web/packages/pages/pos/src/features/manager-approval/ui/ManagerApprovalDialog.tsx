/**
 * ApprovalDialog (07 POS-05 / POS-14; 18 §2.4, §9): the approver's own PIN on this register (local,
 * offline too) or a remote request to BO-16 (online only). `inline` renders the same form inside the
 * screen (POS-14 shows it in the form, 07).
 */
import { useUnit } from "effector-react";
import { CircleAlert, Send, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import type { StaffRow } from "@shared/offline";
import { $isOnline } from "@shared/state/network";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FormField,
  Icon,
  Input,
  NativeSelect,
  cn,
} from "@shared/ui";

import { tashkentTime } from "#/shared/lib/dates.ts";

import {
  defaultApprovalDeps,
  eligibleApprovers,
  localPinOutcome,
  waitRemoteApproval,
  type ApprovalDeps,
  type ApprovalKind,
  type ApprovalRef,
} from "../model/index.ts";

export interface ManagerApprovalDialogProps {
  kind: ApprovalKind;
  /** The approver's permission (15 §2.3): `returns.approve`, `cash.withdraw` … */
  permission: string;
  /** Value the approver's limit must cover; `null` — only an unlimited holder (expired goods). */
  amount: string | null;
  /** approval-requests `context` (remote path). */
  context: Record<string, unknown>;
  requesterId: string | null;
  /** Why the approval is needed (shown under the title). */
  reason: string;
  allowRemote?: boolean;
  inline?: boolean;
  onApproved: (approval: ApprovalRef) => void;
  onClose: () => void;
  deps?: ApprovalDeps;
}

type ErrorKey =
  | "PIN_INVALID"
  | "ACCOUNT_LOCKED"
  | "PIN_NOT_SET"
  | "PIN_MUST_CHANGE"
  | "rejected"
  | "expired"
  | "consumed"
  | "error";

export function ManagerApprovalDialog(props: ManagerApprovalDialogProps) {
  const {
    kind,
    permission,
    amount,
    context,
    requesterId,
    reason,
    allowRemote = true,
    inline = false,
  } = props;
  const { onApproved, onClose } = props;
  const deps = props.deps ?? defaultApprovalDeps;
  const { t } = useTranslation("pos");
  const online = useUnit($isOnline);
  const [rows, setRows] = useState<StaffRow[] | null>(null);
  const [userId, setUserId] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ key: ErrorKey; left?: number; until?: string } | null>(null);
  const [waiting, setWaiting] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    let alive = true;
    void deps
      .staff()
      .then((r) => alive && setRows(r))
      .catch(() => alive && setRows([]));
    return () => {
      alive = false;
      abort.current?.abort();
    };
  }, [deps]);

  const approvers = useMemo(
    () => eligibleApprovers(rows ?? [], permission, amount, requesterId),
    [rows, permission, amount, requesterId],
  );
  const selected = userId || approvers[0]?.userId || "";

  const submitPin = async () => {
    if (!selected || pin.length < 4 || busy) return;
    setBusy(true);
    try {
      const outcome = localPinOutcome(selected, await deps.verifyPin(selected, pin));
      setPin("");
      if (outcome.ok) {
        setError(null);
        onApproved(outcome.approval);
      } else if (outcome.error === "PIN_INVALID")
        setError({ key: outcome.error, left: outcome.attemptsLeft });
      else if (outcome.error === "ACCOUNT_LOCKED")
        setError({ key: outcome.error, until: outcome.lockedUntil });
      else setError({ key: outcome.error });
    } finally {
      setBusy(false);
    }
  };

  const sendRemote = async () => {
    setBusy(true);
    setError(null);
    try {
      const { id } = await deps.createRemote(kind, context);
      setWaiting(true);
      abort.current = new AbortController();
      const outcome = await waitRemoteApproval(deps, id, abort.current.signal);
      setWaiting(false);
      if (outcome.ok) onApproved(outcome.approval);
      else setError({ key: outcome.status });
    } catch (e) {
      setWaiting(false);
      if ((e as { name?: string }).name !== "AbortError") {
        setError({ key: "error" });
        console.warn("approval request failed", toApiError(e).code);
      }
    } finally {
      setBusy(false);
    }
  };

  const cancelWaiting = () => {
    abort.current?.abort();
    setWaiting(false);
  };

  const errorText = error
    ? t(`login.managerApproval.errors.${error.key}`, {
        left: error.left ?? 0,
        until: tashkentTime(error.until),
      })
    : null;

  const body: ReactNode = (
    <div className="flex flex-col gap-4" data-testid="manager-approval">
      {rows !== null && approvers.length === 0 ? (
        <Banner tone="warning" icon={CircleAlert}>
          {t("login.managerApproval.noApprovers")}
        </Banner>
      ) : null}
      {waiting ? (
        <Banner tone="info" icon={Send} live="polite">
          {t("login.managerApproval.waiting")}
        </Banner>
      ) : approvers.length > 0 ? (
        <form
          className="flex flex-col gap-3"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void submitPin();
          }}
        >
          <FormField label={t("login.managerApproval.approver")} required>
            <NativeSelect
              value={selected}
              onChange={(e) => setUserId(e.target.value)}
              options={approvers.map((a) => ({ value: a.userId, label: a.name }))}
            />
          </FormField>
          <FormField label={t("login.managerApproval.pin")} required>
            <Input
              type="password"
              inputMode="numeric"
              autoComplete="off"
              name="approver-pin"
              data-testid="approver-pin"
              maxLength={6}
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
            />
          </FormField>
          {inline ? (
            <Button type="submit" size="pos" disabled={pin.length < 4 || !selected || busy}>
              <Icon as={ShieldCheck} size="md" />
              {t("login.managerApproval.confirm")}
            </Button>
          ) : null}
        </form>
      ) : null}
      {errorText ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          {errorText}
        </Banner>
      ) : null}
      {allowRemote ? (
        waiting ? (
          <Button variant="secondary" size="pos" onClick={cancelWaiting}>
            {t("login.managerApproval.cancelRemote")}
          </Button>
        ) : (
          <Button
            variant="secondary"
            size="pos"
            disabled={!online || busy}
            onClick={() => void sendRemote()}
            data-testid="approval-remote"
          >
            <Icon as={Send} size="md" />
            {online ? t("login.managerApproval.remote") : t("login.managerApproval.remoteOffline")}
          </Button>
        )
      ) : null}
    </div>
  );

  if (inline) {
    return (
      <div
        className={cn("flex flex-col gap-3 rounded-xl border border-warning-border bg-warning-soft/40 p-4")}
      >
        <div className="flex flex-col">
          <span className="text-[15px] font-extrabold">{t("login.managerApproval.title")}</span>
          <span className="text-[13px] text-muted-foreground">{reason}</span>
        </div>
        {body}
      </div>
    );
  }

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent size="sm" data-testid="manager-approval-dialog">
        <DialogHeader>
          <DialogTitle>{t("login.managerApproval.title")}</DialogTitle>
          <DialogDescription>{reason}</DialogDescription>
        </DialogHeader>
        {body}
        <DialogFooter>
          <Button variant="secondary" size="lg" onClick={onClose}>
            {t("login.managerApproval.close")}
          </Button>
          {!waiting && approvers.length > 0 ? (
            <Button size="lg" disabled={pin.length < 4 || !selected || busy} onClick={() => void submitPin()}>
              {t("login.managerApproval.confirm")}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
