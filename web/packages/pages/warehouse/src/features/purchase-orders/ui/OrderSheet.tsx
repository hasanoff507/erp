/**
 * «Yangi xaridnoma» / «Xaridnomani tahrirlash» (07 BO-04 fields): yetkazib beruvchi (Combobox), sana,
 * qatorlar (tovar, miqdor > 0, kutilgan narx — ixtiyoriy, 4 xona), izoh; «Qoralama saqlash» /
 * «Saqlash va yuborish» (`POST` → `/send`, raqam Z-… shu yerda beriladi).
 */
import { useUnit } from "effector-react";
import { Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  DecimalInput,
  FormField,
  Icon,
  Input,
  PriceInput,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  Textarea,
  toast,
} from "@shared/ui";

import { ProductPicker, type PickedProduct } from "#/entities/product/index.tsx";
import { productCached, unitLabel, type Warehouse } from "#/entities/refs/index.ts";
import { SupplierPicker, type PickedSupplier } from "#/entities/supplier/index.tsx";
import { todayIso } from "#/shared/lib/effect.ts";
import { errorText } from "#/shared/lib/errors.ts";

import {
  draftLinesOf,
  formTotal,
  lineError,
  orderProductSearch,
  orderSupplierSearch,
  saveOrderFx,
  toOrderBody,
  type Order,
  type OrderLineDraft,
} from "../model/index.ts";

export interface OrderSheetProps {
  open: boolean;
  onClose: () => void;
  /** Edited order, `null` = new. */
  order: Order | null;
  warehouse: Warehouse | null;
  online: boolean;
}

export function OrderSheet({ open, onClose, order, warehouse, online }: OrderSheetProps) {
  const { t } = useTranslation("warehouse");
  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent wide>
        <SheetHeader>
          <SheetTitle>
            {order ? t("orders.editTitle", { number: order.number ?? "" }) : t("orders.createTitle")}
          </SheetTitle>
          <SheetDescription>{t("orders.formDescription")}</SheetDescription>
        </SheetHeader>
        {open && warehouse ? (
          <OrderForm
            key={order?.id ?? "new"}
            order={order}
            warehouse={warehouse}
            online={online}
            onClose={onClose}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function OrderForm({
  order,
  warehouse,
  online,
  onClose,
}: {
  order: Order | null;
  warehouse: Warehouse;
  online: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation("warehouse");
  const [save, pending, cache] = useUnit([saveOrderFx, saveOrderFx.pending, productCached]);
  const [supplier, setSupplier] = useState<PickedSupplier | null>(
    order
      ? order.supplier.name
        ? { id: order.supplier_id, name: order.supplier.name, stir: order.supplier.stir }
        : null
      : null,
  );
  const [docDate, setDocDate] = useState(order?.doc_date ?? todayIso());
  const [lines, setLines] = useState<OrderLineDraft[]>(() => (order ? draftLinesOf(order) : []));
  const [comment, setComment] = useState(order?.comment ?? "");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = lines.map(lineError);
  const valid = supplier !== null && docDate !== "" && lines.length > 0 && errors.every((e) => e === null);
  const update = (key: string, patch: Partial<OrderLineDraft>) =>
    setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const add = (p: PickedProduct) => {
    cache(p);
    if (lines.some((l) => l.productId === p.id)) return;
    setLines((prev) => [
      ...prev,
      { key: p.id, productId: p.id, name: p.name, unitCode: p.unit_code, qty: "", price: "" },
    ]);
  };

  const submit = (send: boolean) => {
    setSubmitted(true);
    if (!valid || !supplier) return;
    setError(null);
    save({
      id: order?.id ?? null,
      send,
      body: toOrderBody({ supplierId: supplier.id, warehouseId: warehouse.id, docDate, lines, comment }),
    })
      .then(({ order: saved, sendError }) => {
        // A refused send: the draft is kept and selected, its detail shows the error (no «sent» toast).
        toast.success(
          sendError || saved.status === "draft"
            ? t("orders.toast.saved")
            : t("orders.toast.sent", { number: saved.number ?? "" }),
        );
        onClose();
      })
      .catch((e: unknown) => setError(errorText(e)));
  };

  return (
    <>
      <SheetBody>
        <FormField
          label={t("orders.fields.supplier")}
          required
          error={submitted && !supplier ? "validation.required" : null}
        >
          {(a11y) => (
            <SupplierPicker
              {...a11y}
              model={orderSupplierSearch}
              value={supplier}
              onPick={(s) => setSupplier({ id: s.id, name: s.name, stir: s.stir })}
              disabled={!online}
            />
          )}
        </FormField>
        <FormField label={t("orders.fields.docDate")} required className="w-48">
          <Input type="date" value={docDate} onChange={(e) => setDocDate(e.target.value)} />
        </FormField>
        <section className="flex flex-col gap-2" aria-label={t("orders.linesLabel")}>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[14px] font-bold">{t("orders.linesLabel")}</h3>
            <ProductPicker model={orderProductSearch} onPick={add} disabled={!online} />
          </div>
          {submitted && lines.length === 0 ? (
            <p role="alert" className="text-small font-semibold text-destructive">
              {t("orders.noLines")}
            </p>
          ) : null}
          {lines.map((l, i) => (
            <div
              key={l.key}
              className="flex flex-wrap items-start gap-3 rounded-lg border border-border px-3 py-2"
            >
              <p className="min-w-40 flex-1 pt-3 text-[13px] font-semibold">{l.name}</p>
              <FormField
                label={t("orders.fields.qty")}
                className="w-36"
                error={submitted && errors[i] === "qty" ? t("validation.positiveQty") : null}
              >
                <DecimalInput
                  precision={3}
                  outputScale={3}
                  suffix={unitLabel(l.unitCode)}
                  value={l.qty}
                  onChange={(v) => update(l.key, { qty: v })}
                />
              </FormField>
              <FormField label={t("orders.fields.price")} className="w-44" optional>
                <PriceInput value={l.price} onChange={(v) => update(l.key, { price: v })} />
              </FormField>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="mt-7"
                aria-label={t("actions.removeLine", { name: l.name })}
                onClick={() => setLines((prev) => prev.filter((x) => x.key !== l.key))}
              >
                <Icon as={Trash2} size="sm" />
              </Button>
            </div>
          ))}
          {lines.length > 0 ? (
            <p className="self-end text-[14px] font-bold">
              {t("orders.total")}: <span className="tabular-nums">{formatMoney(formTotal(lines))}</span>
            </p>
          ) : null}
        </section>
        <FormField label={t("orders.fields.comment")} optional>
          <Textarea value={comment} rows={2} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
        </FormField>
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
      </SheetBody>
      <SheetFooter>
        <Button variant="secondary" disabled={pending || !online} onClick={() => submit(false)}>
          {t("orders.saveDraft")}
        </Button>
        {!order || order.status === "draft" ? (
          <Button disabled={pending || !online} aria-busy={pending || undefined} onClick={() => submit(true)}>
            {t("orders.saveAndSend")}
          </Button>
        ) : null}
      </SheetFooter>
    </>
  );
}
