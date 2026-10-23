/**
 * «Riskli kiruvchi e-fakturalar» (07 BO-07; 20 #1 `pending_credit_invoices[]`; US-M10-03, QT-M10-04): inbound
 * e-invoices with a red / unknown risk flag whose VAT credit is not (fully) confirmed — e-faktura, yetkazib
 * beruvchi, sana, summa, QQS, hisobga olingan (to'lov bilan ochilgan) va kutilayotgan QQS, risk chipi; the credit
 * opens only after payment (13 §2.8, §2.16). «E-faktura markazi» → BO-15.
 */
import { useUnit } from "effector-react";
import { ExternalLink, FileWarning } from "lucide-react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { DataTable, EmptyState, Icon, StatusChip, type DataTableColumn } from "@shared/ui";

import { $summary, type PendingCreditInvoice } from "../../model/index.ts";

const money2 = (v: string) => formatMoney(v, { precision: 2, withCurrency: false });

export function RedInvoices() {
  const { t } = useTranslation("finance");
  const summary = useUnit($summary);
  if (!summary || summary.pendingCreditTotal === null) return null;

  const columns: DataTableColumn<PendingCreditInvoice>[] = [
    {
      id: "invoice",
      header: t("vat.red.columns.invoice"),
      cell: (i) => (
        <span className="flex flex-col">
          <span className="font-semibold">{i.number ?? t("vat.red.noNumber")}</span>
          <span className="text-[12px] text-muted-foreground">{i.counterparty_name}</span>
        </span>
      ),
    },
    {
      id: "date",
      header: t("vat.red.columns.date"),
      width: "110px",
      cell: (i) => <span className="tabular-nums">{i.doc_date ? formatDate(i.doc_date) : "—"}</span>,
    },
    {
      id: "risk",
      header: t("vat.red.columns.risk"),
      width: "140px",
      cell: (i) => (
        <span className="flex flex-col items-start gap-1">
          <StatusChip tone={i.risk_flag === "red" ? "destructive" : "warning"} dot>
            {t(`vat.red.risk.${i.risk_flag}`)}
          </StatusChip>
          <span className="text-[11px] text-muted-foreground">{t(`vat.red.credit.${i.credit_status}`)}</span>
        </span>
      ),
    },
    { id: "total", header: t("vat.red.columns.total"), numeric: true, width: "140px", cell: (i) => money2(i.total_amount) },
    { id: "vat", header: t("vat.red.columns.vat"), numeric: true, width: "130px", cell: (i) => money2(i.vat_amount) },
    {
      id: "credited",
      header: t("vat.red.columns.credited"),
      numeric: true,
      width: "130px",
      cell: (i) => money2(i.credited_vat),
    },
    {
      id: "pending",
      header: t("vat.red.columns.pending"),
      numeric: true,
      width: "130px",
      cell: (i) => <span data-testid="red-pending">{money2(i.pending_vat)}</span>,
    },
  ];

  return (
    <section aria-labelledby="red-invoices-title" className="flex flex-col gap-2.5" data-testid="red-invoices">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="red-invoices-title" className="text-h2">
          {t("vat.red.title")}
        </h2>
        <span className="grow" />
        <Link to="/app/einvoices" className="inline-flex items-center gap-1 text-[13px] font-semibold underline">
          {t("vat.red.center")}
          <Icon as={ExternalLink} size="sm" />
        </Link>
      </div>
      <p className="text-small text-foreground-secondary">{t("vat.red.hint")}</p>
      <DataTable
        label={t("vat.red.title")}
        columns={columns}
        data={summary.pendingCreditInvoices}
        getRowId={(i) => i.einvoice_id}
        minWidth={900}
        empty={<EmptyState icon={FileWarning} title={t("vat.red.empty")} />}
      />
    </section>
  );
}
