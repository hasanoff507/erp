/**
 * BO-01 entry action (07 "Amallar" → KIRISH, 14 §2.1). The SPA holds no password form: «Kirish» is a
 * plain link, so the browser itself (not an XHR) goes to `GET /auth/login/start?return_to=…`; the BFF
 * keeps state + PKCE server-side and redirects to the server-rendered AS page (`/oauth/authorize`),
 * where the phone + password form lives (the only credential form). The callback sets the
 * HttpOnly cookie and returns to `return_to`, or to `/login?error=<reason>`.
 * «Google bilan kirish» is the same kind of full-page link to `GET /auth/google/start` (14 §2.2), shown
 * only when the runtime config enables it (`googleEnabled`);
 * a new Google user comes back to /onboarding?method=google. «Parolni unutdim» → /recover,
 * «Taklif kodi bor» → /invite (SPA pages of @pages/billing).
 */
import { useUnit } from "effector-react";
import { KeyRound, LogIn, Send, ShieldCheck, TriangleAlert, WifiOff } from "lucide-react";
import { Link } from "react-router-dom";

import { loginStartUrl } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { googleStartUrl } from "@shared/lib/runtime-config";
import { $isOnline } from "@shared/state/network";
import { Banner, Button, Icon, Kbd } from "@shared/ui";

import { isOnboardingReason, type LoginErrorReason } from "../../model/index.ts";

export interface LoginStartProps {
  returnTo: string;
  tenantId: string | null;
  errorReason: LoginErrorReason | null;
}

export function LoginStart({ returnTo, tenantId, errorReason }: LoginStartProps) {
  const { t } = useTranslation("auth");
  const { t: to } = useTranslation("onboarding");
  const online = useUnit($isOnline);
  const href = loginStartUrl({ returnTo, tenantId });
  // `null` when this deployment has no Google sign-in (runtime config `googleEnabled`) → no button.
  const googleHref = googleStartUrl({ returnTo, tenantId });

  return (
    <>
      {!online ? (
        <Banner tone="warning" icon={WifiOff}>
          {t("login.offline")}
        </Banner>
      ) : null}
      {errorReason ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {isOnboardingReason(errorReason)
            ? to(`login.errors.${errorReason}`)
            : t(`login.errors.${errorReason}`)}
        </Banner>
      ) : null}

      {/* A real link: full-page navigation, works with Enter, no token or password in JS. */}
      <Button asChild className="h-[50px] text-[16px] font-extrabold">
        <a href={href} autoFocus>
          <Icon as={LogIn} size="lg" />
          {t("login.startButton")}
          <Kbd keys="Enter" inverted />
        </a>
      </Button>

      {googleHref ? (
        <>
          <div className="flex items-center gap-3 text-[12px] text-muted-foreground" aria-hidden="true">
            <span className="h-px grow bg-border" />
            {to("login.or")}
            <span className="h-px grow bg-border" />
          </div>
          <Button asChild variant="secondary" className="h-[50px] text-[15px]">
            <a href={googleHref}>
              <span aria-hidden="true" className="text-[17px] font-extrabold text-info">
                G
              </span>
              {to("login.google")}
            </a>
          </Button>
        </>
      ) : null}

      <p className="flex items-start gap-2 text-[13px] text-foreground-secondary">
        <Icon as={ShieldCheck} size="md" className="mt-px shrink-0 text-primary" />
        {t("login.startHint")}
      </p>

      <div id="recovery" className="flex flex-col gap-2 rounded-lg bg-info-soft px-3.5 py-3">
        <p className="flex items-start gap-2.5 text-[12px] leading-normal text-foreground-secondary">
          <Icon as={Send} size="md" className="mt-px shrink-0 text-info" />
          <span>
            <b className="text-info-strong">{t("login.recoveryTitle")}</b> {t("login.recoveryText")}
          </span>
        </p>
        <nav className="flex flex-wrap gap-x-4 gap-y-1 pl-7 text-[13px] font-bold">
          <Link to="/recover">{to("login.forgot")}</Link>
          <Link to="/invite" className="inline-flex items-center gap-1">
            <Icon as={KeyRound} size="sm" />
            {to("login.invite")}
          </Link>
        </nav>
      </div>
    </>
  );
}
