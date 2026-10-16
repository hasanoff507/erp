import { createEvent } from "effector";

import type { AccountData, ProductsMethod, SignupMethod, StepId, StoreData } from "../types/index.ts";

/** `?method=google` after the Google callback (14 §2.2); otherwise the phone path. */
export const pageMounted = createEvent<{ method: SignupMethod }>();
export const methodSelected = createEvent<SignupMethod>();

/** Phone typed in ① (national digits) — a different number drops the sent/verified code. */
export const phoneChanged = createEvent<string>();
/** «Kod olish» / «Qayta yuborish» with the E.164 number. */
export const otpRequested = createEvent<string>();
/** Six digits typed (OtpInput `onComplete`). */
export const otpCodeSubmitted = createEvent<string>();

export const accountSubmitted = createEvent<AccountData>();
/** ② «Davom» → POST /auth/signup. */
export const storeSubmitted = createEvent<StoreData>();
/** Draft of ② kept when going back to ① («O'zgartirish» / «Orqaga»). */
export const storeDraftChanged = createEvent<StoreData>();
export const termsReloadRequested = createEvent();

export const backClicked = createEvent();
/** «Davom» on ③–⑤. */
export const nextClicked = createEvent();
/** «O'tkazib yuborish» on ④–⑥. */
export const skipClicked = createEvent();
/** «O'zgartirish» on a finished pre-signup step. */
export const stepEditRequested = createEvent<StepId>();

export const productsMethodSelected = createEvent<ProductsMethod | null>();
/** The embedded import flow committed: `created_product_count`. */
export const productsImported = createEvent<number>();
export const connectNowToggled = createEvent<boolean>();
/** «Yakunlash» on ⑥ → BO-02. */
export const finishClicked = createEvent();

/** 1 s tick of the resend countdown (patronum interval, runs only while a countdown is active). */
export const countdownTicked = createEvent<number>();
