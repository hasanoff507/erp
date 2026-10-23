/**
 * BO-01 footer «Foydalanish shartlari» / «…siyosati» — real documents from GET /auth/terms (`text_url`,
 * like BO-21 ②). Until the list loads (or when it fails) the sentence is not shown: no dead `#terms`
 * links. Only same-origin paths or https URLs become links.
 */
import { createEffect, createEvent, createStore, sample } from "effector";

import { api } from "@shared/api";
import type { TermsVersionOut } from "@shared/models";

export interface LegalLinks {
  terms: string;
  privacy: string;
}

/** `/legal/terms.html` or `https://…` → itself; anything else (javascript:, //host, http:) → null. */
export function safeDocumentUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  if (value.startsWith("/") && !value.startsWith("//") && !value.includes("\\")) return value;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

/** Both documents are needed for the sentence; either missing → null (the footer hides it). */
export function legalLinksOf(items: readonly TermsVersionOut[]): LegalLinks | null {
  const terms = safeDocumentUrl(items.find((i) => i.kind === "terms")?.text_url);
  const privacy = safeDocumentUrl(items.find((i) => i.kind === "privacy")?.text_url);
  return terms && privacy ? { terms, privacy } : null;
}

export const legalLinksRequested = createEvent();
export const loadLegalLinksFx = createEffect(async () => {
  const res = await api.auth.termsCurrent({ erpPublic: true });
  return legalLinksOf(res.items);
});
export const $legalLinks = createStore<LegalLinks | null>(null, { skipVoid: false });

sample({
  clock: legalLinksRequested,
  source: { links: $legalLinks, pending: loadLegalLinksFx.pending },
  filter: ({ links, pending }) => links === null && !pending,
  target: loadLegalLinksFx,
});
$legalLinks.on(loadLegalLinksFx.doneData, (_, links) => links);
