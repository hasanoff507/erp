/**
 * Shell-level states (07 "Holatlar"): splash while the session is checked, «Tez orada» for sidebar
 * screens not built yet, 404, and NoPermissionState (403 PERMISSION_DENIED).
 */
import { useUnit } from "effector-react";
import { Construction, Lock, SearchX } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { $sessionUnavailable, sessionCheckRequested } from "@shared/state/session";
import { Button, Card, EmptyState, LogoMark } from "@shared/ui";

import { navItemForPath } from "../sidebar/nav-items.ts";

/**
 * Session check in progress. While the first GET /auth/session keeps failing (network, 5xx) the
 * store retries with backoff; the splash says so and offers an immediate retry.
 */
export function Splash() {
  const { t } = useTranslation();
  const [unavailable, retry] = useUnit([$sessionUnavailable, sessionCheckRequested]);
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-dvh flex-col items-center justify-center gap-3 bg-background"
    >
      <LogoMark size={38} />
      <span className="text-small text-foreground-secondary">
        {unavailable ? t("session.checkFailed") : t("states.loading")}
      </span>
      {unavailable ? (
        <Button variant="secondary" onClick={() => retry()}>
          {t("actions.retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function ComingSoonPage() {
  const { t } = useTranslation();
  const item = navItemForPath(useLocation().pathname);
  return (
    <Card className="p-0">
      <EmptyState
        icon={Construction}
        title={item ? `${t(`nav.items.${item.key}`)} — ${t("placeholder.title")}` : t("placeholder.title")}
        description={t("placeholder.description")}
      />
    </Card>
  );
}

/** NoPermissionState (08). `inline` — inside the back-office layout (sidebar stays usable). */
export function NoPermissionPage({ inline = false }: { inline?: boolean }) {
  const { t } = useTranslation();
  const state = (
    <Card className="p-0" data-testid="no-permission">
      <EmptyState icon={Lock} title={t("noPermission.title")} />
    </Card>
  );
  if (inline) return <div className="flex justify-center p-4">{state}</div>;
  return <div className="flex min-h-dvh items-center justify-center bg-background p-4">{state}</div>;
}

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background p-4">
      <Card className="p-0">
        <EmptyState
          icon={SearchX}
          title={t("notFound.title")}
          action={
            <Button asChild variant="secondary" className="mt-2">
              <Link to="/">{t("notFound.action")}</Link>
            </Button>
          }
        />
      </Card>
    </div>
  );
}

/** Full-page «Tez orada» for routes outside the back-office layout (e.g. /onboarding). */
export function StandaloneComingSoonPage() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background p-4">
      <Card className="p-0">
        <EmptyState
          icon={Construction}
          title={t("placeholder.title")}
          description={t("placeholder.description")}
          action={
            <Button asChild variant="secondary" className="mt-2">
              <Link to="/login">{t("actions.back")}</Link>
            </Button>
          }
        />
      </Card>
    </div>
  );
}

export { isChunkLoadError, RouteErrorPage } from "./RouteErrorPage.tsx";
