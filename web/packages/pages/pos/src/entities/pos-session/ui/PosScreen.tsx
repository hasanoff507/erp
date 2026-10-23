/**
 * PosScreen — the frame of the POS operation screens (POS-05/07/14/15): title + hotkey chip, «Orqaga»
 * (Esc) and the body. The POS status bar (online chip, shift, cashier) is the shell's (PosLayout).
 */
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";

import { Button, Icon, Kbd, cn } from "@shared/ui";

export interface PosScreenProps {
  title: string;
  /** Hotkey that opens the screen (F6 / F8). */
  hotkey?: string;
  subtitle?: string;
  backLabel: string;
  onBack: () => void;
  /** UX-03: back is held while the terminal may move money. */
  backDisabled?: boolean;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
}

export function PosScreen({
  title,
  hotkey,
  subtitle,
  backLabel,
  onBack,
  backDisabled,
  actions,
  children,
  className,
  testId,
}: PosScreenProps) {
  return (
    <section
      data-testid={testId}
      className={cn(
        "flex h-full min-h-0 flex-col gap-4 rounded-2xl border border-border bg-card p-5 shadow-raised",
        className,
      )}
    >
      <header className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" size="pos" onClick={onBack} disabled={backDisabled}>
          <Icon as={ArrowLeft} size="md" />
          {backLabel}
          <Kbd keys="Esc" />
        </Button>
        <div className="flex min-w-0 flex-col">
          <h1 className="flex items-center gap-2 text-[22px] font-extrabold">
            {title}
            {hotkey ? <Kbd keys={hotkey} /> : null}
          </h1>
          {subtitle ? <span className="text-[13px] text-muted-foreground">{subtitle}</span> : null}
        </div>
        <div className="grow" />
        {actions}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </section>
  );
}
