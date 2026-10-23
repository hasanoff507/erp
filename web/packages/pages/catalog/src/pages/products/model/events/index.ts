import { createEvent } from "effector";

export const pageMounted = createEvent();
export const searchChanged = createEvent<string>();
export const categoryChanged = createEvent<string | null>();
export const archivedChanged = createEvent<boolean>();
export const pageChanged = createEvent<number>();
export const listRefreshRequested = createEvent();

/** Editor Sheet: a product id from the route (`/app/catalog/products/:productId`). */
export const productRequested = createEvent<string>();
export const editorClosed = createEvent();

/** MXIK search box (debounced in SearchInput). */
export const mxikQueryChanged = createEvent<string>();
