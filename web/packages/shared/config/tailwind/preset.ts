/**
 * Tailwind preset — 24-frontend-arxitekturasi.md §4.3, 08-dizayn-tizimi.md §1–§3.
 *
 * Every colour resolves to a CSS variable from `@shared/ui/styles/theme.css` (HSL triplets, shadcn
 * format). No hex values live here: change a token in theme.css, never in this file.
 */
import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const c = (v: string) => `hsl(var(--${v}) / <alpha-value>)`;

const preset = {
  content: [],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "'Manrope Variable'",
          "Manrope",
          "system-ui",
          "-apple-system",
          "'Segoe UI'",
          "Roboto",
          "sans-serif",
        ],
      },
      colors: {
        background: c("background"),
        foreground: c("foreground"),
        "foreground-secondary": c("foreground-secondary"),
        card: { DEFAULT: c("card"), foreground: c("card-foreground") },
        popover: { DEFAULT: c("popover"), foreground: c("popover-foreground") },
        primary: {
          DEFAULT: c("primary"),
          foreground: c("primary-foreground"),
          strong: c("primary-strong"),
          soft: c("primary-soft"),
          "soft-border": c("primary-soft-border"),
        },
        secondary: { DEFAULT: c("secondary"), foreground: c("secondary-foreground") },
        muted: { DEFAULT: c("muted"), foreground: c("muted-foreground") },
        accent: { DEFAULT: c("accent"), foreground: c("accent-foreground") },
        destructive: {
          DEFAULT: c("destructive"),
          foreground: c("destructive-foreground"),
          strong: c("destructive-strong"),
          soft: c("destructive-soft"),
          border: c("destructive-border"),
        },
        success: {
          DEFAULT: c("success"),
          foreground: c("success-foreground"),
          strong: c("success-strong"),
          soft: c("success-soft"),
        },
        warning: {
          DEFAULT: c("warning"),
          foreground: c("warning-foreground"),
          strong: c("warning-strong"),
          soft: c("warning-soft"),
          border: c("warning-border"),
        },
        info: {
          DEFAULT: c("info"),
          foreground: c("info-foreground"),
          strong: c("info-strong"),
          soft: c("info-soft"),
        },
        "awaiting-approval": {
          DEFAULT: c("awaiting-approval"),
          foreground: c("awaiting-approval-foreground"),
          strong: c("awaiting-approval-strong"),
          soft: c("awaiting-approval-soft"),
        },
        offline: {
          DEFAULT: c("offline"),
          strong: c("offline-strong"),
          soft: c("offline-soft"),
          foreground: c("offline-foreground"),
        },
        "offline-critical": {
          DEFAULT: c("offline-critical"),
          strong: c("offline-critical-strong"),
          soft: c("offline-critical-soft"),
        },
        "fiscal-pending": {
          DEFAULT: c("fiscal-pending"),
          strong: c("fiscal-pending-strong"),
          soft: c("fiscal-pending-soft"),
          foreground: c("fiscal-pending-foreground"),
        },
        border: c("border"),
        input: c("input"),
        ring: c("ring"),
        divider: c("divider"),
        track: c("track"),
        "disabled-foreground": c("disabled-foreground"),
        overlay: c("overlay"),
        sidebar: {
          DEFAULT: c("sidebar-background"),
          foreground: c("sidebar-foreground"),
          "muted-foreground": c("sidebar-muted-foreground"),
          primary: c("sidebar-primary"),
          "primary-foreground": c("sidebar-primary-foreground"),
          accent: c("sidebar-accent"),
          "accent-foreground": c("sidebar-accent-foreground"),
          border: c("sidebar-border"),
          ring: c("sidebar-ring"),
        },
      },
      borderRadius: { sm: "6px", md: "10px", lg: "var(--radius)", xl: "14px", "2xl": "16px", "3xl": "20px" },
      boxShadow: {
        card: "0 1px 2px rgb(15 27 45 / .04), 0 6px 20px rgb(15 27 45 / .05)",
        raised: "0 1px 2px rgb(15 27 45 / .04), 0 10px 28px rgb(15 27 45 / .06)",
        popover: "0 1px 2px rgb(15 27 45 / .04), 0 12px 32px rgb(15 27 45 / .10)",
        dialog: "0 24px 60px rgb(15 27 45 / .30)",
        cta: "0 8px 20px rgb(14 124 102 / .28)",
        "pos-sheet": "0 -8px 24px -4px rgb(15 27 45 / .12)",
        "focus-soft": "0 0 0 4px hsl(var(--primary-soft))",
      },
      fontSize: {
        display: ["46px", { lineHeight: "52px", fontWeight: "800", letterSpacing: "-0.5px" }],
        h1: ["26px", { lineHeight: "34px", fontWeight: "800" }],
        h2: ["17px", { lineHeight: "24px", fontWeight: "700" }],
        kpi: ["28px", { lineHeight: "34px", fontWeight: "800" }],
        money: ["24px", { lineHeight: "32px", fontWeight: "800" }],
        body: ["14px", "20px"],
        "body-pos": ["16px", "24px"],
        label: ["13px", { lineHeight: "18px", fontWeight: "600" }],
        small: ["13px", "18px"],
        caption: ["12px", { lineHeight: "16px", fontWeight: "700" }],
        overline: ["11px", { lineHeight: "16px", fontWeight: "700", letterSpacing: "0.6px" }],
        kbd: ["11px", { lineHeight: "14px", fontWeight: "600" }],
      },
      // 08 §3 z-index skeleton.
      zIndex: {
        "sticky-header": "30",
        dropdown: "40",
        overlay: "50",
        dialog: "60",
        toast: "70",
        "pos-statusbar": "80",
      },
    },
  },
  plugins: [animate],
} satisfies Config;

export default preset;
