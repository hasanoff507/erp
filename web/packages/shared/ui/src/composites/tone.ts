/**
 * Semantic tone → token classes. 08 §1: a chip/banner is always the pair bg-X-soft + text-X-strong;
 * the base colour X is for icons, dots, borders and charts only (never text — §10 contrast).
 */
export type Tone =
  "neutral" | "primary" | "success" | "warning" | "destructive" | "info" | "awaiting-approval";

export const SOFT_TONE: Record<Tone, string> = {
  neutral: "bg-accent text-foreground-secondary",
  primary: "bg-primary-soft text-primary-strong",
  success: "bg-success-soft text-success-strong",
  warning: "bg-warning-soft text-warning-strong",
  destructive: "bg-destructive-soft text-destructive-strong",
  info: "bg-info-soft text-info-strong",
  "awaiting-approval": "bg-awaiting-approval-soft text-awaiting-approval-strong",
};

export const DOT_TONE: Record<Tone, string> = {
  neutral: "bg-muted-foreground",
  primary: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
  info: "bg-info",
  "awaiting-approval": "bg-awaiting-approval",
};

export const STRONG_TEXT_TONE: Record<Tone, string> = {
  neutral: "text-muted-foreground",
  primary: "text-primary-strong",
  success: "text-success-strong",
  warning: "text-warning-strong",
  destructive: "text-destructive-strong",
  info: "text-info-strong",
  "awaiting-approval": "text-awaiting-approval-strong",
};
