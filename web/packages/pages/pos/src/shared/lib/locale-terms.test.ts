import { describe, expect, it } from "vitest";

import { resources } from "@shared/i18n";

/** UX-10: the uz UI writes «Onlayn» (Latin orthography), never the English «Online». */
describe("uz terminology", () => {
  it("no «Online» in the uz pos / common texts", () => {
    const uz = JSON.stringify([resources.uz.pos, resources.uz.common]);
    expect(uz).not.toMatch(/"Online\b/);
    expect(resources.uz.pos.shell.onlineSynced).toMatch(/^Onlayn/);
  });
});
