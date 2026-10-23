import { useTranslation } from "@shared/i18n";
import { DataTable, type DataTableColumn } from "@shared/ui";

import { fieldMessageText } from "#/shared/lib/messages.ts";

import { isFileLevelError } from "../model/lib/index.ts";
import type { ImportErrorItem } from "../model/types/index.ts";

export interface ErrorRowsTableProps {
  rows: readonly ImportErrorItem[];
  total: number;
  hasMore: boolean;
  loading: boolean;
  onLoadMore: () => void;
}

/** `GET /import-jobs/{id}/errors` — row, column, message (19 §6): the user fixes the file and re-uploads. */
export function ErrorRowsTable({ rows, total, hasMore, loading, onLoadMore }: ErrorRowsTableProps) {
  const { t } = useTranslation("catalog");

  const columns: DataTableColumn<ImportErrorItem>[] = [
    {
      id: "row",
      header: t("import.errors.row"),
      width: "90px",
      numeric: true,
      cell: (item) => (isFileLevelError(item) ? t("import.errors.fileRow") : item.row),
    },
    {
      id: "field",
      header: t("import.errors.column"),
      width: "160px",
      cell: (item) => <code className="text-small font-semibold">{item.field}</code>,
    },
    { id: "message", header: t("import.errors.message"), cell: (item) => fieldMessageText(item.message) },
  ];

  return (
    <section className="flex flex-col gap-2" aria-labelledby="import-error-rows-title">
      <h3 id="import-error-rows-title" className="text-h2">
        {t("import.errors.title", { count: total })}
      </h3>
      <DataTable
        label={t("import.errors.tableLabel")}
        columns={columns}
        data={rows}
        getRowId={(item) => `${item.row}-${item.field}-${item.code}`}
        status={loading && rows.length === 0 ? "loading" : "idle"}
        minWidth={520}
        skeletonRows={3}
        pagination={{ kind: "cursor", hasMore, loadingMore: loading, onLoadMore }}
      />
    </section>
  );
}
