import { expect, test } from "@playwright/test";

/**
 * Bosqich 0 font spike (qaror #57, 27 Bosqich 0 DoD, 26 #141 / OQ-065, 08 §2, 24 §4.1).
 * Result: research_notes/ochiq-savollar/spike-font.md.
 *
 * Coverage check per character: the glyph width is measured with Manrope first and two *different*
 * fallbacks (monospace / serif). If Manrope has the glyph the width does not depend on the fallback;
 * if it is missing the fallback decides and the widths differ. Missing glyphs must still render from
 * the app's font stack (08 §2: `system-ui` fallback) as a real glyph — non-zero width, not the
 * .notdef box (compared with a private-use code point no font maps).
 * Chromium only (CI installs chromium); real Android/iOS devices remain an external check.
 */
const SAMPLES = {
  uzLatin: "Oʻzbekiston, oʻqituvchi, gʻalaba, Gʻarb, maʻno — sotuvchi qoʻshdi",
  uzCyrillic: "Ўзбекистон, ўқитувчи, ғалаба, Ғарб, Қўқон, Ҳисоб, ҳа — Ўў Ққ Ғғ Ҳҳ",
  russian: "Съешь же ещё этих мягких французских булок, да выпей чаю. Ёё Ъъ Ыы Ээ",
};
const CHECKED = [
  "ʻ",
  "Ў",
  "ў",
  "Қ",
  "қ",
  "Ғ",
  "ғ",
  "Ҳ",
  "ҳ",
  "Ё",
  "ё",
  "Ъ",
  "ъ",
  "Ы",
  "ы",
  "Э",
  "э",
  "Ж",
  "щ",
  "—",
];
/**
 * Spike finding (@fontsource-variable/manrope 5.3.0, cmap of the woff2 files): Manrope has no U+02BB
 * and no Uzbek Cyrillic Ққ Ғғ Ҳҳ (U+049A/B, U+0492/3, U+04B2/3). If this list changes (font update or
 * a Noto Sans subset added after Manrope, 24 §4.1), update the spike note and this list.
 */
const KNOWN_MANROPE_GAPS = ["ʻ", "Қ", "қ", "Ғ", "ғ", "Ҳ", "ҳ"];
const FAMILY = "'Manrope Variable'";
/** 24 §4.1 / 08 §2 font stack (Tailwind `fontFamily.sans`). */
const STACK = "'Manrope Variable', 'Manrope', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

test.use({ viewport: { width: 1100, height: 520 } });

test("U+02BB (oʻ gʻ), Uzbek Cyrillic and Russian render — Manrope or the system-ui fallback", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "font spike runs on Chromium only");
  await page.route("**/auth/session", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "UNAUTHORIZED", message_key: "x", details: [], request_id: "e2e" },
      }),
    }),
  );
  await page.goto("/login");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  const result = await page.evaluate(
    async ({ samples, checked, family, stack }) => {
      const text = Object.values(samples).join(" ");
      // Load every subset (unicode-range) the samples touch, at the weights the UI uses.
      for (const weight of [400, 700, 800]) await document.fonts.load(`${weight} 32px ${family}`, text);
      await document.fonts.ready;

      const ctx = document.createElement("canvas").getContext("2d");
      if (!ctx) throw new Error("no 2d canvas");
      const width = (font: string, s: string) => {
        ctx.font = font;
        return ctx.measureText(s).width;
      };
      const notdef = width(`32px ${stack}`, "");
      const glyphs = checked.map((ch) => ({
        ch,
        code: `U+${(ch.codePointAt(0) ?? 0).toString(16).toUpperCase().padStart(4, "0")}`,
        manropeFirstMono: width(`32px ${family}, monospace`, ch),
        manropeFirstSerif: width(`32px ${family}, serif`, ch),
        appStack: width(`32px ${stack}`, ch),
      }));
      const loadedSubsets = [...document.fonts]
        .filter((f) => f.family.replaceAll(/["']/g, "") === "Manrope Variable" && f.status === "loaded")
        .map((f) => f.unicodeRange);

      // Visible specimen in the app font stack (screenshot attached to the report).
      const box = document.createElement("div");
      box.id = "font-specimen";
      box.style.cssText = `position:fixed;inset:0;z-index:9999;background:#fff;color:#0f172a;padding:28px;font-family:${stack};`;
      for (const [weight, size] of [
        [400, 22],
        [700, 22],
        [800, 28],
      ] as const) {
        for (const sample of Object.values(samples)) {
          const line = document.createElement("p");
          line.textContent = sample;
          line.style.cssText = `margin:0 0 8px;font-weight:${weight};font-size:${size}px;`;
          box.append(line);
        }
      }
      document.body.append(box);

      return {
        manropeReady: document.fonts.check(`700 16px ${family}`, "Oʻzbek"),
        notdef,
        glyphs,
        loadedSubsets,
        specimenFont: getComputedStyle(box).fontFamily,
      };
    },
    { samples: SAMPLES, checked: CHECKED, family: FAMILY, stack: STACK },
  );

  const screenshot = await page
    .locator("#font-specimen")
    .screenshot({ path: testInfo.outputPath("font-glyphs.png") });
  await testInfo.attach("font-glyphs.png", { body: screenshot, contentType: "image/png" });
  await testInfo.attach("font-glyphs.json", {
    body: JSON.stringify(result, null, 2),
    contentType: "application/json",
  });

  // Manrope itself is self-hosted and loaded (latin + cyrillic subsets at least).
  expect(result.manropeReady).toBe(true);
  expect(result.specimenFont).toContain("Manrope Variable");
  expect(result.loadedSubsets.length).toBeGreaterThanOrEqual(2);

  // Which glyphs Manrope lacks — exactly the documented gaps (Russian, Ўў are Manrope's own).
  const notInManrope = result.glyphs
    .filter((g) => g.manropeFirstMono !== g.manropeFirstSerif)
    .map((g) => g.ch);
  expect(notInManrope).toEqual(KNOWN_MANROPE_GAPS);

  // Every checked character renders as a real glyph in the app stack (fallback included), not tofu.
  for (const g of result.glyphs) {
    expect(g.appStack, `${g.code} width`).toBeGreaterThan(0);
    expect(g.appStack, `${g.code} is not the .notdef box`).not.toBe(result.notdef);
  }
});
