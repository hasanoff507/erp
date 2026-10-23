/**
 * BO-16 effects — generated `api.approvals.*` (18 §9.3–§9.5). Writes carry `Idempotency-Key` and the
 * CSRF token from the shared client; `approve` is a PIN step-up of the approver.
 */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";

import { toListParams } from "../lib/index.ts";
import {
  RESOLVED_PAGE_SIZE,
  type ApprovalRequest,
  type ApprovalRequestPage,
  type ApproveOut,
  type ApproveRequest,
  type ListRequest,
  type RejectOut,
  type RejectRequest,
} from "../types/index.ts";

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

export const listRequestsFx = wrap<ListRequest, ApprovalRequestPage>((req) =>
  api.approvals.listRequests(toListParams(req)),
);

/** Newest approved + rejected (+ consumed = approved and used) requests; the caller keeps today's. */
export const listResolvedFx = wrap<void, ApprovalRequest[]>(async () => {
  const pages = await Promise.all(
    (["approved", "consumed", "rejected"] as const).map((status) =>
      api.approvals.listRequests({ status, limit: RESOLVED_PAGE_SIZE }),
    ),
  );
  return pages.flatMap((p) => p.items);
});

export const approveFx = wrap<ApproveRequest, ApproveOut>(({ id, pin }) =>
  api.approvals.approveRequest(id, { pin }),
);

export const rejectFx = wrap<RejectRequest, RejectOut>(({ id, reason }) =>
  api.approvals.rejectRequest(id, { reason }),
);

/** `Date.now()` behind an effect (connections stay pure). */
export const readClockFx = createEffect(() => Date.now());
