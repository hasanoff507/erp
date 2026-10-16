import { ShoppingCart } from "lucide-react";

import { useTranslation } from "@shared/i18n";

import { PendingScreen } from "#/shared/ui/PendingScreen.tsx";

/** POS-02 — Sotish paneli (07, route /pos/sale; maket Main.dc.html). Bosqich 3. */
function SalePage() {
  const { t } = useTranslation("pos");
  return <PendingScreen icon={ShoppingCart} title={t("sale.title")} description={t("sale.pending")} />;
}

export const Sale = { route: "sale", titleKey: "pos:sale.title", Page: SalePage } as const;
