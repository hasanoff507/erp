// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import path from "node:path";

import { render } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { setNonce } from "get-nonce";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui";

import { CSP_NONCE_PLACEHOLDER, cspDirectives, securityHeaders, serializeCsp } from "./csp.ts";
import {
  inlineCspViolations,
  runtimeStyleHashes,
  SCROLL_LOCK_MAX_GAP,
  scrollLockCss,
  SELECT_VIEWPORT_CSS,
  sha256Source,
} from "./csp-hashes.ts";
import { staticHostHeaders } from "./deploy/render.ts";

/** Opens a real Radix (shadcn) Dialog with the given scrollbar gap; returns the injected <style> texts. */
function radixRuntimeStyles(gap: number): string[] {
  Object.defineProperty(document.documentElement, "clientWidth", {
    configurable: true,
    get: () => window.innerWidth - gap,
  });
  document.body.style.margin = "0"; // Tailwind preflight in the app; jsdom's UA sheet has 8px.
  const { unmount } = render(
    createElement(
      Dialog,
      { open: true },
      createElement(
        DialogContent,
        null,
        createElement(DialogTitle, null, "Sarlavha"),
        createElement(DialogDescription, null, "Matn"),
      ),
    ),
  );
  const styles = Array.from(document.head.querySelectorAll("style"), (el) => el.textContent ?? "");
  unmount();
  return styles;
}

/** Opens a real Radix (shadcn) Select; returns its viewport <style> elements (text + nonce). */
function radixSelectStyles(): { css: string; nonce: string | null }[] {
  const { unmount } = render(
    createElement(
      Select,
      { open: true, value: "a" },
      createElement(SelectTrigger, { "aria-label": "Tanlov" }, createElement(SelectValue)),
      createElement(SelectContent, null, createElement(SelectItem, { value: "a" }, "A")),
    ),
  );
  const styles = Array.from(document.querySelectorAll("style"), (el) => ({
    css: el.textContent ?? "",
    nonce: el.getAttribute("nonce"),
  })).filter((s) => s.css.includes("data-radix-select-viewport"));
  unmount();
  return styles;
}

afterEach(() => {
  Reflect.deleteProperty(document.documentElement, "clientWidth");
});

describe("CSP sha256 fallback for static hosts — 24 §4.4", () => {
  it("scrollLockCss() is byte-identical to what Radix (react-remove-scroll-bar) injects", () => {
    for (const gap of [0, 15, 17, SCROLL_LOCK_MAX_GAP]) {
      const styles = radixRuntimeStyles(gap);
      const lock = styles.filter((css) => css.includes("data-scroll-locked"));
      expect(lock, `gap ${gap}`).toEqual([scrollLockCss(gap)]);
    }
  });

  it("every runtime <style> a Radix modal injects is covered by a hash", () => {
    const hashes = runtimeStyleHashes();
    expect(hashes).toHaveLength(SCROLL_LOCK_MAX_GAP + 2);
    expect(new Set(hashes).size).toBe(hashes.length);
    for (const gap of [0, 12, 17, 34]) {
      const styles = radixRuntimeStyles(gap);
      expect(styles.length).toBeGreaterThan(0);
      for (const css of styles) expect(hashes, `gap ${gap}`).toContain(sha256Source(css));
    }
  });

  it("test_web08_select_viewport_style_allowed", () => {
    // hash mode: the Select viewport <style> Radix renders is byte-identical to SELECT_VIEWPORT_CSS and hashed
    const styles = radixSelectStyles();
    expect(styles.map((s) => s.css)).toEqual([SELECT_VIEWPORT_CSS]);
    expect(runtimeStyleHashes()).toContain(sha256Source(styles[0]?.css ?? ""));
    // nonce mode: the per-response nonce (main.tsx → get-nonce) is stamped on the viewport <style>
    setNonce("n0nce-web08");
    try {
      expect(radixSelectStyles().map((s) => s.nonce)).toEqual(["n0nce-web08"]);
    } finally {
      setNonce("");
    }
  });

  it("sha256Source follows the CSP hash-source grammar", () => {
    // echo -n "" | openssl dgst -sha256 -binary | base64
    expect(sha256Source("")).toBe("'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='");
  });

  it("hash policy: style-src = 'self' + hashes, no nonce, never 'unsafe-inline'; script-src stays 'self'", () => {
    const styleHashes = runtimeStyleHashes();
    const directives = cspDirectives({ nonce: null, styleHashes });
    expect(directives["style-src"]).toEqual(["'self'", ...styleHashes]);
    expect(directives["script-src"]).toEqual(["'self'"]);
    const header = serializeCsp(directives, "header");
    expect(header).not.toMatch(/nonce-|unsafe-inline|unsafe-hashes/);
    expect(header).toContain("frame-ancestors 'none'");
  });

  it("_headers (static host) carries the hash policy and the security headers", () => {
    const styleHashes = runtimeStyleHashes();
    const file = staticHostHeaders(securityHeaders({ nonce: null, styleHashes }));
    expect(file.split("\n")[1]).toBe("/*");
    expect(file).toContain(
      `  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' ${styleHashes.join(" ")};`,
    );
    expect(file).toContain("  X-Content-Type-Options: nosniff");
    expect(file).toContain("frame-ancestors 'none'");
    expect(file).not.toContain(CSP_NONCE_PLACEHOLDER);
  });
});

describe("inline script/style guard (build gate) — 24 §4.4", () => {
  const hashPolicy = cspDirectives({ nonce: null, styleHashes: [sha256Source("a{}")] });
  const noncePolicy = cspDirectives();

  it("the source index.html has no inline script/style/handler", () => {
    const html = readFileSync(path.join(import.meta.dirname, "index.html"), "utf8");
    expect(inlineCspViolations(html, noncePolicy)).toEqual([]);
    expect(inlineCspViolations(html, hashPolicy)).toEqual([]);
  });

  it("external scripts pass; inline scripts never do (script-src 'self')", () => {
    expect(inlineCspViolations('<script type="module" src="/a.js"></script>', hashPolicy)).toEqual([]);
    expect(inlineCspViolations("<script>alert(1)</script>", hashPolicy)).toHaveLength(1);
    expect(
      inlineCspViolations(`<script nonce="${CSP_NONCE_PLACEHOLDER}">x()</script>`, noncePolicy),
    ).toHaveLength(1);
  });

  it("inline <style>: allowed only by a matching hash (hash mode) or the nonce placeholder (nonce mode)", () => {
    expect(inlineCspViolations("<style>a{}</style>", hashPolicy)).toEqual([]);
    expect(inlineCspViolations("<style>b{}</style>", hashPolicy)).toEqual([
      `inline <style> without a matching CSP source: ${sha256Source("b{}")}`,
    ]);
    expect(inlineCspViolations(`<style nonce="${CSP_NONCE_PLACEHOLDER}">b{}</style>`, noncePolicy)).toEqual(
      [],
    );
    expect(
      inlineCspViolations(`<style nonce="${CSP_NONCE_PLACEHOLDER}">b{}</style>`, hashPolicy),
    ).toHaveLength(1);
    expect(inlineCspViolations('<style nonce="other">b{}</style>', noncePolicy)).toHaveLength(1);
  });

  it("style attributes and inline event handlers always fail", () => {
    expect(inlineCspViolations('<div style="color:red"></div>', hashPolicy)).toHaveLength(1);
    expect(inlineCspViolations('<img src="/a.png" onerror="x()">', hashPolicy)).toHaveLength(1);
    // The CSP meta itself (style-src inside a content attribute) is not an inline style.
    const meta = `<meta http-equiv="Content-Security-Policy" content="${serializeCsp(hashPolicy, "meta")}">`;
    expect(inlineCspViolations(meta, hashPolicy)).toEqual([]);
  });
});
