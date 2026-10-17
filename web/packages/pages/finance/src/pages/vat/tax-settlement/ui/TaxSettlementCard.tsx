/**
 * «Soliq hisob-kitobi (ST)» card of BO-07 (07 BO-07 lines «Soliq hisob-kitobi (ST)» bloki; 20 #8a–#8d):
 * status, document, kind, period, base, rate, amount, posting (Dt/Kt with account names); «Qoralama
 * hisoblash» (`accounting.post`), «O'tkazish» (confirm «{davr} uchun {amount} so'm provodka yoziladi»;
 * the server recomputes), «Bekor qilish» (reason). Months only; a turnover-tax payer settles per branch.
 */
import { useUnit } from "effector-react";
import { Calculator, CheckCircle2, CircleAlert, Hourglass, Send, X } from "lucide-react";
import { useState } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import { $activeBranchId, $branches, ALL_BRANCHES } from "@shared/state/session";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  FormField,
  Icon,
  SimpleSelect,
  Skeleton,
  StatusChip,
  type Tone,
} from "@shared/ui";

import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";

import { $period } from "../../model/index.ts";
import {
  $isMonthPeriod,
  $lastPosted,
  $sortedSettlements,
  $stActionError,
  $stBusy,
  $stError,
  $stStatus,
  $taxKinds,
  cancelSettlementFx,
  createBody,
  createSettlementFx,
  hasLiveFor,
  postSettlementFx,
  postingOf,
  stNoticeDismissed,
  stReloadRequested,
  type TaxKind,
  type TaxSettlement,
} from "../model/index.ts";

const STATUS_TONE: Readonly<Record<TaxSettlement["status"], Tone>> = {
  draft: "neutral",
  posted: "success",
  cancelled: "destructive",
};
const money2 = (v: string) => formatMoney(v, { precision: 2 });

export function TaxSettlementCard({ monthLabel }: { monthLabel: (period: string) => string }) {
  const { t } = useTranslation("finance");
  const canPost = useCan({ permission: "accounting.post" });
  const [
    period,
    isMonth,
    list,
    status,
    error,
    busy,
    lastPosted,
    actionError,
    online,
    activeBranch,
    branches,
    kinds,
  ] = useUnit([
    $period,
    $isMonthPeriod,
    $sortedSettlements,
    $stStatus,
    $stError,
    $stBusy,
    $lastPosted,
    $stActionError,
    $isOnline,
    $activeBranchId,
    $branches,
    $taxKinds,
  ]);
  const [create, post, cancel, reload, dismiss] = useUnit([
    createSettlementFx,
    postSettlementFx,
    cancelSettlementFx,
    stReloadRequested,
    stNoticeDismissed,
  ]);
  const topbarBranch = activeBranch && activeBranch !== ALL_BRANCHES ? activeBranch : null;
  const [pickedBranch, setPickedBranch] = useState<string | null>(null);
  const branchId = pickedBranch ?? topbarBranch ?? (branches.length === 1 ? (branches[0]?.id ?? null) : null);
  const [posting, setPosting] = useState<TaxSettlement | null>(null);
  const [cancelling, setCancelling] = useState<TaxSettlement | null>(null);
  const canAct = canPost && online;
  const needsBranch = kinds.includes("turnover_tax") && branches.length > 1;
  const canCreate = (k: TaxKind) =>
    canAct && isMonth && !hasLiveFor(list, k, branchId) && (k === "vat_offset" || branchId !== null);
  const branchName = (id: string) => branches.find((b) => b.id === id)?.name ?? "—";

  return (
    <Card
      role="region"
      aria-labelledby="st-title"
      className="flex flex-col gap-3"
      data-testid="tax-settlement"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="st-title" className="text-[15px] font-bold">
          {t("vat.settlement.title")}
        </h2>
        {kinds.map((k) => (
          <StatusChip key={k} tone="info">
            {t(`vat.settlement.kinds.${k}`)}
          </StatusChip>
        ))}
      </div>
      {(kinds.length > 0 ? kinds : ["vat_offset" as const]).map((k) => (
        <p key={k} className="text-small text-foreground-secondary">
          {k === "turnover_tax" ? t("vat.settlement.turnoverHint") : t("vat.settlement.vatHint")}
        </p>
      ))}

      {!isMonth ? (
        <p className="text-small text-foreground-secondary">{t("vat.settlement.monthOnly")}</p>
      ) : status === "loading" && list.length === 0 ? (
        <Skeleton className="h-20 w-full" />
      ) : status === "error" && error ? (
        <Banner tone="destructive" icon={CircleAlert}>
          {serverErrorText(error)}{" "}
          <button type="button" className="font-semibold underline" onClick={reload}>
            {t("vat.settlement.retry")}
          </button>
        </Banner>
      ) : list.length === 0 ? (
        <p className="text-small text-foreground-secondary">
          {t("vat.settlement.none", { period: monthLabel(period) })}
        </p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {list.map((s) => {
            const p = postingOf(s);
            return (
              <li
                key={s.id}
                data-testid="st-row"
                className="flex flex-col gap-2 rounded-xl border border-border bg-background p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <StatusChip tone={STATUS_TONE[s.status]} dot>
                    {t(`vat.settlement.status.${s.status}`)}
                  </StatusChip>
                  <span className="font-bold tabular-nums">{s.number ?? t("vat.settlement.noNumber")}</span>
                  {s.tax_kind === "turnover_tax" ? (
                    <span className="text-[12px] text-foreground-secondary">{branchName(s.branch_id)}</span>
                  ) : null}
                </div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[13px] sm:grid-cols-4">
                  <div>
                    <dt className="text-[12px] text-foreground-secondary">{t("vat.settlement.period")}</dt>
                    <dd>{monthLabel(s.period)}</dd>
                  </div>
                  <div>
                    <dt className="text-[12px] text-foreground-secondary">{t("vat.settlement.base")}</dt>
                    <dd className="tabular-nums">{money2(s.base_amount)}</dd>
                  </div>
                  <div>
                    <dt className="text-[12px] text-foreground-secondary">{t("vat.settlement.rate")}</dt>
                    <dd className="tabular-nums">{s.rate === null ? "—" : formatPercent(s.rate)}</dd>
                  </div>
                  <div>
                    <dt className="text-[12px] text-foreground-secondary">{t("vat.settlement.amount")}</dt>
                    <dd className="font-extrabold tabular-nums" data-testid="st-amount">
                      {money2(s.amount)}
                    </dd>
                  </div>
                </dl>
                <p className="text-[12px] text-foreground-secondary">
                  {t("vat.settlement.posting", {
                    dt: p.dt,
                    dtName: t(`accounts.${p.dt}`, { defaultValue: "" }),
                    kt: p.kt,
                    ktName: t(`accounts.${p.kt}`, { defaultValue: "" }),
                  })}
                </p>
                {s.cancel_reason ? (
                  <p className="text-[12px] text-foreground-secondary">
                    {t("vat.settlement.cancelReason", { reason: s.cancel_reason })}
                  </p>
                ) : null}
                {canAct && s.status !== "cancelled" ? (
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button variant="outline" size="sm" disabled={busy} onClick={() => setCancelling(s)}>
                      {t("vat.settlement.cancel")}
                    </Button>
                    {s.status === "draft" ? (
                      <Button size="sm" disabled={busy} onClick={() => setPosting(s)} data-testid="st-post">
                        <Icon as={Send} size="sm" />
                        {t("vat.settlement.post")}
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      {lastPosted ? (
        <Banner
          tone={lastPosted.recalculated ? "warning" : "success"}
          icon={lastPosted.recalculated ? Hourglass : CheckCircle2}
          action={
            <Button variant="ghost" size="icon" aria-label={t("vat.settlement.close")} onClick={dismiss}>
              <Icon as={X} size="sm" />
            </Button>
          }
        >
          <span data-testid="st-posted">
            {lastPosted.recalculated
              ? t("vat.settlement.recalculated", {
                  number: lastPosted.number ?? "",
                  amount: money2(lastPosted.amount),
                })
              : t("vat.settlement.posted", { number: lastPosted.number ?? "" })}
          </span>
        </Banner>
      ) : null}
      {actionError ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          {serverErrorText(actionError)}
        </Banner>
      ) : null}

      {canAct && isMonth && kinds.length > 0 ? (
        <div className="flex flex-wrap items-end justify-end gap-2">
          {needsBranch ? (
            <FormField label={t("vat.settlement.branch")} className="w-52">
              <SimpleSelect
                options={branches.map((b) => ({ value: b.id, label: b.name }))}
                value={branchId ?? undefined}
                placeholder={t("vat.settlement.branchPlaceholder")}
                onValueChange={setPickedBranch}
              />
            </FormField>
          ) : null}
          {kinds.map((k) => (
            <Button
              key={k}
              disabled={!canCreate(k) || busy}
              onClick={() => void create(createBody(k, period, branchId)).catch(() => undefined)}
              data-testid={`st-create-${k}`}
            >
              <Icon as={Calculator} size="sm" />
              {kinds.length > 1
                ? t("vat.settlement.createKind", { kind: t(`vat.settlement.kinds.${k}`) })
                : t("vat.settlement.create")}
            </Button>
          ))}
        </div>
      ) : null}

      <ConfirmDialog
        open={posting !== null}
        onOpenChange={(open) => (open ? undefined : setPosting(null))}
        title={t("vat.settlement.postTitle")}
        description={
          posting
            ? t("vat.settlement.postDescription", {
                period: monthLabel(posting.period),
                amount: money2(posting.amount),
              })
            : undefined
        }
        confirmLabel={t("vat.settlement.post")}
        cancelLabel={t("vat.settlement.back")}
        onConfirm={async () => {
          if (!posting) return;
          const id = posting.id;
          setPosting(null);
          await post(id).catch(() => undefined);
        }}
      />
      <ReasonDialog
        open={cancelling !== null}
        onOpenChange={(open) => (open ? undefined : setCancelling(null))}
        title={t("vat.settlement.cancelTitle")}
        description={cancelling?.status === "posted" ? t("vat.settlement.cancelPosted") : undefined}
        onConfirm={async (reason) => {
          if (!cancelling) return;
          await cancel({ id: cancelling.id, reason });
          setCancelling(null);
        }}
      />
    </Card>
  );
}
