/**
 * shadcn/ui Command (cmdk) — 08 §6 `Command`, §9 back-office `Ctrl+K` palette. Keyboard: ↑ / ↓ move,
 * Enter selects, Esc closes (dialog). `CommandDialog` puts it in our Dialog (Radix; the scroll-lock
 * <style> carries the CSP nonce, 24 §4.4); cmdk itself styles only through the CSSOM (no <style>).
 * `shouldFilter={false}` on `Command` when the caller filters (server search) itself.
 */
import { Command as CommandPrimitive } from "cmdk";
import { Search } from "lucide-react";
import type { ComponentProps, HTMLAttributes, ReactNode } from "react";

import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./dialog.tsx";

export function Command({ className, ...props }: ComponentProps<typeof CommandPrimitive>) {
  return (
    <CommandPrimitive
      className={cn("flex h-full w-full flex-col overflow-hidden bg-card text-card-foreground", className)}
      {...props}
    />
  );
}

export interface CommandDialogProps extends ComponentProps<typeof Dialog> {
  /** Accessible title / description of the dialog (visually hidden). */
  title: string;
  description?: string;
  children: ReactNode;
  commandProps?: ComponentProps<typeof CommandPrimitive>;
  className?: string;
}

export function CommandDialog({
  title,
  description,
  children,
  commandProps,
  className,
  ...props
}: CommandDialogProps) {
  return (
    <Dialog {...props}>
      <DialogContent size="lg" hideClose className={cn("gap-0 overflow-hidden p-0", className)}>
        <DialogTitle className="sr-only">{title}</DialogTitle>
        {description ? <DialogDescription className="sr-only">{description}</DialogDescription> : null}
        <Command label={title} {...commandProps}>
          {children}
        </Command>
      </DialogContent>
    </Dialog>
  );
}

export function CommandInput({ className, ...props }: ComponentProps<typeof CommandPrimitive.Input>) {
  return (
    <div className="flex items-center gap-2 border-b border-border px-4" cmdk-input-wrapper="">
      <Icon as={Search} size="md" className="shrink-0 text-muted-foreground" />
      <CommandPrimitive.Input
        className={cn(
          "flex h-14 w-full bg-transparent text-[15px] outline-none placeholder:text-muted-foreground",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
    </div>
  );
}

export function CommandList({ className, ...props }: ComponentProps<typeof CommandPrimitive.List>) {
  return (
    <CommandPrimitive.List
      className={cn("max-h-[min(420px,60dvh)] overflow-y-auto overflow-x-hidden p-2", className)}
      {...props}
    />
  );
}

export function CommandEmpty({ className, ...props }: ComponentProps<typeof CommandPrimitive.Empty>) {
  return (
    <CommandPrimitive.Empty
      className={cn("py-8 text-center text-small text-muted-foreground", className)}
      {...props}
    />
  );
}

export function CommandLoading({ className, ...props }: ComponentProps<typeof CommandPrimitive.Loading>) {
  return (
    <CommandPrimitive.Loading
      className={cn("px-3 py-2 text-small text-muted-foreground", className)}
      {...props}
    />
  );
}

export function CommandGroup({ className, ...props }: ComponentProps<typeof CommandPrimitive.Group>) {
  return (
    <CommandPrimitive.Group
      className={cn(
        "overflow-hidden py-1 text-foreground",
        "[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-overline [&_[cmdk-group-heading]]:text-foreground-secondary",
        className,
      )}
      {...props}
    />
  );
}

export function CommandItem({ className, ...props }: ComponentProps<typeof CommandPrimitive.Item>) {
  return (
    <CommandPrimitive.Item
      className={cn(
        "flex cursor-pointer select-none items-center gap-3 rounded-lg px-3 py-2.5 text-[14px] outline-none",
        "data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground",
        "data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function CommandSeparator({ className, ...props }: ComponentProps<typeof CommandPrimitive.Separator>) {
  return <CommandPrimitive.Separator className={cn("-mx-2 my-1 h-px bg-border", className)} {...props} />;
}

export function CommandShortcut({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("ml-auto text-[12px] text-muted-foreground", className)} {...props} />;
}
