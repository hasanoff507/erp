/**
 * @pages/finance — Xarajatlar, kassa harakati, buxgalteriya, QQS, bank tushumi (M10, M11, M15, M16).
 * Package router (24 §1): route objects relative to the back-office root `/app`.
 *
 * - BO-08 `/app/accounting/journal` — buxgalteriya jurnali + «Qayta hisoblash navbati» (Bosqich 2 part).
 * - BO-07 `/app/tax/vat` — QQS ichki hisobi: vat-summary KPI + QQS registri (B3) + «Soliq hisob-kitobi
 *   (ST)» bloki (B4).
 * - BO-17 `/app/expenses` — xarajatlar, takrorlanuvchi xarajatlar, toifalar (B4).
 * - BO-24 `/app/finance/bank-settlements` (+ `/new`, `/:id`) — bank tushumi tasdig'i (B4).
 *
 * Not built yet (the shell shows "Tez orada"): BO-15 /app/einvoices (07).
 * Each screen lives in src/pages/<screen>/{model/{events,stores,effects,connections,types,lib},ui}.
 */
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { BankSettlements } from "#/pages/bank-settlements/ui/page/Page.tsx";
import { Expenses } from "#/pages/expenses/ui/page/Page.tsx";
import { Journal } from "#/pages/journal/ui/page/Page.tsx";
import { Reconciliation } from "#/pages/reconciliation/ui/page/Page.tsx";
import { Vat } from "#/pages/vat/ui/page/Page.tsx";

export const routes: RouteObject[] = [Journal, Vat, Reconciliation, Expenses, BankSettlements].map((screen) => ({
  path: screen.route,
  element: <screen.Page />,
  handle: { titleKey: screen.titleKey } satisfies RouteHandle,
}));
