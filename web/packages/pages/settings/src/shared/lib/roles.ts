/**
 * System roles (15 §2.2). `GET /roles` returns `{id, name, is_system, system_code, version}`; the five
 * system roles carry a stable `system_code` (`owner`, `manager`, ...). The UI shows them in the
 * current language through `common:user.roles.*` and recognises the owner role by that code — never
 * by the (editable, language-specific) name.
 */
export type SystemRoleKey = "owner" | "manager" | "cashier" | "storekeeper" | "accountant";

const SYSTEM_ROLE_KEYS: ReadonlySet<string> = new Set<SystemRoleKey>([
  "owner",
  "manager",
  "cashier",
  "storekeeper",
  "accountant",
]);

export interface RoleLike {
  id: string;
  name: string;
  is_system: boolean;
  system_code?: string | null;
}

export function systemRoleKey(role: RoleLike): SystemRoleKey | null {
  const code = role.system_code;
  return role.is_system && code && SYSTEM_ROLE_KEYS.has(code) ? (code as SystemRoleKey) : null;
}

/** The owner role cannot be assigned/removed through BO-11 and its permissions are read-only. */
export function isOwnerRole(role: RoleLike): boolean {
  return systemRoleKey(role) === "owner";
}

/** Limit unit by permission code (15 §2.1): `discount.*` and `prices.approve` — percent, others — so'm. */
export type LimitUnit = "percent" | "amount";

export function limitUnitOf(code: string): LimitUnit {
  return code.startsWith("discount.") || code === "prices.approve" ? "percent" : "amount";
}
