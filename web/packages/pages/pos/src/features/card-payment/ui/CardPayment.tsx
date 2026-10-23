/**
 * The card part of POS-03 (07; 24 §6.5) — connects the `$cardAttempt` state machine to CardTerminalPanel,
 * CardManualConfirm and the local-PIN CardApprovalDialog. POS-03 (wave 2) renders it when «Karta» is chosen,
 * starts it with `cardPaymentStarted(...)`, reads `$cardPaymentOutcome` for `payments[]`, then fires
 * `cardOutcomeConsumed` after `enqueueEvent(..., { removeCardAttemptIds })`. While `$cardPanelLocked` is true
 * the host dialog must refuse to close (its own `onEscapeKeyDown` — UX-01/UX-11); this block adds no global
 * key handler, so Esc still closes a nested dialog (the manager PIN dialog).
 */
import { useUnit } from "effector-react";
import { useState } from "react";

import { CircleAlert } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { Banner } from "@shared/ui";

import {
  $cardAttempt,
  $cardPanelLocked,
  $danglingAttachable,
  danglingAttached,
  danglingVoided,
  $elapsedS,
  $manualApprovalNeeded,
  cancelPressed,
  managerResolved,
  manualConfirmed,
  manualRequested,
  retryPressed,
  statusCheckRequested,
} from "../model/index.ts";
import { CardApprovalDialog } from "./CardApprovalDialog.tsx";
import { CardManualConfirm } from "./CardManualConfirm.tsx";
import { CardTerminalPanel } from "./CardTerminalPanel.tsx";

export function CardPayment() {
  const { t } = useTranslation("pos");
  const [s, elapsed, locked, needsApproval, cancel, retry, check, resolve, toManual, confirmManual] = useUnit(
    [
      $cardAttempt,
      $elapsedS,
      $cardPanelLocked,
      $manualApprovalNeeded,
      cancelPressed,
      retryPressed,
      statusCheckRequested,
      managerResolved,
      manualRequested,
      manualConfirmed,
    ],
  );
  const [attachable, attach, voidDangling] = useUnit([$danglingAttachable, danglingAttached, danglingVoided]);
  const [dialog, setDialog] = useState<"approve" | "resolve" | null>(null);

  if (s.phase === "idle") return null;

  const body =
    (s.phase === "manual_confirm" || s.phase === "manual") && s.amount && s.manualReason ? (
      <CardManualConfirm
        amount={s.amount}
        manualReason={s.manualReason}
        requiresApproval={needsApproval === true}
        errorCode={s.errorCode}
        onConfirm={() => (needsApproval ? setDialog("approve") : confirmManual({ approval: null }))}
      />
    ) : (
      <CardTerminalPanel
        attempt={s}
        elapsedS={elapsed}
        onCancel={cancel}
        onRetry={retry}
        onCheckStatus={check}
        onManagerResolve={() => setDialog("resolve")}
        onManual={toManual}
        attachable={attachable}
        onAttach={attach}
        onVoidDangling={voidDangling}
      />
    );

  return (
    <>
      {body}
      {locked ? (
        <Banner tone="info" icon={CircleAlert}>
          {t("cardPayment.escLocked")}
        </Banner>
      ) : null}
      {dialog ? (
        <CardApprovalDialog
          mode={dialog}
          onClose={() => setDialog(null)}
          onApproved={(approval, passed) => {
            setDialog(null);
            if (dialog === "resolve") resolve({ passed, approval });
            else confirmManual({ approval });
          }}
        />
      ) : null}
    </>
  );
}
