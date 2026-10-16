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
import { CreditCard, Download } from "lucide-react";
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
import { Banner, Button, Icon } from "@shared/ui";

import { loginErrorReason, safeNextPath, safeTenantId, SUBSCRIPTION_REASON } from "../../model/index.ts";
import { BranchStep } from "../branch-step/BranchStep.tsx";
import { LoginHeader } from "../header/LoginHeader.tsx";
import { PromoPanel } from "../promo/PromoPanel.tsx";
import { LoginStart } from "../start/LoginStart.tsx";

export function LoginPage({ defaultPath }: { defaultPath: string }) {
  const { t } = useTranslation("auth");
  const [status, branchChoiceRequired, restriction, sessionError] = useUnit([
    $authStatus,
    $branchChoiceRequired,
    $subscriptionRestriction,
    $sessionError,
  ]);
  const [params] = useSearchParams();
  const title = t("login.pageTitle");
  const returnTo = safeNextPath(params.get("next")) ?? defaultPath;
  const error = params.get("error");

  useEffect(() => {
    document.title = `${title} · ERP`;
  }, [title]);

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
              <h1 className="text-[28px] font-extrabold leading-tight">{t("login.title")}</h1>
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
                <span className="block">{t("login.subscriptionExpired")}</span>
                <a href="#export" className="mt-1 inline-flex items-center gap-1 text-destructive-strong">
                  <Icon as={Download} size="sm" />
                  {t("login.exportData")}
                </a>
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
            <p className="text-center text-[12px] leading-normal text-foreground-secondary">
              {t("login.termsPrefix")} <a href="#terms">{t("login.terms")}</a> {t("login.and")}{" "}
              <a href="#privacy">{t("login.privacy")}</a>
              {t("login.termsSuffix")}
            </p>
          </div>
        </div>
      </main>
      <PromoPanel />
    </div>
  );
}
