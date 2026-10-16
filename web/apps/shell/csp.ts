/**
 * Content-Security-Policy — qaror #57, 15-xavfsizlik-va-audit.md §8, 32-kod-qoidalari.md §10,
 * 24-frontend-arxitekturasi.md §4.4 (style nonce, agent port in connect-src, qaror #60).
 *
 * Single source of the policy. It is delivered two ways:
 *  1. HTTP header (authoritative) — reverse proxy in production (deploy/nginx-security-headers.conf,
 *     generated from this file) and `vite preview` (vite.config.ts).
 *  2. <meta http-equiv> injected into the built index.html — defence in depth when the app is served
 *     by a static host without custom headers. `frame-ancestors` is ignored inside <meta>, so it is
 *     header-only (clickjacking protection therefore REQUIRES the header).
 *
 * Strict by design: no 'unsafe-inline', no 'unsafe-eval', no CDN. Fonts are self-hosted (24 §4.1).
 * `style-src 'self' 'nonce-<N>'` (24 §4.4): Radix modal parts (react-remove-scroll) inject a <style>
 * at runtime. The built index.html carries the placeholder `__CSP_NONCE__` (CSP <meta> and
 * `<meta property="csp-nonce">`); the layer that serves index.html replaces it with a fresh nonce per
 * response, sends the same value in the CSP header and `Cache-Control: no-store`. The SPA hands the
 * nonce to `get-nonce` (main.tsx) so Radix stamps it on its <style> elements.
 * Dev server is exempt (Vite HMR/React Refresh inject inline scripts); build + preview are strict.
 */
export const CSP_NONCE_PLACEHOLDER = "__CSP_NONCE__";

/** nginx: the per-request id (32 hex chars) serves as the nonce — deploy/nginx-security-headers.conf. */
export const NGINX_NONCE = "$request_id";

export interface CspOptions {
  /** Shop agent loopback port (21 §16, default 47110). */
  agentPort?: number;
  /** Extra API origins when the API is not same-origin (normally empty: BFF cookie is same-origin). */
  connectSrc?: readonly string[];
  /**
   * Style nonce of this response. Default: the placeholder (substituted when index.html is served).
   * `null` — no nonce (responses that are not index.html: their CSP does not govern the document).
   */
  nonce?: string | null;
}

export type CspDirectives = Record<string, readonly string[]>;

export function cspDirectives({
  agentPort = 47110,
  connectSrc = [],
  nonce = CSP_NONCE_PLACEHOLDER,
}: CspOptions = {}): CspDirectives {
  return {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": nonce ? ["'self'", `'nonce-${nonce}'`] : ["'self'"],
    "img-src": ["'self'"],
    "font-src": ["'self'"],
    "connect-src": ["'self'", `http://127.0.0.1:${agentPort}`, ...connectSrc],
    "manifest-src": ["'self'"],
    "worker-src": ["'self'"],
    "frame-src": ["'none'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
}

const HEADER_ONLY = new Set(["frame-ancestors", "report-uri", "report-to", "sandbox"]);

export function serializeCsp(directives: CspDirectives, target: "header" | "meta"): string {
  return Object.entries(directives)
    .filter(([name]) => target === "header" || !HEADER_ONLY.has(name))
    .map(([name, values]) => `${name} ${values.join(" ")}`)
    .join("; ");
}

/** Companion security headers sent with the CSP (15 §8 / OWASP baseline). */
export function securityHeaders(options: CspOptions = {}): Record<string, string> {
  return {
    "Content-Security-Policy": serializeCsp(cspDirectives(options), "header"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy":
      "camera=(self), microphone=(), geolocation=(), payment=(), usb=(self), serial=(self), bluetooth=(self)",
    "Cross-Origin-Opener-Policy": "same-origin",
  };
}

/** 128-bit random nonce, base64 (CSP nonce-source grammar). */
export function generateNonce(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return btoa(String.fromCharCode(...bytes));
}

/** index.html for one response: every placeholder (CSP <meta>, csp-nonce <meta>) gets the nonce. */
export function applyNonce(html: string, nonce: string): string {
  return html.replaceAll(CSP_NONCE_PLACEHOLDER, nonce);
}
