/**
 * «Inventarizatsiya» (07 BO-03, `stock.count.create`): «Inventarizatsiyani boshlaysizmi?» →
 * `POST /stock-counts {warehouse_id, doc_date, responsible_user_id?}` — the whole warehouse of the
 * current branch; the snapshot is taken by the server (`started_at`). The new count opens in the
 * detail sheet for the back-office line entry.
 */
import { useUnit } from "effector-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { ConfirmDialog, FormField, Input, toast } from "@shared/ui";

import { ResponsibleSelect } from "#/entities/refs/ui/ResponsibleSelect.tsx";
import type { Warehouse } from "#/entities/refs/index.ts";
import { todayIso } from "#/shared/lib/effect.ts";
import { errorText } from "#/shared/lib/errors.ts";

import { createCountFx } from "../model/index.ts";

export function StartCountDialog({
  open,
  onClose,
  warehouse,
}: {
  open: boolean;
  onClose: () => void;
  warehouse: Warehouse | null;
}) {
  return open && warehouse ? <StartForm onClose={onClose} warehouse={warehouse} /> : null;
}

function StartForm({ onClose, warehouse }: { onClose: () => void; warehouse: Warehouse }) {
  const { t } = useTranslation("warehouse");
  const create = useUnit(createCountFx);
  const [docDate, setDocDate] = useState(todayIso());
  const [responsible, setResponsible] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={t("counts.start.title")}
      description={t("counts.start.description", { warehouse: warehouse.name })}
      confirmLabel={t("counts.start.confirm")}
      error={error}
      onConfirm={async () => {
        setError(null);
        try {
          const count = await create({
            warehouse_id: warehouse.id,
            doc_date: docDate,
            responsible_user_id: responsible,
          });
          toast.success(t("counts.toast.started", { count: count.line_count }));
        } catch (e) {
          setError(errorText(e));
          throw e;
        }
      }}
    >
      <div className="flex flex-col gap-3">
        <FormField label={t("counts.fields.docDate")} required>
          <Input type="date" value={docDate} onChange={(e) => setDocDate(e.target.value)} />
        </FormField>
        <FormField label={t("counts.fields.responsible")} hint={t("counts.fields.responsibleHint")}>
          {(a11y) => <ResponsibleSelect {...a11y} value={responsible} onChange={setResponsible} />}
        </FormField>
      </div>
    </ConfirmDialog>
  );
}
