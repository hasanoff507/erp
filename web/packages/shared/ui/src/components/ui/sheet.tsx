/**
 * shadcn/ui Sheet (Radix Dialog as a side panel) — the add/edit form panel of BO-11 / BO-12 / BO-05
 * and the mobile sidebar (08 §6.2). `side="right"` (default, 480px), `"left"`, `"bottom"`
 * (POS: `rounded-t-3xl shadow-pos-sheet`, 08 §7.4). Same overlay, focus trap and Esc as Dialog.
 * Layout: SheetHeader (title + description) · SheetBody (scrolls) · SheetFooter (sticky actions).
 */
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import type { ComponentProps, HTMLAttributes } from "react";

import { useTranslation } from "@shared/i18n";

import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

import { overlayClassName } from "./dialog.tsx";

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

const sheetVariants = cva(
  "fixed z-dialog flex flex-col bg-card text-card-foreground shadow-dialog focus:outline-none " +
    "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:duration-200 data-[state=closed]:duration-150",
  {
    variants: {
      side: {
        right:
          "inset-y-0 right-0 h-full w-full border-l border-border sm:max-w-[480px] data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right",
        left: "inset-y-0 left-0 h-full w-[280px] border-r border-border data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left",
        bottom:
          "inset-x-0 bottom-0 max-h-[90dvh] rounded-t-3xl shadow-pos-sheet data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
      },
    },
    defaultVariants: { side: "right" },
  },
);

export interface SheetContentProps
  extends ComponentProps<typeof DialogPrimitive.Content>, VariantProps<typeof sheetVariants> {
  hideClose?: boolean;
  /** Wide variant for forms with tables (price history): 640px instead of 480px. */
  wide?: boolean;
}

export function SheetContent({
  className,
  children,
  side,
  hideClose = false,
  wide = false,
  ...props
}: SheetContentProps) {
  const { t } = useTranslation("common");
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className={overlayClassName} />
      <DialogPrimitive.Content
        className={cn(sheetVariants({ side }), wide && side !== "bottom" && "sm:max-w-[640px]", className)}
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

export function SheetHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex flex-col gap-1 border-b border-border px-6 py-5 pr-16", className)} {...props} />
  );
}

export function SheetBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-6 py-5", className)}
      {...props}
    />
  );
}

export function SheetFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-end gap-2 border-t border-border bg-muted px-6 py-4",
        className,
      )}
      {...props}
    />
  );
}

export function SheetTitle({ className, ...props }: ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title className={cn("text-h2 font-extrabold text-foreground", className)} {...props} />
  );
}

export function SheetDescription({
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
