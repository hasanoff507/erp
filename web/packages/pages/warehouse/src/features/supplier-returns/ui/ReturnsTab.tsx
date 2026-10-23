/**
 * BO-04 «Qaytarish» (07, US-M07-05): list (holat), «Qaytarish qoralamasi» (kirim hujjati — `posted`,
 * qaytariladigan qatorlar — partiya qoldig'idan ko'p emas, sabab, sana) → `POST /supplier-returns`;
 * detail: «Qaytarishni o'tkazish» (`purchases.post`, «Qaytarishni tasdiqlaysizmi?») / «Bekor qilish».
 * The 12-month refusal (409 `reverse_sale_required`) is explained; `awaiting_einvoice` is shown.
 */
import { useUnit } from "effector-react";
import { Check, Plus, TriangleAlert, Undo2, X } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  ConfirmDialog,
  DataTable,
  DecimalInput,
  EmptyState,
  ErrorState,
  FormField,
  Icon,
  Input,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SimpleSelect,
  Skeleton,
  StatusChip,
  Textarea,
  toast,
  type DataTableColumn,
  type Tone,
} from "@shared/ui";

import { useQtyFormat } from "#/entities/refs/index.ts";
import { todayIso } from "#/shared/lib/effect.ts";
import { errorText } from "#/shared/lib/errors.ts";
import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";
import { SearchPicker } from "#/shared/ui/SearchPicker.tsx";

import {
  $acting,
  $actionError,
  $createOpen,
  $cursor,
  $detail,
  $detailError,
  $error,
  $filter,
  $moreLoading,
  $receipt,
  $receiptError,
  $returns,
  $selectedId,
  $status,
  RETURN_REASONS,
  RETURN_STATUSES,
  cancelReturnFx,
  createClosed,
  createOpened,
  createReturnFx,
  isReturnStatus,
  loadReceiptFx,
  moreRequested,
  postReturnFx,
  receiptChosen,
  receiptSearch,
  reloadRequested,
  returnLineError,
  returnSelected,
  returnableLines,
  statusChanged,
  toReturnBody,
  type ReturnDraft,
  type ReturnReason,
  type ReturnRow,
  type ReturnStatus,
} from "../model/index.ts";

const ALL = "all";
const TONE: Readonly<Record<string, Tone>> = {
  draft: "awaiting-approval",
  posted: "success",
  cancelled: "neutral",
};

function ReturnStatusChip({ status }: { status: string }) {
  const { t } = useTranslation("warehouse");
  return (
    <StatusChip tone={TONE[status] ?? "neutral"}>{t(`returns.status.${status as ReturnStatus}`)}</StatusChip>
  );
}

export interface ReturnRights {
  create: boolean;
  post: boolean;
}

export function ReturnsTab({ rights, online }: { rights: ReturnRights; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const [rows, status, error, cursor, moreLoading, filter] = useUnit([
    $returns,
    $status,
    $error,
    $cursor,
    $moreLoading,
    $filter,
  ]);
  const [onStatus, more, reload, select, openCreate] = useUnit([
    statusChanged,
    moreRequested,
    reloadRequested,
    returnSelected,
    createOpened,
  ]);

  const columns: DataTableColumn<ReturnRow>[] = [
    {
      id: "doc",
      header: t("returns.columns.doc"),
      width: "170px",
      cell: (r) => (
        <span className="flex flex-col">
          <span className="font-semibold">{r.number ?? t("returns.draftNumber")}</span>
          <span className="text-[12px] text-muted-foreground">{formatDate(r.doc_date)}</span>
        </span>
      ),
    },
    {
      id: "supplier",
      header: t("returns.columns.supplier"),
      cell: (r) => (
        <span className="flex flex-col">
          <span className="font-semibold">{r.supplier.name ?? "—"}</span>
          <span className="text-[12px] text-muted-foreground">
            {t("returns.receiptRef", { number: r.receipt_number ?? "—" })} ·{" "}
            {t(`returns.reasons.${r.reason}`)}
          </span>
        </span>
      ),
    },
    {
      id: "total",
      header: t("returns.columns.total"),
      numeric: true,
      width: "150px",
      cell: (r) => formatMoney(r.invoice_total, { withCurrency: false }),
    },
    {
      id: "status",
      header: t("returns.columns.status"),
      width: "230px",
      cell: (r) => (
        <span className="flex flex-wrap gap-1.5">
          <ReturnStatusChip status={r.status} />
          {r.vat_adjustment_status === "awaiting_einvoice" ? (
            <StatusChip tone="awaiting-approval">{t("returns.awaitingEinvoice")}</StatusChip>
          ) : null}
        </span>
      ),
    },
  ];

  return (
    <section className="flex flex-col gap-3" aria-label={t("purchases.tabs.returns")}>
      <div className="flex flex-wrap items-end gap-3">
        <FormField label={t("returns.filter")} className="w-48">
          <SimpleSelect
            options={[
              { value: ALL, label: t("returns.allStatuses") },
              ...RETURN_STATUSES.map((s) => ({ value: s, label: t(`returns.status.${s}`) })),
            ]}
            value={filter ?? ALL}
            onValueChange={(v) => onStatus(isReturnStatus(v) ? v : null)}
          />
        </FormField>
        <div className="grow" />
        {rights.create ? (
          <Button disabled={!online} onClick={() => openCreate()}>
            <Icon as={Plus} size="sm" />
            {t("returns.create")}
          </Button>
        ) : null}
      </div>
      <DataTable
        label={t("returns.tableLabel")}
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        onRowClick={(r) => select(r.id)}
        minWidth={820}
        empty={
          <EmptyState
            icon={Undo2}
            title={t("returns.empty.title")}
            description={t("returns.empty.description")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
      <ReturnDetail rights={rights} online={online} />
      <CreateReturnSheet online={online} />
    </section>
  );
}

function CreateReturnSheet({ online }: { online: boolean }) {
  const { t } = useTranslation("warehouse");
  const [open, close] = useUnit([$createOpen, createClosed]);
  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : close())}>
      <SheetContent wide>
        <SheetHeader>
          <SheetTitle>{t("returns.createTitle")}</SheetTitle>
          <SheetDescription>{t("returns.createDescription")}</SheetDescription>
        </SheetHeader>
        {open ? <CreateReturnForm online={online} /> : null}
      </SheetContent>
    </Sheet>
  );
}

function CreateReturnForm({ online }: { online: boolean }) {
  const { t } = useTranslation("warehouse");
  const formatQty = useQtyFormat();
  const [receipt, receiptError, loading, choose, create, pending, close] = useUnit([
    $receipt,
    $receiptError,
    loadReceiptFx.pending,
    receiptChosen,
    createReturnFx,
    createReturnFx.pending,
    createClosed,
  ]);
  const [draft, setDraft] = useState<ReturnDraft>({});
  const [reason, setReason] = useState<ReturnReason | "">("");
  const [docDate, setDocDate] = useState(todayIso());
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lines = receipt ? returnableLines(receipt) : [];
  const errors = Object.fromEntries(
    lines.map((l) => [l.id, returnLineError(draft[l.id] ?? "", l.lot_qty_left ?? "0")]),
  );
  const chosen = lines.filter((l) => (draft[l.id] ?? "") !== "");
  const valid =
    receipt !== null && reason !== "" && chosen.length > 0 && Object.values(errors).every((e) => e === null);

  const submit = () => {
    setSubmitted(true);
    if (!valid || !receipt || !reason) return;
    setError(null);
    create(toReturnBody(receipt, draft, reason, docDate, comment))
      .then(() => toast.success(t("returns.toast.drafted")))
      .catch((e: unknown) => setError(errorText(e)));
  };

  return (
    <>
      <SheetBody>
        <FormField
          label={t("returns.fields.receipt")}
          required
          error={submitted && !receipt ? "validation.required" : null}
        >
          {(a11y) => (
            <SearchPicker
              {...a11y}
              model={receiptSearch}
              variant="outline"
              className="w-full justify-start font-semibold"
              trigger={
                receipt
                  ? `${receipt.number ?? "—"} · ${receipt.supplier.name ?? ""} · ${formatDate(receipt.doc_date)}`
                  : t("returns.chooseReceipt")
              }
              searchLabel={t("returns.receiptSearch")}
              placeholder={t("returns.receiptPlaceholder")}
              getKey={(r) => r.id}
              renderItem={(r) => ({
                title: r.number ?? "—",
                meta: [r.supplier.name, formatDate(r.doc_date)].filter(Boolean).join(" · "),
              })}
              onPick={(r) => {
                setDraft({});
                choose(r.id);
              }}
              disabled={!online}
            />
          )}
        </FormField>
        {receiptError ? (
          <Banner tone="destructive" icon={TriangleAlert}>
            {errorText(receiptError)}
          </Banner>
        ) : null}
        {loading ? <Skeleton className="h-32 w-full" /> : null}
        {receipt && !loading ? (
          lines.length === 0 ? (
            <Banner tone="info" icon={TriangleAlert}>
              {t("returns.nothingToReturn")}
            </Banner>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full min-w-[560px] text-[13px]" aria-label={t("returns.linesLabel")}>
                <thead className="bg-muted text-caption text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 text-left">{t("returns.lines.product")}</th>
                    <th className="px-3 py-2 text-right">{t("returns.lines.received")}</th>
                    <th className="px-3 py-2 text-right">{t("returns.lines.left")}</th>
                    <th className="px-3 py-2 text-right">{t("returns.lines.qty")}</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l) => (
                    <tr key={l.id} className="border-t border-divider align-top">
                      <td className="px-3 py-2">
                        <span className="font-semibold">{l.product_name ?? "—"}</span>
                        {l.expiry_date ? (
                          <span className="block text-[12px] text-muted-foreground">
                            {t("receipts.expiryValue", { date: formatDate(l.expiry_date) })}
                          </span>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatQty(l.qty, l.unit_code)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {formatQty(l.lot_qty_left ?? "0", l.unit_code)}
                      </td>
                      <td className="w-36 px-3 py-1.5">
                        <DecimalInput
                          aria-label={t("returns.qtyFor", { name: l.product_name ?? "" })}
                          aria-invalid={errors[l.id] !== null || undefined}
                          precision={3}
                          outputScale={3}
                          value={draft[l.id] ?? ""}
                          onChange={(v) => setDraft((d) => ({ ...d, [l.id]: v }))}
                        />
                        {errors[l.id] ? (
                          <p role="alert" className="mt-1 text-[12px] font-semibold text-destructive">
                            {t("returns.overLot")}
                          </p>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : null}
        {submitted && receipt && chosen.length === 0 ? (
          <p role="alert" className="text-small font-semibold text-destructive">
            {t("returns.noLines")}
          </p>
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            label={t("returns.fields.reason")}
            required
            error={submitted && reason === "" ? "validation.required" : null}
          >
            <SimpleSelect
              options={RETURN_REASONS.map((r) => ({ value: r, label: t(`returns.reasons.${r}`) }))}
              value={reason || undefined}
              onValueChange={(v) => setReason(v as ReturnReason)}
            />
          </FormField>
          <FormField label={t("returns.fields.docDate")} required>
            <Input type="date" value={docDate} onChange={(e) => setDocDate(e.target.value)} />
          </FormField>
        </div>
        <FormField label={t("returns.fields.comment")} optional>
          <Textarea value={comment} rows={2} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
        </FormField>
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
      </SheetBody>
      <SheetFooter>
        <Button variant="secondary" disabled={pending} onClick={() => close()}>
          {t("actions.back")}
        </Button>
        <Button disabled={pending || !online} aria-busy={pending || undefined} onClick={submit}>
          {t("returns.saveDraft")}
        </Button>
      </SheetFooter>
    </>
  );
}

function ReturnDetail({ rights, online }: { rights: ReturnRights; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const formatQty = useQtyFormat();
  const [selectedId, ret, detailError, acting, actionError, select, post, cancel] = useUnit([
    $selectedId,
    $detail,
    $detailError,
    $acting,
    $actionError,
    returnSelected,
    postReturnFx,
    cancelReturnFx,
  ]);
  const [confirmPost, setConfirmPost] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  return (
    <Sheet open={selectedId !== null} onOpenChange={(next) => (next ? undefined : select(null))}>
      <SheetContent wide>
        {!ret ? (
          <>
            <SheetHeader>
              <SheetTitle>{t("returns.detailTitle")}</SheetTitle>
            </SheetHeader>
            {detailError ? (
              <SheetBody>
                <ErrorState
                  message={errorText(detailError)}
                  onRetry={() => (selectedId ? select(selectedId) : undefined)}
                />
              </SheetBody>
            ) : (
              <SheetBody aria-busy="true">
                <Skeleton className="h-40 w-full" />
              </SheetBody>
            )}
          </>
        ) : (
          <>
            <SheetHeader>
              <SheetTitle>{ret.number ?? t("returns.draftNumber")}</SheetTitle>
              <SheetDescription>
                {[
                  ret.supplier.name,
                  t("returns.receiptRef", { number: ret.receipt_number ?? "—" }),
                  formatDate(ret.doc_date),
                  t(`returns.reasons.${ret.reason}`),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </SheetDescription>
              <div className="flex flex-wrap gap-2 pt-1">
                <ReturnStatusChip status={ret.status} />
                {ret.vat_adjustment_status === "awaiting_einvoice" ? (
                  <StatusChip tone="awaiting-approval">{t("returns.awaitingEinvoice")}</StatusChip>
                ) : null}
              </div>
            </SheetHeader>
            <SheetBody>
              {actionError ? (
                <Banner tone="destructive" icon={TriangleAlert} live="assertive">
                  {errorText(actionError)}
                </Banner>
              ) : null}
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full min-w-[520px] text-[13px]" aria-label={t("returns.linesLabel")}>
                  <thead className="bg-muted text-caption text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("returns.lines.product")}</th>
                      <th className="px-3 py-2 text-right">{t("returns.lines.qty")}</th>
                      <th className="px-3 py-2 text-right">{t("returns.lines.cost")}</th>
                      <th className="px-3 py-2 text-right">{t("returns.lines.amount")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ret.lines.map((l) => (
                      <tr key={l.id} className="border-t border-divider">
                        <td className="px-3 py-2 font-semibold">{l.product_name ?? "—"}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatQty(l.qty, l.unit_code)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {formatMoney(l.cost, { withCurrency: false })}
                        </td>
                        <td className="px-3 py-2 text-right font-bold tabular-nums">
                          {formatMoney(l.invoice_amount, { precision: 2, withCurrency: false })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 self-end text-[13px]">
                <dt className="text-muted-foreground">{t("receipts.net")}</dt>
                <dd className="text-right tabular-nums">{formatMoney(ret.net_total, { precision: 2 })}</dd>
                <dt className="text-muted-foreground">{t("receipts.vatTotal")}</dt>
                <dd className="text-right tabular-nums">{formatMoney(ret.vat_total, { precision: 2 })}</dd>
                <dt className="font-bold">{t("returns.invoiceTotal")}</dt>
                <dd className="text-right font-extrabold tabular-nums">
                  {formatMoney(ret.invoice_total, { precision: 2 })}
                </dd>
              </dl>
              {ret.cancel_reason ? (
                <p className="text-small text-foreground-secondary">
                  {t("cancel.reason")}: {ret.cancel_reason}
                </p>
              ) : null}
            </SheetBody>
            {rights.post && ret.status !== "cancelled" ? (
              <SheetFooter>
                <Button
                  variant="destructive-outline"
                  disabled={!online || acting}
                  onClick={() => setCancelling(true)}
                >
                  <Icon as={X} size="sm" />
                  {t("actions.cancelDoc")}
                </Button>
                {ret.status === "draft" ? (
                  <Button disabled={!online || acting} onClick={() => setConfirmPost(true)}>
                    <Icon as={Check} size="sm" />
                    {t("returns.post")}
                  </Button>
                ) : null}
              </SheetFooter>
            ) : null}
            <ConfirmDialog
              open={confirmPost}
              onOpenChange={setConfirmPost}
              title={t("returns.postConfirm.title")}
              description={t("returns.postConfirm.description", { total: formatMoney(ret.invoice_total) })}
              confirmLabel={t("returns.post")}
              onConfirm={() => {
                setConfirmPost(false);
                post(ret.id)
                  .then((r) => toast.success(t("returns.toast.posted", { number: r.number ?? "" })))
                  .catch(() => undefined);
              }}
            />
            <ReasonDialog
              open={cancelling}
              onOpenChange={setCancelling}
              title={t("returns.cancelTitle")}
              onConfirm={async (reason) => {
                await cancel({ id: ret.id, reason });
                toast.success(t("returns.toast.cancelled"));
              }}
            />
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
