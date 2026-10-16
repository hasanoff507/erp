# Veb frontend arxitekturasi (back-office + veb-kassa)

**Maqsad:** Frontend (back-office + veb-kassa) papka strukturasi, holat boshqaruvi (Effector), API qatlami, kutubxona tanlovlari va platforma/chop etish strategiyasini belgilash.
**Kim uchun:** Frontend ishlab chiquvchi.
**Bog'liq fayllar:** `14-autentifikatsiya-oauth2.md`, `16-offline-sync.md`, `06-ekranlar-umumiy.md`, `07-ekran-tafsilotlari.md`, `08-dizayn-tizimi.md` (tokenlar, komponentlar, §13 chek shabloni), `design/USLUB.md`, `21-integratsiyalar.md` (§1 fiskal, §9.2/§9.4 karta terminali, §16 Do'kon agenti), `12-db-sxema.md` (`app.card_terminals`, `app.card_terminal_transactions`), `18-api-kassa.md` (§4.1 `card_result`), `25-nofunksional-talablar.md`, `33-1c-integratsiya.md` (§13 BO-22/BO-23), `01-qarorlar.md` #21, #57, #60, #71.
**Holat:** joriy, 2026-10-16.

*Stack: React + Vite + TypeScript, FSD strukturasi, Effector, shadcn/ui, iloji boricha tayyor kutubxonalar. Namuna loyiha: `E:/Project/monorepo/projects/metadata management/src/client` (bundan keyin — "namuna").*

## Asosiy xulosalar

1. **Struktura namunadagidek**: Turborepo monorepo — `apps/shell` (yagona kirish nuqtasi, router, layout, auth) + `packages/pages/*` (har bir sahifa guruhi alohida paket) + `packages/shared/*` (api, models, state, ui, i18n, lib). Har sahifa ichida FSD: `model/` va `ui/`.
2. **Effector modeli namunadagi tartibda**: har bir `model/` papkasi `events/`, `stores/`, `effects/`, `connections/` (faqat `sample` bilan bog'lash), `types/`, `lib/` dan iborat. UI faqat `useUnit` orqali store o'qiydi va event chaqiradi; API'ni hech qachon to'g'ridan-to'g'ri chaqirmaydi.
3. **API qatlami namunadagidek**: `packages/shared/api` — bitta axios instance, interceptorlar (auth, CSRF, xato), har domen uchun funksiyalar fayli. Farqi: **tiplar va API funksiyalari FastAPI'ning OpenAPI sxemasidan avtomatik generatsiya qilinadi** (qo'lda yozilmaydi).
4. **UI — shadcn/ui** (Radix + Tailwind CSS). Namunadagi Mantine o'rniga. Jadval — TanStack Table (shadcn data-table), forma — react-hook-form + zod. Vizual uslub — `design/USLUB.md` tokenlari (`08-dizayn-tizimi.md`) Tailwind presetiga xaritalangan (§4.3); shrift Manrope ilova bilan bundle qilinadi (§4.1), ikonlar — lucide-react (§4.2).
5. **Qo'lda yozish o'rniga kutubxona** — har bir vazifa uchun tanlangan kutubxona quyidagi jadvalda; yangi narsa qo'shishdan oldin avval shu ro'yxat va keyin tayyor kutubxona qidiriladi.
6. **Veb-kassa offline ishlaydi**: PWA (vite-plugin-pwa) + IndexedDB (Dexie) + append-only outbox; tafsiloti `16-offline-sync.md` da.
7. Namunadagi kamchiliklar takrorlanmaydi: `console.log` qoldirilmaydi, sana formatlash qo'lda yozilmaydi (dayjs), xato xabari `JSON.stringify` bilan foydalanuvchiga ko'rsatilmaydi (tarjima qilingan matn).
8. **Chop etish va uskunalar (§6)**: printer transporti qurilmaga qarab tanlanadi — USB (Web Serial/WebUSB), HTTP LAN printer (Epson ePOS/Star WebPRNT), xom TCP 9100 LAN printer — faqat **Do'kon agenti** orqali (qaror #60), bulut printer (Star CloudPRNT/Epson SDP), tizim printeri; standart — bosma chek, elektron chek — zaxira. Lokal fiskal ko'prik rejimida kassa platformasi — Windows PK + Do'kon agenti; iOS kassa — faqat fiskal hamkorning bulut rejimida. Karta to'lovi — `CardTerminalPort` (§6.5, qaror #71): Windows veb-kassada Do'kon agenti orqali bank terminaliga, MVP'da `FakeCardTerminalAdapter`; `purchase` hech qachon avtomatik takrorlanmaydi.
9. **Autentifikatsiya — BFF (Backend-for-Frontend) naqshi, OAuth 2.0 token hech qachon brauzer JS'iga chiqmaydi**: login `features/auth-provider` orqali backend'ning `/auth/login`iga POST qiladi, backend ichida OAuth Authorization Code+PKCE almashinuvini bajaradi va faqat `HttpOnly` sessiya cookie qaytaradi; access/refresh token faqat serverda. To'liq protokol — `14-autentifikatsiya-oauth2.md`. Login sahifasi obuna muddati tugagan holatni alohida ko'rsatadi (to'lov havolasi bilan).

---

## 1. Papka strukturasi

```
web/                                  # Turborepo (npm workspaces)
├── apps/
│   └── shell/                        # yagona Vite ilova
│       └── src/
│           ├── app/                  # providerlar, router, layout, global stillar
│           │   ├── router/
│           │   └── ui/layout/  ui/sidebar/
│           ├── features/             # ilova darajasidagi: auth-provider (BFF login/logout, cookie, OAuth brauzerga chiqmaydi — 14-autentifikatsiya-oauth2.md), protected-route, tenant-switcher
│           └── main.tsx
├── packages/
│   ├── pages/                        # har biri alohida paket (@pages/*)
│   │   ├── pos/                      # veb-kassa (POS-01…16)
│   │   ├── catalog/                  # tovarlar, narxlar, yorliqlar (M09)
│   │   ├── warehouse/                # qoldiq, kirim, ko'chirish, inventarizatsiya (M04-M07)
│   │   ├── debts/                    # qarz daftari (M08)
│   │   ├── finance/                  # xarajatlar, kassa harakati, buxgalteriya, QQS, bank tushumi tasdig'i — `bank-settlements` (BO-24) (M10, M11, M15, M16)
│   │   ├── reports/                  # hisobotlar, dashboard (M12)
│   │   ├── settings/                 # do'kon, xodimlar/huquqlar, filiallar, integratsiyalar, Telegram (M13, M14, M18)
│   │   ├── billing/                  # tarif va to'lov, ro'yxatdan o'tish (M17)
│   │   ├── ai-assistant/             # AI chat (AI-01), OCR tasdiqlash (AI-03)
│   │   └── onec/                     # 1C integratsiyasi (M19, Bosqich 7): `onec-settings` (BO-22), `onec-exports` (BO-23) — §1.1
│   └── shared/
│       ├── api/                      # axios instance, interceptorlar, GENERATSIYA qilingan klient
│       ├── models/                   # GENERATSIYA qilingan tiplar (OpenAPI) + qo'shimcha domen tiplari
│       ├── state/                    # global Effector modellari: user, tenant, branch, shift, online-status
│       ├── ui/                       # shadcn/ui komponentlari (components/ui) + umumiy kompozitlar
│       ├── i18n/                     # i18next: uz (lotin, asosiy), ru
│       ├── offline/                  # Dexie baza, outbox, sync (faqat pos va kerakli sahifalar ishlatadi)
│       ├── lib/                      # formatlash, pul, shtrix-kod/og'irlik kodi parser (scanner), printer adapterlari (printer), fiskal port klienti (fiscal), karta terminali porti va adapterlari (cardTerminal, §6.5), Do'kon agenti lokal klienti (agent)
│       └── config/                   # eslint-config, typescript-config, tailwind preset
└── turbo.json
```

Har bir `@pages/*` paketi ichida (namunadagi `packagess/pages/list-metadata/src` kabi):

```
src/
├── app/                 # paket routeri (index.tsx eksport qiladi)
├── pages/
│   └── <sahifa>/        # masalan debt-book, debtor-detail
│       ├── model/
│       │   ├── events/      index.ts — createEvent
│       │   ├── stores/      index.ts — createStore, pending(), combine()
│       │   ├── effects/     index.ts — createEffect, faqat @shared/api funksiyasini chaqiradi
│       │   ├── connections/ index.ts — FAQAT sample/split/attach — biznes oqimi shu yerda
│       │   ├── types/
│       │   ├── lib/         toza funksiyalar (React'siz)
│       │   └── index.ts     hammasini qayta eksport
│       └── ui/
│           ├── page/        Page.tsx — pageMounted chaqiradi, bo'limlarni yig'adi; { route, Page } eksport
│           ├── header/  main/  dialogs/  ...
├── features/            # bir nechta sahifada ishlatiladigan amal: add-debt, accept-payment, print-label
├── entities/            # domen obyektlari UI+model: product-card, customer-badge, money
└── shared/              # paketga xos constants/routes/ui
```

### 1.1. 1C integratsiyasi va bank tushumi sahifalari (marshrutlar)

| Ekran | Paket / sahifa | Route | Ruxsat (`ProtectedRoute`) | Ma'lumot manbai |
|---|---|---|---|---|
| BO-22 — 1C integratsiyasi sozlamalari va moslashtirish | `@pages/onec` → `pages/onec-settings` | `/app/settings/onec` (`?tab=computer\|bases\|checks\|mapping\|settings\|log`); ulash — `/app/settings/onec/pair?user_code=` | `onec.view` (o'zgartirish — `onec.settings.manage`, `onec.mapping.edit`, `onec.refs.create`; avto-tasdiq — faqat Egasi) | W-01…W-33, W-53; agent holati W-55 — `patronum/interval` 30 s |
| BO-23 — 1C ga yuborish (kunlar) | `@pages/onec` → `pages/onec-exports` | `/app/onec/exports`, `/app/onec/exports/:batchId` | `onec.view` (`onec.export.prepare` / `.approve` / `.correct` — `<Can>` bilan tugma darajasida) | W-34…W-51, W-55; progress — `patronum/interval` **2 s**, faqat `queued/sending/verifying` holatida (SSE — keyinroq) |
| BO-24 — Bank tushumi tasdig'i (`bank_settlements`, 5710 → 5110) | `@pages/finance` → `pages/bank-settlements` | `/app/finance/bank-settlements`, `/app/finance/bank-settlements/:id` | `bank_settlements.manage` (Egasi, Buxgalter) | `/bank-settlements` (ro'yxat, yaratish, `post`, `cancel`) — `13-provodka-qoidalari.md` §2.18a |

BO-22/BO-23 Bosqich 7 da (`27-backlog.md`), BO-24 — moliya bosqichida. Matnlar i18next `onec.*` (uz/ru), `ONEC_*` xato kodlari `errors.onec.*`, tuzatish maslahatlari `fix_hints.onec.*` (`33-1c-integratsiya.md` §12). BO-23 dagi tasdiq effekti `preview_hash` va `acknowledged_warnings` ni yuboradi; `409 ONEC_PREVIEW_CHANGED` — forma xatosi emas: yangi preview qayta yuklanadi va «Ma'lumot o'zgardi» banneri ko'rsatiladi. 1C sahifalari faqat back-office'da (offline'da faqat ko'rish), `@shared/offline` ishlatilmaydi.

**Import qoidalari (FSD):** `app → pages → features → entities → shared`, faqat pastga. Sahifalar bir-birini import qilmaydi. Paketlararo faqat `@shared/*`. Paket ichida `#/*` alias (namunadagidek `"imports": {"#*": "./src/*"}`). ESLint'da `eslint-plugin-boundaries` (yoki `@feature-sliced/eslint-config`) bilan majburlanadi.

## 2. Effector naqshi (namunadan, ERP misolida)

```ts
// pages/debts/src/pages/debt-book/model/events/index.ts
export const pageMounted = createEvent();
export const searchChanged = createEvent<string>();
export const paymentSubmitted = createEvent<AcceptPaymentBody>();

// model/effects/index.ts
export const getDebtorsFx = createEffect((q: DebtorsQuery) => api.debts.listDebtors(q));
export const acceptPaymentFx = createEffect((b: AcceptPaymentBody) => api.debts.acceptPayment(b));

// model/stores/index.ts
export const $query = createStore<DebtorsQuery>({ page: 1, size: 20, search: "" });
export const $debtors = createStore<DebtorPage | null>(null);
export const $loading = pending([getDebtorsFx]);           // patronum

// model/connections/index.ts
sample({ clock: [pageMounted, $query, acceptPaymentFx.done], source: $query, target: getDebtorsFx });
sample({ clock: getDebtorsFx.doneData, target: $debtors });
sample({ clock: searchChanged, source: $query, fn: (q, search) => ({ ...q, search, page: 1 }), target: $query });
sample({ clock: paymentSubmitted, target: acceptPaymentFx });
sample({ clock: acceptPaymentFx.done, fn: () => ({ title: t("debts.paid") }), target: showToastFx });
```

Qoidalar:
- Komponentda `useEffect` faqat `pageMounted()` uchun; boshqa mantiq `connections` da.
- Qidiruv kechiktirish — `patronum/debounce`; davriy yangilash — `patronum/interval`; yuklanish — `patronum/pending`.
- Formalar: react-hook-form + zod; `onSubmit` faqat event chaqiradi.
- Global holat (`@shared/state`): `$user`, `$tenant`, `$activeBranch`, `$activeShift`, `$isOnline`, `$permissions`, `$agentStatus` (Do'kon agenti, §6.4).
- Huquq tekshiruvi: route darajasida `ProtectedRoute` (namunadagi `CheckRole` o'rniga ruxsatlar ro'yxati asosida, `$permissions`), tugma darajasida `<Can permission="debts.forgive">`.

## 3. API qatlami

- **Generatsiya:** FastAPI `/openapi.json` → **orval** (axios mutator bilan) → `@shared/api/generated` (funksiyalar) va `@shared/models/generated` (tiplar). `npm run api:gen` buyrug'i; CI'da sxema o'zgarsa generatsiya qayta tekshiriladi. Shu bilan backend va frontend tiplari doim mos. orval: `client: "axios-functions"`, `mode: "tags-split"`, `mutator` — umumiy axios instance; `override.operationName` `operation_id`dagi teg prefiksini olib tashlaydi (`debts_list_debtors` → `listDebtors`). `@shared/api/index.ts`: `export * as debts from "./generated/debts/debts";` — bundan `api.debts.listDebtors(...)` kelib chiqadi (qo'lda o'ram kodi yo'q, faqat ESM namespace re-export).
- **Instance** (namunadagi `_base` kabi): `withCredentials: true` (HttpOnly sessiya cookie), interceptorlar: CSRF tokeni (`GET /auth/csrf` dan, xotirada keshlanadi — namunadagi `getCsrfToken`) (POST/PUT/PATCH/DELETE), `X-Tenant-Id` emas — tenant sessiyadan olinadi, `X-Branch-Id` (tanlangan filial), `Idempotency-Key` (barcha yozuvchi so'rovlarda — offline qayta yuborishda takror yozuvdan himoya), `Accept-Language`.
- **Xatolar:** 401 → BFF avval jim refresh qiladi (`14-autentifikatsiya-oauth2.md` §7), muvaffaqiyatsiz bo'lsa qayta autentifikatsiya oynasi (POS'da outbox/Dexie saqlanadi; to'liq logout faqat foydalanuvchi tanlovi bilan); 403 `PERMISSION_DENIED` → "huquq yo'q"; **403 `SUBSCRIPTION_RESTRICTED`** → `/login?reason=subscription_expired`ga yo'naltirish, login sahifasida "Obuna muddati tugagan" banner + Click/Payme to'lov havolasi (javobdagi `pay_url`/`amount_due` bilan, `14-autentifikatsiya-oauth2.md` §16) — to'lov o'tgach kirish darhol tiklanadi; 409/422 → forma maydonlariga xato (zod bilan bir xil format); tarmoq xatosi → `$isOnline=false` va kassa offline rejimga o'tadi. `409 IDEMPOTENCY_IN_PROGRESS` — forma xatosi emas: effekt `Retry-After`dan keyin xuddi shu kalit bilan avtomatik takrorlanadi (maks. 3 marta). `422 IDEMPOTENCY_KEY_REUSED` — dasturiy xato, Sentry'ga. Foydalanuvchiga xom JSON ko'rsatilmaydi — backend xato kodi i18n kalitiga tarjima qilinadi.
- Runtime konfiguratsiya: `window.__ERP_CONFIG__` (namunadagi `window.metadataApiConfig` kabi) — bitta build turli muhitlarda ishlaydi.

## 4. Kutubxonalar (qo'lda yozish o'rniga)

| Vazifa | Kutubxona | Izoh |
|---|---|---|
| Build / monorepo | Vite, Turborepo, npm workspaces | namunadagidek |
| Holat va API oqimi | effector, effector-react, patronum | namunadagidek |
| HTTP | axios | namunadagidek |
| API tip/klient generatsiyasi | orval (axios mutator bilan) | qo'lda DTO yozilmaydi (26 #58) |
| UI komponentlar | shadcn/ui (Radix UI) + Tailwind CSS | Mantine o'rniga |
| Ikonkalar | lucide-react (nomli import, tree-shaking; `strokeWidth` 1.8 — §4.2) | shadcn standarti; maketlardagi chiziqli ikon uslubiga mos |
| Shrift | @fontsource-variable/manrope (self-hosted woff2 — §4.1) | CDN/Google Fonts yo'q, offline PWA keshida (qaror #57) |
| Jadvallar | @tanstack/react-table + @tanstack/react-virtual | katta ro'yxatlar (tovarlar, cheklar) virtualizatsiya bilan |
| Formalar va validatsiya | react-hook-form + zod + @hookform/resolvers | backend Pydantic xatolari bilan bir xil shakl |
| Routing | react-router-dom | namunadagidek |
| Sana | dayjs (+ uz/ru lokal) | qo'lda formatlash taqiqlanadi |
| Raqam/pul formatlash | `Intl.NumberFormat("uz-UZ")` + kichik `formatMoney` | pul hisob-kitobi frontendda qilinmaydi — backend beradi |
| Xabarlar (toast) | sonner (shadcn) | |
| Grafiklar | recharts (shadcn charts) | dashboard, hisobotlar |
| Sana tanlash | react-day-picker **^9.14** (shadcn calendar; v10 — `@daypicker/react`, v9 moslik API'lari olib tashlangan, alohida sinovdan keyin) | shadcn calendar `date-fns` ni tranzitiv olib keladi — UI formatlash baribir dayjs |
| UUIDv7 (`client_event_id`, lokal hujjat ID) | uuid (`v7()`, ≥10) | `crypto.randomUUID()` faqat v4 beradi — ishlatilmaydi |
| Buyruq paneli / tez qidiruv | cmdk (shadcn command) | kassada tovar qidiruvi |
| Tarjima | i18next + react-i18next | uz (lotin) asosiy, ru |
| Offline baza | Dexie (IndexedDB) | veb-kassa, outbox |
| PWA / offline yuklash | vite-plugin-pwa (Workbox) | |
| Shtrix-kod chizish | bwip-js (MIT; EAN-13, Code128, GS1 DataMatrix — asosiy yorliq renderer) | yorliqlar, ichki kodlar |
| Shtrix-kod skaner | o'z kichik hook'i `useBarcodeWedge` (`shared/lib/scanner`: belgilar orasidagi interval < ~30 ms + Enter suffiksi, input fokusidan mustaqil) | onScan.js 2020 dan beri yangilanmagan — ishlatilmaydi |
| Kamera orqali skaner/foto | @zxing/browser | telefon kamerasi bilan kod o'qish; AI-03 foto |
| Excel eksport/import | exceljs (yoki SheetJS) | boshlang'ich tovar/qarz importi (US-M04-04, US-M08-07) |
| Chop etish (A4, yorliq) | react-to-print | Yorliq — HTML/SVG + `bwip-js` + OS drayveri; chek printeri (ESC/POS) — `shared/lib/printer` adapterlari (Web Serial, WebUSB, HTTP ePOS/WebPRNT, Do'kon agenti orqali xom TCP 9100, bulut printer, tizim printeri) — §6 |
| Testlar | vitest, @testing-library/react, msw, playwright | |
| Kod sifati | eslint + @feature-sliced/eslint-config, prettier, typescript strict | ESLint `no-restricted-syntax` + custom qoida: `Number(`, `parseFloat(`, `parseInt(` va `Money` tipidagi `+ - * /` taqiqlanadi; CI'da `npm audit --audit-level=high`; qat'iy CSP (`default-src 'self'`, `frame-ancestors 'none'`; `connect-src` ga `http://127.0.0.1:<agent port>` qo'shiladi) — qaror #57 |

### 4.1 Shrift — Manrope (ilova bilan bundle)

- Paket: `@fontsource-variable/manrope` (bitta variable woff2, og'irlik o'qi 200–800; ishlatiladigani 400–800 — `08-dizayn-tizimi.md` §2). Ulash `apps/shell/src/main.tsx` da: `import "@fontsource-variable/manrope/wght.css";` — fayllar Vite build'iga (`dist/assets`, hashlangan nom) tushadi; runtime'da CDN/Google Fonts so'rovi yo'q (CSP `default-src 'self'`, qaror #57).
- Subsetlar: **latin, latin-ext, cyrillic, cyrillic-ext** (o'zbek lotin, U+02BB, rus va o'zbek kirill `Ққ Ғғ Ҳҳ Ўў`); `@font-face` `unicode-range` bilan bo'lingan — brauzer faqat kerakli subsetni yuklaydi. Greek/vietnamese fayllari build'dan chiqariladi (Vite `build.rollupOptions` / PWA `globIgnores`).
- `font-display: swap` (Fontsource standarti); `index.html` da latin subset fayli `<link rel="preload" as="font" type="font/woff2" crossorigin>` bilan oldindan yuklanadi (hashlangan nom Vite `transformIndexHtml` plagini orqali qo'yiladi).
- **Offline (POS/PWA)**: vite-plugin-pwa `workbox.globPatterns` ga `**/*.woff2` qo'shiladi — to'rt subset fayli precache'da, internet yo'q holatda va birinchi offline ishga tushishda ham shrift bor.
- Stek (Tailwind `fontFamily.sans`, §4.3): `'Manrope Variable', 'Manrope', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`. Bosqich 0 glif skrinshot-testi (qaror #57) yomon natija bersa — self-hosted Noto Sans subset'i (`@fontsource/noto-sans`, latin-ext + cyrillic-ext) stekka Manrope'dan keyin qo'shiladi.
- Chek/yorliq rastr rejimi (`@shared/lib/printer`, §6.1) canvas'da shu shriftni ishlatadi — chizishdan oldin `document.fonts.load("700 24px 'Manrope Variable'")` kutiladi.

### 4.2 Ikonkalar — lucide-react

- `lucide-react` — faqat **nomli import** (`import { ScanLine, Wifi } from "lucide-react"`), ESM tree-shaking bilan build'ga faqat ishlatilgan ikonlar tushadi. Taqiqlanadi (ESLint `no-restricted-imports`): `import * as Icons from "lucide-react"`, `lucide-react/dynamic` (`DynamicIcon`) va nom bo'yicha runtime qidiruv — ular butun to'plamni bundle'ga qo'shadi.
- Umumiy o'ram `@shared/ui/icon`: `<Icon as={ScanLine} size="md" />` — `strokeWidth={1.8}`, `aria-hidden="true"` standart; o'lchamlar `sm` 16 / `md` 18 / `lg` 20 / `xl` 24 px (`08-dizayn-tizimi.md` §4). Komponentlar lucide ikonini to'g'ridan-to'g'ri emas, shu o'ram orqali chizadi; menyu/to'lov usuli kabi ro'yxatlarda ikonka maydoni komponent havolasi (`LucideIcon` tipi), satr nomi emas.
- Versiya `package.json` da aniq qulflanadi (lucide ikon nomlarini qayta nomlaydi — `08` §4 jadvalidagi nomlar joriy versiyaga mos; yangilashda tekshiriladi).

### 4.3 Tailwind preset — tokenlarga xaritalash

`packages/shared/config/tailwind/preset.ts` — barcha ilova va paketlar shu presetni ishlatadi; qiymatlar faqat `theme.css` CSS o'zgaruvchilaridan (`08` §1), Tailwind konfigida hex yozilmaydi:

```ts
const c = (v: string) => `hsl(var(--${v}) / <alpha-value>)`;
export default {
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: { sans: ["'Manrope Variable'", "Manrope", "system-ui", "-apple-system", "'Segoe UI'", "Roboto", "sans-serif"] },
      colors: {
        background: c("background"), foreground: c("foreground"), "foreground-secondary": c("foreground-secondary"),
        card: { DEFAULT: c("card"), foreground: c("card-foreground") },
        popover: { DEFAULT: c("popover"), foreground: c("popover-foreground") },
        primary: { DEFAULT: c("primary"), foreground: c("primary-foreground"), strong: c("primary-strong"), soft: c("primary-soft"), "soft-border": c("primary-soft-border") },
        secondary: { DEFAULT: c("secondary"), foreground: c("secondary-foreground") },
        muted: { DEFAULT: c("muted"), foreground: c("muted-foreground") },
        accent: { DEFAULT: c("accent"), foreground: c("accent-foreground") },
        destructive: { DEFAULT: c("destructive"), foreground: c("destructive-foreground"), strong: c("destructive-strong"), soft: c("destructive-soft"), border: c("destructive-border") },
        success: { DEFAULT: c("success"), foreground: c("success-foreground"), strong: c("success-strong"), soft: c("success-soft") },
        warning: { DEFAULT: c("warning"), foreground: c("warning-foreground"), strong: c("warning-strong"), soft: c("warning-soft"), border: c("warning-border") },
        info: { DEFAULT: c("info"), foreground: c("info-foreground"), strong: c("info-strong"), soft: c("info-soft") },
        "awaiting-approval": { DEFAULT: c("awaiting-approval"), foreground: c("awaiting-approval-foreground"), strong: c("awaiting-approval-strong"), soft: c("awaiting-approval-soft") },
        offline: { DEFAULT: c("offline"), strong: c("offline-strong"), soft: c("offline-soft"), foreground: c("offline-foreground") },
        "offline-critical": { DEFAULT: c("offline-critical"), strong: c("offline-critical-strong"), soft: c("offline-critical-soft") },
        "fiscal-pending": { DEFAULT: c("fiscal-pending"), strong: c("fiscal-pending-strong"), soft: c("fiscal-pending-soft"), foreground: c("fiscal-pending-foreground") },
        border: c("border"), input: c("input"), ring: c("ring"), divider: c("divider"), track: c("track"),
        "disabled-foreground": c("disabled-foreground"), overlay: c("overlay"),
        sidebar: { DEFAULT: c("sidebar-background"), foreground: c("sidebar-foreground"), "muted-foreground": c("sidebar-muted-foreground"),
                   primary: c("sidebar-primary"), "primary-foreground": c("sidebar-primary-foreground"), accent: c("sidebar-accent"),
                   "accent-foreground": c("sidebar-accent-foreground"), border: c("sidebar-border"), ring: c("sidebar-ring") },
      },
      borderRadius: { sm: "6px", md: "10px", lg: "var(--radius)", xl: "14px", "2xl": "16px", "3xl": "20px" },
      boxShadow: {
        card: "0 1px 2px rgb(15 27 45 / .04), 0 6px 20px rgb(15 27 45 / .05)",
        raised: "0 1px 2px rgb(15 27 45 / .04), 0 10px 28px rgb(15 27 45 / .06)",
        popover: "0 1px 2px rgb(15 27 45 / .04), 0 12px 32px rgb(15 27 45 / .10)",
        dialog: "0 24px 60px rgb(15 27 45 / .30)",
        cta: "0 8px 20px rgb(14 124 102 / .28)",
        "pos-sheet": "0 -8px 24px -4px rgb(15 27 45 / .12)",
        "focus-soft": "0 0 0 4px hsl(var(--primary-soft))",
      },
      fontSize: {
        display: ["46px", { lineHeight: "52px", fontWeight: "800", letterSpacing: "-0.5px" }],
        h1: ["26px", { lineHeight: "34px", fontWeight: "800" }],
        h2: ["17px", { lineHeight: "24px", fontWeight: "700" }],
        kpi: ["28px", { lineHeight: "34px", fontWeight: "800" }],
        money: ["24px", { lineHeight: "32px", fontWeight: "800" }],
        body: ["14px", "20px"], "body-pos": ["16px", "24px"],
        label: ["13px", { lineHeight: "18px", fontWeight: "600" }], small: ["13px", "18px"],
        caption: ["12px", { lineHeight: "16px", fontWeight: "700" }],
        overline: ["11px", { lineHeight: "16px", fontWeight: "700", letterSpacing: "0.6px" }],
        kbd: ["11px", { lineHeight: "14px", fontWeight: "600" }],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
```

`text-display`, `text-kpi`, `text-money` klasslari bilan birga doim `tabular-nums` qo'yiladi (komponent ichida; ESLint/Stylelint emas — `MoneyDisplay`/`KpiCard` kabi komponentlar orqali). `DataTable` raqamli ustun meta'si (`meta.numeric: true`) `text-right tabular-nums` ni avtomatik qo'shadi.

## 5. Veb-kassa (POS) maxsus talablari

- Kassa sahifasi (`@pages/pos`) — to'liq ekran, klaviatura/skaner bilan ishlaydi (F-tugmalar, Enter, Esc), sichqonchasiz ham.
- Ma'lumot manbai: Dexie'dagi lokal katalog (tovarlar, narxlar, mijozlar, qarzlar) — server bilan fon rejimida sinxronlanadi.
- Har bir amal (chek, qaytarish, qarz, kassa pul harakati) — avval Dexie outbox'ga yoziladi, keyin serverga yuboriladi (har voqeada `client_event_id` (UUIDv7) — server `sync_receipts` bilan dedupe qiladi; POS hujjatlari uchun alohida REST endpoint yo'q). Internet holati `$isOnline` da, UI'da doimiy ko'rsatkich.
- Fiskal chek — `@shared/lib/fiscal` (`FiscalPort`, `21` §1): **lokal ko'prik** rejimida POS chekni Do'kon agenti orqali fiskal modulga imzolatadi (internetsiz ham), natija (`fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`, `fiscal_at`) chekka chop etiladi va outbox voqeasiga (`sale.created`, `return.created`, `debt_payment.created`) `fiscal_result` sifatida yoziladi (`18-api-kassa.md` §4.1); **hamkor bulut** rejimida chek server orqali fiskallashtiriladi (`fiscal_receipts.status=pending` → keyingi `/sync/pull`). Ichki chek raqami (`receipt_seq`) qurilmada, outbox yozuvi bilan bir Web Lock ichida beriladi; FM raqami — alohida `fm_receipt_seq`.
- **48 soat shkalasi (qaror #43)**: `ofd_acked_at` bo'lmagan eng eski fiskal chek yoshi bo'yicha — 24 soat 🟡 status panelida, 40 soat 🔴, 46 soat — har yangi chek oldidan yopib bo'lmaydigan modal, 48 soat — savdo bloklanadi (`FISCAL_OFFLINE_48H_BLOCKED`), faqat sinxron/yuborish ishlaydi. `fm_state='locked'` — `FISCAL_DEVICE_LOCKED`.
- Markirovka: chekka qo'shishdan oldin lokal takror-kod nazorati (bitta chekda va avval sotilgan kod — rad); online'da `MARKING_PRECHECK=warn` tekshiruvi (`21` §4).
- Android POS (Kotlin) keyingi bosqichda xuddi shu backend API va sync protokolidan foydalanadi (`28-android-pos.md`).

### 5.1 POS-02 katalog: ko'rinish almashtirgichi va kategoriya tablari

Maket — `design/canvas/project/Main.dc.html`; komponentlar — `08-dizayn-tizimi.md` §7.2 (`SegmentedControl`, `CategoryTabs`, `ProductTile`, `ProductRow`). Model — `@pages/pos` → `pages/sale/model` (§2 naqshi):

| Holat | Store | Qiymat | Saqlanishi |
|---|---|---|---|
| Ko'rinish (Kartochka / Ro'yxat) | `$catalogView` | `"grid" \| "list"`, standart `"grid"` | **Qurilma darajasida** — `device_settings` (kalit `pos.catalog_view`), `printer.transport` bilan bir joyda (§6.1, `07-ekran-tafsilotlari.md` POS-16); `erp-pos` dan alohida Dexie bazasi `erp-device` da, logout'da o'chirilmaydi (`16-offline-sync.md` §12); serverga yuborilmaydi va sinxronlanmaydi |
| Faol kategoriya | `$activeCategoryId` | `string \| null` (`null` — «Hammasi») | Faqat xotirada (Effector store); `pageMounted` da `null` |
| Qidiruv matni | `$catalogQuery` | `string` | Faqat xotirada |

- Oqim: `pageMounted` → `loadDeviceSettingFx("pos.catalog_view")` → `$catalogView` (o'qib bo'lmasa yoki qiymat noto'g'ri — `"grid"`); `catalogViewChanged` → `$catalogView` → `saveDeviceSettingFx` (`patronum/debounce` 300 ms). `device_settings` o'qish/yozish — `@shared/offline` dagi umumiy `deviceSettings` moduli (`get(key)`, `set(key, value)`); komponent Dexie'ga to'g'ridan-to'g'ri murojaat qilmaydi.
- Kategoriya tablari Dexie `catalog` dagi `product_categories` dan quriladi (shu filialda tovari bor kategoriyalar), birinchisi «Hammasi»; `categorySelected(id)` → `$activeCategoryId`. Qidiruv matni bo'sh bo'lmasa filtr barcha kategoriyalar bo'yicha ishlaydi (tanlangan tab ko'rinishda qoladi, lekin ro'yxatni cheklamaydi); qidiruv tozalanganda tab filtri qaytadi. Shtrix-kod skanerlash (`useBarcodeWedge`) katalog holatiga bog'liq emas — tovar to'g'ridan-to'g'ri chekka qo'shiladi.
- `$visibleProducts = combine($catalogQuery, $activeCategoryId, …)` — Dexie so'rovi `lib/` dagi toza funksiya orqali; ikkala ko'rinish ham bir xil ma'lumotni `@tanstack/react-virtual` bilan chizadi (`grid` — 4 ustunli qatorlar, `list` — bir qatorli elementlar).
- Klaviatura: `CategoryTabs` — Radix Tabs (`←`/`→` bilan tab almashadi); ko'rinish almashtirgichi `aria-pressed` tugmalari; `F1` har doim skaner/qidiruv maydoniga fokus qaytaradi (`08` §9).

## 6. Qo'llab-quvvatlanadigan platformalar, chop etish va uskunalar

### 6.1 Chop etish transportlari

`@shared/lib/printer` — bitta `PrinterPort` (`printReceipt(doc)`, `printLabel(doc)`, `status()`), sozlama `printer.transport` (qurilma darajasida — alohida Dexie bazasi `erp-device`, `device_settings`; logout'da saqlanadi, `16-offline-sync.md` §12; kalitlar — `printer.transport`, `printer.paper_width`, `printer.codepage`, `printer.render_mode`, `printer.lan_address` (`agent_raw`/`http_*` uchun IPv4:port), `printer.cloud_id`; `07-ekran-tafsilotlari.md` POS-16) va transport adapterlari:

| `printer.transport` | Adapter | Qaysi printer | Brauzer/platforma | Cheklov |
|---|---|---|---|---|
| `webserial` | `WebSerialPrinterAdapter` | USB printer virtual COM bilan (CH340/CP2102/FTDI) | Chrome/Edge desktop 89+ | Port bir marta tanlanadi, `getPorts()` eslab qoladi |
| `webusb` | `WebUsbPrinterAdapter` | USB printer (printer klassi `0x07` WebUSB'da bloklanmagan) | Chrome/Edge desktop, Chrome Android | Windows'da `usbprint` drayveri interfeysni egallasa `claimInterface` xatosi — onboarding'da Zadig/WinUSB yo'riqnomasi; Android'da odatda muammo yo'q |
| `webbluetooth` | `WebBluetoothPrinterAdapter` | Faqat BLE/GATT printerlar | Chrome desktop/Android | Klassik Bluetooth SPP (ko'p arzon 58 mm printerlar) **ishlamaydi** — tavsiya etilmaydi |
| `http_epos` / `http_webprnt` | `EposPrinterAdapter` / `WebPrntPrinterAdapter` | HTTP qabul qiluvchi LAN printerlar — Epson ePOS-Print (TM-m30 seriyasi), Star WebPRNT | Chrome/Edge | Chrome 142+ — sahifa lokal tarmoq qurilmasiga birinchi murojaatda foydalanuvchidan ruxsat so'raydi (Local Network Access) |
| `agent_raw` | `AgentRawPrinterAdapter` | **Xom TCP 9100 (ESC/POS) LAN printerlar** — Xprinter, Rongta va b. (bozordagi arzon LAN printerlarning aksariyati) | Faqat **Windows PK + Do'kon agenti** (qaror #60) | Brauzer xom TCP ocha olmaydi (Direct Sockets faqat Isolated Web Apps); baytlar agent lokal API'siga (`127.0.0.1`) yuboriladi, agent `host:9100` ga uzatadi (`21` §16) |
| `cloud` | `CloudPrintAdapter` | Star CloudPRNT (TSP143IV, mC-Print), Epson Server Direct Print (TM-m30III) | Har qanday brauzer, **iOS uchun yagona to'g'ridan-to'g'ri yo'l** | Frontend faqat chop etish ishini serverga navbatga qo'yadi; printer o'zi serverni so'raydi: `/print/cloudprnt` (Star CloudPRNT HTTP, standart 5 s), `/print/epson-sdp` (Epson SDP, ePOS-Print XML); do'konda kiruvchi port kerak emas. Sunmi bulut printeri (o'z API'si) — MVP'dan keyin alohida adapter |
| `system_print` | `SystemPrintAdapter` | OS drayveri o'rnatilgan har qanday printer | Barcha brauzerlar | `window.print()` / tizim dialogi; chek uchun eng sekin, zaxira |

**Avto-tanlov** (birinchi sozlashda, keyin saqlanadi): `agent_raw` (agent topilsa va LAN printer sozlangan bo'lsa) → `webserial` → `webusb` → `http_*` → `cloud` → `system_print`. Hech biri ishlamasa — **elektron chek zaxirasi**: ekranda `ofd.soliq.uz` QR havolasi, Telegram yoki SMS havola; standart — bosma chek, elektron faqat printer ishlamay qolganda yoki xaridor o'zi so'raganda, kassir tasdig'i bilan (`fiscal_receipts.delivery='electronic'` + `delivery_reason`, `21` §1).

**Chek kodlash**: `printer.codepage="cp866"` (ESC t 17); CP866/CP1251 da Ў/ў bor, lekin **Қ/Ғ/Ҳ yo'q** va U+02BB (ʻ) hech qaysi kod sahifasida yo'q — chek matnida o'zbek kirill harflari bo'lsa `printer.render_mode="raster"` avtomatik yoqiladi (matn canvas'da chiziladi, ESC/POS rastr buyrug'i bilan yuboriladi); lotin matnda U+02BB → `'` almashtiriladi. Test matni: "Ўзбекистон Қўқон Ғалла Ҳисоб / Oʻzbekiston gʻalla". Chek shabloni — `08-dizayn-tizimi.md` §13.

### 6.2 Platforma matritsasi

| Platforma | Veb-kassa | Chop etish | Fiskal modul (`21` §1) |
|---|---|---|---|
| **Windows PK — Chrome/Edge** (asosiy kassa platformasi) | To'liq — o'rnatilgan PWA, `navigator.storage.persist()` | `agent_raw`, `webserial`, `webusb`, `http_*`, `cloud`, `system_print` | Lokal ko'prik (Do'kon agenti) yoki hamkor bulut |
| **Android — Chrome** | To'liq PWA | `webusb`, `webbluetooth` (BLE), `http_*`, `cloud` (Web Serial holati noaniq; Do'kon agenti yo'q) | Faqat hamkor bulut rejimida |
| **iPhone/iPad — Safari** | **Shartli**: faqat fiskal hamkorning bulut rejimi bo'lsa (qaror #21, #60); aks holda iOS — faqat back-office | Faqat `cloud` yoki elektron chek zaxirasi | Faqat hamkor bulut rejimida |
| Back-office (kassa emas) | Barcha zamonaviy brauzerlar (Chrome, Edge, Safari, Firefox) | A4/PDF — oddiy brauzer chop etish | — |

**iOS cheklovlari**: Safari'da WebUSB/Web Serial/Web Bluetooth yo'q; lokal ko'prik (Do'kon agenti) yo'q. Safari 26 dan Home Screen'ga qo'shilgan sayt standart bo'yicha web app sifatida ochiladi; Home Screen web app domeni Safari ITP'ning 7 kunlik xotira o'chirish qoidasidan ozod — shuning uchun iOS'da faqat o'rnatilgan PWA ishlatiladi (tab'da emas). iOS kassa to'plami (bulut printer ~5–7 mln so'm, `25-nofunksional-talablar.md` §7.2) qimmat — iOS kassa zaxira yo'l, arzon variant — Windows PK yoki Android planshet + USB printer.

### 6.3 Yorliqlar va tarozi

- **Yorliq chop etish**: brauzerda HTML/SVG + `bwip-js` (EAN-13, Code128, GS1 DataMatrix), CSS `@page { size: Wmm Hmm; margin: 0 }`, chiqish — OS drayveri orqali (`system_print`); yorliq printeri drayverda bir marta mos qog'oz o'lchamiga sozlanadi (onboarding yo'riqnomasi). Standart o'lchamlar: 58×40 (asosiy narx yorlig'i), 58×30, 43×25, 40×30, 30×20 mm va A4 (3×8 yoki 4×10 to'r); 203 dpi uchun shtrix moduli butun nuqtaga (≈ 0,125 mm) yaxlitlanadi. Xom TSPL/ZPL — MVP'da yo'q (bozor lideri Xprinter XP-365B ZPL'ni qo'llamaydi; kelajakda birinchi TSPL). Server PDF — faqat > 200 yorliq yoki iOS uchun (qaror #54).
- **Tarozi og'irlik shtrix-kodi**: `shared/lib/scanner` EAN-13 `PP CCCCC VVVVV K` ni tahlil qiladi — `tenants.settings.weight_barcode_templates[]` (`prefixes`, `item_code_len` 4..6, `value_len` 5, `value_kind` `WEIGHT|AMOUNT`, `decimals`); standart: **22** — og'irlik (gramm), **21** — summa (so'm, ≤ 99 999); nazorat raqami mos kelmasa kod rad etiladi; bir tovarning bir nechta og'irlik yorlig'i bitta chek qatorida jamlanadi; summa prefiksida miqdor = summa ÷ joriy narx.
- **Kassadagi jonli og'irlik** (yorliqsiz tarozi: CAS-M, Mertech POS2-M, Massa-K "Протокол 100") — desktop Chrome/Edge'da Web Serial orqali, **MVP'dan keyin**; qo'lda og'irlik kiritish — doimiy zaxira.
- **PLU yuklash** (yorliqli tarozi) — MVP'da CSV eksport (PLU kodi, nom, narx, yaroqlilik muddati) vendor dasturi (CL-Works, Shtrih Loader, Rongta tool) bilan import; to'g'ridan-to'g'ri yuklash — Do'kon agentining `scale.plu_upload` vazifasi (`21` §16).

### 6.4 Do'kon agenti bilan ishlash (`@shared/lib/agent`)

- Agent lokal API'si: `http://127.0.0.1:<port>/v1/*` — `GET /v1/status`, `POST /v1/pair`, `POST /v1/fiscal/open-shift|close-shift|sale|refund`, `GET /v1/fiscal/device-status`, `GET /v1/fiscal/unsent`, `POST /v1/fiscal/resend`, `POST /v1/print/raw` (yagona ta'rif — `21` §16). Brauzer `http://127.0.0.1` ni xavfsiz kontekst deb hisoblaydi (mixed content emas); Chrome 142+ birinchi murojaatda Local Network Access ruxsatini so'raydi — onboarding'da ko'rsatiladi.
- Himoya: agent faqat `127.0.0.1` da tinglaydi va `Origin` oq ro'yxatini (`https://app.<domen>`) tekshiradi; har so'rovda **qurilmaga bog'langan lokal token** (`Authorization: Bearer`) — POS-16 «Uskunalar sozlamasi»da agent tray'idagi 6 raqamli kod bilan bir marta bog'lanadi (`POST /v1/pair {code, device_id}`), token Dexie'da saqlanadi, serverga yuborilmaydi (`21` §16).
- `$agentStatus` (`@shared/state`): `online | offline | not_installed | unpaired`, agent versiyasi, yoqilgan imkoniyatlar (`fiscal`, `print`, `card_terminal` — `34-1c-agent.md` §14.2 dagi nomlar), `fm_state`, `card_terminals[]` (`local_id`, `driver`, `tid`, `status` — `GET /v1/status`, `21` §16.1; karta oqimi — §6.5); `patronum/interval` bilan 10 s da `GET /v1/status`. Lokal ko'prik rejimida `$agentStatus != online` bo'lsa POS chekni **yopmaydi** — «Fiskal modul ulanmagan» holati (savat saqlanadi, agentni qayta ishga tushirish yo'riqnomasi); bu lokal holat, server xato kodi emas. `fm_state='locked'` → `FISCAL_DEVICE_LOCKED`; 48 soat → `FISCAL_OFFLINE_48H_BLOCKED` (`21` §1, `16-offline-sync.md`).
- Sotuv paytidagi fiskal chek va chop etish faqat lokal API orqali; server navbatidagi agent vazifalari (`fiscal.status`, `fiscal.resend_unsent`, `fiscal.zreport`, `print.raw`, `scale.plu_upload`) frontend'ga tegishli emas (`21` §16).

### 6.5 Bank karta terminali klienti (`@shared/lib/cardTerminal`, qaror #71)

Kassir hech qachon karta ma'lumotini (raqam, niqob, RRN, tasdiq kodi, karta turi) yozmaydi — integratsiyalangan terminalda POS summani bank terminaliga yuboradi va natijani avtomatik oladi; terminalsiz kartada (rekvizitsiz) faqat summa yoziladi. Kontrakt, holatlar, taymautlar va xato kodlari — `21-integratsiyalar.md` §9.4 (yagona manba), agent lokal API'si — `21` §16.1, jadval — `12-db-sxema.md` `app.card_terminal_transactions`, ekran — `07-ekran-tafsilotlari.md` POS-03 (`CardTerminalPanel`, `TerminalStatusChip`, `StepIndicator` — `08-dizayn-tizimi.md`).

**`CardTerminalPort` (TypeScript)** — `21` §9.4 Python kontraktining aynan tarjimasi; DTO tiplari backend Pydantic sxemasidan generatsiya qilinadi (`@shared/models/generated`), qo'lda yozilmaydi:

```ts
// packages/shared/lib/cardTerminal/port.ts
export interface CardTerminalPort {
  purchase(req: CardPurchaseRequest): Promise<CardTxResult>;          // hech qachon avtomatik takrorlanmaydi
  refund(req: CardRefundRequest): Promise<CardTxResult>;              // original_rrn | original_attempt_id, amount_tiyin
  void(req: CardVoidRequest): Promise<CardTxResult>;                  // shu kunniki, settlementgacha
  get_status(attempt_id: string): Promise<CardTxResult>;              // "unknown" ni hal qilish
  get_last_transaction(terminal: TerminalRef): Promise<CardTxResult | null>;
  settlement(terminal: TerminalRef): Promise<SettlementResult>;       // smena yopilishida
  health(terminal: TerminalRef): Promise<TerminalHealth>;             // online | busy | offline | error
}

type TerminalRef = { card_terminal_id: string; local_id: string };
type CardPurchaseRequest = {
  attempt_id: string;            // UUIDv7 (uuid v7()), = card_terminal_transactions.id
  terminal: TerminalRef;
  amount_tiyin: number;          // butun son, faqat adapter chegarasida (quyida)
  currency: "UZS";
  cash_register_id: string;
  client_event_id: string;       // kelgusi sale.created / return.created / debt_payment.created
  receipt_seq?: number;
};
type CardTxResult = {
  attempt_id: string; kind: "purchase" | "refund" | "void";
  status: "approved" | "declined" | "cancelled" | "timeout" | "unknown" | "error";
  amount_tiyin: number; approval_code: string | null; rrn: string | null; stan: string | null;
  card_mask: string | null;      // ^[0-9]{4}\*+[0-9]{4}$ ga normallashtirilgan
  card_scheme: "uzcard" | "humo" | "visa" | "mastercard" | "unionpay" | "mir" | "other" | null;
  card_type: "personal" | "corporate" | "social" | "unknown" | null;
  entry_mode: "chip" | "contactless" | "magstripe" | "fallback" | null;
  tid: string | null; mid: string | null; acquirer: string | null; tx_at: string | null;
  decline_code: string | null; decline_message: string | null; slip_text?: string | null;
};
// CardRefundRequest, CardVoidRequest, SettlementResult, TerminalHealth — 21 §9.4 / §16.1 dagi maydonlar bilan
```

- **Pul chegarasi**: `amount_tiyin` faqat adapter chaqiruvida hosil qilinadi — `shared/lib/money.toTiyin(value: string)` (`decimal.js`, butun son, `Number.isSafeInteger` tekshiruvi); ilova ichida summa doim kasr-satr (`"12000.00"`, `08` §0 band 1). Qaytgan `amount_tiyin` `fromTiyin()` bilan satrga aylantiriladi va so'ralgan summa bilan satr darajasida solishtiriladi.
- **PCI**: port faqat niqob qaytaradi; to'liq PAN/track/CVV hech qachon store'ga, Dexie'ga, logga yoki Sentry'ga tushmaydi (`21` §9.4). POS-03 (va POS-05, POS-13) DOM'ida karta ma'lumoti kiritiladigan input umuman yo'q — terminalsiz karta rejimida ham.

**Adapter tanlovi** — `createCardTerminalPort(terminal)` kassaning standart terminali (`card_terminals.is_default`, aks holda yagona `status='active'` terminal) `adapter` qiymatiga qarab:

| `card_terminals.adapter` | Veb-kassa adapteri | Transport |
|---|---|---|
| `agent_ecr` | `AgentEcrAdapter` | `http://127.0.0.1:47110/v1/card/*` — Do'kon agenti (`@shared/lib/agent` klienti: lokal `Authorization: Bearer` token, §6.4) |
| `fake` | `FakeCardTerminalAdapter` | Brauzer ichida (tarmoqsiz) |
| `cloud` | — | Faqat vendor bulut API'si bo'lsa (server adapteri, `21` §9.4); veb-kassa natijani server orqali oladi |
| `android_intent`, `softpos` | — | Veb-kassada yo'q (Kotlin POS, `28`) |

POS faqat `card_terminals.capabilities` da `true` bo'lgan amallarni taklif qiladi (`refund`, `void`, `status_query`, `last_transaction`, `settlement`).

**`AgentEcrAdapter`** (Windows PK veb-kassa) — har metod bitta agent yo'liga mos (`21` §16.1):

| Port metodi | Agent so'rovi | Klient taymauti |
|---|---|---|
| `health` | `GET /v1/card/health?local_id=` | 3 s |
| `purchase` | `POST /v1/card/purchase` `{attempt_id, local_id, amount_tiyin, currency:"UZS", cash_register_id, client_event_id, receipt_seq?}` — uzun so'rov; `202 {attempt_id}` kelsa `GET /v1/card/tx/{attempt_id}` 2 s oraliqda poll | 125 s (`AbortController`) |
| `get_status` | `GET /v1/card/tx/{attempt_id}` (agent jurnali; jurnalda `unknown` bo'lsa agent terminaldan holat/oxirgi tranzaksiyani so'raydi) | 10 s |
| `get_last_transaction` | Alohida agent yo'li yo'q — xuddi shu `GET /v1/card/tx/{attempt_id}` (agent ichida bajaradi); natija faqat `attempt_id` mos kelsa qabul qilinadi | 10 s |
| `refund` / `void` | `POST /v1/card/refund` / `POST /v1/card/void` `{attempt_id, local_id, amount_tiyin, original_rrn \| original_attempt_id}` | 60 s |
| `settlement` | `POST /v1/card/settlement` `{local_id}` | 60 s |
| (bekor qilish) | `POST /v1/card/cancel-pending` `{attempt_id}` — "Terminalda bekor qilish" tugmasi | 5 s |

HTTP → holat xaritasi: `200` → `CardTxResult` (rad etilgan karta ham `200`, `status:"declined"` → `CARD_DECLINED`); `409 CARD_TERMINAL_BUSY` / `CARD_OUTCOME_UNKNOWN`; `422 CARD_AMOUNT_MISMATCH`; `502 CARD_VOID_FAILED`; `503 CARD_TERMINAL_UNREACHABLE`; `504 CARD_TERMINAL_TIMEOUT`, klient `AbortController` taymauti yoki aloqa uzilishi (`purchase` yuborilgandan keyin) → `unknown`; `401`/`403` → `$agentStatus='unpaired'` (POS-16 qayta bog'lash). Xato shakli `{code, message_key, params?}` — matn i18n kalitidan (`08` §11).

**`FakeCardTerminalAdapter`** — dev, test (vitest, Playwright), staging va demo-tenant uchun; `21` §16.1 sxemalariga aynan tayanadi. Prod guard (`12-db-sxema.md` `card_terminals`: `fake` — dev/test/staging va demo-tenant, real pul yo'q): production muhitida (`window.__ERP_CONFIG__`) demo bo'lmagan tenantda `createCardTerminalPort` `fake` adapterni yaratmaydi — "Karta" tugmasi `CARD_TERMINAL_UNREACHABLE` sababi bilan o'chiq. Natija deterministik — summaning (so'm) oxirgi uch raqami bo'yicha:

| Summa oxiri | Natija |
|---|---|
| boshqa | 3 s dan keyin `approved` (`rrn`, `approval_code`, `card_mask="8600****1234"`, `card_scheme="uzcard"`, `card_type=null`) |
| `…001` | `declined` (`decline_code="51"`, `decline_message="Mablag' yetarli emas"`) |
| `…002` | `purchase` javobsiz → `unknown`; `get_status` → `approved` |
| `…003` | `purchase` javobsiz → `unknown`; `get_status` va `get_last_transaction` ham natijasiz (menejer yopishi) |
| `…004` | `CARD_TERMINAL_BUSY` |
| `…005` | `approved`, lekin `amount_tiyin` 100 000 kam (`CARD_AMOUNT_MISMATCH`) |
| `…006` | `approved`; keyingi `void` → `CARD_VOID_FAILED` |

Testlarda deterministik qoida `fakeCardScenario(...)` bilan ustidan yoziladi (31 qabul testlari "Fake sozlamasi"). Bir xil `attempt_id` bilan qayta `purchase` saqlangan natijani qaytaradi (`purchase` chaqiruvlari hisoblagichi testlarda tekshiriladi).

**Holat mashinasi (Effector)** — `@pages/pos` → `features/card-payment/model` (§2 naqshi: `events/`, `stores/`, `effects/`, `connections/`). Bitta `$cardAttempt` store'i, holat `$cardAttempt.phase`:

```
idle ──purchase()──▶ pending (120 s teskari hisoblagich)
pending ──approved, amount = so'ralgan──▶ approved ──▶ fiskal chek ──▶ sale.created
pending ──approved, summa farqi──▶ void (avtomatik) ──▶ declined (CARD_AMOUNT_MISMATCH)
pending ──declined / cancelled / error / cancel-pending──▶ declined
pending ──timeout / 504 / aloqa uzildi──▶ unknown
unknown ──get_status()──▶ approved | declined | unknown
unknown ──get_last_transaction() (capabilities.last_transaction)──▶ approved | declined | unknown
unknown ──"Menejer tasdig'i bilan yopish" (card_manual_entry)──▶ resolved_manual (tx approved, resolved_by='manager', rekvizitsiz) | declined (decline_code='not_found')
resolved_manual ──▶ fiskal chek (payment_form='card', rekvizitsiz) ──▶ sale.created (card_entry_mode='manual', manual_reason='unknown_result')
declined ──"Qayta yuborish" (yangi attempt_id)──▶ pending
idle | declined ──terminalsiz karta (siyosat bo'yicha; terminal bog'lanmagan kassada darhol)──▶ manual_confirm ──[ApprovalDialog, kerak bo'lsa]──▶ manual ──▶ fiskal chek ──▶ sale.created
```

- Effektlar: `healthFx`, `purchaseFx`, `getStatusFx`, `getLastTransactionFx`, `cancelPendingFx`, `voidFx`, `recordTxFx` (`POST /api/v1/card-terminal-transactions`, online bo'lsa). Hisoblagich — `patronum/interval` (1 s), chegara `purchase` taymauti (120 s, `21` §9.4); UI "Kutish: mm:ss / 02:00".
- **`purchase` hech qachon avtomatik takrorlanmaydi**: `purchaseFx` faqat `idle` va `declined` (foydalanuvchi "Qayta yuborish"ni bosganda, har safar yangi `attempt_id`) holatidan chaqiriladi; `sample` `filter` bilan majburlanadi. `unknown` va `pending` holatida yangi `purchase` bloklanadi (`CARD_OUTCOME_UNKNOWN`), "Qayta yuborish" o'chiq, `Esc` dialogni yopmaydi.
- `unknown` ga o'tilganda darhol `get_status(attempt_id)` (xavfsiz so'rov — 3 marta, 2 s oraliq), natija hali `unknown` bo'lsa `get_last_transaction` (faqat `attempt_id` mos kelsa qabul); `resolved_by='status_query'`. Ikkalasi ham natija bermasa — "Terminal javobini tekshiring" va "Menejer tasdig'i bilan yopish" (`ApprovalDialog`, tasdiq turi `card_manual_entry`, ruxsat `card.manual_entry.approve`; menejer terminal chekiga qarab faqat "o'tgan / o'tmagan"ni tasdiqlaydi, hech narsa kiritmaydi; audit `card.outcome.resolved_manual`). "O'tgan" → tranzaksiya `approved`, `resolved_by='manager'`, `approved_amount` = summa, `rrn`/`card_mask`/`approval_code`/`card_type` NULL; to'lov qatori `card_entry_mode='manual'`, `manual_reason='unknown_result'`, rekvizitsiz, `card_terminal_transaction_id` NULL (tranzaksiya hujjatga `card_terminal_transactions.doc_type/doc_id` orqali bog'lanadi). "O'tmagan" → `declined` (`decline_code='not_found'`).
- `unknown` holati Dexie'da (`card_attempts`: `attempt_id`, `card_terminal_id`, `local_id`, `kind`, `amount` (Money), `client_event_id`, `status`, `started_at`, oxirgi natija (`CardResult`, PAN'siz) — `16-offline-sync.md` §2.1) saqlanadi — sahifa yangilansa yoki PWA qayta ochilsa ham bloklash davom etadi va holat so'rovi qayta boshlanadi; offline'da ham bloklaydi.
- Aralash to'lovda har karta qismi — alohida `sale_payments` qatori va alohida `attempt_id`; bir vaqtda bitta urinish.

**Sotuv ketma-ketligi (qat'iy)**: karta `approved` → fiskal chek (`@shared/lib/fiscal`, `payment_form='card'`, aralashda `mixed`; `card_tiyin`, `card_type`, `card_mask`, `rrn` natijadan) → `sale.created` outbox voqeasi `payments[].card_result` bilan (`CardResult`, `18-api-kassa.md` §2.7: `{attempt_id, card_terminal_id, kind, original_attempt_id?, status, amount (Money), approval_code, rrn, stan, card_mask, card_scheme, card_type, card_type_source, entry_mode, tid, mid, acquirer, tx_at, resolved_by, decline_code?, decline_message?, slip_text?}` — adapterning `amount_tiyin` (int) qiymati `Money` satriga o'giriladi; `16-offline-sync.md` §2.1, `18-api-kassa.md` §4.1); `sale_payments`: `card_entry_mode='integrated'`, `card_terminal_transaction_id = attempt_id`. Qaytarishda — `return.created` → `refund_card.card_result`, qarz to'lovida — `debt_payment.created` ildizida `card_result`.
- `card_type` tartibi (`21` §9.4): natijada bo'lsa — `card_type_source='terminal'`; aks holda `platform.card_bin_rules` (`bin_table`); topilmasa `card_type='unknown'`, `card_type_source='bin_table'`. POS'da karta turini tanlash UI'si yo'q.
- Karta tasdiqlangan, fiskal chek chiqmagan bo'lsa: sotuv "To'lov qabul qilingan, chek kutilmoqda" holatida qoladi, savat saqlanadi, `sale.created` yuborilmaydi, fiskal qayta urinish (POS-04/POS-12); kassir sotuvni bekor qilsa — **avtomatik `void`** (`voidFx`, `kind='void'`, `original_transaction_id` = xarid, audit `card.void.auto`); `void` ham bajarilmasa — `CARD_VOID_FAILED`, sotuv bekor qilinmaydi. `CARD_AMOUNT_MISMATCH` da ham avtomatik `void`, fiskal chek chiqmaydi.

**Terminalsiz karta (rekvizitsiz)** (`21` §9.2): to'lov qatori faqat `method='card'`, summa va `manual_reason` (`card_entry_mode='manual'`); forma/validatsiyada karta maydonlari yo'q — `card_type`, `card_type_source`, `card_mask`, `rrn`, `approval_code`, `card_scheme`, `card_terminal_transaction_id`, `terminal_ref` yuborilmaydi (server null bo'lmagan qiymatni `422 VALIDATION_ERROR` bilan rad etadi). UI — faqat "Karta terminalsiz qabul qilindi" tasdig'i (`CardManualConfirm`), karta turi tanlovi yo'q.
- Kassaga faol terminal bog'lanmagan: "Karta" bosilganda darhol shu tasdiq, `manual_reason='standalone_terminal'`; siyosat qo'llanmaydi, tasdiq so'ralmaydi, offline ham ishlaydi.
- Faol terminal bog'langan kassada terminal `offline`/`error`/`busy` yoki agent ulanmagan (`terminal_offline`/`terminal_error`) — `tenants.settings.card_manual_fallback` (Dexie `settings`; kalit yo'q bo'lsa `manager_approval`) bo'yicha: `allow` — tasdiqsiz; `manager_approval` — avval `ApprovalDialog` (tasdiq turi `card_manual_entry`, `card.manual_entry.approve`; lokal PIN — offline ham, yoki BO-16 masofaviy tasdiq), tasdiqsiz — `CARD_MANUAL_APPROVAL_REQUIRED`; `forbid` — terminalsiz karta yopiq (`CARD_MANUAL_NOT_ALLOWED`). `unknown_result` — faqat yuqoridagi "Menejer tasdig'i bilan yopish" orqali.
- Fiskal chek: `payment_form='card'`, karta turi/niqob/RRN'siz (bunday chekning maqbulligi — 26 #178).

**`$agentStatus` bog'liqligi**: `adapter='agent_ecr'` terminalda integratsiyalangan "Karta" faqat `$agentStatus.status === 'online'`, `capabilities.card_terminal.enabled === true` va `card_terminals[]` da shu `local_id` `status='online'` bo'lsa faol; `busy` — "Terminal band", qolgan holatlar — "Terminal ulanmagan" (`CARD_TERMINAL_UNREACHABLE`, lokal holat) va terminalsiz karta siyosati. `TerminalStatusChip` shu store'dan hosil qilinadi (`online` — "Wi-Fi · ulangan", `busy` — "Band", `offline`/`error` — "Ulanmagan", `unknown` urinish — "Tekshirilmoqda"). "Karta" bosilganda `health` (≤ 3 s) qayta tekshiriladi. Do'kon interneti yo'qligi (`$isOnline=false`) integratsiyalangan kartani o'chirmaydi — agent va terminal ishlasa to'lov o'tadi, natija `sale.created` bilan keyin yuboriladi.

**Smena yopilishi**: har bog'langan terminal uchun `settlement()` → `POST /api/v1/card-terminal-settlements`; POS yopiq bo'lsa — server vazifasi `card.settlement` (`21` §9.4); Z-hisobotda "Karta (integratsiyalangan)" va "Karta (terminalsiz)" alohida.

## Ochiq savollar

Faqat tashqi javob kerak bo'lgan bandlar:

1. **Printer transportlarining amaliy sinovi** — 2–3 model (Xprinter XP-58IIH USB, XP-80 USB+LAN, bitta BT) × transport × matn/raster, Windows 11 Chrome va Android Chrome; Zadig/WinUSB bilan WebUSB — 26 #139 (OQ-060). Interim: §6.1 avto-tanlov; Bosqich 3 qabul testlari.
2. **Faqat elektron chek** do'kon savdosida ruxsat etiladimi — 26 #112 (OQ-018). Interim: standart bosma, elektron — zaxira.
3. **Fiskal hamkorning bulut rejimi** (iOS/Android kassa yo'li va lokal ko'prik ruxsati) — 26 #109 (OQ-012).

## Manbalar

- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — BFF login oqimi, OAuth token, obuna-lokaut holati.
- Namuna: `E:/Project/monorepo/projects/metadata management/src/client` — `package.json` (workspaces, effector, patronum, axios), `packagess/pages/list-metadata/src/pages/notification/model/*` (events/stores/effects/connections naqshi), `packagess/shared/api/src/_base/metadata-management.ts` va `interceptors.ts` (axios instance, CSRF, xato), `apps/shell/src/main.tsx`.
- `spec/kod-uchun/06-ekranlar-umumiy.md` — ekranlar ro'yxati (POS-xx, BO-xx).
- `spec/kod-uchun/33-1c-integratsiya.md` §10, §13 — BO-22/BO-23 marshrutlari, veb API W-01…W-55, polling.
- `research_notes/ochiq-savollar/P6-uskuna-ai-narx.md` (WebUSB/Web Serial/Web Bluetooth, Direct Sockets, Local Network Access, bulut printerlar, tarozi EAN-13, yorliq o'lchamlari), `D-qarorlar-va-E-standartlar.md` (OQ-060 printer interim standarti), `P1-soliq-fiskal.md` (OQ-018 elektron chek).
- https://caniuse.com/webusb, https://developer.chrome.com/docs/capabilities/serial, https://developer.chrome.com/docs/iwa/direct-sockets, https://developer.chrome.com/blog/local-network-access, https://webkit.org/tracking-prevention/
- `research_notes/texnik/04-arxitektura-va-stack.md` — offline-first, PWA + IndexedDB.
- Feature-Sliced Design: https://feature-sliced.design
- `design/USLUB.md`, `design/canvas/project/Main.dc.html` (POS-02 katalog, ko'rinish almashtirgichi), `Pos03Tolov.dc.html` (karta terminali paneli); Fontsource Manrope (https://fontsource.org/fonts/manrope), lucide-react (https://lucide.dev/guide/packages/lucide-react)
