/**
 * Shell entry (24 §1). Order matters: fonts → design tokens/Tailwind → i18n → app.
 * Manrope is self-hosted (24 §4.1, qaror #57): no CDN request at runtime.
 */
import "@fontsource-variable/manrope/wght.css";
// G-02: Noto Sans only for the code points Manrope lacks (ʻ ʼ, Ққ Ғғ Ҳҳ) — narrow unicode-range.
import "./noto-sans-fallback.css";
import "@shared/ui/styles.css";

import { setNonce } from "get-nonce";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { initI18n } from "@shared/i18n";

import { App } from "./app/index.tsx";

// 24 §4.4: Radix (react-remove-scroll → react-style-singleton) stamps this nonce on the <style> it
// injects, so the strict `style-src 'self' 'nonce-…'` allows it. Must run before the first render.
// A placeholder that nobody substituted is a public, predictable value — never use it as a nonce
// (static hosts use the sha256 build instead: ERP_CSP_MODE=hash, which drops this meta).
const nonce = document.querySelector<HTMLMetaElement>('meta[property="csp-nonce"]')?.content;
if (nonce && nonce !== "__CSP_NONCE__") setNonce(nonce);

initI18n();

const container = document.getElementById("root");
if (!container) throw new Error("#root element is missing in index.html");

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
