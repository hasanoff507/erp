/**
 * BO-01 — Kirish (login). Route /login (07), mockup Bo01Kirish.dc.html, flow 14 §2.1.
 * Full page without sidebar (08 §6.2). The page is an entry screen: «Kirish» sends the browser to the
 * BFF (`/auth/login/start`), credentials are typed on the AS page only. Query parameters:
 * After login: several branches → BO-01 branch step (07 `branchId`), then redirect to `next`.
 * GET /auth/session 403 PERMISSION_DENIED (no active membership) → explained here.
 *   next=<path>                         where to return after login (same-app paths only)
 *   tenant_id=<uuid>                    forwarded for multi-tenant users (14 §9)
 *   error=<reason>                      from /auth/callback → translated message
 *   reason=subscription_expired | error=subscription_restricted → restricted-subscription banner
 */
import { useUnit } from "effector-react";
import { CreditCard } from "lucide-react";
import { useEffect } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import {
  $authStatus,
  $branchChoiceRequired,
  $sessionError,
  $subscriptionRestriction,
} from "@shared/state/session";
import { Banner, Button } from "@shared/ui";

import {
  $legalLinks,
  legalLinksRequested,
  loginErrorReason,
  safeNextPath,
  safeTenantId,
  SUBSCRIPTION_REASON,
} from "../../model/index.ts";
import { BranchStep } from "../branch-step/BranchStep.tsx";
import { LoginHeader } from "../header/LoginHeader.tsx";
import { PromoPanel } from "../promo/PromoPanel.tsx";
import { LoginStart } from "../start/LoginStart.tsx";

export function LoginPage({ defaultPath }: { defaultPath: string }) {
  const { t } = useTranslation("auth");
  const { t: to } = useTranslation("onboarding");
  const [status, branchChoiceRequired, restriction, sessionError, legal, requestLegal] = useUnit([
    $authStatus,
    $branchChoiceRequired,
    $subscriptionRestriction,
    $sessionError,
    $legalLinks,
    legalLinksRequested,
  ]);
  const [params] = useSearchParams();
  const title = t("login.pageTitle");
  const returnTo = safeNextPath(params.get("next")) ?? defaultPath;
  const error = params.get("error");

  useEffect(() => {
    document.title = `${title} · ERP`;
  }, [title]);
  useEffect(() => {
    requestLegal();
  }, [requestLegal]);

  if (status === "authenticated" && !branchChoiceRequired) return <Navigate to={returnTo} replace />;

  const subscriptionExpired =
    params.get("reason") === "subscription_expired" || error === SUBSCRIPTION_REASON || restriction !== null;

  return (
    <div className="flex min-h-dvh flex-wrap gap-4 bg-background p-4">
      <main className="flex min-w-0 flex-[1_1_560px] flex-col px-1 pb-2 pt-4 sm:px-12">
        <LoginHeader />
        <div className="flex grow items-center justify-center py-5">
          <div className="flex w-full max-w-[420px] flex-col gap-3.5">
            <div className="flex flex-col gap-1.5">
              <h1 className="text-h1">{t("login.title")}</h1>
              <p className="text-[14px] text-foreground-secondary">{t("login.subtitle")}</p>
            </div>

            {subscriptionExpired ? (
              <Banner
                tone="destructive"
                icon={CreditCard}
                live="assertive"
                action={
                  restriction?.payUrl ? (
                    <Button asChild size="sm" variant="destructive">
                      <a href={restriction.payUrl}>
                        {t("login.payButton")}
                        {restriction.amountDue ? ` · ${formatMoney(restriction.amountDue)}` : ""}
                      </a>
                    </Button>
                  ) : undefined
                }
              >
                {/* «Ma'lumotlarimni yuklab olish» comes with the B6 data-export flow — no dead link until then. */}
                <span className="block">{t("login.subscriptionExpired")}</span>
              </Banner>
            ) : null}

            {branchChoiceRequired ? (
              <BranchStep />
            ) : (
              <LoginStart
                returnTo={returnTo}
                tenantId={safeTenantId(params.get("tenant_id"))}
                errorReason={
                  sessionError?.code === "PERMISSION_DENIED" ? "no_membership" : loginErrorReason(error)
                }
              />
            )}

            <p className="text-center text-[14px] text-foreground-secondary">
              {t("login.noAccount")}{" "}
              <Link to="/onboarding" className="font-bold">
                {t("login.register")}
              </Link>
            </p>
            <p className="text-center text-[13px]">
              <Link to="/install">{to("login.install")}</Link>
            </p>
            {/* Documents from GET /auth/terms (`text_url`); hidden until both are known — no `#terms` stubs. */}
            {legal ? (
              <p className="text-center text-[12px] leading-normal text-foreground-secondary">
                {t("login.termsPrefix")}{" "}
                <a href={legal.terms} target="_blank" rel="noreferrer">
                  {t("login.terms")}
                </a>{" "}
                {t("login.and")}{" "}
                <a href={legal.privacy} target="_blank" rel="noreferrer">
                  {t("login.privacy")}
                </a>
                {t("login.termsSuffix")}
              </p>
            ) : null}
          </div>
        </div>
      </main>
      <PromoPanel />
    </div>
  );
}
