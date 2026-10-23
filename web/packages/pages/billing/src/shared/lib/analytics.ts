/**
 * Product analytics hooks (07 BO-21 / UX-INSTALL "Audit/analitika"). There is no analytics module
 * in Bosqich 1, so events are a no-op sink; `setAnalyticsSink` lets a future module subscribe
 * (and tests observe) without touching the screens.
 */
export type AnalyticsEvent =
  | "onboarding_started"
  | "onboarding_step_completed"
  | "onboarding_skipped_step"
  | "onboarding_completed"
  | "terms_accepted"
  | "consent.ai_cross_border_changed"
  | "install_guide_viewed"
  | "pwa_installed"
  | "cloud_printer_test_printed";

export type AnalyticsSink = (event: AnalyticsEvent, props?: Readonly<Record<string, string>>) => void;

let sink: AnalyticsSink = () => undefined;

export function setAnalyticsSink(next: AnalyticsSink): void {
  sink = next;
}

export function track(event: AnalyticsEvent, props?: Readonly<Record<string, string>>): void {
  try {
    sink(event, props);
  } catch {
    // analytics must never break a screen
  }
}
