/**
 * BO-17 — Xarajatlar (07, route /app/expenses, `expenses.create`; mockup Bo17Xarajatlar).
 * Tabs «Xarajatlar» / «Takrorlanuvchi (N)» / «Toifalar»; due recurring reminders above; the «Yangi
 * xarajat» panel on the right of the list. Offline: view only (cash expenses are recorded at the till,
 * POS-14). useEffect only fires pageMounted (24 §2).
 */
import { useUnit } from "effector-react";
import { CheckCircle2, Hourglass, Info, Plus, WifiOff, X } from "lucide-react";
import { useEffect, useRef } from "react";

import { useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import { $activeBranchId, $branches, ALL_BRANCHES } from "@shared/state/session";
import {
  Banner,
  Button,
  Icon,
  NoPermissionState,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  type Tone,
  type LucideIcon,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  $actionError,
  $activeRulesCount,
  $error,
  $notice,
  $tab,
  $today,
  actionErrorDismissed,
  isExpensesTab,
  noticeDismissed,
  pageMounted,
  tabChanged,
  type Notice,
} from "../../model/index.ts";
import { CategoriesTab } from "../categories/CategoriesTab.tsx";
import { ExpenseForm } from "../form/ExpenseForm.tsx";
import { ExpensesList } from "../list/ExpensesList.tsx";
import { DueReminders } from "../recurring/DueReminders.tsx";
import { RecurringTab } from "../recurring/RecurringTab.tsx";

const NOTICE: Readonly<Record<Notice["kind"], { tone: Tone; icon: LucideIcon }>> = {
  posted: { tone: "success", icon: CheckCircle2 },
  approval: { tone: "awaiting-approval", icon: Hourglass },
  draft: { tone: "info", icon: Info },
  cancelled: { tone: "neutral", icon: Info },
  ruleCreated: { tone: "info", icon: Info },
};

function ExpensesPage() {
  const { t } = useTranslation("finance");
  const canView = useCan({ permission: "expenses.create" });
  const [mounted, onTab, dismissNotice, dismissError] = useUnit([
    pageMounted,
    tabChanged,
    noticeDismissed,
    actionErrorDismissed,
  ]);
  const [tab, today, rulesCount, notice, actionError, error, online, activeBranch, branches] = useUnit([
    $tab,
    $today,
    $activeRulesCount,
    $notice,
    $actionError,
    $error,
    $isOnline,
    $activeBranchId,
    $branches,
  ]);
  const formRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!canView) return;
    const branchId =
      activeBranch && activeBranch !== ALL_BRANCHES
        ? activeBranch
        : branches.length === 1
          ? (branches[0]?.id ?? null)
          : null;
    mounted({ today: dayjs().format("YYYY-MM-DD"), branchId });
    // Only on entry (24 §2).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, canView]);

  if (!canView || error?.status === 403) return <NoPermissionState />;

  const focusForm = () => {
    onTab("expenses");
    formRef.current?.querySelector<HTMLElement>("input, button")?.focus();
  };

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="flex flex-wrap items-center gap-2.5">
        <p className="min-w-0 text-small text-foreground-secondary">{t("expenses.subtitle")}</p>
        <div className="grow" />
        <Button disabled={!online} onClick={focusForm} data-testid="expense-add">
          <Icon as={Plus} size="sm" />
          {t("expenses.add")}
        </Button>
      </div>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("expenses.offline")}
        </Banner>
      )}
      <DueReminders canAct={online} />
      {notice ? (
        <Banner
          tone={NOTICE[notice.kind].tone}
          icon={NOTICE[notice.kind].icon}
          action={
            <Button variant="ghost" size="icon" aria-label={t("shared.close")} onClick={dismissNotice}>
              <Icon as={X} size="sm" />
            </Button>
          }
        >
          <span data-testid="expense-notice">
            {notice.kind === "posted"
              ? notice.number
                ? t("expenses.notice.postedNumber", { number: notice.number })
                : t("expenses.notice.posted")
              : t(`expenses.notice.${notice.kind}`)}
          </span>
        </Banner>
      ) : null}
      {actionError ? (
        <Banner
          tone="destructive"
          icon={Info}
          live="assertive"
          action={
            <Button variant="ghost" size="icon" aria-label={t("shared.close")} onClick={dismissError}>
              <Icon as={X} size="sm" />
            </Button>
          }
        >
          {errorText(actionError)}
        </Banner>
      ) : null}
      <Tabs value={tab} onValueChange={(v) => (isExpensesTab(v) ? onTab(v) : undefined)}>
        <TabsList aria-label={t("expenses.tabs.label")}>
          <TabsTrigger value="expenses">{t("expenses.tabs.expenses")}</TabsTrigger>
          <TabsTrigger value="recurring">{t("expenses.tabs.recurring", { count: rulesCount })}</TabsTrigger>
          <TabsTrigger value="categories">{t("expenses.tabs.categories")}</TabsTrigger>
        </TabsList>
        <TabsContent value="expenses">
          <div className="grid items-start gap-[18px] xl:grid-cols-[minmax(0,1fr)_380px]">
            <ExpensesList canAct={online} />
            <div ref={formRef}>
              <ExpenseForm key={today} disabled={!online} />
            </div>
          </div>
        </TabsContent>
        <TabsContent value="recurring">
          <RecurringTab canAct={online} />
        </TabsContent>
        <TabsContent value="categories">
          <CategoriesTab canAct={online} online={online} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export const Expenses = {
  route: "expenses",
  titleKey: "finance:expenses.title",
  Page: ExpensesPage,
} as const;
