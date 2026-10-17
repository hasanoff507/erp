/**
 * ImportProductsFlow — Excel/CSV product import (US-M04-04, 19 §6, 07 BO-21 ③a / catalog import).
 *
 *   ① Shablon (CSV, `;`, UTF-8) → ② fayl (xlsx/csv ≤ 10 MB) → server tekshiruvi (async, poll) →
 *   ③ xatoli qatorlar jadvali (qator, ustun, xabar) → tuzatib qayta yuklash yoki xatolarsiz davom →
 *   ④ commit (async, poll) → natija (yaratilgan tovarlar soni).
 *
 * Self-contained: owns its model instance (factory), so it can be embedded in the onboarding wizard
 * (`embedded` hides the kind picker and the screen-level title) and in the catalog import screen.
 * Requires `catalog.manage` (the server checks; the caller decides whether to render it).
 *
 * `kind="opening_stock"` (BO-21 ③b, 19 §6, permission `stock.opening.manage`): the same flow with the
 * `barcode;qty;unit_cost;expiry_date` template; the commit posts one stock-opening document.
 */
import {
  CircleCheck,
  Download,
  FileWarning,
  LoaderCircle,
  RotateCcw,
  TriangleAlert,
  WifiOff,
} from "lucide-react";
import { useUnit } from "effector-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { useTranslation } from "@shared/i18n";
import { $isOnline } from "@shared/state/network";
import { Banner, Button, Card, ConfirmDialog, FileDropzone, Icon, StatusChip } from "@shared/ui";

import { apiErrorText } from "#/shared/lib/messages.ts";

import { importFlowDeps } from "../model/deps/index.ts";
import { createImportFlow, type ImportFlowModel } from "../model/factory/index.ts";
import {
  ENABLED_IMPORT_KINDS,
  IMPORT_KINDS,
  TEMPLATE_COLUMNS,
  type FlowImportKind,
  type ImportFlowDeps,
  type ImportProductsResult,
} from "../model/types/index.ts";
import { ErrorRowsTable } from "./ErrorRowsTable.tsx";

export interface ImportProductsFlowProps {
  /** Inside another screen (BO-21 ③a/③b): no kind picker, compact header. */
  embedded?: boolean;
  /** What the file holds (19 §6): `products` (default) or `opening_stock` (BO-21 ③b). */
  kind?: FlowImportKind;
  /** Called once when the commit finished (products created). */
  onDone?: (result: ImportProductsResult) => void;
  /** Shown as a secondary action next to the result ("Tovarlar ro'yxati" on the catalog screen). */
  doneAction?: ReactNode;
  /** Test/wiring override of the generated API + timers. */
  deps?: ImportFlowDeps;
  className?: string;
}

export function ImportProductsFlow({
  embedded = false,
  kind = "products",
  onDone,
  doneAction,
  deps,
  className,
}: ImportProductsFlowProps) {
  const [model] = useState(() => createImportFlow(deps ?? importFlowDeps, kind));
  const onDoneRef = useRef(onDone);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    const subscription = model.completed.watch((result) => onDoneRef.current?.(result));
    return () => {
      subscription.unsubscribe();
      model.disposed();
    };
  }, [model]);

  return (
    <div className={className}>
      <FlowBody model={model} embedded={embedded} doneAction={doneAction} />
    </div>
  );
}

function FlowBody({
  model,
  embedded,
  doneAction,
}: {
  model: ImportFlowModel;
  embedded: boolean;
  doneAction?: ReactNode;
}) {
  const { t } = useTranslation("catalog");
  const online = useUnit($isOnline);
  const kind: FlowImportKind = model.kind === "opening_stock" ? "opening_stock" : "products";
  const [phase, flowError, templateLoading, requestTemplate] = useUnit([
    model.$phase,
    model.$flowError,
    model.$templateLoading,
    model.templateRequested,
  ]);

  return (
    <div className="flex flex-col gap-4">
      {embedded ? null : <KindPicker />}

      <Card className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-h2">{t("import.template.title")}</h2>
            <p className="text-small text-foreground-secondary">{t("import.template.hint")}</p>
            {kind === "opening_stock" ? (
              <p className="text-small text-foreground-secondary">{t("import.openingStock.hint")}</p>
            ) : null}
            <p className="mt-1 text-[12px] text-muted-foreground">
              {t("import.template.columns")}{" "}
              <code className="font-semibold text-foreground-secondary">{TEMPLATE_COLUMNS[kind]}</code>
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => requestTemplate()}
            disabled={templateLoading || !online}
            aria-busy={templateLoading || undefined}
          >
            <Icon as={Download} size="sm" />
            {t("import.template.download")}
          </Button>
        </div>
      </Card>

      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("import.offline")}
        </Banner>
      )}

      {flowError ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {apiErrorText(flowError)}
        </Banner>
      ) : null}

      {phase === "select" ? <SelectStep model={model} online={online} /> : null}
      {phase === "processing" || phase === "committing" ? <ProgressStep model={model} /> : null}
      {phase === "review" || phase === "invalid" ? <ReviewStep model={model} online={online} /> : null}
      {phase === "done" ? <DoneStep model={model} embedded={embedded} doneAction={doneAction} /> : null}
    </div>
  );
}

/** 19 §6 kinds: only `products` in Bosqich 1; the others are shown disabled ("keyingi bosqich"). */
function KindPicker() {
  const { t } = useTranslation("catalog");
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1.5 text-label text-foreground-secondary">{t("import.kind.label")}</legend>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-2.5">
        {IMPORT_KINDS.map((kind) => {
          const enabled = ENABLED_IMPORT_KINDS.has(kind);
          return (
            <div
              key={kind}
              aria-disabled={!enabled || undefined}
              aria-current={kind === "products" ? "true" : undefined}
              className={
                enabled
                  ? "flex flex-col gap-1 rounded-lg border-2 border-primary bg-primary-soft/40 px-4 py-3"
                  : "flex flex-col gap-1 rounded-lg border border-border bg-muted px-4 py-3 opacity-70"
              }
            >
              <span className="flex items-center justify-between gap-2 text-[14px] font-bold">
                {t(`import.kind.${kind}.title`)}
                {enabled ? null : (
                  <StatusChip tone="neutral">
                    {kind === "opening_stock" ? t("import.kind.opening_stock.where") : t("common.nextPhase")}
                  </StatusChip>
                )}
              </span>
              <span className="text-small text-foreground-secondary">
                {t(`import.kind.${kind}.description`)}
              </span>
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}

function SelectStep({ model, online }: { model: ImportFlowModel; online: boolean }) {
  const { t } = useTranslation("catalog");
  const [file, fileError, onFile, onRemove, start] = useUnit([
    model.$file,
    model.$fileError,
    model.fileSelected,
    model.fileRemoved,
    model.startRequested,
  ]);

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="text-h2">{t("import.upload.title")}</h2>
      <FileDropzone
        file={file}
        onFile={onFile}
        onRemove={onRemove}
        error={fileError}
        disabled={!online}
        title={t("import.upload.dropTitle")}
      />
      <div className="flex justify-end">
        <Button onClick={() => start()} disabled={!file || !online}>
          {t("import.upload.validate")}
        </Button>
      </div>
    </Card>
  );
}

function ProgressStep({ model }: { model: ImportFlowModel }) {
  const { t } = useTranslation("catalog");
  const [phase, step, file] = useUnit([model.$phase, model.$processingStep, model.$file]);
  const text =
    phase === "committing"
      ? t(model.kind === "opening_stock" ? "import.openingStock.committing" : "import.progress.committing")
      : step === "uploading"
        ? t("import.progress.uploading")
        : t("import.progress.validating");
  return (
    <Card className="flex items-center gap-3" role="status" aria-live="polite" aria-busy="true">
      <Icon as={LoaderCircle} size="lg" className="animate-spin text-primary" />
      <div className="min-w-0">
        <p className="text-[15px] font-bold">{text}</p>
        {file ? <p className="truncate text-small text-foreground-secondary">{file.name}</p> : null}
      </div>
    </Card>
  );
}

function ReviewStep({ model, online }: { model: ImportFlowModel; online: boolean }) {
  const { t } = useTranslation("catalog");
  const [phase, job, rows, cursor, errorsLoading, busy, commit, restart, loadMore] = useUnit([
    model.$phase,
    model.$job,
    model.$errorRows,
    model.$errorsCursor,
    model.$errorsLoading,
    model.$busy,
    model.commitRequested,
    model.restarted,
    model.moreErrorsRequested,
  ]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  if (!job) return null;

  const invalid = phase === "invalid";
  const opening = model.kind === "opening_stock";
  const okRows = job.ok_rows;
  const errorRows = job.error_rows;

  const onCommit = () => {
    if (errorRows > 0) setConfirmOpen(true);
    else commit();
  };

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-h2">{t("import.review.title")}</h2>
        <dl className="grid grid-cols-3 gap-3" aria-label={t("import.review.summaryLabel")}>
          <Stat label={t("import.review.total")} value={job.total_rows} />
          <Stat label={t("import.review.ok")} value={okRows} tone="success" />
          <Stat
            label={t("import.review.errors")}
            value={errorRows}
            tone={errorRows > 0 ? "destructive" : "neutral"}
          />
        </dl>
      </div>

      {invalid ? (
        <Banner tone="destructive" icon={FileWarning} live="assertive">
          {t("import.review.invalid")}
        </Banner>
      ) : errorRows > 0 ? (
        <Banner tone="warning" icon={TriangleAlert}>
          {t("import.review.partial", { ok: okRows, errors: errorRows })}
        </Banner>
      ) : (
        <Banner tone="success" icon={CircleCheck}>
          {t(opening ? "import.openingStock.allOk" : "import.review.allOk", { count: okRows })}
        </Banner>
      )}

      {errorRows > 0 || rows.length > 0 ? (
        <ErrorRowsTable
          rows={rows}
          total={errorRows || rows.length}
          hasMore={cursor !== null}
          loading={errorsLoading}
          onLoadMore={loadMore}
        />
      ) : null}

      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" onClick={() => restart()} disabled={busy}>
          <Icon as={RotateCcw} size="sm" />
          {t("import.review.reupload")}
        </Button>
        {invalid ? null : (
          <Button onClick={onCommit} disabled={busy || !online || okRows === 0}>
            {t("import.review.commit", { count: okRows })}
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("import.review.confirmTitle")}
        description={t(opening ? "import.openingStock.confirmBody" : "import.review.confirmBody", {
          ok: okRows,
          errors: errorRows,
        })}
        confirmLabel={t("import.review.confirmAction")}
        onConfirm={() => {
          setConfirmOpen(false);
          commit();
        }}
      />
    </Card>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "success" | "destructive";
}) {
  const color =
    tone === "success"
      ? "text-success-strong"
      : tone === "destructive"
        ? "text-destructive-strong"
        : "text-foreground";
  return (
    <div className="rounded-lg border border-border px-4 py-3">
      <dt className="text-caption text-muted-foreground">{label}</dt>
      <dd className={`text-kpi tabular-nums ${color}`}>{value}</dd>
    </div>
  );
}

function DoneStep({
  model,
  embedded,
  doneAction,
}: {
  model: ImportFlowModel;
  embedded: boolean;
  doneAction?: ReactNode;
}) {
  const { t } = useTranslation("catalog");
  const [result, restart] = useUnit([model.$result, model.restarted]);
  if (!result) return null;
  return (
    <Card className="flex flex-col items-center gap-2 py-8 text-center" role="status" aria-live="polite">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-success-soft text-success-strong">
        <Icon as={CircleCheck} size="lg" />
      </span>
      <p className="text-h2">
        {model.kind === "opening_stock"
          ? t("import.openingStock.doneTitle", { count: result.lineCount })
          : t("import.done.title", { count: result.createdProductCount })}
      </p>
      {result.skippedRows > 0 ? (
        <p className="text-small text-foreground-secondary">
          {t("import.done.skipped", { count: result.skippedRows })}
        </p>
      ) : null}
      {result.createdDocIds.length > 0 && model.kind === "products" ? (
        <p className="text-small text-foreground-secondary">{t("import.done.prices")}</p>
      ) : null}
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        {embedded ? null : (
          <Button variant="secondary" onClick={() => restart()}>
            {t("import.done.again")}
          </Button>
        )}
        {doneAction}
      </div>
    </Card>
  );
}
