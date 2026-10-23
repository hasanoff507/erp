/**
 * shadcn/ui Dialog (Radix) — 08 §7.4 "Dialog": bg-card rounded-3xl shadow-dialog, overlay
 * `hsl(var(--overlay) / 0.55)`, title text-h1 (BO: h2-size for compact dialogs), close = icon button.
 * Radix modal mode injects a scroll-lock <style>; the shell stamps the CSP nonce on it (24 §4.4).
 * Esc closes; focus is trapped and returned to the trigger.
 */
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ComponentProps, HTMLAttributes } from "react";

import { useTranslation } from "@shared/i18n";

import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export const overlayClassName =
  "fixed inset-0 z-overlay bg-overlay/55 data-[state=open]:animate-in data-[state=closed]:animate-out " +
  "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0";

const DIALOG_SIZES = {
  sm: "max-w-[420px]",
  md: "max-w-[560px]",
  lg: "max-w-[760px]",
} as const;

export interface DialogContentProps extends ComponentProps<typeof DialogPrimitive.Content> {
  size?: keyof typeof DIALOG_SIZES;
  /** Hide the top-right close button (e.g. a blocking confirmation that must be answered). */
  hideClose?: boolean;
}

export function DialogContent({
  className,
  children,
  size = "md",
  hideClose = false,
  ...props
}: DialogContentProps) {
  const { t } = useTranslation("common");
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className={overlayClassName} />
      <DialogPrimitive.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-dialog flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 overflow-y-auto",
          "rounded-3xl border border-border bg-card p-6 text-card-foreground shadow-dialog focus:outline-none",
          "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          DIALOG_SIZES[size],
          className,
        )}
        {...props}
      >
        {children}
        {hideClose ? null : (
          <DialogPrimitive.Close
            aria-label={t("ui.dialog.close")}
            className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-lg text-foreground-secondary hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon as={X} size="lg" />
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1.5 pr-10", className)} {...props} />;
}

export function DialogFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-2 flex flex-wrap items-center justify-end gap-2", className)} {...props} />;
}

export function DialogTitle({ className, ...props }: ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title className={cn("text-h2 font-extrabold text-foreground", className)} {...props} />
  );
}

export function DialogDescription({
  className,
  ...props
}: ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      className={cn("text-small text-foreground-secondary", className)}
      {...props}
    />
  );
}
