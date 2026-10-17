/**
 * POS-02 — Sotish paneli (07, route /pos/sale; mockup Main.dc.html) with POS-03 (/pos/sale/payment) and POS-04
 * (/pos/sale/receipt) as overlays. Fully keyboard / scanner operated (07 "Klaviatura"):
 *   F1 scanner field · F2 discount · F3 customer · F4 payment · F5 debt (nasiya) · F9 POS-11 lookup ·
 *   F12 POS-12 sync · +/- qty of the selected line · ↑/↓ select line · Delete void line · Enter scan / accept.
 * States: loading (catalog snapshot), empty («Chekni boshlang, skanerlang»), error (product not found, marking),
 * offline (TO'LOV stays active), fiscal-blocked (48 h — no lines, no payment), fm locked, no-permission.
 */
import { useUnit } from "effector-react";
import { CircleAlert, Lock, ScanBarcode, ShieldAlert, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { $fiscalLadder, customers } from "@shared/offline";
import { Banner, Button, Icon, NoPermissionState, Skeleton, toast } from "@shared/ui";

import {
  $draft,
  customerSet,
  qtyChanged,
  qtyStepped,
  selectionMoved,
} from "#/entities/receipt-draft/index.ts";
import { $posCashier, $posShift, cashierCan } from "#/entities/pos-session/index.ts";
import { Ladder46Modal } from "#/features/fiscal-ladder/index.tsx";
import { dyn, errorText } from "#/shared/lib/i18n-errors.ts";
import { useBarcodeWedge } from "#/shared/lib/use-barcode-wedge.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

import { $contextLoaded, $fiscalDeviceLocked, saleScreenOpened } from "../../model/context.ts";
import { modeChosen, paymentOpened, saleCompleted } from "../../model/payment.ts";
import {
  $awaitingMarking,
  $scanError,
  $weighing,
  codeScanned,
  scanErrorDismissed,
  scanPromptClosed,
  weightEntered,
} from "../../model/scan.ts";
import { voidFx, voidRequested } from "../../model/void.ts";
import { PaymentDialog } from "../PaymentDialog.tsx";
import { ProductPanel } from "../ProductPanel.tsx";
import { ReceiptDialog } from "../ReceiptDialog.tsx";
import { ReceiptPanel } from "../ReceiptPanel.tsx";
import { CustomerDialog, DiscountDialog, QtyDialog, VoidConfirm, WeightDialog } from "../SaleDialogs.tsx";

export const SALE_PATH = "/pos/sale";
export const PAYMENT_PATH = "/pos/sale/payment";
export const RECEIPT_PATH = "/pos/sale/receipt";
export const LOOKUP_PATH = "/pos/lookup";
export const SYNC_PATH = "/pos/sync";
export const EQUIPMENT_PATH = "/pos/settings/devices";

type Overlay = "payment" | "receipt" | null;
type Dialogs = "discount" | "customer" | { qty: string } | { void: string | null } | null;

function SalePage({ overlay }: { overlay: Overlay }) {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const navigate = useNavigate();
  const [draft, cashier, shift, ladder, fmLocked, loaded, scanError, awaiting, weighing, voiding] = useUnit([
    $draft,
    $posCashier,
    $posShift,
    $fiscalLadder,
    $fiscalDeviceLocked,
    $contextLoaded,
    $scanError,
    $awaitingMarking,
    $weighing,
    voidFx.pending,
  ]);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dialog, setDialog] = useState<Dialogs>(null);
  const [ladderAck, setLadderAck] = useState(false);
  const [customer, setCustomer] = useState<{ id: string; name: string | null } | null>(null);
  const customerName = draft.customerId && customer?.id === draft.customerId ? customer.name : null;

  useEffect(() => {
    saleScreenOpened();
  }, []);
  useEffect(() => {
    const id = draft.customerId;
    if (!id) return;
    void customers.get(id).then((c) => setCustomer({ id, name: c?.name ?? null }));
  }, [draft.customerId]);
  useEffect(
    () =>
      saleCompleted.watch((sale) => {
        if (sale.fiscal) void navigate(RECEIPT_PATH);
        else {
          toast.success(tt("payment.debtSaved"));
          void navigate(SALE_PATH);
        }
      }),
    [navigate, tt],
  );

  const blocked = ladder.level === "blocked48";
  const canSell = cashierCan(cashier, "sales.create");
  const canDiscount = cashierCan(cashier, "discount.give");
  const canVoid = cashierCan(cashier, "sales.void");
  const canDebt = cashierCan(cashier, "debts.create");
  const linesDisabled = blocked || !canSell || overlay !== null;
  const payDisabled = blocked || fmLocked || !shift || !canSell;

  const focusScanner = () => inputRef.current?.focus();
  const openPayment = (mode?: "debt") => {
    if (payDisabled || draft.lines.length === 0) return;
    if (ladder.level === "modal46" && !ladderAck) {
      setLadderAck(true);
      return;
    }
    paymentOpened();
    if (mode) modeChosen(mode);
    void navigate(PAYMENT_PATH);
  };

  useBarcodeWedge(
    (code) => {
      if (linesDisabled) return;
      codeScanned(code);
    },
    overlay === null && dialog === null && weighing === null,
  );

  const selected = draft.lines.find((l) => l.id === draft.selectedLineId) ?? null;
  const lineKey = (run: () => unknown) => {
    const field = inputRef.current;
    const active = typeof document !== "undefined" ? document.activeElement : null;
    if (active instanceof HTMLInputElement && (active !== field || field.value !== "")) return false;
    if (linesDisabled) return false;
    run();
    return true;
  };
  useHotkeys(
    [
      { key: "F1", handler: focusScanner },
      { key: "F2", handler: () => canDiscount && draft.lines.length > 0 && setDialog("discount") },
      { key: "F3", handler: () => setDialog("customer") },
      { key: "F4", handler: () => openPayment() },
      { key: "F5", handler: () => canDebt && openPayment("debt") },
      // line keys also work from the (empty) scanner field — the cashier never has to leave it
      {
        key: "+",
        allowInInput: true,
        handler: () => lineKey(() => selected && qtyStepped({ lineId: selected.id, delta: 1 })),
      },
      {
        key: "-",
        allowInInput: true,
        handler: () => lineKey(() => selected && qtyStepped({ lineId: selected.id, delta: -1 })),
      },
      { key: "ArrowUp", allowInInput: true, handler: () => lineKey(() => selectionMoved(-1)) },
      { key: "ArrowDown", allowInInput: true, handler: () => lineKey(() => selectionMoved(1)) },
      {
        key: "Delete",
        allowInInput: true,
        handler: () => lineKey(() => selected && canVoid && setDialog({ void: selected.id })),
      },
      {
        key: "Escape",
        allowInInput: true,
        handler: () => (awaiting ? scanPromptClosed() : scanErrorDismissed()),
      },
    ],
    overlay === null && dialog === null && weighing === null,
  );

  // the scanner field keeps the focus between actions (06 §1.1)
  useEffect(() => {
    if (overlay === null && dialog === null) focusScanner();
  }, [overlay, dialog, draft.lines.length]);

  if (!canSell && cashier) return <NoPermissionState />;

  const receiptLabel = t("sale.receiptLabel", { ref: draft.ref.slice(-6).toUpperCase() });
  const qtyLine =
    dialog && typeof dialog === "object" && "qty" in dialog
      ? draft.lines.find((l) => l.id === dialog.qty)
      : undefined;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {blocked ? (
        <Banner
          tone="destructive"
          icon={Lock}
          live="assertive"
          action={
            <Button size="sm" variant="secondary" onClick={() => void navigate(SYNC_PATH)}>
              {t("fiscalLadder.syncAction")}
            </Button>
          }
        >
          <span data-testid="fiscal-blocked">{t("fiscalLadder.blockedBanner")}</span>
        </Banner>
      ) : null}
      {fmLocked ? (
        <Banner tone="destructive" icon={ShieldAlert}>
          {errorText("FISCAL_DEVICE_LOCKED")}
        </Banner>
      ) : null}
      {!shift ? (
        <Banner tone="warning" icon={CircleAlert}>
          {t("sale.noShift")}
        </Banner>
      ) : null}
      {awaiting ? (
        <Banner
          tone="info"
          icon={ScanBarcode}
          live="assertive"
          action={
            <Button
              size="sm"
              variant="ghost"
              aria-label={t("sale.cancel")}
              onClick={() => scanPromptClosed()}
            >
              <Icon as={X} size="sm" />
            </Button>
          }
        >
          <span data-testid="marking-prompt">{t("sale.scanMarking", { name: awaiting.product.name })}</span>
        </Banner>
      ) : null}
      {scanError ? (
        <Banner
          tone="destructive"
          icon={CircleAlert}
          live="assertive"
          action={
            <Button
              size="sm"
              variant="ghost"
              aria-label={t("sale.cancel")}
              onClick={() => scanErrorDismissed()}
            >
              <Icon as={X} size="sm" />
            </Button>
          }
        >
          <span data-testid="scan-error">{errorText(scanError.code, scanError.params ?? {})}</span>
        </Banner>
      ) : null}

      <div className="flex min-h-0 flex-1 gap-3">
        {loaded ? (
          <ProductPanel disabled={linesDisabled} inputRef={inputRef} />
        ) : (
          <div className="flex flex-1 flex-col gap-3 rounded-2xl border border-border bg-card p-4">
            <Skeleton className="h-14" />
            <Skeleton className="h-12" />
            <Skeleton className="flex-1" />
          </div>
        )}
        <ReceiptPanel
          receiptLabel={receiptLabel}
          customerName={customerName}
          canDiscount={canDiscount && !blocked}
          canVoid={canVoid}
          canDebt={canDebt}
          payDisabled={payDisabled}
          linesDisabled={linesDisabled}
          onCustomer={() => setDialog("customer")}
          onDiscount={() => setDialog("discount")}
          onDebt={() => openPayment("debt")}
          onVoidReceipt={() => setDialog({ void: null })}
          onVoidLine={(id) => setDialog({ void: id })}
          onQty={(id) => setDialog({ qty: id })}
          onPay={() => openPayment()}
        />
      </div>

      {weighing ? (
        <WeightDialog
          view={weighing}
          onSubmit={(qty) => weightEntered({ view: weighing, qty })}
          onClose={() => scanPromptClosed()}
        />
      ) : null}
      {dialog === "discount" ? <DiscountDialog onClose={() => setDialog(null)} /> : null}
      {dialog === "customer" ? (
        <CustomerDialog
          selectedId={draft.customerId}
          onSelect={(c) => {
            customerSet(c?.id ?? null);
            setDialog(null);
          }}
          onClose={() => setDialog(null)}
        />
      ) : null}
      {qtyLine ? (
        <QtyDialog
          title={t("sale.qtyTitle", { name: qtyLine.name })}
          unit={qtyLine.unitCode}
          initial={qtyLine.qty.replace(/\.?0+$/, "")}
          fractional={qtyLine.fractional}
          onSubmit={(qty) => {
            qtyChanged({ lineId: qtyLine.id, qty });
            setDialog(null);
          }}
          onClose={() => setDialog(null)}
        />
      ) : null}
      {dialog && typeof dialog === "object" && "void" in dialog ? (
        <VoidConfirm
          whole={dialog.void === null}
          pending={voiding}
          onConfirm={() => {
            voidRequested({ lineId: dialog.void });
            setDialog(null);
          }}
          onClose={() => setDialog(null)}
        />
      ) : null}
      {ladderAck && overlay === null && ladder.level === "modal46" ? (
        <Ladder46Modal
          onOk={() => {
            paymentOpened();
            void navigate(PAYMENT_PATH);
          }}
        />
      ) : null}

      {overlay === "payment" ? (
        <PaymentDialog
          receiptLabel={receiptLabel}
          onDone={() => {
            setLadderAck(false);
            void navigate(SALE_PATH);
          }}
        />
      ) : null}
      {overlay === "receipt" ? (
        <ReceiptDialog
          equipmentPath={EQUIPMENT_PATH}
          onNewReceipt={() => {
            setLadderAck(false);
            void navigate(SALE_PATH);
          }}
        />
      ) : null}
    </div>
  );
}

export const Sale = {
  route: "sale",
  titleKey: "pos:sale.title",
  Page: () => <SalePage overlay={null} />,
} as const;
export const SalePayment = {
  route: "sale/payment",
  titleKey: "pos:payment.title",
  Page: () => <SalePage overlay="payment" />,
} as const;
export const SaleReceipt = {
  route: "sale/receipt",
  titleKey: "pos:receipt.title",
  Page: () => <SalePage overlay="receipt" />,
} as const;
