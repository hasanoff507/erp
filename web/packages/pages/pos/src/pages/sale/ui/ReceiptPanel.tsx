/**
 * POS-02 right column (07 POS-02, mockup Main.dc.html): receipt number, «+ Mijoz» (F3), lines (name,
 * `narx × miqdor` or discount / marking note, `−`/`+`, line sum), totals (Oraliq summa, Chegirma, «Shu jumladan
 * QQS» by rate — US-M10-01, JAMI the largest figure), CHEGIRMA (F2) · NASIYA (F5) · BEKOR and «TO'LOVGA O'TISH» (F4).
 */
import { useUnit } from "effector-react";
import { Minus, Plus, ScanBarcode, ShoppingCart, UserPlus, X } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney, formatPercent, formatQty } from "@shared/lib/format";
import { Button, cn, EmptyState, Icon, Kbd } from "@shared/ui";

import {
  $draft,
  $totals,
  lineSelected,
  qtyStepped,
  type PricedLine,
} from "#/entities/receipt-draft/index.ts";

export interface ReceiptPanelProps {
  receiptLabel: string;
  customerName: string | null;
  canDiscount: boolean;
  canVoid: boolean;
  canDebt: boolean;
  payDisabled: boolean;
  linesDisabled: boolean;
  onCustomer: () => void;
  onDiscount: () => void;
  onDebt: () => void;
  onVoidReceipt: () => void;
  onVoidLine: (lineId: string) => void;
  onQty: (lineId: string) => void;
  onPay: () => void;
}

function LineRow({
  line,
  selected,
  disabled,
  canVoid,
  onVoid,
  onQty,
}: {
  line: PricedLine;
  selected: boolean;
  disabled: boolean;
  canVoid: boolean;
  onVoid: () => void;
  onQty: () => void;
}) {
  const { t } = useTranslation("pos");
  const [select, step] = useUnit([lineSelected, qtyStepped]);
  const qtyText = formatQty(line.qty, line.fractional ? "fractional" : "integer");
  const meta = line.markingCode
    ? t("sale.markingScanned")
    : `${formatMoney(line.price, { withCurrency: false })} × ${qtyText}${line.fractional ? ` ${line.unitCode}` : ""}`;
  const stepper = line.kind === "piece" && !line.markingCode;
  return (
    <li
      data-testid="receipt-line"
      aria-selected={selected}
      onClick={() => select(line.id)}
      className={cn(
        "flex items-center gap-2 rounded-xl border px-3 py-2",
        selected ? "border-primary bg-primary-soft/40" : "border-transparent",
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-[15px] font-bold">{line.name}</div>
        <div
          className={cn("text-[12px]", line.markingCode ? "text-primary-strong" : "text-muted-foreground")}
        >
          {meta}
          {line.markingWarning ? ` · ${t("sale.markingWarning")}` : ""}
        </div>
        {line.discount !== "0.00" ? (
          <div className="text-[12px] text-success-strong">
            {t("sale.lineDiscount", { amount: formatMoney(line.discount, { withCurrency: false }) })}
          </div>
        ) : null}
      </div>
      {stepper ? (
        <div className="flex items-center gap-1">
          <Button
            size="icon-pos"
            variant="secondary"
            aria-label={t("sale.qtyMinus")}
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              step({ lineId: line.id, delta: -1 });
            }}
          >
            <Icon as={Minus} size="lg" />
          </Button>
          <button
            type="button"
            data-testid="line-qty"
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              onQty();
            }}
            className="h-12 min-w-10 text-center text-[16px] font-extrabold"
          >
            {qtyText}
          </button>
          <Button
            size="icon-pos"
            variant="secondary"
            aria-label={t("sale.qtyPlus")}
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              step({ lineId: line.id, delta: 1 });
            }}
          >
            <Icon as={Plus} size="lg" />
          </Button>
        </div>
      ) : line.kind === "weighed" ? (
        <button
          type="button"
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation();
            onQty();
          }}
          className="h-12 rounded-lg border border-input px-3 text-[14px] font-bold"
        >
          {qtyText} {line.unitCode}
        </button>
      ) : null}
      <span data-testid="line-total" className="w-24 text-right text-[16px] font-extrabold">
        {formatMoney(line.total, { withCurrency: false })}
      </span>
      {canVoid ? (
        <Button
          size="icon-pos"
          variant="ghost"
          aria-label={t("sale.voidLine")}
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation();
            onVoid();
          }}
        >
          <Icon as={X} size="lg" />
        </Button>
      ) : null}
    </li>
  );
}

export function ReceiptPanel(props: ReceiptPanelProps) {
  const { t } = useTranslation("pos");
  const [draft, totals] = useUnit([$draft, $totals]);
  const empty = totals.lines.length === 0;

  return (
    <section className="flex w-[440px] shrink-0 flex-col rounded-2xl border border-border bg-card shadow-raised xl:w-[480px]">
      <header className="flex items-center gap-2 border-b border-border px-4 py-3">
        <span className="text-[16px] font-extrabold" data-testid="receipt-label">
          {props.receiptLabel}
        </span>
        <div className="grow" />
        <Button size="sm" variant="secondary" onClick={props.onCustomer} data-testid="customer-button">
          <Icon as={UserPlus} size="sm" />
          {props.customerName ?? t("sale.customer")}
          <Kbd keys="F3" />
        </Button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {empty ? (
          <EmptyState icon={ShoppingCart} title={t("sale.emptyTitle")} description={t("sale.emptyHint")} />
        ) : (
          <ul className="flex flex-col gap-1" aria-label={t("sale.linesLabel")}>
            {totals.lines.map((l) => (
              <LineRow
                key={l.id}
                line={l}
                selected={l.id === draft.selectedLineId}
                disabled={props.linesDisabled}
                canVoid={props.canVoid}
                onVoid={() => props.onVoidLine(l.id)}
                onQty={() => props.onQty(l.id)}
              />
            ))}
          </ul>
        )}
      </div>

      <dl className="flex flex-col gap-1 border-t border-border px-4 py-3 text-[14px]">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">{t("sale.subtotal")}</dt>
          <dd className="font-bold">{formatMoney(totals.subtotal, { withCurrency: false })}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">
            {t("sale.discount")}
            {draft.discount ? ` (${formatPercent(draft.discount.pct)})` : ""}
          </dt>
          <dd className="font-bold" data-testid="discount-total">
            {totals.discount === "0.00" ? "0" : `−${formatMoney(totals.discount, { withCurrency: false })}`}
          </dd>
        </div>
        {totals.vat.map((v) => (
          <div key={v.rate} className="flex justify-between" data-testid="vat-row">
            <dt className="text-muted-foreground">
              {t("sale.vatIncluded", { rate: formatPercent(v.rate) })}
            </dt>
            <dd className="font-bold">{formatMoney(v.amount, { precision: 2, withCurrency: false })}</dd>
          </div>
        ))}
        <div className="mt-1 flex items-baseline justify-between">
          <dt className="text-[18px] font-extrabold">{t("sale.total")}</dt>
          <dd className="text-[34px] font-extrabold leading-none" data-testid="receipt-total">
            {formatMoney(totals.total)}
          </dd>
        </div>
      </dl>

      <div className="grid grid-cols-3 gap-2 px-4 pb-2">
        <Button
          size="pos"
          variant="secondary"
          disabled={!props.canDiscount || empty}
          onClick={props.onDiscount}
        >
          {t("sale.discountButton")}
          <Kbd keys="F2" />
        </Button>
        <Button
          size="pos"
          variant="warning"
          disabled={!props.canDebt || empty || props.payDisabled}
          onClick={props.onDebt}
        >
          {t("sale.debtButton")}
          <Kbd keys="F5" />
        </Button>
        <Button
          size="pos"
          variant="destructive-outline"
          disabled={!props.canVoid || empty}
          onClick={props.onVoidReceipt}
          data-testid="void-receipt"
        >
          {t("sale.voidButton")}
        </Button>
      </div>
      <div className="px-4 pb-4">
        <Button
          size="pos-cta"
          className="w-full"
          disabled={empty || props.payDisabled}
          onClick={props.onPay}
          data-testid="pay-button"
        >
          <Icon as={ScanBarcode} size="xl" />
          {t("sale.payButton")}
          <Kbd keys="F4" inverted />
        </Button>
      </div>
    </section>
  );
}
