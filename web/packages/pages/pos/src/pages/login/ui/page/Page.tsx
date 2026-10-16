import { KeyRound } from "lucide-react";

import { useTranslation } from "@shared/i18n";

import { PendingScreen } from "#/shared/ui/PendingScreen.tsx";

/** POS-01 — Kassaga kirish / Smena ochish (07, route /pos/login). Bosqich 3. */
function PosLoginPage() {
  const { t } = useTranslation("pos");
  return <PendingScreen icon={KeyRound} title={t("login.title")} description={t("login.pending")} />;
}

export const PosLogin = { route: "login", titleKey: "pos:login.title", Page: PosLoginPage } as const;
