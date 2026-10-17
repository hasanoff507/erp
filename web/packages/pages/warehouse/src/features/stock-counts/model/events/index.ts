import { createEvent } from "effector";

import type { CountStatus, ExtraLine, LineFilter } from "../types/index.ts";

export const countsOpened = createEvent();
export const filterChanged = createEvent<CountStatus | null>();
export const moreRequested = createEvent();
export const reloadRequested = createEvent();
/** Detail sheet (`null` closes it). */
export const countSelected = createEvent<string | null>();
export const detailReloadRequested = createEvent();

/** Back-office line entry (POS-10 is Bosqich 3): typed counted value of a product. */
export const countedChanged = createEvent<{ productId: string; value: string }>();
/** An unexpected product found on the shelf (not in the snapshot). */
export const extraLineAdded = createEvent<ExtraLine>();
export const draftsReset = createEvent();
export const lineFilterChanged = createEvent<LineFilter>();
export const lineSearchChanged = createEvent<string>();
export const actionErrorDismissed = createEvent();
