/**
 * Screen states — 08 §7.2: EmptyState, Banner, NoPermissionState. Text arrives already translated
 * (i18n keys are resolved by the caller); raw JSON / error codes are never rendered.
 */
import { CircleX, Lock, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { useTranslation } from "@shared/i18n";

import { Button } from "#/components/ui/button.tsx";
import { Icon, type LucideIcon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

import { SOFT_TONE, type Tone } from "./tone.ts";

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 px-6 py-10 text-center", className)}>
      <span className="flex h-11 w-11 items-center justify-center rounded-md bg-accent text-foreground-secondary">
        <Icon as={icon} size="lg" />
      </span>
      <p className="text-[15px] font-bold text-foreground">{title}</p>
      {description ? <p className="max-w-sm text-small text-foreground-secondary">{description}</p> : null}
      {action}
    </div>
  );
}

export interface ErrorStateProps {
  /** Already translated message (`translateMessageKey(error.messageKey)`), never raw JSON. */
  message: string;
  title?: string;
  retryable?: boolean;
  onRetry?: () => void;
  className?: string;
}

/** 08 §7.2 ErrorState — icon + message + "Qayta urinish" (06 §1–§3 error state of a screen/list). */
export function ErrorState({ message, title, retryable = true, onRetry, className }: ErrorStateProps) {
  const { t } = useTranslation("common");
  return (
    <div
      role="alert"
      className={cn("flex flex-col items-center justify-center gap-2 px-6 py-10 text-center", className)}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-md bg-destructive-soft text-destructive-strong">
        <Icon as={CircleX} size="lg" />
      </span>
      <p className="text-[15px] font-bold text-foreground">{title ?? t("states.error")}</p>
      <p className="max-w-sm text-small text-foreground-secondary">{message}</p>
      {retryable && onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry} className="mt-1">
          <Icon as={RefreshCw} size="sm" />
          {t("actions.retry")}
        </Button>
      ) : null}
    </div>
  );
}

/** 08 §7.2 NoPermissionState — `403 PERMISSION_DENIED`: lock icon + "Sizda bu bo'limga kirish huquqi yo'q". */
export function NoPermissionState({ className }: { className?: string }) {
  const { t } = useTranslation("common");
  return <EmptyState icon={Lock} title={t("noPermission.title")} className={className} />;
}

export interface BannerProps {
  tone: Tone;
  icon: LucideIcon;
  children: ReactNode;
  action?: ReactNode;
  /** 08 §10 band 4: fiscal / security / subscription warnings are announced assertively. */
  live?: "polite" | "assertive" | "off";
  className?: string;
}

export function Banner({ tone, icon, children, action, live = "polite", className }: BannerProps) {
  return (
    <div
      role={live === "assertive" ? "alert" : "status"}
      aria-live={live}
      className={cn(
        "flex items-start gap-2.5 rounded-lg px-4 py-3 text-[13px] font-semibold",
        SOFT_TONE[tone],
        className,
      )}
    >
      <Icon as={icon} size="md" className="mt-px shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
      {action}
    </div>
  );
}
