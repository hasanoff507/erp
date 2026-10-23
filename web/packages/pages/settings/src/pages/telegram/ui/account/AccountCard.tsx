/**
 * «Telegram akkaunt» (07 BO-20, mockup Bo20Telegram; US-M18-01, QT-M18-01): the current user's link —
 * «Ulangan» chip, since when, last message and this month's count (`notifications.manage`), «Uzish»;
 * not linked / «Boshqa akkauntni ulash» — the one-time `bot_url` link and code, «Havola 10 daqiqa amal
 * qiladi · HH:mm gacha», «Nusxa olish», «Yangi havola»; the status is polled until the bot binds it.
 * Expired without «Start» — the 07 error banner + «Qayta urinish».
 */
import { useUnit } from "effector-react";
import { Copy, ExternalLink, Link2, RefreshCw, Send, TriangleAlert, Unlink } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime } from "@shared/lib/format";
import {
  Banner,
  Button,
  Card,
  CardTitle,
  ConfirmDialog,
  ErrorState,
  Icon,
  Skeleton,
  StatusChip,
  toast,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  $link,
  $linkError,
  $linkExpired,
  $linking,
  $logSummary,
  $rights,
  $status,
  $statusError,
  hhmm,
  linkStartRequested,
  statusReloadRequested,
  unlinkFx,
} from "../../model/index.ts";
import { useKindText } from "../kind-text.ts";

function LinkPanel() {
  const { t } = useTranslation("settings");
  const [link, expired, linking, start] = useUnit([$link, $linkExpired, $linking, linkStartRequested]);
  if (!link) return null;
  const copy = () => {
    void navigator.clipboard
      ?.writeText(link.bot_url)
      .then(() => toast({ title: t("telegram.account.copied"), tone: "success" }))
      .catch(() => toast({ title: t("telegram.account.copyFailed"), tone: "destructive" }));
  };
  if (expired) {
    return (
      <Banner
        tone="destructive"
        icon={TriangleAlert}
        action={
          <Button size="sm" variant="secondary" disabled={linking} onClick={() => start()}>
            <Icon as={RefreshCw} size="sm" />
            {t("telegram.account.retry")}
          </Button>
        }
      >
        {t("telegram.account.expired")}
      </Banner>
    );
  }
  return (
    <section
      aria-label={t("telegram.account.linkTitle")}
      className="flex flex-col gap-2.5 rounded-xl border border-border bg-muted p-4"
    >
      <h3 className="text-[14px] font-bold">{t("telegram.account.linkTitle")}</h3>
      <p className="text-small text-foreground-secondary">{t("telegram.account.linkHint")}</p>
      <a
        href={link.bot_url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 break-all text-[14px] font-semibold text-primary-strong underline-offset-2 hover:underline"
      >
        <Icon as={ExternalLink} size="sm" />
        {link.bot_url}
      </a>
      <p className="text-[13px]">
        {t("telegram.account.code")}{" "}
        <code
          className="rounded-md bg-card px-2 py-0.5 font-mono text-[13px]"
          data-testid="telegram-link-code"
        >
          {link.link_code}
        </code>
      </p>
      <p className="text-[12px] text-muted-foreground">
        {t("telegram.account.validUntil", { time: hhmm(link.expires_at) })}
      </p>
      <p role="status" aria-live="polite" className="text-[12px] text-info-strong">
        {t("telegram.account.waiting")}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={copy}>
          <Icon as={Copy} size="sm" />
          {t("telegram.account.copy")}
        </Button>
        <Button size="sm" variant="secondary" disabled={linking} onClick={() => start()}>
          <Icon as={RefreshCw} size="sm" />
          {t("telegram.account.newLink")}
        </Button>
      </div>
    </section>
  );
}

export function AccountCard({ online }: { online: boolean }) {
  const { t } = useTranslation("settings");
  const kindText = useKindText();
  const [status, statusError, link, linkError, linking, rights, summary] = useUnit([
    $status,
    $statusError,
    $link,
    $linkError,
    $linking,
    $rights,
    $logSummary,
  ]);
  const [start, reload, unlink] = useUnit([linkStartRequested, statusReloadRequested, unlinkFx]);
  const [confirm, setConfirm] = useState(false);
  const [unlinkError, setUnlinkError] = useState<string | null>(null);

  return (
    <Card className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle className="min-w-0 flex-1">{t("telegram.account.title")}</CardTitle>
        {status ? (
          status.linked ? (
            <StatusChip tone="success">{t("telegram.account.linked")}</StatusChip>
          ) : (
            <StatusChip tone="neutral">{t("telegram.account.notLinked")}</StatusChip>
          )
        ) : null}
      </div>
      <p className="text-small text-foreground-secondary">{t("telegram.account.hint")}</p>

      {!status && statusError ? (
        <ErrorState message={errorText(statusError)} onRetry={reload} />
      ) : !status ? (
        <Skeleton className="h-16 w-full" />
      ) : status.linked ? (
        <dl className="grid gap-x-6 gap-y-1.5 text-[13px] sm:grid-cols-[auto_1fr]">
          <dt className="text-foreground-secondary">{t("telegram.account.since")}</dt>
          <dd className="font-semibold">{status.linked_at ? formatDate(status.linked_at) : "—"}</dd>
          {rights.canManage ? (
            <>
              <dt className="text-foreground-secondary">{t("telegram.account.lastMessage")}</dt>
              <dd className="font-semibold">
                {summary.last
                  ? t("telegram.account.lastMessageValue", {
                      at: formatDateTime(summary.last.created_at),
                      kind: kindText(summary.last.template).title,
                    })
                  : t("telegram.account.noMessages")}
              </dd>
              <dt className="text-foreground-secondary">{t("telegram.account.thisMonth")}</dt>
              <dd className="font-semibold tabular-nums">
                {t("telegram.account.thisMonthValue", {
                  count: summary.sentThisMonth,
                  more: summary.more ? "+" : "",
                })}
              </dd>
            </>
          ) : null}
        </dl>
      ) : null}

      {linkError ? (
        <Banner tone="destructive" icon={TriangleAlert}>
          {errorText(linkError)}
        </Banner>
      ) : null}

      <LinkPanel />

      {status ? (
        <div className="flex flex-wrap gap-2">
          {status.linked ? (
            <>
              <Button variant="secondary" disabled={!online} onClick={() => setConfirm(true)}>
                <Icon as={Unlink} size="sm" />
                {t("telegram.account.unlink")}
              </Button>
              {link ? null : (
                <Button variant="secondary" disabled={!online || linking} onClick={() => start()}>
                  <Icon as={Link2} size="sm" />
                  {t("telegram.account.linkOther")}
                </Button>
              )}
            </>
          ) : link ? null : (
            <Button disabled={!online || linking} onClick={() => start()}>
              <Icon as={Send} size="sm" />
              {t("telegram.account.link")}
            </Button>
          )}
        </div>
      ) : null}

      <ConfirmDialog
        open={confirm}
        onOpenChange={(open) => {
          setConfirm(open);
          if (!open) setUnlinkError(null);
        }}
        title={t("telegram.account.unlinkTitle")}
        description={t("telegram.account.unlinkDescription")}
        confirmLabel={t("telegram.account.unlink")}
        tone="destructive"
        error={unlinkError}
        onConfirm={() =>
          unlink().catch((e: unknown) => {
            setUnlinkError(errorText(e));
            throw e;
          })
        }
      />
    </Card>
  );
}
