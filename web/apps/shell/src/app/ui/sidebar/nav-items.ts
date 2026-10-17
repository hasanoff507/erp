/**
 * Back-office navigation — 06-ekranlar-umumiy.md §1.9 (groups/items, permission-gated), routes and
 * permission codes from 07-ekran-tafsilotlari.md, icons from 08-dizayn-tizimi.md §4.
 * An item is shown only if the user has its permission; an empty group shows no title.
 */
import {
  BookOpen,
  Boxes,
  ChartColumn,
  Check,
  FileText,
  House,
  Landmark,
  Link2,
  Package,
  Receipt,
  Settings,
  Shield,
  ShoppingCart,
  Sparkles,
  Tag,
  Truck,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import { SETTINGS_TABS, settingsTabCodes } from "@shared/lib/settings-tabs";
import { hasPermissions, type GrantedAccess, type PermissionRequirement } from "@shared/state/permissions";

export type NavGroupKey = "main" | "sales" | "warehouse" | "finance" | "management";
export type NavItemKey =
  | "dashboard"
  | "aiAssistant"
  | "approvals"
  | "pos"
  | "debtors"
  | "catalogPrices"
  | "stock"
  | "products"
  | "purchases"
  | "labels"
  | "expenses"
  | "bankSettlements"
  | "einvoices"
  | "taxReconciliation"
  | "accounting"
  | "reports"
  | "onec"
  | "settings";

export interface NavItem {
  key: NavItemKey;
  /** Screen route (07). */
  to: string;
  icon: LucideIcon;
  requires: PermissionRequirement;
  /** Extra path prefixes that keep this item active (e.g. Settings tabs, BO-07 inside BO-10). */
  activePrefixes?: readonly string[];
}

export interface NavGroup {
  key: NavGroupKey;
  items: readonly NavItem[];
}

export const NAV_GROUPS: readonly NavGroup[] = [
  {
    key: "main",
    items: [
      {
        key: "dashboard",
        to: "/app/dashboard",
        icon: House,
        requires: { permission: ["reports.sales.view", "reports.finance.view"] },
      },
      { key: "aiAssistant", to: "/app/ai", icon: Sparkles, requires: { permission: "ai.chat.use" } },
      {
        key: "approvals",
        to: "/app/approvals",
        icon: Check,
        requires: {
          anyOf: [
            "discount.approve",
            "returns.approve",
            "debts.approve",
            "prices.approve",
            "cash.withdraw",
            "expenses.approve",
            "stock.writeoff",
            "card.manual_entry.approve",
          ],
        },
      },
    ],
  },
  {
    key: "sales",
    items: [
      // Opens the web POS (POS-01) — 06 §1.9.
      // The whole `/pos/*` area is guarded by this item (route-level check, 24 §2).
      {
        key: "pos",
        to: "/pos/login",
        icon: ShoppingCart,
        requires: { permission: "sales.create" },
        activePrefixes: ["/pos"],
      },
      {
        key: "debtors",
        to: "/app/debts",
        icon: Users,
        requires: { anyOf: ["debts.payment.accept", "reports.finance.view"] },
      },
      {
        key: "catalogPrices",
        to: "/app/catalog/prices",
        icon: Tag,
        requires: { anyOf: ["prices.edit", "discount.rule.manage", "prices.approve"] },
      },
    ],
  },
  {
    key: "warehouse",
    items: [
      { key: "stock", to: "/app/warehouse/stock", icon: Package, requires: { permission: "stock.view" } },
      // 06 §1.9: the product catalogue (19 §1–§3) for users without price rights (e.g. the
      // storekeeper). The list needs stock.view (backend GET /products, 19 §1 — same as the page);
      // catalog.manage only adds editing inside it. Also the route guard of /app/catalog/products/*.
      {
        key: "products",
        to: "/app/catalog/products",
        icon: Boxes,
        requires: { permission: "stock.view" },
      },
      {
        key: "purchases",
        to: "/app/purchases",
        icon: Truck,
        requires: {
          anyOf: [
            "purchases.create",
            "purchases.receive",
            "purchases.post",
            "purchases.pay",
            "purchases.return",
          ],
        },
      },
      { key: "labels", to: "/app/catalog/labels", icon: FileText, requires: { permission: "labels.print" } },
    ],
  },
  {
    key: "finance",
    items: [
      { key: "expenses", to: "/app/expenses", icon: Wallet, requires: { permission: "expenses.create" } },
      {
        key: "bankSettlements",
        to: "/app/finance/bank-settlements",
        icon: Landmark,
        requires: { permission: "bank_settlements.manage" },
      },
      {
        key: "einvoices",
        to: "/app/einvoices",
        icon: Receipt,
        requires: { anyOf: ["purchases.post", "einvoice.create", "einvoice.sign"] },
      },
      {
        key: "taxReconciliation",
        to: "/app/tax/reconciliation",
        icon: Shield,
        requires: { anyOf: ["tax.compare.review", "tax.vat.view"] },
        activePrefixes: ["/app/tax"],
      },
      {
        key: "accounting",
        to: "/app/accounting/journal",
        icon: BookOpen,
        requires: { permission: "accounting.post" },
      },
    ],
  },
  {
    key: "management",
    items: [
      {
        key: "reports",
        to: "/app/reports",
        icon: ChartColumn,
        requires: { anyOf: ["reports.sales.view", "reports.finance.view"] },
      },
      {
        key: "onec",
        to: "/app/onec/exports",
        icon: Link2,
        requires: { permission: "onec.view" },
        activePrefixes: ["/app/onec"],
      },
      // Shown when any Settings tab is allowed (06 §1.9 tabs, @shared/lib/settings-tabs); the link
      // opens the first allowed tab (navItemTarget), not always «Do'kon».
      {
        key: "settings",
        to: "/app/settings/tenant",
        icon: Settings,
        requires: { anyOf: settingsTabCodes() },
        activePrefixes: ["/app/settings", "/app/billing"],
      },
    ],
  },
];

const ALL_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

function matches(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/** The sidebar item a path belongs to (longest prefix wins; Settings tabs → «Sozlamalar»). */
export function navItemForPath(pathname: string): NavItem | null {
  let best: { item: NavItem; length: number } | null = null;
  for (const item of ALL_ITEMS) {
    for (const prefix of [item.to, ...(item.activePrefixes ?? [])]) {
      if (matches(pathname, prefix) && (!best || prefix.length > best.length)) {
        best = { item, length: prefix.length };
      }
    }
  }
  return best?.item ?? null;
}

/**
 * Route-level permission of a path (24 §2 `ProtectedRoute`): the same requirement as its sidebar item
 * (longest prefix), so a screen hidden from the menu cannot be opened by URL either. Paths without a
 * sidebar item need an authenticated session only; the server's `require_permission` stays the final
 * decision (403 PERMISSION_DENIED).
 */
export function requiresForPath(pathname: string): PermissionRequirement {
  return navItemForPath(pathname)?.requires ?? {};
}

/** BO-07 «QQS ichki hisobi» — the built tab of the «QQS va davlat hisoboti» section (07 BO-07). */
export const VAT_INTERNAL_PATH = "/app/tax/vat";

/**
 * Where an item's link goes for this user: «Sozlamalar» → the first Settings tab the user may open
 * (same order and permissions as the Settings tab bar); «QQS va davlat hisoboti» → the BO-07 tab for a
 * `tax.vat.view` holder (BO-10 «Davlat hisoboti bilan solishtirish» is a later stage); every other item →
 * its route.
 */
export function navItemTarget(item: NavItem, granted: GrantedAccess): string {
  if (item.key === "taxReconciliation") {
    return hasPermissions(granted, { permission: "tax.vat.view" }) ? VAT_INTERNAL_PATH : item.to;
  }
  if (item.key !== "settings") return item.to;
  return SETTINGS_TABS.find((tab) => hasPermissions(granted, tab.requires))?.to ?? item.to;
}

/** Landing screen on `/` and `/app`: the first sidebar item the user may open (06 §1.9), or none. */
export function firstAllowedNavItem(granted: GrantedAccess): NavItem | null {
  return ALL_ITEMS.find((item) => hasPermissions(granted, item.requires)) ?? null;
}
