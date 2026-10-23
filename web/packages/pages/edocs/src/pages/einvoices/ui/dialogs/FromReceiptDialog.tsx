/**
 * «Chek asosida e-faktura» (07 BO-15, BP-13, US-M01-06; `POST /einvoices/from-receipt`): find the original
 * receipt by its number, choose the company buyer — a new outgoing e-invoice linked to the receipt; VAT is NOT
 * recalculated (13 §2.22). Errors: `EINVOICE_ALREADY_LINKED`, `EINVOICE_AMOUNT_EXCEEDS_RECEIPT`,
 * `EINVOICE_COUNTERPARTY_INCOMPLETE` (→ BO-06 customer card).
 */
import { useUnit } from "effector-react";
import { Info, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { formatDate, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FormField,
  Input,
  cn,
  Icon,
} from "@shared/ui";

import { errorText } from "#/shared/lib/effect.ts";
import { useTx } from "#/shared/lib/i18n.ts";

import {
  $actionError,
  $busy,
  $dialog,
  $sales,
  dialogOpened,
  fromReceiptSubmitted,
  salesSearched,
  searchSalesFx,
} from "../../model/index.ts";
import { CompanyPicker } from "./CompanyPicker.tsx";

export function FromReceiptDialog() {
  const { t } = useTx();
  const [sales, searching, busy, error] = useUnit([$sales, searchSalesFx.pending, $busy, $actionError]);
  const [search, submit, dialog, openDialog] = useUnit([
    salesSearched,
    fromReceiptSubmitted,
    $dialog,
    dialogOpened,
  ]);
  const open = dialog === "fromReceipt";
  const onOpenChange = (next: boolean) => openDialog(next ? "fromReceipt" : null);
  const [query, setQuery] = useState("");
  const [saleId, setSaleId] = useState<string | null>(null);
  const [companyId, setCompanyId] = useState<string | null>(null);
  const incomplete = error?.code === "EINVOICE_COUNTERPARTY_INCOMPLETE";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("dialogs.fromReceipt")}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex items-end gap-2">
            <FormField label={t("dialogs.receiptSearch")} className="flex-1">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => (e.key === "Enter" ? search(query) : undefined)}
                placeholder={t("dialogs.receiptPlaceholder")}
              />
            </FormField>
            <Button
              variant="secondary"
              disabled={searching}
              onClick={() => search(query)}
              aria-label={t("dialogs.searchReceipt")}
            >
              <Icon as={Search} size="sm" />
            </Button>
          </div>
          <ul className="flex flex-col gap-1" aria-label={t("dialogs.receipts")}>
            {sales.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  aria-pressed={saleId === s.id}
                  onClick={() => setSaleId(s.id)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-[13px]",
                    saleId === s.id ? "border-primary bg-primary-soft" : "border-border hover:bg-accent",
                  )}
                >
                  <span className="font-semibold">{s.number ?? s.temp_number ?? "—"}</span>
                  <span className="text-foreground-secondary">
                    {formatDate(s.doc_date)} · {formatMoney(s.total_amount, { precision: 2 })}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <CompanyPicker value={companyId} onChange={setCompanyId} />
          <Banner tone="info" icon={Info}>
            {t("noSecondVat")}
          </Banner>
          {error ? (
            <Banner tone="destructive" icon={Info}>
              {errorText(error)}
              {incomplete && companyId ? (
                <>
                  {" "}
                  <Link className="underline" to="/app/debts">
                    {t("dialogs.openCustomer")}
                  </Link>
                </>
              ) : null}
            </Banner>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {t("dialogs.close")}
          </Button>
          <Button
            disabled={busy || saleId === null || companyId === null}
            data-testid="from-receipt-submit"
            onClick={() => (saleId && companyId ? submit({ saleId, counterpartyId: companyId }) : undefined)}
          >
            {t("dialogs.create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
