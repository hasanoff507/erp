# API katalogi — 3. Moliya va Admin (M10–M18, AI)

*2026-10-15 · Konventsiyalar: `13-api-katalog-0-umumiy.md` (base path, ID/pul/sana format, pagination, headerlar, xato konverti, hujjat hayot sikli, xato kodlari katalogi — bu faylda takrorlanmaydi, faqat qo'llaniladi). Auth/sync endpoint'lari: `12-autentifikatsiya-oauth2.md` §20, `04-offline-sync.md` §3 — bu faylda faqat havola qilinadi, qayta yozilmaydi. Asos: `spec/01-mahsulot/02-modullar-talablari.md` (M10–M18), `04-ekranlar-va-ux.md`, `05-ai-funksiyalar.md`, `07-ai-qatlami.md`, `01-malumotlar-modeli.md`, `02-provodka-qoidalari.md`, `05-xavfsizlik-va-audit.md` §2.1–2.2.*

## Asosiy xulosalar

1. **79 endpoint + qabul-6/7 qo'shimchalari** 10 guruhda: M10 QQS (8, yo'llar `/reports/vat-summary`/`/vat-moves`ga ko'chirildi), M11 Buxgalteriya (8 + `ledger-adjustments` 2 ta yangi — jami 10), M12 Hisobotlar (7), M13 Huquqlar (6, foydalanuvchi CRUD'i `12-autentifikatsiya-oauth2.md`da — bu yerda faqat rol/ruxsat), M14 Filiallar (11), **M13a/M14 Tenant sozlamalari (5, yangi — K3-01)**, M15 Xarajatlar (11), M16 Kassa pul harakati (4), M17 Obuna (10 + `/billing/export-my-data` havolasi + platforma admin havolasi), M18 Bildirishnomalar (6), AI (8). *(2026-10-15: qabul-6/7)*
2. Hujjat turidagi resurslar (`expenses`, `cash-movements`) — `13-api-katalog-0-umumiy.md` §9dagi `draft → post → cancel` naqshiga rioya qiladi; faqat sof o'qish/sozlama resurslari (`roles`, `branches`, `notification-settings`) CRUD (`GET`/`POST`/`PATCH`) shaklida.
3. M17 platforma admin endpoint'lari (`/platform/*`) **allaqachon** `12-autentifikatsiya-oauth2.md` §18.1'da to'liq yozilgan — bu faylda faqat ro'yxat ko'rinishida qayta ko'rsatiladi (to'liq sxema u yerda), ikki marta yozilmaydi.
4. Excel/PDF eksport (M12, M10 hisobotlari) — `13-api-katalog-0-umumiy.md` §13dagi asinxron job naqshi; Click/Payme (M17) — §14dagi webhook naqshi.
5. AI-01 (chat) — SSE streaming (`text/event-stream`); AI-03 (OCR) — ikki bosqichli (yuklash+tahlil → tasdiqlash); AI-05/AI-06 — "kod hisoblaydi, AI tushuntiradi" tamoyili bo'yicha faqat tushuntirish/matn, raqamni o'zi hech qachon hisoblamaydi (`05-ai-funksiyalar.md` Asosiy xulosa #2).
6. Bu seriya yozilayotganda ma'lumotlar modelida **6 ta qo'shimcha** kerak bo'ldi (oxirgi bo'limda, `01-malumotlar-modeli.md` tahrirlanmadi — faqat shu yerda ro'yxat qilindi).

---

## Endpoint indeksi

| # | Metod + yo'l | Modul | Maqsad | Ruxsat |
|---|---|---|---|---|
| 1 | `GET /reports/vat-summary` | M10 | Ichki QQS/aylanma hisob-kitobi (davr bo'yicha) | `tax.vat.view` |
| 2 | `GET /vat-moves` | M10 | QQS registri (`vat_moves`) ro'yxati | `tax.vat.view` |
| 3 | `POST /state-reports` | M10 | Davlat hisoboti faylini yuklash | `tax.compare.review` |
| 4 | `POST /state-reports/{id}/compare` | M10 | Solishtirishni (qayta) ishga tushirish | `tax.compare.review` |
| 5 | `GET /state-reports` | M10 | Davlat hisobotlari ro'yxati | `tax.vat.view` |
| 6 | `GET /state-reports/{id}` | M10 | Hisobot tafsiloti + holat | `tax.vat.view` |
| 7 | `GET /state-reports/{id}/diffs` | M10 | Farq qatorlari ro'yxati | `tax.compare.review` |
| 8 | `POST /state-reports/{id}/correction` | M10 | Tuzatish/e'tiroz yuborish (E-IMZO) | `tax.correction.submit` |
| 9 | `GET /ledger-entries` | M11 | Buxgalteriya jurnali | `accounting.post` |
| 10 | `POST /ledger-adjustments` | M11 | Qo'lda tuzatuvchi yozuv (joriy ochiq davr, bir bosqichli hujjat) | `accounting.post` |
| 10a | `POST /ledger-adjustments/{id}/cancel` | M11 | Tuzatuvchi yozuvni bekor qilish | `accounting.post` |
| 10b | `GET /ledger-adjustments` | M11 | Tuzatuvchi yozuvlar ro'yxati | `accounting.post` |
| 11 | `GET /reports/trial-balance` | M11 | Aylanma-saldo vedomosti | `reports.finance.view` |
| 12 | `GET /reports/profit-and-loss` | M11 | Foyda-zarar hisoboti | `reports.finance.view` |
| 13 | `GET /reports/balance-sheet` | M11 | Balans hisoboti | `reports.finance.view` |
| 14 | `GET /period-closings` | M11 | Yopilgan davrlar ro'yxati | `accounting.post` |
| 15 | `POST /period-closings` | M11 | Davrni yopish | `accounting.period.close` |
| 16 | `GET /period-closings/{period}/readiness` | M11 | Yopishga tayyormi (recost/fiskal tekshiruvi) | `accounting.post` |
| 17 | `GET /reports/dashboard` | M12 | Egasi/Menejer dashboard ma'lumoti | `reports.sales.view` |
| 18 | `GET /reports/sales` | M12 | Savdo hisoboti (filial/davr) | `reports.sales.view` |
| 19 | `GET /reports/top-products` | M12 | Eng ko'p/kam sotilgan tovarlar | `reports.sales.view` |
| 20 | `GET /reports/stock` | M12 | Qoldiq hisoboti | `stock.view` |
| 21 | `GET /reports/debts-aging` | M12 | Qarzdorlik "yosh" guruhlari (0-30/31-60/60+) | `reports.finance.view` |
| 22 | `POST /reports/{report-kod}/export` | M12 | Hisobotni Excel/PDF eksport qilish (job) | `reports.export` |
| 23 | `GET /reports/export-jobs/{job_id}` | M12 | Eksport job holati | `reports.export` |
| 24 | `GET /roles` | M13 | Rollar ro'yxati | `settings.users` |
| 25 | `POST /roles` | M13 | Yangi (maxsus) rol yaratish | `settings.users` |
| 26 | `PATCH /roles/{id}` | M13 | Rol nomini/tavsifini tahrirlash | `settings.users` |
| 27 | `GET /roles/{id}/permissions` | M13 | Rolning ruxsat/limit ro'yxati | `settings.users` |
| 28 | `PUT /roles/{id}/permissions` | M13 | Rol ruxsat/limitlarini belgilash | `settings.users` |
| 29 | `GET /permissions-catalog` | M13 | To'liq ruxsat kodlari katalogi (statik) | `settings.users` |
| 30 | `GET /branches` | M14 | Filiallar ro'yxati | `—` |
| 31 | `POST /branches` | M14 | Yangi filial yaratish | `settings.branches` |
| 32 | `GET /branches/{id}` | M14 | Filial tafsiloti | `—` |
| 33 | `PATCH /branches/{id}` | M14 | Filialni tahrirlash | `settings.branches` |
| 34 | `GET /branches/{id}/tax-settings` | M14 | Aholi punkti toifasi tarixi | `—` |
| 35 | `POST /branches/{id}/tax-settings` | M14 | Yangi toifa qiymati qo'shish | `settings.branches` |
| 36 | `POST /branches/{id}/copy-pricing` | M14 | Narx/chegirma siyosatini boshqa filialga nusxalash | `prices.edit` |
| 37 | `GET /warehouses` | M14 | Omborlar ro'yxati | `—` |
| 38 | `GET /cash-registers` | M14 | Kassalar ro'yxati | `—` |
| 39 | `POST /cash-registers` | M14 | Yangi kassa qo'shish | `cash_register.manage` |
| 40 | `PATCH /cash-registers/{id}` | M14 | Kassani tahrirlash/arxivlash | `cash_register.manage` |
| 40a | `GET /tenant/settings` | M13a/M14 | Do'kon sozlamalari + integratsiya holati | `settings.tenant` |
| 40b | `PATCH /tenant/settings` | M13a/M14 | Do'kon nomi/tilini yangilash | `settings.tenant` |
| 40c | `POST /tenant/tax-regimes` | M13a/M14 | Soliq rejimini o'zgartirish (keyingi oydan) | `settings.tenant` |
| 40d | `PUT /tenant/integrations/faktura-uz`, `/crpt` | M13a/M14 | Integratsiya kalitlari | `settings.tenant` |
| 40e | `DELETE /tenant/integrations/{provider}` | M13a/M14 | Integratsiyani uzish | `settings.tenant` |
| 41 | `GET /expenses` | M15 | Xarajatlar ro'yxati | `expenses.create` |
| 42 | `POST /expenses` | M15 | Xarajat qoralamasi yaratish | `expenses.create` |
| 43 | `POST /expenses/{id}/post` | M15 | Xarajatni o'tkazish | `expenses.create` (limit) |
| 44 | `POST /expenses/{id}/cancel` | M15 | Xarajatni bekor qilish | `expenses.create` |
| 45 | `GET /expense-categories` | M15 | Xarajat toifalari ro'yxati | `—` |
| 46 | `POST /expense-categories` | M15 | Yangi toifa qo'shish | `expenses.create` |
| 47 | `PATCH /expense-categories/{id}` | M15 | Toifani tahrirlash | `expenses.create` |
| 48 | `GET /recurring-expenses` | M15 | Takrorlanuvchi xarajat qoidalari | `expenses.create` |
| 49 | `POST /recurring-expenses` | M15 | Yangi takrorlanuvchi qoida | `expenses.create` |
| 50 | `PATCH /recurring-expenses/{id}` | M15 | Qoidani tahrirlash | `expenses.create` |
| 51 | `POST /recurring-expenses/{id}/confirm` | M15 | Eslatmani tasdiqlab xarajat yaratish | `expenses.create` |
| 52 | `GET /cash-movements` | M16 | Kassa pul harakati ro'yxati | `reports.sales.view` yoki `cash.count.shift` |
| 53 | `POST /cash-movements` | M16 | Pul qo'yish/olish yozish | `cash.deposit` / `cash.withdraw` (limit) |
| 54 | `POST /cash-movements/{id}/cancel` | M16 | Harakatni bekor qilish | `cash.deposit` / `cash.withdraw` |
| 55 | `GET /cash-registers/{id}/cash-history` | M16 | Smena/kassa bo'yicha naqd tarixi | `cash.count.shift` yoki `reports.sales.view` |
| 56 | `GET /billing/plan` | M17 | Joriy tarif va limitlar | `—` |
| 57 | `GET /billing/subscription` | M17 | Obuna holati (status, muddat) | `—` |
| 58 | `GET /billing/addons` | M17 | Qo'shimcha xizmatlar katalogi | `—` |
| 59 | `POST /billing/addons` | M17 | Qo'shimcha kassa qo'shish | `billing.manage` |
| 60 | `POST /billing/addons/{addon_code}/reduce` | M17 | Qo'shimchadan voz kechish | `billing.manage` |
| 61 | `POST /billing/checkout` | M17 | To'lov checkout yaratish (Click/Payme) | `billing.manage` |
| 62 | `GET /billing/payments` | M17 | To'lovlar tarixi | `billing.manage` |
| 63 | `POST /billing/webhooks/click` | M17 | Click webhook (bizning billing) | `—` (imzo tekshiruvi) |
| 64 | `POST /billing/webhooks/payme` | M17 | Payme webhook (bizning billing) | `—` (imzo tekshiruvi) |
| 65 | `GET /billing/invoices/{payment_id}` | M17 | To'lov hujjati (kvitansiya PDF) | `billing.manage` |
| 65a | `POST`/`GET /billing/export-my-data` | M17 | Ma'lumotlarni eksport qilish (D2, lokaut davrida SMS-OTP bilan ruxsat) — to'liq sxema `12-autentifikatsiya-oauth2.md` §16.5 | `—` (OTP, bir martalik token) |
| — | `/platform/*` (9 endpoint) | M17 | Platforma admin — **to'liq sxema `12-autentifikatsiya-oauth2.md` §18.1** | `platform.admin` |
| 66 | `POST /notifications/telegram/link-start` | M18 | Telegram ulash kodi generatsiya | `telegram.link` |
| 67 | `GET /notifications/telegram/status` | M18 | Ulanish holati | `telegram.link` |
| 68 | `DELETE /notifications/telegram/link` | M18 | Ulanishni uzish | `telegram.link` |
| 69 | `GET /notification-settings` | M18 | Ogohlantirish sozlamalari | `notifications.manage` |
| 70 | `PATCH /notification-settings` | M18 | Sozlamalarni yangilash | `notifications.manage` |
| 71 | `GET /notifications-log` | M18 | Yuborilgan xabarlar tarixi | `notifications.manage` |
| 72 | `POST /ai/chat` | AI-01 | AI chat (SSE stream) | `ai.chat.use` |
| 73 | `POST /ai/ocr/jobs` | AI-03 | Hujjat fotosini OCR tahliliga yuborish | `ai.ocr.use` |
| 74 | `GET /ai/ocr/jobs/{job_id}` | AI-03 | OCR natijasini olish | `ai.ocr.use` |
| 75 | `POST /ai/ocr/jobs/{job_id}/confirm` | AI-03 | Natijani tasdiqlab hujjat yaratish | `ai.ocr.use` |
| 76 | `POST /ai/vat-diffs/{diff_id}/explain` | AI-05 | Davlat hisoboti farqini tushuntirish | `tax.compare.review` |
| 77 | `POST /ai/debt-reminders/draft` | AI-06 | Qarz eslatma matni loyihasi | `ai.chat.use` |
| 78 | `POST /ai/debt-reminders/send` | AI-06 | Tasdiqlangan eslatmani yuborish | `debts.remind` |
| 79 | `GET /ai/usage` | AI | Joriy oy AI limiti sarfi | `ai.chat.use` |

---

## M10 — QQS

### 1. `GET /reports/vat-summary`

| | |
|---|---|
| Maqsad | Davr bo'yicha ichki QQS (yoki aylanma solig'i, tenant rejimiga qarab) hisob-kitobi — `vat_moves`dan agregatlangan: `output − input` (`02-provodka-qoidalari.md` §4.2). *(2026-10-15: qabul-6 A3-22 — yo'l `/vat/summary`dan `/reports/vat-summary`ga ko'chirildi, eksport kodi `#22`dagi `vat-summary` bilan bir xil bo'lishi uchun)* |
| Ruxsat | `tax.vat.view` |
| So'rov | `?period=2026-10` (majburiy, `YYYY-MM`), `?branch_id=` (ixtiyoriy) |
| Javob | `{period, regime: "vat"\|"turnover", output_vat, input_vat, net_vat, pending_credit_red_invoices, pending_credit_pct, turnover_base, turnover_rate_pct, turnover_amount}` — `regime` tenant joriy oyi uchun `tenant_tax_regimes`dan; `pending_credit_*` faqat `regime=vat` bo'lsa (BO-07, US-M10-03, qizil e-fakturalar) |
| Xatolar | `VALIDATION_ERROR` (noto'g'ri `period` format) |
| Idempotency-Key | Kerak emas (`GET`) |
| Offline | Ishlamaydi — faqat online (server tomonida hisoblanadi, M10 offline xatti-harakati bo'yicha) |
| Bog'langan | US-M10-01, US-M10-04; BO-07 |

### 2. `GET /vat-moves`

| | |
|---|---|
| Maqsad | `vat_moves` registri — qator darajasida (hujjat, asos, QQS summasi). *(2026-10-15: qabul-6 A3-22 — yo'l `/vat/moves`dan `/vat-moves`ga, kebab-case)* |
| Ruxsat | `tax.vat.view` |
| So'rov | Cursor pagination; filtr: `?kind=output\|input&period=2026-10&doc_type=sales\|goods_receipts\|returns\|supplier_returns&einvoice_id=` (`doc_type` qiymatlari — jadval nomlari, Q7; `returns`/`supplier_returns` qo'shildi, K3-06/US-M02-03) |
| Javob | `{items: [{id, kind, period, base_amount, vat_amount, doc_type, doc_id, einvoice_id, created_at}], next_cursor}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M10-01, US-M10-03; BO-07 |

### 3. `POST /state-reports`

| | |
|---|---|
| Maqsad | my.soliq.uz'dan qo'lda yuklab olingan davlat hisoboti faylini tizimga kiritish (`01-malumotlar-modeli.md` §9) |
| Ruxsat | `tax.compare.review` |
| So'rov | `multipart/form-data`: `file` (PDF/Excel, ≤5 MB), `tax_type` (`vat`\|`turnover`, majburiy), `period` (`YYYY-MM`, majburiy), `published_at` (sana, davlat hisoboti e'lon qilingan kun, majburiy — 5 kunlik hisoblagich shundan boshlanadi) |
| Javob | `201 {id, tax_type, period, status: "uploaded", deadline_at}` — `deadline_at = min(published_at+5 kalendar kun, qonuniy topshirish muddati)` (US-M10-02) |
| Xatolar | `VALIDATION_ERROR`, `FILE_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE` |
| Idempotency-Key | Majburiy |
| Offline | Ishlamaydi |
| Bog'langan | US-M10-02, US-M10-04; BO-10 |

### 4. `POST /state-reports/{id}/compare`

| | |
|---|---|
| Maqsad | Ichki hisob (`vat_moves` yig'indisi) bilan yuklangan davlat hisobotini solishtirishni ishga tushirish/qayta ishga tushirish |
| Ruxsat | `tax.compare.review` |
| So'rov | Tana yo'q |
| Javob | `{id, status: "match"\|"diff_found", diff_count, state_amount, our_amount, diff_amount}` |
| Xatolar | `DOC_INVALID_STATE` (status allaqachon `correction_sent`/`auto_accepted` bo'lsa qayta solishtirish rad etiladi; `DOC_NOT_DRAFT` qayta nomlandi, A3-15) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M10-02; BO-10 |

### 5. `GET /state-reports`

| | |
|---|---|
| Maqsad | Davlat hisobotlari ro'yxati |
| Ruxsat | `tax.vat.view` |
| So'rov | Cursor; filtr `?tax_type=&period=&status=` |
| Javob | `{items: [{id, tax_type, period, status, deadline_at, diff_amount}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Faqat oxirgi keshlangan ro'yxat (BO-09 kabi) |
| Bog'langan | US-M10-02; BO-10 |

### 6. `GET /state-reports/{id}`

| | |
|---|---|
| Maqsad | Bitta hisobot tafsiloti + holat tarixi |
| Ruxsat | `tax.vat.view` |
| So'rov | — |
| Javob | `{id, tax_type, period, status, published_at, deadline_at, state_amount, our_amount, diff_amount, file_url, correction_sent_at}` |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish (kesh) |
| Bog'langan | US-M10-02; BO-10 |

### 7. `GET /state-reports/{id}/diffs`

| | |
|---|---|
| Maqsad | Farq qatorlari (`state_report_diffs`) — ko'rsatkich darajasida yoki (agar hujjat darajasida ma'lumot kelsa) hujjat darajasida |
| Ruxsat | `tax.compare.review` |
| So'rov | Cursor; `?resolved=true\|false` |
| Javob | `{items: [{id, indicator, state_value, our_value, diff, explanation, resolved}], next_cursor}` — `explanation` AI-05 orqali to'ldiriladi (`POST /ai/vat-diffs/{diff_id}/explain`, bo'sh bo'lishi mumkin) |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M10-02, US-M10-03; BO-10 |

### 8. `POST /state-reports/{id}/correction`

| | |
|---|---|
| Maqsad | Farqga tuzatish/e'tiroz yuborish (E-IMZO bilan imzolangan) |
| Ruxsat | `tax.correction.submit` (**yakuniy tasdiq — faqat Egasi**, `05-xavfsizlik-va-audit.md` §2.2) |
| So'rov | `{signed_document: string (E-IMZO imzo, base64), comment: string (ixtiyoriy)}` |
| Javob | `200 {id, status: "correction_sent", correction_sent_at}` |
| Xatolar | `VALIDATION_ERROR`, `EIMZO_SIGN_FAILED` (imzo yaroqsiz; `EINVOICE_SIGN_FAILED` qayta nomlandi — e-faktura va davlat hisoboti tuzatishida bir xil kod, A3-15), `DOC_INVALID_STATE` (allaqachon yuborilgan) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M10-02; BO-10; audit: `tax.correction.submit` (`05-xavfsizlik-va-audit.md` §6.1) |

---

## M11 — Buxgalteriya

### 9. `GET /ledger-entries`

| | |
|---|---|
| Maqsad | Buxgalteriya jurnali (`ledger_entries`) — hisob rejasi bo'yicha filtr (`02-provodka-qoidalari.md` §1) |
| Ruxsat | `accounting.post` |
| So'rov | Cursor; filtr `?account_dt=&account_kt=&entry_date__gte=&entry_date__lte=&branch_id=&doc_type=` (`doc_date__*` → `entry_date__*`, ustun nomi bilan bir xil — Q1, A3-05; `branch_id` — DB-12 ustuni) |
| Javob | `{items: [{id, entry_date, account_dt, account_kt, amount, branch_id, doc_type, doc_id, analytics, reversal_of_id}], next_cursor}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish (kesh) |
| Bog'langan | US-M11-01; BO-08 |

### 10. `POST /ledger-adjustments`

> **Hujjat jadvali qo'shildi** (DB-12, A3-04) — `ledger_entries.doc_type/doc_id NOT NULL` hech narsaga ishora qilmasligi uchun `POST /ledger-entries/adjustments` o'rniga mustaqil hujjat `ledger_adjustments` (`doc_sequences` kodi `BX`). **Bir bosqichli hujjat** (`13-api-katalog-0-umumiy.md` §9, A0-03) — darhol `status="posted"` qaytaradi, `draft` bosqichi yo'q.

| | |
|---|---|
| Maqsad | Yopilgan davrdagi xatoni **joriy ochiq davrda** tuzatuvchi qo'lda yozuv (append-only, `02-provodka-qoidalari.md` §5.1) |
| Ruxsat | `accounting.post` |
| So'rov | `{doc_date (joriy ochiq davrda bo'lishi shart — `entry_date` emas), account_dt, account_kt, amount, comment (majburiy), correction_of_period ("YYYY-MM", ixtiyoriy — qaysi yopilgan davrga tegishli)}` |
| Javob | `201 {id, status: "posted", doc_date, account_dt, account_kt, amount, correction_of_period}` |
| Xatolar | `VALIDATION_ERROR`, `PERIOD_CLOSED` (`doc_date` yopilgan davrda bo'lsa) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08; audit: `ledger_entries.manual_adjustment` majburiy |

### 10a. `POST /ledger-adjustments/{id}/cancel`

| | |
|---|---|
| Maqsad | Tuzatuvchi yozuvni bekor qilish (storno — alohida teskari hujjat yo'q, `00-qarorlar.md` #6) |
| Ruxsat | `accounting.post` |
| So'rov | `{reason: string (majburiy)}` |
| Javob | `200 {id, status: "cancelled", cancelled_at}` |
| Xatolar | `DOC_ALREADY_CANCELLED`, `PERIOD_CLOSED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08; audit majburiy |

### 10b. `GET /ledger-adjustments`

| | |
|---|---|
| Maqsad | Qo'lda kiritilgan tuzatuvchi yozuvlar ro'yxati |
| Ruxsat | `accounting.post` |
| So'rov | Cursor; filtr `?doc_date__gte=&doc_date__lte=&status=` |
| Javob | `{items: [{id, doc_date, account_dt, account_kt, amount, correction_of_period, status, comment}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08 |

### 11. `GET /reports/trial-balance`

| | |
|---|---|
| Maqsad | Aylanma-saldo vedomosti (oborot-saldo) — har hisob bo'yicha boshlang'ich/aylanma/yakuniy qoldiq |
| Ruxsat | `reports.finance.view` |
| So'rov | `?period=2026-10&branch_id=` (`branch_id` bo'lmasa — konsolidatsiya, `02-provodka-qoidalari.md` §5.4) |
| Javob | `{period, rows: [{account, opening_balance, debit_turnover, credit_turnover, closing_balance}]}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat oxirgi keshlangan hisobot |
| Bog'langan | US-M11-02; BO-08, BO-09 |

### 12. `GET /reports/profit-and-loss`

| | |
|---|---|
| Maqsad | Foyda-zarar hisoboti (daromad − COGS − xarajat, M15 bilan birga, US-M15-03) |
| Ruxsat | `reports.finance.view` |
| So'rov | `?period=2026-10&branch_id=` |
| Javob | `{period, revenue, returns, discounts, cogs, gross_profit, expenses_by_category: [{category, amount}], net_profit}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M11-03, US-M15-03; BO-02, BO-09 |

### 13. `GET /reports/balance-sheet`

| | |
|---|---|
| Maqsad | Balans hisoboti (aktiv/passiv/kapital, `02-provodka-qoidalari.md` §1 hisoblar bo'yicha) |
| Ruxsat | `reports.finance.view` |
| So'rov | `?as_of=2026-10-31&branch_id=` |
| Javob | `{as_of, assets: [{account, amount}], liabilities: [...], equity: [...], total_assets, total_liabilities_and_equity}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M11-02; BO-09 |

### 14. `GET /period-closings`

| | |
|---|---|
| Maqsad | Yopilgan davrlar ro'yxati |
| Ruxsat | `accounting.post` |
| So'rov | Cursor |
| Javob | `{items: [{period, closed_at, closed_by}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M11-02; BO-08 |

### 15. `POST /period-closings`

| | |
|---|---|
| Maqsad | Davrni yopish (`period_closings` yozuvi, 02-provodka-qoidalari.md §5.1) |
| Ruxsat | `accounting.period.close` |
| So'rov | `{period: "YYYY-MM"}` |
| Javob | `201 {period, closed_at, closed_by}` |
| Xatolar | `PERIOD_ALREADY_CLOSED` (davr allaqachon yopilgan — `VALIDATION_ERROR` o'rniga, A3-16), `PERIOD_CLOSE_NOT_READY` (16-endpointga qarang: `recost_jobs` tugallanmagan yoki `fiscal_receipts.status IN (pending,sent,failed)` qolgan) — davr yopilgach **qayta ochilmaydi** (00-qarorlar #23/#15); keyingi tuzatish faqat `POST /ledger-adjustments` (10-endpoint) bilan joriy ochiq davrda |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08; audit majburiy |

### 16. `GET /period-closings/{period}/readiness`

| | |
|---|---|
| Maqsad | Davrni yopishdan oldin tekshiruv (`09-backend-arxitekturasi.md` §2.4) |
| Ruxsat | `accounting.post` |
| So'rov | — (`period` path parametri `YYYY-MM`) |
| Javob | `{period, ready: bool, pending_recost_jobs: int, pending_fiscal_receipts: int, blockers: ["recost_pending"\|"fiscal_pending"]}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08 |

---

## M12 — Hisobotlar

### 17. `GET /reports/dashboard`

| | |
|---|---|
| Maqsad | Egasi/Menejer dashboard (BO-02): savdo grafigi, top mahsulot, kassa holati, ogohlantirishlar |
| Ruxsat | `reports.sales.view` |
| So'rov | `?period=today\|week\|month&branch_id=` |
| Javob | `{period, total_sales, receipt_count, avg_receipt, net_profit, by_branch: [{branch_id, sales, profit}], top_products: [{product_id, name, qty}], alerts: [{type, message_key, severity}]}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan ma'lumot, `"N daqiqa oldin"` belgisi bilan (BO-02) |
| Bog'langan | US-M12-01; BO-02 |

### 18. `GET /reports/sales`

| | |
|---|---|
| Maqsad | Savdo hisoboti — filial/davr bo'yicha jami savdo, chek soni, o'rtacha chek |
| Ruxsat | `reports.sales.view` |
| So'rov | `?date_from=&date_to=&branch_id=&group_by=day\|branch\|cashier` |
| Javob | `{rows: [{group_key, total_sales, receipt_count, avg_receipt}]}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M12-01; BO-02, BO-09 |

### 19. `GET /reports/top-products`

| | |
|---|---|
| Maqsad | Eng ko'p/kam sotiladigan tovarlar (US-M12-02) |
| Ruxsat | `reports.sales.view` |
| So'rov | `?date_from=&date_to=&branch_id=&order=top\|bottom&limit=20` |
| Javob | `{items: [{product_id, name, qty_sold, revenue}]}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M12-02; BO-09 |

### 20. `GET /reports/stock`

| | |
|---|---|
| Maqsad | Qoldiq hisoboti (ombor/filial bo'yicha, minimal daraja belgisi) |
| Ruxsat | `stock.view` |
| So'rov | `?branch_id=&warehouse_id=&below_min_only=true` |
| Javob | `{items: [{product_id, name, qty, value, below_min: bool}]}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish, IndexedDB'dagi oxirgi nusxa (BO-03) |
| Bog'langan | US-M12-01; BO-03, BO-09 |

### 21. `GET /reports/debts-aging`

| | |
|---|---|
| Maqsad | Qarzdorlik "yosh" guruhlari (0-30 / 31-60 / 60+ kun), BO-06/BO-09 uchun manba. **Yagona/kanonik endpoint** — `13-api-katalog-1-kassa.md` §12.8dagi `GET /reports/debt-aging` o'chirildi, shu yerga havola qilinadi (K1-05/A1-26); BO-04 "Men qarzdorman" tabi ham `direction=payable` bilan shu yerdan foydalanadi (E-07) |
| Ruxsat | `reports.finance.view` **yoki** `debts.approve` (A3-08) |
| So'rov | `?direction=receivable\|payable&as_of=2026-10-15&branch_id=&limit_exceeded_offline=` |
| Javob | `{rows: [{counterparty_id, name, balance, days_overdue, overdue_since, bucket: "0-30"\|"31-60"\|"60+", doubtful_flag: bool, limit_exceeded_offline: bool}]}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish |
| Bog'langan | US-M12-01; BO-06, BO-09 |

### 22. `POST /reports/{report-kod}/export`

| | |
|---|---|
| Maqsad | Yuqoridagi hisobotlarning (shuningdek M10'dagi) Excel/PDF eksporti — asinxron job (`13-api-katalog-0-umumiy.md` §13) |
| Ruxsat | `reports.export` |
| So'rov parametrlari (path) | `report-kod` ∈ `{sales, top-products, stock, debts-aging, trial-balance, profit-and-loss, balance-sheet, vat-summary, ledger-entries, cash-history, state-report-diffs, vat-moves}` (so'nggi to'rttasi — BO-08/BO-09/BO-10 eksporti, US-M12-03/US-M16-03, K3-06) |
| So'rov (tana) | `{format: "xlsx"\|"pdf", filters: {...} (report-kodga mos query parametrlar bilan bir xil shakl)}` |
| Javob | `202 {job_id, status: "queued"}` |
| Xatolar | `VALIDATION_ERROR` (noma'lum `report-kod`) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M12-03; BO-09 |

### 23. `GET /reports/export-jobs/{job_id}`

| | |
|---|---|
| Maqsad | Eksport job holati (poll) |
| Ruxsat | `reports.export` |
| So'rov | — |
| Javob | `{job_id, status: "queued"\|"running"\|"done"\|"failed", progress_pct, file_url, error_code}` |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M12-03; BO-09 |

---

## M13 — Huquqlar

> Foydalanuvchi (xodim) CRUD, taklif/bloklash/parol-PIN tiklash, sessiya/qurilma boshqaruvi — **`12-autentifikatsiya-oauth2.md` §18.2'da allaqachon to'liq**: `POST /admin/users`, `PATCH /admin/users/{id}`, `POST /admin/users/{id}/reset-pin`, `POST /admin/users/{id}/reset-password`, `POST /admin/users/{id}/revoke-sessions`, `GET /admin/users/{id}/sessions`, `GET /admin/users/{id}/devices`. Bu fayl ularni takrorlamaydi. Quyida faqat **rol/ruxsat/limit** boshqaruvi (shu hujjatdagi `05-xavfsizlik-va-audit.md` §2.1–2.2 katalogiga mos).

### 24. `GET /roles`

| | |
|---|---|
| Maqsad | Rollar ro'yxati (5 standart + tenant maxsus rollari) |
| Ruxsat | `settings.users` |
| So'rov | Page pagination |
| Javob | `{items: [{id, name, is_system, version}], total, page, size}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan ro'yxat (huquqlar faqat online o'zgaradi, `02-modullar-talablari.md` M13) |
| Bog'langan | US-M13-01, US-M13-02; BO-11 |

### 25. `POST /roles`

| | |
|---|---|
| Maqsad | Yangi maxsus rol yaratish |
| Ruxsat | `settings.users` |
| So'rov | `{name: string (majburiy, 1-50 belgi)}` |
| Javob | `201 {id, name, is_system: false, version: 1}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M13-01; BO-11 |

### 26. `PATCH /roles/{id}`

| | |
|---|---|
| Maqsad | Maxsus rol nomini tahrirlash (`is_system=true` rollar — faqat ruxsat/limit, 28-endpoint) |
| Ruxsat | `settings.users` |
| So'rov | `{name: string, version: int (majburiy)}` |
| Javob | `200 {id, name, version}` |
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT`, `409 {code:"SYSTEM_ROLE_READONLY"}` (`is_system=true` bo'lsa nom o'zgartirish rad etiladi; `DOC_NOT_DRAFT` qo'shimcha kod sifatida ishlatilmaydi — faqat shu bitta kod, A3-17) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M13-01; BO-11 |

### 27. `GET /roles/{id}/permissions`

| | |
|---|---|
| Maqsad | Rolning joriy ruxsat kodlari va limitlari (`role_permissions`) |
| Ruxsat | `settings.users` |
| So'rov | — |
| Javob | `{role_id, permissions: [{code, limit_value}]}` |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan (huquq tekshiruvi uchun qurilmada keshlanadi, `04-offline-sync.md` §2) |
| Bog'langan | US-M13-03; BO-11 |

### 28. `PUT /roles/{id}/permissions`

| | |
|---|---|
| Maqsad | Rolning to'liq ruxsat/limit to'plamini almashtirish (standart limitlar — `05-xavfsizlik-va-audit.md` §2.3) |
| Ruxsat | `settings.users` |
| So'rov | `{permissions: [{code: string (kod — `05-xavfsizlik-va-audit.md` §2.1 ro'yxatidan), limit_value: string\|null (pul/foiz, kod `discount.give`/`returns.approve`/`cash.withdraw` kabi limitli kodlarda)}]}` |
| Javob | `200 {role_id, permissions: [...]}` |
| Xatolar | `VALIDATION_ERROR` (noma'lum kod yoki limit talab qilinmaydigan kodga limit berilsa) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M13-03; BO-11; audit: huquq/limit o'zgarishi majburiy (`05-xavfsizlik-va-audit.md` §6.1) |

### 29. `GET /permissions-catalog`

| | |
|---|---|
| Maqsad | To'liq ruxsat kodlari katalogi (statik, kod ichidan — `01-malumotlar-modeli.md` §3: "permissions (kod ichida, jadval emas)") |
| Ruxsat | `settings.users` |
| So'rov | — |
| Javob | `{items: [{code, module, description, requires_limit: bool}]}` — `05-xavfsizlik-va-audit.md` §2.1 bilan bir xil ro'yxat |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Statik, frontend bundle'da keshlanishi mumkin |
| Bog'langan | US-M13-03; BO-11 |

---

## M14 — Filiallar

### 30. `GET /branches`

| | |
|---|---|
| Maqsad | Filiallar ro'yxati (`memberships.branch_ids` bo'yicha cheklangan) |
| Ruxsat | `—` (auth yetarli; natija `branch_ids` bo'yicha filtrlanadi) |
| So'rov | Page pagination |
| Javob | `{items: [{id, name, code, address, is_default, settlement_category, activity_type, version}], total, page, size}` (`code` — DB-02/M-05) |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan (`GET /sync/pull?scope=catalog`) |
| Bog'langan | US-M14-01; BO-12 |

### 31. `POST /branches`

| | |
|---|---|
| Maqsad | Yangi filial yaratish (US-M14-03) — avtomatik 1 ombor + sozlamalar bo'yicha kassa talabi |
| Ruxsat | `settings.branches` |
| So'rov | `{name: string (majburiy), address: string, code: string (ixtiyoriy — bo'sh bo'lsa server keyingi bo'sh ikki xonali raqamni beradi, DB-02/A3-18), settlement_category: "city_100k_plus"\|"other"\|"remote_mountain" (standart: `city_100k_plus`, US-M14-04), activity_type: "retail"\|"other"}` |
| Javob | `201 {id, name, address, code, settlement_category, activity_type, version: 1}` — birga `warehouses` yozuvi avtomatik yaratiladi (MVP: 1 ombor/filial); `code` hujjat raqamidagi filial kodi (`01-malumotlar-modeli.md` M-05) |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M14-03, US-M14-04; BO-12 |

### 32. `GET /branches/{id}`

| | |
|---|---|
| Maqsad | Filial tafsiloti + konsolidatsiyalangan qisqa hisob (savdo/qoldiq) |
| Ruxsat | `—` (branch scope tekshiradi) |
| So'rov | — |
| Javob | `{id, name, address, is_default, settlement_category, activity_type, version, today_sales, stock_value}` |
| Xatolar | `NOT_FOUND`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi kesh |
| Bog'langan | US-M14-01; BO-12 |

### 33. `PATCH /branches/{id}`

| | |
|---|---|
| Maqsad | Filialni tahrirlash (nom/manzil/toifa) |
| Ruxsat | `settings.branches` |
| So'rov | `{name?, address?, settlement_category?, activity_type?, version: int (majburiy)}` — `settlement_category` o'zgarsa yangi `branch_tax_settings` qatori avtomatik yaratiladi (`valid_from` = joriy oyning 1-sanasi, US-M14-04) |
| Javob | `200 {id, name, address, settlement_category, activity_type, version}` |
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M14-04; BO-12 |

### 34. `GET /branches/{id}/tax-settings`

| | |
|---|---|
| Maqsad | Aholi punkti toifasi/stavka tarixi (`branch_tax_settings`) |
| Ruxsat | `—` (branch scope) |
| So'rov | Page pagination |
| Javob | `{items: [{valid_from, settlement_category, activity_type}], total, page, size}` |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi kesh |
| Bog'langan | US-M14-04; BO-12 |

### 35. `POST /branches/{id}/tax-settings`

| | |
|---|---|
| Maqsad | Yangi toifa qiymatini qo'lda qo'shish (masalan kelajak sana bilan rejalashtirish) |
| Ruxsat | `settings.branches` |
| So'rov | `{valid_from: date (majburiy, o'tgan oyga yozib bo'lmaydi), settlement_category, activity_type}` |
| Javob | `201 {branch_id, valid_from, settlement_category, activity_type}` |
| Xatolar | `VALIDATION_ERROR` (`valid_from` o'tgan davrda) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M14-04; BO-12 |

### 36. `POST /branches/{id}/copy-pricing`

| | |
|---|---|
| Maqsad | Narx/chegirma siyosatini manba filialdan maqsad filialga nusxalash (US-M14-02) |
| Ruxsat | `prices.edit` |
| So'rov (path) | `{id}` — maqsad filial |
| So'rov (tana) | `{source_branch_id: UUID (majburiy), include: ["prices", "discount_rules"] (kamida bitta)}` |
| Javob | `200 {copied_prices: int, copied_discount_rules: int}` |
| Xatolar | `VALIDATION_ERROR`, `BRANCH_SCOPE_DENIED` (manba filialga kirish yo'q) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M14-02; BO-12 |

### 37. `GET /warehouses`

| | |
|---|---|
| Maqsad | Omborlar ro'yxati (filial bo'yicha) |
| Ruxsat | `—` (branch scope) |
| So'rov | `?branch_id=` |
| Javob | `{items: [{id, branch_id, name, type}]}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan (catalog scope) |
| Bog'langan | US-M14-01; BO-03, BO-12 |

### 38. `GET /cash-registers`

| | |
|---|---|
| Maqsad | Kassalar ro'yxati (filial bo'yicha, obuna limiti bilan bog'liq — M17) |
| Ruxsat | `—` (branch scope) |
| So'rov | `?branch_id=&include_archived=false` |
| Javob | `{items: [{id, branch_id, name, kind, fiscal_module_id, ofd_status, archived_at}]}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan |
| Bog'langan | US-M14-03; BO-12, BO-19 |

### 39. `POST /cash-registers`

| | |
|---|---|
| Maqsad | Yangi kassa qo'shish — faol kassalar soni `tenant_addons` (`extra_register`) limitidan oshmasligi tekshiriladi (M17) |
| Ruxsat | `cash_register.manage` |
| So'rov | `{branch_id: UUID (majburiy), name: string (majburiy), kind: "web"\|"android"}` |
| Javob | `201 {id, branch_id, name, kind, ofd_status: "pending"}` |
| Xatolar | `VALIDATION_ERROR`, `ADDON_REQUIRED` (faol kassa soni limitdan oshadi — `tenant_addons.extra_register` sotib olinmagan) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M14-03, US-M17-02; BO-12 |

### 40. `PATCH /cash-registers/{id}`

| | |
|---|---|
| Maqsad | Kassani tahrirlash (nomi) |
| Ruxsat | `cash_register.manage` |
| So'rov | `{name?: string, version: int (majburiy)}` — `version` endi majburiy (DDL'da yo'q edi); arxivlash **alohida** endpoint (13-2'dagi naqsh, A3-11): `POST /cash-registers/{id}/archive` (tana `{}`, M17 chekka holat — qo'shimcha kassa sonini kamaytirish) |
| Javob | `200 {id, name, version}` |
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT`, `409 {code:"RESOURCE_ARCHIVED"}` (allaqachon arxivlangan — `DOC_ALREADY_CANCELLED` o'rniga, 13-0 §15.2) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M17-02 (chekka holat — qo'shimcha kassa kamaytirish); BO-12, BO-19 |

---

## M13a/M14 — Tenant sozlamalari va integratsiya kalitlari

> **Yangi bo'lim** (BO-14 — ilgari katalogda umuman yo'q edi, K3-01). Ruxsat — hammasi `settings.tenant` (X-01/P-06, yangi kod, **faqat Egasi**).

### 40a. `GET /tenant/settings`

| | |
|---|---|
| Maqsad | Do'kon sozlamalari + integratsiya holati umumiy ko'rinishi |
| Ruxsat | `settings.tenant` |
| So'rov | — |
| Javob | `{store_name, locale, tax_regime: {current, history: [...]}, integrations: {ofd: {status}, faktura_uz: {status, connected_at}, crpt: {status, key_last4}}, version}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan |
| Bog'langan | BO-14 |

### 40b. `PATCH /tenant/settings`

| | |
|---|---|
| Maqsad | Do'kon nomi/tilini yangilash; soliq rejimi o'zgarishi — alohida endpoint (40c) orqali |
| Ruxsat | `settings.tenant` |
| So'rov | `{store_name?: string, locale?: string, version: int (majburiy)}` |
| Javob | `200 {store_name, locale, version}` |
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; audit majburiy |

### 40c. `POST /tenant/tax-regimes`

| | |
|---|---|
| Maqsad | Soliq rejimini (QQS/aylanma) o'zgartirish — faqat keyingi oy 1-sanasidan kuchga kiradi |
| Ruxsat | `settings.tenant` |
| So'rov | `{regime: "vat"\|"turnover", valid_from: date (keyingi oy 1-sanasi)}` |
| Javob | `201 {regime, valid_from}` |
| Xatolar | `VALIDATION_ERROR` (`valid_from` noto'g'ri sana) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; audit majburiy |

### 40d. `PUT /tenant/integrations/faktura-uz` · `PUT /tenant/integrations/crpt`

| | |
|---|---|
| Maqsad | Integratsiya kalitlarini (Faktura.uz login/parol, CRPT API kalit) kiritish/yangilash |
| Ruxsat | `settings.tenant` |
| So'rov | `faktura-uz`: `{login, password}`; `crpt`: `{api_key}` — ikkisi ham `tenant_secrets`da shifrlangan saqlanadi (KMS/`pgcrypto`), javobda hech qachon qaytmaydi |
| Javob | `200 {status: "connected"}` — server token olib tekshiradi |
| Xatolar | `422 {code:"EINVOICE_PROVIDER_UNAVAILABLE"}` (faktura-uz) / `503 {code:"MARKING_VERIFY_UNAVAILABLE"}` (crpt), `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; audit majburiy |

### 40e. `DELETE /tenant/integrations/{provider}`

| | |
|---|---|
| Maqsad | Integratsiyani uzish (`provider` ∈ `faktura-uz`, `crpt`) |
| Ruxsat | `settings.tenant` |
| So'rov | — |
| Javob | `204` |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; audit majburiy |

---

## M15 — Xarajatlar

### 41. `GET /expenses`

| | |
|---|---|
| Maqsad | Xarajatlar ro'yxati |
| Ruxsat | `expenses.create` |
| So'rov | Cursor; filtr `?category_id=&branch_id=&doc_date__gte=&doc_date__lte=&status=` |
| Javob | `{items: [{id, category_id, amount, source, cash_register_id, shift_id, attachment_id, status, doc_date}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish (BO-17) |
| Bog'langan | US-M15-01; BO-17 |

### 42. `POST /expenses`

| | |
|---|---|
| Maqsad | Xarajat qoralamasi yaratish (10 soniyada, US-M15-01) |
| Ruxsat | `expenses.create` |
| So'rov | `{doc_date: date (majburiy, standart bugun — A3-07), branch_id: UUID (majburiy, standart `X-Branch-Id`), category_id: UUID (majburiy), amount: string (majburiy, >0), source: "cash"\|"bank"\|"card" (majburiy), cash_register_id: UUID (source=cash bo'lsa majburiy), shift_id: UUID (source=cash bo'lsa majburiy), attachment_id: UUID (ixtiyoriy), comment: string (ixtiyoriy), recurring_rule_id: UUID (ixtiyoriy)}` |
| Javob | `201 {id, status: "draft", doc_date, amount, category_id}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Kassa naqdi (`source="cash"`) bo'lsa — sync voqeasi `expense.created` orqali offline yoziladi (`04-offline-sync.md` §2 enum, S-01): payload = shu tana + `{id, doc_date, cash_register_id, shift_id}`, server `ExpensePostingService` bilan `draft` yaratmasdan **darhol** o'tkazadi; boshqa manba — online |
| Bog'langan | US-M15-01; BO-17 |

### 43. `POST /expenses/{id}/post`

| | |
|---|---|
| Maqsad | Xarajatni o'tkazish — `ExpensePostingService` (`02-provodka-qoidalari.md` §2.17): `ledger_entries` (9410/9420) + (agar `source=cash`) `cash_moves` |
| Ruxsat | `expenses.create` (limit) — katta summa `expenses.approve` talab qiladi (`05-xavfsizlik-va-audit.md` §2.1) |
| So'rov | Tana yo'q |
| Javob | `200 {id, status: "posted", posted_at}` yoki limitdan oshsa `202 {status: "draft", approval_request_id}` (`APPROVAL_REQUIRED`, Q3 — hujjat `draft`da qoladi, `pending_approval`ga o'tmaydi; `price_changes`dan farqli bu umumiy qoida) |
| Xatolar | `DOC_NOT_DRAFT`, `EXPENSE_LIMIT_EXCEEDED` (`EXPENSE_APPROVAL_REQUIRED` qayta nomlandi — oila nomlashi bilan izchil, A3-06), `PERIOD_CLOSED` |
| Idempotency-Key | Majburiy |
| Offline | `source=cash` bo'lsa offline postinglanadi, sinxronlashda serverga tushadi |
| Bog'langan | US-M15-01, US-M15-03; BO-17 |

### 44. `POST /expenses/{id}/cancel`

| | |
|---|---|
| Maqsad | Xarajatni bekor qilish (teskari yozuv, `02-provodka-qoidalari.md` §5.2) |
| Ruxsat | `expenses.create` |
| So'rov | `{reason: string (majburiy)}` |
| Javob | `200 {id, status: "cancelled", cancelled_at}` |
| Xatolar | `DOC_ALREADY_CANCELLED`, `PERIOD_CLOSED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q (bekor qilish faqat online) |
| Bog'langan | M15 chekka holat ("xarajat bekor qilinsa — teskari yozuv"); BO-17; audit majburiy |

### 45. `GET /expense-categories`

| | |
|---|---|
| Maqsad | Xarajat toifalari ro'yxati (standart: Ijara, Kommunal, Ish haqi, Transport, Soliq va yig'imlar, Ta'mirlash, Boshqa) |
| Ruxsat | `—` |
| So'rov | — |
| Javob | `{items: [{id, name, archived_at}]}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan (catalog scope) |
| Bog'langan | US-M15-01; BO-17 |

### 46. `POST /expense-categories`

| | |
|---|---|
| Maqsad | Yangi toifa qo'shish |
| Ruxsat | `expenses.create` |
| So'rov | `{name: string (majburiy, 1-50 belgi)}` |
| Javob | `201 {id, name}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M15-01; BO-17 |

### 47. `PATCH /expense-categories/{id}`

| | |
|---|---|
| Maqsad | Toifani tahrirlash/arxivlash |
| Ruxsat | `expenses.create` |
| So'rov | `{name?: string, archived?: bool, version: int (majburiy)}` |
| Javob | `200 {id, name, archived_at, version}` |
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M15-01; BO-17 |

### 48. `GET /recurring-expenses`

| | |
|---|---|
| Maqsad | Takrorlanuvchi xarajat qoidalari (US-M15-02, oylik ijara va h.k.) |
| Ruxsat | `expenses.create` |
| So'rov | Page pagination; `branch_id` — `X-Branch-Id` header orqali (A3-09) |
| Javob | `{items: [{id, name, category_id, amount, day_of_month, period, source, cash_register_id, next_due_date, last_triggered_at, is_active}], total, page, size}` (`active`→`is_active`, `next_due_at`→`next_due_date`, DB-17/A3-09) |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish |
| Bog'langan | US-M15-02; BO-17 |

### 49. `POST /recurring-expenses`

| | |
|---|---|
| Maqsad | Yangi takrorlanuvchi qoida yaratish |
| Ruxsat | `expenses.create` |
| So'rov | `{name?: string (bo'sh bo'lsa UI toifa nomini ko'rsatadi), category_id: UUID (majburiy), amount: string (majburiy), day_of_month: int 1-28 (majburiy), period: "month"\|"quarter"\|"year" (majburiy), source: "cash"\|"bank"\|"card" (majburiy), cash_register_id?: UUID (`source="cash"` bo'lsa majburiy)}` |
| Javob | `201 {id, name, category_id, amount, day_of_month, period, next_due_date, is_active: true}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M15-02; BO-17 |

### 50. `PATCH /recurring-expenses/{id}`

| | |
|---|---|
| Maqsad | Qoidani tahrirlash/o'chirish (faollikni o'chirish) |
| Ruxsat | `expenses.create` |
| So'rov | `{amount?, day_of_month?, is_active?: bool, version: int (majburiy)}` |
| Javob | `200 {id, amount, day_of_month, is_active, version}` |
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M15-02; BO-17 |

### 51. `POST /recurring-expenses/{id}/confirm`

| | |
|---|---|
| Maqsad | Eslatma kelganda ("Ijara to'lash vaqti") bir bosishda tasdiqlab tegishli `expenses` qoralamasini yaratish+o'tkazish (US-M15-02 — **avtomatik to'lanmaydi**, har doim qo'lda tasdiq) |
| Ruxsat | `expenses.create` |
| So'rov | Tana yo'q (yoki `{amount_override?: string}` — bir martalik summa farqi bo'lsa) |
| Javob | `201 {expense_id, status: "posted"}` |
| Xatolar | `VALIDATION_ERROR`, `SHIFT_NOT_OPEN` (`source="cash"` bo'lgan qoidada ochiq smena bo'lmasa, A3-09) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q (eslatma M18 orqali keladi, tasdiq — online back-office) |
| Bog'langan | US-M15-02; BO-17, M18 eslatma |

---

## M16 — Kassa pul harakati

### 52. `GET /cash-movements`

| | |
|---|---|
| Maqsad | Kassa pul harakati ro'yxati (`cash_movements`) — ruxsat/ta'rif **yagona manba shu yerda**, `13-api-katalog-1-kassa.md` §13.2 shu yerga havola qiladi (K3-02) |
| Ruxsat | `reports.sales.view` **yoki** `cash.count.shift` (`cash.deposit` noto'g'ri edi — Omborchi/Buxgalter ko'ra olmasdi, kassir esa barcha kassalarni ko'rishi kerak, A1-27/A3-20) |
| So'rov | Cursor; filtr `?cash_register_id=&shift_id=&direction=in\|out&reason=` |
| Javob | `{items: [{id, cash_register_id, shift_id, direction, amount, reason, created_by, doc_date}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | To'liq offline ishlaydi (append-only jurnal, `04-offline-sync.md`) |
| Bog'langan | US-M16-01, US-M16-03; BO-11 (xodim audit), POS-15 |

### 53. `POST /cash-movements`

| | |
|---|---|
| Maqsad | Pul qo'yish/olish yozish (US-M16-01). **POS'dan — faqat `cash_movement.created` sync voqeasi; bu REST — back-office (masalan inkasso yozish)** (K3-02) |
| Ruxsat | `direction=in` → `cash.deposit`; `direction=out` → `cash.withdraw` (limit, standart 50 000 so'm, `05-xavfsizlik-va-audit.md` §2.3) |
| So'rov | `{cash_register_id: UUID (majburiy), shift_id: UUID (majburiy, faol smena), direction: "in"\|"out" (majburiy), amount: string (majburiy, >0), reason: "collection"\|"deposit"\|"owner_withdrawal"\|"other" (majburiy), comment: string (`reason="other"`da majburiy, A3-21), doc_date: date (majburiy)}` |
| Javob | `201 {id, status: "posted", amount}` yoki limitdan oshsa `202 {status: "draft", approval_request_id}` (`APPROVAL_REQUIRED`, Q3 — `kind="cash_withdrawal_over_limit"`, BO-16) |
| Xatolar | `VALIDATION_ERROR`, `CASH_WITHDRAW_LIMIT_EXCEEDED` |
| Idempotency-Key | Majburiy (back-office'dan); POS'dan — `/sync/push` orqali `cash_movement.created` voqeasi (`04-offline-sync.md` §2) |
| Offline | To'liq offline (M01 bilan bir xil append-only, `02-modullar-talablari.md` M16) |
| Bog'langan | US-M16-01; POS ekrani, BO-16 (limitdan oshganda) |

### 54. `POST /cash-movements/{id}/cancel`

| | |
|---|---|
| Maqsad | Harakatni bekor qilish (teskari yozuv) |
| Ruxsat | Yaratuvchi huquqi bilan bir xil (`cash.deposit`/`cash.withdraw`) |
| So'rov | `{reason: string (majburiy)}` |
| Javob | `200 {id, status: "cancelled"}` |
| Xatolar | `DOC_ALREADY_CANCELLED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q (faqat online) |
| Bog'langan | US-M16-01; audit majburiy |

### 55. `GET /cash-registers/{id}/cash-history`

| | |
|---|---|
| Maqsad | Smena/kassa bo'yicha naqd tarixi: boshlanish, sotuvlar, qo'yilgan/olingan, kutilgan vs sanalgan, farq (US-M16-03) |
| Ruxsat | `cash.count.shift` **yoki** `reports.sales.view` (Egasida `cash.count.shift` yo'q, lekin US-M16-03 "Egasi sifatida" ko'rishni talab qiladi — K3-03/A3-20) |
| So'rov | `?date_from=&date_to=` |
| Javob | `{items: [{shift_id, opened_at, closed_at, opening_cash, expected_cash, counted_cash, variance, counted_card_total}]}` (`diff`→`variance`, `card_total`→`counted_card_total`, DB-07/A3-19) |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish |
| Bog'langan | US-M16-02, US-M16-03; **BO-09 "Kassa/smena tarixi" eksport kodi** (ochiq savol #1 yopildi — K3-03/K3-06) |

---

## M17 — Obuna

### 56. `GET /billing/plan`

| | |
|---|---|
| Maqsad | Joriy yagona tarif va limitlar (`plans` — `standard` qatori) |
| Ruxsat | `—` |
| So'rov | — |
| Javob | `{code: "standard", price_month: "99000.00", price_year: "950400.00", limits: {included_cash_registers: 1, ai_monthly_tokens: int}}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan |
| Bog'langan | US-M17-02; BO-19 |
| **Lokaut** | **Ochiq** — `require_subscription_ok` middleware istisnosi, `restricted` holatida ham ishlaydi (A3-01/B-02) |

### 57. `GET /billing/subscription`

| | |
|---|---|
| Maqsad | Obuna holati (`subscriptions` — yagona manba, `01-malumotlar-modeli.md` §8) |
| Ruxsat | `—` |
| So'rov | — |
| Javob | `{status: "trial"\|"active"\|"grace"\|"restricted"\|"closed", period: "month"\|"year", current_period_end, grace_ends_at, active_cash_registers: int}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Mahalliy litsenziya tokenidan (`license`), server holatidan farqlanishi mumkin (`12-autentifikatsiya-oauth2.md` §17) |
| Bog'langan | US-M17-03; BO-01 (banner), BO-19 |
| **Lokaut** | **Ochiq** — `restricted`da ham ishlaydi (A3-01/B-02) |

### 58. `GET /billing/addons`

| | |
|---|---|
| Maqsad | Qo'shimcha xizmatlar katalogi (`addons`, hozircha faqat `extra_register`) + tenant joriy soni |
| Ruxsat | `—` |
| So'rov | — |
| Javob | `{catalog: [{code: "extra_register", name, price_month: "39000.00"}], tenant_addons: [{addon_code, quantity, price_month_snapshot, added_at}]}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan |
| Bog'langan | US-M17-02; BO-19 |
| **Lokaut** | **Ochiq** — `restricted`da ham ishlaydi (A3-01/B-02) |

### 59. `POST /billing/addons`

| | |
|---|---|
| Maqsad | Qo'shimcha kassa qo'shish (US-M17-02) |
| Ruxsat | `billing.manage` — **faqat Egasi** |
| So'rov | `{addon_code: "extra_register" (majburiy), quantity: int (majburiy, >0, qo'shiladigan miqdor)}` |
| Javob | `201 {addon_code, quantity, price_month_snapshot: "39000.00", added_at}` — keyingi to'lovdan qo'llanadi |
| Xatolar | `VALIDATION_ERROR`, `OWNER_ONLY` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M17-02; BO-19 |

### 60. `POST /billing/addons/{addon_code}/reduce`

> `DELETE /billing/addons/{code}` tanasi bilan — HTTP semantikasiz, proksi/orval tashlab yuborishi mumkin edi; `POST .../reduce` bilan almashtirildi (A3-12).

| | |
|---|---|
| Maqsad | Qo'shimchadan voz kechish (M17 chekka holat — kamaytirish, ortiqcha kassa arxivlanishi talab qilinadi) |
| Ruxsat | `billing.manage` — **faqat Egasi** |
| So'rov | `{quantity: int (majburiy, kamaytiriladigan miqdor)}` |
| Javob | `200 {addon_code, quantity, removed_at}` — agar faol kassalar soni yangi limitdan ko'p bo'lsa, javobda `requires_archiving: [cash_register_id, ...]` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M17-02 chekka holat; BO-19 |

### 61. `POST /billing/checkout`

> **KRITIK — lokautda ham ochiq** (A3-01/B-02/Z-01): ilgari `require_subscription_ok` middleware bu endpoint'ni ham bloklardi, natijada lokautdagi tenant to'lov qila **olmasdi** — qaror #15 ("to'lov darhol kirishni tiklaydi") amalga oshmasdi. Endi `/billing/*` o'qish yo'llari + shu endpoint + `/billing/webhooks/*` — lokaut istisnolari ro'yxatida (`09-backend-arxitekturasi.md` §3, `12-autentifikatsiya-oauth2.md` §16.1/§20).
>
> **`restricted` holatida sessiya yo'q** (K3-04): to'lov `12-autentifikatsiya-oauth2.md` §16.1.1 `GET /billing/pay` orqali — telefon+parol identifikatsiyasidan keyin qisqa muddatli `pay_token` beriladi, bu endpoint shu token bilan (`Authorization: PayToken ...`) chaqiriladi, faqat shu bir amal uchun ruxsat etiladi.

| | |
|---|---|
| Maqsad | To'lov checkout yaratish (Click/Payme) — obuna davrini uzaytirish uchun |
| Ruxsat | `billing.manage` (sessiya bilan) **yoki** `pay_token` (`restricted`, sessiyasiz, K3-04) — **faqat Egasi** |
| So'rov | `{provider: "click"\|"payme", period: "month"\|"year"}` |
| Javob | `201 {payment_id, checkout_url, amount, period}` — `provider_tx_id` checkout paytida noma'lum (Payme `CreateTransaction`da beradi, A3-02): server `billing_payments(status="pending")` yozuvini `payment_id` bilan yaratadi, Click `merchant_trans_id` = shu `payment_id` (`billing_payment_by_id()`, DB-30) |
| Xatolar | `VALIDATION_ERROR`, `OWNER_ONLY` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q (ro'yxatdan o'tish/to'lov faqat online, `02-modullar-talablari.md` M17) |
| Bog'langan | US-M17-02, US-M17-03; BO-19 |
| **Lokaut** | **Ochiq** — `restricted`da ham ishlaydi, `pay_token` orqali (A3-01/K3-04) |

### 62. `GET /billing/payments`

| | |
|---|---|
| Maqsad | To'lovlar tarixi (`billing_payments`) |
| Ruxsat | `billing.manage` — **faqat Egasi** |
| So'rov | Cursor |
| Javob | `{items: [{id, amount, provider, provider_tx_id, status, paid_at}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M17-02; BO-19 |
| **Lokaut** | **Ochiq** — `restricted`da ham ishlaydi (A3-01/B-02) |

### 63. `POST /billing/webhooks/click`

| | |
|---|---|
| Maqsad | Click webhook (bizning obuna billing'imiz, platforma merchant hisobi) — `13-api-katalog-0-umumiy.md` §14 naqshi |
| Ruxsat | `—` (MD5 imzo tekshiruvi) |
| So'rov | Click "Shop API" Prepare/Complete shakli (`action`, `click_trans_id`, `merchant_trans_id`, `amount`, `sign_time`, `sign_string`) |
| Javob | Click protokoliga mos JSON (`error: 0` muvaffaqiyat) |
| Xatolar | `WEBHOOK_SIGNATURE_INVALID` |
| Idempotency-Key | Kerak emas (`provider_tx_id` UNIQUE orqali dedupe) |
| Offline | — |
| Bog'langan | US-M17-02; `03-integratsiyalar.md` §9 |
| **Lokaut** | **Ochiq** (o'z imzo tekshiruvi bilan) — A3-01/B-02 |

### 64. `POST /billing/webhooks/payme`

| | |
|---|---|
| Maqsad | Payme webhook (JSON-RPC, bizning billing) |
| Ruxsat | `—` (`Authorization: Basic` merchant login:key tekshiruvi) |
| So'rov | JSON-RPC: `method` (`CheckPerformTransaction`\|`CreateTransaction`\|`PerformTransaction`\|`CancelTransaction`\|`CheckTransaction`\|`GetStatement`), `params` |
| Javob | JSON-RPC natija (Payme protokoliga mos) |
| Xatolar | `WEBHOOK_SIGNATURE_INVALID` |
| Idempotency-Key | Kerak emas (`provider_tx_id` UNIQUE) |
| Offline | — |
| Bog'langan | US-M17-02; `03-integratsiyalar.md` §9 |
| **Lokaut** | **Ochiq** (o'z imzo tekshiruvi bilan) — A3-01/B-02 |

### 65. `GET /billing/invoices/{payment_id}`

| | |
|---|---|
| Maqsad | To'lov uchun hujjat (kvitansiya/invoys PDF, US-M17-02: "to'lov uchun hujjat beriladi") |
| Ruxsat | `billing.manage` — **faqat Egasi** |
| So'rov | — |
| Javob | `200 {payment_id, invoice_url (signed PDF, 24 soat)}` |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M17-02; BO-19 |

### Platforma admin (`/platform/*`) — havola

To'liq sxema **`12-autentifikatsiya-oauth2.md` §18.1**da. Bu yerda faqat ro'yxat (ADM-01):

| Metod + yo'l | Maqsad |
|---|---|
| `GET /platform/tenants` | Tenantlar ro'yxati, filtr (holat, tarif) |
| `GET /platform/tenants/{id}` | Tafsilot: obuna, to'lov, AI sarfi, qurilmalar |
| `POST /platform/tenants/{id}/extend-subscription` | Muddatni qo'lda uzaytirish |
| `POST /platform/tenants/{id}/revoke-all-sessions` | Insident javobi |
| `GET /platform/tenants/{id}/ai-usage` | AI sarfi |
| `POST /platform/tenants/{id}/owner/block`, `/unblock` | Egasi hisobini bloklash/blokdan chiqarish |
| `POST /platform/tenants/{id}/owner/reset-password` | Egasiga tiklash OTP yuborish |
| `GET /platform/tenants/{id}/owner/sessions`, `POST …/owner/sessions/{sid}/revoke` | Egasi sessiyalari |

Ruxsat — hammasi `platform.admin` (**faqat `platform_admins`**, majburiy TOTP, har kirish audit'da — `05-xavfsizlik-va-audit.md` §3.4). Bog'langan: US-M13-08, US-M17-04; ADM-01.

---

## M18 — Bildirishnomalar

### 66. `POST /notifications/telegram/link-start`

| | |
|---|---|
| Maqsad | Telegram ulash uchun bir martalik kod/havola generatsiya (US-M18-01) |
| Ruxsat | `telegram.link` |
| So'rov | Tana yo'q |
| Javob | `201 {link_code, bot_url, expires_at (10 daqiqa, taxmin)}` |
| Xatolar | — |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M18-01; BO-20 |

### 67. `GET /notifications/telegram/status`

| | |
|---|---|
| Maqsad | Joriy foydalanuvchining Telegram ulanish holati |
| Ruxsat | `telegram.link` |
| So'rov | — |
| Javob | `{linked: bool, chat_id: string\|null, linked_at: timestamptz\|null}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan |
| Bog'langan | US-M18-01; BO-20 |

### 68. `DELETE /notifications/telegram/link`

| | |
|---|---|
| Maqsad | Ulanishni uzish (`telegram_links` yozuvini o'chirish) |
| Ruxsat | `telegram.link` |
| So'rov | — |
| Javob | `204` |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M18-01 chekka holat (xodim o'chirilganda avtomatik); BO-20 |

### 69. `GET /notification-settings`

| | |
|---|---|
| Maqsad | Ogohlantirish turlari sozlamalari (US-M18-03: kam qoldiq, smena farqi, limitdan katta amal, davlat hisoboti farqi, offline 48 soat, obuna eslatmalari) |
| Ruxsat | `notifications.manage` |
| So'rov | — |
| Javob | `{items: [{kind, enabled, time}]}` — `kind` ∈ `{daily_report, low_stock, cash_variance, over_limit_action, state_report_diff, offline_48h, subscription_due, subscription_grace, debt_due_today, debt_aging_60, debt_limit_exceeded_offline, expiry_soon}` (to'liq ro'yxat, K3-05: `subscription_due` — 3/1/0 kun oldin; `subscription_grace` — darhol/12s/2s; `debt_due_today` — US-M08-09; `debt_aging_60` — US-M08-10; `debt_limit_exceeded_offline` — tavsiya #7; `expiry_soon` — US-M04-06) |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan |
| Bog'langan | US-M18-02, US-M18-03; BO-20 |

### 70. `PATCH /notification-settings`

| | |
|---|---|
| Maqsad | Sozlamalarni (yoqish/o'chirish, vaqt) yangilash |
| Ruxsat | `notifications.manage` |
| So'rov | `{items: [{kind: string, enabled: bool, time?: "HH:mm"}]}` |
| Javob | `200 {items: [...]}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M18-02, US-M18-03; BO-20 |

### 71. `GET /notifications-log`

| | |
|---|---|
| Maqsad | Yuborilgan xabarlar tarixi (`notifications_log` — Telegram/SMS, holat, narx) |
| Ruxsat | `notifications.manage` |
| So'rov | Cursor; filtr `?channel=telegram\|sms&status=` |
| Javob | `{items: [{id, channel, recipient, template, status, cost, created_at}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | M08/M18 qarz bildirishnoma kuzatuvi; BO-06, BO-20 |

---

## AI (AI-01, AI-03, AI-05, AI-06)

### 72. `POST /ai/chat`

| | |
|---|---|
| Maqsad | AI-01 — umumiy biznes savol-javob chat ("kod hisoblaydi, AI tushuntiradi", `05-ai-funksiyalar.md`) |
| Ruxsat | `ai.chat.use` |
| So'rov | `{message: string (majburiy, ≤2000 belgi), history: [{role: "user"\|"assistant", content: string}] (ixtiyoriy, oxirgi ≤10 xabar — holat stateless, server saqlamaydi), locale: "uz"\|"ru"}` |
| Javob | `text/event-stream` (SSE): `event: token` (`data: {"text": "..."}`) ketma-ket, yakunda `event: done` (`data: {"citations": [{"metric": "net_profit", "value": "1240000.00", "source": "reports.profit_and_loss"}], "ai_request_id": "..."}`); AI xato bersa `event: error` (`data: {"code": "AI_PROVIDER_UNAVAILABLE"}`) |
| Xatolar | `AI_LIMIT_EXCEEDED`, `AI_PROVIDER_UNAVAILABLE`, `VALIDATION_ERROR`, `RATE_LIMITED` |
| Idempotency-Key | Kerak emas (strim, qayta yuborish — yangi so'rov) |
| Offline | Ishlamaydi — internet/LLM API talab qiladi (BO-13) |
| Bog'langan | AI-01; BO-13, M18 Telegram bot (`07-ai-qatlami.md` §11, bitta huquq/budjet quvuri) |

> **AI-03 — yagona oqim, 13-2 bilan birlashtirilgan** (Q4/A2-01): `ai_ocr_jobs` jadvali (DB-13) `13-2`dagi `purchase_ocr_drafts` taklifini o'zida qamrab oladi — alohida OCR endpoint boshqa fayllarda yo'q. `doc_type_hint` uchta qiymatga ega — `purchase` (goods-receipts, BO-04/K2-01), `catalog` (mahsulot katalogi + boshlang'ich qoldiq, BO-21 onboarding, K2-04), `return` (**faqat back-office**, POS orqali emas — offline markirovka qaytarish har doim online bo'lishi kerakligi uchun qaytarish OCR'i ham back-office operatsiyasi, K3-07). *(2026-10-15: qabul-6 A3-13, qabul-7 K3-07)*

### 73. `POST /ai/ocr/jobs`

| | |
|---|---|
| Maqsad | AI-03 — qog'oz hujjat (yuk xati/faktura/chek) fotosini tahlilga yuborish (`07-ai-qatlami.md` §10) |
| Ruxsat | `ai.ocr.use` |
| So'rov | `{attachment_id: UUID (majburiy, avval `POST /attachments`ga yuklangan — `13-api-katalog-0-umumiy.md` §12, ≤10 MB), doc_type_hint: "purchase"\|"return"\|"catalog" (majburiy)}` |
| Javob | `202 {job_id, status: "processing"}` |
| Xatolar | `VALIDATION_ERROR`, `AI_LIMIT_EXCEEDED`, `AI_PROVIDER_UNAVAILABLE` |
| Idempotency-Key | Majburiy |
| Offline | Ishlamaydi (AI chaqiruvi online talab qiladi) |
| Bog'langan | AI-03; BO-04 (purchase), BO-21 (catalog, K2-04), BO-15/M02 (qaytarish, faqat back-office) |

### 74. `GET /ai/ocr/jobs/{job_id}`

| | |
|---|---|
| Maqsad | OCR natijasini olish — maydon bo'yicha ishonch darajasi bilan (summa ≥95%, sana ≥90%, miqdor/nom ≥80% — `07-ai-qatlami.md` §10) |
| Ruxsat | `ai.ocr.use` |
| So'rov | — |
| Javob | `{job_id, status: "processing"\|"done"\|"confirmed"\|"failed"\|"expired" (DB-13 holatlari), doc_type_hint, fields: {header: {<maydon>: {value, confidence (0..1)}, ...}, lines: [{<maydon>: {value, confidence}, ...}]}, low_confidence_fields: ["lines[0].product_name", ...], error_code}` — shakl 13-2'dagi bilan bir xil (`confidence_pct` → `confidence` 0..1, tekis `fields[]` massivi → `header`+`lines` ichma-ich obyekt, A3-13) |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | AI-03; BO-04, BO-15, BO-21 |

### 75. `POST /ai/ocr/jobs/{job_id}/confirm`

| | |
|---|---|
| Maqsad | Foydalanuvchi tasdiqlagan/tuzatgan maydonlar bilan hujjat loyihasini **to'g'ridan-to'g'ri** yaratish (AI hech qachon o'zi hujjat yozmaydi — foydalanuvchi `fields`ni o'qib, tuzatib, hujjat shaklida yuboradi) |
| Ruxsat | `ai.ocr.use` **va** `doc_type_hint`ga mos modul ruxsati: `purchase` → `purchases.receive`; `catalog` → `catalog.manage`; `return` → `returns.create` (`13-api-katalog-1-kassa.md`) |
| So'rov | `doc_type_hint`ga qarab tana shakli: `purchase` — `POST /goods-receipts` (13-2 §8) bilan **bir xil** (`supplier_id, warehouse_id, doc_date, paid_immediately, lines[...]`); `catalog` — `{products: [...]}` (+ miqdor ko'rsatilgan bo'lsa `stock_opening_lines: [...]`); `return` — tegishli qaytarish qoralamasi shakli (13-1) |
| Javob | `201 {created_doc_type: "goods_receipts"\|"products"\|"stock_openings"\|"returns", created_doc_id, status: "draft"}` — yakuniy tasdiq/o'tkazish oddiy hujjat oqimi orqali (`POST /goods-receipts/{id}/post` va h.k., boshqa modul faylida) |
| Xatolar | `VALIDATION_ERROR`, `409 {code:"DOC_INVALID_STATE"}` (job allaqachon `confirmed`/`expired` — `DOC_ALREADY_CANCELLED` o'rniga, A3-13) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | AI-03; BO-04, BO-15, BO-21; audit: AI hech qachon avtomatik tasdiqlamaydi (`05-ai-funksiyalar.md` Asosiy xulosa #3) |

### 76. `POST /ai/vat-diffs/{diff_id}/explain`

| | |
|---|---|
| Maqsad | AI-05 — davlat hisoboti farqini (`state_report_diffs`) o'zbek tilida tushuntirish; raqamni AI o'zi hisoblamaydi, faqat kod hisoblagan `diff`/manba hujjatlarni tabiiy tilda ifodalaydi |
| Ruxsat | `tax.compare.review` |
| So'rov | Tana yo'q |
| Javob | `200 {diff_id, explanation: string, source_documents: [{doc_type, doc_id, doc_date}], ai_request_id}` — `explanation` `state_report_diffs.explanation`ga yoziladi |
| Xatolar | `AI_LIMIT_EXCEEDED`, `AI_PROVIDER_UNAVAILABLE`, `NOT_FOUND` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | AI-05; BO-10 |

### 77. `POST /ai/debt-reminders/draft`

| | |
|---|---|
| Maqsad | AI-06 — qarz eslatma matni loyihasi (risk balli kod hisoblaydi — kechikkan kun/marta soni, AI faqat matn yozadi) |
| Ruxsat | `ai.chat.use` (loyiha chiqarish — ko'rish/matn, A3-14/K1-10) |
| So'rov | `{counterparty_id: UUID (majburiy)}` |
| Javob | `200 {counterparty_id, draft_text, risk_score: "low"\|"medium"\|"high" (kod hisoblagan), overdue_days, amount, ai_request_id}` — **avtomatik yuborilmaydi** |
| Xatolar | `AI_LIMIT_EXCEEDED`, `AI_PROVIDER_UNAVAILABLE`, `NOT_FOUND` |
| Idempotency-Key | Majburiy |
| Offline | Faqat ko'rish (BO-06, oxirgi loyihalar) |
| Bog'langan | AI-06; BO-06 |

### 78. `POST /ai/debt-reminders/send`

| | |
|---|---|
| Maqsad | Menejer/Buxgalter tasdiqlagan (tahrirlangan bo'lishi mumkin) matnni yuborish — `notifications_log` yozuvi; standart shablon (AI'siz, qo'lda `message_text`) bilan yuborish ham shu endpoint orqali |
| Ruxsat | `debts.remind` (yangi kod, X-01/P-06 — `ai.chat.use` o'rniga: mijozga xabar yuborish AI huquqi bilan emas, alohida kod bilan himoyalanishi kerak, A3-14/K1-10) |
| So'rov | `{counterparty_id: UUID (majburiy), message_text: string (majburiy — tasdiqlangan yakuniy matn), channel: "telegram"\|"sms" (majburiy, `counterparties.notify_consent=true` talab qiladi)}` |
| Javob | `201 {notification_log_id, status: "sent"\|"queued"}` |
| Xatolar | `422 {code:"NOTIFY_CONSENT_REQUIRED"}` (`notify_consent=false` bo'lsa — `VALIDATION_ERROR` o'rniga, 13-0 §15.13), `NOT_FOUND` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | AI-06; BO-06; audit: AI matnini odam tasdiqlashi majburiy (`05-ai-funksiyalar.md` Asosiy xulosa #3) |

### 79. `GET /ai/usage`

| | |
|---|---|
| Maqsad | Joriy oy AI token/so'rov sarfi va qolgan limit (`plans.limits.ai_monthly_tokens`, `07-ai-qatlami.md` §5) |
| Ruxsat | `ai.chat.use` |
| So'rov | — |
| Javob | `{period: "2026-10", tokens_used, tokens_limit, requests_by_feature: {"AI-01": int, "AI-03": int, "AI-05": int, "AI-06": int}, pct_used}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | `07-ai-qatlami.md` §5 (80% ogohlantirish); BO-13, BO-19 |

---

## Ma'lumotlar modeliga kerakli qo'shimchalar

**Hal qilindi — `tekshiruv/qabul-6-api-db.md`** (A3-24, *2026-10-15*):
1. `outbox_jobs.kind=report_export` → DB-19 (qo'shildi).
2. `recurring_expenses` to'liq ustun ro'yxati → DB-17 (jadval to'liq qayta yozildi).
3. `billing_payments.period`/`invoice_attachment_id` → DB-18 (qo'shildi; alohida `billing_invoices` jadvali — rad, ustun yetarli).
4. Yangi jadval `ai_ocr_jobs` → DB-13 (13-2'dagi `purchase_ocr_drafts` bilan birlashtirilgan holda qo'shildi).
5. `cash_registers.archived_at` → allaqachon DDL'da bor, `01-malumotlar-modeli.md` M-06.
6. QQS/aylanma tolerance (`vat_diff_tolerance_amount`) → `tenants.settings` M-03 (standart `"1000.00"`, buxgalter tasdig'i kutilmoqda — *(tasdiq kutilmoqda)*).

---

## Ochiq savollar

1. ~~M16 uchun alohida BO ekrani raqami~~ — **yopildi** (K3-03): `GET /cash-registers/{id}/cash-history` — BO-09 "Kassa/smena tarixi" (E-28), eksport kodi `cash-history` (K3-06).
2. M18'ning "Telegram ulash" tugmasi joylashuvi — `12-autentifikatsiya-oauth2.md` §1.4 "back-office'da" deydi, `04-ekranlar-va-ux.md` BO-20 sifatida alohida ekran beradi; ikkisi izchil (BO-20), lekin bu faylda yozilgan `/notifications/telegram/link-start` shu ekranga bog'langan deb qabul qilindi — tasdiqlash kerak.
3. `AI_LOW_CONFIDENCE` — bu haqiqiy xato emas, javob ichidagi bayroq (`13-api-katalog-0-umumiy.md` §15.13); OpenAPI'da alohida xato kodi sifatida modellashtirish noto'g'ri bo'lishi mumkin — faqat `fields.header[].low_confidence`/`low_confidence_fields[]` orqali ifodalanishi kerakligi tasdiqlanishi kerak.
4. `POST /ai/chat` uchun aniq rate-limit raqami (AI xarajat nazorati, `12-autentifikatsiya-oauth2.md` §12ga o'xshash) — bu faylda belgilanmadi, backend jamoasi bilan kelishiladi.
5. Platforma admin ro'yxatidagi (`/platform/*`) ba'zi amallar (masalan `extend-subscription`) `billing_payments`ga ta'sir qilmasdan `subscriptions.current_period_end`ni qo'lda o'zgartiradi — bu yozuv `billing_payments`da ko'rinmaydi, audit orqali kuzatiladi; `GET /billing/payments` (62-endpoint) javobida bu holatni qanday ko'rsatish kerakligi ochiq.
6. `approval_requests.expires_at` (15 daqiqa) va POS poll oralig'i (3 soniya) — taxmin, pilotda tasdiqlanadi *(tasdiq kutilmoqda)*. *(2026-10-15: qabul-6)*

## Manbalar

- `spec/02-arxitektura/13-api-katalog-0-umumiy.md` — konventsiyalar, xato kodlari katalogi (bu fayl shunga bog'liq).
- `spec/01-mahsulot/02-modullar-talablari.md` — M10–M18 foydalanuvchi hikoyalari.
- `spec/01-mahsulot/04-ekranlar-va-ux.md` — BO-07/08/09/10/11/12/13/16/17/19/20, ADM-01.
- `spec/01-mahsulot/05-ai-funksiyalar.md`, `spec/02-arxitektura/07-ai-qatlami.md` — AI-01/03/05/06 arxitektura qoidalari, model routing, limitlar.
- `spec/02-arxitektura/01-malumotlar-modeli.md` — jadval/maydon nomlari (§2–10).
- `spec/02-arxitektura/02-provodka-qoidalari.md` — M11/M15/M16 provodka qoidalari.
- `spec/02-arxitektura/05-xavfsizlik-va-audit.md` §2.1–2.3 — ruxsat kodlari, standart limitlar.
- `spec/02-arxitektura/12-autentifikatsiya-oauth2.md` §18 — `/admin/users`, `/platform/*` (takrorlanmadi, faqat havola).
- `spec/02-arxitektura/03-integratsiyalar.md` §9 — Click/Payme webhook protokoli.
