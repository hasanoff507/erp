/**
 * Renders the security headers (csp.ts) as an nginx include — kept in sync by csp.test.ts.
 *
 * 24 §4.4: index.html is served with a per-request style nonce. nginx uses `$request_id` (32 hex
 * chars, fresh for every request) as the nonce: `sub_filter` puts it in place of the `__CSP_NONCE__`
 * placeholder (CSP <meta> + `<meta property="csp-nonce">`), the CSP header carries the same value,
 * and the document is `Cache-Control: no-store`. Other files get the policy without a nonce.
 */
import { CSP_NONCE_PLACEHOLDER, NGINX_NONCE } from "../csp.ts";

type Headers = Record<string, string>;

const addHeaders = (headers: Headers, indent: string) =>
  Object.entries(headers).map(([name, value]) => `${indent}add_header ${name} "${value}" always;`);

/**
 * @param staticHeaders  headers for every file except index.html (CSP without nonce)
 * @param documentHeaders headers for index.html (CSP with `'nonce-$request_id'`)
 */
export function nginxSecurityHeaders(staticHeaders: Headers, documentHeaders: Headers): string {
  const pad = "    ";
  return [
    "# GENERATED from apps/shell/csp.ts — do not edit by hand (qaror #57, 15 §8, 24 §4.4).",
    "# Regenerate: pnpm --filter shell exec node --experimental-strip-types deploy/write.ts",
    "# Include inside the `server` block whose `root` is apps/shell/dist (backend paths — /api, /auth,",
    "# /oauth, … — are proxied by their own, longer `location` blocks).",
    "# Note: a nested `location` with its own add_header drops these — repeat the include there.",
    "",
    "# Static files (hashed assets, sw.js, config.js, icons) and the SPA fallback.",
    "location / {",
    `${pad}try_files $uri /index.html;`,
    ...addHeaders(staticHeaders, pad),
    "}",
    "",
    "# The SPA document: fresh style nonce per response, never cached (24 §4.4).",
    "location = /index.html {",
    ...addHeaders({ ...documentHeaders, "Cache-Control": "no-store" }, pad),
    `${pad}sub_filter_once off;`,
    `${pad}sub_filter '${CSP_NONCE_PLACEHOLDER}' '${NGINX_NONCE}';`,
    "}",
    "",
  ].join("\n");
}
