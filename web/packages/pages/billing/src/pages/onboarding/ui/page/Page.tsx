/**
 * BO-21 — Ro'yxatdan o'tish va birinchi sozlash (07, route /onboarding, mockup Bo21Royxat.dc.html).
 * Full page without sidebar: ink left panel with the step list, right panel with progress, the
 * finished-step summary and the current step. ①② are public; the tenant and the session cookie are
 * created by «Davom» on ②, so ③–⑥ run signed in (a lost session sends the user to the login).
 * `?method=google` — back from Google with a pending identity (14 §2.2): ① asks only phone + name.
 * useEffect only fires pageMounted (24 §2).
 */
import { useUnit } from "effector-react";
import { LogIn, WifiOff } from "lucide-react";
import { useEffect, type ComponentType } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { loginStartUrl } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { $isOnline } from "@shared/state/network";
import { $authStatus } from "@shared/state/session";
import { Banner, Button } from "@shared/ui";

import {
  $finished,
  $step,
  PRE_SIGNUP_STEPS,
  pageMounted,
  type OpeningStockImportSlotProps,
  type ProductImportSlotProps,
} from "../../model/index.ts";
import { AccountStep } from "../account-step/AccountStep.tsx";
import { Header } from "../header/Header.tsx";
import { ProductsStep } from "../products-step/ProductsStep.tsx";
import { SidePanel } from "../side-panel/SidePanel.tsx";
import { DebtsStep, InstallStep, OfdStep } from "../simple-steps/SimpleSteps.tsx";
import { StoreStep } from "../store-step/StoreStep.tsx";
import { Summary } from "../summary/Summary.tsx";

export interface OnboardingPageProps {
  /** ③a Excel/CSV import (catalog flow, injected by the shell). */
  productImport?: ComponentType<ProductImportSlotProps>;
  /** ③a «Qo'lda» → catalog product form route (owned by the catalog package). */
  manualProductHref?: string | null;
  /** ③b Excel/CSV opening stock (catalog flow `kind="opening_stock"`, injected by the shell). */
  openingStockImport?: ComponentType<OpeningStockImportSlotProps>;
  /** «Yakunlash» → BO-02. */
  dashboardPath?: string;
}

const SELF = "/onboarding";

function OnboardingPage({
  productImport,
  manualProductHref = null,
  openingStockImport,
  dashboardPath = "/app/dashboard",
}: OnboardingPageProps) {
  const { t } = useTranslation("onboarding");
  const [params] = useSearchParams();
  const method = params.get("method") === "google" ? "google" : "phone";
  const [step, finished, status, online, mounted] = useUnit([
    $step,
    $finished,
    $authStatus,
    $isOnline,
    pageMounted,
  ]);

  useEffect(() => {
    mounted({ method });
  }, [mounted, method]);

  useEffect(() => {
    document.title = `${t("title")} · ERP`;
  }, [t]);

  if (finished) return <Navigate to={dashboardPath} replace />;
  const postSignup = !PRE_SIGNUP_STEPS.includes(step);

  return (
    <div className="flex min-h-dvh flex-col bg-background lg:flex-row">
      <SidePanel />
      <main className="flex min-w-0 flex-1 flex-col gap-3.5 px-4 py-6 sm:px-8 lg:px-12">
        <Header />
        {!online ? (
          <Banner tone="warning" icon={WifiOff}>
            {t("wizard.offline")}
          </Banner>
        ) : null}
        {postSignup && status === "anonymous" ? (
          <Banner
            tone="warning"
            icon={LogIn}
            action={
              <Button asChild size="sm">
                <a href={loginStartUrl({ returnTo: SELF })}>{t("account.login")}</a>
              </Button>
            }
          >
            {t("wizard.sessionLost")}
          </Banner>
        ) : null}
        <Summary />
        <div className="w-full max-w-[960px]">
          {step === "account" ? <AccountStep /> : null}
          {step === "store" ? <StoreStep /> : null}
          {step === "products" ? (
            <ProductsStep
              productImport={productImport}
              manualProductHref={manualProductHref}
              openingStockImport={openingStockImport}
            />
          ) : null}
          {step === "debts" ? <DebtsStep /> : null}
          {step === "ofd" ? <OfdStep /> : null}
          {step === "install" ? <InstallStep /> : null}
        </div>
      </main>
    </div>
  );
}

export const Onboarding = {
  route: "/onboarding",
  titleKey: "onboarding:title",
  Page: OnboardingPage,
} as const;
