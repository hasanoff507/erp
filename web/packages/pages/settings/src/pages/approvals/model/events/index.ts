import { createEvent } from "effector";

import type {
  ApprovalKind,
  ApprovalsMountParams,
  ApproveRequest,
  QueueTab,
  RejectRequest,
} from "../types/index.ts";

export const pageMounted = createEvent<ApprovalsMountParams>();
/** Starts the 15 s poll clock (fired by the page after mount; stopped by `pageUnmounted`). */
export const pollingStarted = createEvent();
export const pageUnmounted = createEvent();

/** Status tab (18 §9.3 `?status=`). */
export const tabChanged = createEvent<QueueTab>();
/** Kind chip (`null` = «Barchasi»; filtered on the client — the API has no `kind` filter). */
export const kindChanged = createEvent<ApprovalKind | null>();
/** ErrorState «Qayta urinish» / «Yangilash». */
export const reloadRequested = createEvent();
/** «Yana yuklash» — next cursor page. */
export const moreRequested = createEvent();
/** Poll tick (internal) — the clock for «… daq qoldi» and a quiet refresh of the pending list. */
export const clockTicked = createEvent<number>();

/** «Tasdiqlash» with the approver's PIN (18 §9.4 step-up). */
export const approveSubmitted = createEvent<ApproveRequest>();
/** «Rad etishni yuborish» with the mandatory reason (18 §9.5). */
export const rejectSubmitted = createEvent<RejectRequest>();
/** The PIN field changed — the previous PIN error of this request is cleared. */
export const pinErrorCleared = createEvent<string>();
