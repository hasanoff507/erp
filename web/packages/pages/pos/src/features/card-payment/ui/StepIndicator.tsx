/**
 * StepIndicator `horizontal` (08 §7.4 "Qadam indikatori"): `<ol>` 4-column grid, each step a small card with a
 * 26px numbered circle, title and sub line; states done / active / next / error.
 */
import { Check, X } from "lucide-react";

import { Icon, cn } from "@shared/ui";

export type StepState = "done" | "active" | "next" | "error";

export interface Step {
  title: string;
  sub?: string;
  state: StepState;
}

const BOX: Record<StepState, string> = {
  done: "bg-card border border-primary-soft-border",
  active: "bg-primary-soft border-2 border-primary",
  next: "bg-card border border-border",
  error: "bg-destructive-soft border border-destructive-border",
};
const DOT: Record<StepState, string> = {
  done: "bg-primary text-primary-foreground",
  active: "bg-card text-primary-strong",
  next: "bg-track text-muted-foreground",
  error: "bg-destructive text-destructive-foreground",
};
const SUB: Record<StepState, string> = {
  done: "text-success-strong",
  active: "text-primary-strong",
  next: "text-muted-foreground",
  error: "text-destructive-strong",
};

export function StepIndicator({ steps, label }: { steps: readonly Step[]; label: string }) {
  return (
    <ol aria-label={label} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {steps.map((step, index) => (
        <li
          key={step.title}
          aria-current={step.state === "active" ? "step" : undefined}
          data-state={step.state}
          className={cn("flex min-w-0 flex-col gap-1 rounded-lg p-3", BOX[step.state])}
        >
          <span className="flex min-w-0 items-center gap-2">
            <span
              aria-hidden="true"
              className={cn(
                "flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full text-[12px] font-extrabold",
                DOT[step.state],
              )}
            >
              {step.state === "done" ? (
                <Icon as={Check} size="sm" />
              ) : step.state === "error" ? (
                <Icon as={X} size="sm" />
              ) : (
                index + 1
              )}
            </span>
            <span className="text-[13px] font-bold leading-tight text-foreground">{step.title}</span>
          </span>
          {step.sub ? <span className={cn("text-[12px]", SUB[step.state])}>{step.sub}</span> : null}
        </li>
      ))}
    </ol>
  );
}
