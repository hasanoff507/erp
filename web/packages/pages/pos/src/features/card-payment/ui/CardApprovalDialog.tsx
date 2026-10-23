/**
 * Manager approval with the LOCAL PIN (16 §2.1, 15 §2.3 `card_manual_entry`, `card.manual_entry.approve`):
 * works offline through `@shared/offline` `verifyLocalPin`. Two uses: a manual card that the policy wants
 * approved, and closing an `unknown` attempt from the terminal slip («o'tdi / o'tmadi» — nothing about the card
 * is typed; the only input is the approver's own PIN).
 */
import { useUnit } from "effector-react";
import { CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { useTranslation } from "@shared/i18n";
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
  Input,
  NativeSelect,
} from "@shared/ui";

import { $approvalError, $approvers, loadApproversFx, verifyApproverFx } from "../model/index.ts";
import type { ApprovalRef } from "../model/types/index.ts";
import { dyn } from "./i18n.ts";

export interface CardApprovalDialogProps {
  /** `resolve` — unknown attempt: two outcome buttons; `approve` — one confirm button. */
  mode: "approve" | "resolve";
  onApproved: (approval: ApprovalRef, passed: boolean) => void;
  onClose: () => void;
}

export function CardApprovalDialog({ mode, onApproved, onClose }: CardApprovalDialogProps) {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const [approvers, error, verify, load, busy] = useUnit([
    $approvers,
    $approvalError,
    verifyApproverFx,
    loadApproversFx,
    verifyApproverFx.pending,
  ]);
  const [userId, setUserId] = useState("");
  const [pin, setPin] = useState("");

  useEffect(() => {
    void load().catch(() => undefined);
  }, [load]);
  const selected = userId || approvers[0]?.userId || "";

  const submit = async (passed: boolean) => {
    try {
      const approval = await verify({ userId: selected, pin });
      setPin("");
      onApproved(approval, passed);
    } catch {
      setPin("");
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent size="sm" data-testid="card-approval-dialog">
        <DialogHeader>
          <DialogTitle>
            {mode === "resolve" ? t("cardPayment.approval.resolveTitle") : t("cardPayment.approval.title")}
          </DialogTitle>
          <DialogDescription>
            {mode === "resolve"
              ? t("cardPayment.approval.resolveHint")
              : t("cardPayment.approval.description")}
          </DialogDescription>
        </DialogHeader>
        {approvers.length === 0 ? (
          <Banner tone="warning" icon={CircleAlert}>
            {t("cardPayment.approval.noApprovers")}
          </Banner>
        ) : (
          <form
            className="flex flex-col gap-4"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              if (mode === "approve") void submit(true);
            }}
          >
            <FormField label={t("cardPayment.approval.approver")} required>
              <NativeSelect
                value={selected}
                onChange={(e) => setUserId(e.target.value)}
                options={approvers.map((a) => ({ value: a.userId, label: a.name }))}
              />
            </FormField>
            <FormField label={t("cardPayment.approval.pin")} required>
              <Input
                type="password"
                inputMode="numeric"
                autoComplete="off"
                name="approver-pin"
                maxLength={8}
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
              />
            </FormField>
            {error ? (
              <Banner tone="destructive" icon={CircleAlert} live="assertive">
                {t(`cardPayment.approval.errors.${error}`, {
                  defaultValue: t("cardPayment.approval.errors.PIN_INVALID"),
                })}
              </Banner>
            ) : null}
          </form>
        )}
        <DialogFooter>
          <Button variant="secondary" size="lg" onClick={onClose}>
            {t("cardPayment.actions.close")}
          </Button>
          {mode === "resolve" ? (
            <>
              <Button
                variant="destructive-outline"
                size="lg"
                disabled={!pin || !selected || busy}
                onClick={() => void submit(false)}
              >
                {t("cardPayment.approval.notPassed")}
              </Button>
              <Button size="lg" disabled={!pin || !selected || busy} onClick={() => void submit(true)}>
                {t("cardPayment.approval.passed")}
              </Button>
            </>
          ) : (
            <Button size="lg" disabled={!pin || !selected || busy} onClick={() => void submit(true)}>
              {t("cardPayment.approval.submit")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
