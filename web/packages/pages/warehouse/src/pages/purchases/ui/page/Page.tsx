/**
 * BO-04 — Xaridlar (07, route /app/purchases): «Xaridnomalar» (ro'yxat–tafsilot, yaratish / tahrirlash /
 * yuborish / bekor qilish), «Kirimlar» (qoralama — qo'lda yoki xaridnomadan, o'tkazish, bekor qilish),
 * «Yetkazib beruvchiga to'lov» (B4: bank yoki kassadan naqd, taqsimot, avans — `purchases.pay`),
 * «Qaytarish» (o'tkazilgan kirimdan), «Yetkazib beruvchilar» (STIR bo'yicha to'ldirish, qarz).
 * Later stages, not rendered: AI-03 OCR (B6), e-ishonchnoma (B5). Offline: view only (PWA'da yaratish internet talab qiladi).
 * useEffect fires pageMounted (24 §2) and consumes the one-shot `?new=1` link (WEB-20).
 */
import { useUnit } from "effector-react";
import { Plus, WifiOff } from "lucide-react";
import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { useCan } from "@shared/state/permissions";
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

import { $currentWarehouse, $warehousesLoaded } from "#/entities/refs/index.ts";
import { ReceiptsTab } from "#/features/goods-receipts/index.ts";
import { PaymentsTab, paymentFormOpened } from "#/features/supplier-payments/index.ts";
import { PayablesTab } from "#/features/payables/index.ts";
import { OrdersTab } from "#/features/purchase-orders/index.ts";
import { ReturnsTab } from "#/features/supplier-returns/index.ts";
import { SuppliersTab } from "#/features/suppliers/index.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $draftReceipts,
  $orderSheetOpen,
  $tab,
  isPurchasesTab,
  orderSheetToggled,
  pageMounted,
  receiptFromOrderRequested,
  returnFromReceiptRequested,
  tabChanged,
} from "../../model/index.ts";

function PurchasesPage() {
  const { t } = useTranslation("warehouse");
  const canView = useCan({ permission: "stock.view" });
  const canCreate = useCan({ permission: "purchases.create" });
  const canReceive = useCan({ permission: "purchases.receive" });
  const canPost = useCan({ permission: "purchases.post" });
  const canReturn = useCan({ permission: "purchases.return" });
  const canPay = useCan({ permission: "purchases.pay" });
  // «Men qarzdorman» (B4): the payable aging needs `reports.finance.view` (or `debts.approve`), 07 BO-04
  const canPayables = useCan({ anyOf: ["reports.finance.view", "debts.approve"] });
  const canListStaff = useCan({ permission: "settings.users" });
  const online = useOnline();
  const [mounted, tab, onTab, drafts, warehouse, warehousesLoaded, fromOrder, fromReceipt] = useUnit([
    pageMounted,
    $tab,
    tabChanged,
    $draftReceipts,
    $currentWarehouse,
    $warehousesLoaded,
    receiptFromOrderRequested,
    returnFromReceiptRequested,
  ]);
  const [creatingOrder, setCreatingOrder] = useUnit([$orderSheetOpen, orderSheetToggled]);
  const [params, setParams] = useSearchParams();
  const newConsumed = useRef(false);

  // `?new=1` (e.g. «Xaridnoma tuzish» from BO-03) is used once, after the warehouses are known: the
  // sheet opens only when an order can be created here; the flag then leaves the URL either way.
  useEffect(() => {
    if (newConsumed.current || !warehousesLoaded || params.get("new") !== "1") return;
    newConsumed.current = true;
    if (warehouse && online && canCreate) {
      onTab("orders");
      setCreatingOrder(true);
    }
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("new");
        return next;
      },
      { replace: true },
    );
  }, [warehousesLoaded, warehouse, online, canCreate, params, setParams, onTab, setCreatingOrder]);

  useEffect(() => {
    if (!canView) return;
    const initial = params.get("tab");
    mounted({ tab: isPurchasesTab(initial) ? initial : "orders", canListStaff });
    // Only on entry (24 §2).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, canView, canListStaff]);

  // Lists and documents need `stock.view` (19 §8–§12 GET); purchases.* alone cannot read them.
  if (!canView) return <NoPermissionState />;

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="flex flex-wrap items-center gap-2.5">
        <p className="min-w-0 text-small text-foreground-secondary">{t("purchases.subtitle")}</p>
        <div className="grow" />
        {canCreate ? (
          <Button
            disabled={!online || !warehouse}
            onClick={() => {
              onTab("orders");
              setCreatingOrder(true);
            }}
          >
            <Icon as={Plus} size="sm" />
            {t("orders.create")}
          </Button>
        ) : null}
      </div>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("purchases.offline")}
        </Banner>
      )}
      <Tabs value={tab} onValueChange={(v) => (isPurchasesTab(v) ? onTab(v) : undefined)}>
        <TabsList aria-label={t("purchases.tabs.label")}>
          <TabsTrigger value="orders">{t("purchases.tabs.orders")}</TabsTrigger>
          <TabsTrigger value="receipts">
            {t("purchases.tabs.receipts")}
            {drafts ? (
              <span className="rounded-full bg-primary-soft px-1.5 text-[11px] font-extrabold text-primary-strong">
                {drafts}
              </span>
            ) : null}
          </TabsTrigger>
          {canPay ? <TabsTrigger value="payments">{t("purchases.tabs.payments")}</TabsTrigger> : null}
          <TabsTrigger value="returns">{t("purchases.tabs.returns")}</TabsTrigger>
          {canPayables ? <TabsTrigger value="payables">{t("purchases.tabs.payables")}</TabsTrigger> : null}
          <TabsTrigger value="suppliers">{t("purchases.tabs.suppliers")}</TabsTrigger>
        </TabsList>
        <TabsContent value="orders">
          <OrdersTab
            rights={{ create: canCreate, receive: canReceive }}
            online={online}
            warehouse={warehouse}
            createOpen={creatingOrder}
            onCreateOpenChange={setCreatingOrder}
            onCreateReceipt={(o) => fromOrder(o.id)}
          />
        </TabsContent>
        <TabsContent value="receipts">
          <ReceiptsTab
            rights={{ receive: canReceive, post: canPost, ret: canReturn }}
            online={online}
            warehouse={warehouse}
            onCreateReturn={(r) => fromReceipt(r.id)}
          />
        </TabsContent>
        {canPay ? (
          <TabsContent value="payments">
            <PaymentsTab canPay={canPay} online={online} />
          </TabsContent>
        ) : null}
        <TabsContent value="returns">
          <ReturnsTab rights={{ create: canReturn, post: canPost }} online={online} />
        </TabsContent>
        {canPayables ? (
          <TabsContent value="payables">
            <PayablesTab
              canPay={canPay}
              online={online}
              onPay={(supplierId) => {
                onTab("payments");
                paymentFormOpened({ supplierId });
              }}
            />
          </TabsContent>
        ) : null}
        <TabsContent value="suppliers">
          <SuppliersTab canManage={canCreate} online={online} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export const Purchases = {
  route: "purchases",
  titleKey: "warehouse:purchases.title",
  Page: PurchasesPage,
} as const;
