# Spike: Manrope — U+02BB va o'zbek kirill gliflari

**Savol:** 26 #141 / OQ-065 (qaror #57, 27 Bosqich 0 DoD, 08 §2, 24 §4.1). **Sana:** 2026-10-16.
**Test:** `web/apps/shell/e2e/font-glyphs.spec.ts` (Playwright, Chromium, production build — `vite preview`).
**Skrinshot:** `spike-font-chromium-windows.png` (Windows 11, Chromium; 400/700/800 og'irlik).

## Nima tekshirildi

- Shrift: `@fontsource-variable/manrope` 5.3.0, ilovaga bundle qilingan (latin, latin-ext, cyrillic, cyrillic-ext subsetlari), stek `'Manrope Variable', 'Manrope', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`.
- Matnlar: o'zbek lotin U+02BB bilan (`Oʻzbekiston, gʻalaba, maʻno`), o'zbek kirill (`Ўў Ққ Ғғ Ҳҳ`), rus (`Ёё Ъъ Ыы Ээ`, pangramma).
- Usul: (1) `document.fonts.load()` / `check()` — Manrope self-hosted va yuklangan; (2) har belgi kengligi canvas'da Manrope + ikki xil zaxira (monospace / serif) bilan o'lchanadi — kenglik zaxiraga bog'liq bo'lsa, glif Manrope'da yo'q; (3) ilova stekida kenglik > 0 va `.notdef` (tofu) qutisidan farqli; (4) natija woff2 fayllarining `cmap` jadvali bilan alohida tasdiqlandi.

## Natija

- **Manrope'da bor:** butun rus alifbosi, `Ўў` (U+040E/045E), lotin, `—`, `‘ ’` (U+2018/2019).
- **Manrope'da yo'q:** **U+02BB `ʻ`** (va U+02BC), o'zbek kirill **`Ққ Ғғ Ҳҳ`** (U+049A/B, U+0492/3, U+04B2/3). Fontsource CSS `unicode-range`i ularni e'lon qiladi, lekin fayllarda glif yo'q.
- Bu belgilar Windows/Chromium'da `system-ui` (Segoe UI) zaxirasidan chiqadi — **tofu yo'q**, o'qiladi. Lekin skrinshotda uslub farqi ko'rinadi: ayniqsa 700/800 og'irlikda `Ққ Ғғ Ҳҳ` boshqa shriftdan (shakli va qalinligi farqli); `oʻ gʻ` dagi `ʻ` kamroq seziladi.
- Test bu holatni qayd etadi (`KNOWN_MANROPE_GAPS`): ro'yxat o'zgarsa (shrift yangilansa yoki zaxira shrift qo'shilsa) test yiqiladi va bu eslatma yangilanadi.

## Xulosa

Natija **qisman yomon**: o'zbek lotin va rus — joyida; `ʻ` va o'zbek kirillning 6 harfi Manrope'da yo'q. 24 §4.1 / 08 §2 dagi zaxira qoidasi ishga tushadi: Manrope'dan keyin self-hosted Noto Sans subset'i (`@fontsource/noto-sans`, latin-ext + cyrillic-ext; `ʻ` lotin subsetida) stekka qo'shilishi tavsiya etiladi — shunda gliflar har platformada bir xil manbadan keladi, `system-ui` ga bog'liq bo'lmaydi. Qaror (Noto qo'shish yoki `system-ui` bilan qolish) — dizayn/jamoa bilan; qo'shilsa, PWA precache hajmi (+2 woff2) va `KNOWN_MANROPE_GAPS` testi yangilanadi.

**Ochiq qoldiq:** haqiqiy Android (Chrome, Roboto) va iOS (Safari, SF) qurilmalarida ko'rish tekshiruvi — tashqi tekshiruv, CI'da faqat Chromium bor (WebKit o'rnatilmagan).
