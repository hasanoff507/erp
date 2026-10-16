/**
 * @pages/finance — Xarajatlar, kassa harakati, buxgalteriya, QQS, bank tushumi (M10, M11, M15, M16).
 * Package router (24 §1). Placeholder in Bosqich 0: no screens yet, the shell shows "Tez orada"
 * for the sidebar routes owned by this package: BO-07 /app/tax/vat, BO-08 /app/accounting/journal, BO-10 /app/tax/reconciliation, BO-15 /app/einvoices, BO-17 /app/expenses, BO-24 /app/finance/bank-settlements (07-ekran-tafsilotlari.md).
 * Each screen will live in src/pages/<screen>/{model/{events,stores,effects,connections,types,lib},ui}.
 */
import type { RouteObject } from "react-router-dom";

export const routes: RouteObject[] = [];
