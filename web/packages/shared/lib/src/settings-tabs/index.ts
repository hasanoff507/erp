/**
 * 06 §1.9 "Sozlamalar ichki tablari" — the single list of Settings tabs (route + permission), in order.
 * Used by the Settings tab bar (@pages/settings `SettingsNav`) and by the shell sidebar: «Sozlamalar»
 * opens the first tab the user may open and is shown when any tab is allowed.
 *
 * `requires` has the shape of `@shared/state/permissions` `PermissionRequirement` (kept structural here:
 * @shared/lib does not depend on @shared/state).
 */
export type SettingsTabKey = "tenant" | "users" | "branches" | "telegram" | "billing" | "onec";

export interface SettingsTabRequirement {
  permission?: string | readonly string[];
  anyOf?: readonly string[];
}

export interface SettingsTab {
  key: SettingsTabKey;
  to: string;
  requires: SettingsTabRequirement;
}

export const SETTINGS_TABS: readonly SettingsTab[] = [
  { key: "tenant", to: "/app/settings/tenant", requires: { permission: "settings.tenant" } },
  // BO-11 «Qurilmalar» inside users (qaror #56).
  { key: "users", to: "/app/settings/users", requires: { anyOf: ["settings.users", "devices.revoke"] } },
  // BO-12 kassalar inside branches.
  {
    key: "branches",
    to: "/app/settings/branches",
    requires: { anyOf: ["settings.branches", "cash_register.manage"] },
  },
  {
    key: "telegram",
    to: "/app/settings/telegram",
    requires: { anyOf: ["notifications.manage", "telegram.link"] },
  },
  { key: "billing", to: "/app/billing", requires: { permission: "billing.manage" } },
  { key: "onec", to: "/app/settings/onec", requires: { permission: "onec.view" } },
];

/** Every permission code that opens at least one Settings tab (the «Sozlamalar» item's `anyOf`). */
export function settingsTabCodes(tabs: readonly SettingsTab[] = SETTINGS_TABS): string[] {
  const codes = new Set<string>();
  for (const tab of tabs) {
    const { permission, anyOf } = tab.requires;
    if (typeof permission === "string") codes.add(permission);
    else permission?.forEach((c) => codes.add(c));
    anyOf?.forEach((c) => codes.add(c));
  }
  return [...codes];
}
