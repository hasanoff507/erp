import { useUnit } from "effector-react";
import { Building2, Plus, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { useCan } from "@shared/state/permissions";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Icon,
  NoPermissionState,
  Skeleton,
  StatusChip,
  cn,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { PageHeader } from "#/shared/ui/PageHeader.tsx";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $branches,
  $branchesError,
  $branchesLoaded,
  $selectedBranch,
  $verifyHints,
  branchSelected,
  branchesReloadRequested,
  pageMounted,
  type Branch,
} from "../../model/index.ts";
import { BranchSummary } from "../detail/BranchDetail.tsx";
import { CardPolicy } from "../detail/CardPolicy.tsx";
import { CashRegisters } from "../detail/CashRegisters.tsx";
import { TaxHistory } from "../detail/TaxHistory.tsx";
import { Warehouses } from "../detail/Warehouses.tsx";
import { CreateBranchDialog, EditBranchDialog } from "../form/BranchDialogs.tsx";

/**
 * BO-12 — Filiallar boshqaruvi (07, route /app/settings/branches): branches, settlement category
 * (turnover-tax rate, US-M14-04) with its history, warehouses, cash registers, card policy.
 * Copy-pricing (US-M14-02) is after MVP (qaror #33) and is not shown.
 */
function BranchesPage() {
  const { t } = useTranslation("settings");
  const canBranches = useCan({ permission: "settings.branches" });
  const canRegisters = useCan({ permission: "cash_register.manage" });
  const canTenant = useCan({ permission: "settings.tenant" });
  const online = useOnline();
  const [branches, loaded, error, selected, hints, select, reload, mounted] = useUnit([
    $branches,
    $branchesLoaded,
    $branchesError,
    $selectedBranch,
    $verifyHints,
    branchSelected,
    branchesReloadRequested,
    pageMounted,
  ]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);

  useEffect(() => {
    mounted({ canTenant });
  }, [mounted, canTenant]);

  const header = (
    <PageHeader
      title={t("branches.title")}
      description={t("branches.description")}
      actions={
        canBranches ? (
          <Button disabled={!online} onClick={() => setCreating(true)}>
            <Icon as={Plus} size="sm" />
            {t("branches.add")}
          </Button>
        ) : null
      }
    />
  );

  let body;
  if (!canBranches && !canRegisters) {
    body = <NoPermissionState />;
  } else if (error) {
    body =
      error.status === 403 ? (
        <NoPermissionState />
      ) : (
        <ErrorState message={errorText(error)} onRetry={reload} />
      );
  } else if (!loaded) {
    body = (
      <div className="flex flex-col gap-3" aria-busy="true">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  } else if (branches.length === 0) {
    body = <EmptyState icon={Building2} title={t("branches.empty")} />;
  } else {
    body = (
      <div className="flex flex-col gap-3.5 lg:flex-row lg:items-start">
        <Card className="flex w-full flex-col gap-1 lg:w-[300px] lg:shrink-0">
          <h2 className="mb-1 text-[15px] font-bold">
            {t("branches.listTitle", { count: branches.length })}
          </h2>
          <ul className="flex flex-col gap-1" aria-label={t("branches.title")}>
            {branches.map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  aria-current={selected?.id === b.id ? "true" : undefined}
                  onClick={() => select(b.id)}
                  className={cn(
                    "flex w-full flex-col items-start gap-0.5 rounded-md px-3 py-2.5 text-left",
                    "hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selected?.id === b.id && "bg-primary-soft",
                  )}
                >
                  <span className="flex w-full items-center gap-2 text-[14px] font-bold">
                    <span className="truncate">{b.name}</span>
                    {b.is_default ? <StatusChip tone="info">{t("branches.default")}</StatusChip> : null}
                    {hints.includes(b.id) ? (
                      <span className="flex items-center text-warning">
                        <Icon as={TriangleAlert} size="sm" />
                        <span className="sr-only">{t("branches.verifyHint.short")}</span>
                      </span>
                    ) : null}
                  </span>
                  <span className="text-[12px] text-muted-foreground">
                    {t(`branches.category.${b.settlement_category}`)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {branches.length === 1 ? (
            <p className="px-3 pt-2 text-[12px] text-muted-foreground">{t("branches.singleHint")}</p>
          ) : null}
        </Card>
        {selected ? (
          <div className="flex min-w-0 flex-1 flex-col gap-3.5">
            <BranchSummary branch={selected} canEdit={canBranches} onEdit={() => setEditing(selected)} />
            <TaxHistory branch={selected} canEdit={canBranches} />
            <Warehouses canEdit={canBranches} />
            <CashRegisters branch={selected} canManage={canRegisters} />
            {canTenant ? <CardPolicy /> : null}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-[18px]">
      {header}
      {body}
      <CreateBranchDialog open={creating} onClose={() => setCreating(false)} />
      <EditBranchDialog branch={editing} onClose={() => setEditing(null)} />
    </div>
  );
}

export const Branches = {
  route: "settings/branches",
  titleKey: "settings:branches.title",
  Page: BranchesPage,
} as const;
