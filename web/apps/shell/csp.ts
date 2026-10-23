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
 * Static host without per-response nonces: `ERP_CSP_MODE=hash` build — sha256 list of the runtime
 * <style> texts instead of the nonce (csp-hashes.ts, 24 §4.4).
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
   * LAN HTTP receipt printers (Epson ePOS / Star WebPRNT, 24 §6.1) of this deployment — exact origins from the
   * deploy config `ERP_CSP_LAN_PRINTERS` (`parseLanPrinterOrigins`), never wildcards. Default: none.
   */
  lanPrinterOrigins?: readonly string[];
  /**
   * Style nonce of this response. Default: the placeholder (substituted when index.html is served).
   * `null` — no nonce (responses that are not index.html: their CSP does not govern the document).
   */
  nonce?: string | null;
  /**
   * Static-host fallback (24 §4.4, csp-hashes.ts): sha256 hash-sources of the runtime <style>
   * texts, used instead of a nonce when nothing can mint one per response.
   */
  styleHashes?: readonly string[];
}

export type CspDirectives = Record<string, readonly string[]>;

export function cspDirectives({
  agentPort = 47110,
  connectSrc = [],
  lanPrinterOrigins = [],
  nonce = CSP_NONCE_PLACEHOLDER,
  styleHashes = [],
}: CspOptions = {}): CspDirectives {
  return {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'", ...(nonce ? [`'nonce-${nonce}'`] : []), ...styleHashes],
    "img-src": ["'self'"],
    "font-src": ["'self'"],
    "connect-src": ["'self'", `http://127.0.0.1:${agentPort}`, ...connectSrc, ...lanPrinterOrigins],
    "manifest-src": ["'self'"],
    "worker-src": ["'self'"],
    "frame-src": ["'none'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
}

const PRIVATE_IPV4 = /^(10\.\d{1,3}|172\.(1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}$/;

/**
 * `ERP_CSP_LAN_PRINTERS` (comma/space separated) → CSP origins. Each entry must be `http(s)://<private IPv4>[:port]`
 * (10/8, 172.16/12, 192.168/16) — no hostnames, paths or wildcards; anything else fails the build/deploy step.
 */
export function parseLanPrinterOrigins(raw: string | undefined): string[] {
  const out: string[] = [];
  for (const entry of (raw ?? "").split(/[\s,]+/).filter(Boolean)) {
    let url: URL;
    try {
      url = new URL(entry);
    } catch {
      throw new Error(`ERP_CSP_LAN_PRINTERS: invalid origin "${entry}"`);
    }
    const octetsOk = url.hostname.split(".").every((o) => o.length > 0 && (o.length < 3 || o <= "255"));
    if (
      !["http:", "https:"].includes(url.protocol) ||
      !PRIVATE_IPV4.test(url.hostname) ||
      !octetsOk ||
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash ||
      entry.endsWith("/")
    ) {
      throw new Error(`ERP_CSP_LAN_PRINTERS: "${entry}" must be http(s)://<private IPv4>[:port]`);
    }
    if (!out.includes(url.origin)) out.push(url.origin);
  }
  return out;
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
