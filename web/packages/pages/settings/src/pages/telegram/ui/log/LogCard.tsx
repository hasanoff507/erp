/** Notifications log (20 #71, `notifications.manage`): what was sent to Telegram, when, to which chat, status. */
import { useUnit } from "effector-react";
import { Inbox } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/format";
import { Card, CardTitle, DataTable, EmptyState, StatusChip, type DataTableColumn } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  $log,
  $logCursor,
  $logError,
  $logStatus,
  logMoreRequested,
  logReloadRequested,
  type LogItem,
} from "../../model/index.ts";
import { useKindText } from "../kind-text.ts";

export function LogCard() {
  const { t } = useTranslation("settings");
  const kindText = useKindText();
  const [rows, cursor, status, error, more, reload] = useUnit([
    $log,
    $logCursor,
    $logStatus,
    $logError,
    logMoreRequested,
    logReloadRequested,
  ]);
  const columns: DataTableColumn<LogItem>[] = [
    {
      id: "at",
      header: t("telegram.log.columns.at"),
      width: "170px",
      cell: (r) => <span className="tabular-nums">{formatDateTime(r.created_at)}</span>,
    },
    {
      id: "template",
      header: t("telegram.log.columns.template"),
      cell: (r) => <span className="font-semibold">{kindText(r.template).title}</span>,
    },
    {
      id: "recipient",
      header: t("telegram.log.columns.recipient"),
      width: "160px",
      cell: (r) => <span className="tabular-nums text-foreground-secondary">{r.recipient}</span>,
    },
    {
      id: "status",
      header: t("telegram.log.columns.status"),
      width: "130px",
      cell: (r) =>
        r.status === "sent" ? (
          <StatusChip tone="success">{t("telegram.log.status.sent")}</StatusChip>
        ) : (
          <StatusChip tone="destructive">{t("telegram.log.status.failed")}</StatusChip>
        ),
    },
  ];
  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{t("telegram.log.title")}</CardTitle>
      <DataTable
        label={t("telegram.log.title")}
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        minWidth={640}
        skeletonRows={3}
        empty={<EmptyState icon={Inbox} title={t("telegram.log.empty")} />}
        pagination={{ kind: "cursor", hasMore: cursor !== null, onLoadMore: more }}
      />
    </Card>
  );
}
