# Veb frontend arxitekturasi (back-office + veb-kassa)

*2026-10-14 · Foydalanuvchi qarori: React + Vite + TypeScript, FSD strukturasi, Effector, shadcn/ui, iloji boricha tayyor kutubxonalar. Namuna loyiha: `E:/Project/monorepo/projects/metadata management/src/client` (bundan keyin — "namuna").*

## Asosiy xulosalar

1. **Struktura namunadagidek**: Turborepo monorepo — `apps/shell` (yagona kirish nuqtasi, router, layout, auth) + `packages/pages/*` (har bir sahifa guruhi alohida paket) + `packages/shared/*` (api, models, state, ui, i18n, lib). Har sahifa ichida FSD: `model/` va `ui/`.
2. **Effector modeli namunadagi tartibda**: har bir `model/` papkasi `events/`, `stores/`, `effects/`, `connections/` (faqat `sample` bilan bog'lash), `types/`, `lib/` dan iborat. UI faqat `useUnit` orqali store o'qiydi va event chaqiradi; API'ni hech qachon to'g'ridan-to'g'ri chaqirmaydi.
3. **API qatlami namunadagidek**: `packages/shared/api` — bitta axios instance, interceptorlar (auth, CSRF, xato), har domen uchun funksiyalar fayli. Farqi: **tiplar va API funksiyalari FastAPI'ning OpenAPI sxemasidan avtomatik generatsiya qilinadi** (qo'lda yozilmaydi).
4. **UI — shadcn/ui** (Radix + Tailwind CSS). Namunadagi Mantine o'rniga. Jadval — TanStack Table (shadcn data-table), forma — react-hook-form + zod.
5. **Qo'lda yozish o'rniga kutubxona** — har bir vazifa uchun tanlangan kutubxona quyidagi jadvalda; yangi narsa qo'shishdan oldin avval shu ro'yxat va keyin tayyor kutubxona qidiriladi.
6. **Veb-kassa offline ishlaydi**: PWA (vite-plugin-pwa) + IndexedDB (Dexie) + append-only outbox; tafsiloti `04-offline-sync.md` da.
7. Namunadagi kamchiliklar takrorlanmaydi: `console.log` qoldirilmaydi, sana formatlash qo'lda yozilmaydi (dayjs), xato xabari `JSON.stringify` bilan foydalanuvchiga ko'rsatilmaydi (tarjima qilingan matn).
8. **Autentifikatsiya — BFF (Backend-for-Frontend) naqshi, OAuth 2.0 token hech qachon brauzer JS'iga chiqmaydi**: login `features/auth-provider` orqali backend'ning `/auth/login`iga POST qiladi, backend ichida OAuth Authorization Code+PKCE almashinuvini bajaradi va faqat `HttpOnly` sessiya cookie qaytaradi; access/refresh token faqat serverda. To'liq protokol — `12-autentifikatsiya-oauth2.md`. Login sahifasi obuna muddati tugagan holatni alohida ko'rsatadi (to'lov havolasi bilan). *(2026-10-15: foydalanuvchi qarori)*

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
│           ├── features/             # ilova darajasidagi: auth-provider (BFF login/logout, cookie, OAuth brauzerga chiqmaydi — 12-autentifikatsiya-oauth2.md), protected-route, tenant-switcher
│           └── main.tsx
├── packages/
│   ├── pages/                        # har biri alohida paket (@pages/*)
│   │   ├── pos/                      # veb-kassa (POS-01…15)
│   │   ├── catalog/                  # tovarlar, narxlar, yorliqlar (M09)
│   │   ├── warehouse/                # qoldiq, kirim, ko'chirish, inventarizatsiya (M04-M07)
│   │   ├── debts/                    # qarz daftari (M08)
│   │   ├── finance/                  # xarajatlar, kassa harakati, buxgalteriya, QQS (M10, M11, M15, M16)
│   │   ├── reports/                  # hisobotlar, dashboard (M12)
│   │   ├── settings/                 # do'kon, xodimlar/huquqlar, filiallar, integratsiyalar, Telegram (M13, M14, M18)
│   │   ├── billing/                  # tarif va to'lov, ro'yxatdan o'tish (M17)
│   │   └── ai-assistant/             # AI chat (AI-01), OCR tasdiqlash (AI-03)
│   └── shared/
│       ├── api/                      # axios instance, interceptorlar, GENERATSIYA qilingan klient
│       ├── models/                   # GENERATSIYA qilingan tiplar (OpenAPI) + qo'shimcha domen tiplari
│       ├── state/                    # global Effector modellari: user, tenant, branch, shift, online-status
│       ├── ui/                       # shadcn/ui komponentlari (components/ui) + umumiy kompozitlar
│       ├── i18n/                     # i18next: uz (lotin, asosiy), ru
│       ├── offline/                  # Dexie baza, outbox, sync (faqat pos va kerakli sahifalar ishlatadi)
│       ├── lib/                      # formatlash, pul, shtrix-kod parser, printer adapteri
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
- Global holat (`@shared/state`): `$user`, `$tenant`, `$activeBranch`, `$activeShift`, `$isOnline`, `$permissions`.
- Huquq tekshiruvi: route darajasida `ProtectedRoute` (namunadagi `CheckRole` o'rniga ruxsatlar ro'yxati asosida, `$permissions`), tugma darajasida `<Can permission="debts.forgive">`.

## 3. API qatlami

- **Generatsiya:** FastAPI `/openapi.json` → **orval** (axios mutator bilan) → `@shared/api/generated` (funksiyalar) va `@shared/models/generated` (tiplar). `npm run api:gen` buyrug'i; CI'da sxema o'zgarsa generatsiya qayta tekshiriladi. Shu bilan backend va frontend tiplari doim mos. orval: `client: "axios-functions"`, `mode: "tags-split"`, `mutator` — umumiy axios instance; `override.operationName` `operation_id`dagi teg prefiksini olib tashlaydi (`debts_list_debtors` → `listDebtors`). `@shared/api/index.ts`: `export * as debts from "./generated/debts/debts";` — bundan `api.debts.listDebtors(...)` kelib chiqadi (qo'lda o'ram kodi yo'q, faqat ESM namespace re-export). *(2026-10-14: tekshiruv)*
- **Instance** (namunadagi `_base` kabi): `withCredentials: true` (HttpOnly sessiya cookie), interceptorlar: CSRF tokeni (`GET /auth/csrf` dan, xotirada keshlanadi — namunadagi `getCsrfToken`) (POST/PUT/PATCH/DELETE), `X-Tenant-Id` emas — tenant sessiyadan olinadi, `X-Branch-Id` (tanlangan filial), `Idempotency-Key` (barcha yozuvchi so'rovlarda — offline qayta yuborishda takror yozuvdan himoya), `Accept-Language`. *(2026-10-14: tekshiruv)*
- **Xatolar:** 401 → BFF avval jim refresh qiladi (`12-autentifikatsiya-oauth2.md` §7), muvaffaqiyatsiz bo'lsa qayta autentifikatsiya oynasi (POS'da outbox/Dexie saqlanadi; to'liq logout faqat foydalanuvchi tanlovi bilan); 403 `PERMISSION_DENIED` → "huquq yo'q"; **403 `SUBSCRIPTION_RESTRICTED`** → `/login?reason=subscription_expired`ga yo'naltirish, login sahifasida "Obuna muddati tugagan" banner + Click/Payme to'lov havolasi (javobdagi `pay_url`/`amount_due` bilan, `12-autentifikatsiya-oauth2.md` §16) — to'lov o'tgach kirish darhol tiklanadi; 409/422 → forma maydonlariga xato (zod bilan bir xil format); tarmoq xatosi → `$isOnline=false` va kassa offline rejimga o'tadi. `409 IDEMPOTENCY_IN_PROGRESS` — forma xatosi emas: effekt `Retry-After`dan keyin xuddi shu kalit bilan avtomatik takrorlanadi (maks. 3 marta). `422 IDEMPOTENCY_KEY_REUSED` — dasturiy xato, Sentry'ga. Foydalanuvchiga xom JSON ko'rsatilmaydi — backend xato kodi i18n kalitiga tarjima qilinadi. *(2026-10-15: foydalanuvchi qarori — subscription-expired holati qo'shildi)*
- Runtime konfiguratsiya: `window.__ERP_CONFIG__` (namunadagi `window.metadataApiConfig` kabi) — bitta build turli muhitlarda ishlaydi.

## 4. Kutubxonalar (qo'lda yozish o'rniga)

| Vazifa | Kutubxona | Izoh |
|---|---|---|
| Build / monorepo | Vite, Turborepo, npm workspaces | namunadagidek |
| Holat va API oqimi | effector, effector-react, patronum | namunadagidek |
| HTTP | axios | namunadagidek |
| API tip/klient generatsiyasi | orval (yoki openapi-typescript) | qo'lda DTO yozilmaydi |
| UI komponentlar | shadcn/ui (Radix UI) + Tailwind CSS | Mantine o'rniga |
| Ikonkalar | lucide-react | shadcn standarti |
| Jadvallar | @tanstack/react-table + @tanstack/react-virtual | katta ro'yxatlar (tovarlar, cheklar) virtualizatsiya bilan |
| Formalar va validatsiya | react-hook-form + zod + @hookform/resolvers | backend Pydantic xatolari bilan bir xil shakl |
| Routing | react-router-dom | namunadagidek |
| Sana | dayjs (+ uz/ru lokal) | qo'lda formatlash taqiqlanadi |
| Raqam/pul formatlash | `Intl.NumberFormat("uz-UZ")` + kichik `formatMoney` | pul hisob-kitobi frontendda qilinmaydi — backend beradi |
| Xabarlar (toast) | sonner (shadcn) | |
| Grafiklar | recharts (shadcn charts) | dashboard, hisobotlar |
| Sana tanlash | react-day-picker **^9.14** (shadcn calendar; v10 — `@daypicker/react`, v9 moslik API'lari olib tashlangan, alohida sinovdan keyin) | shadcn calendar `date-fns` ni tranzitiv olib keladi — UI formatlash baribir dayjs *(2026-10-14: tekshiruv)* |
| UUIDv7 (`client_event_id`, lokal hujjat ID) | uuid (`v7()`, ≥10) | `crypto.randomUUID()` faqat v4 beradi — ishlatilmaydi *(2026-10-14: tekshiruv)* |
| Buyruq paneli / tez qidiruv | cmdk (shadcn command) | kassada tovar qidiruvi |
| Tarjima | i18next + react-i18next | uz (lotin) asosiy, ru |
| Offline baza | Dexie (IndexedDB) | veb-kassa, outbox |
| PWA / offline yuklash | vite-plugin-pwa (Workbox) | |
| Shtrix-kod chizish | bwip-js (MIT; EAN-13, Code128, GS1 DataMatrix — asosiy yorliq renderer) | yorliqlar, ichki kodlar *(2026-10-14: tekshiruv)* |
| Shtrix-kod skaner | o'z kichik hook'i `useBarcodeWedge` (`shared/lib/scanner`: belgilar orasidagi interval < ~30 ms + Enter suffiksi, input fokusidan mustaqil) | onScan.js 2020 dan beri yangilanmagan — ishlatilmaydi *(2026-10-14: tekshiruv)* |
| Kamera orqali skaner/foto | @zxing/browser | telefon kamerasi bilan kod o'qish; AI-03 foto |
| Excel eksport/import | exceljs (yoki SheetJS) | boshlang'ich tovar/qarz importi (US-M04-04, US-M08-07) |
| Chop etish (A4, yorliq) | react-to-print | chek printeri (ESC/POS) — `shared/lib/printer` adapteri: Chromium (WebUSB/Web Serial/Web Bluetooth/tarmoq) + bulut printer (iOS uchun yagona yo'l) — §6, D3 *(2026-10-15)* |
| Testlar | vitest, @testing-library/react, msw, playwright | |
| Kod sifati | eslint + @feature-sliced/eslint-config, prettier, typescript strict | |

## 5. Veb-kassa (POS) maxsus talablari

- Kassa sahifasi (`@pages/pos`) — to'liq ekran, klaviatura/skaner bilan ishlaydi (F-tugmalar, Enter, Esc), sichqonchasiz ham.
- Ma'lumot manbai: Dexie'dagi lokal katalog (tovarlar, narxlar, mijozlar, qarzlar) — server bilan fon rejimida sinxronlanadi.
- Har bir amal (chek, qaytarish, qarz, kassa pul harakati) — avval Dexie outbox'ga yoziladi, keyin serverga yuboriladi (har voqeada `client_event_id` (UUIDv7) — server `sync_receipts` bilan dedupe qiladi; POS hujjatlari uchun alohida REST endpoint yo'q). Internet holati `$isOnline` da, UI'da doimiy ko'rsatkich. *(2026-10-14: tekshiruv)*
- Fiskal chek: veb-kassa uchun fiskal modul (virtual kassa) server orqali ishlaydi — offline paytda 48 soat qoidasi (`04-offline-sync.md`). Fiskal chek raqami (`receipt_seq`) qurilmada, outbox yozuvi bilan bir Web Lock ichida beriladi. *(2026-10-14: tekshiruv)*
- Android POS (Kotlin) keyingi bosqichda xuddi shu backend API va sync protokolidan foydalanadi (`10-android-pos.md`).

## 6. Qo'llab-quvvatlanadigan platformalar va chop etish strategiyasi *(2026-10-15: foydalanuvchi qarori, D3 — "faqat Chromium" qarorini almashtiradi)*

Avvalgi qaror ("veb-kassa faqat Chromium — Chrome/Edge/Android Chrome, Safari/iOS qo'llab-quvvatlanmaydi") **bekor qilindi**. iPhone/iPad endi o'rnatilgan PWA sifatida qo'llab-quvvatlanadi, lekin chop etish imkoniyati platformaga qarab farqlanadi:

| Platforma | Qo'llab-quvvatlash darajasi | Chop etish |
|---|---|---|
| Chrome/Edge (desktop), Android Chrome | To'liq — o'rnatilgan PWA, `navigator.storage.persist()` | WebUSB / Web Serial / Web Bluetooth (USB/Bluetooth printer/skaner) + tarmoq printeri (http) + bulut printer (quyida) |
| Safari, iOS/iPadOS (iPhone/iPad) | O'rnatilgan PWA (Home Screen'ga qo'shilgan) — **majburiy**, tab'da ochib ishlatish tavsiya etilmaydi | **Faqat**: (a) bulut printer adapteri (Star CloudPRNT / Epson Server Direct Print klassi) yoki (b) elektron chek (QR/Telegram) |
| Back-office (ko'rish/boshqaruv, kassa emas) | Barcha zamonaviy brauzer (Chrome, Edge, Safari, Firefox) | Tegishli emas (A4/PDF hisobotlar — oddiy brauzer chop etish) |

**Sabab (iOS cheklovi)**: Safari'da WebUSB/Web Serial/Web Bluetooth mavjud emas; https sahifadan (PWA) oddiy http tarmoq printeriga ulanib bo'lmaydi (mixed content, brauzer bloklaydi); o'rnatilmagan (faqat tab) holatda Safari ITP sayt xotirasini (shu jumladan IndexedDB) agressiv tozalashi mumkin — shuning uchun Home Screen'ga o'rnatish shart qilib qo'yilgan.

**`shared/lib/printer` adapteri** uch implementatsiyaga ega: `WebUsbPrinterAdapter`/`WebSerialPrinterAdapter`/`WebBluetoothPrinterAdapter` (Chromium), `NetworkPrinterAdapter` (http tarmoq printeri, Chromium), `CloudPrintAdapter` (Star CloudPRNT/Epson Server Direct Print — har ikki platformada ishlaydi, iOS uchun yagona yo'l). Runtime'da platforma va mavjud API aniqlanib tegishli adapter tanlanadi; hech biri mavjud bo'lmasa — elektron chek (QR/Telegram) zahira sifatida taklif qilinadi.

**Ochiq savol**: bulut printerning O'zbekiston bozorida mavjudligi/narxi va faqat-elektron chekning (qog'ozsiz) qonuniyligi — `06-nofunksional-talablar.md` §6–7.2'da qayd etilgan, hal qilinmagan.

## Ochiq savollar

1. ~~Chromium-only sababli WebUSB/Web Serial asosiy yo'l~~ — 2026-10-15'da D3 bilan almashtirildi (6-bo'lim): endi platformaga qarab ikki yo'l (Chromium — WebUSB/Serial/Bluetooth + tarmoq/bulut; iOS — faqat bulut/elektron chek). QZ Tray/tizim printeri — Chromium uchun hamon zaxira, pilot uskunasida sinab tasdiqlanadi.
2. ~~Veb-kassa faqat Chromium~~ — 2026-10-15'da **bekor qilindi** (D3, 6-bo'lim): iPhone/iPad endi o'rnatilgan PWA sifatida qo'llab-quvvatlanadi, chop etish faqat bulut printer/elektron chek orqali. Ochiq qolgan qism: bulut printer narxi/mavjudligi, faqat-elektron chek qonuniyligi.
3. orval vs openapi-typescript + openapi-fetch — birinchi sprintda sinab tanlanadi (orval axios bilan namunaga yaqinroq).

## Manbalar

- `spec/02-arxitektura/12-autentifikatsiya-oauth2.md` — BFF login oqimi, OAuth token, obuna-lokaut holati. *(2026-10-15: foydalanuvchi qarori)*
- Namuna: `E:/Project/monorepo/projects/metadata management/src/client` — `package.json` (workspaces, effector, patronum, axios), `packagess/pages/list-metadata/src/pages/notification/model/*` (events/stores/effects/connections naqshi), `packagess/shared/api/src/_base/metadata-management.ts` va `interceptors.ts` (axios instance, CSRF, xato), `apps/shell/src/main.tsx`.
- `spec/01-mahsulot/04-ekranlar-va-ux.md` — ekranlar ro'yxati (POS-xx, BO-xx).
- `research_notes/texnik/04-arxitektura-va-stack.md` — offline-first, PWA + IndexedDB.
- Feature-Sliced Design: https://feature-sliced.design
