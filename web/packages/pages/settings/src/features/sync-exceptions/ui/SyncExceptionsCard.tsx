/**
 * BO-14 «Sinxron istisnolari» (07 BO-14, qaror #56b): flagged POS events — when, what (kind), which
 * document, branch, review state; «Ko'rib chiqildi» asks for a mandatory note (1–500). The raw `details`
 * JSON is not rendered (08 §11) — the kind text explains the case.
 */
import { useUnit } from "effector-react";
import { CheckCheck, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { toApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/format";
import { $branches } from "@shared/state/session";
import {
  Button,
  Card,
  ConfirmDialog,
  DataTable,
  EmptyState,
  FormField,
  Icon,
  SimpleSelect,
  StatusChip,
  Textarea,
  type DataTableColumn,
} from "@shared/ui";

import {
  $exceptions,
  $exceptionsCursor,
  $exceptionsError,
  $exceptionsFilter,
  $exceptionsMoreLoading,
  $exceptionsStatus,
  REVIEW_FILTERS,
  REVIEW_NOTE_MAX,
  exceptionDocType,
  exceptionsFilterChanged,
  exceptionsMoreRequested,
  exceptionsOpened,
  exceptionsReloadRequested,
  isNoteValid,
  isReviewFilter,
  reviewExceptionFx,
  type SyncException,
} from "../model/index.ts";

export function SyncExceptionsCard({ online }: { online: boolean }) {
  const { t } = useTranslation("settings");
  const [items, status, error, cursor, moreLoading, filter, branches] = useUnit([
    $exceptions,
    $exceptionsStatus,
    $exceptionsError,
    $exceptionsCursor,
    $exceptionsMoreLoading,
    $exceptionsFilter,
    $branches,
  ]);
  const [opened, onFilter, more, reload, review] = useUnit([
    exceptionsOpened,
    exceptionsFilterChanged,
    exceptionsMoreRequested,
    exceptionsReloadRequested,
    reviewExceptionFx,
  ]);
  const branchNames = useMemo(() => new Map(branches.map((b) => [b.id, b.name])), [branches]);
  const [target, setTarget] = useState<SyncException | null>(null);
  const [note, setNote] = useState("");
  const [touched, setTouched] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    opened();
  }, [opened]);

  const kindLabel = (x: SyncException) => t(`syncExceptions.kinds.${x.kind}`);
  const close = () => {
    setTarget(null);
    setNote("");
    setTouched(false);
    setReviewError(null);
  };
  const submit = async () => {
    setTouched(true);
    if (!target || !isNoteValid(note)) throw new Error("invalid");
    setReviewError(null);
    try {
      await review({ id: target.id, note: note.trim() });
      close();
    } catch (e) {
      setReviewError(serverErrorText(toApiError(e)));
      throw e;
    }
  };

  const columns: DataTableColumn<SyncException>[] = [
    {
      id: "created",
      header: t("syncExceptions.columns.created"),
      width: "140px",
      cell: (x) => <span className="tabular-nums">{formatDateTime(x.created_at)}</span>,
    },
    {
      id: "kind",
      header: t("syncExceptions.columns.kind"),
      cell: (x) => (
        <div className="flex flex-col">
          <span className="font-semibold">{kindLabel(x)}</span>
          <span className="text-[12px] text-muted-foreground">{t(`syncExceptions.hints.${x.kind}`)}</span>
        </div>
      ),
    },
    {
      id: "doc",
      header: t("syncExceptions.columns.document"),
      width: "150px",
      cell: (x) => {
        const doc = exceptionDocType(x.doc_type);
        return doc ? t(`syncExceptions.docTypes.${doc}`) : "—";
      },
    },
    {
      id: "branch",
      header: t("syncExceptions.columns.branch"),
      width: "140px",
      cell: (x) => (x.branch_id ? (branchNames.get(x.branch_id) ?? "—") : "—"),
    },
    {
      id: "review",
      header: t("syncExceptions.columns.review"),
      width: "220px",
      cell: (x) =>
        x.reviewed_at ? (
          <div className="flex flex-col gap-0.5">
            <StatusChip tone="success" icon={CheckCheck}>
              {t("syncExceptions.reviewed")}
            </StatusChip>
            {x.review_note ? (
              <span className="break-words text-[12px] text-muted-foreground">«{x.review_note}»</span>
            ) : null}
          </div>
        ) : (
          <Button
            size="sm"
            variant="secondary"
            disabled={!online}
            aria-label={t("syncExceptions.reviewFor", { kind: kindLabel(x) })}
            onClick={() => setTarget(x)}
          >
            <Icon as={ShieldCheck} size="sm" />
            {t("syncExceptions.review")}
          </Button>
        ),
    },
  ];

  return (
    <Card role="region" aria-labelledby="sync-exceptions-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <h3 id="sync-exceptions-title" className="text-[15px] font-bold">
            {t("syncExceptions.title")}
          </h3>
          <p className="text-small text-foreground-secondary">{t("syncExceptions.subtitle")}</p>
        </div>
        <FormField label={t("syncExceptions.filter")} className="w-56">
          <SimpleSelect
            options={REVIEW_FILTERS.map((f) => ({ value: f, label: t(`syncExceptions.filters.${f}`) }))}
            value={filter}
            onValueChange={(v) => (isReviewFilter(v) ? onFilter(v) : undefined)}
          />
        </FormField>
      </div>
      <DataTable
        label={t("syncExceptions.tableLabel")}
        columns={columns}
        data={items}
        getRowId={(x) => x.id}
        status={status}
        errorMessage={error ? serverErrorText(error) : undefined}
        onRetry={reload}
        minWidth={880}
        skeletonRows={3}
        empty={
          <EmptyState
            icon={CheckCheck}
            title={t(filter === "open" ? "syncExceptions.empty.open" : "syncExceptions.empty.other")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
      {target ? (
        <ConfirmDialog
          open
          onOpenChange={(o) => (o ? undefined : close())}
          title={t("syncExceptions.reviewTitle")}
          description={kindLabel(target)}
          confirmLabel={t("syncExceptions.review")}
          onConfirm={submit}
          error={reviewError}
        >
          <FormField
            label={t("syncExceptions.note")}
            required
            error={touched && !isNoteValid(note) ? t("syncExceptions.noteRequired") : undefined}
          >
            {(a11y) => (
              <Textarea
                {...a11y}
                value={note}
                maxLength={REVIEW_NOTE_MAX}
                rows={3}
                onChange={(e) => setNote(e.target.value)}
              />
            )}
          </FormField>
        </ConfirmDialog>
      ) : null}
    </Card>
  );
}
