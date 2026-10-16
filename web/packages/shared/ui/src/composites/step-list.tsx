/**
 * StepList + StepProgress — BO-21 signup wizard (mockup Bo21Royxat; 08 §7.2 StepIndicator `vertical`,
 * §7.4 "Qadam indikatori"): <ol>, 30px circle with a 2px ring, number or Check (stroke 2.2);
 * done/current = primary circle, current row has a highlighted background and aria-current="step";
 * sub line "description · state" (bajarildi / joriy / keyingi / ixtiyoriy). `tone="dark"` for the ink
 * left panel (sidebar tokens), `"light"` on cards. StepProgress = "2-bosqich / 6" + progressbar.
 */
import { Check, X } from "lucide-react";
import type { ReactNode } from "react";

import { useTranslation } from "@shared/i18n";

import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

export type StepState = "done" | "current" | "next" | "optional" | "error";

export interface StepItem {
  id: string;
  title: string;
  description?: string;
  state: StepState;
}

export interface StepListProps {
  steps: readonly StepItem[];
  tone?: "dark" | "light";
  /** Accessible name of the list (default "Bosqichlar"). */
  label?: string;
  /** Makes done/optional steps clickable (go back to a finished step). */
  onStepClick?: (id: string) => void;
  className?: string;
}

const TONES = {
  dark: {
    currentBg: "bg-sidebar-accent",
    title: "text-sidebar-foreground",
    titleLit: "text-sidebar-accent-foreground",
    sub: "text-sidebar-muted-foreground",
    ringIdle: "border-sidebar-border text-sidebar-muted-foreground",
  },
  light: {
    currentBg: "bg-primary-soft",
    title: "text-foreground-secondary",
    titleLit: "text-foreground",
    sub: "text-muted-foreground",
    ringIdle: "border-input bg-track text-muted-foreground",
  },
} as const;

export function StepList({ steps, tone = "dark", label, onStepClick, className }: StepListProps) {
  const { t } = useTranslation("common");
  const c = TONES[tone];
  return (
    <ol aria-label={label ?? t("ui.stepper.label")} className={cn("flex flex-col gap-1", className)}>
      {steps.map((step, index) => {
        const lit = step.state === "done" || step.state === "current";
        const clickable = onStepClick !== undefined && step.state === "done";
        const content: ReactNode = (
          <>
            <span
              className={cn(
                "flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full border-2 text-[13px] font-extrabold",
                lit && "border-primary bg-primary text-primary-foreground",
                step.state === "error" && "border-destructive bg-destructive text-destructive-foreground",
                !lit && step.state !== "error" && c.ringIdle,
              )}
              aria-hidden="true"
            >
              {step.state === "done" ? (
                <Icon as={Check} size="sm" strokeWidth={2.2} />
              ) : step.state === "error" ? (
                <Icon as={X} size="sm" strokeWidth={2.2} />
              ) : (
                index + 1
              )}
            </span>
            <span className="flex min-w-0 flex-col gap-0.5 text-left">
              <span className={cn("text-[14px] font-bold", lit ? c.titleLit : c.title)}>{step.title}</span>
              <span className={cn("text-[12px]", c.sub)}>
                {step.description ? `${step.description} · ` : ""}
                {t(`ui.stepper.state.${step.state}`)}
              </span>
            </span>
          </>
        );
        const rowClass = cn(
          "flex w-full items-center gap-3.5 rounded-lg px-3.5 py-3",
          step.state === "current" && c.currentBg,
        );
        return (
          <li key={step.id} aria-current={step.state === "current" ? "step" : undefined}>
            {clickable ? (
              <button
                type="button"
                onClick={() => onStepClick(step.id)}
                className={cn(
                  rowClass,
                  "hover:bg-sidebar-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                )}
              >
                {content}
              </button>
            ) : (
              <div className={rowClass}>{content}</div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export interface StepProgressProps {
  /** 1-based current step. */
  current: number;
  total: number;
  /** Accessible name of the progressbar. */
  label: string;
  className?: string;
}

/** "2-bosqich / 6" overline + 6px progress track (mockup Bo21Royxat). */
export function StepProgress({ current, total, label, className }: StepProgressProps) {
  const { t } = useTranslation("common");
  const percent = total > 0 ? Math.min(100, Math.max(0, (current / total) * 100)) : 0;
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <span className="text-[13px] font-bold text-primary-strong">
        {t("ui.stepper.progress", { current, total })}
      </span>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={current}
        className="h-1.5 overflow-hidden rounded-full bg-track"
      >
        <div className="h-1.5 rounded-full bg-primary transition-[width]" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
