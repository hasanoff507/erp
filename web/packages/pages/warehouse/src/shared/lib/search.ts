/**
 * Debounced remote search (product / supplier pickers). The input debounces (SearchInput); the model
 * keeps only the answer for the CURRENT query — a slow answer to an older query is dropped.
 */
import {
  createEvent,
  createStore,
  sample,
  type Effect,
  type EventCallable,
  type StoreWritable,
} from "effector";

import type { ApiError } from "@shared/api";

import { apiFx } from "./effect.ts";

export interface SearchModel<T> {
  queryChanged: EventCallable<string>;
  reset: EventCallable<void>;
  searchFx: Effect<string, T[], ApiError>;
  $query: StoreWritable<string>;
  $results: StoreWritable<T[]>;
  $error: StoreWritable<ApiError | null>;
}

export function createSearch<T>(search: (query: string) => Promise<T[]>): SearchModel<T> {
  const queryChanged = createEvent<string>();
  const reset = createEvent();
  const searchFx = apiFx<string, T[]>(search);

  const $query = createStore("")
    .on(queryChanged, (_, q) => q)
    .reset(reset);
  const $results = createStore<T[]>([]).reset(reset);
  const $error = createStore<ApiError | null>(null, { skipVoid: false }).reset(reset, searchFx);

  sample({ clock: queryChanged, filter: (q) => q !== "", target: searchFx });
  sample({ clock: queryChanged, filter: (q) => q === "", fn: (): T[] => [], target: $results });
  sample({
    clock: searchFx.done,
    source: $query,
    filter: (current, { params }) => current === params,
    fn: (_, { result }) => result,
    target: $results,
  });
  sample({
    clock: searchFx.fail,
    source: $query,
    filter: (current, { params }) => current === params,
    fn: (_, { error }) => error,
    target: $error,
  });

  return { queryChanged, reset, searchFx, $query, $results, $error };
}
