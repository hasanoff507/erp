# Ekran tafsilotlari — 37 ekran (implementatsiyaga tayyor)

*UX dizayner · 2026-10-15 · Asos: `04-ekranlar-va-ux.md` (37 ekran ro'yxati, wireframelar, UX qoidalari), `02-modullar-talablari.md` (US-Mxx-nn), `03-biznes-jarayonlar.md` (BP-nn), `08-dizayn-tizimi.md` (tokenlar, komponentlar), `08-frontend-arxitekturasi.md` (FSD/Effector/route), `04-offline-sync.md`, `12-autentifikatsiya-oauth2.md`, `06-mvp-chegarasi.md` (tarif).*

## Qanday o'qish kerak

- **Route** — `apps/shell` routeri ichida, `@pages/*` paketiga mos (`08-frontend-arxitekturasi.md` §1). POS yo'llari `/pos/...`, back-office `/app/...`, login `/login`, onboarding `/onboarding`, platforma admin `/platform/...` (alohida `admin-bff`, `12-autentifikatsiya-oauth2.md` §18.1).
- **Ruxsat (permission)** — `role_permissions.permission_code` formatida, scope prefiksi `12-autentifikatsiya-oauth2.md` §10 jadvaliga mos (`sales.*`, `stock.*`, `debts.*`, ...). Aniq kod nomlari **loyihaviy taxmin** — backend ruxsat katalogi bilan 1-sprintda moslashtiriladi.
- **Ma'lumot manbai** — REST `/api/v1/<resource>` uslubida, **boshqa jamoa `spec/02-arxitektura/13-api-katalog-*.md` yozayotgan aniq katalog bilan moslashtirilishi kerak** (nomlar mantiqan to'g'ri, lekin yakuniy emas). Bu eslatma har bir ekranda qaytarilmaydi — bir marta shu yerda qayd etiladi.
- **Holatlar** — har ekranda quyidagi olti holatning tegishlilari ko'rsatiladi: `loading` (skeleton), `empty` (`EmptyState`), `error` (`ErrorState`), `offline` (`OfflineBadge` + funksional cheklov), `no-permission` (`NoPermissionState`, 403 `PERMISSION_DENIED`), `subscription-restricted` (`SubscriptionRestrictedState`, 403 `SUBSCRIPTION_RESTRICTED` — faqat `/login`, to'lov va POS-01 bundan mustasno, chunki ular bu holatning o'zini ko'rsatadi).
- **Audit/analytics** — `audit_log` voqea turlari (`05-xavfsizlik-va-audit.md`, `12-autentifikatsiya-oauth2.md` §14 ro'yxatiga mos) + mahsulot-analitika voqeasi (ichki telemetriya, tashqi vosita tanlanmagan — **ochiq savol**).
- **Validatsiya** — `react-hook-form` + `zod`; backend bir xil xato shaklini (`field`, `code`) qaytaradi (`08-frontend-arxitekturasi.md` §3).

---

# A. Android POS / veb-kassa ekranlari (POS-01…15)

## POS-01 — Kassaga kirish / Smena ochish

- **Maqsad**: kassirni autentifikatsiya qilish (PIN, qurilma OAuth sessiyasi ichida) va smenani ochish.
- **Rol/ruxsat**: Kassir (`shift.open`); huquqsiz foydalanuvchi kira olmaydi.
- **Route**: `/pos/login`
- **Layout** (ASCII — `04-ekranlar-va-ux.md` §6 asosida):

```
┌───────────────────────────────────────┐
│  AIOS Kassa              [UZ/RU]  🔴   │
├───────────────────────────────────────┤
│        Filial: "Chilonzor-3"  ▾        │
│   PIN kod:  [ * * * * ]                │
│        [ 1 ][ 2 ][ 3 ]  [ 4 ][ 5 ][ 6 ]│
│        [ 7 ][ 8 ][ 9 ]  [  ][ 0 ][ ⌫ ] │
│         [  SMENANI OCHISH  ]           │
│   Boshlang'ich naqd:  [ 500 000 ]      │
│   PIN/parolni unutdim?                 │
└───────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `branchId` | Filial | Филиал | `Select` | Ha | Ro'yxatdan biri | Oxirgi tanlangan (local) | — |
| `pin` | PIN kod | PIN-код | `PinPad` (4–6 raqam) | Ha | Faqat raqam, 4–6 ta | — | 6 |
| `openingCash` | Boshlang'ich naqd | Начальная наличность | `MoneyInput` | Ha (smena ochishda) | ≥0, butun son | 0 yoki oxirgi smena yopilgan qoldiq (taxmin) | 9 999 999 999 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Smenani ochish | `shift.open` | Yo'q | `shift.opened` voqeasi, POS-02ga o'tish |
| PIN/parolni unutdim | — | SMS OTP oynasi (`purpose=recovery`) | Yangi PIN/parol o'rnatish seansi |

- **Ma'lumot manbai**: `GET /api/v1/branches`, `POST /api/v1/auth/pin/verify` (online qo'shimcha tasdiq, 4.3-bo'lim), outbox: `shift.opened` (`04-offline-sync.md` §2), `GET /auth/license` (litsenziya tokeni, offline qurilma).
- **Holatlar**: `loading` (filiallar yuklanmoqda) · `empty` — yo'q (smena ochish bo'sh bo'lmaydi) · `error` (PIN noto'g'ri — standart xabar #17/#18) · `offline` (PIN mahalliy heshga qarshi tekshiriladi, litsenziya token amal qilsa) · `no-permission` — yo'q (login ekrani) · `subscription-restricted` — butun ekran qizil banner, faqat to'lov havolasi va "Ma'lumotlarimni yuklab olish" (D2) faol, PIN maydoni o'chirilgan (`12-autentifikatsiya-oauth2.md` §16).
- **Klaviatura**: raqam tugmalari PIN kiritadi, `Enter` tasdiqlaydi, `Esc` tozalaydi.
- **Audit/analitika**: `login_success`, `login_failed`, `account_locked`, `shift.opened`, `pos_login_screen_viewed`.
- **Bog'liq US**: US-M01-04, US-M17-03 (lockout holati), US-M13-06 (parol/PIN tiklash).

---

## POS-02 — Sotish paneli (asosiy chek)

- **Maqsad**: tovarlarni chekka qo'shish, chegirma qo'llash, jami summani ko'rsatish.
- **Rol/ruxsat**: Kassir (`sales.create`, `discount.apply`).
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
| CHEGIRMA | `discount.apply` (>5% — `discount.override`, `ApprovalDialog`) | >5%da Menejer PIN | Chek summasi qayta hisoblanadi |
| BEKOR (qator/chek) | `sales.void` | "Haqiqatan bekor qilasizmi?" (#15) | `sale.draft_voided` audit voqeasi, fiskal chek yo'q |
| TO'LOV ▶ | `sales.create` | Yo'q | POS-03ga o'tish |
| + Mijoz | `debts.create` yoki `sales.create` | Yo'q | Mijoz tanlash/yaratish bottom sheet |

- **Ma'lumot manbai**: lokal Dexie `catalog`/`prices`/`customers` (`04-offline-sync.md` §1); outbox `sale.created` (payload: `sales`+`sale_lines`+`sale_payments`); `GET /api/v1/products?query=` (online qidiruv zahira).
- **Holatlar**: `loading` (katalog snapshot yuklanmoqda) · `empty` ("Chekni boshlang, skanerlang") · `error` ("Mahsulot topilmadi" #21, "Markirovka o'qilmadi" #23 → 3 urinishdan keyin qo'lda MXIK) · `offline` (status panel 🟡/🔴, TO'LOV faol qoladi, markirovka `fiscal-pending` belgisi) · `no-permission` — modul butunlay yopiq bo'lmaydi (Kassir uchun asosiy ekran) · `subscription-restricted` — ekran ochilmaydi, `/pos/login`ga redirect.
- **Klaviatura**: `F1` skaner fokus, `F2` chegirma, `F3` mijoz, `F4` to'lov, `F5` nasiya, `+`/`-` miqdor, `Delete` qatorni o'chirish, `Enter` skaner natijasini qabul qilish.
- **Audit/analitika**: `sale_line_added`, `discount_applied`, `sale.draft_voided`, `marking.offline_sold`, `marking.offline_refused_no_price`.
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

- **Ma'lumot manbai**: to'lov provayderlari (UzQR/Payme/Click/Uzum) — online webhook/Prepare-Complete (`03-integratsiyalar.md`); outbox `sale.created` (`sale_payments.method`).
- **Holatlar**: `loading` (provayder javobi kutilmoqda) · `empty` (summa 0) · `error` ("Payme javob bermadi..." , yetarli naqd yo'q) · `offline` — UzQR/Payme/Click/Uzum tugmalari o'chirilgan (kulrang), naqd/karta(qo'lda)/nasiya faol · `no-permission` — yo'q · `subscription-restricted` — bu ekranga kirilmaydi.
- **Klaviatura**: raqam tugmalari olingan naqdni kiritadi, `Enter` tasdiqlaydi, `Esc` POS-02ga qaytaradi.
- **Audit/analitika**: `payment_method_selected`, `sale.created`, `payment_provider_timeout`.
- **Bog'liq US**: US-M01-01, US-M01-05 (UzQR), US-M08-01 (nasiya).

---

## POS-04 — Chekni chop etish / QR orqali yuborish

- **Maqsad**: fiskal chekni chop etish, QR orqali elektron chek yuborish, qayta chop etish.
- **Rol/ruxsat**: Kassir (`sales.create`, qayta chop etish — `sales.reprint`).
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

- **Maydonlar**: yo'q (faqat ko'rsatish ekrani) — `ReceiptPreview` komponenti chekni render qiladi (`08-dizayn-tizimi.md` §13.1).
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Chop etish | `sales.create` | Yo'q | `shared/lib/printer` adapteri orqali ESC/POS chop |
| QR chek | `sales.create` | Yo'q | Elektron chek havolasi (QR/Telegram) |
| Qayta chop etish | `sales.reprint` | Yo'q | "NUSXA" belgisi bilan chop, `receipt.reprinted` audit |
| Yangi chek boshlash | `sales.create` | Yo'q | POS-02ga qaytish |

- **Ma'lumot manbai**: `fiscal_receipts` (lokal + server tasdiqlangandan keyin), `outbox_jobs(ofd_send)` holati.
- **Holatlar**: `loading` (fiskal belgi kutilmoqda — online) · `empty` — yo'q · `error` (printer ulanmagan/qog'oz tugagan → "QR orqali elektron chek" taklifi, #27) · `offline` (chek lokal saqlanadi, "offlayn" belgisi, fiskal belgi keyin) · `no-permission` — qayta chop etish huquqi yo'q bo'lsa tugma ko'rinmaydi · `subscription-restricted` — bu ekranga kirilmaydi.
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
| `reason` | Sabab | Причина | `Select` | Ha | Ro'yxatdan biri (Nuqsonli/Mos kelmadi/Boshqa) | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| QAYTARISHNI TASDIQLA | `returns.create` | 100 000 so'mdan yuqori yoki chek topilmagan — `ApprovalDialog` (Menejer PIN, har doim) | `return.created` outbox, ombor/qarz/pul tuzatiladi |

- **Ma'lumot manbai**: `GET /api/v1/sales?receipt_no=` (online) yoki lokal keshi; outbox `return.created`.
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
| `dueDays` | To'lov muddati | Срок оплаты | `Select` (7/14/30/60 kun) | Yo'q | — | 30 kun (taxmin) | — |
| `note` | Izoh | Комментарий | `Textarea` | Yo'q | — | — | 200 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| NASIYAGA RASMIYLASHTIR | `debts.create` | Limitdan oshsa `ApprovalDialog` (Menejer PIN; offlaynda bayroq bilan davom) | `sale.created` (`sale_payments.method=debt`) |

- **Ma'lumot manbai**: `customers`/`debt_balances` (lokal, `04-offline-sync.md` §1); mijoz B2B bo'lsa `einvoices` avtomatik loyiha (BO-15da imzolanadi).
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
| Smenani yopish | `shift.close` | "Smenani yopasizmi? Keyin qayta ocholmaysiz" | POS-15ga o'tadi (naqd sanash), keyin `shift.closed` + Z-hisobot |

- **Ma'lumot manbai**: `GET /api/v1/shifts/{id}/summary` (lokal jamlanma offline ham hisoblanadi); outbox `shift.closed`.
- **Holatlar**: `loading` · `empty` (savdo bo'lmagan kun) · `error` (sinxronlanmagan cheklar bor — ogohlantirish, lekin yopishni bloklamaydi) · `offline` (Z-hisobot lokal shakllanadi, OFD'ga ulanganda yuboriladi) · `no-permission` — yo'q · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F8` (global) ochadi.
- **Audit/analitika**: `shift.closed`, `z_report_generated`.
- **Bog'liq US**: US-M01-04.

---

## POS-08 — Yetkazib beruvchidan tovar qabul qilish (kirim)

- **Maqsad**: xaridnoma bo'yicha kelgan tovarni skanerlab solishtirish, qabul qilish.
- **Rol/ruxsat**: Omborchi (`purchases.receive`, `stock.create`).
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
| Markirovkani skanerlash | `stock.create` | 2–3 urinishdan keyin qo'lda MXIK maydoni | Kod `marking_codes` ga yoziladi |
| QABULNI YAKUNLASH | `purchases.receive` | Farq bo'lsa "Nomuvofiqlik bilan yakunlaysizmi?" | `purchase.received` outbox, M04 balans oshadi |

- **Ma'lumot manbai**: `GET /api/v1/purchase-orders/{id}`, outbox `purchase.received`, `marking_codes`.
- **Holatlar**: `loading` · `empty` (xaridnoma tanlanmagan) · `error` (markirovka o'qilmadi, miqdor mos kelmadi) · `offline` (qabul lokal yoziladi) · `no-permission` — ekranga kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F1` skaner fokus.
- **Audit/analitika**: `purchase.received`, `marking_scan_failed`, `receive_discrepancy_flagged`.
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

- **Ma'lumot manbai**: `GET /api/v1/stock/balances?branch=`, outbox `transfer.created`/`transfer.received`.
- **Holatlar**: `loading` · `empty` (ombor tanlanmagan) · `error` (qoldiq yetarli emas) · `offline` (markirovkalangan tovar ham o'z filiallar orasida offline ko'chirilishi **ruxsat etiladi**, audit bilan) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F1` skaner fokus.
- **Audit/analitika**: `transfer.created`, `transfer.received`, `marking.transfer_offline`.
- **Bog'liq US**: US-M06-01, US-M06-02.

---

## POS-10 — Inventarizatsiya (jismoniy sanash)

- **Maqsad**: ombordagi tovarni jismoniy sanab, tizim qoldig'i bilan solishtirish.
- **Rol/ruxsat**: Omborchi (`stock.count`).
- **Route**: `/pos/warehouse/stocktake`
- **Layout**: `04-ekranlar-va-ux.md` §6 POS-10 wireframe'i.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `lines[].countedQty` | Sanalgan miqdor | Подсчитанное количество | `QtyInput` | Ha | ≥0 | Bo'sh | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Skanerlash / Qo'lda kirit | `stock.count` | Yo'q | Qator "sanalgan" deb belgilanadi |
| SANASHNI YAKUNLASH | `stock.count` | "Barcha tovarlar sanaldimi?" | `stock_count.line_recorded` → BO-03ga farq tasdiqlash uchun |

- **Ma'lumot manbai**: `GET /api/v1/stock/count-sheets/{id}`, outbox `stock_count.line_recorded`.
- **Holatlar**: `loading` · `empty` (sanash boshlanmagan) · `error` ("Bu shtrix-kod tizimda yo'q") · `offline` (to'liq lokal ishlaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F1` skaner fokus.
- **Audit/analitika**: `stock_count.line_recorded`, `stock_count_completed`.
- **Bog'liq US**: US-M05-01.

---

## POS-11 — Mahsulot va narxni tez qidirish

- **Maqsad**: narx/qoldiqni faqat ko'rish (sotuvsiz tezkor tekshirish).
- **Rol/ruxsat**: Kassir, Omborchi (`prices.view`, `stock.view`).
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
- **Rol/ruxsat**: Barcha POS rollari (`sync.view`, implicit).
- **Route**: `/pos/sync`
- **Layout**: `04-ekranlar-va-ux.md` §6 POS-12 wireframe'i.
- **Maydonlar**: yo'q.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| QAYTA ULANISHGA URINISH | — | Yo'q | `/sync/push` qayta chaqiriladi |

- **Ma'lumot manbai**: Dexie `outbox` (`04-offline-sync.md` §1–2), `POST /sync/push` natijalari.
- **Holatlar**: `loading` · `empty` (hammasi sinxron — ekran ko'rinmaydi/kichik ko'k belgi) · `error` ("Ulanish muvaffaqiyatsiz, 2 daqiqadan keyin qayta urinadi") · `offline` (asosiy holat — ro'yxat va 48 soat hisoblagichi) · `no-permission` — yo'q · `subscription-restricted` — `sync.drain` holatida ham ko'rsatiladi (fonda drain ishlaydi, UI login sahifasini ko'rsatadi, `12-autentifikatsiya-oauth2.md` §16.4).
- **Klaviatura**: `F12` (global) ochadi.
- **Audit/analitika**: `sync_retry_clicked`, `sync_drain_started`, `sync_drain_completed`.
- **Bog'liq US**: US-M01-02.

---

## POS-13 — Qarz daftari (tezkor)

- **Maqsad**: mijoz qarzini ism/telefon bo'yicha tezkor ko'rish, yozish, to'lov qabul qilish.
- **Rol/ruxsat**: Kassir, Egasi (`debts.view`, `debts.create`, `debts.collect`).
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
| `newDebt.amount` | Qarz summasi | Сумма долга | `MoneyInput` | Ha (yozishda) | >0 | — | 9 999 999 999 |
| `newDebt.note` | Izoh | Комментарий | `Textarea` | Yo'q | — | — | 200 |
| `payment.amount` | To'lov summasi | Сумма платежа | `MoneyInput` | Ha (to'lovda) | >0, ≤ joriy qarz (taxmin — ortig'ini qabul qilish siyosati ochiq) | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| QARZ YOZISH | `debts.create` | Yo'q | `sale.created`/`debt_moves` yozuvi (2–3 soniyada) |
| TO'LOV QABUL QILISH | `debts.collect` | Yo'q | `debt_payment.created`, eng eski qarzdan yopiladi |

- **Ma'lumot manbai**: lokal `customers`/`debt_balances`, outbox `debt_payment.created`.
- **Holatlar**: `loading` · `empty` (qarzdor yo'q) · `error` (telefon formati noto'g'ri, #13) · `offline` (to'liq ishlaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F7` (global) ochadi.
- **Audit/analitika**: `debt_quick_entry`, `debt_payment_collected`.
- **Bog'liq US**: US-M08-05, US-M08-06, US-M08-09.

---

## POS-14 — Kassaga pul qo'yish / kassadan pul olish

- **Maqsad**: naqd pul harakatini sabab bilan yozish.
- **Rol/ruxsat**: Kassir (`cash.movement`); >50 000 so'm olishda `cash.approve` (Menejer/Egasi).
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
| `reason` | Sabab | Причина | `Select` | Ha | Egasi oldi/Inkasso/Xarajat to'lovi/Boshqa | — | — |
| `note` | Izoh | Комментарий | `Textarea` | Reason="Boshqa"da Ha | — | — | 200 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| TASDIQLASH | `cash.movement` | >50 000 so'm olishda `ApprovalDialog` (PIN) | `cash_movement.created`; Xarajat to'lovi → M15'ga avtomatik yozuv |

- **Ma'lumot manbai**: outbox `cash_movement.created`.
- **Holatlar**: `loading` · `empty` — yo'q · `error` (PIN noto'g'ri) · `offline` (to'liq ishlaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: raqamlar summa kiritadi, `Enter` tasdiqlaydi.
- **Audit/analitika**: `cash_movement.created`.
- **Bog'liq US**: US-M16-01.

---

## POS-15 — Smena yopishda naqdni sanash

- **Maqsad**: jismoniy sanalgan naqdni kutilgan naqd bilan solishtirish, farqni qayd etish.
- **Rol/ruxsat**: Kassir (`cash.count`).
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
| DAVOM ETISH | `cash.count` | Farq bo'lsa izohsiz bloklanadi | `cash_count.recorded`, POS-07 Z-hisobotga o'tadi, Egasiga M18 orqali farq xabari |

- **Ma'lumot manbai**: `GET /api/v1/shifts/{id}/expected-cash` (kutilgan naqd — boshlang'ich + naqd sotuv − naqd qaytarish + naqd qarz to'lov + qo'yilgan − olingan), outbox `cash_count.recorded`.
- **Holatlar**: `loading` · `empty` — yo'q · `error` (izohsiz farq — saqlanmaydi) · `offline` (to'liq ishlaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Enter` davom ettiradi.
- **Audit/analitika**: `cash_count.recorded`, `cash_discrepancy_flagged`.
- **Bog'liq US**: US-M16-02.

---

# B. Back-office PWA ekranlari (BO-01…21)

## BO-01 — Kirish (login), tenant/filial tanlash

- **Maqsad**: back-office foydalanuvchilarini (Egasi/Menejer/Buxgalter) autentifikatsiya qilish.
- **Rol/ruxsat**: Barcha (login ekrani — ruxsat talab qilinmaydi).
- **Route**: `/login`
- **Layout**:

```
┌─────────────────────────────────────────┐
│               AIOS                        │
│         [UZ/RU]                           │
│   Telefon:  [ +998 __ ___ __ __ ]          │
│   Parol:    [ ************ ]               │
│          [  KIRISH  ]                      │
│   Parolni unutdim?                         │
└─────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `phone` | Telefon | Телефон | `Input` (mask `+998 XX XXX XX XX`) | Ha | `+998` bilan 9 raqam | — | 17 |
| `password` | Parol | Пароль | `Input type=password` | Ha | ≥1 belgi (backend tekshiradi) | — | 128 |
| `branchId` (login'dan keyin, bir nechta filial bo'lsa) | Filial | Филиал | `Select` | Ha (ko'p filial bo'lsa) | — | Birinchi filial | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| KIRISH | — | Yo'q | Front-channel Authorization Code+PKCE (`12-autentifikatsiya-oauth2.md` §2.1) → BFF cookie |
| Parolni unutdim | — | Yo'q | SMS OTP oynasi (`purpose=recovery`) → yangi parol o'rnatish |
| Ma'lumotlarimni yuklab olish (faqat `subscription-restricted`da ko'rinadi) | — | SMS OTP (`purpose=data_export`) | Bir martalik eksport havolasi (15 daqiqa, D2) |
| To'lash (Click/Payme, faqat `subscription-restricted`da) | — | Yo'q | `pay_url`ga o'tish |

- **Ma'lumot manbai**: `POST /auth/login`, `POST /auth/otp/request`, `POST /auth/otp/verify`, `GET /billing/pay`, `POST /billing/export-my-data`.
- **Holatlar**: `loading` · `empty` — yo'q · `error` ("Telefon yoki parol noto'g'ri", #18 — qaysi qism xato ekani oshkor qilinmaydi) · `offline` (PWA offline ombor/hisobot ko'rishga ruxsat beradi, lekin yangi login internetsiz ishlamaydi) · `no-permission` — yo'q · `subscription-restricted` — banner + to'lov havolasi + eksport havolasi, parol maydoni faol (identifikatsiya uchun), token berilmaydi.
- **Klaviatura**: `Enter` kirishni yuboradi.
- **Audit/analitika**: `login_success`, `login_failed`, `account_locked`, `otp_requested`, `otp_verified`, `data_export_during_restriction`.
- **Bog'liq US**: US-M13-06, US-M17-03.

---

## BO-02 — Dashboard (Egasi/Menejer)

- **Maqsad**: kunlik/haftalik savdo, qoldiq, qarzdorlik, ogohlantirishlarni bir joyda ko'rsatish.
- **Rol/ruxsat**: Egasi, Menejer (`reports.view`).
- **Route**: `/app/dashboard`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-02 wireframe'i.
- **Maydonlar**: `periodFilter` — Davr — Период — `Select` (Bugun/Hafta/Oy) — majburiy emas — default "Bugun"; `branchFilter` — Filial — Филиал — `Select` — majburiy emas — default "Barchasi".
- **Amallar**: karta/ogohlantirish bosilganda tegishli ekranga o'tish (masalan "Davlat hisoboti" → BO-10).
- **Ma'lumot manbai**: `GET /api/v1/reports/dashboard?period=&branch=`.
- **Holatlar**: `loading` (skeleton kartalar) · `empty` (yangi tenant, ma'lumot yo'q) · `error` (hisoblash xatosi, "qayta urinish") · `offline` ("Oxirgi yangilanish: N daqiqa oldin" belgisi) · `no-permission` — Kassir/Omborchi/Buxgalter uchun ko'rinmaydi (sidebar'da yo'q) · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K` tezkor navigatsiya.
- **Audit/analitika**: `dashboard_viewed`.
- **Bog'liq US**: US-M12-01, US-M11-03.

---

## BO-03 — Ombor qoldig'i (+ Ko'chirishlar tab)

- **Maqsad**: qoldiqni ko'rish/boshqarish, ko'chirishlar holatini kuzatish.
- **Rol/ruxsat**: Menejer, Omborchi (`stock.view`, `stock.edit`); Ko'chirish tasdiqlash — `transfer.view`.
- **Route**: `/app/warehouse/stock`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-03 wireframe'i + "Ko'chirishlar" tab (holat: yo'lda/qabul qilindi/farq bilan, 72 soat hisoblagichi).
- **Maydonlar**: `search` — Qidirish — Поиск — `Input` — yo'q — max 64; `branchId` — Ombor/filial — Склад/филиал — `Select` — ha — default joriy filial.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Ko'chirish | `transfer.create` | Yo'q | BO-04 uslubidagi forma/sheet |
| Inventarizatsiya | `stock.count` | "Inventarizatsiyani boshlaysizmi?" | Sanash varag'i yaratiladi (POS-10ga tushadi) |
| Eksport | `reports.export` | Yo'q | Excel yuklanadi |

- **Ma'lumot manbai**: `GET /api/v1/stock/balances?branch=`, `GET /api/v1/transfers?status=`.
- **Holatlar**: `loading` · `empty` (ombor bo'sh — yangi filial) · `error` (ma'lumot sinxron emas, "Oxirgi yangilanish") · `offline` (faqat ko'rish, IndexedDB oxirgi nusxa) · `no-permission` — Kassir/Buxgalterga faqat ko'rish (K), yaratish/tasdiqlash yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K` qidiruv.
- **Audit/analitika**: `stock_viewed`, `transfer_list_viewed`.
- **Bog'liq US**: US-M04-01, US-M04-02, US-M04-03, US-M06-03, US-M04-06.

---

## BO-04 — Xaridnoma yaratish, yetkazib beruvchiga to'lov/qaytarish

- **Maqsad**: xarid buyurtmasi yaratish, AI-03 OCR orqali qog'oz hujjat kiritish, to'lov va qaytarish qayd etish.
- **Rol/ruxsat**: Menejer, Omborchi, Buxgalter (`purchases.create`, `purchases.pay`, `purchases.return`).
- **Route**: `/app/purchases`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│ [Xaridnomalar] [Yetkazib beruvchiga to'lov] [Qaytarish]│
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

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `supplierId` | Yetkazib beruvchi | Поставщик | `Combobox` | Ha | Mavjud/yangi | — | — |
| `lines[].qty` | Miqdor | Количество | `QtyInput` | Ha | >0 | — | — |
| `lines[].price` | Narx | Цена | `MoneyInput` | Ha | >0 | — | — |
| `ocrPhoto` | Hujjat fotosi | Фото документа | Fayl yuklash | Yo'q | JPEG/PNG, ≤10MB | — | — |
| `payment.amount` | To'lov summasi | Сумма платежа | `MoneyInput` | Ha (to'lov tabida) | >0, ≤qarz | — | — |
| `return.reason` | Qaytarish sababi | Причина возврата | `Select` | Ha (qaytarish tabida) | — | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Qog'oz hujjatdan o'qish (AI-03) | `purchases.create` | Past-ishonchli maydonlar sariq, foydalanuvchi tasdiqlashi shart | Forma AI taklifi bilan to'ladi, raqamlar tasdiqlanmaguncha saqlanmaydi |
| XARIDNOMANI YUBORISH | `purchases.create` | Yo'q | `purchase_order.created` |
| To'lov qayd etish | `purchases.pay` | Yo'q | `supplier_payment.created`, kreditorlik kamayadi |
| Yetkazib beruvchiga qaytarish | `purchases.return` | "Qaytarishni tasdiqlaysizmi?" | `supplier_return.created`, ombor/kreditorlik tuzatiladi |

- **Ma'lumot manbai**: `GET/POST /api/v1/purchase-orders`, `POST /api/v1/ai/ocr-document` (AI-03), `POST /api/v1/suppliers/{id}/payments`, `POST /api/v1/supplier-returns`.
- **Holatlar**: `loading` · `empty` (yangi xaridnoma) · `error` (AI OCR noto'g'ri o'qidi — qo'lda tuzatish shart) · `offline` (PWA'da yangi xaridnoma yaratish cheklangan, internet talab qilinadi) · `no-permission` — Kassir/Omborchiga to'lov/qaytarish yopiq (faqat Omborchi — qabul, bu ekranda emas POS-08da) · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `purchase_order.created`, `ai_ocr_used`, `supplier_payment.created`, `supplier_return.created`.
- **Bog'liq US**: US-M07-01, US-M07-02, US-M07-03, US-M07-04, US-M07-05.

---

## BO-05 — Narxlar va chegirma qoidalarini boshqarish

- **Maqsad**: tovar narxini yangilash (tarix bilan), avtomatik chegirma qoidalarini sozlash.
- **Rol/ruxsat**: Menejer (`prices.edit`, `discount.rules.manage`); >limit narx o'zgarishi — `prices.approve` (Egasi).
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
| `rule.category` | Kategoriya | Категория | `Select` | Ha (qoida) | — | — | — |
| `rule.percent` | Chegirma % | Скидка % | `Input` number | Ha (qoida) | 0–100 | — | 100 |
| `rule.startDate`/`endDate` | Boshlanish/tugash | Начало/Конец | `Calendar` | Ha (qoida) | `endDate` ≥ `startDate` | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| SAQLASH (narx) | `prices.edit` | Limitdan katta o'zgarishda `pending_approval` → BO-16 | Eski narx tarixga, yangi narx saqlanadi |
| Qoida yaratish | `discount.rules.manage` | Yo'q | `discount_rule.created` |

- **Ma'lumot manbai**: `GET/PATCH /api/v1/products/{id}/price`, `GET/POST /api/v1/discount-rules`.
- **Holatlar**: `loading` · `empty` (narx belgilanmagan) · `error` (manfiy narx/chegirma) · `offline` (faqat ko'rish) · `no-permission` — Kassir/Omborchiga faqat ko'rish · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `price_changed`, `price_change_pending_approval`, `discount_rule.created`.
- **Bog'liq US**: US-M09-01, US-M09-02, US-M03-02.

---

## BO-06 — Nasiya/qarzdorlar ro'yxati va eslatmalar

- **Maqsad**: qarzdorlarni ko'rish, AI-06 eslatma matnini tasdiqlash, to'lov qabul qilish.
- **Rol/ruxsat**: Menejer, Buxgalter (`debts.view`, `debts.collect`, `debts.remind`); shubhali qarz yopish — `debts.forgive` (Egasi).
- **Route**: `/app/debts`
- **Layout**: `04-ekranlar-va-ux.md` tasvirlangan mazmunga mos jadval + AI eslatma paneli.

```
┌──────────────────────────────────────────────────┐
│  Mijoz          Qarz       Muddat   AI eslatma     │
│  Aliyev Botir   450 000    15 kun   [Ko'rish/Yubor]│
│  [ TO'LOV QABUL QILISH ]                           │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `periodFilter`, `overdueFilter` (0–30/31–60/60+ kun) — `Select`; `payment.amount` — To'lov summasi — Сумма платежа — `MoneyInput` — ha — >0.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| AI eslatmani ko'rish/yuborish | `debts.remind` | Yo'q (matn ko'rib chiqiladi, keyin yuboriladi) | Telegram/SMS orqali yuboriladi |
| TO'LOV QABUL QILISH | `debts.collect` | Yo'q | `debt_payment.created` |
| Shubhali qarz deb yopish | `debts.forgive` (faqat Egasi) | Sabab majburiy matn maydoni | `debt_write_off.created`, audit |

- **Ma'lumot manbai**: `GET /api/v1/debts?overdue=`, `POST /api/v1/ai/debt-reminder` (AI-06), `POST /api/v1/debts/{id}/payments`, `POST /api/v1/debts/{id}/write-off`.
- **Holatlar**: `loading` · `empty` (qarzdor yo'q) · `error` (aloqa ma'lumoti yo'q) · `offline` (faqat ko'rish) · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `debt_reminder_sent`, `debt_payment.created`, `debt_write_off.created`.
- **Bog'liq US**: US-M08-03, US-M08-09, US-M08-10, US-M08-04.

---

## BO-07 — QQS ichki hisob-kitobi

- **Maqsad**: QQS bazasi/summasini ko'rish, qizil faktura kreditini kuzatish.
- **Rol/ruxsat**: Buxgalter (`tax.view`).
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

- **Maydonlar**: `period` — Davr — Период — `Select` (oy/chorak) — ha.
- **Amallar**: yo'q (asosan ko'rish; BO-10ga "Solishtirishni ochish" havolasi).
- **Ma'lumot manbai**: `GET /api/v1/tax/vat-summary?period=`.
- **Holatlar**: `loading` · `empty` (davr yopilmagan) · `error` (hisoblashda nomuvofiqlik) · `offline` (faqat ko'rish) · `no-permission` — faqat Buxgalterda Y/T, Egasi/Menejerda K · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `vat_summary_viewed`.
- **Bog'liq US**: US-M10-01, US-M10-03.

---

## BO-08 — Buxgalteriya jurnali, provodkalar

- **Maqsad**: hisob rejasi bo'yicha avtomatik provodkalarni ko'rish, filtrlash, eksport qilish.
- **Rol/ruxsat**: Buxgalter (`accounting.view`, `accounting.export`).
- **Route**: `/app/accounting/journal`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Sana: [ ... ]  Hisob: [ ... ]   [ Eksport ]       │
├──────────────────────────────────────────────────┤
│  12.10.2026  Sotuv #K-000154   Kassa +69 000       │
│                                 Daromad −69 000     │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `dateFrom`/`dateTo` — `Calendar`; `accountFilter` — `Select` — majburiy emas.
- **Amallar**: Eksport (`accounting.export`) — CSV/Excel yuklash.
- **Ma'lumot manbai**: `GET /api/v1/accounting/ledger-entries?from=&to=&account=`.
- **Holatlar**: `loading` · `empty` (yozuv yo'q) · `error` (balans mos kelmadi) · `offline` (faqat ko'rish) · `no-permission` — faqat Buxgalterda to'liq, boshqa rollarda yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `ledger_viewed`, `ledger_exported`.
- **Bog'liq US**: US-M11-01, US-M11-02.

---

## BO-09 — Hisobotlar markazi

- **Maqsad**: savdo/ombor/buxgalteriya/QQS hisobotlarini tanlab, davr bo'yicha ko'rish va eksport qilish.
- **Rol/ruxsat**: Egasi, Menejer, Buxgalter (`reports.view`, `reports.export`).
- **Route**: `/app/reports`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Hisobot turi: [ Kunlik savdo ▾ ]  Davr: [ ... ]   │
│                                [ PDF ] [ Excel ]    │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `reportType` — Hisobot turi — Тип отчёта — `Select` — ha; `period` — `Calendar range` — ha.
- **Amallar**: PDF/Excel eksport (`reports.export`).
- **Ma'lumot manbai**: `GET /api/v1/reports/{type}?from=&to=`, `POST /api/v1/reports/{type}/export`.
- **Holatlar**: `loading` · `empty` (ma'lumot yo'q) · `error` (eksport muvaffaqiyatsiz) · `offline` (faqat oxirgi keshlangan hisobot) · `no-permission` — Kassir (faqat o'z smenasi), Omborchi (faqat ombor) cheklangan ko'rinishda · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `report_viewed`, `report_exported`.
- **Bog'liq US**: US-M12-01, US-M12-02, US-M12-03.

---

## BO-10 — Davlat hisobotini ichki hisob bilan solishtirish

- **Maqsad**: QQS/aylanma solig'i hisobotini davlat ma'lumoti bilan 5 kalendar kun ichida solishtirish; mulk/yer/JShDS/ijtimoiy — faqat davlat raqami.
- **Rol/ruxsat**: Buxgalter (`tax.reconcile`), Egasi (`tax.view`, yakuniy tasdiq).
- **Route**: `/app/tax/reconciliation`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-10 wireframe'i.
- **Maydonlar**: `taxTypeTab` — `Tabs` (QQS/Aylanma/Mulk*/Yer*/JShDS*/Ijtimoiy*); `correctionNote` — Tuzatish izohi — Комментарий к исправлению — `Textarea` — tuzatish yuborilganda ha — max 1000.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Farqni ko'rib chiqish | `tax.reconcile` | Yo'q | Hujjat darajasidagi farq ro'yxati ochiladi |
| Tuzatish (E-IMZO bilan) | `tax.reconcile` | E-IMZO sertifikat/parol tasdig'i | Holat `tuzatish yuborildi` (kanal — ochiq savol) |

- **Ma'lumot manbai**: `GET /api/v1/tax/reconciliation?type=&period=`, `POST /api/v1/tax/reconciliation/{id}/correction`.
- **Holatlar**: `loading` · `empty` (davlat hisoboti hali e'lon qilinmagan, "Kutilmoqda") · `error` ("⚠ Farq topildi") · `offline` (faqat ichki ustun ko'rinadi, davlat ustuni "internet kerak") · `no-permission` — Egasida faqat K (ko'rish+yakuniy tasdiq), boshqa rollarga yopiq · `subscription-restricted` — kirilmaydi. Qo'shimcha holat: **"Muddat o'tdi — avtomatik qabul qilindi"** (5 kalendar kun ichida javob berilmagan).
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `tax_reconciliation_viewed`, `tax_correction_submitted`, `tax_auto_accepted`.
- **Bog'liq US**: US-M10-02, US-M10-04, AI-05.

---

## BO-11 — Foydalanuvchilar, huquqlar va sessiyalar

- **Maqsad**: xodim qo'shish/bloklash, rol/limit sozlash, parol/PIN tiklash, sessiya/qurilma boshqaruvi.
- **Rol/ruxsat**: Egasi (`settings.users`).
- **Route**: `/app/settings/users`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│ [Xodimlar] [Qurilmalar] [Sessiyalar]               │
├──────────────────────────────────────────────────┤
│  Dilnoza   Kassir    Chilonzor-3   [●Faol]         │
│  [Bloklash][Parolni tiklash][PINni tiklash][Seanslar]│
│                                [ + Xodim qo'shish ] │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `phone` | Telefon | Телефон | `Input` (mask) | Ha | `+998` formati | — | 17 |
| `fullName` | To'liq ism | Полное имя | `Input` | Ha | 2–100 belgi | — | 100 |
| `roleIds` | Rol(lar) | Роль(и) | `Select` (multi) | Ha (≥1) | Kassir/Omborchi/Menejer/Buxgalter | — | — |
| `branchIds` | Filial(lar) | Филиал(ы) | `Select` (multi) | Ha (≥1) | — | Joriy filial | — |
| `limits.discountPercent` | Chegirma limiti % | Лимит скидки % | `Input` number | Yo'q | 0–100 | 5 | 100 |
| `limits.returnAmount` | Qaytarish limiti | Лимит возврата | `MoneyInput` | Yo'q | ≥0 | 100 000 | — |
| `limits.cashOutAmount` | Pul olish limiti | Лимит выдачи | `MoneyInput` | Yo'q | ≥0 | 50 000 | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| + Xodim qo'shish | `settings.users` | Yo'q | SMS taklif kodi (`purpose=invite`) yuboriladi |
| Bloklash/Blokdan chiqarish | `settings.users` | "Xodimni bloklaysizmi?" | Sessiyalar darhol revoke |
| Parolni tiklash | `settings.users` | Yo'q | SMS tiklash kodi (`purpose=admin_reset`) |
| PINni qayta o'rnatish | `settings.users` | Yo'q | Eski PIN bekor, keyingi kirishda yangi PIN majburiy |
| Seanslarni tugatish | `settings.users` | Yo'q | Tanlangan sessiya/barcha sessiya bekor |
| Qurilmani bekor qilish | `settings.users` | "Qurilmani bekor qilasizmi?" | `devices.revoked_at`, token/litsenziya bekor |

- **Ma'lumot manbai**: `POST/PATCH /api/v1/admin/users`, `GET /api/v1/admin/users/{id}/sessions`, `GET /api/v1/admin/users/{id}/devices`, `POST /api/v1/admin/users/{id}/reset-password`, `POST /api/v1/admin/users/{id}/reset-pin`, `POST /api/v1/admin/users/{id}/revoke-sessions`.
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
| `cashRegisterCount` | Kassa soni | Количество касс | `Input` number | Ha | ≥1 | 1 | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| + Filial qo'shish | `settings.branches` | Yo'q | `branches.created` |
| Tahrir/Saqlash | `settings.branches` | Toifa o'zgartirilsa "Yangi stavka faqat shu sanadan qo'llanadi" | `branch_tax_settings` yangi yozuv (`valid_from`) |

- **Ma'lumot manbai**: `GET/POST/PATCH /api/v1/branches`.
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
- **Maydonlar**: `message` — Xabar — Сообщение — `Textarea`/`Input` — ha (yuborishda) — max 500.
- **Amallar**: tez savol tugmalari (preset), yuborish (`Enter`/`➤`).
- **Ma'lumot manbai**: `POST /api/v1/ai/chat` (backend SQL hisoblaydi, LLM faqat tushuntiradi).
- **Holatlar**: `loading` (AI yozmoqda) · `empty` (suhbat boshlanmagan — tez savol tugmalari) · `error` ("Bu savolga aniq javob topa olmadim", #33) · `offline` (chat butunlay o'chirilgan, "AI uchun internet kerak") · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi; AI oylik limiti tugaganda alohida xabar ("AI limiti tugadi, keyingi oygacha kutilmoqda yoki tarifni oshiring").
- **Klaviatura**: `Enter` yuboradi, `Shift+Enter` yangi qator.
- **Audit/analitika**: `ai_chat_message_sent`, `ai_chat_no_answer`, `ai_quota_exceeded`.
- **Bog'liq US**: AI-01, US-M18-04 (bot orqali bir xil backend).

---

## BO-14 — Tenant/do'kon sozlamalari

- **Maqsad**: do'kon nomi, til, valyuta, soliq rejimi, integratsiyalar holatini boshqarish.
- **Rol/ruxsat**: Egasi (`settings.tenant`).
- **Route**: `/app/settings/tenant`
- **Layout**:

```
┌──────────────────────────────────────────────────┐
│  Do'kon nomi:   [ "Mega Market" ]                  │
│  Soliq rejimi:  [ QQS to'lovchi ▾ ]                │
│  Zaxira usuli:  [ O'rtacha narx (AVECO) ▾ ]        │
│  OFD:       🟢 ulangan     E-faktura: 🟢 Faktura.uz │
│  Asl belgisi: 🟡 kalit kiritilmagan                │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `storeName` | Do'kon nomi | Название магазина | `Input` | Ha | 2–100 | — | 100 |
| `taxRegime` | Soliq rejimi | Налоговый режим | `Select` | Ha | `vat\|turnover` | — | — |
| `costingMethod` | Zaxira baholash usuli | Метод оценки запасов | `Select` | Ha | `AVECO\|FIFO` | `AVECO` | — |
| `crptApiKey` | Asl belgisi API kaliti | API-ключ Asl belgisi | `Input` (masked) | Yo'q | — | — | 256 |
| `fakturaUzCredentials` | Faktura.uz login/parol | Логин/пароль Faktura.uz | `Input`×2 (masked) | Yo'q | — | — | — |

- **Amallar**: Saqlash (`settings.tenant`); zaxira usulini o'zgartirish — "Bu o'zgarish faqat keyingi hisobot yili boshidan kuchga kiradi" tasdiqlash dialogi.
- **Ma'lumot manbai**: `GET/PATCH /api/v1/tenant/settings`, `POST /api/v1/tenant/integrations/crpt`, `POST /api/v1/tenant/integrations/faktura-uz`.
- **Holatlar**: `loading` · `empty` (sozlanmagan) · `error` (integratsiya ulanmagan) · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `tenant_settings_updated`, `costing_method_change_scheduled`, `integration_connected`.
- **Bog'liq US**: US-M04-05.

---

## BO-15 — Kiruvchi va chiquvchi e-faktura markazi

- **Maqsad**: kiruvchi e-fakturalarni qabul/E-IMZO imzolash, chiquvchi (B2B nasiya + chekdan keyingi) e-fakturalarni boshqarish.
- **Rol/ruxsat**: Buxgalter (`einvoice.view`, `einvoice.sign`).
- **Route**: `/app/einvoices`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-15 wireframe'i.
- **Maydonlar**: `receiptSearch` — Chekni qidirish (chekdan e-faktura chiqarishda) — Поиск чека — `Input` — ha — chek raqami/sana.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Qabul qilish | `einvoice.view` | Yo'q | Faktura `ledger`/`tax`ga qo'shiladi |
| Rad etish | `einvoice.view` | Sabab majburiy | Faktura rad etilgan deb belgilanadi |
| E-IMZO imzo | `einvoice.sign` | Sertifikat/parol | PKCS#7 imzo, EDO operatoriga yuborish |
| Chek asosida e-faktura chiqarish | `einvoice.sign` | Yo'q | `einvoices.related_doc` bilan chekka bog'langan yangi hujjat, QQS qayta hisoblanmaydi |

- **Ma'lumot manbai**: `GET /api/v1/einvoices?direction=in|out`, `POST /api/v1/einvoices/{id}/sign`, `POST /api/v1/einvoices/from-receipt`.
- **Holatlar**: `loading` · `empty` (faktura yo'q) · `error` (E-IMZO imzolashda xato — sertifikat/parol) · `offline` (faqat ko'rish, imzolash internet talab qiladi) · `no-permission` — faqat Buxgalterda · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `einvoice_signed`, `einvoice_rejected`, `einvoice_from_receipt_created`.
- **Bog'liq US**: US-M07-03, US-M01-06, US-M10-03.

---

## BO-16 — Tasdiqlash navbati (limitdan oshgan so'rovlar)

- **Maqsad**: chegirma/qaytarish/nasiya/narx/katta pul olish so'rovlarini bitta navbatda ko'rish va PIN bilan tasdiqlash.
- **Rol/ruxsat**: Egasi, Menejer (`approvals.manage`).
- **Route**: `/app/approvals`
- **Layout**: `04-ekranlar-va-ux.md` §6 BO-16 wireframe'i.
- **Maydonlar**: `pin` — PIN — PIN — `Input` (4–6 raqam) — ha (tasdiqlashda) — raqam.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Tasdiqlash | `approvals.manage` | PIN kiritish | So'rov bajariladi (chegirma/qaytarish/nasiya/narx/pul olish) |
| Rad etish | `approvals.manage` | Sabab majburiy | So'rov bekor, kassirga xabar |

- **Ma'lumot manbai**: `GET /api/v1/approvals?status=pending`, `POST /api/v1/approvals/{id}/approve`, `POST /api/v1/approvals/{id}/reject`.
- **Holatlar**: `loading` · `empty` (navbat bo'sh) · `error` (PIN noto'g'ri) · `offline` (PWA'da yangi tasdiqlash cheklangan — Menejer Android POSda inline tasdiqlaydi) · `no-permission` — Buxgalter/Omborchi/Kassirga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `approval_approved`, `approval_rejected`.
- **Bog'liq US**: US-M02-02, US-M03-01, US-M08-01, US-M09-02, US-M16-01.

---

## BO-17 — Xarajatlar

- **Maqsad**: operatsion xarajatlarni (ijara, kommunal, transport) yozish, takrorlanuvchi xarajatlarni sozlash.
- **Rol/ruxsat**: Egasi, Menejer, Buxgalter (`expenses.create`, `expenses.view`).
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
| `category` | Toifa | Категория | `Select` | Ha | Ijara/Kommunal/Ish haqi/Transport/Soliq/Ta'mirlash/Boshqa | — | — |
| `source` | To'lov manbai | Источник оплаты | `Select` | Ha | `cash\|bank\|card` | — | — |
| `note` | Izoh | Комментарий | `Textarea` | Yo'q | — | — | 200 |
| `receiptPhoto` | Hujjat fotosi | Фото документа | Fayl yuklash | Yo'q | JPEG/PNG ≤10MB | — | — |
| `recurrence` | Takrorlanish | Повторение | `Select` | Yo'q | `none\|monthly` | `none` | — |

- **Amallar**: + Xarajat qo'shish (`expenses.create`), takrorlanuvchi xarajat eslatmasini tasdiqlash ("Ijara to'lash vaqti" — bir bosishda).
- **Ma'lumot manbai**: `GET/POST /api/v1/expenses`, `GET/POST /api/v1/expenses/recurring`.
- **Holatlar**: `loading` · `empty` (xarajat yo'q) · `error` — standart validatsiya · `offline` (faqat ko'rish; kassadan to'langan xarajat POSda yoziladi) · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `expense.created`, `expense_voided` (teskari yozuv).
- **Bog'liq US**: US-M15-01, US-M15-02, US-M15-03.

---

## BO-18 — Yorliq va shtrix-kod chop etish

- **Maqsad**: narxi o'zgargan tovarlar uchun yorliq chop etish, ichki shtrix-kod yaratish.
- **Rol/ruxsat**: Menejer (`labels.print`, `labels.generate`).
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
- **Amallar**: Ichki shtrix-kod yaratish (`labels.generate`), CHOP ETISH (`labels.print`).
- **Ma'lumot manbai**: `GET /api/v1/products?label_pending=true`, `POST /api/v1/products/{id}/internal-barcode`, chop etish — `react-to-print` + `bwip-js` (frontendda).
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
│  AI sarfi (shu oy): 1 240 / 5 000 so'rov            │
│  [ + Qo'shimcha kassa ]  [ Oylik/Yillik ▾ ]         │
│                      [  TO'LASH (Click/Payme)  ]    │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `billingCycle` — To'lov davri — Период оплаты — `Select` (`monthly\|yearly`, yillik −20%) — ha; `extraRegisters` — Qo'shimcha kassa soni — Количество дополнительных касс — `Input` number — yo'q — ≥0.
- **Amallar**: + Qo'shimcha kassa (`billing.manage`), TO'LASH (Click/Payme checkout).
- **Ma'lumot manbai**: `GET /api/v1/billing/subscription`, `GET /api/v1/billing/ai-usage`, `POST /api/v1/billing/checkout`, `GET /api/v1/billing/payments`.
- **Holatlar**: `loading` · `empty` — yo'q (har doim obuna mavjud) · `error` (to'lov o'tmadi) · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida · `subscription-restricted` — bu ekran `restricted` holatda ham to'lov qilish uchun ochiq (login orqali emas, `/billing/pay` alohida ochiq yo'l).
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `billing_checkout_started`, `subscription_payment_succeeded`, `extra_register_added`.
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
- **Amallar**: Telegram ulash (QR/havola orqali `Start`) — `telegram.link`; sozlamalarni saqlash — `notifications.manage`.
- **Ma'lumot manbai**: `POST /api/v1/telegram/link`, `GET/PATCH /api/v1/notifications/settings`.
- **Holatlar**: `loading` · `empty` — yo'q · `error` (bot ulanmadi) · `offline` — ekran ochilmaydi (ulash online talab qiladi) · `no-permission` — Kassir/Omborchi/Buxgalterga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `telegram_linked`, `notification_settings_updated`.
- **Bog'liq US**: US-M18-01, US-M18-02, US-M18-03.

---

## BO-21 — Ro'yxatdan o'tish va birinchi sozlash (onboarding wizard)

- **Maqsad**: yangi Egasini 2 daqiqada ro'yxatdan o'tkazish, boshlang'ich katalog/qarzlarni kiritish, OFD/e-faktura ulash yo'riqnomasini ko'rsatish, iOS/Android o'rnatish bo'yicha yo'naltirish.
- **Rol/ruxsat**: Yangi foydalanuvchi (ruxsatsiz, o'z-o'ziga ro'yxatdan o'tish).
- **Route**: `/onboarding`
- **Layout** (bosqichlar — wizard, `Tabs`/step indikator bilan):

```
┌──────────────────────────────────────────────────┐
│  ① Telefon → ② Do'kon → ③ Boshlang'ich tovar →      │
│  ④ Boshlang'ich qarzlar → ⑤ OFD/e-faktura →          │
│  ⑥ Qurilma o'rnatish (Android/iOS)                  │
├──────────────────────────────────────────────────┤
│   [ Joriy bosqich kontenti ]                        │
│                      [ Orqaga ]   [ Davom ]         │
└──────────────────────────────────────────────────┘
```

- **Maydonlar** (bosqich bo'yicha):

| Bosqich | Maydon | Label (uz) | Label (ru) | Tur | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|---|
| ① | `phone` | Telefon | Телефон | `Input` mask | Ha | `+998` | — | 17 |
| ① | `otp` | SMS kod | SMS-код | `Input` 6 raqam | Ha | 6 raqam, 5 daq TTL | — | 6 |
| ② | `storeName` | Do'kon nomi | Название магазина | `Input` | Ha | 2–100 | — | 100 |
| ② | `businessType` | Faoliyat turi | Вид деятельности | `Select` | Ha | Ro'yxatdan biri | — | — |
| ③ | `method` | Kiritish usuli | Способ ввода | Tugmalar | Ha | Qo'lda/Excel-CSV/Foto (AI-03) | — | — |
| ④ | `debts[]` | Boshlang'ich qarzlar | Начальные долги | Jadval/Excel | Yo'q | ism+telefon+summa | — | — |
| ⑤ | `connectNow` | Hozir ulashni istaysizmi? | Подключить сейчас? | `Switch` | Yo'q | — | Yo'q (keyin ham mumkin) | — |
| ⑥ | `platform` | Qurilma turi | Тип устройства | Tugmalar | Yo'q | Android/iOS/Windows | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Davom | — | Yo'q | Keyingi bosqich |
| Orqaga | — | Yo'q | Oldingi bosqich |
| O'tkazib yuborish (④,⑤,⑥ bosqichlarida) | — | Yo'q | Keyinroq sozlamalarda bajarish mumkin |
| Yakunlash | — | Yo'q | Tenant yaratiladi, 30 kunlik sinov boshlanadi, BO-02ga yo'naltiriladi |

- **iOS o'rnatish yo'riqnomasi (⑥ bosqich, iOS tanlanganda)**: "Safari'da ochib, pastdagi ulashish tugmasi → 'Home ekranga qo'shish' bosing. Chek chop etish uchun bulut-printer kerak bo'ladi (keyinroq sozlamalardan ulanadi)" — matnli qadamlar + rasm, Home Screen'ga PWA sifatida o'rnatish majburiy ekanligi tushuntiriladi (`08-frontend-arxitekturasi.md` §6).
- **Owner Telegram link**: ⑤ bosqichda (yoki keyin BO-20 orqali) "Telegram botni ulash" tezkor havolasi — BO-20 bilan bir xil oqim, lekin onboarding ichida qisqartirilgan (faqat QR, batafsil sozlama BO-20da).
- **Ma'lumot manbai**: `POST /api/v1/onboarding/signup`, `POST /api/v1/auth/otp/verify`, `POST /api/v1/onboarding/products/bulk` (qo'lda/CSV), `POST /api/v1/ai/ocr-document` (AI-03, boshlang'ich katalog fotosi), `POST /api/v1/onboarding/debts/bulk`.
- **Holatlar**: `loading` (SMS kutilmoqda) · `empty` — yo'q (wizard har doim bo'sh boshlanadi) · `error` (SMS kelmadi — qayta yuborish) · `offline` — wizard online talab qiladi (ro'yxatdan o'tish) · `no-permission` — yo'q · `subscription-restricted` — tegishli emas (hali obuna yo'q, 30 kun sinov avtomatik).
- **Klaviatura**: `Enter` keyingi bosqichga o'tadi.
- **Audit/analitika**: `onboarding_started`, `onboarding_step_completed`, `onboarding_completed`, `onboarding_skipped_step`.
- **Bog'liq US**: US-M17-01, US-M04-04, US-M08-07.

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

- **Maydonlar**: `search`/`statusFilter`/`planFilter` — ro'yxat filtri — `Input`/`Select` — yo'q; `extendDays` — Muddatni uzaytirish (kun) — Продлить срок (дней) — `Input` number — ha (amalda) — >0.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Muddatni qo'lda uzaytirish | `platform.admin` | Yo'q (pilot uchun) | `subscriptions.current_period_end` uzayadi |
| Barcha sessiyalarni tugatish | `platform.admin` | "Tenantning barcha sessiyalari bekor qilinadi" | Insident javobi — audit |
| Egasi hisobini bloklash/blokdan chiqarish | `platform.admin` | "Egasi hisobini bloklaysizmi?" | Sessiyalar bekor (bloklashda) |
| Egasi parolini tiklash | `platform.admin` | Yo'q | SMS tiklash kodi (`purpose=admin_reset`) |
| Egasi sessiyalarini ko'rish/bekor qilish | `platform.admin` | Yo'q | Tanlangan sessiya bekor |

- **Ma'lumot manbai**: `GET /platform/tenants`, `GET /platform/tenants/{id}`, `POST /platform/tenants/{id}/extend-subscription`, `POST /platform/tenants/{id}/revoke-all-sessions`, `GET /platform/tenants/{id}/ai-usage`, `POST /platform/tenants/{id}/owner/block`, `/unblock`, `/reset-password`, `GET/POST /platform/tenants/{id}/owner/sessions`.
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
3. **iOS o'rnatish yo'riqnomasi** — 04-faylda alohida ekran yo'q, faqat §1.6/§1.7da "iOS PWA" texnik eslatma bor edi. Bu hujjatda BO-21 ⑥-bosqichi (va BO-20/Telegram bilan bog'liq holda) ichiga joylashtirildi — **tavsiya**: kelajakda alohida qisqa ekran/modal (`/onboarding/install-ios`) sifatida ajratilishi mumkin, chunki u login-dan keyin ham (qurilma almashtirilganda) qayta kerak bo'ladi.
4. **Egasi Telegram havolasi** (owner link) — 04-faylda BO-20 ichida umumiy "Telegram ulash" sifatida bor; bu hujjatda BO-20 to'liq maydon/amal jadvali bilan yozildi, BO-21 ichida qisqartirilgan tezkor havola sifatida takrorlandi.
5. **BO-19 (Obuna)ning `restricted` holatda ham ochiq qolishi** ("to'lov sahifasi") 04-faylda aniq ko'rsatilmagan edi — `12-autentifikatsiya-oauth2.md` §16.1 asosida aniqlashtirildi.
6. Aniq ruxsat kodlari (`permission_code` qiymatlari) 04-faylda yo'q — bu hujjatda **loyihaviy taxmin** sifatida qo'yildi, backend ruxsat katalogi bilan moslashtirilishi kerak.
7. API endpoint nomlari — na 04-faylda, na boshqa joyda yakuniy ro'yxat yo'q; `spec/02-arxitektura/13-api-katalog-*.md` bilan reconciliation kerak (yuqorida bir marta qayd etildi).

## Manbalar

- `spec/01-mahsulot/04-ekranlar-va-ux.md` — 37 ekran ro'yxati, wireframelar
- `spec/01-mahsulot/02-modullar-talablari.md` — US-Mxx-nn
- `spec/01-mahsulot/03-biznes-jarayonlar.md` — BP-nn
- `spec/01-mahsulot/08-dizayn-tizimi.md` — tokenlar, komponentlar
- `spec/02-arxitektura/08-frontend-arxitekturasi.md`, `04-offline-sync.md`, `12-autentifikatsiya-oauth2.md`
- `spec/01-mahsulot/06-mvp-chegarasi.md` — yagona tarif
