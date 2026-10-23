/**
 * Card payment feature (qaror #71/#64; 24 §6.5, 07 POS-03 / POS-16). Public surface for POS-03 / POS-16 /
 * shift close (wave 2): the state machine, its outcome, the connected `CardPayment` block and the pairing
 * section.
 */
export {
  $canCancelOnTerminal,
  $canRetry,
  $cardAttempt,
  $cardPanelLocked,
  $cardPaymentOutcome,
  $cardPhase,
  $elapsedS,
  cancelPressed,
  cardOutcomeConsumed,
  cardPaymentClosed,
  cardRecoveryClosed,
  cardRecoveryRequested,
  $cardRecoveryOpen,
  cardPaymentRestored,
  cardPaymentStarted,
  configureCardPayment,
  $danglingAttachable,
  danglingAttached,
  danglingAttemptsFx,
  danglingVoided,
  orphanDanglingFx,
  defaultCardPaymentDeps,
  managerResolved,
  manualConfirmed,
  manualRequested,
  retryPressed,
  saleCancelled,
  statusCheckRequested,
  type ApprovalRef,
  type CardAttemptState,
  type CardPaymentDeps,
  type CardPaymentOutcome,
  type CardPhase,
  type ManualReason,
  type StartInput,
} from "./model/index.ts";
export { CardPayment } from "./ui/CardPayment.tsx";
export { CardRecoveryDialog } from "./ui/CardRecoveryDialog.tsx";
export { CardTerminalPanel, type CardTerminalPanelProps } from "./ui/CardTerminalPanel.tsx";
export { CardManualConfirm } from "./ui/CardManualConfirm.tsx";
export { CardApprovalDialog } from "./ui/CardApprovalDialog.tsx";
export { StepIndicator, type Step, type StepState } from "./ui/StepIndicator.tsx";
export { TerminalStatusChip } from "./ui/TerminalStatusChip.tsx";
export { TerminalPairingSection } from "./ui/TerminalPairingSection.tsx";
