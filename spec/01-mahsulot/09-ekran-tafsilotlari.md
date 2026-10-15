# Ekran tafsilotlari — 37 ekran (implementatsiyaga tayyor)

*UX dizayner · 2026-10-15 · Asos: `04-ekranlar-va-ux.md` (37 ekran ro'yxati, wireframelar, UX qoidalari), `02-modullar-talablari.md` (US-Mxx-nn), `03-biznes-jarayonlar.md` (BP-nn), `08-dizayn-tizimi.md` (tokenlar, komponentlar), `08-frontend-arxitekturasi.md` (FSD/Effector/route), `04-offline-sync.md`, `12-autentifikatsiya-oauth2.md`, `06-mvp-chegarasi.md` (tarif).*

## Qanday o'qish kerak

- **Route** — `apps/shell` routeri ichida, `@pages/*` paketiga mos (`08-frontend-arxitekturasi.md` §1). POS yo'llari `/pos/...`, back-office `/app/...`, login `/login`, onboarding `/onboarding`, platforma admin `/platform/...` (alohida `admin-bff`, `12-autentifikatsiya-oauth2.md` §18.1).
- **Ruxsat (permission)** — `role_permissions.permission_code` formatida, scope prefiksi `12-autentifikatsiya-oauth2.md` §10 jadvaliga mos (`sales.*`, `stock.*`, `debts.*`, ...). Kod nomlari `spec/02-arxitektura/05-xavfsizlik-va-audit.md` ruxsat katalogi va `spec/tekshiruv/qabul-7-ekran-api.md` E-02 jadvali bilan moslashtirildi. *(2026-10-15: qabul-6/7)*
- **Egasi — barcha ekranlarga kirish** *(2026-10-15: asoschi qarori, Q1)*: har bir ekran tafsilotidagi "Rol/ruxsat" qatorida faqat shu ekranning odatiy (operatsion) roli ko'rsatilgan; Egasi tenantning barcha ruxsatlarining supersetiga ega bo'lgani uchun (`01-rollar-va-ssenariylar.md`, 6-bo'lim) quyida alohida sanalmagan bo'lsa ham **har doim** har qanday ekranga (shu jumladan POS-01…15) kira oladi va shu ekrandagi har qanday `Y`/`T` amalni bajara oladi; faqat `platform.admin` (ADM-01) bundan mustasno.
- **Ma'lumot manbai** — REST `/api/v1/<resource>` uslubida, kebab-case ko'plik yo'l (`/goods-receipts`), `spec/02-arxitektura/13-api-katalog-*.md` katalogiga mos nomlar bilan moslashtirildi (`spec/tekshiruv/qabul-7-ekran-api.md` E-01 jadvali); `/auth/*`, `/billing/pay`, `/billing/export-my-data` — `/api/v1`siz. *(2026-10-15: qabul-6/7)*
- **Holatlar** — har ekranda quyidagi yetti holatning tegishlilari ko'rsatiladi: `loading` (skeleton), `empty` (`EmptyState`), `error` (`ErrorState`), `offline` (`OfflineBadge` + funksional cheklov), `no-permission` (`NoPermissionState`, 403 `PERMISSION_DENIED`), `subscription-restricted` (`SubscriptionRestrictedState`, 403 `SUBSCRIPTION_RESTRICTED` — faqat `/login`, to'lov va POS-01 bundan mustasno, chunki ular bu holatning o'zini ko'rsatadi), **`subscription-grace`** — `GET /billing/subscription.status=grace`: barcha ekran odatdagidek ishlaydi, shell tepasida qizil `aria-live="assertive"` banner «Obuna muddati o'tdi. {HH:mm} ichida to'lang, aks holda kassa to'xtaydi» + "To'lash" havolasi (BO-19); muddatdan 3/1/0 kun oldin sariq banner «Obuna {sana} da tugaydi» (US-M17-03). *(2026-10-15: qabul-6/7)*
- **Audit/analytics** — `audit_log.action` — nuqtali `domen.fe'l` uslubida (masalan `sale.draft_voided`); mahsulot-analitika (faqat ichki telemetriya) voqealari — `snake_case` (masalan `receipt_printed`); ikkisi aralashtirilmaydi. *(2026-10-15: qabul-6/7, E-31)*
- **Validatsiya** — `react-hook-form` + `zod`; backend bir xil xato shaklini (`field`, `code`) qaytaradi (`08-frontend-arxitekturasi.md` §3).

---

# A. Android POS / veb-kassa ekranlari (POS-01…15)

## POS-01 — Kassaga kirish / Smena ochish

- **Maqsad**: kassirni (yoki har qanday POS foydalanuvchisini) autentifikatsiya qilish (PIN, qurilma OAuth sessiyasi ichida), so'ng rolga qarab smenani ochish yoki to'g'ridan-to'g'ri ombor menyusiga yo'naltirish. *(2026-10-15: qabul-6/7, E-29)* Ekran ikki qadamga bo'linadi: ① **"PIN bilan kirish"** — har qanday POS foydalanuvchisi (Kassir, Omborchi); ② rolga qarab: `shift.open` huquqi bor bo'lsa (Kassir) — "Smenani ochish" qadami; `shift.open` yo'q bo'lsa (Omborchi) — to'g'ridan-to'g'ri POS-08/POS-09/POS-10 menyusiga o'tadi, smena ochmaydi.
- **Rol/ruxsat**: Kassir, Omborchi (PIN kirish — ruxsatsiz, autentifikatsiya o'zi); smena ochish — `shift.open`; huquqsiz foydalanuvchi (hech qaysi POS roli bo'lmagan) kira olmaydi.
- **Route**: `/pos/login`
- **Layout** (ASCII — `04-ekranlar-va-ux.md` §6 asosida):

```
┌───────────────────────────────────────┐
│  AIOS Kassa              [UZ/RU]  🔴   │
├───────────────────────────────────────┤
│        Filial: "Chilonzor-3" (qurilmaga bog'langan, faqat ko'rsatiladi) │
│   PIN kod:  [ * * * * ]                │
│        [ 1 ][ 2 ][ 3 ]  [ 4 ][ 5 ][ 6 ]│
│        [ 7 ][ 8 ][ 9 ]  [  ][ 0 ][ ⌫ ] │
│         [  SMENANI OCHISH  ]  (Kassirda)│
│   Boshlang'ich naqd:  [ 500 000 ]      │
│   PIN/parolni unutdim?                 │
└───────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `branchId` | Filial | Филиал | Faqat ko'rsatish (matn) | — | — | `devices.cash_register_id` orqali avtomatik aniqlangan filial *(2026-10-15: qabul-6/7, E-29 — `Select` olib tashlandi, qurilma filialga bog'langan)* | — |
| `pin` | PIN kod | PIN-код | `PinPad` (4–6 raqam) | Ha | Faqat raqam, 4–6 ta | — | 6 |
| `openingCash` | Boshlang'ich naqd | Начальная наличность | `MoneyInput` | Ha (`shift.open` bor foydalanuvchida smena ochishda) | ≥0, butun son | 0 yoki oxirgi smena yopilgan qoldiq (taxmin) | 9 999 999 999 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| PIN bilan kirish | — | Yo'q | PIN tasdiqlanadi; `shift.open` bor bo'lsa "Smenani ochish" qadami ko'rsatiladi, yo'q bo'lsa (Omborchi) to'g'ridan-to'g'ri POS-08/09/10 menyusiga o'tadi *(2026-10-15: qabul-6/7, E-29)* |
| Smenani ochish | `shift.open` | Yo'q | `shift.opened` voqeasi, POS-02ga o'tish |
| PIN/parolni unutdim | — | *(2026-10-15: asoschi qarori, Q7)* OTP oynasi (`purpose=recovery`) — kod birinchi navbatda Telegram botga, ulanmagan bo'lsa SMS'ga (zaxira) | Yangi PIN/parol o'rnatish seansi |

- **Ma'lumot manbai**: `POST /auth/pin/verify` (online qo'shimcha tasdiq, 4.3-bo'lim) *(2026-10-15: qabul-6/7, E-01 — `/api/v1`siz, 12-auth §20)*, outbox: `shift.opened` (`04-offline-sync.md` §2), `GET /auth/license` (litsenziya tokeni, offline qurilma).
- **Holatlar**: `loading` (qurilma/filial ma'lumoti yuklanmoqda) · `empty` — yo'q (smena ochish bo'sh bo'lmaydi) · `error` (PIN noto'g'ri — standart xabar #17/#18) · `offline` (PIN mahalliy heshga qarshi tekshiriladi, litsenziya token amal qilsa) · `no-permission` — yo'q (login ekrani) · `subscription-restricted` — butun ekran qizil banner, PIN maydoni o'chirilgan; "Ma'lumotlarimni yuklab olish" tugmasi PIN ekranida emas — `/login?reason=subscription_expired`ga yo'naltiradi (telefon+parol identifikatsiyasi + `purpose=data_export` OTP — *(2026-10-15: asoschi qarori, Q7)* Telegram bot birinchi, SMS zaxira, D2) (`12-autentifikatsiya-oauth2.md` §16) *(2026-10-15: qabul-6/7, E-04)* · **`subscription-grace`** — ekran odatdagidek ishlaydi, tepada qizil banner (yuqoridagi "Qanday o'qish kerak").
- **Klaviatura**: raqam tugmalari PIN kiritadi, `Enter` tasdiqlaydi, `Esc` tozalaydi.
- **Audit/analitika**: `login_success`, `login_failed`, `account_locked`, `shift.opened`, `pos_login_screen_viewed`.
- **Bog'liq US**: US-M01-04, US-M17-03 (lockout holati), US-M13-06 (parol/PIN tiklash).

---

## POS-02 — Sotish paneli (asosiy chek)

- **Maqsad**: tovarlarni chekka qo'shish, chegirma qo'llash, jami summani ko'rsatish.
- **Rol/ruxsat**: Kassir (`sales.create`, `discount.give`). *(2026-10-15: qabul-6/7, E-02)*
- **Route**: `/pos/sale`
- **Layout**: `04-ekranlar-va-ux.md` §6 POS-02 wireframe'i aynan shu ko'rinishda qo'llanadi (status panel + chek ro'yxati + skaner/qidiruv + jami + CHEGIRMA/BEKOR/TO'LOV).
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `customerId` | Mijoz | Клиент | `Combobox` | Yo'q | Mavjud mijoz yoki yangi | Bo'sh (anonim) | — |
| `barcode` | Skanerlash/qidiruv | Сканирование/поиск | `BarcodeField` | — | Katalogda mavjud kod | — | 64 belgi |
| `lines[].qty` | Miqdor | Количество | `QtyInput` | Ha | >0, o'lchov birligiga mos kasr | 1 | 99 999 |
| `discountPercent` | Chegirma % | Скидка % | `Input` (number) | Yo'q | 0–100, PIN'siz ≤5% (standart, M13 orqali sozlanadi) | 0 | 100 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Skanerlash | `sales.create` | Yo'q | Qator qo'shiladi; markirovkalangan tovarda `MarkingBadge` |
| Qidirish | `sales.create` | Yo'q | `Combobox` natija ro'yxati |
| CHEGIRMA | `discount.give` (>5% — `discount.approve`, `ApprovalDialog`) *(2026-10-15: qabul-6/7, E-02)* | >5%da Menejer/Egasi PIN | Chek summasi qayta hisoblanadi |
| BEKOR (qator/chek) | `sales.void` | "Haqiqatan bekor qilasizmi?" (#15) | `sale.draft_voided` audit voqeasi, fiskal chek yo'q |
| TO'LOV ▶ | `sales.create` | Yo'q | POS-03ga o'tish |
| + Mijoz | `debts.create` yoki `sales.create` | Yo'q | Mijoz tanlash/yaratish bottom sheet; online skanerda `POST /api/v1/marking/verify` (`sale.created`dan oldin), "+ Mijoz" bosilganda `counterparty.created` voqeasi *(2026-10-15: qabul-6/7, E-01)* |

- **Ma'lumot manbai**: lokal Dexie `catalog`/`prices`/`customers` (`04-offline-sync.md` §1); outbox `sale.created` (payload: `sales`+`sale_lines`+`sale_payments`); `GET /api/v1/products?search=` (online qidiruv zahira) *(2026-10-15: qabul-6/7, E-01)*; `POST /api/v1/marking/verify` (online markirovka tekshiruvi); `counterparty.created` voqeasi.
- **Holatlar**: `loading` (katalog snapshot yuklanmoqda) · `empty` ("Chekni boshlang, skanerlang") · `error` ("Mahsulot topilmadi" #21; "Markirovka o'qilmadi" (#23) → 3 urinishdan keyin **DataMatrix kodini qo'lda kiritish** maydoni — faqat online, `POST /marking/verify` bilan tekshiriladi, offline'da qo'lda kiritish taqiq, audit `marking.manual_entry`; MXIK — tovar katalogi rekviziti, markirovka kodi emas) *(2026-10-15: qabul-6/7, E-16)* · `offline` (status panel 🟡/🔴, TO'LOV faol qoladi, markirovka `fiscal-pending` belgisi) · `no-permission` — modul butunlay yopiq bo'lmaydi (Kassir uchun asosiy ekran) · `subscription-restricted` — ekran ochilmaydi, `/pos/login`ga redirect.
- **Klaviatura**: `F1` skaner fokus, `F2` chegirma, `F3` mijoz, `F4` to'lov, `F5` nasiya, `+`/`-` miqdor, `Delete` qatorni o'chirish, `Enter` skaner natijasini qabul qilish.
- **Audit/analitika**: `sale_line_added`, `discount_applied`, `sale.draft_voided`, `marking.offline_sold`, `marking.offline_refused_no_price`, `marking.manual_entry`.
- **Bog'liq US**: US-M01-01, US-M01-02, US-M01-03, US-M03-01, US-M09-03, US-M09-07.

---

## POS-03 — To'lov usuli va hisoblash

- **Maqsad**: to'lov turini tanlash (naqd/karta-qo'lda/UzQR/Payme/Click/Uzum/nasiya), qaytimni hisoblash, chekni yakunlash.
- **Rol/ruxsat**: Kassir (`sales.create`).
- **Route**: `/pos/sale/payment`
- **Layout**: `04-ekranlar-va-ux.md` §6 POS-03 wireframe'i.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `paymentMethod` | To'lov usuli | Способ оплаты | Tugmalar guruhi | Ha | `cash\|card_manual\|uzqr\|payme\|click\|uzum\|debt` | — | — |
| `cashReceived` | Olingan naqd | Полученная наличность | `MoneyInput` | Ha (naqd bo'lsa) | ≥ to'lanadigan summa | To'lanadigan summa | 9 999 999 999 |
| `terminalRef` | Terminal operatsiya raqami | Номер операции терминала | `Input` | Yo'q (ixtiyoriy) | Max 40 belgi | — | 40 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| NAQD/KARTA/UzQR/Payme/Click/Uzum/NASIYA | `sales.create` | Nasiya limitdan oshsa `ApprovalDialog` | To'lov biriktiriladi |
| TASDIQLASH | `sales.create` | Yo'q | `sale.created` outbox, POS-04ga o'tish |

- **Ma'lumot manbai**: `POST /api/v1/payments/{provider}/checkout` → poll `GET /api/v1/payments/{provider}/{provider_tx_id}` (webhook — server tomoni, ekran o'zi chaqirmaydi) *(2026-10-15: qabul-6/7, E-01, 13-1 §16)*; outbox `sale.created` (`sale_payments.method`).
- **Holatlar**: `loading` (provayder javobi kutilmoqda) · `empty` (summa 0) · `error` ("Payme javob bermadi..." , yetarli naqd yo'q) · `offline` — UzQR/Payme/Click/Uzum tugmalari o'chirilgan (kulrang), naqd/karta(qo'lda)/nasiya faol · `no-permission` — yo'q · `subscription-restricted` — bu ekranga kirilmaydi.
- **Klaviatura**: raqam tugmalari olingan naqdni kiritadi, `Enter` tasdiqlaydi, `Esc` POS-02ga qaytaradi.
- **Audit/analitika**: `payment_method_selected`, `sale.created`, `payment_provider_timeout`.
- **Bog'liq US**: US-M01-01, US-M01-05 (UzQR), US-M08-01 (nasiya).

---

## POS-04 — Chekni chop etish / QR orqali yuborish

- **Maqsad**: fiskal chekni chop etish, QR orqali elektron chek yuborish, qayta chop etish.
- **Rol/ruxsat**: Kassir (`sales.create`; qayta chop etish ham `sales.create` — tugma yashirilmaydi, har chop audit yoziladi) *(2026-10-15: qabul-6/7, E-02, 13-1 §6)*.
- **Route**: `/pos/sale/receipt`
- **Layout**:

```
┌───────────────────────────────────────┐
│ 🟢 ONLAYN                    22:43    │
├───────────────────────────────────────┤
│   Chek № K-01-2026-000154              │
│   Fiskal belgi: ****  QR: [▦]          │
│   Summa: 69 000 so'm                   │
│                                         │
│   [ 🖨 CHOP ETISH ]  [ 📱 QR CHEK ]     │
│   [ 🔁 QAYTA CHOP ETISH ]              │
│   [  YANGI CHEK BOSHLASH  ]            │
└───────────────────────────────────────┘
```

- **Maydonlar**: yo'q (faqat ko'rsatish ekrani) — `ReceiptPreview` komponenti chekni render qiladi (`08-dizayn-tizimi.md` §13.1). *(2026-10-15: asoschi qarori, Q2)* `ReceiptPreview` har bir tovar qatorini **ikki tilda** chiqaradi: `"{name} / {name_ru}"` (`name_ru` bo'sh bo'lsa faqat `name`), shuningdek sarlavha/yakun matnlari ikki tilda ("Jami / Итого", "Naqd / Наличные" va h.k., to'liq ro'yxat — `08-dizayn-tizimi.md` chek shabloni bo'limi).
- *(2026-10-15: asoschi qarori, Q3)* **Nasiyaga sotuvda bu ekran ochilmaydi**: to'lov usuli to'liq "Nasiya" bo'lgan sotuvda fiskal chek shu zahotda chiqarilmaydi (`fiscal_receipts` yaratilmaydi, holat `deferred`) — POS-03 to'g'ridan-to'g'ri POS-06 (yoki POS-02'ga qaytish) ga o'tadi, bu ekran faqat **naqd/karta qismi bo'lgan** (to'liq yoki aralash to'lovning naqd qismi) sotuvlarda ko'rsatiladi. Qarz to'langanda chiqariladigan fiskal chek — alohida oqim, POS-13/BO-06 (`debt_settlement`).
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Chop etish | `sales.create` | Yo'q | `shared/lib/printer` runtime tanlovi: Chromium (Windows/Android) — WebUSB/Serial/Bluetooth/tarmoq; **iOS o'rnatilgan PWA — faqat `CloudPrintAdapter`** (Star CloudPRNT/Epson Server Direct Print klassi); hech biri sozlanmagan bo'lsa tugma o'rniga "QR chek" asosiy bo'ladi *(2026-10-15: qabul-6/7, E-12)* |
| QR chek | `sales.create` | Yo'q | Elektron chek havolasi (QR/Telegram) |
| Qayta chop etish | `sales.create` *(2026-10-15: qabul-6/7, E-02)* | Yo'q | "NUSXA" belgisi bilan chop, `receipt.reprinted` audit |
| Yangi chek boshlash | `sales.create` | Yo'q | POS-02ga qaytish |

- **Ma'lumot manbai**: `GET /api/v1/fiscal-receipts?sale_id=` (online), lokal Dexie (offline); event `receipt.reprinted` *(2026-10-15: qabul-6/7, E-01, 13-1 §6/§14)*.
- **Holatlar**: `loading` (fiskal belgi kutilmoqda — online) · `empty` — yo'q · `error` (printer ulanmagan/qog'oz tugagan → "QR orqali elektron chek" taklifi, #27) · `offline` (chek lokal saqlanadi, "offlayn" belgisi, fiskal belgi keyin) · `no-permission` — qayta chop etish huquqi yo'q bo'lsa tugma ko'rinmaydi · `subscription-restricted` — bu ekranga kirilmaydi · **iOS, bulut printer sozlanmagan** — «Chop etish uchun bulut-printerni ulang» + `/install#cloud-print` havolasi *(2026-10-15: qabul-6/7, E-12)*.
- **Klaviatura**: `Ctrl+P` qayta chop etish, `Enter` yangi chek.
- **Audit/analitika**: `receipt.reprinted`, `receipt_printed`, `receipt_print_failed`, `electronic_receipt_sent`.
- **Bog'liq US**: US-M01-01, chekka holat "qayta chop etish" (`02-modullar-talablari.md` M01).

---

## POS-05 — Mijozdan tovar qaytarish

- **Maqsad**: asl chek bo'yicha to'liq/qisman qaytarish.
- **Rol/ruxsat**: Kassir (`returns.create`); limitdan yuqori/chek topilmagan — `returns.approve` (Menejer).
- **Route**: `/pos/returns`
- **Layout**: `04-ekranlar-va-ux.md` §6 POS-05 wireframe'i.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `receiptQuery` | Chekni qidirish | Поиск чека | `Input`/skaner | Ha | Chek raqami yoki QR | — | 40 |
| `lines[].selected` | Qaytariladigan qator | Возвращаемая строка | `Checkbox` | Ha (≥1) | — | Belgilanmagan | — |
| `reason` | Sabab | Причина | `Select` | Ha | `defective` (Nuqsonli) / `wrong_item` (Mos kelmadi) / `customer_changed_mind` (Fikri o'zgardi) / `other` (Boshqa) *(2026-10-15: qabul-6/7, E-14)* | — | — |
| `refundMethod` | Qaytarish usuli | Способ возврата | Tugmalar | Ha | `cash\|card\|debt_adjustment` | Asl to'lov usuli *(2026-10-15: qabul-6/7, E-14)* | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| QAYTARISHNI TASDIQLA | `returns.create` | 100 000 so'mdan yuqori yoki chek topilmagan — `ApprovalDialog` (Menejer PIN, har doim) | `return.created` outbox, ombor/qarz/pul tuzatiladi |

- **Ma'lumot manbai**: `GET /api/v1/sales?number=` (online) yoki lokal keshi — **katalogda yo'q, K1-01 bilan qo'shiladi**; outbox `return.created`. *(2026-10-15: qabul-6/7, E-01)*
- **Holatlar**: `loading` · `empty` (chek topilmagan, #20) · `error` ("Bu chek allaqachon qaytarilgan") · `offline` — oddiy tovar lokal yoziladi; **markirovkalangan tovar qatori uchun "Qaytarish" tugmasi bloklanadi** ("Qaytarish uchun internet kerak", #26) · `no-permission` — ekran ochilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F6` (global) ekranni ochadi, `Enter` chekni qidiradi.
- **Audit/analitika**: `return.created`, `return_blocked_offline_marking`.
- **Bog'liq US**: US-M02-01, US-M02-02.

---

## POS-06 — Nasiyaga sotish

- **Maqsad**: mijozga kredit limiti ichida (yoki limitsiz, offline bayroq bilan) qarzga sotish.
- **Rol/ruxsat**: Kassir (`debts.create`); limitdan oshganda `debts.approve` (Menejer).
- **Route**: `/pos/sale/credit`
- **Layout**: `04-ekranlar-va-ux.md` §6 POS-06 wireframe'i.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `customerId` | Mijoz | Клиент | `Combobox` + `+ Yangi` | Ha | Mavjud yoki yangi (ism+telefon) | — | — |
| `promiseDate` | Va'da sanasi | Обещанная дата оплаты | `Calendar` + tezkor tugmalar (7/14/30 kun) *(2026-10-15: qabul-6/7, E-17 — `dueDays` nomi `promiseDate`ga almashtirildi)* | Yo'q | ≥ bugun | Bo'sh | — |
| `note` | Izoh | Комментарий | `Textarea` | Yo'q | — | — | 200 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| NASIYAGA RASMIYLASHTIR | `debts.create` | Limitdan oshsa `ApprovalDialog` (Menejer PIN; offlaynda bayroq bilan davom) | `sale.created` (`sale_payments.method=debt`, `due_date`=`promiseDate`), holat `deferred` — *(2026-10-15: asoschi qarori, Q3)* **fiskal chek chiqarilmaydi**, POS-04 ekrani ochilmaydi; chek qarz to'langanda (POS-13/BO-06, `debt_settlement`) chiqadi |

- **Ma'lumot manbai**: `customers`/`debt_balances` (lokal, `04-offline-sync.md` §1); mijoz B2B bo'lsa `POST /api/v1/einvoices` (`direction=out`) — **katalogda yo'q, K1-04 bilan qo'shiladi** (BO-15da imzolanadi). *(2026-10-15: qabul-6/7, E-01)*
- **Holatlar**: `loading` · `empty` (mijoz tanlanmagan) · `error` ("Limitdan oshdi — Menejer PIN kiriting") · `offline` (limit oxirgi sinxron ma'lumot asosida, sotuv **bloklanmaydi**, `limit_exceeded=true` bayrog'i) · `no-permission` — tugma ko'rinmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F5` (global) ochadi.
- **Audit/analitika**: `debt_sale_created`, `debt_limit_exceeded_offline`.
- **Bog'liq US**: US-M08-01, US-M08-02, US-M01-06 (B2B e-faktura eslatmasi).

---

## POS-07 — Smena yopish, Z-hisobot

- **Maqsad**: kunlik savdo jamlanmasini ko'rsatish va smenani yopish.
- **Rol/ruxsat**: Kassir (`shift.close`).
- **Route**: `/pos/shift/close`
- **Layout**:

```
┌───────────────────────────────────────┐
│ 🟢 ONLAYN                    21:58    │
├───────────────────────────────────────┤
│  Smena №7 — 09:02 dan boshlab          │
│  Naqd: 2 100 000  Karta: 1 500 000     │
│  Nasiya: 650 000  Jami: 4 250 000      │
│  Cheklar: 112   Bekor qilingan: 2      │
│          [  SMENANI YOPISH  ]          │
└───────────────────────────────────────┘
```

- **Maydonlar**: yo'q (jamlanma faqat ko'rsatish) — naqd sanash POS-15da alohida.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Smenani yopish | `shift.close` | "Smenani yopasizmi? Keyin qayta ocholmaysiz" | POS-15ga o'tadi (naqd sanash) → tasdiq → **bitta** `shift.closed` voqeasi (`counted_cash`, `counted_card_total`, `variance_note`) → Z-hisobot *(2026-10-15: qabul-6/7, E-11 — oqim tartibi: POS-07 (jamlanma) → POS-15 (sanash) → tasdiq → `shift.closed` → Z-hisobot)* |

- **Ma'lumot manbai**: `GET /api/v1/shifts/{id}` (+ `running_totals`, K1-02; lokal jamlanma offline ham hisoblanadi) → yopilgandan keyin `GET /api/v1/shifts/{id}/z-report`; outbox `shift.closed`. *(2026-10-15: qabul-6/7, E-01/E-11, 13-1 §3.3)*
- **Holatlar**: `loading` · `empty` (savdo bo'lmagan kun) · `error` (sinxronlanmagan cheklar bor — ogohlantirish, lekin yopishni bloklamaydi) · `offline` (Z-hisobot lokal shakllanadi, OFD'ga ulanganda yuboriladi) · `no-permission` — yo'q · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F8` (global) ochadi.
- **Audit/analitika**: `shift.closed`, `z_report_generated`, `cash_discrepancy_flagged`. *(2026-10-15: qabul-6/7, E-11)*
- **Bog'liq US**: US-M01-04.

---

## POS-08 — Yetkazib beruvchidan tovar qabul qilish (kirim)

- **Maqsad**: xaridnoma bo'yicha kelgan tovarni skanerlab solishtirish, qabul qilish.
- **Rol/ruxsat**: Omborchi (`purchases.receive`). *(2026-10-15: qabul-6/7, E-02 — `stock.create` → `purchases.receive`)*
- **Route**: `/pos/warehouse/receive`
- **Layout**: `04-ekranlar-va-ux.md` §6 POS-08 wireframe'i.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `purchaseOrderId` | Xaridnoma | Заказ на закупку | `Select` | Ha | Ochiq xaridnomalardan biri | — | — |
| `lines[].receivedQty` | Kelgan miqdor | Полученное количество | `QtyInput` | Ha | ≥0 | Buyurtma miqdori | — |
| `lines[].discrepancyReason` | Nomuvofiqlik sababi | Причина несоответствия | `Select` | Farq bo'lsa Ha | — | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Markirovkani skanerlash | `purchases.receive` | 2–3 urinishdan keyin qo'lda MXIK maydoni | Kod `marking_codes` ga yoziladi |
| QABULNI YAKUNLASH | `purchases.receive` | Farq bo'lsa "Nomuvofiqlik bilan yakunlaysizmi?" | `POST /goods-receipts` (draft) → Buxgalter BO-04 "Kirimlar" tabida `POST /goods-receipts/{id}/post` (`purchases.post`) bilan o'tkazadi — qoldiq shu paytda oshadi *(2026-10-15: qabul-6/7, E-13)* |

- **Ma'lumot manbai**: `GET /api/v1/purchase-orders/{id}` → `POST /api/v1/goods-receipts` (`po_id` bilan) → `PATCH /api/v1/goods-receipts/{id}` → `POST /api/v1/goods-receipts/{id}/post` (online, E-13); **voqea yo'q** — `purchase.received` outbox olib tashlandi; `marking_codes`. *(2026-10-15: qabul-6/7, E-01, 13-2 §8)*
- **Holatlar**: `loading` · `empty` (xaridnoma tanlanmagan) · `error` (markirovka o'qilmadi, miqdor mos kelmadi) · `offline` — **qabul yopiq** ("Tovar qabul qilish uchun internet kerak"); sanash/skanerni lokal davom ettirish mumkin, yakunlash faqat online (markirovkalangan tovar qabulida egalik o'zgaradi, kirim faqat online — 13-2 Asosiy xulosa 7) *(2026-10-15: qabul-6/7, E-13)* · `no-permission` — ekranga kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F1` skaner fokus.
- **Audit/analitika**: `goods_receipt.drafted`, `marking_scan_failed`, `receive_discrepancy_flagged`. *(2026-10-15: qabul-6/7, E-01/E-13)*
- **Bog'liq US**: US-M07-02, US-M04-01.

---

## POS-09 — Omborlar orasida tovar ko'chirish

- **Maqsad**: filial/ombor ichida/orasida tovar yuborish va qabul qilish.
- **Rol/ruxsat**: Omborchi (`transfer.create`, `transfer.receive`).
- **Route**: `/pos/warehouse/transfer`
- **Layout**:

```
┌───────────────────────────────────────┐
│ 🟡 OFFLAYN · 1 chek kutmoqda           │
├───────────────────────────────────────┤
│  Manba: Asosiy ombor ▾  →  Manzil: ▾   │
│  [ 📷 Skanerlash ]                     │
│  ┌─────────────────────────────────┐   │
│  │ Coca-Cola 1.5L         x10      │   │
│  └─────────────────────────────────┘   │
│          [  YUBORISH  ]                │
└───────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `fromBranchId` | Manba ombor | Склад-источник | `Select` | Ha | ≠ `toBranchId` | Joriy filial | — |
| `toBranchId` | Manzil ombor | Склад-назначение | `Select` | Ha | ≠ `fromBranchId` | — | — |
| `lines[].qty` | Miqdor | Количество | `QtyInput` | Ha | ≤ mavjud qoldiq (overselling ogohlantiradi, bloklamaydi) | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| YUBORISH | `transfer.create` | Qoldiq yetarli emasligida ogohlantirish (davom etish mumkin) | `transfer.created`, manba ombor "yo'lda" |
| QABUL QILISH (qabul tomonda) | `transfer.receive` | Yo'q | `transfer.received`, manzil ombor oshadi |

- **Ma'lumot manbai**: `GET /api/v1/stock-balances?warehouse_id=`; offline — event `transfer.created`/`transfer.received` (payload — K1-03); online — `POST /api/v1/transfers` → `/send`, `POST /api/v1/transfers/{id}/receive`. *(2026-10-15: qabul-6/7, E-01, 13-2 §7/§13)*
- **Holatlar**: `loading` · `empty` (ombor tanlanmagan) · `error` (qoldiq yetarli emas) · `offline` (markirovkalangan tovar ham o'z filiallar orasida offline ko'chirilishi **ruxsat etiladi**, audit bilan) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F1` skaner fokus.
- **Audit/analitika**: `transfer.created`, `transfer.received`, `marking.transfer_offline`.
- **Bog'liq US**: US-M06-01, US-M06-02.

---

## POS-10 — Inventarizatsiya (jismoniy sanash)

- **Maqsad**: ombordagi tovarni jismoniy sanab, tizim qoldig'i bilan solishtirish.
- **Rol/ruxsat**: Omborchi (`stock.count.create`). *(2026-10-15: qabul-6/7, E-02)*
- **Route**: `/pos/warehouse/stocktake`
- **Layout**: `04-ekranlar-va-ux.md` §6 POS-10 wireframe'i.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `lines[].countedQty` | Sanalgan miqdor | Подсчитанное количество | `QtyInput` | Ha | ≥0 | Bo'sh | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Skanerlash / Qo'lda kirit | `stock.count.create` | Yo'q | Qator "sanalgan" deb belgilanadi |
| SANASHNI YAKUNLASH | `stock.count.create` | "Barcha tovarlar sanaldimi?" | `POST /api/v1/stock-counts/{id}/submit-for-review` → BO-03 "Inventarizatsiyalar" tabiga farq tasdiqlash uchun tushadi (E-08) |

- **Ma'lumot manbai**: `GET /api/v1/stock-counts/{id}`; offline — event `stock_count.line_recorded` (payload — K1-03), online — `POST /api/v1/stock-counts/{id}/lines`. *(2026-10-15: qabul-6/7, E-01, 13-2 §14)*
- **Holatlar**: `loading` · `empty` (sanash boshlanmagan) · `error` ("Bu shtrix-kod tizimda yo'q") · `offline` (to'liq lokal ishlaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F1` skaner fokus.
- **Audit/analitika**: `stock_count.line_recorded`, `stock_count_completed`.
- **Bog'liq US**: US-M05-01.

---

## POS-11 — Mahsulot va narxni tez qidirish

- **Maqsad**: narx/qoldiqni faqat ko'rish (sotuvsiz tezkor tekshirish).
- **Rol/ruxsat**: Kassir, Omborchi (`stock.view`). *(2026-10-15: qabul-6/7, E-02 — `prices.view` → `stock.view`)*
- **Route**: `/pos/lookup`
- **Layout**:

```
┌───────────────────────────────────────┐
│  🔍 [ Qidiruv: nom/kod/shtrix-kod ]     │
├───────────────────────────────────────┤
│  Coca-Cola 1.5L     18 000 so'm        │
│  Qoldiq: 12 dona   (5 daq. oldin)      │
└───────────────────────────────────────┘
```

- **Maydonlar**: `query` — Qidiruv — Поиск — `BarcodeField`/`Input` — majburiy emas — max 64.
- **Amallar**: yo'q (faqat ko'rish ekrani).
- **Ma'lumot manbai**: lokal `catalog`/`prices`/`stock` keshi.
- **Holatlar**: `loading` · `empty` (natija yo'q) · `error` — yo'q · `offline` (oxirgi sinxronlangan narx/qoldiq + "oxirgi yangilanish" vaqti) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F9` (global) ochadi.
- **Audit/analitika**: `price_lookup_viewed`.
- **Bog'liq US**: US-M09-03.

---

## POS-12 — Offline/sinxronizatsiya holati

- **Maqsad**: sinxronlanmagan hujjatlarni va 48 soatlik fiskal muddatni ko'rsatish.
- **Rol/ruxsat**: Barcha POS rollari — ruxsat tekshiruvi yo'q, har autentifikatsiyalangan POS foydalanuvchisi. *(2026-10-15: qabul-6/7, E-02 — `sync.view` kodi olib tashlandi)*
- **Route**: `/pos/sync`
- **Layout**: `04-ekranlar-va-ux.md` §6 POS-12 wireframe'i.
- **Maydonlar**: yo'q.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| QAYTA ULANISHGA URINISH | — | Yo'q | `POST /api/v1/sync/push` qayta chaqiriladi *(2026-10-15: qabul-6/7, E-01, 04-offline §3)* |

- **Ma'lumot manbai**: Dexie `outbox` (`04-offline-sync.md` §1–2), `POST /api/v1/sync/push` natijalari.
- **Holatlar**: `loading` · `empty` (hammasi sinxron — ekran ko'rinmaydi/kichik ko'k belgi) · `error` ("Ulanish muvaffaqiyatsiz, 2 daqiqadan keyin qayta urinadi") · `offline` (asosiy holat — ro'yxat va 48 soat hisoblagichi) · `no-permission` — yo'q · `subscription-restricted` — `sync.drain` holatida ham ko'rsatiladi (fonda drain ishlaydi, UI login sahifasini ko'rsatadi, `12-autentifikatsiya-oauth2.md` §16.4).
- **Klaviatura**: `F12` (global) ochadi.
- **Audit/analitika**: `sync_retry_clicked`, `sync_drain_started`, `sync_drain_completed`.
- **Bog'liq US**: US-M01-02.

---

## POS-13 — Qarz daftari (tezkor)

- **Maqsad**: mijoz qarzini ism/telefon bo'yicha tezkor ko'rish, to'lov qabul qilish; yangi qarz yozish endi POS-02 orqali normal (tovar qatorlari bilan) sotuv sifatida amalga oshadi — tovarsiz, erkin summali qarz yo'q. *(2026-10-15: qabul-6/7, E-03; 2026-10-15: asoschi qarori, Q3 — "fiskal chekli" aniqlashtirildi)* Fiskal chek bu bosqichda **chiqarilmaydi** (holat `deferred`) — chek faqat qarz to'langanda chiqadi (pastda, TO'LOV QABUL QILISH).
- **Rol/ruxsat**: Kassir, Egasi (`debts.create` yoki `debts.payment.accept` — ko'rish; `debts.create` — yozish; `debts.payment.accept` — to'lov qabul qilish). *(2026-10-15: qabul-6/7, E-02)*
- **Route**: `/pos/debts`
- **Layout**:

```
┌───────────────────────────────────────┐
│  🔍 Mijoz: [ ism yoki telefon    ]     │
├───────────────────────────────────────┤
│  Aliyev Botir — Qarzi: 350 000 so'm    │
│  12.10 +45 000 (non, sut)  izoh: ...   │
│  08.10 -100 000 (to'lov)               │
│  [ TO'LOV QABUL QILISH ] [ QARZ YOZISH]│
└───────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `search` | Ism yoki telefon | Имя или телефон | `Combobox` | Ha | — | — | 64 |
| `payment.amount` | To'lov summasi | Сумма платежа | `MoneyInput` | Ha (to'lovda) | >0, ≤ joriy qarz (taxmin — ortig'ini qabul qilish siyosati ochiq) | — | — |
| `promiseDate` | Yangi va'da sanasi | Новая обещанная дата | `Calendar` | Yo'q (qoldiq qolsa ixtiyoriy) | ≥ bugun | Bo'sh | — | *(2026-10-15: qabul-6/7, E-17, K1-09)* |

*(2026-10-15: qabul-6/7, E-03)* `newDebt.amount`/`newDebt.note` maydonlari **olib tashlandi** — tovarsiz, erkin summali qarz yozish qoidaga ("qarzga sotuv ham tovar qatorlari bilan oddiy sotuv hujjati sifatida yoziladi, faqat fiskal chek to'lovgacha kechiktiriladi", 02 M08 Qoidalar, Q3) zid edi.

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| QARZ YOZISH | `debts.create` | Yo'q | POS-02ni shu mijoz tanlangan holda ochadi, to'lov usuli oldindan `debt` (POS-06 oqimi); natija — `sale.created` (`payments[].method=debt`), holat `deferred` — *(2026-10-15: asoschi qarori, Q3 — avvalgi "+ fiskal chek" qoidasi almashtirildi)* **fiskal chek bu bosqichda chiqarilmaydi** *(2026-10-15: qabul-6/7, E-03 — to'liq qayta yozildi)* |
| TO'LOV QABUL QILISH | `debts.payment.accept` | Yo'q | `debt_payment.created` → `/post`, eng eski qarzdan yopiladi; qoldiq qolsa `promiseDate` bilan joriy va'da yangilanadi. *(2026-10-15: asoschi qarori, Q3)* **To'langan summaga fiskal chek chiqariladi** (`fiscal_receipts.kind=debt_settlement`), tovar qatorlari yopilgan sotuv(lar)dan proporsional; natijada POS-04 (chek) ekraniga o'tiladi |

Tovarsiz "eski qarz"ni kiritish faqat BO-06 → "Boshlang'ich qarz" (`POST /api/v1/debt-openings`, faqat Egasi) orqali amalga oshadi. *(2026-10-15: qabul-6/7, E-03)*

- **Ma'lumot manbai**: lokal `customers`/`debt_balances` + online `GET /api/v1/counterparties/{id}/debt-ledger`; event `debt_payment.created`. *(2026-10-15: qabul-6/7, E-01, 13-1 §12)*
- **Holatlar**: `loading` · `empty` (qarzdor yo'q) · `error` (telefon formati noto'g'ri, #13) · `offline` (to'liq ishlaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F7` (global) ochadi.
- **Audit/analitika**: `debt_sale_created` (POS-02/06 oqimi orqali), `debt_payment_collected`. *(2026-10-15: qabul-6/7, E-03)*
- **Bog'liq US**: US-M08-05, US-M08-06, US-M08-09, US-M08-11. *(2026-10-15: qabul-6/7, E-05)*

---

## POS-14 — Kassaga pul qo'yish / kassadan pul olish

- **Maqsad**: naqd pul harakatini sabab bilan yozish.
- **Rol/ruxsat**: Kassir — qo'yish `cash.deposit`, olish `cash.withdraw` (limit); >50 000 so'm olishda tasdiqlovchining `cash.withdraw` limiti summani qoplashi shart (alohida `cash.approve` kodi yo'q, 13-1 §2.4). *(2026-10-15: qabul-6/7, E-02)*
- **Route**: `/pos/cash-movement`
- **Layout**:

```
┌───────────────────────────────────────┐
│  [ Pul qo'yish ]   [ Pul olish ]       │
├───────────────────────────────────────┤
│  Summa:  [        ]                    │
│  Sabab:  [ Xarajat to'lovi      ▾ ]    │
│  Izoh:   [                      ]      │
│          [  TASDIQLASH  ]              │
└───────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `direction` | Yo'nalish | Направление | Tugmalar | Ha | `in\|out` | — | — |
| `amount` | Summa | Сумма | `MoneyInput` | Ha | >0 | — | 9 999 999 999 |
| `reason` | Sabab | Причина | `Select` | Ha | `owner_withdrawal` (Egasi oldi) / `collection` (Inkasso) / `deposit` (Qo'yish) / `expense` (Xarajat to'lovi) / `other` (Boshqa) *(2026-10-15: qabul-6/7, E-15)* | — | — |
| `expenseCategoryId` | Xarajat toifasi | Категория расхода | `Select` (`GET /expense-categories` keshidan) | Ha (`reason=expense`da) *(2026-10-15: qabul-6/7, E-15)* | — | — | — |
| `note` | Izoh | Комментарий | `Textarea` | Reason="Boshqa"da Ha | — | — | 200 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| TASDIQLASH | `cash.deposit` (qo'yish) / `cash.withdraw` (olish) | >50 000 so'm olishda `ApprovalDialog` (tasdiqlovchining `cash.withdraw` limiti summani qoplashi shart) | `cash_movement.created`; `reason=expense` → server bir tranzaksiyada `expenses(source=cash, status=posted)` yozadi (M15, K1-06) *(2026-10-15: qabul-6/7, E-02/E-15)* |

- **Ma'lumot manbai**: outbox `cash_movement.created`.
- **Holatlar**: `loading` · `empty` — yo'q · `error` (PIN noto'g'ri) · `offline` (to'liq ishlaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: raqamlar summa kiritadi, `Enter` tasdiqlaydi.
- **Audit/analitika**: `cash_movement.created`.
- **Bog'liq US**: US-M16-01.

---

## POS-15 — Smena yopishda naqdni sanash

- **Maqsad**: jismoniy sanalgan naqdni kutilgan naqd bilan solishtirish, farqni qayd etish.
- **Rol/ruxsat**: Kassir (`cash.count.shift`). *(2026-10-15: qabul-6/7, E-02)*
- **Route**: `/pos/shift/cash-count`
- **Layout**: `04-ekranlar-va-ux.md` tasvirlangan mazmunga mos sodda forma.

```
┌───────────────────────────────────────┐
│  Kutilgan naqd:     2 100 000 so'm     │
│  Sanalgan naqd:     [            ]     │
│  Karta jami (qo'lda belgilangan):      │
│                     1 500 000 so'm     │
│  Farq:              0 so'm             │
│  Izoh (farq bo'lsa): [            ]    │
│          [  DAVOM ETISH (Z-hisobot) ]  │
└───────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `countedCash` | Sanalgan naqd | Подсчитанная наличность | `MoneyInput` | Ha | ≥0 | — | 9 999 999 999 |
| `note` | Izoh | Комментарий | `Textarea` | Farq ≠0 bo'lsa Ha | — | — | 200 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| DAVOM ETISH | `cash.count.shift` | Farq bo'lsa izohsiz bloklanadi | `counted_cash`/`variance_note` lokal saqlanadi; POS-07 "SMENANI YOPISH" bosilganda **bitta** `shift.closed` voqeasi (`counted_cash`, `counted_card_total`, `variance_note`) yuboriladi — `cash_count.recorded` voqeasi **yo'q** (E-11); keyin Z-hisobot *(2026-10-15: qabul-6/7, E-11)* |

- **Ma'lumot manbai**: **Yo'q** (`GET /shifts/{id}/expected-cash` endpoint yo'q) → lokal hisob + online `GET /api/v1/shifts/{id}` → `running_totals.expected_cash` (kutilgan naqd — boshlang'ich + naqd sotuv − naqd qaytarish + naqd qarz to'lov + qo'yilgan − olingan, K1-02); `counted_cash`/`variance_note` `shift.closed` payload'ida yuboriladi (E-11). *(2026-10-15: qabul-6/7, E-01/E-11)*
- **Holatlar**: `loading` · `empty` — yo'q · `error` (izohsiz farq — saqlanmaydi) · `offline` (to'liq ishlaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Enter` davom ettiradi.
- **Audit/analitika**: `shift.closed`, `cash_discrepancy_flagged` (`cash_count.recorded` olib tashlandi — E-11). *(2026-10-15: qabul-6/7, E-11)*
- **Bog'liq US**: US-M16-02.

---

# B. Back-office PWA ekranlari (BO-01…21)

## BO-01 — Kirish (login), tenant/filial tanlash

- **Maqsad**: back-office foydalanuvchilarini (Egasi/Menejer/Buxgalter) autentifikatsiya qilish.
- **Rol/ruxsat**: Barcha (login ekrani — ruxsat talab qilinmaydi).
- **Route**: `/login`
- **Layout**: *(2026-10-15: asoschi qarori, Q7 — "Google bilan kirish" tugmasi qo'shildi)*

```
┌─────────────────────────────────────────┐
│               AIOS                        │
│         [UZ/RU]                           │
│   Telefon:  [ +998 __ ___ __ __ ]          │
│   Parol:    [ ************ ]               │
│          [  KIRISH  ]                      │
│   ──────────── yoki ────────────           │
│   [  G  Google bilan kirish  ]             │
│   Parolni unutdim?                         │
└─────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `phone` | Telefon | Телефон | `Input` (mask `+998 XX XXX XX XX`) | Ha (telefon yo'li) | `+998` bilan 9 raqam | — | 17 |
| `password` | Parol | Пароль | `Input type=password` | Ha (telefon yo'li) | ≥1 belgi (backend tekshiradi) | — | 128 |
| `branchId` (login'dan keyin, bir nechta filial bo'lsa) | Filial | Филиал | `Select` | Ha (ko'p filial bo'lsa) | — | Birinchi filial | — |

- **Amallar** *(2026-10-15: asoschi qarori, Q7)*:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| KIRISH | — | Yo'q | Front-channel Authorization Code+PKCE (`12-autentifikatsiya-oauth2.md` §2.1) → BFF cookie |
| **Google bilan kirish** | — | Yo'q | Google OIDC'ga redirect (bizning OAuth AS'da tashqi provayder) → qaytgach BFF cookie; birinchi marta kirishda hisob telefon raqami bilan bog'lanishi so'raladi (STIR/fiskal uchun) |
| Parolni unutdim | — | Yo'q | OTP oynasi (`purpose=recovery`) — kod birinchi navbatda **Telegram bot**ga, Telegram ulanmagan bo'lsa **SMS**ga (zaxira) → yangi parol o'rnatish |
| Ma'lumotlarimni yuklab olish (faqat `subscription-restricted`da ko'rinadi) | — | OTP (`purpose=data_export`) — Telegram bot birinchi, SMS zaxira | Bir martalik eksport havolasi (15 daqiqa, D2) |
| To'lash (Click/Payme, faqat `subscription-restricted`da) | — | Yo'q | `pay_url`ga o'tish |

- **Ma'lumot manbai**: `POST /auth/login`, `GET /auth/oauth/google/authorize` → `GET /auth/oauth/google/callback` (Q7), `POST /auth/otp/request`, `POST /auth/otp/verify`, `GET /billing/pay`, `POST /billing/export-my-data`.
- **Holatlar**: `loading` · `empty` — yo'q · `error` ("Telefon yoki parol noto'g'ri", #18 — qaysi qism xato ekani oshkor qilinmaydi) · `offline` (PWA offline ombor/hisobot ko'rishga ruxsat beradi, lekin yangi login internetsiz ishlamaydi) · `no-permission` — yo'q · `subscription-restricted` — banner + to'lov havolasi + eksport havolasi, parol maydoni faol (identifikatsiya uchun), token berilmaydi.
- **Klaviatura**: `Enter` kirishni yuboradi.
- **Audit/analitika**: `login_success`, `login_failed`, `account_locked`, `otp_requested`, `otp_verified`, `data_export_during_restriction`.
- **Bog'liq US**: US-M13-06, US-M17-03.

---

## BO-02 — Dashboard (Egasi/Menejer)

- **Maqsad**: kunlik/haftalik savdo, qoldiq, qarzdorlik, ogohlantirishlarni bir joyda ko'rsatish.
- **Rol/ruxsat**: Egasi, Menejer (`reports.sales.view` + `reports.finance.view`). *(2026-10-15: qabul-6/7, E-02)*
- **Route**: `/app/dashboard`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-02 wireframe'i.
- **Maydonlar**: `periodFilter` — Davr — Период — `Select` (Bugun/Hafta/Oy) — majburiy emas — default "Bugun"; `branchFilter` — Filial — Филиал — `Select` — majburiy emas — default "Barchasi".
- **Amallar**: karta/ogohlantirish bosilganda tegishli ekranga o'tish (masalan "Davlat hisoboti" → BO-10).
- **Ma'lumot manbai**: `GET /api/v1/reports/dashboard?period=today|week|month&branch_id=`. *(2026-10-15: qabul-6/7, E-01, 13-3 #17)*
- **Holatlar**: `loading` (skeleton kartalar) · `empty` (yangi tenant, ma'lumot yo'q) · `error` (hisoblash xatosi, "qayta urinish") · `offline` ("Oxirgi yangilanish: N daqiqa oldin" belgisi) · `no-permission` — Kassir/Omborchi/Buxgalter uchun ko'rinmaydi (sidebar'da yo'q) · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K` tezkor navigatsiya.
- **Audit/analitika**: `dashboard_viewed`.
- **Bog'liq US**: US-M12-01, US-M11-03.

---

## BO-03 — Ombor qoldig'i (+ Ko'chirishlar tab)

- **Maqsad**: qoldiqni ko'rish/boshqarish, ko'chirishlar holatini kuzatish, inventarizatsiya farqini tasdiqlash, hisobdan chiqarish.
- **Rol/ruxsat**: Menejer, Omborchi (`stock.view`); ko'chirish ro'yxati — `stock.view`; ko'chirish yaratish — `transfer.create`; hisobdan chiqarish — `stock.writeoff`; inventarizatsiya farqini tasdiqlash — `stock.count.post`. *(2026-10-15: qabul-6/7, E-02 — `stock.edit` olib tashlandi, umumiy tahrir yo'q; `transfer.view` → `stock.view`)*
- **Route**: `/app/warehouse/stock`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-03 wireframe'i + "Ko'chirishlar" tab (holat: yo'lda/qabul qilindi/farq bilan, 72 soat hisoblagichi) + **"Inventarizatsiyalar" tab** *(2026-10-15: qabul-6/7, E-08)*: ro'yxat `GET /api/v1/stock-counts?status=review`, qator — kutilgan/sanalgan/farq/summa; tugmalar "Farqni tasdiqlash" (`stock.count.post`, `POST /stock-counts/{id}/post`, dialog «Kamomad X so'm, ortiqcha Y so'm hisobga olinadi») va "Bekor qilish" (`POST /stock-counts/{id}/cancel`).
- **Maydonlar**: `search` — Qidirish — Поиск — `Input` — yo'q — max 64; `branchId` — Ombor/filial — Склад/филиал — `Select` (**"Barchasi" varianti bor**, bo'sh = konsolidatsiya) — ha — default joriy filial *(2026-10-15: qabul-6/7, E-19, US-M04-03)*; `lowStockOnly` — Faqat kam qoldiq — Только низкий остаток — `Switch` — yo'q — default o'chiq *(2026-10-15: qabul-6/7, E-19, US-M04-02)*; `expiringWithinDays` — "Muddati 7 kunda tugaydi" filtri — `GET /stock-lots?expiring_within_days=7` — yo'q — default o'chiq *(2026-10-15: qabul-6/7, E-19, US-M04-06)*.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Ko'chirish | `transfer.create` | Yo'q | BO-04 uslubidagi forma/sheet |
| Inventarizatsiya | `stock.count.create` | "Inventarizatsiyani boshlaysizmi?" | Sanash varag'i yaratiladi (POS-10ga tushadi) |
| Hisobdan chiqarish | `stock.writeoff` | — | Partiya, miqdor, sabab (`expired\|damaged\|gift\|other`) → `POST /write-offs` → `/post` *(2026-10-15: qabul-6/7, E-19)* |
| Eksport | `reports.export` | Yo'q | `POST /api/v1/reports/stock/export` → poll `GET /api/v1/reports/export-jobs/{job_id}` *(2026-10-15: qabul-6/7, E-01, 13-3 #22–23)* |

- **Ma'lumot manbai**: `GET /api/v1/stock-balances?warehouse_id=&low_stock=&search=`; "Barchasi" filial — `GET /api/v1/reports/stock?branch_id=` (bo'sh = konsolidatsiya); `GET /api/v1/transfers?status=`; "Inventarizatsiyalar" tab — `GET /api/v1/stock-counts?status=review`; `GET /stock-lots?expiring_within_days=7`. *(2026-10-15: qabul-6/7, E-01/E-08/E-19, 13-2 §7/§14, 13-3 #20)*
- **Holatlar**: `loading` · `empty` (ombor bo'sh — yangi filial) · `error` (ma'lumot sinxron emas, "Oxirgi yangilanish") · `offline` (faqat ko'rish, IndexedDB oxirgi nusxa) · `no-permission` — Kassir/Buxgalterga faqat ko'rish (K), yaratish/tasdiqlash yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K` qidiruv.
- **Audit/analitika**: `stock_viewed`, `transfer_list_viewed`, `stock_count_review_viewed`, `stock_count.posted`, `write_off.posted`.
- **Bog'liq US**: US-M04-01, US-M04-02, US-M04-03, US-M06-03, US-M04-06, US-M05-02, US-M05-03.

---

## BO-04 — Xaridnoma yaratish, yetkazib beruvchiga to'lov/qaytarish

- **Maqsad**: xarid buyurtmasi yaratish, AI-03 OCR orqali qog'oz hujjat kiritish, to'lov va qaytarish qayd etish, kirimlarni o'tkazish, yetkazib beruvchiga bo'lgan qarzni ko'rish.
- **Rol/ruxsat**: Menejer, Omborchi, Buxgalter (`purchases.create`, `purchases.pay`, `purchases.return`, `purchases.post`); AI-03 tugmasi — qo'shimcha `ai.ocr.use`. *(2026-10-15: qabul-6/7, E-02 — `ai.ocr.use` qo'shildi)*
- **Route**: `/app/purchases`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│ [Xaridnomalar] [Kirimlar] [Yetkazib beruvchiga to'lov]│
│ [Qaytarish] [Men qarzdorman]                       │
├──────────────────────────────────────────────────┤
│  Yetkazib beruvchi: [ "Mega Trade" MChJ  ▾ ]       │
│  [ 📷 Qog'oz hujjatdan o'qish (AI-03) ]            │
│  ┌────────────────────────────────────────────┐   │
│  │ Tovar          Miqdor    Narx     Jami      │   │
│  │ Coca-Cola 1.5L   50    12 000   600 000     │   │
│  └────────────────────────────────────────────┘   │
│         [  XARIDNOMANI YUBORISH  ]                │
└──────────────────────────────────────────────────┘
```

*(2026-10-15: qabul-6/7, E-07)* Beshinchi tab **"Men qarzdorman"** — yetkazib beruvchiga bo'lgan qarzimiz ro'yxati: `GET /api/v1/reports/debts-aging?direction=payable` (yetkazib beruvchi, summa, muddat), qatordan "To'lash" → mavjud "To'lov qayd etish" formasi; ruxsat `purchases.pay` (ko'rish — `reports.finance.view`).

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `supplierId` | Yetkazib beruvchi | Поставщик | `Combobox` | Ha | Mavjud/yangi | — | — |
| `lines[].qty` | Miqdor | Количество | `QtyInput` | Ha | >0 | — | — |
| `lines[].price` | Narx | Цена | `MoneyInput` | Ha | >0 | — | — |
| `ocrPhoto` | Hujjat fotosi | Фото документа | Fayl yuklash (`POST /attachments`) | Yo'q | JPEG/PNG, ≤10MB (13-0 §12) | — | — |
| `payment.source` | To'lov manbai | Источник платежа | `Select` | Ha (to'lov tabida) | `cash\|bank` | — | — |
| `payment.cashRegisterId` | Kassa | Касса | `Select` | Ha (`source=cash`da) | — | — | — |
| `payment.allocations[]` | Taqsimot (kirim hujjati + summa) | Распределение | Jadval | Ha | Standart — eng eskisidan avtomatik | Avtomatik | — |
| `payment.docDate` | Hujjat sanasi | Дата документа | `Calendar` | Ha | — | Bugun | — |
| `payment.amount` | To'lov summasi | Сумма платежа | `MoneyInput` | Ha (to'lov tabida) | ≤qarz — oshsa ogohlantirish, avans sifatida qabul qilinadi (13-2 §11) | — | — |
| `return.reason` | Qaytarish sababi | Причина возврата | `Select` | Ha (qaytarish tabida) | — | — | — |

*(2026-10-15: qabul-6/7, E-18)* AI-03 sariq belgi chegarasi: summa <95%, sana <90%, miqdor/nom <80%; **har bir hujjat** foydalanuvchi "Tasdiqlash" bosmaguncha saqlanmaydi; AI-03 feature-flag o'chiq bo'lsa tugma ko'rinmaydi (ochiq savollar reestri #19).

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Qog'oz hujjatdan o'qish (AI-03) | `purchases.create` + `ai.ocr.use` | Past-ishonchli maydonlar sariq, foydalanuvchi "Tasdiqlash" bosmaguncha saqlanmaydi | `POST /api/v1/attachments` → `POST /api/v1/ai/ocr/jobs` (`doc_type_hint=purchase`) → poll `GET /api/v1/ai/ocr/jobs/{job_id}` → `POST /api/v1/ai/ocr/jobs/{job_id}/confirm` |
| XARIDNOMANI YUBORISH | `purchases.create` | Yo'q | `POST /api/v1/purchase-orders` → `POST /api/v1/purchase-orders/{id}/send` |
| O'tkazish (Kirimlar tabida) | `purchases.post` | Yo'q | `GET /goods-receipts?status=draft` dan tanlangan hujjatni `POST /goods-receipts/{id}/post` bilan o'tkazadi — qoldiq shu paytda oshadi *(2026-10-15: qabul-6/7, E-18, E-13)* |
| E-fakturadan kirim | `purchases.receive` | Yo'q | BO-15'dan `POST /goods-receipts/from-einvoice/{id}` (E-23) |
| To'lov qayd etish | `purchases.pay` | Yo'q | `POST /api/v1/supplier-payments`, kreditorlik kamayadi |
| Yetkazib beruvchiga qaytarish | `purchases.return` | "Qaytarishni tasdiqlaysizmi?" | `POST /api/v1/supplier-returns` → `POST /api/v1/supplier-returns/{id}/post`, ombor/kreditorlik tuzatiladi |

- **Ma'lumot manbai**: `GET/POST /api/v1/purchase-orders` + `POST /api/v1/purchase-orders/{id}/send`; `GET /api/v1/suppliers`, `GET /api/v1/suppliers/{id}/debt-balance`; `GET /api/v1/goods-receipts`, `POST /api/v1/goods-receipts/{id}/post`; `POST /api/v1/attachments` → `POST /api/v1/ai/ocr/jobs` (`doc_type_hint=purchase`) → poll → `/confirm` (AI-03); `POST /api/v1/supplier-payments`; `POST /api/v1/supplier-returns` + `POST /api/v1/supplier-returns/{id}/post`; `GET /api/v1/reports/debts-aging?direction=payable`. *(2026-10-15: qabul-6/7, E-01/E-07/E-18, 13-2 §4/§8–12, 13-3 #73–75)*
- **Holatlar**: `loading` · `empty` (yangi xaridnoma) · `error` (AI OCR noto'g'ri o'qidi — qo'lda tuzatish shart) · `offline` (PWA'da yangi xaridnoma yaratish cheklangan, internet talab qilinadi) · `no-permission` — Kassir/Omborchiga to'lov/qaytarish yopiq (faqat Omborchi — qabul, bu ekranda emas POS-08da) · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `purchase_order.created`, `ai_ocr_used`, `goods_receipt.posted`, `supplier_payment.created`, `supplier_return.created`.
- **Bog'liq US**: US-M07-01, US-M07-02, US-M07-03, US-M07-04, US-M07-05, US-M08-11.

---

## BO-05 — Narxlar va chegirma qoidalarini boshqarish

- **Maqsad**: tovar narxini yangilash (tarix bilan), avtomatik chegirma qoidalarini sozlash.
- **Rol/ruxsat**: Menejer (`prices.edit`, `discount.rule.manage`); >limit narx o'zgarishi — `prices.approve` (Egasi). *(2026-10-15: qabul-6/7, E-02 — `discount.rules.manage` → `discount.rule.manage`)*
- **Route**: `/app/catalog/prices`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│ [Narxlar] [Chegirma qoidalari]                     │
├──────────────────────────────────────────────────┤
│  Tovar              Joriy narx   Yangi narx         │
│  Coca-Cola 1.5L      18 000      [ 19 000 ]        │
│                                [ SAQLASH ]          │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `newPrice` | Yangi narx | Новая цена | `MoneyInput` | Ha | >0 | Joriy narx | — |
| `effectiveFrom` | Amal qilish sanasi | Дата применения | `Calendar` | Ha | ≥ bugun | Bugun | — |
| `nameRu` *(2026-10-15: asoschi qarori, Q2)* | Rus tilidagi nomi | Название на русском | `Input` | Yo'q (ixtiyoriy) | Max 200 | Bo'sh | 200 — chekda "{name} / {nameRu}" ko'rinishida chiqadi (bo'sh bo'lsa faqat `name`), `products.name_ru` |
| `rule.category` | Kategoriya | Категория | `Select` | Ha (qoida) | — | — | — |
| `rule.percent` | Chegirma % | Скидка % | `Input` number | Ha (qoida) | 0–100 | — | 100 |
| `rule.startDate`/`endDate` | Boshlanish/tugash | Начало/Конец | `Calendar` | Ha (qoida) | `endDate` ≥ `startDate` | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| SAQLASH (narx) | `prices.edit` | Limitdan katta o'zgarishda `pending_approval` → BO-16 | `POST /api/v1/price-changes` → `POST /api/v1/price-changes/{id}/post` (javob `posted` yoki `pending_approval`) — eski narx tarixga, yangi narx saqlanadi |
| SAQLASH (`nameRu`) *(2026-10-15: asoschi qarori, Q2)* | `prices.edit` | Yo'q | `PATCH /api/v1/products/{id}` (`name_ru`) — tasdiqlash shart emas, darhol kuchga kiradi |
| Qoida yaratish | `discount.rule.manage` | Yo'q | `discount_rule.created` |

- **Ma'lumot manbai**: `GET /api/v1/products/{id}/prices` (tarix) + `POST /api/v1/price-changes` → `POST /api/v1/price-changes/{id}/post`; `GET/POST /api/v1/discount-rules` (+ `PATCH /{id}`, `POST /{id}/archive`). *(2026-10-15: qabul-6/7, E-01, 13-2 §4, 13-1 §8.2)*
- **Holatlar**: `loading` · `empty` (narx belgilanmagan) · `error` (manfiy narx/chegirma) · `offline` (faqat ko'rish) · `no-permission` — Kassir/Omborchiga faqat ko'rish · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `price_changed`, `price_change_pending_approval`, `discount_rule.created`.
- **Bog'liq US**: US-M09-01, US-M09-02, US-M03-02.

---

## BO-06 — Nasiya/qarzdorlar ro'yxati va eslatmalar

- **Maqsad**: qarzdorlarni ko'rish, mijoz kartasi/kredit limitini boshqarish, AI-06 eslatma matnini tasdiqlash, to'lov qabul qilish, shubhali qarzni belgilash/kechish.
- **Rol/ruxsat**: Menejer, Buxgalter — ko'rish `reports.finance.view` (eskirish hisoboti) + `reports.sales.view` (qarz daftari); to'lov qabul qilish `debts.payment.accept`; eslatma yuborish `debts.remind`; mijoz kartasi/limit `debts.limit.manage`; shubhali belgilash/kechish — `debts.forgive` (faqat Egasi). *(2026-10-15: qabul-6/7, E-02/E-06)*
- **Route**: `/app/debts`
- **Layout**: `04-ekranlar-va-ux.md` tasvirlangan mazmunga mos jadval + AI eslatma paneli + **"Mijoz kartasi" Sheet** *(2026-10-15: qabul-6/7, E-06)*.

```
┌──────────────────────────────────────────────────┐
│  [Bugun/o'tgan va'da] [60+ kun] [Barchasi]         │
│  Mijoz          Qarz       Muddat   AI eslatma     │
│  Aliyev Botir   450 000    15 kun   [Ko'rish/Yubor]│
│  [ TO'LOV QABUL QILISH ] [ Mijoz kartasi ]         │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `periodFilter` — `Select`; **"Bugun/o'tgan va'da" tab** — `due_date ≤ bugun` (US-M08-09); **"60+ kun" tab** — eslatma ro'yxati, tizim avtomatik belgilamaydi (US-M08-10, tavsiya #9); `limit_exceeded_offline=true` filtri (Egasi); `payment.amount` — To'lov summasi — Сумма платежа — `MoneyInput` — ha — >0. *(2026-10-15: qabul-6/7, E-05)*

  **"Mijoz kartasi" Sheet** *(2026-10-15: qabul-6/7, E-06)*: `name`, `phone`, `kind` (`person|company`), `stir`, `legal_address`, `bank_account`, `bank_mfo` (B2B e-faktura uchun), `creditLimit` (`MoneyInput`, bo'sh = limitsiz), `standingDiscountPct` (0–100), `notifyConsent` (`Switch`); saqlash — `PATCH /api/v1/counterparties/{id}` (`version` bilan), ruxsat `debts.limit.manage`.

- **Amallar** *(2026-10-15: qabul-6/7, E-05 — to'liq qayta yozildi)*:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| AI eslatmani ko'rish/yuborish | `debts.remind` | Yo'q (matn ko'rib chiqiladi, keyin yuboriladi) | *(2026-10-15: asoschi qarori, Q7)* Telegram orqali birinchi navbatda, SMS — zaxira |
| TO'LOV QABUL QILISH | `debts.payment.accept` | Yo'q | `POST /debt-payments` → `POST /debt-payments/{id}/post` — *(2026-10-15: asoschi qarori, Q3)* to'langan summaga fiskal chek chiqariladi (`fiscal_receipts.kind=debt_settlement`); tovar qatorlari yopilgan sotuv(lar)dan proporsional bo'linadi; qonuniylik (QQS/daromad tan olish vaqti) hali buxgalter/yurist tasdig'ini kutadi (`FiscalPolicy` sozlamasi) |
| Shubhali deb belgilash | `debts.forgive` (faqat Egasi) | Sabab majburiy | `POST /debt-doubtful-flags` — provodka **yo'q**, faqat belgi |
| Belgini olib tashlash | `debts.forgive` | Yo'q | `POST /debt-doubtful-flags/{id}/unflag` |
| Qarzni kechish (hisobdan chiqarish) | `debts.forgive` (faqat Egasi) | Sabab majburiy + "Bu amal provodka yaratadi" | `POST /debt-writeoffs` → `/post` |

- **Ma'lumot manbai**: `GET /api/v1/reports/debts-aging?direction=receivable&bucket=` (+ `limit_exceeded_offline=`, `branch_id=`, K1-05); `POST /api/v1/ai/debt-reminders/draft` → `POST /api/v1/ai/debt-reminders/send` (AI-06); `POST /api/v1/debt-payments` → `/post`; `POST /api/v1/debt-doubtful-flags`, `POST /api/v1/debt-doubtful-flags/{id}/unflag`; `GET /api/v1/counterparties/{id}/debt-ledger`; `PATCH /api/v1/counterparties/{id}`. *(2026-10-15: qabul-6/7, E-01, 13-3 #21/#77-78, 13-1 §11-12)*
- **Holatlar**: `loading` · `empty` (qarzdor yo'q) · `error` (aloqa ma'lumoti yo'q) · `offline` (faqat ko'rish) · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `debt_reminder_sent`, `debt_payment.created`, `debt_doubtful_flagged`, `debt_doubtful_unflagged`, `debt_writeoff.posted`.
- **Bog'liq US**: US-M08-03, US-M08-06, US-M08-09, US-M08-10, US-M08-04, US-M08-11. *(2026-10-15: qabul-6/7, E-05)*

---

## BO-07 — QQS ichki hisob-kitobi

- **Maqsad**: QQS bazasi/summasini ko'rish, qizil faktura kreditini kuzatish.
- **Rol/ruxsat**: Buxgalter (`tax.vat.view`). *(2026-10-15: qabul-6/7, E-02)*
- **Route**: `/app/tax/vat`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Davr: [ 2026-sentyabr ▾ ]                         │
│  QQS (12%) bazasi: 18 420 000   Summa: 2 210 400   │
│  Kutilayotgan QQS krediti (qizil fakturalar):       │
│                            96 000 so'm (≤10% limit) │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `period` — Davr — Период — `Select` (`YYYY-MM`; "chorak" — 3 oyni klient tomonda yig'adi, API faqat oylik qaytaradi, E-30) — ha.
- **Amallar**: yo'q (asosan ko'rish; BO-10ga "Solishtirishni ochish" havolasi).
- **Ma'lumot manbai**: `GET /api/v1/vat/summary?period=YYYY-MM` (+ `GET /api/v1/vat/moves`). *(2026-10-15: qabul-6/7, E-01, 13-3 #1-2)*
- **Holatlar**: `loading` · `empty` (davr yopilmagan) · `error` (hisoblashda nomuvofiqlik) · `offline` (faqat ko'rish) · `no-permission` — faqat Buxgalterda Y/T, Egasi/Menejerda K · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `vat_summary_viewed`.
- **Bog'liq US**: US-M10-01, US-M10-03.

---

## BO-08 — Buxgalteriya jurnali, provodkalar

- **Maqsad**: hisob rejasi bo'yicha avtomatik provodkalarni ko'rish, filtrlash, eksport qilish, davrni (oyni) yopish, tuzatuvchi yozuv kiritish.
- **Rol/ruxsat**: Buxgalter (`accounting.post`, `reports.export`); davrni yopish — `accounting.period.close`. *(2026-10-15: qabul-6/7, E-02 — `accounting.view` → `accounting.post`, `accounting.export` → `reports.export`)*
- **Route**: `/app/accounting/journal`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Sana: [ ... ]  Hisob: [ ... ]   [ Eksport ]       │
├──────────────────────────────────────────────────┤
│  12.10.2026  Sotuv #K-000154   Kassa +69 000       │
│                                 Daromad −69 000     │
├──────────────────────────────────────────────────┤
│  [ Davrni yopish ]   [ Tuzatuvchi yozuv ]          │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `dateFrom`/`dateTo` — `Calendar`; `accountFilter` — `Select` — majburiy emas; `adjustment.entryDate` — Tuzatuvchi yozuv sanasi — faqat joriy **ochiq** davr — ha (tuzatuvchi yozuvda); `adjustment.comment` — Izoh — majburiy (tuzatuvchi yozuvda). *(2026-10-15: qabul-6/7, E-09)*
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Eksport | `reports.export` | Yo'q | CSV/Excel yuklash |
| Davrni yopish | `accounting.period.close` | Avval `GET /period-closings/{period}/readiness` (bloker: `recost_pending`, `fiscal_pending`); so'ng «{oy} yopiladi. Yopilgan oy **qayta ochilmaydi** — keyingi tuzatishlar joriy ochiq oyda tuzatuvchi yozuv bilan kiritiladi» | `POST /period-closings` |
| Tuzatuvchi yozuv | `accounting.post` | Yo'q | `POST /ledger-entries/adjustments` (`entry_date` faqat ochiq davr, `comment` majburiy) |

- **Ma'lumot manbai**: `GET /api/v1/ledger-entries?doc_date__gte=&doc_date__lte=&account_dt=&account_kt=`; `GET /period-closings/{period}/readiness`, `POST /period-closings`, `POST /ledger-entries/adjustments`. *(2026-10-15: qabul-6/7, E-01/E-09, 13-3 #9)*
- **Holatlar**: `loading` · `empty` (yozuv yo'q) · `error` (balans mos kelmadi, `PERIOD_CLOSED` — tuzatish yopilgan davrga kiritilmoqchi bo'lsa) · `offline` (faqat ko'rish) · `no-permission` — faqat Buxgalterda to'liq, boshqa rollarda yopiq · `subscription-restricted` — kirilmaydi. *(2026-10-15: qabul-6/7, E-09, D-06 #41)*
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `ledger_viewed`, `ledger_exported`, `period_closing.posted`, `ledger_adjustment.posted`.
- **Bog'liq US**: US-M11-01, US-M11-02.

---

## BO-09 — Hisobotlar markazi

- **Maqsad**: savdo/ombor/buxgalteriya/QQS hisobotlarini tanlab, davr bo'yicha ko'rish va eksport qilish.
- **Rol/ruxsat**: Egasi, Menejer, Buxgalter (`reports.sales.view` savdo/ombor hisobotlari uchun, `reports.finance.view` moliya/QQS/P&L uchun; `reports.export`). *(2026-10-15: qabul-6/7, E-02)*
- **Route**: `/app/reports`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Hisobot turi: [ Kunlik savdo ▾ ]  Davr: [ ... ]   │
│                                [ PDF ] [ Excel ]    │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `reportType` — Hisobot turi — Тип отчёта — `Select` — ha (ro'yxatga **"Kassa/smena tarixi"** va **"QQS registri (qaytarishlar bilan)"** qo'shildi, quyida); `period` — `Calendar range` — ha.
- **Amallar**: PDF/Excel eksport (`reports.export`).
- **Ma'lumot manbai**: hisobotga qarab — `sales`/`top-products` — `?date_from=&date_to=`; `trial-balance`/`profit-and-loss` — `?period=`; `balance-sheet`/`debts-aging` — `?as_of=`; **"Kassa/smena tarixi"** — `GET /api/v1/cash-registers/{id}/cash-history`; **"QQS registri (qaytarishlar bilan)"** — `GET /api/v1/vat/moves?doc_type=returns`; eksport — `POST /api/v1/reports/{report-kod}/export` + poll `GET /api/v1/reports/export-jobs/{job_id}`. *(2026-10-15: qabul-6/7, E-01/E-28, 13-3 #11-23)*
- **Holatlar**: `loading` · `empty` (ma'lumot yo'q) · `error` (eksport muvaffaqiyatsiz) · `offline` (faqat oxirgi keshlangan hisobot) · `no-permission` — Kassir (faqat o'z smenasi), Omborchi (faqat ombor) cheklangan ko'rinishda · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `report_viewed`, `report_exported`.
- **Bog'liq US**: US-M12-01, US-M12-02, US-M12-03, US-M16-03, US-M02-03. *(2026-10-15: qabul-6/7, E-28)*

---

## BO-10 — Davlat hisobotini ichki hisob bilan solishtirish

- **Maqsad**: davlat hisobotini (fayl yuklash orqali) tizimga kiritish, QQS/aylanma solig'i hisobotini ichki hisob bilan 5 kalendar kun ichida solishtirish, AI-05 bilan farqni tushuntirish.
- **Rol/ruxsat**: Buxgalter (`tax.compare.review` — ko'rish/farq/yuklash, `tax.correction.submit` — tuzatish yuborish), Egasi (`tax.vat.view`, yakuniy tasdiq). *(2026-10-15: qabul-6/7, E-02 — `tax.view`→`tax.vat.view`, `tax.reconcile` ikkiga bo'lindi)*
- **Route**: `/app/tax/reconciliation`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-10 wireframe'i.
- **Maydonlar**: `taxTypeTab` — `Tabs` (**QQS/Aylanma** — `tax_type` API'da faqat `vat|turnover`, `Mulk*/Yer*/JShDS*/Ijtimoiy*` tablari **olib tashlandi**, 06 §1.3 Won't) *(2026-10-15: qabul-6/7, E-10)*; `uploadForm.taxType` — `vat|turnover`; `uploadForm.period` — `YYYY-MM`; `uploadForm.publishedAt` — sana (5 kunlik hisoblagich shundan boshlanadi); `uploadForm.file` — PDF/XLSX ≤5MB; `correctionNote` — Tuzatish izohi — Комментарий к исправлению — `Textarea` — tuzatish yuborilganda ha — max 1000.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Davlat hisobotini yuklash | `tax.compare.review` | Yo'q | `POST /state-reports` → avtomatik `POST /state-reports/{id}/compare` *(2026-10-15: qabul-6/7, E-10)* |
| Farqni ko'rib chiqish | `tax.compare.review` | Yo'q | Hujjat darajasidagi farq ro'yxati ochiladi |
| Farqni tushuntirish (AI-05) | `tax.compare.review` | Yo'q | `POST /ai/vat-diffs/{diff_id}/explain`; matn ostida «AI tushuntirish — raqamlar tizim hisobidan» belgisi *(2026-10-15: qabul-6/7, E-10)* |
| Tuzatish (E-IMZO bilan) | `tax.correction.submit` | E-IMZO sertifikat/parol tasdig'i | Holat `tuzatish yuborildi` (kanal — ochiq savol) |

- **Ma'lumot manbai**: `GET /api/v1/state-reports?tax_type=&period=` + `GET /api/v1/state-reports/{id}` + `GET /api/v1/state-reports/{id}/diffs`; `POST /api/v1/state-reports` (fayl yuklash), `POST /api/v1/state-reports/{id}/compare`, `POST /api/v1/state-reports/{id}/correction`, `POST /api/v1/ai/vat-diffs/{diff_id}/explain`. *(2026-10-15: qabul-6/7, E-01/E-10, 13-3 #3-8/#76)*
- **Holatlar**: `loading` · `empty` (davlat hisoboti hali e'lon qilinmagan, "Kutilmoqda") · `error` ("⚠ Farq topildi") · `offline` (faqat ichki ustun ko'rinadi, davlat ustuni "internet kerak") · `no-permission` — Egasida faqat K (ko'rish+yakuniy tasdiq), boshqa rollarga yopiq · `subscription-restricted` — kirilmaydi. Qo'shimcha holat: **"Muddat o'tdi — avtomatik qabul qilindi"** (5 kalendar kun ichida javob berilmagan); **3-kalendar kundan keyin** Egasiga ham eskalatsiya banneri ko'rsatiladi (ochiq savollar reestri #3). *(2026-10-15: qabul-6/7, E-10)*
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `state_report.uploaded`, `tax_reconciliation_viewed`, `tax_correction_submitted`, `tax_auto_accepted`, `ai_vat_diff_explained`, `tax_reconciliation_escalated_to_owner`.
- **Bog'liq US**: US-M10-02, US-M10-04, AI-05.

---

## BO-11 — Foydalanuvchilar, huquqlar va sessiyalar

- **Maqsad**: xodim qo'shish/bloklash, rol/limit sozlash, parol/PIN tiklash, sessiya/qurilma boshqaruvi.
- **Rol/ruxsat**: Egasi (`settings.users`).
- **Route**: `/app/settings/users`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│ [Xodimlar] [Rollar] [Qurilmalar] [Sessiyalar]      │
├──────────────────────────────────────────────────┤
│  Dilnoza   Kassir    Chilonzor-3   [●Faol]         │
│  [Bloklash][Parolni tiklash][PINni tiklash][Seanslar]│
│                                [ + Xodim qo'shish ] │
└──────────────────────────────────────────────────┘
```

*(2026-10-15: qabul-6/7, E-20)* **"Rollar" tab**: `GET /roles`, rol ichida `PUT /roles/{id}/permissions` — limitlar endi **shaxsga emas, rolga** bog'langan (`discount.give` limit 5%, `returns.approve` 100 000, `cash.withdraw` 50 000 — default qiymatlar shu).

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `phone` | Telefon | Телефон | `Input` (mask) | Ha | `+998` formati | — | 17 |
| `fullName` | To'liq ism | Полное имя | `Input` | Ha | 2–100 belgi | — | 100 |
| `roleIds` | Rol(lar) | Роль(и) | `Select` (multi) | Ha (≥1) | Kassir/Omborchi/Menejer/Buxgalter | — | — |
| `branchIds` | Filial(lar) | Филиал(ы) | `Select` (multi) | Ha (≥1) | — | Joriy filial | — |

*(2026-10-15: qabul-6/7, E-20)* `limits.discountPercent`/`limits.returnAmount`/`limits.cashOutAmount` xodim formasidan **"Rollar" tabiga ko'chirildi** — xodim formasida faqat `roleIds`, `branchIds` qoladi.

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| + Xodim qo'shish | `settings.users` | Yo'q | *(2026-10-15: asoschi qarori, Q7)* Taklif kodi (`purpose=invite`) — Telegram bot birinchi, SMS zaxira |
| Bloklash/Blokdan chiqarish | `settings.users` | "Xodimni bloklaysizmi?" | Sessiyalar darhol revoke |
| Parolni tiklash | `settings.users` | Yo'q | *(2026-10-15: asoschi qarori, Q7)* Tiklash kodi (`purpose=admin_reset`) — Telegram bot birinchi, SMS zaxira |
| PINni qayta o'rnatish | `settings.users` | Yo'q | Eski PIN bekor, keyingi kirishda yangi PIN majburiy |
| Seanslarni tugatish | `settings.users` | Yo'q | Tanlangan sessiya/barcha sessiya bekor |
| Qurilmani bekor qilish | `settings.users` | "Qurilmani bekor qilasizmi?" | `devices.revoked_at`, token/litsenziya bekor |

- **Ma'lumot manbai**: `POST/PATCH /api/v1/admin/users`, `GET /api/v1/admin/users/{id}/sessions`, `GET /api/v1/admin/users/{id}/devices`, `POST /api/v1/admin/users/{id}/reset-password`, `POST /api/v1/admin/users/{id}/reset-pin`, `POST /api/v1/admin/users/{id}/revoke-sessions`; `GET /api/v1/roles`, `GET/PUT /api/v1/roles/{id}/permissions`, `GET /api/v1/permissions-catalog`. *(2026-10-15: qabul-6/7, E-01, 12-auth §18.2, 13-3 #24-29)*
- **Holatlar**: `loading` · `empty` (faqat Egasi mavjud) · `error` (bir xil telefon takror) · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida, boshqalarga butunlay yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `user_created`, `user_blocked`, `password_reset`, `pin_reset_forced`, `session_revoked`, `device_revoked`.
- **Bog'liq US**: US-M13-01…08.

---

## BO-12 — Filiallar boshqaruvi

- **Maqsad**: filiallarni ro'yxatlash, aholi punkti toifasini (aylanma solig'i stavkasi uchun) belgilash, yangi filial qo'shish.
- **Rol/ruxsat**: Egasi (`settings.branches`).
- **Route**: `/app/settings/branches`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Chilonzor-3   Shahar, 100 ming+ (4%)   [Tahrir]   │
│  Yunusobod-1   Boshqa aholi punkti (2%) [Tahrir]   │
│                                [ + Filial qo'shish ]│
└──────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `name` | Filial nomi | Название филиала | `Input` | Ha | 2–100 | — | 100 |
| `address` | Manzil | Адрес | `Input` | Yo'q | — | — | 200 |
| `settlementCategory` | Aholi punkti toifasi | Категория населённого пункта | `Select` | Ha | `city_100k_plus\|other\|remote_mountain` | `city_100k_plus` (eng ehtiyotkor) | — |

*(2026-10-15: qabul-6/7, E-21)* `cashRegisterCount` maydoni **olib tashlandi** — o'rniga filial ichida "Kassalar" ro'yxati: har bir kassa qatorida "Arxivlash" amali.

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| + Filial qo'shish | `settings.branches` | Yo'q | `branches.created` |
| Tahrir/Saqlash | `settings.branches` | Toifa o'zgartirilsa "Yangi stavka faqat shu sanadan qo'llanadi" | `branch_tax_settings` yangi yozuv (`valid_from`) |
| + Kassa qo'shish | `cash_register.manage` | `ADDON_REQUIRED` bo'lsa dialog «Qo'shimcha kassa — +39 000 so'm/oy. Obunaga qo'shasizmi?» → BO-19 | `POST /cash-registers` *(2026-10-15: qabul-6/7, E-21)* |
| Arxivlash (kassa) | `cash_register.manage` | Yo'q | `PATCH /cash-registers/{id}` (`archived:true`) |

- **Ma'lumot manbai**: `GET/POST/PATCH /api/v1/branches` + `GET/POST /api/v1/cash-registers`, `PATCH /api/v1/cash-registers/{id}`, `GET /api/v1/branches/{id}/tax-settings`. *(2026-10-15: qabul-6/7, E-01/E-21, 13-3 #30-40)*
- **Holatlar**: `loading` · `empty` (bitta filial) · `error` — yo'q · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida, boshqa rollar K · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `branch.created`, `branch_tax_category_changed`.
- **Bog'liq US**: US-M14-01, US-M14-03, US-M14-04.

---

## BO-13 — AI yordamchi — savol-javob chat

- **Maqsad**: biznes savollariga (AI-01) tabiiy tilda javob, raqamni kod hisoblaydi.
- **Rol/ruxsat**: Egasi, Menejer, Buxgalter (`ai.chat.use`).
- **Route**: `/app/ai`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-13 wireframe'i.
- **Maydonlar**: `message` — Xabar — Сообщение — `Textarea`/`Input` — ha (yuborishda) — max 500 (API max 2000, UI 500da qoladi — E-30).
- **Amallar**: tez savol tugmalari (preset), yuborish (`Enter`/`➤`).
- **Ma'lumot manbai**: `POST /api/v1/ai/chat` (backend SQL hisoblaydi, LLM faqat tushuntiradi).
- **Holatlar**: `loading` (AI yozmoqda) · `empty` (suhbat boshlanmagan — tez savol tugmalari) · `error` ("Bu savolga aniq javob topa olmadim", #33) · `offline` (chat butunlay o'chirilgan, "AI uchun internet kerak") · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi; AI oylik limiti tugaganda alohida xabar ("AI limiti tugadi, keyingi oygacha kutilmoqda yoki tarifni oshiring").
- **Klaviatura**: `Enter` yuboradi, `Shift+Enter` yangi qator.
- **Audit/analitika**: `ai_chat_message_sent`, `ai_chat_no_answer`, `ai_quota_exceeded`.
- **Bog'liq US**: AI-01, US-M18-04 (bot orqali bir xil backend).

---

## BO-14 — Tenant/do'kon sozlamalari

- **Maqsad**: do'kon nomi, til, valyuta, soliq rejimi, integratsiyalar holatini boshqarish.
- **Rol/ruxsat**: Egasi (`settings.tenant` — 05+, yangi kod, faqat Egasi; zaxira usuli — `valuation.settings.manage`). *(2026-10-15: qabul-6/7, E-02)*
- **Route**: `/app/settings/tenant`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Do'kon nomi:   [ "Mega Market" ]                  │
│  Soliq rejimi:  [ QQS to'lovchi ▾ ]                │
│  Zaxira usuli:  [ O'rtacha narx (AVECO) ▾ ]        │
│  Tarozi shtrix-kod prefiksi: [ 20 ]                │
│  OFD:       🟢 ulangan   OFD yuborilmagan: 0 ta    │
│  E-faktura: 🟢 Faktura.uz  Asl belgisi: 🟡 kalit yo'q│
└──────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `storeName` | Do'kon nomi | Название магазина | `Input` | Ha | 2–100 | — | 100 |
| `taxRegime` | Soliq rejimi | Налоговый режим | `Select` | Ha | `vat\|turnover` | — | — |
| `costingMethod` | Zaxira baholash usuli | Метод оценки запасов | `Select` | Ha | `AVECO\|FIFO` | `AVECO` | — |
| `crptApiKey` | Asl belgisi API kaliti | API-ключ Asl belgisi | `Input` (masked) | Yo'q | — | — | 256 |
| `fakturaUzCredentials` | Faktura.uz login/parol | Логин/пароль Faktura.uz | `Input`×2 (masked) | Yo'q | — | — | — — parol serverda shifrlangan saqlanadi, qayta ko'rsatilmaydi *(2026-10-15: qabul-6/7, E-22)* |
| `scaleBarcodePrefix` | Tarozi shtrix-kod prefiksi | Префикс штрихкода весов | `Input` | Yo'q | 2 raqam | — | 2 |
| `scaleBarcodeVersion` | Tarozi kod formati | Формат кода весов | `Select` | Yo'q | — | — | — |

- **Amallar**: Saqlash (`settings.tenant`) → `PATCH /valuation-settings` (`valuation.settings.manage`), javobdagi `pending_change.effective_from`ni ko'rsatish; zaxira usulini o'zgartirish — "Bu o'zgarish faqat keyingi hisobot yili boshidan kuchga kiradi" tasdiqlash dialogi; tarozi maydonlari — `PATCH /stock-settings` (US-M09-06); "OFD: N ta chek yuborilmagan" qatori → ro'yxat + "Qayta urinish" (`POST /fiscal-receipts/{id}/retry`). *(2026-10-15: qabul-6/7, E-22)*
- **Ma'lumot manbai**: **Katalogda yo'q — K3-01 bilan qo'shiladi**; zaxira usuli — `GET/PATCH /api/v1/valuation-settings`; OFD — `GET /api/v1/fiscal-receipts?status=failed` + `POST /api/v1/fiscal-receipts/{id}/retry`. *(2026-10-15: qabul-6/7, E-01, 13-2 §17, 13-1 §14)*
- **Holatlar**: `loading` · `empty` (sozlanmagan) · `error` (integratsiya ulanmagan) · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `tenant_settings_updated`, `costing_method_change_scheduled`, `integration_connected`, `fiscal_receipt.retry_requested`.
- **Bog'liq US**: US-M04-05, US-M09-06.

---

## BO-15 — Kiruvchi va chiquvchi e-faktura markazi

- **Maqsad**: kiruvchi e-fakturalarni qabul/E-IMZO imzolash, chiquvchi (B2B nasiya + chekdan keyingi) e-fakturalarni boshqarish.
- **Rol/ruxsat**: Buxgalter (`purchases.post` — kiruvchi ro'yxat/qabul/rad, `einvoice.sign` — imzolash/chiquvchi, `purchases.receive` — e-fakturadan kirim). *(2026-10-15: qabul-6/7, E-02 — `einvoice.view` → `purchases.post`)*
- **Route**: `/app/einvoices`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-15 wireframe'i.
- **Maydonlar**: `receiptSearch` — Chekni qidirish (chekdan e-faktura chiqarishda) — Поиск чека — `Input` — ha — chek raqami/sana.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Qabul qilish | `purchases.post` | Yo'q | `POST /api/v1/einvoices/{id}/accept` |
| Rad etish | `purchases.post` | Sabab majburiy | `POST /api/v1/einvoices/{id}/reject` (`{reason}`) |
| E-IMZO imzo | `einvoice.sign` | Sertifikat/parol | `POST /api/v1/einvoices/{id}/sign-challenge` → E-IMZO → `POST /api/v1/einvoices/{id}/submit-signed`, EDO operatoriga yuborish |
| Chek asosida e-faktura chiqarish | `einvoice.sign` | Yo'q | `POST /api/v1/einvoices/from-receipt` — `{sale_id, counterparty_id}`; `einvoices.related_doc` bilan chekka bog'langan yangi hujjat, QQS qayta hisoblanmaydi; xatolar `EINVOICE_ALREADY_LINKED`, `EINVOICE_AMOUNT_EXCEEDS_RECEIPT`, `EINVOICE_COUNTERPARTY_INCOMPLETE` (→ BO-06 "Mijoz kartasi"ga havola, E-06) *(2026-10-15: qabul-6/7, E-23)* |
| Kirim yaratish | `purchases.receive` | Yo'q | `POST /goods-receipts/from-einvoice/{id}` (US-M07-03) *(2026-10-15: qabul-6/7, E-23)* |

- **Ma'lumot manbai**: `GET /api/v1/einvoices?direction=in|out` (`in` — ✓; `out` — **yo'q, K1-04 bilan qo'shiladi**), `POST /api/v1/einvoices` (B2B nasiya sotuvdan avtomatik qoralama, K1-04), `POST /api/v1/einvoices/{id}/sign-challenge` → `POST /api/v1/einvoices/{id}/submit-signed`, `POST /api/v1/einvoices/{id}/accept`/`reject`, `POST /api/v1/einvoices/from-receipt` (**yo'q, K1-04**), `POST /goods-receipts/from-einvoice/{id}`. *(2026-10-15: qabul-6/7, E-01, 13-2 §19)*
- **Holatlar**: `loading` · `empty` (faktura yo'q) · `error` (E-IMZO imzolashda xato — sertifikat/parol; `EINVOICE_ALREADY_LINKED`/`EINVOICE_AMOUNT_EXCEEDS_RECEIPT`/`EINVOICE_COUNTERPARTY_INCOMPLETE`) · `offline` (faqat ko'rish, imzolash internet talab qiladi) · `no-permission` — faqat Buxgalterda · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `einvoice_signed`, `einvoice_accepted`, `einvoice_rejected`, `einvoice_from_receipt_created`, `goods_receipt.created_from_einvoice`.
- **Bog'liq US**: US-M07-03, US-M01-06, US-M10-03.

---

## BO-16 — Tasdiqlash navbati (limitdan oshgan so'rovlar)

- **Maqsad**: chegirma/qaytarish/nasiya/narx/katta pul olish/katta xarajat/limitdan katta hisobdan chiqarish so'rovlarini bitta navbatda ko'rish va PIN bilan tasdiqlash.
- **Rol/ruxsat**: Egasi, Menejer — `kind`ga mos: `discount.approve` / `returns.approve` / `debts.approve` / `prices.approve` / `cash.withdraw` (limit) / `expenses.approve`; foydalanuvchi faqat o'z `*.approve` huquqiga mos `kind`ni ko'radi. *(2026-10-15: qabul-6/7, E-02/E-24)*
- **Route**: `/app/approvals`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-16 wireframe'i + `kind` ustuni (chegirma/qaytarish/nasiya/narx/pul olish/**katta xarajat**/**limitdan katta hisobdan chiqarish**). *(2026-10-15: qabul-6/7, E-24)*
- **Maydonlar**: `pin` — PIN — PIN — `Input` (4–6 raqam) — ha (tasdiqlashda) — raqam.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Tasdiqlash | `kind`ga mos `*.approve` | PIN kiritish | `POST /api/v1/approval-requests/{id}/approve` (`{pin}`) |
| Rad etish | `kind`ga mos `*.approve` | Sabab majburiy | `POST /api/v1/approval-requests/{id}/reject` (`{reason}`) |

- **Ma'lumot manbai**: `GET /api/v1/approval-requests?status=pending`, `POST /api/v1/approval-requests/{id}/approve`, `POST /api/v1/approval-requests/{id}/reject`; `kind` enumiga `expense_over_limit`, `write_off_over_limit` qo'shildi. *(2026-10-15: qabul-6/7, E-01/E-24, 13-1 §9)*
- **Holatlar**: `loading` · `empty` (navbat bo'sh) · `error` (PIN noto'g'ri) · `offline` (PWA'da yangi tasdiqlash cheklangan — Menejer Android POSda inline tasdiqlaydi) · `no-permission` — Buxgalter/Omborchi/Kassirga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `approval_approved`, `approval_rejected`.
- **Bog'liq US**: US-M02-02, US-M03-01, US-M08-01, US-M09-02, US-M16-01.

---

## BO-17 — Xarajatlar

- **Maqsad**: operatsion xarajatlarni (ijara, kommunal, transport) yozish, takrorlanuvchi xarajatlarni sozlash.
- **Rol/ruxsat**: Egasi, Menejer, Buxgalter (`expenses.create`). *(2026-10-15: qabul-6/7, E-02 — `expenses.view` → `expenses.create`, 13-3 #41)*
- **Route**: `/app/expenses`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Sana        Toifa        Summa      Manba         │
│  12.10.2026  Ijara        3 000 000  Bank           │
│                                [ + Xarajat qo'shish ]│
└──────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `amount` | Summa | Сумма | `MoneyInput` | Ha | >0 | — | — |
| `categoryId` | Toifa | Категория | `Select` (`GET /expense-categories`dan, UUID) *(2026-10-15: qabul-6/7, E-25 — enum emas)* | Ha | — | — | — |
| `source` | To'lov manbai | Источник оплаты | `Select` | Ha | `bank\|card` (`cash` BO-17'da **o'chirildi** — naqd xarajat POS-14 `expense` orqali yoziladi, E-25) | — | — |
| `note` | Izoh | Комментарий | `Textarea` | Yo'q | — | — | 200 |
| `receiptPhoto` | Hujjat fotosi | Фото документа | Fayl yuklash (`POST /attachments`) | Yo'q | JPEG/PNG ≤10MB | — | — |
| `period` | Takrorlanish davri | Период повторения | `Select` | Yo'q | `none\|month\|quarter\|year` *(2026-10-15: qabul-6/7, E-25 — `recurrence` → `period`)* | `none` | — |
| `dayOfMonth` | Oyning kuni | День месяца | `Input` number | Takrorlanuvchida Ha | 1–28 | — | 28 |

- **Amallar**: + Xarajat qo'shish (`expenses.create`); takrorlanuvchi xarajat eslatmasini tasdiqlash ("Ijara to'lash vaqti" — bir bosishda, `POST /api/v1/recurring-expenses/{id}/confirm`); O'tkazish (`POST /api/v1/expenses/{id}/post`, limitdan oshsa «Egasi tasdig'iga yuborildi»); Bekor qilish (`POST /api/v1/expenses/{id}/cancel`, sabab). *(2026-10-15: qabul-6/7, E-25)*
- **Ma'lumot manbai**: `GET/POST /api/v1/expenses` + `POST /api/v1/expenses/{id}/post`, `POST /api/v1/expenses/{id}/cancel`, `GET /api/v1/expense-categories`, `POST /api/v1/attachments`; `GET/POST /api/v1/recurring-expenses`, `PATCH /{id}`, `POST /api/v1/recurring-expenses/{id}/confirm`. *(2026-10-15: qabul-6/7, E-01, 13-3 #41-51)*
- **Holatlar**: `loading` · `empty` (xarajat yo'q) · `error` — standart validatsiya · `offline` (faqat ko'rish; kassadan to'langan xarajat POSda yoziladi) · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `expense.created`, `expense.posted`, `expense.cancelled`.
- **Bog'liq US**: US-M15-01, US-M15-02, US-M15-03.

---

## BO-18 — Yorliq va shtrix-kod chop etish

- **Maqsad**: narxi o'zgargan tovarlar uchun yorliq chop etish, ichki shtrix-kod yaratish.
- **Rol/ruxsat**: Menejer (`labels.print`, `catalog.manage`). *(2026-10-15: qabul-6/7, E-02 — `labels.generate` → `catalog.manage`)*
- **Route**: `/app/catalog/labels`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Narxi o'zgargan, chop etilmagan tovarlar:          │
│  [x] Coca-Cola 1.5L   19 000 so'm                   │
│  Shablon: [ 58×40mm ▾ ]        [ CHOP ETISH ]       │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `template` — Shablon — Шаблон — `Select` (58×40mm) — ha; `selectedProducts` — `Checkbox` ro'yxat — ha (≥1).
- **Amallar**: Ichki shtrix-kod yaratish (`catalog.manage`) → `POST /api/v1/products/{id}/barcodes/internal-generate`; CHOP ETISH (`labels.print`) → chop etilgandan keyin `POST /api/v1/label-print-queue/mark-printed`. *(2026-10-15: qabul-6/7, E-01/E-02)*
- **Ma'lumot manbai**: `GET /api/v1/label-print-queue`, `GET /api/v1/label-templates`, `POST /api/v1/products/{id}/barcodes/internal-generate`, `POST /api/v1/label-print-queue/mark-printed`, chop etish — `react-to-print` + `bwip-js` (frontendda). *(2026-10-15: qabul-6/7, E-01, 13-2 §1/§5)*
- **Holatlar**: `loading` · `empty` (chop etiladigan yorliq yo'q) · `error` (printer topilmadi) · `offline` (lokal printer bilan ishlaydi) · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `label_printed`, `internal_barcode_generated`.
- **Bog'liq US**: US-M09-04, US-M09-05.

---

## BO-19 — Obuna va to'lov

- **Maqsad**: yagona tarif holatini, qo'shimcha kassa sonini, AI sarfini ko'rsatish, to'lovni amalga oshirish.
- **Rol/ruxsat**: Egasi (`billing.manage`).
- **Route**: `/app/billing`
- **Layout**: `04-ekranlar-va-ux.md` BO-19 tasvirlangan mazmunga mos.

```
┌──────────────────────────────────────────────────┐
│  Tarif: Yagona — 99 000 so'm/oy                     │
│  Faol kassalar: 2 (1 asosiy + 1 qo'shimcha)         │
│  Keyingi to'lov: 15.11.2026                         │
│  AI limiti: 24% ishlatildi                          │
│  [ − ] 1 [ + ]  Qo'shimcha kassa   [ Oylik/Yillik ▾ ]│
│                      [  TO'LASH (Click/Payme)  ]    │
│  To'lovlar tarixi:  15.10.2026  99 000  [Kvitansiya]│
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `billingCycle` — To'lov davri — Период оплаты — `Select` (`monthly\|yearly`, yillik −20%) — ha; `extraRegisters` — Qo'shimcha kassa soni — Количество дополнительных касс — **+/− stepper** *(2026-10-15: qabul-6/7, E-26 — `Input` number'dan stepper'ga almashtirildi)* — yo'q — ≥0.
- **Amallar**: + Qo'shimcha kassa — oshirish `POST /billing/addons` (`{addon_code:"extra_register", quantity}`); kamaytirish — `DELETE /billing/addons/extra_register` (`requires_archiving` bo'lsa BO-12ga yo'naltirish); TO'LASH (Click/Payme checkout, tana `{provider:"click"|"payme", period:"month"|"year"}`); Kvitansiya — `GET /billing/invoices/{payment_id}`. *(2026-10-15: qabul-6/7, E-26)*
- **Ma'lumot manbai**: `GET /api/v1/billing/addons`, `GET /api/v1/billing/plan`, `GET /api/v1/ai/usage` (`pct_used` — "AI limiti: {pct_used}% ishlatildi", token qaytaradi), `POST /billing/checkout`, `GET /api/v1/billing/invoices/{payment_id}`. *(2026-10-15: qabul-6/7, E-01/E-26, 13-3 #56-65)*
- **Holatlar**: `loading` · `empty` — yo'q (har doim obuna mavjud) · `error` (to'lov o'tmadi) · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida · `subscription-restricted` — bu ekran `restricted` holatda **ochilmaydi** — sessiya bekor qilingan; to'lov faqat BO-01'ning `reason=subscription_expired` variantidagi `GET /billing/pay` tor sahifasida *(2026-10-15: qabul-6/7, E-04, 12-auth §16.1.1)* · **`subscription-grace`** — to'liq ishlaydi (E-04).
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `billing_checkout_started`, `subscription_payment_succeeded`, `extra_register_added`, `extra_register_removed`, `billing_invoice_viewed`.
- **Bog'liq US**: US-M17-02, US-M17-03.

---

## BO-20 — Telegram va bildirishnomalar

- **Maqsad**: Egasi/Menejer Telegram akkauntini ulash, kunlik hisobot vaqtini va ogohlantirish turlarini sozlash.
- **Rol/ruxsat**: Egasi (`telegram.link`, `notifications.manage`), Menejer (`telegram.link` — o'z hisobi, Egasi ruxsati bilan).
- **Route**: `/app/settings/telegram`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Telegram: 🟢 ulangan (@egasi_username)             │
│  Kunlik hisobot vaqti: [ 21:00 ▾ ]                  │
│  Ogohlantirishlar:                                  │
│   [x] Kam qolgan tovar     [x] Kassa farqi          │
│   [x] Limitdan oshgan      [x] Davlat hisoboti      │
│   [x] Offline 48 soat      [x] Obuna eslatmasi      │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `dailyReportTime` — Kunlik hisobot vaqti — Время ежедневного отчёта — `Select` (soat) — ha — default 21:00; `alertToggles.*` — Ogohlantirish turlari — Типы уведомлений — `Switch` (har biri) — yo'q — default barcha yoqilgan.
- **Amallar**: Telegram ulash (QR/havola orqali `Start`) — `telegram.link` → `POST /api/v1/notifications/telegram/link-start`; uzish — `DELETE /api/v1/notifications/telegram/link`; sozlamalarni saqlash — `notifications.manage`. *(2026-10-15: qabul-6/7, E-01)*
- **Ma'lumot manbai**: `POST /api/v1/notifications/telegram/link-start` (+ `GET /api/v1/notifications/telegram/status`, `DELETE /api/v1/notifications/telegram/link`), `GET/PATCH /api/v1/notification-settings`. *(2026-10-15: qabul-6/7, E-01, 13-3 #66-70)*
- **Holatlar**: `loading` · `empty` — yo'q · `error` (bot ulanmadi) · `offline` — ekran ochilmaydi (ulash online talab qiladi) · `no-permission` — Kassir/Omborchi/Buxgalterga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `telegram_linked`, `notification_settings_updated`.
- **Bog'liq US**: US-M18-01, US-M18-02, US-M18-03.

---

## BO-21 — Ro'yxatdan o'tish va birinchi sozlash (onboarding wizard)

- **Maqsad**: yangi Egasini 2 daqiqada ro'yxatdan o'tkazish (tenant ①② dan keyin darhol yaratiladi), boshlang'ich katalog/qoldiq/qarzlarni kiritish, OFD/e-faktura ulash yo'riqnomasini ko'rsatish, iOS/Android o'rnatish bo'yicha yo'naltirish. *(2026-10-15: qabul-6/7, E-27)*
- **Rol/ruxsat**: Yangi foydalanuvchi (ruxsatsiz, o'z-o'ziga ro'yxatdan o'tish).
- **Route**: `/onboarding`
- **Layout** (bosqichlar — wizard, `Tabs`/step indikator bilan):

```
┌──────────────────────────────────────────────────┐
│  ① Telefon+parol yoki Google → ② Do'kon →           │
│  ③ Tovarlar/Qoldiq → ④ Boshlang'ich qarzlar →        │
│  ⑤ OFD/e-faktura → ⑥ Qurilma o'rnatish (/install)    │
├──────────────────────────────────────────────────┤
│   [ Joriy bosqich kontenti ]                        │
│                      [ Orqaga ]   [ Davom ]         │
└──────────────────────────────────────────────────┘
```

- **Maydonlar** (bosqich bo'yicha) — *(2026-10-15: asoschi qarori, Q7 — ① bosqich ikki usulga bo'lindi)*:

| Bosqich | Maydon | Label (uz) | Label (ru) | Tur | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|---|
| ① | `signupMethod` | Usul | Способ | Tugmalar: "Telefon + parol" / "**Google bilan kirish**" | Ha | — | Telefon + parol | — |
| ①-telefon | `phone` | Telefon | Телефон | `Input` mask | Ha (telefon yo'li) | `+998` | — | 17 |
| ①-telefon | `otp` | Tasdiqlash kodi | Код подтверждения | `Input` 6 raqam | Ha (telefon yo'li) | 6 raqam, 5 daq TTL; kod **Telegram bot**ga yuboriladi, foydalanuvchi hali botga ulanmagan bo'lsa bot havolasi ko'rsatiladi; Telegram mavjud bo'lmasa **SMS** (zaxira) | — | 6 |
| ①-telefon | `password` | Parol | Пароль | `Input type=password` | Ha (telefon yo'li) | ≥8 belgi | — | 128 — login telefon+parol bilan, parolsiz hisob kira olmaydi *(2026-10-15: qabul-6/7, E-27)* |
| ①-Google | — | — | — | Google OIDC redirect tugmasi | Ha (Google yo'li) | — | — | Qaytgandan keyin telefon raqami (STIR/fiskal uchun) so'raladi |
| ② | `storeName` | Do'kon nomi | Название магазина | `Input` | Ha | 2–100 | — | 100 |
| ② | `businessType` | Faoliyat turi | Вид деятельности | `Select` | Ha | Ro'yxatdan biri | — | — |
| ③a "Tovarlar" | `method` | Kiritish usuli | Способ ввода | Tugmalar | Ha | Qo'lda/Excel-CSV/Foto (AI-03) | — | — |
| ③b "Boshlang'ich qoldiq" | `openingStockMethod` | Kiritish usuli | Способ ввода | Tugmalar | Yo'q | Excel-CSV/qo'lda | — | — *(2026-10-15: qabul-6/7, E-27 — ③ bosqich ikki qismga bo'lindi)* |
| ④ | `debts[]` | Boshlang'ich qarzlar | Начальные долги | Jadval/Excel | Yo'q | ism+telefon+summa | — | — |
| ⑤ | `connectNow` | Hozir ulashni istaysizmi? | Подключить сейчас? | `Switch` | Yo'q | — | Yo'q (keyin ham mumkin) | — |
| ⑥ | `platform` | Qurilma turi | Тип устройства | Tugmalar | Yo'q | Android/iOS/Windows | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Davom (① dan keyin) | — | Yo'q | `POST /auth/signup` (A-01) — tenant ①② dan keyin darhol yaratiladi, ③–⑥ dan oldin (aks holda import qiladigan tenant yo'q) *(2026-10-15: qabul-6/7, E-27)* |
| Davom (boshqa bosqich) | — | Yo'q | Keyingi bosqich |
| Orqaga | — | Yo'q | Oldingi bosqich |
| O'tkazib yuborish (④,⑤,⑥ bosqichlarida) | — | Yo'q | Keyinroq sozlamalarda bajarish mumkin |
| Yakunlash | — | Yo'q | 30 kunlik sinov boshlangan, BO-02ga yo'naltiriladi |

- **UX-INSTALL (⑥ bosqich)**: `<InstallGuide embedded />` — bu bosqich endi alohida `/install` route'ini ichiga oladi (nusxasi emas), batafsil — yuqoridagi **UX-INSTALL** bo'limi. *(2026-10-15: qabul-6/7, E-32)*
- **Owner Telegram link**: ⑤ bosqichda (yoki keyin BO-20 orqali) "Telegram botni ulash" tezkor havolasi — BO-20 bilan bir xil oqim, lekin onboarding ichida qisqartirilgan (faqat QR, batafsil sozlama BO-20da).
- **Ma'lumot manbai**: `POST /auth/signup` (A-01, telefon yo'li) yoki `GET /auth/oauth/google/authorize` → `GET /auth/oauth/google/callback` (Google yo'li, Q7); `POST /auth/otp/request` (`purpose=signup`, Telegram bot birinchi/SMS zaxira) + `POST /auth/otp/verify`; Excel/CSV: `GET /api/v1/import-jobs/templates/products` → `POST /api/v1/import-jobs` (`kind=products`) → `/validate` → `/commit`; qo'lda — `POST /api/v1/products`; boshlang'ich qoldiq — `POST /api/v1/import-jobs` (`kind=opening_stock`) yoki qo'lda `POST /stock-openings`; boshlang'ich qarzlar — `POST /api/v1/import-jobs` (`kind=opening_debts`) → `/validate` → `/commit`, qo'lda — `POST /api/v1/debt-openings` → `/post`; AI-03 foto — `POST /api/v1/attachments` → `POST /api/v1/ai/ocr/jobs` (`doc_type_hint=catalog`), ruxsat `ai.ocr.use`. *(2026-10-15: qabul-6/7, E-01/E-02/E-27, 12-auth §20, 13-2 §1/§6, 13-1 §12.4, 13-3 #73)*
- **Holatlar**: `loading` (OTP kutilmoqda — Telegram yoki SMS) · `empty` — yo'q (wizard har doim bo'sh boshlanadi) · `error` (OTP kelmadi — qayta yuborish/zaxira kanalga o'tish, `OTP_INVALID`, telefon allaqachon ro'yxatda — `VALIDATION_ERROR`; Google yo'lida — "Google autorizatsiyasi muvaffaqiyatsiz") · `offline` — wizard online talab qiladi (ro'yxatdan o'tish) · `no-permission` — yo'q · `subscription-restricted` — tegishli emas (hali obuna yo'q, 30 kun sinov avtomatik). *(2026-10-15: asoschi qarori, Q7)*
- **Klaviatura**: `Enter` keyingi bosqichga o'tadi.
- **Audit/analitika**: `onboarding_started`, `onboarding_step_completed`, `onboarding_completed`, `onboarding_skipped_step`.
- **Bog'liq US**: US-M17-01, US-M04-04, US-M08-07.

---

## UX-INSTALL — Qurilmani o'rnatish yo'riqnomasi (37 ta biznes ekranga kirmaydi, yordamchi route) *(2026-10-15: qabul-6/7, E-32)*

- **Route**: `/install` (ochiq, autentifikatsiyasiz — login'dan oldin ham kerak); BO-21 ⑥ bosqichi shu komponentni ichiga oladi (`<InstallGuide embedded />`), alohida nusxa yo'q.
- **Kim ochadi**: (a) BO-21 ⑥; (b) iOS Safari'da `/pos/*` yoki `/app/*` **o'rnatilmagan** holatda ochilsa (`navigator.standalone !== true` va `display-mode: standalone` emas) — POS yo'llari bloklanadi, `/install?platform=ios`ga yo'naltiriladi, back-office'da faqat yuqori banner; (c) BO-11 "Qurilmalar" tab → "Yangi qurilma qo'shish"; (d) POS-04 "bulut printer sozlanmagan" havolasi (`/install#cloud-print`).
- **Bo'limlar**: platforma avtomatik aniqlanadi (iOS / Android Chrome / Windows-Chrome), qo'lda almashtirish tugmalari; iOS: 3 qadam rasm bilan (Safari → Ulashish → "Home ekranga qo'shish") + «O'rnatilmasa ma'lumotlar o'chib ketishi mumkin» ogohlantirishi; Android/Chrome: `beforeinstallprompt` orqali "O'rnatish" tugmasi; **Bulut printer**: Star CloudPRNT/Epson SDP — printer URL'ini sozlash qadamlari, "Sinov cheki"; printer yo'q bo'lsa — elektron chek (QR/Telegram).
- **Holatlar**: `loading` — yo'q; `offline` — matn keshdan (service worker precache); `no-permission`/`subscription-restricted` — tegishli emas.
- **Audit/analitika**: `install_guide_viewed`, `pwa_installed` (`appinstalled` hodisasi), `cloud_printer_test_printed`.
- **Sabab**: iOS'da o'rnatish **majburiy** (ITP IndexedDB'ni tozalaydi, `08-frontend-arxitekturasi.md` §6) va qurilma almashtirilganda login'dan keyin ham qayta kerak — wizard ichida qolib ketsa topib bo'lmaydi.

---

# C. Platforma admin paneli

## ADM-01 — Ichki admin panel

- **Maqsad**: platforma jamoasi tomonidan tenantlar, obunalar, to'lovlar, AI sarfini boshqarish; Egasi hisobi darajasida xavfsizlik amallari.
- **Rol/ruxsat**: Platforma admin (`platform.admin`, alohida `aud=urn:erp:platform`, majburiy TOTP MFA — `12-autentifikatsiya-oauth2.md` §18.1).
- **Route**: `/platform/tenants` (alohida `admin-bff`, asosiy tenant domenidan izolyatsiyalangan)
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Tenantlar          Obuna      To'lov    AI sarfi   │
│  "Mega Market"      active     15.11     1 240/5000 │
│  [Tafsilot] [Muddatni uzaytirish] [Xavfsizlik]       │
├──────────────────────────────────────────────────┤
│  Tafsilot → [Egasi hisobi] [Barcha sessiyalarni tugatish]│
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `search`/`statusFilter`/`addonFilter` ("qo'shimcha kassasi bor") — ro'yxat filtri — `Input`/`Select` — yo'q *(2026-10-15: qabul-6/7, E-30 — `planFilter` olib tashlandi, yagona tarif)*; `extendDays` — Muddatni uzaytirish (kun) — Продлить срок (дней) — `Input` number — ha (amalda) — >0.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Muddatni qo'lda uzaytirish | `platform.admin` | Yo'q (pilot uchun) | `subscriptions.current_period_end` uzayadi |
| Barcha sessiyalarni tugatish | `platform.admin` | "Tenantning barcha sessiyalari bekor qilinadi" | Insident javobi — audit |
| Egasi hisobini bloklash/blokdan chiqarish | `platform.admin` | "Egasi hisobini bloklaysizmi?" | Sessiyalar bekor (bloklashda) |
| Egasi parolini tiklash | `platform.admin` | Yo'q | *(2026-10-15: asoschi qarori, Q7)* Tiklash kodi (`purpose=admin_reset`) — Telegram bot birinchi, SMS zaxira |
| Egasi sessiyalarini ko'rish/bekor qilish | `platform.admin` | Yo'q | `POST /platform/tenants/{id}/owner/sessions/{sid}/revoke` *(2026-10-15: qabul-6/7, E-01 — aniq yozildi)* |

- **Ma'lumot manbai**: `GET /platform/tenants`, `GET /platform/tenants/{id}`, `POST /platform/tenants/{id}/extend-subscription`, `POST /platform/tenants/{id}/revoke-all-sessions`, `GET /platform/tenants/{id}/ai-usage`, `POST /platform/tenants/{id}/owner/block`, `/unblock`, `/reset-password`, `GET/POST /platform/tenants/{id}/owner/sessions`, `POST /platform/tenants/{id}/owner/sessions/{sid}/revoke`. *(2026-10-15: qabul-6/7, E-01)*
- **Holatlar**: `loading` · `empty` (tenant yo'q) · `error` (TOTP noto'g'ri — login rad) · `offline` — ekran online talab qiladi · `no-permission` — `aud=urn:erp:api` token bilan 403 (tenant foydalanuvchisi kira olmaydi) · `subscription-restricted` — tegishli emas (bu ekran obunadan mustaqil).
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `platform_admin_access`, `subscription_extended`, `owner_blocked`, `owner_password_reset`.
- **Bog'liq US**: US-M13-08, US-M17-04.

---

## Yakuniy eslatma — screen count va topilgan bo'shliqlar

**Qamrov**: barcha 37 ekran (POS-01…15 = 15, BO-01…21 = 21, ADM-01 = 1) `04-ekranlar-va-ux.md`dagi ro'yxatga mos yozildi — har biriga maqsad, rol/ruxsat, route, layout, maydon jadvali, amallar, ma'lumot manbai, holatlar, klaviatura, audit va bog'liq US qo'shildi.

**04-ekranlar-va-ux.md'da topilgan bo'shliqlar** (shu hujjat ularni to'ldirdi/izohladi):

1. **Login sahifasining to'liq tafsiloti** (parol, SMS OTP tiklash, obuna-tugagan holat, eksport havolasi) 04-faylda POS-01/BO-01 "Holatlar" ustunida qisqa jumla sifatida bor edi, lekin alohida maydon/amal jadvali yo'q edi — shu hujjatda BO-01/POS-01 to'liq yozildi.
2. **Onboarding wizard (BO-21) bosqichlari** 04-faylda bitta qatorli "Asosiy elementlar" ro'yxati edi (olti bosqich nomi) — bu yerda har bosqich uchun aniq maydon jadvali va validatsiya qo'shildi.
3. **iOS/qurilma o'rnatish yo'riqnomasi** — endi alohida **UX-INSTALL** bo'limi (`/install`, ochiq route) sifatida ajratildi: BO-21 ⑥ bosqichi uni ichiga oladi (`<InstallGuide embedded />`), shu bilan birga login'dan oldin, qurilma almashtirilganda va POS-04/BO-11 havolalaridan ham mustaqil ochiladi — chunki wizard ichida qolib ketsa topib bo'lmas edi. *(2026-10-15: qabul-6/7, E-32)*
4. **Egasi Telegram havolasi** (owner link) — 04-faylda BO-20 ichida umumiy "Telegram ulash" sifatida bor; bu hujjatda BO-20 to'liq maydon/amal jadvali bilan yozildi, BO-21 ichida qisqartirilgan tezkor havola sifatida takrorlandi.
5. **BO-19 (Obuna)ning `restricted` holatda ham ochiq qolishi** ("to'lov sahifasi") 04-faylda aniq ko'rsatilmagan edi — `12-autentifikatsiya-oauth2.md` §16.1 asosida aniqlashtirildi.
6. Aniq ruxsat kodlari (`permission_code` qiymatlari) — 2026-10-15'da `05-xavfsizlik-va-audit.md` ruxsat katalogi bilan moslashtirildi (`spec/tekshiruv/qabul-7-ekran-api.md` E-02). *(2026-10-15: qabul-6/7)*
7. API endpoint nomlari — 2026-10-15'da `spec/02-arxitektura/13-api-katalog-*.md` katalogi bilan moslashtirildi (`spec/tekshiruv/qabul-7-ekran-api.md` E-01). *(2026-10-15: qabul-6/7)*

## Manbalar

- `spec/01-mahsulot/04-ekranlar-va-ux.md` — 37 ekran ro'yxati, wireframelar
- `spec/01-mahsulot/02-modullar-talablari.md` — US-Mxx-nn
- `spec/01-mahsulot/03-biznes-jarayonlar.md` — BP-nn
- `spec/01-mahsulot/08-dizayn-tizimi.md` — tokenlar, komponentlar
- `spec/02-arxitektura/08-frontend-arxitekturasi.md`, `04-offline-sync.md`, `12-autentifikatsiya-oauth2.md`
- `spec/01-mahsulot/06-mvp-chegarasi.md` — yagona tarif
