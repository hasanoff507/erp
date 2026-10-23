/**
 * Search tokens for the multiEntry `*tokens` indexes (catalog, customers): lower-cased words of the
 * searchable fields. Queries match word prefixes (`where("tokens").startsWith(q)`), so "kola" finds
 * "Coca Kola 1L" and "1l" finds it too. Apostrophe variants of Uzbek Latin are folded to "'".
 */
const APOSTROPHES = /[ʻʼ‘’`]/g;
const SEPARATORS = /[\s,.;:/\\|()[\]{}"«»\-_+*#]+/;

export function normalizeSearch(text: string): string {
  return text.toLocaleLowerCase("en-US").replace(APOSTROPHES, "'").trim();
}

export function searchTokens(...fields: (string | null | undefined)[]): string[] {
  const out = new Set<string>();
  for (const field of fields) {
    if (!field) continue;
    const normalized = normalizeSearch(field);
    for (const word of normalized.split(SEPARATORS)) if (word) out.add(word);
  }
  return [...out];
}

/** Query words (every word must match a token prefix). */
export function queryWords(query: string): string[] {
  return normalizeSearch(query).split(SEPARATORS).filter(Boolean);
}
