/**
 * BO-16 — Tasdiqlash navbati (07, route /app/approvals; 18 §9.3–§9.5). Who sees it: any approver code of
 * 15 §2.3 (`discount.approve`, `returns.approve`, `debts.approve`, `prices.approve`, `cash.withdraw`,
 * `expenses.approve`, `stock.writeoff`); the server returns only the kinds the user may decide.
 * Status tabs (`?status=`), kind chips with counters (client-side), cards with PIN step-up approve and
 * reason-required reject, «Bugun hal qilinganlar». The pending queue refreshes every 15 s.
 * Offline: view only — deciding needs the network (18 §9.6). useEffect only fires mount/unmount (24 §2).
 */
import { useUnit } from "effector-react";
import { Inbox, WifiOff } from "lucide-react";
import { useEffect, useMemo } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import { $branches, $user } from "@shared/state/session";
import {
  Banner,
  Button,
  EmptyState,
  ErrorState,
  NoPermissionState,
  Skeleton,
  Tabs,
  TabsList,
  TabsTrigger,
  cn,
} from "@shared/ui";

import {
  $cursor,
  $error,
  $kind,
  $kindCounts,
  $moreLoading,
  $pendingCount,
  $requests,
  $status,
  $tab,
  $visible,
  APPROVAL_KINDS,
  QUEUE_TABS,
  isQueueTab,
  kindChanged,
  moreRequested,
  pageMounted,
  pageUnmounted,
  pollingStarted,
  reloadRequested,
  tabChanged,
} from "../../model/index.ts";
import { RequestCard } from "../card/RequestCard.tsx";
import { ResolvedToday } from "../side/ResolvedToday.tsx";

/** 15 §2.3 — approver codes per kind (any of them opens the queue). */
export const APPROVER_CODES = [
  "discount.approve",
  "returns.approve",
  "debts.approve",
  "prices.approve",
  "cash.withdraw",
  "expenses.approve",
  "stock.writeoff",
  "card.manual_entry.approve",
] as const;

function ApprovalsPage() {
  const { t } = useTranslation("settings");
  const canView = useCan({ anyOf: APPROVER_CODES });
  const [mounted, startPolling, unmounted] = useUnit([pageMounted, pollingStarted, pageUnmounted]);
  const [tab, kind, requests, visible, counts, status, error, cursor, moreLoading, online] = useUnit([
    $tab,
    $kind,
    $requests,
    $visible,
    $kindCounts,
    $status,
    $error,
    $cursor,
    $moreLoading,
    $isOnline,
  ]);
  const [onTab, onKind, reload, more] = useUnit([tabChanged, kindChanged, reloadRequested, moreRequested]);
  const [branches, user, pendingCount] = useUnit([$branches, $user, $pendingCount]);
  const branchNames = useMemo(() => new Map(branches.map((b) => [b.id, b.name])), [branches]);

  useEffect(() => {
    if (!canView) return;
    mounted({ today: dayjs().format("YYYY-MM-DD"), now: Date.now() });
    startPolling();
    return () => unmounted();
  }, [mounted, startPolling, unmounted, canView]);

  if (!canView || error?.status === 403) return <NoPermissionState />;

  return (
    <div className="flex flex-col gap-[18px]">
      <p className="text-small text-foreground-secondary">{t("approvals.subtitle")}</p>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("approvals.offline")}
        </Banner>
      )}
      <div className="grid gap-[18px] lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-3.5">
          <Tabs value={tab} onValueChange={(v) => (isQueueTab(v) ? onTab(v) : undefined)}>
            <TabsList aria-label={t("approvals.tabsLabel")}>
              {QUEUE_TABS.map((key) => (
                <TabsTrigger key={key} value={key}>
                  {key === "pending" && pendingCount !== null
                    ? t("approvals.tabs.pendingCount", { count: pendingCount })
                    : t(`approvals.tabs.${key}`)}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <div role="group" aria-label={t("approvals.kindFilter")} className="flex flex-wrap gap-1.5">
            {[null, ...APPROVAL_KINDS].map((k) => {
              const selected = kind === k;
              const n = k === null ? requests.length : counts[k];
              return (
                <button
                  key={k ?? "all"}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => onKind(k)}
                  className={cn(
                    "inline-flex h-9 items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selected
                      ? "border-primary bg-primary-soft text-primary-strong"
                      : "border-border bg-card text-foreground-secondary hover:bg-accent",
                  )}
                >
                  {k === null ? t("approvals.allKinds") : t(`approvals.kinds.${k}`)}
                  <span className="tabular-nums">{n}</span>
                </button>
              );
            })}
          </div>

          {status === "loading" ? (
            <div className="flex flex-col gap-3" aria-busy="true">
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : status === "error" && error ? (
            <ErrorState message={serverErrorText(error)} onRetry={reload} />
          ) : visible.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title={t(tab === "pending" ? "approvals.empty.pending" : "approvals.empty.other")}
              description={tab === "pending" ? t("approvals.empty.pendingHint") : undefined}
            />
          ) : (
            <div className="flex flex-col gap-3">
              {visible.map((r) => (
                <RequestCard
                  key={r.id}
                  request={r}
                  branchName={branchNames.get(r.branch_id) ?? null}
                  own={user?.id === r.requested_by}
                  online={online}
                />
              ))}
            </div>
          )}
          {cursor !== null && status !== "loading" ? (
            <div className="flex justify-center">
              <Button
                variant="secondary"
                disabled={moreLoading}
                aria-busy={moreLoading || undefined}
                onClick={more}
              >
                {t("approvals.loadMore")}
              </Button>
            </div>
          ) : null}
        </div>
        <ResolvedToday />
      </div>
    </div>
  );
}

export const Approvals = {
  route: "approvals",
  titleKey: "settings:approvals.title",
  Page: ApprovalsPage,
} as const;
