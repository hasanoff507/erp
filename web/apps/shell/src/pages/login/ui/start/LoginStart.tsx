/**
 * BO-01 entry action (07 "Amallar" → KIRISH, 14 §2.1). The SPA holds no password form: «Kirish» is a
 * plain link, so the browser itself (not an XHR) goes to `GET /auth/login/start?return_to=…`; the BFF
 * keeps state + PKCE server-side and redirects to the server-rendered AS page (`/oauth/authorize`),
 * where the phone + password form lives (the only credential form). The callback sets the
 * HttpOnly cookie and returns to `return_to`, or to `/login?error=<reason>`.
 */
import { useUnit } from "effector-react";
import { LogIn, Send, ShieldCheck, TriangleAlert, WifiOff } from "lucide-react";

import { loginStartUrl } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { $isOnline } from "@shared/state/network";
import { Banner, Button, Icon, Kbd } from "@shared/ui";

import type { LoginErrorReason } from "../../model/index.ts";

export interface LoginStartProps {
  returnTo: string;
  tenantId: string | null;
  errorReason: LoginErrorReason | null;
}

export function LoginStart({ returnTo, tenantId, errorReason }: LoginStartProps) {
  const { t } = useTranslation("auth");
  const online = useUnit($isOnline);
  const href = loginStartUrl({ returnTo, tenantId });

  return (
    <>
      {!online ? (
        <Banner tone="warning" icon={WifiOff}>
          {t("login.offline")}
        </Banner>
      ) : null}
      {errorReason ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {t(`login.errors.${errorReason}`)}
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

      <p className="flex items-start gap-2 text-[13px] text-foreground-secondary">
        <Icon as={ShieldCheck} size="md" className="mt-px shrink-0 text-primary" />
        {t("login.startHint")}
      </p>

      <div id="recovery" className="flex items-start gap-2.5 rounded-lg bg-info-soft px-3.5 py-3">
        <Icon as={Send} size="md" className="mt-px shrink-0 text-info" />
        <p className="text-[12px] leading-normal text-foreground-secondary">
          <b className="text-info-strong">{t("login.recoveryTitle")}</b> {t("login.recoveryText")}
        </p>
      </div>
    </>
  );
}
