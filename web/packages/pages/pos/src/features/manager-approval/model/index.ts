/**
 * Manager approval for POS operations over a limit (18 §2.4 `ApprovalRef`, §9; 15 §2.3; 07 POS-05 / POS-14
 * `ApprovalDialog`). Two paths:
 *  - local PIN — a Manager/Owner standing at the register picks their name and types their PIN; checked by
 *    the local PBKDF2 verifier with lockout (`verifyLocalPin`, works offline) → `{mode:"local_pin", …}`;
 *  - remote — online only: `POST /approval-requests` then `GET /approval-requests/{id}` every 3 s until
 *    approved / rejected / expired (BO-16) → `{mode:"remote_request", approval_request_id}`.
 * The server re-checks the approver's right and limit at posting (APPROVAL_INVALID otherwise).
 */
import { api, toApiError } from "@shared/api";
import type { ApprovalRequestInKind, ApprovalRequestOutStatus } from "@shared/models";
import { compareMoney, money } from "@shared/lib/money";
import { staff as staffRepo, verifyLocalPin, type PinResult, type StaffRow } from "@shared/offline";

export type ApprovalKind = ApprovalRequestInKind;

/** 18 §2.4 — what goes into the event payload `approval`. */
export interface ApprovalRef {
  mode: "local_pin" | "remote_request";
  approved_by: string | null;
  pin_verified_locally: boolean | null;
  approval_request_id: string | null;
}

export interface Approver {
  userId: string;
  name: string;
  roleCodes: string[];
}

/** The most generous limit of `code` over the user's roles: undefined = none, null = unlimited. */
export function permissionLimit(row: Pick<StaffRow, "permissions">, code: string): string | null | undefined {
  let found = false;
  let best: string | null = "0";
  for (const p of row.permissions) {
    if (p.code !== code) continue;
    if (p.limit_value === null) return null;
    if (!found || compareMoney(money(p.limit_value), money(best ?? "0")) > 0) best = p.limit_value;
    found = true;
  }
  return found ? best : undefined;
}

/**
 * Who may approve: active staff holding `permission` whose limit covers `amount`
 * (`amount === null` → only an unlimited holder, e.g. an expired-goods return, 18 §7.1); never the requester.
 */
export function eligibleApprovers(
  rows: readonly StaffRow[],
  permission: string,
  amount: string | null,
  requesterId: string | null,
): Approver[] {
  return rows
    .filter((r) => r.active && r.user_id !== requesterId)
    .filter((r) => {
      const limit = permissionLimit(r, permission);
      if (limit === undefined) return false;
      if (limit === null) return true;
      if (amount === null) return false;
      return compareMoney(money(amount), money(limit)) <= 0;
    })
    .map((r) => ({ userId: r.user_id, name: r.full_name, roleCodes: [...r.role_codes] }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export type LocalPinOutcome =
  | { ok: true; approval: ApprovalRef }
  | { ok: false; error: "PIN_INVALID"; attemptsLeft: number }
  | { ok: false; error: "ACCOUNT_LOCKED"; lockedUntil: string }
  | { ok: false; error: "PIN_NOT_SET" | "PIN_MUST_CHANGE" };

export function localPinOutcome(userId: string, result: PinResult): LocalPinOutcome {
  if (result.ok) {
    if (result.mustChangePin) return { ok: false, error: "PIN_MUST_CHANGE" };
    return {
      ok: true,
      approval: {
        mode: "local_pin",
        approved_by: userId,
        pin_verified_locally: true,
        approval_request_id: null,
      },
    };
  }
  if (result.reason === "invalid")
    return { ok: false, error: "PIN_INVALID", attemptsLeft: result.attemptsLeft };
  if (result.reason === "locked")
    return { ok: false, error: "ACCOUNT_LOCKED", lockedUntil: result.lockedUntil };
  return { ok: false, error: "PIN_NOT_SET" };
}

export interface ApprovalDeps {
  staff(): Promise<StaffRow[]>;
  verifyPin(userId: string, pin: string): Promise<PinResult>;
  createRemote(kind: ApprovalKind, context: Record<string, unknown>): Promise<{ id: string }>;
  remoteStatus(id: string): Promise<ApprovalRequestOutStatus>;
  sleep(ms: number, signal?: AbortSignal): Promise<void>;
}

export const defaultApprovalDeps: ApprovalDeps = {
  staff: () => staffRepo.list(),
  verifyPin: (userId, pin) => verifyLocalPin(userId, pin),
  createRemote: async (kind, context) => {
    const r = await api.approvals.createRequest({ kind, context });
    return { id: r.id };
  },
  remoteStatus: async (id) => (await api.approvals.getRequest(id)).status,
  sleep: (ms, signal) =>
    new Promise((resolve, reject) => {
      const timer = setTimeout(resolve, ms);
      signal?.addEventListener("abort", () => {
        clearTimeout(timer);
        reject(new DOMException("aborted", "AbortError"));
      });
    }),
};

export const REMOTE_POLL_MS = 3_000;

export type RemoteOutcome =
  | { ok: true; approval: ApprovalRef }
  | { ok: false; status: "rejected" | "expired" | "consumed" | "error"; code?: string };

/** 18 §9.3: poll every 3 s until the request leaves `pending`. */
export async function waitRemoteApproval(
  deps: ApprovalDeps,
  id: string,
  signal?: AbortSignal,
  intervalMs = REMOTE_POLL_MS,
): Promise<RemoteOutcome> {
  for (;;) {
    let status: ApprovalRequestOutStatus;
    try {
      status = await deps.remoteStatus(id);
    } catch (e) {
      const err = toApiError(e);
      if (err.code === "NETWORK_ERROR") {
        await deps.sleep(intervalMs, signal);
        continue;
      }
      return { ok: false, status: "error", code: err.code };
    }
    if (status === "approved") {
      return {
        ok: true,
        approval: {
          mode: "remote_request",
          approved_by: null,
          pin_verified_locally: null,
          approval_request_id: id,
        },
      };
    }
    if (status !== "pending") return { ok: false, status };
    await deps.sleep(intervalMs, signal);
  }
}
