import { Wrench } from "lucide-react";

import { EmptyState, type LucideIcon } from "@shared/ui";

/** Full-height card used by POS placeholder screens in Bosqich 0. */
export function PendingScreen({
  title,
  description,
  icon = Wrench,
}: {
  title: string;
  description: string;
  icon?: LucideIcon;
}) {
  return (
    <section className="flex h-full min-h-0 items-center justify-center rounded-2xl border border-border bg-card shadow-raised">
      <EmptyState icon={icon} title={title} description={description} />
    </section>
  );
}
