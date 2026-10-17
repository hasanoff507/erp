/**
 * POS-08 — Yetkazib beruvchidan tovar qabul qilish (07 POS-08, maket Pos08Kirim.dc.html; route
 * /pos/warehouse/receive). PO select → lines (ordered / received −/+ / discrepancy reason / marking codes),
 * scanner (F1) compares with the order, e-ishonchnoma number, «Keyinroq davom etish» (draft) and
 * «Qabulni yakunlash» (F9; confirmation on discrepancy). Online only — offline shows «Tovar qabul qilish uchun
 * internet kerak», scanning continues locally.
 */
import { useUnit } from "effector-react";
import { AlertTriangle, CheckCircle2, PackageCheck, Trash2, WifiOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatDate } from "@shared/lib/date";
import { $isOnline } from "@shared/state/network";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Icon,
  Input,
  Kbd,
  Label,
  NativeSelect,
  NoPermissionState,
  StatusChip,
} from "@shared/ui";

import { usePosPermission } from "#/entities/pos-session/index.ts";
import { QtyStepper, ScanField, WhScreen, trimQty } from "#/features/wh-scan/index.ts";
import { tashkentDateTime } from "#/shared/lib/dates.ts";
import { errorText } from "#/shared/lib/i18n-errors.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

import {
  $canSave,
  $draftLoaded,
  $error,
  $finished,
  $lines,
  $loading,
  $order,
  $orders,
  $ordersLoaded,
  $poa,
  $problems,
  $saved,
  $saving,
  DISCREPANCY_REASONS,
  costChanged,
  discrepancyCount,
  errorDismissed,
  goodsReceiptOpened,
  hasDiscrepancy,
  markingAdded,
  markingRemoved,
  orderSelected,
  poaChanged,
  reasonChanged,
  receivedChanged,
  saveRequested,
  scanned,
  type DiscrepancyReason,
  type ReceiptError,
  type ReceiveLine,
} from "../../model/index.ts";

const WAREHOUSE_HUB = "/pos/warehouse";

function useErrorMessage(error: ReceiptError | null): string | null {
  const { t } = useTranslation("pos");
  if (!error) return null;
  switch (error.kind) {
    case "not_in_order":
      return t("goodsReceipt.notInOrder", { name: error.name });
    case "unknown_barcode":
      return t("goodsReceipt.unknownBarcode", { code: error.code });
    case "check_digit":
      return t("stockCount.checkDigit", { code: error.code });
    case "marking_duplicate":
      return t("goodsReceipt.markingDuplicate");
    default:
      return errorText(error.code, error.params);
  }
}

function GoodsReceiptPage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const canReceive = usePosPermission("purchases.receive");
  const [online, orders, ordersLoaded, order, lines, error, saving, canSave, finished, saved, draftLoaded, poa,
    loading] = useUnit([
    $isOnline, $orders, $ordersLoaded, $order, $lines, $error, $saving, $canSave, $finished, $saved, $draftLoaded,
    $poa, $loading,
  ]); // prettier-ignore
  const errorMessage = useErrorMessage(error);
  const scanRef = useRef<HTMLInputElement | null>(null);
  const [confirm, setConfirm] = useState(false);
  const diffs = discrepancyCount(lines.filter((l) => l.scanned || hasDiscrepancy(l)));

  useEffect(() => {
    if (canReceive) goodsReceiptOpened();
  }, [canReceive]);

  const finish = () => {
    if (!order || !online || !canSave || saving) return;
    if (diffs > 0) setConfirm(true);
    else saveRequested({ finish: true });
  };

  useHotkeys([
    { key: "F1", handler: () => scanRef.current?.focus() },
    { key: "F9", handler: finish },
    { key: "Escape", allowInInput: true, handler: () => navigate(WAREHOUSE_HUB) },
  ]);

  if (!canReceive) return <NoPermissionState />;

  return (
    <WhScreen
      title={t("goodsReceipt.title")}
      subtitle={order ? `${order.number ?? ""} · ${order.supplier.name ?? ""}` : undefined}
      onBack={() => navigate(WAREHOUSE_HUB)}
      testId="pos-goods-receipt"
      actions={
        order ? (
          <>
            <Button
              size="pos"
              variant="secondary"
              disabled={!online || !canSave || saving}
              onClick={() => saveRequested({ finish: false })}
            >
              {t("goodsReceipt.later")}
            </Button>
            <Button
              size="pos"
              disabled={!online || !canSave || saving}
              onClick={finish}
              data-testid="receipt-finish"
            >
              {t("goodsReceipt.finish")}
              <Kbd keys="F9" inverted />
            </Button>
          </>
        ) : null
      }
    >
      {!online ? (
        <Banner tone="warning" icon={WifiOff} className="mb-3" live="assertive">
          {order ? t("goodsReceipt.offlineScan") : t("goodsReceipt.offline")}
        </Banner>
      ) : null}
      {finished ? (
        <Banner tone="success" icon={CheckCircle2} className="mb-3">
          <span data-testid="receipt-finished">
            {t("goodsReceipt.finished", { id: finished.number ?? "" })}
          </span>
          {finished.marking_acceptance?.due_at ? (
            <span className="block">
              {t("goodsReceipt.markingDeadline", {
                at: tashkentDateTime(finished.marking_acceptance.due_at),
              })}
            </span>
          ) : null}
        </Banner>
      ) : null}
      {saved && !finished ? (
        <Banner tone="success" icon={CheckCircle2} className="mb-3">
          {t("goodsReceipt.saved")}
        </Banner>
      ) : null}
      {draftLoaded && !saved ? (
        <Banner tone="info" icon={PackageCheck} className="mb-3">
          {t("goodsReceipt.draftLoaded")}
        </Banner>
      ) : null}
      {errorMessage ? (
        <Banner
          tone="destructive"
          icon={AlertTriangle}
          className="mb-3"
          action={
            <Button size="sm" variant="ghost" onClick={() => errorDismissed()}>
              ✕
            </Button>
          }
        >
          <span data-testid="receipt-error">{errorMessage}</span>
        </Banner>
      ) : null}

      <Card className="mb-3 grid gap-3 p-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="receipt-po">{t("goodsReceipt.po")}</Label>
          <NativeSelect
            id="receipt-po"
            value={order?.id ?? ""}
            disabled={!online || loading}
            onChange={(e) => orderSelected(e.target.value || null)}
            options={[
              {
                value: "",
                label:
                  ordersLoaded && orders.length === 0
                    ? t("goodsReceipt.noOrders")
                    : t("goodsReceipt.poPlaceholder"),
              },
              ...orders.map((o) => ({
                value: o.id,
                label: t("goodsReceipt.poRow", {
                  number: o.number ?? "—",
                  supplier: o.supplier.name ?? "",
                  date: formatDate(o.doc_date),
                }),
              })),
            ]}
            wrapperClassName="w-full"
            className="h-12"
          />
        </div>
        <div>
          <Label htmlFor="receipt-poa">{t("goodsReceipt.poa")}</Label>
          <Input
            id="receipt-poa"
            value={poa}
            maxLength={64}
            placeholder={t("goodsReceipt.poaHint")}
            onChange={(e) => poaChanged(e.target.value)}
            disabled={!order}
            className="h-12"
          />
        </div>
      </Card>

      {!order ? (
        <EmptyState icon={PackageCheck} title={t("goodsReceipt.empty")} />
      ) : (
        <div className="flex flex-col gap-3">
          <ScanField onScan={(code) => scanned(code)} inputRef={scanRef} />
          {lines.length === 0 ? (
            <EmptyState icon={PackageCheck} title={t("goodsReceipt.noLines")} />
          ) : (
            <Card className="p-0">
              <ul className="divide-y divide-border" data-testid="receipt-lines">
                {lines.map((l) => (
                  <ReceiptLineRow key={l.productId} line={l} />
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("goodsReceipt.confirmTitle")}
        description={t("goodsReceipt.confirmBody", { count: diffs })}
        confirmLabel={t("goodsReceipt.finish")}
        pending={saving}
        onConfirm={() => {
          setConfirm(false);
          saveRequested({ finish: true });
        }}
      />
    </WhScreen>
  );
}

function ReceiptLineRow({ line }: { line: ReceiveLine }) {
  const { t } = useTranslation("pos");
  const problems = useUnit($problems)[line.productId] ?? [];
  const [manual, setManual] = useState("");
  const diff = hasDiscrepancy(line);
  return (
    <li className="flex flex-col gap-2 px-4 py-3" data-testid="receipt-line">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-bold">{line.name}</p>
          <p className="text-[12px] text-muted-foreground">
            {t("goodsReceipt.cols.ordered")}: {trimQty(line.remaining)} {line.unitCode ?? ""}
            {line.scanned ? ` · ${t("goodsReceipt.scanned", { count: trimQty(line.received) })}` : ""}
          </p>
        </div>
        <QtyStepper
          value={line.received}
          label={`${t("goodsReceipt.cols.received")} — ${line.name}`}
          onChange={(qty) => receivedChanged({ productId: line.productId, qty })}
        />
        {diff ? <StatusChip tone="warning">{t("goodsReceipt.cols.reason")}</StatusChip> : null}
      </div>
      {diff ? (
        <NativeSelect
          aria-label={t("goodsReceipt.cols.reason")}
          value={line.reason ?? ""}
          onChange={(e) =>
            reasonChanged({
              productId: line.productId,
              reason: (e.target.value || null) as DiscrepancyReason | null,
            })
          }
          options={[
            { value: "", label: t("goodsReceipt.reason.placeholder") },
            ...DISCREPANCY_REASONS.map((r) => ({ value: r, label: t(`goodsReceipt.reason.${r}`) })),
          ]}
          wrapperClassName="w-full sm:w-72"
          className="h-12"
        />
      ) : null}
      {line.price === null ? (
        <div className="flex items-center gap-2">
          <Label htmlFor={`cost-${line.productId}`}>{t("goodsReceipt.cost")}</Label>
          <Input
            id={`cost-${line.productId}`}
            inputMode="decimal"
            value={line.cost}
            onChange={(e) => costChanged({ productId: line.productId, cost: e.target.value })}
            className="h-12 w-40"
          />
        </div>
      ) : null}
      {line.isMarked ? (
        <div className="flex flex-col gap-1">
          <p className="text-[13px] font-semibold">
            {t("goodsReceipt.marking", { count: line.markingCodes.length, qty: trimQty(line.received) })}
          </p>
          <ul className="flex flex-wrap gap-1">
            {line.markingCodes.map((c) => (
              <li
                key={c}
                className="flex items-center gap-1 rounded bg-accent px-2 py-1 font-mono text-[11px]"
              >
                {c.slice(0, 31)}
                <button
                  type="button"
                  aria-label={t("transfers.remove")}
                  onClick={() => markingRemoved({ productId: line.productId, code: c })}
                >
                  <Icon as={Trash2} size="sm" />
                </button>
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <Input
              aria-label={t("goodsReceipt.markingManual")}
              placeholder={t("goodsReceipt.markingManual")}
              value={manual}
              maxLength={256}
              onChange={(e) => setManual(e.target.value)}
              className="h-12 flex-1 font-mono"
            />
            <Button
              size="pos"
              variant="secondary"
              disabled={!manual.trim()}
              onClick={() => {
                markingAdded({ productId: line.productId, code: manual.trim() });
                setManual("");
              }}
            >
              {t("goodsReceipt.markingAdd")}
            </Button>
          </div>
        </div>
      ) : null}
      {problems.map((p) => (
        <p key={p} className="text-[12px] font-semibold text-destructive-strong">
          {p === "reason_required"
            ? t("goodsReceipt.reasonRequired")
            : p === "cost_required"
              ? t("goodsReceipt.costRequired")
              : t("goodsReceipt.markingMismatch")}
        </p>
      ))}
    </li>
  );
}

export const GoodsReceipt = {
  route: "warehouse/receive",
  titleKey: "pos:goodsReceipt.title",
  Page: GoodsReceiptPage,
} as const;
