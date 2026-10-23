/**
 * CSP sha256 fallback for static hosting — 24 §4.4, qaror #57.
 *
 * When the layer serving index.html cannot mint a nonce per response (a plain static host), the
 * build is made with `ERP_CSP_MODE=hash`: `style-src` lists the sha256 of every <style> text the
 * app can inject at runtime instead of `'nonce-…'`, the `csp-nonce` meta is dropped, and a
 * `_headers` file carries the same policy as an HTTP header (vite.config.ts → cspHashMode()).
 *
 * Runtime <style>s: Radix's modal scroll lock (react-remove-scroll-bar via react-style-singleton)
 * and the fixed Radix Select viewport style (`SELECT_VIEWPORT_CSS`). The scroll-lock text depends on the scrollbar gap (integer CSS px: 0 on overlay /
 * mobile scrollbars, ~15–17 on desktop at 100 % zoom, larger when zoomed out) and on the body
 * margins (0 — Tailwind preflight). Every gap in 0…SCROLL_LOCK_MAX_GAP is hashed; beyond that
 * (browser zoom < ~30 %) the style is blocked, which only means the page behind a modal can scroll.
 * csp-hashes.test.ts renders a real Radix Dialog and Select and fails when the library's text drifts
 * from `scrollLockCss()` / `SELECT_VIEWPORT_CSS`; the build guard (`inlineCspViolations`) fails the build on any inline
 * script/style in index.html that the policy does not allow.
 */
import { createHash } from "node:crypto";

import { CSP_NONCE_PLACEHOLDER, type CspDirectives } from "./csp.ts";

export type CspMode = "nonce" | "hash";

/** Largest scrollbar gap (CSS px) whose scroll-lock <style> is hashed. */
export const SCROLL_LOCK_MAX_GAP = 64;

/** CSP hash-source of an inline script/style text (exact bytes, UTF-8). */
export function sha256Source(text: string): string {
  return `'sha256-${createHash("sha256").update(text, "utf8").digest("base64")}'`;
}

/**
 * The <style> react-remove-scroll-bar 2.3 injects for Radix modals (`gapMode: "margin"`,
 * `!important`, relative body, body margins 0) — byte for byte (checked by csp-hashes.test.ts).
 */
export function scrollLockCss(gap: number): string {
  const imp = "!important";
  return (
    `\n  .with-scroll-bars-hidden {\n   overflow: hidden ${imp};\n   padding-right: ${gap}px ${imp};\n  }` +
    `\n  body[data-scroll-locked] {\n    overflow: hidden ${imp};\n    overscroll-behavior: contain;\n    ` +
    `position: relative ${imp};` +
    `\n    padding-left: 0px;\n    padding-top: 0px;\n    padding-right: 0px;\n    margin-left:0;\n    margin-top:0;\n    margin-right: ${gap}px ${imp};\n    ` +
    `\n  }\n  \n  .right-scroll-bar-position {\n    right: ${gap}px ${imp};\n  }` +
    `\n  \n  .width-before-scroll-bar {\n    margin-right: ${gap}px ${imp};\n  }` +
    `\n  \n  .right-scroll-bar-position .right-scroll-bar-position {\n    right: 0 ${imp};\n  }` +
    `\n  \n  .width-before-scroll-bar .width-before-scroll-bar {\n    margin-right: 0 ${imp};\n  }` +
    `\n  \n  body[data-scroll-locked] {\n    --removed-body-scroll-bar-size: ${gap}px;\n  }\n`
  );
}

/**
 * The <style> @radix-ui/react-select 2.x renders inside `SelectPrimitive.Viewport` (hides the
 * viewport scrollbar) — byte for byte (checked by csp-hashes.test.ts). In nonce mode it carries the
 * nonce through `nonce={getNonce()}` (@shared/ui select.tsx).
 */
export const SELECT_VIEWPORT_CSS =
  "[data-radix-select-viewport]{scrollbar-width:none;-ms-overflow-style:none;-webkit-overflow-scrolling:touch;}" +
  "[data-radix-select-viewport]::-webkit-scrollbar{display:none}";

/** Hash-sources of every runtime <style> the app injects (Radix scroll lock, gaps 0…max; Select viewport). */
export function runtimeStyleHashes(maxGap = SCROLL_LOCK_MAX_GAP): string[] {
  return [
    ...Array.from({ length: maxGap + 1 }, (_, gap) => sha256Source(scrollLockCss(gap))),
    sha256Source(SELECT_VIEWPORT_CSS),
  ];
}

const INLINE_ELEMENT = /<(script|style)\b([^>]*)>([\s\S]*?)<\/\1\s*>/gi;
const NONCE_ATTR = /\snonce\s*=\s*["']?([^"'\s>]+)/i;
const SRC_ATTR = /\ssrc\s*=/i;
const TAG = /<[a-z][^>]*>/gi;
const STYLE_ATTR = /\sstyle\s*=/i;
const HANDLER_ATTR = /\son[a-z]+\s*=/i;

/**
 * Build guard: every inline <script>/<style> in `html` must be allowed by `directives` — by a
 * matching sha256 or (nonce mode) the per-response nonce placeholder. Inline `style="…"` and
 * `on…=` attributes are never allowed (they would need 'unsafe-hashes'). Returns the violations.
 */
export function inlineCspViolations(html: string, directives: CspDirectives): string[] {
  const violations: string[] = [];
  for (const [, tag = "", attrs = "", body = ""] of html.matchAll(INLINE_ELEMENT)) {
    const kind = tag.toLowerCase() as "script" | "style";
    if (kind === "script" && SRC_ATTR.test(attrs)) continue;
    const sources = directives[`${kind}-src`] ?? directives["default-src"] ?? [];
    const nonce = NONCE_ATTR.exec(attrs)?.[1];
    const allowedByNonce =
      nonce !== undefined && nonce === CSP_NONCE_PLACEHOLDER && sources.includes(`'nonce-${nonce}'`);
    if (!allowedByNonce && !sources.includes(sha256Source(body))) {
      violations.push(`inline <${kind}> without a matching CSP source: ${sha256Source(body)}`);
    }
  }
  for (const [tag] of html.matchAll(TAG)) {
    if (STYLE_ATTR.test(tag)) violations.push(`inline style attribute: ${tag}`);
    if (HANDLER_ATTR.test(tag)) violations.push(`inline event handler: ${tag}`);
  }
  return violations;
}
