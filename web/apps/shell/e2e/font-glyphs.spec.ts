import { expect, test } from "@playwright/test";

/**
 * Bosqich 0 font spike → G-02 (qaror #57, 27 Bosqich 0 DoD, 26 #141 / OQ-065, 08 §2, 24 §4.1).
 * Spike: research_notes/ochiq-savollar/spike-font.md.
 *
 * Manrope lacks U+02BB/U+02BC and Uzbek Cyrillic Ққ Ғғ Ҳҳ; a self-hosted Noto Sans fallback
 * (apps/shell/src/noto-sans-fallback.css, narrow unicode-range) sits right after Manrope in the stack.
 * Coverage check per character: the glyph width is measured with the bundled pair (Manrope, Noto)
 * first and two *different* generic fallbacks (monospace / serif). If a bundled font has the glyph
 * the width does not depend on the generic fallback; if neither has it, the system font decides and
 * the widths differ. So every checked character must come from a real, self-hosted font — never
 * from system-ui and never the .notdef box.
 * Chromium only (CI installs chromium); real Android/iOS devices remain an external check.
 */
const SAMPLES = {
  uzLatin: "Oʻzbekiston, oʻqituvchi, gʻalaba, Gʻarb, maʻno — sotuvchi qoʻshdi, taʼlim",
  uzCyrillic: "Ўзбекистон, ўқитувчи, ғалаба, Ғарб, Қўқон, Ҳисоб, ҳа — Ўў Ққ Ғғ Ҳҳ",
  russian: "Съешь же ещё этих мягких французских булок, да выпей чаю. Ёё Ъъ Ыы Ээ",
};
const CHECKED = [
  "ʻ",
  "ʼ",
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
/** Glyphs Manrope (@fontsource-variable/manrope 5.3) does not have — served by the Noto fallback. */
const NOTO_GLYPHS = ["ʻ", "ʼ", "Қ", "қ", "Ғ", "ғ", "Ҳ", "ҳ"];
const MANROPE = "'Manrope Variable'";
const NOTO = "'Noto Sans Variable'";
/** 24 §4.1 / 08 §2 font stack (Tailwind `fontFamily.sans`). */
const STACK =
  "'Manrope Variable', 'Manrope', 'Noto Sans Variable', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
const WEIGHTS = [400, 700, 800];
/** Hex code point without Number.parseInt (no-restricted-syntax, qaror #57). */
const hex = (digits: string) =>
  [...digits.toLowerCase()].reduce((n, ch) => n * 16 + "0123456789abcdef".indexOf(ch), 0);
/** Code points of a CSSFontFace.unicodeRange ("U+2BB-2BC, U+492-493") — format-independent. */
function codePoints(range: string): number[] {
  return range.split(",").flatMap((part) => {
    const [from = "", to] = part.trim().replace(/^U\+/i, "").split("-");
    const start = hex(from);
    const end = to ? hex(to) : start;
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  });
}

test.use({ viewport: { width: 1100, height: 520 } });

test("ʻ ʼ (oʻ gʻ), Uzbek Cyrillic and Russian render from self-hosted fonts — Manrope + Noto", async ({
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
  const fontRequests: string[] = [];
  page.on("request", (req) => {
    if (req.resourceType() === "font") fontRequests.push(new URL(req.url()).pathname);
  });
  await page.goto("/login");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  const result = await page.evaluate(
    async ({ samples, checked, notoGlyphs, manrope, noto, stack, weights }) => {
      const text = Object.values(samples).join(" ");
      // Load every face (unicode-range) the samples touch, at the weights the UI uses.
      for (const weight of weights) {
        await document.fonts.load(`${weight} 32px ${manrope}`, text);
        await document.fonts.load(`${weight} 32px ${noto}`, notoGlyphs.join(""));
      }
      await document.fonts.ready;

      const ctx = document.createElement("canvas").getContext("2d");
      if (!ctx) throw new Error("no 2d canvas");
      const width = (font: string, s: string) => {
        ctx.font = font;
        return ctx.measureText(s).width;
      };
      // Private-use code point no font maps → the .notdef (tofu) width.
      const notdef = width(`32px ${stack}`, "");
      const bundled = `${manrope}, ${noto}`;
      const glyphs = weights.flatMap((weight) =>
        checked.map((ch) => ({
          ch,
          weight,
          code: `U+${(ch.codePointAt(0) ?? 0).toString(16).toUpperCase().padStart(4, "0")}`,
          // Manrope alone: depends on the generic fallback ⇔ Manrope lacks the glyph.
          manropeMono: width(`${weight} 32px ${manrope}, monospace`, ch),
          manropeSerif: width(`${weight} 32px ${manrope}, serif`, ch),
          // Manrope + Noto: must never depend on the generic fallback.
          bundledMono: width(`${weight} 32px ${bundled}, monospace`, ch),
          bundledSerif: width(`${weight} 32px ${bundled}, serif`, ch),
          appStack: width(`${weight} 32px ${stack}`, ch),
        })),
      );
      const faces = (family: string) =>
        [...document.fonts].filter((f) => f.family.replaceAll(/["']/g, "") === family);

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
        manropeReady: document.fonts.check(`700 16px ${manrope}`, "Oʻzbek"),
        notoReady: weights.every((w) => document.fonts.check(`${w} 16px ${noto}`, notoGlyphs.join(""))),
        notdef,
        glyphs,
        loadedManropeSubsets: faces("Manrope Variable")
          .filter((f) => f.status === "loaded")
          .map((f) => f.unicodeRange),
        notoFaces: faces("Noto Sans Variable").map((f) => ({ range: f.unicodeRange, status: f.status })),
        specimenFont: getComputedStyle(box).fontFamily,
      };
    },
    {
      samples: SAMPLES,
      checked: CHECKED,
      notoGlyphs: NOTO_GLYPHS,
      manrope: MANROPE,
      noto: NOTO,
      stack: STACK,
      weights: WEIGHTS,
    },
  );

  const screenshot = await page
    .locator("#font-specimen")
    .screenshot({ path: testInfo.outputPath("font-glyphs.png") });
  await testInfo.attach("font-glyphs.png", { body: screenshot, contentType: "image/png" });
  await testInfo.attach("font-glyphs.json", {
    body: JSON.stringify({ ...result, fontRequests }, null, 2),
    contentType: "application/json",
  });

  // Manrope is self-hosted and loaded (latin + cyrillic subsets at least); the app uses the stack.
  expect(result.manropeReady).toBe(true);
  expect(result.specimenFont).toContain("Manrope Variable");
  expect(result.specimenFont).toContain("Noto Sans Variable");
  expect(result.loadedManropeSubsets.length).toBeGreaterThanOrEqual(2);

  // Noto: two loaded faces whose unicode-range is exactly the Manrope gaps — nothing more.
  expect(result.notoReady).toBe(true);
  expect(result.notoFaces).toHaveLength(2);
  expect(result.notoFaces.every((f) => f.status === "loaded")).toBe(true);
  const notoCodePoints = result.notoFaces.flatMap((f) => codePoints(f.range)).sort((a, b) => a - b);
  expect(notoCodePoints).toEqual(NOTO_GLYPHS.map((ch) => ch.codePointAt(0) ?? 0).sort((a, b) => a - b));
  // Self-hosted: the Noto files come from our own /assets (CSP font-src 'self').
  const notoFiles = fontRequests.filter((p) => p.includes("noto-sans"));
  expect(notoFiles).toHaveLength(2);
  for (const file of notoFiles) expect(file).toMatch(/^\/assets\/noto-sans-[\w-]+\.woff2$/);

  for (const g of result.glyphs) {
    const id = `${g.code} @${g.weight}`;
    // Manrope still renders every glyph it has; Noto fills exactly the documented gaps.
    expect(g.manropeMono !== g.manropeSerif, `${id}: Manrope gap`).toBe(NOTO_GLYPHS.includes(g.ch));
    // Every checked character comes from a bundled font — not system-ui, not tofu.
    expect(g.bundledMono, `${id}: rendered by Manrope/Noto, not a system font`).toBe(g.bundledSerif);
    expect(g.appStack, `${id} width`).toBeGreaterThan(0);
    expect(g.appStack, `${id} is not the .notdef box`).not.toBe(result.notdef);
  }
});
