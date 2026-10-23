/**
 * tenant-switcher — topbar branch filter (06 §1.9 (2)): the user's branches plus «Barcha filiallar»
 * when there are several. The choice is the default for screen filters and the X-Branch-Id header.
 * Tenant switching (14 §9) = a new login with `tenant_id` (/auth/login/start?tenant_id=…).
 */
import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { $activeBranchId, $branches, ALL_BRANCHES, branchSelected } from "@shared/state/session";
import { NativeSelect } from "@shared/ui";

export function BranchSelect({ className }: { className?: string }) {
  const { t } = useTranslation();
  const [branches, activeId, select] = useUnit([$branches, $activeBranchId, branchSelected]);

  if (branches.length === 0) return null;

  const options = [
    ...(branches.length > 1 ? [{ value: ALL_BRANCHES, label: t("topbar.allBranches") }] : []),
    ...branches.map((b) => ({ value: b.id, label: b.name })),
  ];

  return (
    <NativeSelect
      aria-label={t("topbar.branch")}
      value={activeId ?? ALL_BRANCHES}
      onChange={(e) => select(e.target.value)}
      options={options}
      wrapperClassName={className}
    />
  );
}
