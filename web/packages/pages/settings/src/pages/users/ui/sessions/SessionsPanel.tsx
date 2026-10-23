import { useUnit } from "effector-react";
import { LogOut, MonitorSmartphone } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/date";
import { Button, EmptyState, ErrorState, Icon, Skeleton, StatusChip, toast } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $sessions,
  $sessionsError,
  $sessionsUserId,
  fetchSessionsFx,
  revokeAllSessionsFx,
  revokeSessionFx,
  sessionsReloadRequested,
  type Session,
} from "../../model/index.ts";

/**
 * Active login sessions of one user (US-M13-07, 14 §18.2): device kind, sign-in time, last activity,
 * IP; "Tugatish" ends exactly one session (the others stay), "Barcha seanslarni tugatish" ends all.
 */
export function SessionsPanel({ showRevokeAll = true }: { showRevokeAll?: boolean }) {
  const { t } = useTranslation("settings");
  const [userId, sessions, error, loading, reload, revokeOne, revokeAll, revokingAll] = useUnit([
    $sessionsUserId,
    $sessions,
    $sessionsError,
    fetchSessionsFx.pending,
    sessionsReloadRequested,
    revokeSessionFx,
    revokeAllSessionsFx,
    revokeAllSessionsFx.pending,
  ]);
  const online = useOnline();
  const [busyId, setBusyId] = useState<string | null>(null);

  if (!userId) return null;

  const onRevoke = async (session: Session) => {
    setBusyId(session.session_id);
    try {
      await revokeOne({ userId, sessionId: session.session_id });
      toast.success(t("users.sessions.revoked"));
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const onRevokeAll = async () => {
    try {
      const result = await revokeAll(userId);
      toast.success(t("users.sessions.revokedAll", { count: result.sessions_revoked }));
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  let body;
  if (error) {
    body = <ErrorState message={errorText(error)} onRetry={reload} className="py-6" />;
  } else if (loading && sessions.length === 0) {
    body = (
      <div className="flex flex-col gap-2" aria-busy="true">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
    );
  } else if (sessions.length === 0) {
    body = <EmptyState icon={MonitorSmartphone} title={t("users.sessions.empty")} className="py-6" />;
  } else {
    body = (
      <ul className="flex flex-col divide-y divide-divider" aria-label={t("users.sessions.listLabel")}>
        {sessions.map((s) => (
          <li key={s.session_id} className="flex flex-wrap items-center gap-3 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2 text-[14px] font-bold">
                {t(sessionKindKey(s.device_kind))}
                {s.current ? <StatusChip tone="info">{t("users.sessions.current")}</StatusChip> : null}
              </p>
              <p className="truncate text-[12px] text-muted-foreground">
                {[s.user_agent, s.ip].filter(Boolean).join(" · ")}
              </p>
              <p className="text-[12px] text-foreground-secondary">
                {t("users.sessions.times", {
                  created: formatDateTime(s.created_at),
                  seen: formatDateTime(s.last_seen_at),
                })}
              </p>
            </div>
            <Button
              variant="destructive-outline"
              size="sm"
              disabled={!online || s.current || busyId === s.session_id}
              aria-label={t("users.sessions.revokeOneLabel", { device: t(sessionKindKey(s.device_kind)) })}
              onClick={() => void onRevoke(s)}
            >
              {t("users.sessions.revokeOne")}
            </Button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <section className="flex flex-col gap-2.5" aria-label={t("users.sessions.title")}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[15px] font-bold">{t("users.sessions.title")}</h3>
        {showRevokeAll && sessions.length > 0 ? (
          <Button
            variant="destructive-outline"
            size="sm"
            disabled={!online || revokingAll}
            onClick={() => void onRevokeAll()}
          >
            <Icon as={LogOut} size="sm" />
            {t("users.sessions.revokeAll")}
          </Button>
        ) : null}
      </div>
      {body}
    </section>
  );
}

type SessionKindKey = "users.sessions.kind.web" | "users.sessions.kind.android" | "users.sessions.kind.other";

function sessionKindKey(kind: string | null): SessionKindKey {
  if (kind === "android") return "users.sessions.kind.android";
  if (kind === "web" || kind === null) return "users.sessions.kind.web";
  return "users.sessions.kind.other";
}
