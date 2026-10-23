/**
 * ConfirmDialog — 08 §12 #15/#16 ("Haqiqatan o'chirasizmi?"), §7.4: filled `destructive` button only in
 * an irreversible confirmation. Controlled (`open`/`onOpenChange`); `onConfirm` may return a Promise —
 * the confirm button shows the pending state and the dialog stays open until it settles (closes on
 * success, stays open on rejection so the caller can show the error inside via `error`).
 */
import { TriangleAlert } from "lucide-react";
import { useState, type ReactNode } from "react";

import { useTranslation } from "@shared/i18n";

import { Button } from "#/components/ui/button.tsx";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "#/components/ui/dialog.tsx";
import { Banner } from "./states.tsx";

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** `destructive` = filled red confirm (irreversible); `default` = primary. */
  tone?: "default" | "destructive";
  onConfirm: () => void | Promise<unknown>;
  /** Externally controlled pending state (e.g. an effector effect's `pending`). */
  pending?: boolean;
  /** Translated error shown inside the dialog (e.g. after a failed request). */
  error?: string | null;
  children?: ReactNode;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel,
  tone = "default",
  onConfirm,
  pending,
  error,
  children,
}: ConfirmDialogProps) {
  const { t } = useTranslation("common");
  const [running, setRunning] = useState(false);
  const busy = pending ?? running;

  const confirm = async () => {
    const result = onConfirm();
    if (!(result instanceof Promise)) return;
    setRunning(true);
    try {
      await result;
      onOpenChange(false);
    } catch {
      // stays open — the caller renders `error`
    } finally {
      setRunning(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => (busy ? undefined : onOpenChange(next))}>
      <DialogContent size="sm" role="alertdialog" hideClose>
        <DialogHeader className="pr-0">
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        {children}
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
        <DialogFooter>
          <Button variant="secondary" disabled={busy} onClick={() => onOpenChange(false)}>
            {cancelLabel ?? t("actions.cancel")}
          </Button>
          <Button
            variant={tone === "destructive" ? "destructive" : "default"}
            disabled={busy}
            aria-busy={busy || undefined}
            onClick={() => void confirm()}
          >
            {confirmLabel ?? t("actions.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
