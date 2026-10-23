/**
 * BO-24 — Bank tushumi tasdig'i (07, routes /app/finance/bank-settlements, …/new, …/:id;
 * `bank_settlements.manage`; mockup Bo24Bank): filters (branch, method, status, period), «Ko'chirmani
 * yuklash», «+ Yangi», the 5710 transit panel, the documents list and the document panel on the right.
 * Offline: view only. useEffect fires pageMounted / settlementOpened (24 §2).
 */
import { useUnit } from "effector-react";
import { Plus, Upload, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import { $activeBranchId, $branches, ALL_BRANCHES } from "@shared/state/session";
import { Banner, Button, FormField, Icon, Input, NoPermissionState, SimpleSelect } from "@shared/ui";

import {
  $error,
  $filters,
  METHODS,
  STATUSES,
  filtersChanged,
  isMethod,
  isSettlementStatus,
  pageMounted,
  settlementOpened,
} from "../../model/index.ts";
import { SettlementPanel } from "../form/SettlementPanel.tsx";
import { ImportDialog } from "../import/ImportDialog.tsx";
import { ImportResult } from "../import/ImportResult.tsx";
import { SettlementsTable } from "../list/SettlementsTable.tsx";
import { TransitPanel } from "../transit/TransitPanel.tsx";

const ALL = "all";
const BASE = "/app/finance/bank-settlements";

function BankSettlementsPage() {
  const { t } = useTranslation("finance");
  const canView = useCan({ permission: "bank_settlements.manage" });
  const { id } = useParams();
  const navigate = useNavigate();
  const [mounted, opened, change] = useUnit([pageMounted, settlementOpened, filtersChanged]);
  const [filters, error, online, activeBranch, branches] = useUnit([
    $filters,
    $error,
    $isOnline,
    $activeBranchId,
    $branches,
  ]);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (!canView) return;
    mounted({
      today: dayjs().format("YYYY-MM-DD"),
      branchId: activeBranch && activeBranch !== ALL_BRANCHES ? activeBranch : null,
    });
    // Only on entry (24 §2).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, canView]);

  useEffect(() => {
    if (canView) opened(id ?? null);
  }, [opened, canView, id]);

  if (!canView || error?.status === 403) return <NoPermissionState />;

  const open = (next: string) => void navigate(`${BASE}/${next}`);
  const close = () => void navigate(BASE);

  return (
    <div className="flex flex-col gap-[18px]">
      <p className="text-small text-foreground-secondary">{t("bank.subtitle")}</p>
      <div className="flex flex-wrap items-end gap-3">
        {branches.length > 1 ? (
          <FormField label={t("bank.filters.branch")} className="w-48">
            <SimpleSelect
              options={[
                { value: ALL, label: t("bank.filters.allBranches") },
                ...branches.map((b) => ({ value: b.id, label: b.name })),
              ]}
              value={filters.branchId ?? ALL}
              onValueChange={(v) => change({ branchId: v === ALL ? null : v })}
            />
          </FormField>
        ) : null}
        <FormField label={t("bank.filters.method")} className="w-40">
          <SimpleSelect
            options={[
              { value: ALL, label: t("bank.filters.all") },
              ...METHODS.map((m) => ({ value: m, label: t(`bank.methods.${m}`) })),
            ]}
            value={filters.method ?? ALL}
            onValueChange={(v) => change({ method: isMethod(v) ? v : null })}
          />
        </FormField>
        <FormField label={t("bank.filters.status")} className="w-44">
          <SimpleSelect
            options={[
              { value: ALL, label: t("bank.filters.all") },
              ...STATUSES.map((s) => ({ value: s, label: t(`bank.status.${s}`) })),
            ]}
            value={filters.status ?? ALL}
            onValueChange={(v) => change({ status: isSettlementStatus(v) ? v : null, source: null })}
          />
        </FormField>
        <FormField label={t("bank.filters.from")} className="w-40">
          <Input
            type="date"
            value={filters.from ?? ""}
            onChange={(e) => change({ from: e.target.value || null })}
          />
        </FormField>
        <FormField label={t("bank.filters.to")} className="w-40">
          <Input
            type="date"
            value={filters.to ?? ""}
            onChange={(e) => change({ to: e.target.value || null })}
          />
        </FormField>
        <div className="grow" />
        <Button
          variant="outline"
          disabled={!online}
          onClick={() => setImporting(true)}
          data-testid="bank-import"
        >
          <Icon as={Upload} size="sm" />
          {t("bank.actions.import")}
        </Button>
        <Button disabled={!online} onClick={() => open("new")} data-testid="bank-new">
          <Icon as={Plus} size="sm" />
          {t("bank.actions.new")}
        </Button>
      </div>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("bank.offline")}
        </Banner>
      )}
      <ImportResult />
      <div className="grid items-start gap-[18px] xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="flex min-w-0 flex-col gap-[18px]">
          <TransitPanel />
          <SettlementsTable onOpen={open} />
        </div>
        {id ? <SettlementPanel id={id} canAct={online} onClose={close} onOpen={open} /> : null}
      </div>
      <ImportDialog open={importing} onOpenChange={setImporting} />
    </div>
  );
}

/** One route for the list, `/new` and `/:id` (the document opens in the right panel; no remount). */
export const BankSettlements = {
  route: "finance/bank-settlements/:id?",
  titleKey: "finance:bank.title",
  Page: BankSettlementsPage,
} as const;
