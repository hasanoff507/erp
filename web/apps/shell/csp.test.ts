// @vitest-environment node
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  applyNonce,
  CSP_NONCE_PLACEHOLDER,
  cspDirectives,
  generateNonce,
  NGINX_NONCE,
  parseLanPrinterOrigins,
  securityHeaders,
  serializeCsp,
} from "./csp.ts";
import { nginxSecurityHeaders } from "./deploy/render.ts";

describe("CSP — qaror #57, 24 §4.4", () => {
  it("is strict: self only, no inline/eval, no third-party origins", () => {
    const header = serializeCsp(cspDirectives(), "header");
    expect(header).toContain("default-src 'self'");
    expect(header).toContain("script-src 'self';");
    expect(header).toContain("frame-ancestors 'none'");
    expect(header).toContain("object-src 'none'");
    expect(header).toContain("connect-src 'self' http://127.0.0.1:47110");
    expect(header).not.toMatch(/unsafe-inline|unsafe-eval|unsafe-hashes|googleapis|gstatic|https:\/\//);
  });

  it("style-src allows 'self' plus the per-response nonce (Radix <style>), never 'unsafe-inline'", () => {
    expect(cspDirectives()["style-src"]).toEqual(["'self'", `'nonce-${CSP_NONCE_PLACEHOLDER}'`]);
    expect(cspDirectives({ nonce: "abc123" })["style-src"]).toEqual(["'self'", "'nonce-abc123'"]);
    expect(cspDirectives({ nonce: null })["style-src"]).toEqual(["'self'"]);
    // script-src never gets the nonce.
    expect(cspDirectives({ nonce: "abc123" })["script-src"]).toEqual(["'self'"]);
  });

  it("meta variant omits header-only directives", () => {
    const meta = serializeCsp(cspDirectives(), "meta");
    expect(meta).not.toContain("frame-ancestors");
    expect(meta).toContain("default-src 'self'");
    expect(meta).toContain(`'nonce-${CSP_NONCE_PLACEHOLDER}'`);
  });

  it("nonces are fresh, 128-bit, base64 (CSP nonce-source grammar)", () => {
    const nonces = new Set(Array.from({ length: 50 }, generateNonce));
    expect(nonces.size).toBe(50);
    for (const nonce of nonces) {
      expect(nonce).toMatch(/^[A-Za-z0-9+/]{22}==$/);
      expect(atob(nonce)).toHaveLength(16);
    }
  });

  it("applyNonce replaces every placeholder of index.html", () => {
    const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
    expect(html).toContain(`<meta property="csp-nonce" content="${CSP_NONCE_PLACEHOLDER}" />`);
    const meta = `<meta http-equiv="Content-Security-Policy" content="${serializeCsp(cspDirectives(), "meta")}">`;
    const served = applyNonce(meta + html, "N0nce");
    expect(served).not.toContain(CSP_NONCE_PLACEHOLDER);
    expect(served).toContain(`<meta property="csp-nonce" content="N0nce" />`);
    expect(served).toContain("style-src 'self' 'nonce-N0nce'");
  });

  it("deploy/nginx-security-headers.conf is in sync with csp.ts", () => {
    const committed = readFileSync(new URL("./deploy/nginx-security-headers.conf", import.meta.url), "utf8");
    expect(committed).toBe(
      nginxSecurityHeaders(securityHeaders({ nonce: null }), securityHeaders({ nonce: NGINX_NONCE })),
    );
  });

  it("nginx: index.html gets $request_id as nonce via sub_filter, no-store; assets get no nonce", () => {
    const conf = readFileSync(new URL("./deploy/nginx-security-headers.conf", import.meta.url), "utf8");
    const [assets, document] = conf.split("location = /index.html {");
    expect(assets).toContain("style-src 'self';");
    expect(assets).not.toContain("'nonce-");
    expect(document).toContain("style-src 'self' 'nonce-$request_id'");
    expect(document).toContain(`sub_filter '${CSP_NONCE_PLACEHOLDER}' '$request_id';`);
    expect(document).toContain("sub_filter_once off;");
    expect(document).toContain('add_header Cache-Control "no-store" always;');
    expect(document).toContain("frame-ancestors 'none'");
  });

  it("LAN HTTP printers (24 §6.1): exact private-IPv4 origins from ERP_CSP_LAN_PRINTERS, never wildcards", () => {
    expect(parseLanPrinterOrigins(undefined)).toEqual([]);
    expect(parseLanPrinterOrigins("http://192.168.1.60, https://10.0.0.5:8443 http://192.168.1.60")).toEqual([
      "http://192.168.1.60",
      "https://10.0.0.5:8443",
    ]);
    for (const bad of [
      "http://*.local",
      "http://printer.lan",
      "http://8.8.8.8",
      "http://192.168.1.60/cgi-bin",
      "ftp://10.0.0.1",
      "*",
    ]) {
      expect(() => parseLanPrinterOrigins(bad)).toThrow(/ERP_CSP_LAN_PRINTERS/);
    }
    const header = serializeCsp(cspDirectives({ lanPrinterOrigins: ["http://192.168.1.60"] }), "header");
    expect(header).toContain("connect-src 'self' http://127.0.0.1:47110 http://192.168.1.60;");
    expect(serializeCsp(cspDirectives(), "header")).toContain("connect-src 'self' http://127.0.0.1:47110;");
  });
});
