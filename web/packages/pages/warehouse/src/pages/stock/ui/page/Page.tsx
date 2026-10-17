/**
 * BO-03 — Ombor qoldig'i (+ Ko'chirishlar, Inventarizatsiyalar) — 07, route /app/warehouse/stock,
 * `stock.view`. Bosqich 2: «Qoldiq» (KPI, banner, filters, balances / expiring lots), «Ko'chirishlar»
 * (US-M06-03, B2-T11), «Inventarizatsiyalar» (review → post), actions «Hisobdan chiqarish»,
 * «Inventarizatsiya», «Ko'chirish». The current branch only: «Barchasi» (consolidation) needs
 * `GET /reports/stock` (Bosqich 4); «Eksport» (`reports.export`) is Bosqich 4; e-TTN signing /
 * manual registration are Bosqich 5. Offline: view only, writes disabled (qaror #54).
 * useEffect only fires pageMounted (24 §2).
 */
import { useUnit } from "effector-react";
import { ArrowLeftRight, ClipboardList, Info, Trash2, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { useCan } from "@shared/state/permissions";
import { $branches } from "@shared/state/session";
import {
  Banner,
  Button,
  Icon,
  NoPermissionState,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@shared/ui";

import { $warehousesLoaded, useBranchName } from "#/entities/refs/index.ts";
import { CountsTab, StartCountDialog } from "#/features/stock-counts/index.ts";
import { CreateTransferSheet, TransfersTab } from "#/features/transfers/index.ts";
import { WriteOffSheet, lotsRequested, type WriteOffPreset } from "#/features/write-off/index.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $branchId,
  $error,
  $reviewCount,
  $tab,
  $transit,
  $warehouse,
  isStockTab,
  pageMounted,
  tabChanged,
  type Lot,
} from "../../model/index.ts";
import { BalancesTab } from "../balances/BalancesTab.tsx";
import { TransfersDigest } from "../digest/TransfersDigest.tsx";
import { Kpis } from "../kpi/Kpis.tsx";

function Badge({ children, tone = "neutral" }: { children: number; tone?: "neutral" | "destructive" }) {
  return (
    <span
      className={
        tone === "destructive"
          ? "rounded-full bg-destructive-soft px-1.5 text-[11px] font-extrabold text-destructive-strong"
          : "rounded-full bg-primary-soft px-1.5 text-[11px] font-extrabold text-primary-strong"
      }
    >
      {children}
    </span>
  );
}

function StockPage() {
  const { t } = useTranslation("warehouse");
  const canView = useCan({ permission: "stock.view" });
  const canTransfer = useCan({ permission: "transfer.create" });
  const canReceive = useCan({ permission: "transfer.receive" });
  const canCountCreate = useCan({ permission: "stock.count.create" });
  const canCountPost = useCan({ permission: "stock.count.post" });
  const canWriteOff = useCan({ permission: "stock.writeoff" });
  const canCreatePo = useCan({ permission: "purchases.create" });
  const canListStaff = useCan({ permission: "settings.users" });
  const online = useOnline();
  const [mounted, tab, onTab, error, warehouse, branchId, branches, loaded, transit, review, requestLots] =
    useUnit([
      pageMounted,
      $tab,
      tabChanged,
      $error,
      $warehouse,
      $branchId,
      $branches,
      $warehousesLoaded,
      $transit,
      $reviewCount,
      lotsRequested,
    ]);
  const branchName = useBranchName();
  const [params] = useSearchParams();
  const [sheet, setSheet] = useState<"transfer" | "count" | "writeOff" | null>(null);
  const [preset, setPreset] = useState<WriteOffPreset | null>(null);

  useEffect(() => {
    if (!canView) return;
    mounted({ today: dayjs().format("YYYY-MM-DD"), canListStaff });
    const initial = params.get("tab");
    if (isStockTab(initial)) onTab(initial);
    // Only on entry (24 §2) — the tab is then driven by the model.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, canView, canListStaff]);

  if (!canView || error?.status === 403) return <NoPermissionState />;

  const writable = online && warehouse !== null;
  const openWriteOff = (lot: Lot | null) => {
    if (lot && warehouse) {
      requestLots({ warehouseId: warehouse.id, productId: lot.product_id });
      setPreset({
        productId: lot.product_id,
        name: lot.product_name,
        unitCode: "",
        lotId: lot.id,
        reason: "expired",
      });
    } else {
      setPreset(null);
    }
    setSheet("writeOff");
  };
  const transferRights = { create: canTransfer, receive: canReceive, branchIds: branches.map((b) => b.id) };

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="flex flex-wrap items-center gap-2.5">
        <p className="min-w-0 text-small text-foreground-secondary">
          {branchId && warehouse
            ? t("stock.subtitle", { branch: branchName(branchId), warehouse: warehouse.name })
            : t("stock.subtitleNoBranch")}
        </p>
        <div className="grow" />
        {canWriteOff ? (
          <Button variant="secondary" disabled={!writable} onClick={() => openWriteOff(null)}>
            <Icon as={Trash2} size="sm" />
            {t("actions.writeOff")}
          </Button>
        ) : null}
        {canCountCreate ? (
          <Button variant="secondary" disabled={!writable} onClick={() => setSheet("count")}>
            <Icon as={ClipboardList} size="sm" />
            {t("actions.startCount")}
          </Button>
        ) : null}
        {canTransfer ? (
          <Button disabled={!writable} onClick={() => setSheet("transfer")}>
            <Icon as={ArrowLeftRight} size="sm" />
            {t("actions.transfer")}
          </Button>
        ) : null}
      </div>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("stock.offline")}
        </Banner>
      )}
      {branchId === null ? (
        <Banner tone="info" icon={Info}>
          {t("stock.allBranches")}
        </Banner>
      ) : loaded && warehouse === null ? (
        <Banner tone="warning" icon={Info}>
          {t("stock.noWarehouse")}
        </Banner>
      ) : null}
      <Tabs value={tab} onValueChange={(v) => (isStockTab(v) ? onTab(v) : undefined)}>
        <TabsList aria-label={t("tabs.label")}>
          <TabsTrigger value="balances">{t("tabs.balances")}</TabsTrigger>
          <TabsTrigger value="transfers">
            {t("tabs.transfers")}
            {transit && transit.inTransit > 0 ? (
              <Badge tone={transit.overdue > 0 ? "destructive" : "neutral"}>{transit.inTransit}</Badge>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="counts">
            {t("tabs.counts")}
            {review ? <Badge>{review}</Badge> : null}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="balances" className="flex flex-col gap-[18px]">
          {warehouse ? (
            <>
              <Kpis branchName={branchId ? branchName(branchId) : ""} />
              <BalancesTab
                canWriteOff={canWriteOff}
                canCreatePo={canCreatePo}
                online={online}
                onWriteOffLot={openWriteOff}
              />
              <TransfersDigest rights={transferRights} online={online} />
            </>
          ) : null}
        </TabsContent>
        <TabsContent value="transfers">
          <TransfersTab rights={transferRights} online={online} />
        </TabsContent>
        <TabsContent value="counts">
          <CountsTab rights={{ create: canCountCreate, post: canCountPost }} online={online} />
        </TabsContent>
      </Tabs>
      <CreateTransferSheet
        open={sheet === "transfer"}
        onClose={() => setSheet(null)}
        source={warehouse}
        online={online}
      />
      <StartCountDialog open={sheet === "count"} onClose={() => setSheet(null)} warehouse={warehouse} />
      <WriteOffSheet
        open={sheet === "writeOff"}
        onClose={() => setSheet(null)}
        warehouse={warehouse}
        preset={preset}
        online={online}
      />
    </div>
  );
}

export const Stock = {
  route: "warehouse/stock",
  titleKey: "warehouse:stock.title",
  Page: StockPage,
} as const;
