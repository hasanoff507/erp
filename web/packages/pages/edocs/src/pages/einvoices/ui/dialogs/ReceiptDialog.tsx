/**
 * «Kirim yaratish» (07 BO-04 table «E-fakturadan kirim»: BO-15 → `POST /goods-receipts/from-einvoice/{id}`,
 * `purchases.receive`; 19 §8, ACC-07). The warehouse is chosen; e-invoice lines the server cannot match to a
 * product (`validation.einvoice_line_unmatched` on `lines[i].product_id`) are mapped here by a product search.
 * The invoice line amounts stay authoritative (net / VAT). On success → BO-04 «Kirimlar» with the new draft.
 */
import { useUnit } from "effector-react";
import { Info, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ApiError } from "@shared/api";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FormField,
  Icon,
  Input,
  SimpleSelect,
  cn,
} from "@shared/ui";

import { errorText } from "#/shared/lib/effect.ts";
import { useTx } from "#/shared/lib/i18n.ts";

import {
  $warehouses,
  payloadLines,
  receiptFromEinvoiceFx,
  searchProductsFx,
  type EInvoiceDetail,
  type Product,
} from "../../model/index.ts";

const UNMATCHED = /^lines\[(\d+)\]\.product_id$/;

/** Digits → integer without Number()/parseInt (qaror #57 lint). */
function digits(text: string): number {
  let n = 0;
  for (const c of text) n = n * 10 + (c.charCodeAt(0) - 48);
  return n;
}

/** Indexes of the e-invoice lines the server could not match. */
export function unmatchedLines(error: ApiError | null): number[] {
  if (!error) return [];
  return error.details.flatMap((d) => {
    const m = UNMATCHED.exec(d.field);
    return m ? [digits(m[1] ?? "0")] : [];
  });
}

function LineMatcher({
  name,
  value,
  onChange,
}: {
  name: string;
  value: string | null;
  onChange: (id: string) => void;
}) {
  const { t } = useTx();
  const search = useUnit(searchProductsFx);
  const [query, setQuery] = useState(name);
  const [items, setItems] = useState<Product[]>([]);
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-border p-2.5">
      <span className="text-[13px] font-semibold">{name}</span>
      <div className="flex gap-2">
        <Input
          aria-label={t("receipt.productSearch", { name })}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Button
          variant="secondary"
          aria-label={t("receipt.findProduct")}
          onClick={() => void search(query).then(setItems, () => setItems([]))}
        >
          <Icon as={Search} size="sm" />
        </Button>
      </div>
      <ul className="flex flex-col gap-1">
        {items.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              aria-pressed={value === p.id}
              onClick={() => onChange(p.id)}
              className={cn(
                "w-full rounded-md border px-2.5 py-1.5 text-left text-[13px]",
                value === p.id ? "border-primary bg-primary-soft" : "border-border hover:bg-accent",
              )}
            >
              {p.name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ReceiptDialog({
  detail,
  open,
  onOpenChange,
}: {
  detail: EInvoiceDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTx();
  const navigate = useNavigate();
  const [warehouses, create, pending] = useUnit([
    $warehouses,
    receiptFromEinvoiceFx,
    receiptFromEinvoiceFx.pending,
  ]);
  const [chosen, setWarehouseId] = useState<string | null>(null);
  const warehouseId = chosen ?? warehouses[0]?.id ?? null;
  const [mapping, setMapping] = useState<Record<number, string>>({});
  const [error, setError] = useState<ApiError | null>(null);
  const lines = payloadLines(detail.payload);
  const unmatched = unmatchedLines(error);

  const submit = () => {
    if (!warehouseId) return;
    const mapped = unmatched.flatMap((index) => {
      const product_id = mapping[index];
      return product_id ? [{ line_no: lines[index]?.line_no ?? index + 1, product_id }] : [];
    });
    void create({ einvoiceId: detail.id, warehouseId, lines: mapped }).then(
      (receipt) => {
        onOpenChange(false);
        void navigate(`/app/purchases?tab=receipts&receipt=${receipt.id}`);
      },
      (e: ApiError) => setError(e),
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("receipt.title")}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <FormField label={t("receipt.warehouse")}>
            <SimpleSelect
              options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
              value={warehouseId ?? ""}
              onValueChange={setWarehouseId}
            />
          </FormField>
          <Banner tone="info" icon={Info}>
            {t("receipt.amountsKept")}
          </Banner>
          {unmatched.map((index) => (
            <LineMatcher
              key={index}
              name={lines[index]?.name ?? String(index + 1)}
              value={mapping[index] ?? null}
              onChange={(id) => setMapping((m) => ({ ...m, [index]: id }))}
            />
          ))}
          {error && unmatched.length === 0 ? (
            <Banner tone="destructive" icon={Info}>
              {errorText(error)}
            </Banner>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {t("dialogs.close")}
          </Button>
          <Button
            disabled={pending || !warehouseId || unmatched.some((i) => !mapping[i])}
            data-testid="receipt-submit"
            onClick={submit}
          >
            {t("receipt.create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
