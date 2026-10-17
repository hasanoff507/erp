/**
 * Kirim draft sheet (19 §8; 07 BO-04 «Kirimlar», POS-08 fields): manba — qo'lda (yetkazib beruvchi)
 * yoki xaridnoma (yetkazib beruvchi, narx va qolgan miqdor undan; farq bo'lsa nomuvofiqlik sababi
 * majburiy); sana, turi (xarid / tekin), darhol to'langan; qatorlar — miqdor, tannarx QQSsiz (4 xona),
 * QQS stavkasi, yaroqlilik muddati, markirovka kodlari (markirovkali tovar: soni = miqdor). Saved as a
 * draft (`purchases.receive`); posting is a separate action (`purchases.post`).
 */
import { useUnit } from "effector-react";
import { Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  DecimalInput,
  FormField,
  Icon,
  Input,
  Label,
  PriceInput,
  SegmentedControl,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SimpleSelect,
  Skeleton,
  Switch,
  Textarea,
  toast,
} from "@shared/ui";

import { ProductPicker, type PickedProduct } from "#/entities/product/index.tsx";
import { productCached, unitLabel, useQtyFormat, type Warehouse } from "#/entities/refs/index.ts";
import { SupplierPicker, type PickedSupplier } from "#/entities/supplier/index.tsx";
import { todayIso } from "#/shared/lib/effect.ts";
import { errorText } from "#/shared/lib/errors.ts";

import {
  $form,
  $formError,
  $openOrders,
  $pendingPoId,
  DISCREPANCY_REASONS,
  VAT_RATES,
  formClosed,
  formOpened,
  formTotals,
  lineIssue,
  linesFromOrder,
  linesFromReceipt,
  needsReason,
  newLine,
  receiptProductSearch,
  receiptSupplierSearch,
  saveReceiptFx,
  type Discrepancy,
  type ReceiptFormSource,
  type ReceiptLineDraft,
} from "../model/index.ts";

const MANUAL = "manual";

export function ReceiptSheet({ warehouse, online }: { warehouse: Warehouse | null; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const [form, formError, close, pendingPoId] = useUnit([$form, $formError, formClosed, $pendingPoId]);
  // Waiting for a purchase order keeps the sheet open (skeleton); closing drops the late answer (WEB-18).
  const open = form !== null || pendingPoId !== null || formError !== null;
  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) close();
      }}
    >
      <SheetContent wide>
        <SheetHeader>
          <SheetTitle>
            {form?.mode === "edit" ? t("receipts.editTitle") : t("receipts.createTitle")}
          </SheetTitle>
          <SheetDescription>{t("receipts.formDescription")}</SheetDescription>
        </SheetHeader>
        {formError ? (
          <SheetBody>
            <Banner tone="destructive" icon={TriangleAlert}>
              {errorText(formError)}
            </Banner>
          </SheetBody>
        ) : form && warehouse ? (
          <ReceiptForm
            key={form.mode === "po" ? form.order.id : form.mode === "edit" ? form.receipt.id : "new"}
            source={form}
            warehouse={warehouse}
            online={online}
          />
        ) : (
          <SheetBody aria-busy="true">
            <Skeleton className="h-40 w-full" />
          </SheetBody>
        )}
      </SheetContent>
    </Sheet>
  );
}

function ReceiptForm({
  source,
  warehouse,
  online,
}: {
  source: ReceiptFormSource;
  warehouse: Warehouse;
  online: boolean;
}) {
  const { t } = useTranslation("warehouse");
  const formatQty = useQtyFormat();
  const [save, pending, cache, openOrders, open, close] = useUnit([
    saveReceiptFx,
    saveReceiptFx.pending,
    productCached,
    $openOrders,
    formOpened,
    formClosed,
  ]);
  const order = source.mode === "po" ? source.order : null;
  const receipt = source.mode === "edit" ? source.receipt : null;
  const linkedPo = order?.id ?? receipt?.po_id ?? null;

  const [supplier, setSupplier] = useState<PickedSupplier | null>(() => {
    const ref = order?.supplier ?? receipt?.supplier;
    return ref?.name ? { id: ref.id, name: ref.name, stir: ref.stir } : null;
  });
  const [docDate, setDocDate] = useState(receipt?.doc_date ?? todayIso());
  const [kind, setKind] = useState<"purchase" | "gratuitous">(receipt?.kind ?? "purchase");
  const [paid, setPaid] = useState(receipt?.paid_immediately ?? false);
  const [comment, setComment] = useState(receipt?.comment ?? "");
  const [lines, setLines] = useState<ReceiptLineDraft[]>(() => {
    if (receipt) return linesFromReceipt(receipt);
    if (source.mode === "po") return linesFromOrder(source.order, source.products);
    return [];
  });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const issues = lines.map(lineIssue);
  const valid = supplier !== null && docDate !== "" && lines.length > 0 && issues.every((i) => i === null);
  const totals = formTotals(lines);
  const update = (key: string, patch: Partial<ReceiptLineDraft>) =>
    setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const add = (p: PickedProduct) => {
    cache(p);
    setLines((prev) => [...prev, newLine(p)]);
  };

  const submit = () => {
    setSubmitted(true);
    if (!valid || !supplier) return;
    setError(null);
    save({
      id: receipt?.id ?? null,
      values: {
        supplierId: supplier.id,
        warehouseId: warehouse.id,
        poId: linkedPo,
        docDate,
        paidImmediately: paid,
        kind,
        comment,
        lines,
      },
    })
      .then(() => {
        toast.success(t("receipts.toast.saved"));
        close();
      })
      .catch((e: unknown) => setError(errorText(e)));
  };

  const issueText = (l: ReceiptLineDraft, issue: string | null) => {
    if (!submitted || issue === null) return null;
    if (issue === "qty") return t("validation.positiveQty");
    if (issue === "cost") return t("receipts.errors.cost");
    if (issue === "reason") return t("receipts.errors.reason");
    return t("receipts.errors.codes", { count: codesCount(l) });
  };

  return (
    <>
      <SheetBody>
        {receipt === null ? (
          <FormField label={t("receipts.fields.source")}>
            <SimpleSelect
              options={[
                { value: MANUAL, label: t("receipts.manual") },
                ...openOrders.map((o) => ({
                  value: o.id,
                  label: `${o.number ?? "—"} · ${o.supplier.name ?? ""} · ${formatDate(o.doc_date)}`,
                })),
                ...(order && !openOrders.some((o) => o.id === order.id)
                  ? [{ value: order.id, label: `${order.number ?? "—"} · ${order.supplier.name ?? ""}` }]
                  : []),
              ]}
              value={order?.id ?? MANUAL}
              onValueChange={(v) => {
                open(v === MANUAL ? { mode: "new" } : { mode: "po", poId: v });
              }}
            />
          </FormField>
        ) : null}
        <FormField
          label={t("receipts.fields.supplier")}
          required
          error={submitted && !supplier ? "validation.required" : null}
        >
          {(a11y) => (
            <SupplierPicker
              {...a11y}
              model={receiptSupplierSearch}
              value={supplier}
              onPick={(s) => setSupplier({ id: s.id, name: s.name, stir: s.stir })}
              disabled={!online || linkedPo !== null}
            />
          )}
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label={t("receipts.fields.docDate")} required>
            <Input type="date" value={docDate} onChange={(e) => setDocDate(e.target.value)} />
          </FormField>
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-foreground-secondary">{t("receipts.fields.kind")}</span>
            <SegmentedControl
              label={t("receipts.fields.kind")}
              options={[
                { value: "purchase", label: t("receipts.kind.purchase") },
                { value: "gratuitous", label: t("receipts.kind.gratuitous") },
              ]}
              value={kind}
              onChange={setKind}
            />
          </div>
        </div>
        {kind === "purchase" ? (
          <span className="flex items-center gap-2">
            <Switch id="receipt-paid" checked={paid} onCheckedChange={setPaid} />
            <Label htmlFor="receipt-paid">{t("receipts.fields.paidImmediately")}</Label>
          </span>
        ) : null}
        <section className="flex flex-col gap-2" aria-label={t("receipts.linesLabel")}>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[14px] font-bold">{t("receipts.linesLabel")}</h3>
            <ProductPicker model={receiptProductSearch} onPick={add} disabled={!online} />
          </div>
          {submitted && lines.length === 0 ? (
            <p role="alert" className="text-small font-semibold text-destructive">
              {t("receipts.noLines")}
            </p>
          ) : null}
          {lines.map((l, i) => (
            <div key={l.key} className="flex flex-col gap-3 rounded-lg border border-border px-3 py-3">
              <div className="flex items-center gap-2">
                <p className="min-w-0 flex-1 truncate text-[13px] font-bold">
                  {l.name}
                  {l.expected !== null ? (
                    <span className="font-normal text-muted-foreground">
                      {" "}
                      ·{" "}
                      {t("receipts.expected", {
                        qty: `${formatQty(l.expected, l.unitCode)} ${unitLabel(l.unitCode)}`,
                      })}
                    </span>
                  ) : null}
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={t("actions.removeLine", { name: l.name })}
                  onClick={() => setLines((prev) => prev.filter((x) => x.key !== l.key))}
                >
                  <Icon as={Trash2} size="sm" />
                </Button>
              </div>
              <div className="grid gap-3 sm:grid-cols-4">
                <FormField label={t("receipts.fields.qty")} required>
                  <DecimalInput
                    aria-label={t("receipts.qtyFor", { name: l.name })}
                    precision={3}
                    outputScale={3}
                    suffix={unitLabel(l.unitCode)}
                    value={l.qty}
                    onChange={(v) => update(l.key, { qty: v })}
                  />
                </FormField>
                <FormField label={t("receipts.fields.cost")} required>
                  <PriceInput
                    aria-label={t("receipts.costFor", { name: l.name })}
                    value={l.cost}
                    onChange={(v) => update(l.key, { cost: v })}
                  />
                </FormField>
                <FormField label={t("receipts.fields.vatRate")}>
                  <SimpleSelect
                    options={VAT_RATES.map((r) => ({
                      value: r,
                      label: t(`receipts.vat.${r === "12.00" ? "12" : "0"}`),
                    }))}
                    value={l.vatRate}
                    onValueChange={(v) => update(l.key, { vatRate: v })}
                  />
                </FormField>
                <FormField label={t("receipts.fields.expiry")} optional>
                  <Input
                    type="date"
                    value={l.expiry}
                    onChange={(e) => update(l.key, { expiry: e.target.value })}
                  />
                </FormField>
              </div>
              {needsReason(l) || l.reason !== "" ? (
                <FormField label={t("receipts.fields.reason")} required={needsReason(l)} className="sm:w-72">
                  <SimpleSelect
                    aria-label={t("receipts.reasonFor", { name: l.name })}
                    options={DISCREPANCY_REASONS.map((r) => ({
                      value: r,
                      label: t(`receipts.reasons.${r}`),
                    }))}
                    value={l.reason || undefined}
                    onValueChange={(v) => update(l.key, { reason: v as Discrepancy })}
                  />
                </FormField>
              ) : null}
              {l.isMarked ? (
                <FormField
                  label={t("receipts.fields.codes")}
                  required
                  hint={t("receipts.codesHint", { count: codesCount(l) })}
                >
                  <Textarea
                    rows={3}
                    className="font-mono text-[12px]"
                    value={l.codes}
                    onChange={(e) => update(l.key, { codes: e.target.value })}
                  />
                </FormField>
              ) : null}
              {issueText(l, issues[i] ?? null) ? (
                <p role="alert" className="text-small font-semibold text-destructive">
                  {issueText(l, issues[i] ?? null)}
                </p>
              ) : null}
            </div>
          ))}
        </section>
        {lines.length > 0 ? (
          <dl
            className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 self-end text-[13px]"
            aria-label={t("receipts.totalsLabel")}
          >
            <dt className="text-muted-foreground">{t("receipts.net")}</dt>
            <dd className="text-right tabular-nums">{formatMoney(totals.net, { precision: 2 })}</dd>
            <dt className="text-muted-foreground">{t("receipts.vatTotal")}</dt>
            <dd className="text-right tabular-nums">{formatMoney(totals.vat, { precision: 2 })}</dd>
            <dt className="font-bold">{t("receipts.total")}</dt>
            <dd className="text-right font-extrabold tabular-nums">
              {formatMoney(totals.total, { precision: 2 })}
            </dd>
          </dl>
        ) : null}
        <FormField label={t("receipts.fields.comment")} optional>
          <Textarea value={comment} rows={2} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
        </FormField>
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
      </SheetBody>
      <SheetFooter>
        <Button variant="secondary" disabled={pending} onClick={() => close()}>
          {t("actions.back")}
        </Button>
        <Button disabled={pending || !online} aria-busy={pending || undefined} onClick={submit}>
          {t("receipts.saveDraft")}
        </Button>
      </SheetFooter>
    </>
  );
}

function codesCount(l: ReceiptLineDraft): number {
  return l.codes.split("\n").filter((c) => c.trim() !== "").length;
}
