/**
 * BO-14 «Xavfsizlik» → «Sinxron istisnolari» (07 BO-14, qaror #56b; 20 #40f/#40g): POS events accepted
 * with a flag (`sync_exceptions`) — `GET /sync-exceptions?reviewed=` and «Ko'rib chiqildi» with a mandatory
 * note (`POST /sync-exceptions/{id}/review`, audit `sync_exception.reviewed`). Reviewing never changes
 * postings. Permission: `settings.tenant` or `accounting.post` (server-checked).
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type {
  ListSyncExceptionsParams,
  SyncExceptionOut,
  SyncExceptionOutKind,
  SyncExceptionPage,
  SyncExceptionReviewed,
} from "@shared/models";

export type SyncException = SyncExceptionOut;
export type SyncExceptionKind = SyncExceptionOutKind;
/** «Ko'rib chiqilmagan» (default) / «Ko'rib chiqilgan» / «Barchasi». */
export type ReviewFilter = "open" | "reviewed" | "all";
export const REVIEW_FILTERS: readonly ReviewFilter[] = ["open", "reviewed", "all"];
export type LoadStatus = "idle" | "loading" | "error";
export const EXCEPTIONS_PAGE_SIZE = 20;
/** `review_note` 1–500 chars after trim (20 #40g). */
export const REVIEW_NOTE_MAX = 500;

interface ListRequest {
  filter: ReviewFilter;
  cursor: string | null;
}
export interface ReviewRequest {
  id: string;
  note: string;
}

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

// --- events ------------------------------------------------------------------------------------------
export const exceptionsOpened = createEvent();
export const exceptionsFilterChanged = createEvent<ReviewFilter>();
export const exceptionsMoreRequested = createEvent();
export const exceptionsReloadRequested = createEvent();

// --- effects -----------------------------------------------------------------------------------------
export const listExceptionsFx = wrap<ListRequest, SyncExceptionPage>(({ filter, cursor }) =>
  api.branches.listSyncExceptions(toParams(filter, cursor)),
);
export const reviewExceptionFx = wrap<ReviewRequest, SyncExceptionReviewed>(({ id, note }) =>
  api.branches.reviewSyncException(id, { review_note: note }),
);

// --- stores ------------------------------------------------------------------------------------------
export const $exceptionsFilter = createStore<ReviewFilter>("open");
export const $exceptions = createStore<SyncException[]>([]);
export const $exceptionsCursor = createStore<string | null>(null, { skipVoid: false });
export const $exceptionsStatus = createStore<LoadStatus>("idle");
export const $exceptionsError = createStore<ApiError | null>(null, { skipVoid: false });
export const $exceptionsMoreLoading = combine(
  listExceptionsFx.pending,
  $exceptionsStatus,
  (pending, status) => pending && status !== "loading",
);

// --- connections -------------------------------------------------------------------------------------
$exceptionsFilter.on(exceptionsFilterChanged, (_, f) => f);
sample({
  clock: [exceptionsOpened, exceptionsFilterChanged, exceptionsReloadRequested],
  source: $exceptionsFilter,
  fn: (filter) => ({ filter, cursor: null }),
  target: listExceptionsFx,
});
sample({
  clock: exceptionsMoreRequested,
  source: { filter: $exceptionsFilter, cursor: $exceptionsCursor, pending: listExceptionsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ filter, cursor }) => ({ filter, cursor }),
  target: listExceptionsFx,
});
const loaded = sample({
  clock: listExceptionsFx.done,
  source: $exceptionsFilter,
  filter: (current, { params }) => current === params.filter,
  fn: (_, payload) => payload,
});
$exceptions.on(loaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$exceptionsCursor.on(loaded, (_, { result }) => result.next_cursor);
$exceptionsStatus
  .on(listExceptionsFx, (status, { cursor }) => (cursor === null ? "loading" : status))
  .on(loaded, () => "idle")
  .on(listExceptionsFx.fail, (status, { params }) => (params.cursor === null ? "error" : status));
$exceptionsError.on(listExceptionsFx.failData, (_, e) => e).reset(listExceptionsFx);

// Reviewed: under «Ko'rib chiqilmagan» the row leaves the list, otherwise it is updated in place.
sample({
  clock: reviewExceptionFx.doneData,
  source: { list: $exceptions, filter: $exceptionsFilter },
  fn: ({ list, filter }, done) => applyReview(list, done, filter),
  target: $exceptions,
});
// Reviewed elsewhere meanwhile (409) / gone (404): show the truth.
sample({
  clock: reviewExceptionFx.failData,
  filter: (e) => e.status === 404 || e.status === 409,
  fn: () => undefined,
  target: exceptionsReloadRequested,
});

// --- lib ---------------------------------------------------------------------------------------------
export function toParams(filter: ReviewFilter, cursor: string | null): ListSyncExceptionsParams {
  return {
    ...(filter === "all" ? {} : { reviewed: filter === "reviewed" }),
    ...(cursor ? { cursor } : {}),
    limit: EXCEPTIONS_PAGE_SIZE,
  };
}

export function isReviewFilter(value: string): value is ReviewFilter {
  return (REVIEW_FILTERS as readonly string[]).includes(value);
}

export function isNoteValid(note: string): boolean {
  const n = note.trim();
  return n.length > 0 && n.length <= REVIEW_NOTE_MAX;
}

export function applyReview(
  list: readonly SyncException[],
  done: SyncExceptionReviewed,
  filter: ReviewFilter,
): SyncException[] {
  if (filter === "open") return list.filter((x) => x.id !== done.id);
  return list.map((x) =>
    x.id === done.id
      ? { ...x, reviewed_at: done.reviewed_at, reviewed_by: done.reviewed_by, review_note: done.review_note }
      : x,
  );
}

/** Document type → label key suffix (`settings:syncExceptions.docTypes.*`), unknown → `other`. */
const DOC_TYPES = [
  "sales",
  "returns",
  "shifts",
  "cash_movements",
  "transfers",
  "stock_counts",
  "debt_payments",
] as const;
type KnownDocType = (typeof DOC_TYPES)[number];
export type ExceptionDocType = KnownDocType | "other";
function isKnownDocType(value: string): value is KnownDocType {
  return (DOC_TYPES as readonly string[]).includes(value);
}
export function exceptionDocType(docType: string | null): ExceptionDocType | null {
  if (docType === null) return null;
  return isKnownDocType(docType) ? docType : "other";
}
