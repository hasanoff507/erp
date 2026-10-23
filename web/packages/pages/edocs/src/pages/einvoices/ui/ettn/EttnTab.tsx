/**
 * «E-TTN» tab — incoming e-TTN (07 BO-15 «Kiruvchi e-TTN», 19 §20): `GET /ettn-documents?direction=in`;
 * «Tasdiqlash» / «Rad etish» are signed with E-IMZO (`sign-challenge?action=` → `accept` | `reject`;
 * `purchases.receive` + `einvoice.sign`). An e-TTN combined with its e-invoice is answered with the e-invoice.
 */
import { useUnit } from "effector-react";
import { Check, X } from "lucide-react";
import { useState } from "react";

import { formatDate } from "@shared/lib/format";
import { useCan } from "@shared/state/permissions";
import { DataTable, type DataTableColumn, type DataTableRowAction } from "@shared/ui";

import { errorText } from "#/shared/lib/effect.ts";
import { useTx } from "#/shared/lib/i18n.ts";

import {
  $busy,
  $ettnError,
  $ettnStatus,
  $ettns,
  $hasMore,
  $key,
  ettnRespondRequested,
  moreRequested,
  reloadRequested,
  type Ettn,
} from "../../model/index.ts";
import { ReasonDialog } from "../dialogs/ReasonDialog.tsx";
import { DocStatusChip } from "../shared/chips.tsx";

export function EttnTab() {
  const { t } = useTx();
  const canAnswer = useCan({ permission: ["purchases.receive", "einvoice.sign"] });
  const [rows, status, error, hasMore, key, busy] = useUnit([
    $ettns,
    $ettnStatus,
    $ettnError,
    $hasMore,
    $key,
    $busy,
  ]);
  const [respond, more, reload] = useUnit([ettnRespondRequested, moreRequested, reloadRequested]);
  const [rejecting, setRejecting] = useState<string | null>(null);

  const columns: DataTableColumn<Ettn>[] = [
    {
      id: "doc",
      header: t("columns.ettn"),
      cell: (x) => <span className="font-bold">{x.operator_doc_id ?? "—"}</span>,
    },
    {
      id: "date",
      header: t("columns.date"),
      width: "120px",
      cell: (x) => (x.doc_date ? formatDate(x.doc_date) : "—"),
    },
    {
      id: "combined",
      header: t("columns.combined"),
      width: "200px",
      cell: (x) => (x.einvoice_id ? t("ettn.combined") : t("ettn.separate")),
    },
    {
      id: "status",
      header: t("columns.status"),
      width: "150px",
      cell: (x) => <DocStatusChip status={x.status} scope="ettn" />,
    },
  ];
  const actions = (x: Ettn): DataTableRowAction<Ettn>[] =>
    canAnswer && x.status === "received" && x.einvoice_id === null
      ? [
          {
            id: "accept",
            label: t("actions.ettnAccept"),
            icon: Check,
            disabled: busy || key === null,
            onSelect: () => respond({ id: x.id, action: "accept", reason: null }),
          },
          {
            id: "reject",
            label: t("actions.ettnReject"),
            icon: X,
            destructive: true,
            disabled: busy || key === null,
            onSelect: () => setRejecting(x.id),
          },
        ]
      : [];

  return (
    <>
      <DataTable
        label={t("tabs.ettn")}
        columns={columns}
        data={rows}
        getRowId={(x) => x.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={() => reload("ettn")}
        rowActions={actions}
        pagination={{ kind: "cursor", hasMore: hasMore.ettn, onLoadMore: () => more("ettn") }}
      />
      <ReasonDialog
        open={rejecting !== null}
        onOpenChange={(open) => (open ? undefined : setRejecting(null))}
        title={t("actions.ettnReject")}
        confirmLabel={t("actions.ettnReject")}
        pending={busy}
        onSubmit={(reason) => (rejecting ? respond({ id: rejecting, action: "reject", reason }) : undefined)}
      />
    </>
  );
}
