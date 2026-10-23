/**
 * $isOnline — 24 §2 / §3: browser online/offline events plus API network failures.
 * The POS status chip and offline banners read this store.
 */
import { createEffect, createEvent, createStore, sample } from "effector";

export const onlineDetected = createEvent();
export const offlineDetected = createEvent();
export const networkWatchStarted = createEvent();

/** Node ≥21 has a global `navigator` without `onLine` (undefined would crash createStore). */
const initiallyOnline =
  typeof navigator === "undefined" || (navigator as { onLine?: boolean }).onLine !== false;

export const $isOnline = createStore<boolean>(initiallyOnline)
  .on(onlineDetected, () => true)
  .on(offlineDetected, () => false);

let watching = false;
const watchNetworkFx = createEffect(() => {
  if (watching || typeof window === "undefined") return;
  watching = true;
  window.addEventListener("online", () => onlineDetected());
  window.addEventListener("offline", () => offlineDetected());
});

sample({ clock: networkWatchStarted, target: watchNetworkFx });
