/**
 * BO-06 — Nasiya / qarzdorlar ro'yxati va eslatmalar (07, route /app/debts; mockup Bo06Qarzdorlar.dc.html).
 * Top: «Jami debitorlik (4010)» + aging groups; tabs «Bugun/o'tgan va'da» · «60+ kun» · «Limitdan oshgan»
 * (Owner) · «Barchasi» with counts; search; the debtor table; the right panel of the selected debtor
 * (ledger, card, opening, Owner actions, reminder, bank payment) and «Ortiqcha to'lovlar».
 * `?direction=payable` shows the same view for what we owe suppliers (the spec place of «Men qarzdorman» is BO-04);
 * `?counterparty=<id>` (Ctrl+K palette) selects that debtor once the list is loaded. Offline: view only.
 * useEffect only fires pageMounted (24 §2).
 */
import { useUnit } from "effector-react";
import { Plus, RefreshCw, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import type { Money } from "@shared/lib/money";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import {
  Banner,
  Button,
  Icon,
  NoPermissionState,
  SearchInput,
  Tabs,
  TabsList,
  TabsTrigger,
} from "@shared/ui";

import { DEBTOR_TABS, isDebtorTab, type DebtorTab } from "#/entities/debtor/index.ts";
import { CustomerCardSheet } from "#/features/customer-card/index.ts";
import { LedgerSheet } from "#/features/debt-ledger/index.ts";
import { OpeningDialog } from "#/features/debt-opening/index.ts";
import { WriteoffDialog } from "#/features/debt-writeoff/index.ts";
import { FlagDialog } from "#/features/doubtful-flag/index.ts";
import { OverpaymentsBlock } from "#/features/overpayments/index.ts";
import { todayIso } from "#/shared/lib/effect.ts";

import {
  $branchId,
  $counts,
  $direction,
  $names,
  $search,
  $selected,
  $tab,
  $version,
  pageMounted,
  reloadRequested,
  searchChanged,
  tabChanged,
} from "../../model/index.ts";
import { AgingCards } from "../kpi/AgingCards.tsx";
import { DebtorPanel, type PanelDialog } from "../side/DebtorPanel.tsx";
import { DebtorsTable } from "../table/DebtorsTable.tsx";

type Dialog = PanelDialog | "newOpening" | null;

function DebtorsPage() {
  const { t } = useTranslation("debts");
  const canAging = useCan({ anyOf: ["reports.finance.view", "debts.approve"] });
  const canLedger = useCan({ anyOf: ["reports.sales.view", "debts.payment.accept", "debts.create"] });
  const canLedgerPayable = useCan({ anyOf: ["purchases.pay", "reports.finance.view"] });
  const canPay = useCan({ permission: "debts.payment.accept" });
  const canOpen = useCan({ anyOf: ["stock.opening.manage", "debts.limit.manage"] });
  const canForgive = useCan({ permission: "debts.forgive" });
  const canCard = useCan({ permission: "debts.limit.manage" });
  // «Qaytarish» posts a cash movement: accounting.post (07 BO-06) + the server's cash.withdraw
  const canRefund = useCan({ permission: ["accounting.post", "cash.withdraw"] });
  const [params] = useSearchParams();
  const [
    mounted,
    direction,
    tab,
    onTab,
    counts,
    search,
    onSearch,
    selected,
    names,
    version,
    branchId,
    online,
    reload,
  ] = useUnit([
    pageMounted,
    $direction,
    $tab,
    tabChanged,
    $counts,
    $search,
    searchChanged,
    $selected,
    $names,
    $version,
    $branchId,
    $isOnline,
    reloadRequested,
  ]);
  const [dialog, setDialog] = useState<Dialog>(null);

  useEffect(() => {
    if (!canAging) return;
    const initialTab = params.get("tab");
    mounted({
      today: todayIso(),
      direction: params.get("direction") === "payable" ? "payable" : "receivable",
      tab: isDebtorTab(initialTab) ? initialTab : "all",
      counterparty: params.get("counterparty"),
    });
    // Only on entry (24 §2).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, canAging]);

  if (!canAging) return <NoPermissionState />;

  const payable = direction === "payable";
  const tabs: DebtorTab[] = DEBTOR_TABS.filter((x) => x !== "over_limit" || (canForgive && !payable));
  const rights = {
    ledger: payable ? canLedgerPayable : canLedger,
    pay: canPay,
    open: canOpen,
    forgive: canForgive,
    card: canCard,
  };
  const close = () => setDialog(null);

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="flex flex-wrap items-center gap-2.5">
        {payable ? (
          <p className="text-[14px] font-bold" data-testid="direction-payable">
            {t("direction.payable")}
          </p>
        ) : null}
        <div className="grow" />
        <Button variant="secondary" onClick={() => reload()} aria-label={t("actions.reload")}>
          <Icon as={RefreshCw} size="sm" />
          {t("actions.reload")}
        </Button>
        {canOpen ? (
          <Button disabled={!online} onClick={() => setDialog("newOpening")} data-testid="new-opening">
            <Icon as={Plus} size="sm" />
            {payable ? t("opening.titlePayable") : t("opening.title")}
          </Button>
        ) : null}
      </div>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("offline")}
        </Banner>
      )}
      <AgingCards />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <Tabs value={tab} onValueChange={(v) => (isDebtorTab(v) ? onTab(v) : undefined)}>
              <TabsList aria-label={t("tabs.label")}>
                {tabs.map((x) => (
                  <TabsTrigger key={x} value={x} data-testid={`tab-${x}`}>
                    {t(`tabs.${x}`)}
                    <span className="rounded-full bg-accent px-1.5 text-[11px] font-extrabold">
                      {counts[x]}
                    </span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <div className="grow" />
            <SearchInput
              value={search}
              onSearch={(q) => onSearch(q)}
              placeholder={t("search")}
              aria-label={t("search")}
              maxLength={64}
              className="w-64"
            />
          </div>
          {tab === "aged" ? (
            <p className="text-[13px] text-foreground-secondary">{t("tabs.agedNote")}</p>
          ) : null}
          <DebtorsTable />
        </div>
        <div className="flex flex-col gap-3">
          {selected ? (
            <DebtorPanel row={selected} rights={rights} online={online} onDialog={setDialog} />
          ) : (
            <p className="rounded-2xl border border-dashed border-border p-6 text-center text-[13px] text-muted-foreground">
              {t("panel.pick")}
            </p>
          )}
          {payable ? null : <OverpaymentsBlock names={names} version={version} canRefund={canRefund} />}
        </div>
      </div>

      <LedgerSheet />
      {dialog === "card" && selected ? (
        <CustomerCardSheet
          counterpartyId={selected.counterparty_id}
          canEdit={canCard && online}
          onClose={close}
        />
      ) : null}
      {dialog === "opening" && selected ? (
        <OpeningDialog
          direction={direction}
          counterparty={{ id: selected.counterparty_id, name: selected.name }}
          branchId={branchId}
          onClose={close}
        />
      ) : null}
      {dialog === "newOpening" ? (
        <OpeningDialog direction={direction} counterparty={null} branchId={branchId} onClose={close} />
      ) : null}
      {dialog === "writeoff" && selected ? (
        <WriteoffDialog
          counterparty={{ id: selected.counterparty_id, name: selected.name }}
          balance={selected.balance as Money}
          branchId={branchId}
          onClose={close}
        />
      ) : null}
      {dialog === "flag" && selected ? (
        <FlagDialog
          counterparty={{ id: selected.counterparty_id, name: selected.name }}
          flagId={selected.doubtful_flag ? selected.doubtful_flag_id : null}
          onClose={close}
        />
      ) : null}
    </div>
  );
}

export const Debtors = {
  route: "debts",
  titleKey: "debts:title",
  Page: DebtorsPage,
} as const;
