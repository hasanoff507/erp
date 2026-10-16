/**
 * Shell entry (24 §1). Order matters: fonts → design tokens/Tailwind → i18n → app.
 * Manrope is self-hosted (24 §4.1, qaror #57): no CDN request at runtime.
 */
import "@fontsource-variable/manrope/wght.css";
import "@shared/ui/styles.css";

import { setNonce } from "get-nonce";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { initI18n } from "@shared/i18n";

import { App } from "./app/index.tsx";

// 24 §4.4: Radix (react-remove-scroll → react-style-singleton) stamps this nonce on the <style> it
// injects, so the strict `style-src 'self' 'nonce-…'` allows it. Must run before the first render.
const nonce = document.querySelector<HTMLMetaElement>('meta[property="csp-nonce"]')?.content;
if (nonce) setNonce(nonce);

initI18n();

const container = document.getElementById("root");
if (!container) throw new Error("#root element is missing in index.html");

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
