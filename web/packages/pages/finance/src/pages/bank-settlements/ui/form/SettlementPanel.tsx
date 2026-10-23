/**
 * BO-24 document panel (07 BO-24 «Forma», routes `/new` and `/:id`): a new or draft settlement is a form
 * (branch, bank date, method, period, bank ref, gross with the transit-balance suggestion, commission with
 * its share, variance — collection only, net = gross − commission + variance, statement file, comment) with
 * «Saqlash» (`Ctrl+S`; POST / PATCH with `version`), «O'tkazish» (`Ctrl+Enter`; confirm «Bank hisobiga
 * {net} o'tkaziladi, komissiya {commission} xarajatga yoziladi»), «Bekor qilish» (reason ≥ 10). A posted /
 * cancelled one is read-only with its ledger lines (storno rows marked). Posting preview = 13 §2.18a.
 */
import { useUnit } from "effector-react";
import { CircleAlert, Send, X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { toApiError, type ApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime, formatMoney } from "@shared/lib/format";
import { $branches } from "@shared/state/session";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  ErrorState,
  FormField,
  Icon,
  Input,
  Kbd,
  MoneyInput,
  SimpleSelect,
  Skeleton,
  StatusChip,
  Textarea,
} from "@shared/ui";

import { AttachmentField } from "#/shared/ui/AttachmentField.tsx";
import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";

import {
  $busy,
  $defaultBranchId,
  $detail,
  $detailError,
  $detailStatus,
  $today,
  $transit,
  BANK_REF_MAX,
  CANCEL_MAX,
  CANCEL_MIN,
  COMMENT_MAX,
  METHODS,
  cancelSettlementFx,
  commissionPct,
  createSettlementFx,
  detailReloadRequested,
  emptyBankForm,
  formOf,
  isMethod,
  isPatchEmpty,
  netAmount,
  postSettlementFx,
  previewLines,
  toCreateBody,
  toPatchBody,
  transitFor,
  updateSettlementFx,
  validateBankForm,
  type BankForm,
  type BankFormErrors,
  type BankFormField,
  type SettlementDetail,
} from "../../model/index.ts";

const money2 = (v: string) => formatMoney(v, { precision: 2 });

const SERVER_FIELDS: Readonly<Record<string, BankFormField>> = {
  branch_id: "branchId",
  doc_date: "docDate",
  method: "method",
  settled_from: "settledFrom",
  settled_to: "settledTo",
  gross_amount: "gross",
  commission_amount: "commission",
  variance_amount: "variance",
  bank_ref: "bankRef",
  comment: "comment",
};

export interface SettlementPanelProps {
  id: string;
  canAct: boolean;
  onClose: () => void;
  onOpen: (id: string) => void;
}

export function SettlementPanel({ id, canAct, onClose, onOpen }: SettlementPanelProps) {
  const [detail, status, error, today, defaultBranch, branches] = useUnit([
    $detail,
    $detailStatus,
    $detailError,
    $today,
    $defaultBranchId,
    $branches,
  ]);
  const reload = useUnit(detailReloadRequested);

  if (id === "new") {
    return (
      <DocForm
        key="new"
        detail={null}
        initial={emptyBankForm(
          today,
          defaultBranch ?? (branches.length === 1 ? (branches[0]?.id ?? null) : null),
        )}
        canAct={canAct}
        onClose={onClose}
        onOpen={onOpen}
      />
    );
  }
  if (!detail || detail.id !== id) {
    return (
      <Card className="flex flex-col gap-3">
        {status === "error" && error ? (
          <ErrorState message={serverErrorText(error)} onRetry={reload} />
        ) : (
          <Skeleton className="h-64 w-full" />
        )}
      </Card>
    );
  }
  if (detail.status === "draft") {
    return (
      <DocForm
        key={`${detail.id}:${detail.version}`}
        detail={detail}
        initial={formOf(detail)}
        canAct={canAct}
        onClose={onClose}
        onOpen={onOpen}
      />
    );
  }
  return <DocView detail={detail} canAct={canAct} onClose={onClose} />;
}

function Header({ detail, onClose }: { detail: SettlementDetail | null; onClose: () => void }) {
  const { t } = useTranslation("finance");
  return (
    <div className="flex items-start gap-2">
      <div className="min-w-0 flex-1">
        <h2 id="bank-doc-title" className="text-[16px] font-extrabold">
          {detail?.number ?? t("bank.form.newTitle")}
        </h2>
        <p className="text-[12px] text-foreground-secondary">
          {detail ? t(`bank.status.${detail.status}`) : t("bank.form.numberOnPost")}
          {detail?.source === "statement_import" ? ` · ${t("bank.list.imported")}` : ""}
        </p>
      </div>
      <Button variant="ghost" size="icon" aria-label={t("shared.close")} onClick={onClose}>
        <Icon as={X} size="sm" />
      </Button>
    </div>
  );
}

function Lines({
  lines,
}: {
  lines: { key: string; dt: string; kt: string; amount: string; storno?: boolean }[];
}) {
  const { t } = useTranslation("finance");
  if (lines.length === 0) return null;
  return (
    <table className="w-full text-[12px]" aria-label={t("bank.form.lines")} data-testid="bank-lines">
      <thead>
        <tr className="text-left text-foreground-secondary">
          <th className="py-1 font-semibold">Dt</th>
          <th className="py-1 font-semibold">Kt</th>
          <th className="py-1 text-right font-semibold">{t("bank.form.amount")}</th>
        </tr>
      </thead>
      <tbody>
        {lines.map((l) => (
          <tr key={l.key} className="border-t border-border align-top">
            <td className="py-1 pr-2">
              <span className="font-bold tabular-nums">{l.dt}</span>{" "}
              <span className="text-foreground-secondary">{t(`accounts.${l.dt}`, { defaultValue: "" })}</span>
            </td>
            <td className="py-1 pr-2">
              <span className="font-bold tabular-nums">{l.kt}</span>{" "}
              <span className="text-foreground-secondary">{t(`accounts.${l.kt}`, { defaultValue: "" })}</span>
            </td>
            <td className="py-1 text-right tabular-nums">
              {l.storno ? <StatusChip tone="destructive">{t("bank.form.storno")}</StatusChip> : null}{" "}
              {money2(l.amount)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function fieldErrors(error: ApiError, exceeds: (amount: string) => string): BankFormErrors {
  const out: BankFormErrors = {};
  for (const d of error.details) {
    const field = SERVER_FIELDS[d.field.replace(/^body\./, "")];
    if (!field) continue;
    const available = error.params.available;
    out[field] =
      d.messageKey === "validation.bank_settlement_exceeds_in_transit" && typeof available === "string"
        ? exceeds(money2(available))
        : d.messageKey;
  }
  return out;
}

interface DocFormProps {
  detail: SettlementDetail | null;
  initial: BankForm;
  canAct: boolean;
  onClose: () => void;
  onOpen: (id: string) => void;
}

function DocForm({ detail, initial, canAct, onClose, onOpen }: DocFormProps) {
  const { t } = useTranslation("finance");
  const [today, transit, branches, busy] = useUnit([$today, $transit, $branches, $busy]);
  const [create, update, post, cancel] = useUnit([
    createSettlementFx,
    updateSettlementFx,
    postSettlementFx,
    cancelSettlementFx,
  ]);
  const [form, setForm] = useState<BankForm>(initial);
  const [errors, setErrors] = useState<BankFormErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [postTarget, setPostTarget] = useState<string | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const isNew = detail === null;
  const disabled = !canAct || busy;

  const set = <K extends keyof BankForm>(key: K, value: BankForm[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };
  const available = transitFor(transit?.items ?? [], form.branchId, form.method);
  const net = netAmount(form);
  const pct = commissionPct(form.gross, form.commission);
  const exceeds = (amount: string) => t("bank.form.exceedsTransit", { amount });

  const fail = (e: unknown) => {
    const error = toApiError(e);
    const found = fieldErrors(error, exceeds);
    setErrors(found);
    setFailure(Object.keys(found).length === 0 ? serverErrorText(error) : null);
  };

  /** Validates and saves; returns the document id (new or existing), or null when nothing could be saved. */
  const save = async (): Promise<string | null> => {
    const found = validateBankForm(form, today);
    setErrors(found);
    setFailure(null);
    if (Object.keys(found).length > 0) return null;
    try {
      if (isNew) return (await create(toCreateBody(form))).id;
      const patch = toPatchBody(form, detail);
      if (!isPatchEmpty(patch)) await update({ id: detail.id, body: patch });
      return detail.id;
    } catch (e) {
      fail(e);
      return null;
    }
  };

  const onSave = async () => {
    if (disabled) return;
    const id = await save();
    if (id && isNew) onOpen(id);
  };
  const onPost = async () => {
    if (disabled) return;
    const id = await save();
    if (id) {
      setPostError(null);
      setPostTarget(id);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    if (e.key === "s" || e.key === "S") {
      e.preventDefault();
      void onSave();
    } else if (e.key === "Enter") {
      e.preventDefault();
      void onPost();
    }
  };

  const err = (f: BankFormField) => errors[f] ?? null;

  return (
    <Card
      role="region"
      aria-labelledby="bank-doc-title"
      className="flex flex-col gap-3"
      onKeyDown={onKeyDown}
    >
      <Header detail={detail} onClose={onClose} />
      <div className="grid gap-3 sm:grid-cols-2">
        <FormField label={t("bank.form.branch")} required error={err("branchId")}>
          <SimpleSelect
            options={branches.map((b) => ({ value: b.id, label: b.name }))}
            value={form.branchId || undefined}
            placeholder={t("bank.form.branchPlaceholder")}
            disabled={disabled || !isNew}
            onValueChange={(v) => set("branchId", v)}
          />
        </FormField>
        <FormField label={t("bank.form.docDate")} required error={err("docDate")}>
          <Input
            type="date"
            value={form.docDate}
            max={today}
            disabled={disabled || !isNew}
            onChange={(e) => set("docDate", e.target.value)}
          />
        </FormField>
        <FormField label={t("bank.form.method")} required error={err("method")}>
          <SimpleSelect
            options={METHODS.map((m) => ({ value: m, label: t(`bank.methods.${m}`) }))}
            value={form.method ?? undefined}
            placeholder={t("bank.form.methodPlaceholder")}
            disabled={disabled || !isNew}
            onValueChange={(v) => set("method", isMethod(v) ? v : null)}
          />
        </FormField>
        <FormField label={t("bank.form.bankRef")} optional error={err("bankRef")}>
          <Input
            value={form.bankRef}
            maxLength={BANK_REF_MAX}
            disabled={disabled}
            onChange={(e) => set("bankRef", e.target.value)}
          />
        </FormField>
        <FormField label={t("bank.form.settledFrom")} required error={err("settledFrom")}>
          <Input
            type="date"
            value={form.settledFrom}
            disabled={disabled}
            onChange={(e) => set("settledFrom", e.target.value)}
          />
        </FormField>
        <FormField label={t("bank.form.settledTo")} required error={err("settledTo")}>
          <Input
            type="date"
            value={form.settledTo}
            disabled={disabled}
            onChange={(e) => set("settledTo", e.target.value)}
          />
        </FormField>
      </div>
      <FormField
        label={t("bank.form.gross")}
        required
        error={err("gross")}
        hint={
          available ? (
            <span className="flex flex-wrap items-center gap-1.5">
              {t("bank.form.available", { amount: money2(available) })}
              {disabled ? null : (
                <button
                  type="button"
                  className="font-semibold text-primary underline-offset-2 hover:underline"
                  onClick={() => set("gross", available)}
                >
                  {t("bank.form.useAvailable")}
                </button>
              )}
            </span>
          ) : undefined
        }
      >
        <MoneyInput
          precision={2}
          value={form.gross}
          disabled={disabled}
          data-testid="bank-gross"
          onChange={(v) => set("gross", v)}
        />
      </FormField>
      <div className="grid gap-3 sm:grid-cols-2">
        <FormField
          label={t("bank.form.commission", { account: form.method === "collection" ? "9410" : "9430" })}
          required
          error={err("commission")}
          hint={pct ? t("bank.form.commissionPct", { pct }) : undefined}
        >
          <MoneyInput
            precision={2}
            value={form.commission}
            disabled={disabled}
            data-testid="bank-commission"
            onChange={(v) => set("commission", v)}
          />
        </FormField>
        <FormField
          label={t("bank.form.variance")}
          optional
          error={err("variance")}
          hint={t("bank.form.varianceHint")}
        >
          <MoneyInput
            precision={2}
            allowNegative
            value={form.method === "collection" ? form.variance : "0.00"}
            disabled={disabled || form.method !== "collection"}
            onChange={(v) => set("variance", v)}
          />
        </FormField>
      </div>
      <div className="flex items-baseline justify-between rounded-xl bg-accent px-3 py-2.5">
        <span className="text-[13px] font-semibold">{t("bank.form.net")}</span>
        <span className="flex flex-col items-end">
          <output className="text-[18px] font-extrabold tabular-nums" data-testid="bank-net">
            {money2(net)}
          </output>
          <span className="text-[11px] text-foreground-secondary tabular-nums">
            {t("bank.form.netFormula", {
              gross: money2(form.gross || "0"),
              commission: money2(form.commission || "0"),
              variance: money2(form.method === "collection" ? form.variance || "0" : "0"),
            })}
          </span>
        </span>
      </div>
      {isNew ? (
        <FormField label={t("bank.form.attachment")} optional>
          {(a11y) => (
            <AttachmentField
              id={a11y.id}
              kind="import"
              value={form.attachment}
              onChange={(v) => set("attachment", v)}
              disabled={disabled}
              title={t("bank.form.attachmentHint")}
            />
          )}
        </FormField>
      ) : null}
      <FormField label={t("bank.form.comment")} optional error={err("comment")}>
        <Textarea
          value={form.comment}
          rows={2}
          maxLength={COMMENT_MAX}
          disabled={disabled}
          onChange={(e) => set("comment", e.target.value)}
        />
      </FormField>
      <div className="flex flex-col gap-1">
        <h3 className="text-[13px] font-bold">{t("bank.form.preview")}</h3>
        <Lines lines={previewLines(form).map((l, i) => ({ ...l, key: String(i) }))} />
      </div>
      {failure ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          {failure}
        </Banner>
      ) : null}
      {canAct ? (
        <div className="flex flex-wrap justify-end gap-2">
          {isNew ? null : (
            <Button variant="outline" disabled={disabled} onClick={() => setCancelling(true)}>
              {t("bank.actions.cancel")}
            </Button>
          )}
          <Button variant="outline" disabled={disabled} onClick={() => void onSave()} data-testid="bank-save">
            {t("bank.actions.save")}
            <Kbd keys="Ctrl+S" />
          </Button>
          <Button disabled={disabled} onClick={() => void onPost()} data-testid="bank-post">
            <Icon as={Send} size="sm" />
            {t("bank.actions.post")}
            <Kbd keys="Ctrl+Enter" inverted />
          </Button>
        </div>
      ) : null}
      <ConfirmDialog
        open={postTarget !== null}
        onOpenChange={(open) => {
          if (open) return;
          const created = isNew ? postTarget : null;
          setPostTarget(null);
          if (created) onOpen(created);
        }}
        title={t("bank.post.title")}
        description={t("bank.post.description", {
          net: money2(net),
          commission: money2(form.commission || "0"),
        })}
        confirmLabel={t("bank.actions.post")}
        cancelLabel={t("shared.back")}
        error={postError}
        onConfirm={async () => {
          if (!postTarget) return;
          try {
            await post(postTarget);
            if (isNew) onOpen(postTarget);
          } catch (e) {
            const error = toApiError(e);
            setPostError(serverErrorText(error));
            setErrors(fieldErrors(error, exceeds));
            throw e;
          }
        }}
      />
      {detail ? (
        <ReasonDialog
          open={cancelling}
          onOpenChange={setCancelling}
          title={t("bank.cancel.title")}
          description={t("bank.cancel.draft")}
          minLength={CANCEL_MIN}
          maxLength={CANCEL_MAX}
          onConfirm={async (reason) => {
            await cancel({ id: detail.id, reason });
            setCancelling(false);
          }}
        />
      ) : null}
    </Card>
  );
}

function DocView({
  detail,
  canAct,
  onClose,
}: {
  detail: SettlementDetail;
  canAct: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation("finance");
  const [branches, busy] = useUnit([$branches, $busy]);
  const cancel = useUnit(cancelSettlementFx);
  const [cancelling, setCancelling] = useState(false);
  const row = (label: string, value: string) => (
    <>
      <dt className="text-foreground-secondary">{label}</dt>
      <dd className="text-right font-semibold tabular-nums">{value}</dd>
    </>
  );
  return (
    <Card role="region" aria-labelledby="bank-doc-title" className="flex flex-col gap-3">
      <Header detail={detail} onClose={onClose} />
      <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-[13px]" data-testid="bank-doc">
        {row(t("bank.form.branch"), branches.find((b) => b.id === detail.branch_id)?.name ?? "—")}
        {row(t("bank.form.docDate"), formatDate(detail.doc_date))}
        {row(t("bank.form.method"), t(`bank.methods.${detail.method}`))}
        {row(
          t("bank.list.columns.period"),
          `${formatDate(detail.settled_from)}–${formatDate(detail.settled_to)}`,
        )}
        {detail.bank_ref ? row(t("bank.form.bankRef"), detail.bank_ref) : null}
        {row(t("bank.list.columns.gross"), money2(detail.gross_amount))}
        {row(t("bank.list.columns.commission"), money2(detail.commission_amount))}
        {row(t("bank.list.columns.variance"), money2(detail.variance_amount))}
        {row(t("bank.form.net"), money2(detail.net_amount))}
        {detail.posted_at ? row(t("bank.form.postedAt"), formatDateTime(detail.posted_at)) : null}
        {detail.cancelled_at ? row(t("bank.form.cancelledAt"), formatDateTime(detail.cancelled_at)) : null}
      </dl>
      {detail.cancel_reason ? (
        <p className="text-[12px] text-foreground-secondary">
          {t("bank.form.cancelReason")}: «{detail.cancel_reason}»
        </p>
      ) : null}
      {detail.comment ? <p className="text-[12px]">{detail.comment}</p> : null}
      <div className="flex flex-col gap-1">
        <h3 className="text-[13px] font-bold">{t("bank.form.lines")}</h3>
        <Lines
          lines={detail.ledger_entries.map((l) => ({
            key: l.id,
            dt: l.account_dt,
            kt: l.account_kt,
            amount: l.amount,
            storno: l.reversal_of_id !== null,
          }))}
        />
      </div>
      {canAct && detail.status === "posted" ? (
        <div className="flex justify-end">
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => setCancelling(true)}
            data-testid="bank-cancel"
          >
            {t("bank.actions.cancel")}
          </Button>
        </div>
      ) : null}
      <ReasonDialog
        open={cancelling}
        onOpenChange={setCancelling}
        title={t("bank.cancel.title")}
        description={t("bank.cancel.posted")}
        minLength={CANCEL_MIN}
        maxLength={CANCEL_MAX}
        onConfirm={async (reason) => {
          await cancel({ id: detail.id, reason });
          setCancelling(false);
        }}
      />
    </Card>
  );
}
