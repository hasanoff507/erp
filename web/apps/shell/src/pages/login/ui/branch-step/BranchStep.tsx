/**
 * BO-01 post-login step (07 `branchId`: required when the user has several branches; default — first
 * branch). Mockup: dashed card «Kirgandan keyin — bir nechta do'kon yoki filial bo'lsa».
 * The store field shows the session tenant; another store = new login with `tenant_id` (14 §9).
 */
import { useUnit } from "effector-react";
import { useId, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { $branches, $tenant, branchSelected } from "@shared/state/session";
import { Button, NativeSelect } from "@shared/ui";

export function BranchStep() {
  const { t } = useTranslation("auth");
  const [branches, tenant, select] = useUnit([$branches, $tenant, branchSelected]);
  const [branchId, setBranchId] = useState<string>(branches[0]?.id ?? "");
  const storeId = useId();
  const branchSelectId = useId();

  return (
    <section
      aria-label={t("branchStep.label")}
      className="flex flex-col gap-2.5 rounded-xl border border-dashed border-input bg-card p-3.5"
    >
      <span className="flex items-center gap-2 text-[12px] font-bold text-muted-foreground">
        <span className="rounded-full bg-primary-soft px-2 py-0.5 text-primary-strong">
          {t("branchStep.badge")}
        </span>
        {t("branchStep.hint")}
      </span>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (branchId) select(branchId);
        }}
      >
        <div className="flex min-w-0 flex-[1_1_0] flex-col gap-1">
          <label htmlFor={storeId} className="text-[12px] font-semibold text-foreground-secondary">
            {t("branchStep.store")}
          </label>
          <NativeSelect
            id={storeId}
            disabled
            className="h-10 rounded-md text-[13px]"
            options={tenant ? [{ value: tenant.id, label: tenant.name }] : []}
            value={tenant?.id ?? ""}
          />
        </div>
        <div className="flex min-w-0 flex-[1_1_0] flex-col gap-1">
          <label htmlFor={branchSelectId} className="text-[12px] font-semibold text-foreground-secondary">
            {t("branchStep.branch")}
          </label>
          <NativeSelect
            id={branchSelectId}
            className="h-10 rounded-md text-[13px]"
            options={branches.map((b) => ({ value: b.id, label: b.name }))}
            value={branchId}
            onChange={(e) => setBranchId(e.target.value)}
          />
        </div>
        <Button type="submit" variant="inverse" size="sm" className="h-10 rounded-md">
          {t("branchStep.continueButton")}
        </Button>
      </form>
    </section>
  );
}
