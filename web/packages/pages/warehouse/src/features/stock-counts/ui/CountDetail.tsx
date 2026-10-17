/**
 * Stock count detail (07 BO-03 «Inventarizatsiyalar» row → kutilgan / sanalgan / farq / summa).
 * While `counting`, a simple back-office line entry (sanalgan per product, + unexpected product) lets a
 * count be completed without POS-10 (Bosqich 3): «Saqlash» = `POST /stock-counts/{id}/lines`,
 * «Sanashni yakunlash» = `submit-for-review`. In `review`: «Farqni tasdiqlash» / «Bekor qilish».
 */
import { useUnit } from "effector-react";
import { Check, CircleCheck, Save, TriangleAlert, X } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  ConfirmDialog,
  DecimalInput,
  ErrorState,
  Icon,
  SearchInput,
  SegmentedControl,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  Skeleton,
  toast,
} from "@shared/ui";

import { ProductPicker } from "#/entities/product/index.tsx";
import { productCached, useQtyFormat } from "#/entities/refs/index.ts";
import { isNegative, isZero, trimQty } from "#/shared/lib/decimal.ts";
import { errorText } from "#/shared/lib/errors.ts";
import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";

import {
  $acting,
  $actionError,
  $detail,
  $detailError,
  $detailStatus,
  $drafts,
  $extras,
  $lineFilter,
  $lineSearch,
  $pendingLines,
  $selectedId,
  $totals,
  $visibleLines,
  actionErrorDismissed,
  cancelCountFx,
  countProductSearch,
  countSelected,
  countedChanged,
  detailReloadRequested,
  extraLineAdded,
  isCountedValid,
  lineFilterChanged,
  lineSearchChanged,
  recordLinesFx,
  submitCountFx,
  type LineFilter,
} from "../model/index.ts";

import { CountStatusChip } from "./chips.tsx";
import { PostCountDialog } from "./PostCountDialog.tsx";

export interface CountRights {
  /** `stock.count.create` — start, line entry, submit for review. */
  create: boolean;
  /** `stock.count.post` — post the difference, cancel. */
  post: boolean;
}

const PAGE = 100;

export function CountDetail({ rights, online }: { rights: CountRights; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const [selectedId, detail, status, error, select, reload] = useUnit([
    $selectedId,
    $detail,
    $detailStatus,
    $detailError,
    countSelected,
    detailReloadRequested,
  ]);

  return (
    <Sheet open={selectedId !== null} onOpenChange={(open) => (open ? undefined : select(null))}>
      <SheetContent wide>
        {detail ? (
          <DetailBody rights={rights} online={online} />
        ) : (
          <>
            <SheetHeader>
              <SheetTitle>{t("counts.detailTitle")}</SheetTitle>
            </SheetHeader>
            <SheetBody>
              {status === "error" && error ? (
                <ErrorState message={errorText(error)} onRetry={reload} />
              ) : (
                <div className="flex flex-col gap-3" aria-busy="true">
                  <Skeleton className="h-6 w-1/2" />
                  <Skeleton className="h-40 w-full" />
                </div>
              )}
            </SheetBody>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function DetailBody({ rights, online }: { rights: CountRights; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const formatQty = useQtyFormat();
  const [detail, totals, lines, drafts, extras, filter, search, pending, acting, actionError] = useUnit([
    $detail,
    $totals,
    $visibleLines,
    $drafts,
    $extras,
    $lineFilter,
    $lineSearch,
    $pendingLines,
    $acting,
    $actionError,
  ]);
  const [onCounted, onExtra, onFilter, onSearch, save, submit, cancel, cache, dismissError] = useUnit([
    countedChanged,
    extraLineAdded,
    lineFilterChanged,
    lineSearchChanged,
    recordLinesFx,
    submitCountFx,
    cancelCountFx,
    productCached,
    actionErrorDismissed,
  ]);
  const [shown, setShown] = useState(PAGE);
  const [posting, setPosting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  if (!detail || !totals) return null;

  const editable = detail.status === "counting" && rights.create && online;
  const invalid = Object.values(drafts).some((v) => !isCountedValid(v));
  const canCancel = rights.post && (detail.status === "counting" || detail.status === "review");

  const saveLines = () =>
    save({ id: detail.id, lines: pending })
      .then(() => toast.success(t("counts.toast.saved", { count: pending.length })))
      .catch(() => undefined);

  const filters: { value: LineFilter; label: string }[] = [
    { value: "all", label: t("counts.lineFilter.all", { count: detail.lines.length }) },
    { value: "diff", label: t("counts.lineFilter.diff", { count: totals.diffLines }) },
    { value: "uncounted", label: t("counts.lineFilter.uncounted", { count: totals.uncounted }) },
  ];

  return (
    <>
      <SheetHeader>
        <SheetTitle>{detail.number ?? t("counts.noNumber")}</SheetTitle>
        <SheetDescription>
          {formatDate(detail.doc_date)}
          {detail.started_at ? ` · ${t("counts.startedAt", { at: formatDateTime(detail.started_at) })}` : ""}
        </SheetDescription>
        <div className="flex flex-wrap gap-2 pt-1">
          <CountStatusChip status={detail.status} />
        </div>
      </SheetHeader>
      <SheetBody>
        {actionError ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {errorText(actionError)}
          </Banner>
        ) : null}
        <dl className="grid grid-cols-3 gap-2" aria-label={t("counts.summaryLabel")}>
          <div className="rounded-lg border border-border px-3 py-2">
            <dt className="text-[12px] font-semibold text-muted-foreground">
              {t("counts.summary.shortage")}
            </dt>
            <dd className="text-[15px] font-extrabold tabular-nums text-destructive-strong">
              {formatMoney(totals.shortage)}
            </dd>
          </div>
          <div className="rounded-lg border border-border px-3 py-2">
            <dt className="text-[12px] font-semibold text-muted-foreground">{t("counts.summary.surplus")}</dt>
            <dd className="text-[15px] font-extrabold tabular-nums text-success-strong">
              {formatMoney(totals.surplus)}
            </dd>
          </div>
          <div className="rounded-lg border border-border px-3 py-2">
            <dt className="text-[12px] font-semibold text-muted-foreground">
              {t("counts.summary.uncounted")}
            </dt>
            <dd className="text-[15px] font-extrabold tabular-nums">{totals.uncounted}</dd>
          </div>
        </dl>
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedControl
            label={t("counts.lineFilter.label")}
            options={filters}
            value={filter}
            onChange={onFilter}
          />
          <SearchInput
            className="w-56"
            value={search}
            onSearch={onSearch}
            aria-label={t("counts.lineSearch")}
            placeholder={t("counts.lineSearch")}
          />
          {editable ? (
            <ProductPicker
              model={countProductSearch}
              onPick={(p) => {
                cache(p);
                onExtra({ productId: p.id, name: p.name });
              }}
            />
          ) : null}
        </div>
        {extras.length > 0 ? (
          <ul className="flex flex-col gap-2" aria-label={t("counts.extraLabel")}>
            {extras.map((e) => (
              <li
                key={e.productId}
                className="flex items-center gap-3 rounded-lg border border-dashed border-border px-3 py-2"
              >
                <span className="min-w-0 flex-1 truncate text-[13px] font-semibold">
                  {e.name}{" "}
                  <span className="font-normal text-muted-foreground">· {t("counts.extraHint")}</span>
                </span>
                <DecimalInput
                  className="w-32"
                  disabled={acting}
                  aria-label={t("counts.countedFor", { name: e.name })}
                  precision={3}
                  outputScale={3}
                  value={drafts[e.productId] ?? ""}
                  onChange={(v) => onCounted({ productId: e.productId, value: v })}
                />
              </li>
            ))}
          </ul>
        ) : null}
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[560px] text-[13px]" aria-label={t("counts.linesLabel")}>
            <thead className="bg-muted text-caption text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left">{t("counts.lines.product")}</th>
                <th className="px-3 py-2 text-right">{t("counts.lines.expected")}</th>
                <th className="px-3 py-2 text-right">{t("counts.lines.counted")}</th>
                <th className="px-3 py-2 text-right">{t("counts.lines.diff")}</th>
                <th className="px-3 py-2 text-right">{t("counts.lines.amount")}</th>
              </tr>
            </thead>
            <tbody>
              {lines.slice(0, shown).map((l) => {
                const draft = drafts[l.product_id];
                const diffTone =
                  l.diff === null || isZero(l.diff)
                    ? ""
                    : isNegative(l.diff)
                      ? "text-destructive-strong"
                      : "text-success-strong";
                return (
                  <tr key={l.id} className="border-t border-divider">
                    <td className="px-3 py-2 font-semibold">{l.product_name}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatQty(l.expected)}</td>
                    <td className="w-36 px-3 py-1.5 text-right tabular-nums">
                      {editable ? (
                        <DecimalInput
                          disabled={acting}
                          aria-label={t("counts.countedFor", { name: l.product_name })}
                          aria-invalid={(draft !== undefined && !isCountedValid(draft)) || undefined}
                          precision={3}
                          outputScale={3}
                          value={draft ?? (l.counted === null ? "" : trimQty(l.counted))}
                          onChange={(v) => onCounted({ productId: l.product_id, value: v })}
                        />
                      ) : l.counted === null ? (
                        <span className="text-warning-strong">{t("counts.notCounted")}</span>
                      ) : (
                        formatQty(l.counted)
                      )}
                    </td>
                    <td className={`px-3 py-2 text-right font-bold tabular-nums ${diffTone}`}>
                      {l.diff === null ? "—" : formatQty(l.diff)}
                    </td>
                    <td className={`px-3 py-2 text-right tabular-nums ${diffTone}`}>
                      {l.amount === null ? "—" : formatMoney(l.amount, { withCurrency: false })}
                    </td>
                  </tr>
                );
              })}
              {lines.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                    {t("counts.noLines")}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        {lines.length > shown ? (
          <Button
            variant="secondary"
            size="sm"
            className="self-center"
            onClick={() => setShown((n) => n + PAGE)}
          >
            {t("counts.showMore", { count: lines.length - shown })}
          </Button>
        ) : null}
      </SheetBody>
      {editable || canCancel || (detail.status === "review" && rights.post) ? (
        <SheetFooter>
          {canCancel ? (
            <Button
              variant="destructive-outline"
              disabled={!online || acting}
              onClick={() => setCancelling(true)}
            >
              <Icon as={X} size="sm" />
              {t("actions.cancelDoc")}
            </Button>
          ) : null}
          {editable ? (
            <>
              <Button
                variant="secondary"
                disabled={pending.length === 0 || invalid || acting}
                aria-busy={acting || undefined}
                onClick={() => void saveLines()}
              >
                <Icon as={Save} size="sm" />
                {t("counts.actions.save", { count: pending.length })}
              </Button>
              <Button
                disabled={pending.length > 0 || acting}
                onClick={() => {
                  dismissError();
                  setConfirmSubmit(true);
                }}
              >
                <Icon as={CircleCheck} size="sm" />
                {t("counts.actions.submit")}
              </Button>
            </>
          ) : null}
          {detail.status === "review" && rights.post ? (
            <Button disabled={!online || acting} onClick={() => setPosting(true)}>
              <Icon as={Check} size="sm" />
              {t("counts.actions.post")}
            </Button>
          ) : null}
        </SheetFooter>
      ) : null}
      <PostCountDialog count={detail} totals={totals} open={posting} onClose={() => setPosting(false)} />
      <ConfirmDialog
        open={confirmSubmit}
        onOpenChange={setConfirmSubmit}
        title={t("counts.submit.title")}
        description={
          totals.uncounted > 0
            ? t("counts.submit.uncounted", { count: totals.uncounted })
            : t("counts.submit.description")
        }
        confirmLabel={t("counts.actions.submit")}
        error={actionError ? errorText(actionError) : null}
        onConfirm={() => submit(detail.id).then(() => toast.success(t("counts.toast.submitted")))}
      />
      <ReasonDialog
        open={cancelling}
        onOpenChange={setCancelling}
        title={t("counts.cancel.title")}
        description={t("counts.cancel.description")}
        onConfirm={async (reason) => {
          await cancel({ id: detail.id, reason });
          toast.success(t("counts.toast.cancelled"));
        }}
      />
    </>
  );
}
