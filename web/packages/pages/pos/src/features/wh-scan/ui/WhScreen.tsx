/**
 * Frame of the POS warehouse / equipment screens (08 §6.1 POS content area, touch density): a header row
 * with «Orqaga (Esc)», the title, an optional subtitle and the primary actions on the right; the body below
 * scrolls on its own. The online/offline chip lives in the shell status bar (06 §1.3).
 */
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";

import { useTranslation } from "@shared/i18n";
import { Button, Icon, Kbd } from "@shared/ui";

export interface WhScreenProps {
  title: string;
  subtitle?: ReactNode;
  onBack: () => void;
  actions?: ReactNode;
  children: ReactNode;
  testId?: string;
}

export function WhScreen({ title, subtitle, onBack, actions, children, testId }: WhScreenProps) {
  const { t } = useTranslation("pos");
  return (
    <section className="flex h-full min-h-0 flex-col gap-3" data-testid={testId}>
      <header className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" size="pos" onClick={onBack} aria-label={t("wh.back")}>
          <Icon as={ArrowLeft} size="md" />
          <span>{t("wh.back")}</span>
          <Kbd keys="Esc" />
        </Button>
        <div className="flex min-w-0 flex-1 flex-col">
          <h1 className="truncate text-[22px] font-extrabold">{title}</h1>
          {subtitle ? <div className="truncate text-[13px] text-muted-foreground">{subtitle}</div> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </section>
  );
}
