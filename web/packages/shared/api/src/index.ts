/**
 * @shared/api — 24-frontend-arxitekturasi.md §3.
 *
 * Generated domain modules are re-exported as ESM namespaces only (no hand-written wrappers):
 *   import { api } from "@shared/api";  api.auth.sessionGet()
 * Regenerate after any backend schema change: `pnpm api:export` (no running backend needed),
 * `pnpm api:fetch` (running backend) or `pnpm api:gen` (committed schema).
 */
import * as access from "./generated/access/access.ts";
import * as accounting from "./generated/accounting/accounting.ts";
import * as approvals from "./generated/approvals/approvals.ts";
import * as attachments from "./generated/attachments/attachments.ts";
import * as auth from "./generated/auth/auth.ts";
import * as branches from "./generated/branches/branches.ts";
import * as cardTerminals from "./generated/card-terminals/card-terminals.ts";
import * as cash from "./generated/cash/cash.ts";
import * as debts from "./generated/debts/debts.ts";
import * as expenses from "./generated/expenses/expenses.ts";
import * as health from "./generated/health/health.ts";
import * as inventory from "./generated/inventory/inventory.ts";
import * as notifications from "./generated/notifications/notifications.ts";
import * as pricing from "./generated/pricing/pricing.ts";
import * as purchasing from "./generated/purchasing/purchasing.ts";
import * as reports from "./generated/reports/reports.ts";
import * as returns from "./generated/returns/returns.ts";
import * as sales from "./generated/sales/sales.ts";
import * as stockCounts from "./generated/stock-counts/stock-counts.ts";
import * as sync from "./generated/sync/sync.ts";
import * as tax from "./generated/tax/tax.ts";
import * as transfers from "./generated/transfers/transfers.ts";

export const api = {
  access,
  accounting,
  approvals,
  attachments,
  auth,
  branches,
  cardTerminals,
  cash,
  debts,
  expenses,
  health,
  inventory,
  notifications,
  pricing,
  purchasing,
  reports,
  returns,
  sales,
  stockCounts,
  sync,
  tax,
  transfers,
} as const;

export { apiRequest, http } from "./_base/instance.ts";
export {
  ApiError,
  INTERNAL_ERROR,
  NETWORK_ERROR,
  REQUEST_CANCELED,
  toApiError,
  type ApiErrorDetail,
} from "./_base/errors.ts";
export {
  apiFieldErrors,
  applyApiFieldErrors,
  toFieldPath,
  type ApiFieldError,
  type ApplyFieldErrorsResult,
  type SetFieldError,
} from "./_base/field-errors.ts";
export { configureApi, type ApiHooks } from "./_base/hooks.ts";
export { resetCsrfToken } from "./_base/csrf.ts";
export { LOGIN_START_PATH, loginStartUrl, type LoginStartOptions } from "./_base/navigation.ts";
