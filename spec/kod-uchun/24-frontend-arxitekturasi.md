# Veb frontend arxitekturasi (back-office + veb-kassa)

**Maqsad:** Frontend (back-office + veb-kassa) papka strukturasi, holat boshqaruvi (Effector), API qatlami, kutubxona tanlovlari va platforma/chop etish strategiyasini belgilash.
**Kim uchun:** Frontend ishlab chiquvchi.
**Bog'liq fayllar:** `14-autentifikatsiya-oauth2.md`, `16-offline-sync.md`, `06-ekranlar-umumiy.md`, `07-ekran-tafsilotlari.md`, `08-dizayn-tizimi.md` (§13 chek shabloni), `21-integratsiyalar.md` (§1 fiskal, §16 Do'kon agenti), `25-nofunksional-talablar.md`, `33-1c-integratsiya.md` (§13 BO-22/BO-23), `01-qarorlar.md` #21, #57, #60.
**Holat:** joriy, 2026-10-16.

*Stack: React + Vite + TypeScript, FSD strukturasi, Effector, shadcn/ui, iloji boricha tayyor kutubxonalar. Namuna loyiha: `E:/Project/monorepo/projects/metadata management/src/client` (bundan keyin — "namuna").*

## Asosiy xulosalar

1. **Struktura namunadagidek**: Turborepo monorepo — `apps/shell` (yagona kirish nuqtasi, router, layout, auth) + `packages/pages/*` (har bir sahifa guruhi alohida paket) + `packages/shared/*` (api, models, state, ui, i18n, lib). Har sahifa ichida FSD: `model/` va `ui/`.
2. **Effector modeli namunadagi tartibda**: har bir `model/` papkasi `events/`, `stores/`, `effects/`, `connections/` (faqat `sample` bilan bog'lash), `types/`, `lib/` dan iborat. UI faqat `useUnit` orqali store o'qiydi va event chaqiradi; API'ni hech qachon to'g'ridan-to'g'ri chaqirmaydi.
3. **API qatlami namunadagidek**: `packages/shared/api` — bitta axios instance, interceptorlar (auth, CSRF, xato), har domen uchun funksiyalar fayli. Farqi: **tiplar va API funksiyalari FastAPI'ning OpenAPI sxemasidan avtomatik generatsiya qilinadi** (qo'lda yozilmaydi).
4. **UI — shadcn/ui** (Radix + Tailwind CSS). Namunadagi Mantine o'rniga. Jadval — TanStack Table (shadcn data-table), forma — react-hook-form + zod.
5. **Qo'lda yozish o'rniga kutubxona** — har bir vazifa uchun tanlangan kutubxona quyidagi jadvalda; yangi narsa qo'shishdan oldin avval shu ro'yxat va keyin tayyor kutubxona qidiriladi.
6. **Veb-kassa offline ishlaydi**: PWA (vite-plugin-pwa) + IndexedDB (Dexie) + append-only outbox; tafsiloti `16-offline-sync.md` da.
7. Namunadagi kamchiliklar takrorlanmaydi: `console.log` qoldirilmaydi, sana formatlash qo'lda yozilmaydi (dayjs), xato xabari `JSON.stringify` bilan foydalanuvchiga ko'rsatilmaydi (tarjima qilingan matn).
8. **Chop etish va uskunalar (§6)**: printer transporti qurilmaga qarab tanlanadi — USB (Web Serial/WebUSB), HTTP LAN printer (Epson ePOS/Star WebPRNT), xom TCP 9100 LAN printer — faqat **Do'kon agenti** orqali (qaror #60), bulut printer (Star CloudPRNT/Epson SDP), tizim printeri; standart — bosma chek, elektron chek — zaxira. Lokal fiskal ko'prik rejimida kassa platformasi — Windows PK + Do'kon agenti; iOS kassa — faqat fiskal hamkorning bulut rejimida.
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
│       ├── lib/                      # formatlash, pul, shtrix-kod/og'irlik kodi parser (scanner), printer adapterlari (printer), fiskal port klienti (fiscal), Do'kon agenti lokal klienti (agent)
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
| Ikonkalar | lucide-react | shadcn standarti |
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

## 5. Veb-kassa (POS) maxsus talablari

- Kassa sahifasi (`@pages/pos`) — to'liq ekran, klaviatura/skaner bilan ishlaydi (F-tugmalar, Enter, Esc), sichqonchasiz ham.
- Ma'lumot manbai: Dexie'dagi lokal katalog (tovarlar, narxlar, mijozlar, qarzlar) — server bilan fon rejimida sinxronlanadi.
- Har bir amal (chek, qaytarish, qarz, kassa pul harakati) — avval Dexie outbox'ga yoziladi, keyin serverga yuboriladi (har voqeada `client_event_id` (UUIDv7) — server `sync_receipts` bilan dedupe qiladi; POS hujjatlari uchun alohida REST endpoint yo'q). Internet holati `$isOnline` da, UI'da doimiy ko'rsatkich.
- Fiskal chek — `@shared/lib/fiscal` (`FiscalPort`, `21` §1): **lokal ko'prik** rejimida POS chekni Do'kon agenti orqali fiskal modulga imzolatadi (internetsiz ham), natija (`fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`) chekka chop etiladi va `sale.created` voqeasi bilan sinxronlanadi; **hamkor bulut** rejimida chek server orqali fiskallashtiriladi (`fiscal_receipts.status=pending` → keyingi `/sync/pull`). Ichki chek raqami (`receipt_seq`) qurilmada, outbox yozuvi bilan bir Web Lock ichida beriladi; FM raqami — alohida `fm_receipt_seq`.
- **48 soat shkalasi (qaror #43)**: `ofd_acked_at` bo'lmagan eng eski fiskal chek yoshi bo'yicha — 24 soat 🟡 status panelida, 40 soat 🔴, 46 soat — har yangi chek oldidan yopib bo'lmaydigan modal, 48 soat — savdo bloklanadi (`FISCAL_OFFLINE_48H_BLOCKED`), faqat sinxron/yuborish ishlaydi. `fm_state='locked'` — `FISCAL_DEVICE_LOCKED`.
- Markirovka: chekka qo'shishdan oldin lokal takror-kod nazorati (bitta chekda va avval sotilgan kod — rad); online'da `MARKING_PRECHECK=warn` tekshiruvi (`21` §4).
- Android POS (Kotlin) keyingi bosqichda xuddi shu backend API va sync protokolidan foydalanadi (`28-android-pos.md`).

## 6. Qo'llab-quvvatlanadigan platformalar, chop etish va uskunalar

### 6.1 Chop etish transportlari

`@shared/lib/printer` — bitta `PrinterPort` (`printReceipt(doc)`, `printLabel(doc)`, `status()`), sozlama `printer.transport` (qurilma darajasida, Dexie'da) va transport adapterlari:

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
- `$agentStatus` (`@shared/state`): `online | offline | not_installed | unpaired`, agent versiyasi, yoqilgan imkoniyatlar (`fiscal`, `print` — `34-1c-agent.md` §14.2 dagi nomlar), `fm_state`; `patronum/interval` bilan 10 s da `GET /v1/status`. Lokal ko'prik rejimida `$agentStatus != online` bo'lsa POS chekni **yopmaydi** — «Fiskal modul ulanmagan» holati (savat saqlanadi, agentni qayta ishga tushirish yo'riqnomasi); bu lokal holat, server xato kodi emas. `fm_state='locked'` → `FISCAL_DEVICE_LOCKED`; 48 soat → `FISCAL_OFFLINE_48H_BLOCKED` (`21` §1, `16-offline-sync.md`).
- Sotuv paytidagi fiskal chek va chop etish faqat lokal API orqali; server navbatidagi agent vazifalari (`fiscal.status`, `fiscal.resend_unsent`, `fiscal.zreport`, `print.raw`, `scale.plu_upload`) frontend'ga tegishli emas (`21` §16).

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
