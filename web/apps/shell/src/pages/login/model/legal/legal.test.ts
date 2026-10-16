import { describe, expect, it } from "vitest";

import type { TermsVersionOut } from "@shared/models";

import { legalLinksOf, safeDocumentUrl } from "./index.ts";

const doc = (kind: TermsVersionOut["kind"], text_url: string): TermsVersionOut => ({
  kind,
  version: "1.0",
  text_url,
  text_sha256: "a".repeat(64),
  effective_from: "2026-10-01",
});

describe("BO-01 legal links from GET /auth/terms", () => {
  it("accepts same-origin paths and https URLs only", () => {
    expect(safeDocumentUrl("/legal/terms.html")).toBe("/legal/terms.html");
    expect(safeDocumentUrl("https://erp.uz/legal/privacy")).toBe("https://erp.uz/legal/privacy");
    expect(safeDocumentUrl("javascript:alert(1)")).toBeNull();
    expect(safeDocumentUrl("//evil.example/x")).toBeNull();
    expect(safeDocumentUrl("http://erp.uz/terms")).toBeNull();
    expect(safeDocumentUrl("")).toBeNull();
    expect(safeDocumentUrl(undefined)).toBeNull();
  });

  it("needs both the terms and the privacy document", () => {
    expect(legalLinksOf([doc("terms", "/t.html"), doc("privacy", "/p.html")])).toEqual({
      terms: "/t.html",
      privacy: "/p.html",
    });
    expect(legalLinksOf([doc("terms", "/t.html")])).toBeNull();
    expect(legalLinksOf([doc("terms", "/t.html"), doc("privacy", "javascript:x")])).toBeNull();
  });
});
