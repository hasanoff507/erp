/** Ko'chirishlar wiring — sample() only (24 §2). */
import { combine, merge, sample } from "effector";

import {
  cancelTransferFx,
  createTransferFx,
  getTransferFx,
  listTransfersFx,
  loadAvailableFx,
  postTransferFx,
  receiveTransferFx,
  sendTransferFx,
} from "../effects/index.ts";
import {
  actionErrorDismissed,
  filterChanged,
  moreRequested,
  noticeDismissed,
  postRequested,
  reloadRequested,
  transferRefreshRequested,
  transferSelected,
  transferShown,
  transfersOpened,
} from "../events/index.ts";
import { replaceTransfer } from "../lib/index.ts";
import {
  $actionError,
  $available,
  $cursor,
  $error,
  $filter,
  $loaded,
  $notice,
  $pinned,
  $selectedId,
  $status,
  $transfers,
} from "../stores/index.ts";

export const $selected = combine(
  $transfers,
  $pinned,
  $selectedId,
  (list, pinned, id) => list.find((t) => t.id === id) ?? (pinned?.id === id ? pinned : null),
);
export const $moreLoading = combine(
  listTransfersFx.pending,
  $status,
  (pending, status) => pending && status !== "loading",
);
/** Any write in flight (buttons disabled, one action at a time). */
export const $acting = combine(
  [postTransferFx.pending, sendTransferFx.pending, receiveTransferFx.pending, cancelTransferFx.pending],
  (flags) => flags.some(Boolean),
);

// --- list ------------------------------------------------------------------------------------------
$filter.on(filterChanged, (_, status) => status);
sample({
  clock: [transfersOpened, filterChanged, reloadRequested],
  source: $filter,
  fn: (status) => ({ status, cursor: null }),
  target: listTransfersFx,
});
sample({
  clock: moreRequested,
  source: { status: $filter, cursor: $cursor, pending: listTransfersFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ status, cursor }) => ({ status, cursor }),
  target: listTransfersFx,
});
// An answer for a filter that is no longer current is dropped.
const pageLoaded = sample({
  clock: listTransfersFx.done,
  source: $filter,
  filter: (current, { params }) => current === params.status,
  fn: (_, payload) => payload,
});
$transfers.on(pageLoaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$cursor.on(pageLoaded, (_, { result }) => result.next_cursor);
$loaded.on(pageLoaded, () => true);
$status
  .on(listTransfersFx, (s, { cursor }) => (cursor === null ? "loading" : s))
  .on(pageLoaded, () => "idle")
  .on(listTransfersFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$error.on(listTransfersFx.failData, (_, e) => e).reset(listTransfersFx);

// --- detail / actions ------------------------------------------------------------------------------
$selectedId.on(transferSelected, (_, id) => id);
// One write at a time: a second «O'tkazish» while one is running is dropped (WEB-16).
sample({
  clock: postRequested,
  source: { acting: $acting, posting: postTransferFx.pending },
  filter: ({ acting, posting }) => !acting && !posting,
  fn: (_, id) => id,
  target: postTransferFx,
});
sample({ clock: transferRefreshRequested, target: getTransferFx });

const changed = merge([
  createTransferFx.doneData.map((r) => r.transfer),
  getTransferFx.doneData,
  postTransferFx.doneData,
  sendTransferFx.doneData,
  receiveTransferFx.doneData,
  cancelTransferFx.doneData,
]);
$transfers.on(changed, replaceTransfer);
$selectedId.on(transferShown, (_, t) => t.id);
$pinned
  .on(transferShown, (_, t) => t)
  .on(changed, (pinned, t) => (pinned?.id === t.id ? t : pinned))
  .reset(transferSelected);

const actionFailed = merge([
  postTransferFx.fail,
  sendTransferFx.fail,
  receiveTransferFx.fail,
  cancelTransferFx.fail,
]);
$actionError
  .on(actionFailed, (_, { error }) => error)
  .reset(actionErrorDismissed, postTransferFx, sendTransferFx, receiveTransferFx, cancelTransferFx);

// The document changed meanwhile (e-TTN not registered after all, already received…): show the truth.
sample({
  clock: actionFailed,
  filter: ({ error }) => error.status === 409 || error.status === 404,
  fn: ({ params }) => (typeof params === "string" ? params : params.id),
  target: getTransferFx,
});

$notice
  .on(cancelTransferFx.doneData, (_, t) =>
    t.warnings.includes("ETTN_CANCEL_IN_OPERATOR") ? "ettn_cancel_in_operator" : null,
  )
  .reset(noticeDismissed, cancelTransferFx);

$available.on(loadAvailableFx.doneData, (known, { productId, qty }) => ({ ...known, [productId]: qty }));
