# API katalogi — 3. Moliya va Admin (M10–M18, AI; M19 — havola)

**Maqsad:** QQS, buxgalteriya, hisobotlar, huquqlar, filiallar, tenant sozlamalari, xarajatlar, kassa pul harakati, bank tushumi tasdig'i, obuna/billing, bildirishnomalar va AI endpoint'lari uchun API kontrakti; 1C integratsiyasi (M19) API'siga havola.
**Kim uchun:** Backend/frontend ishlab chiquvchilar, QA.
**Bog'liq fayllar:** `17-api-umumiy.md` (base path, ID/pul/sana format, pagination, headerlar, xato konverti, hujjat hayot sikli, xato kodlari katalogi — bu faylda takrorlanmaydi, faqat qo'llaniladi), `14-autentifikatsiya-oauth2.md` §18/§20 (auth/platforma admin/sync, bu faylda faqat havola), `16-offline-sync.md` §3, `03-modullar-talablari.md` (M10–M18), `06-ekranlar-umumiy.md`, `09-ai-funksiyalar.md`, `22-ai-qatlami.md`, `11-malumotlar-modeli.md`, `13-provodka-qoidalari.md` (§2.18a `bank_settlements`, §2.26/§4.3 `tax_settlements`), `15-xavfsizlik-va-audit.md` §2.1–2.2, `33-1c-integratsiya.md` §10 (1C integratsiyasi veb API — W-01…W-55).
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. **107 ta indeks qatori** 12 guruhda (+ `/platform/*` havolasi): M10 QQS (13: hisobot/registr 2, davlat hisoboti 7, `tax-settlements` 4 ta), M11 Buxgalteriya (8 + `ledger-adjustments` 2 ta — jami 10), M12 Hisobotlar (7), M13 Huquqlar (8: rol/ruxsat 6 + tenant qurilmalari 2 — BO-11 «Qurilmalar» tabi; foydalanuvchi CRUD'i `14-autentifikatsiya-oauth2.md`da), M14 Filiallar (13: filial 7, ombor 2, kassa 4), M13a/M14 Tenant sozlamalari (8: sozlamalar, soliq rejimi, integratsiya kalitlari, sinxron istisnolari, AI rozilik), M15 Xarajatlar (11), M16 Kassa pul harakati (4), M11/M16 Bank tushumi tasdig'i (8, `/bank-settlements` + ko'chirma importi), M17 Obuna (10 + `/billing/export-my-data` (65a) + platforma admin havolasi), M18 Bildirishnomalar (6), AI (8). M19 «1C integratsiyasi» (55 endpoint, W-01…W-55) — bu faylda **takrorlanmaydi**, faqat havola bo'limi (`33-1c-integratsiya.md` §10).
2. Hujjat turidagi resurslar `17-api-umumiy.md` §9 naqshiga rioya qiladi: `expenses`, `bank-settlements`, `tax-settlements` — uch bosqichli (`draft → post → cancel`); `cash-movements`, `ledger-adjustments`, `supplier-payments` — bir bosqichli (yaratilganda `posted`, keyin faqat `cancel`); faqat sof o'qish/sozlama resurslari (`roles`, `branches`, `notification-settings`) CRUD (`GET`/`POST`/`PATCH`) shaklida.
3. M17 platforma admin endpoint'lari (`/platform/*`) **allaqachon** `14-autentifikatsiya-oauth2.md` §18.1'da to'liq yozilgan — bu faylda faqat ro'yxat ko'rinishida qayta ko'rsatiladi (to'liq sxema u yerda), ikki marta yozilmaydi.
4. Excel/PDF eksport (M12, M10 hisobotlari) — `17-api-umumiy.md` §13dagi asinxron job naqshi; Click/Payme (M17) — §14dagi webhook naqshi.
5. AI-01 (chat) — SSE streaming (`text/event-stream`); AI-03 (OCR) — ikki bosqichli (yuklash+tahlil → tasdiqlash); AI-05/AI-06 — "kod hisoblaydi, AI tushuntiradi" tamoyili bo'yicha faqat tushuntirish/matn, raqamni o'zi hech qachon hisoblamaydi (`09-ai-funksiyalar.md` Asosiy xulosa #2).

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
| 7a | `POST /state-reports/{id}/confirm` | M10 | Hisobotni tasdiqlangan deb qayd etish | `tax.correction.submit` |
| 8 | `POST /state-reports/{id}/correction` | M10 | Kabinetda kiritilgan tuzatishni qayd etish (imzosiz) | `tax.correction.submit` |
| 8a | `GET /tax-settlements` | M10 | Soliq hisob-kitobi hujjatlari (`tax_settlements`) ro'yxati | `tax.vat.view` |
| 8b | `POST /tax-settlements` | M10 | QQS hisobga olish / aylanma solig'i qoralamasi (server hisoblaydi) | `accounting.post` |
| 8c | `POST /tax-settlements/{id}/post` | M10 | O'tkazish (`Dt 6410 / Kt 4410` yoki `Dt 9430\|9820 / Kt 6410`) | `accounting.post` |
| 8d | `POST /tax-settlements/{id}/cancel` | M10 | Bekor qilish (storno) | `accounting.post` |
| 9 | `GET /ledger-entries` | M11 | Buxgalteriya jurnali | `accounting.post` |
| 10 | `POST /ledger-adjustments` | M11 | Qo'lda tuzatuvchi yozuv (joriy ochiq davr, bir bosqichli hujjat) | `accounting.post` |
| 10a | `POST /ledger-adjustments/{id}/cancel` | M11 | Tuzatuvchi yozuvni bekor qilish | `accounting.post` |
| 10b | `GET /ledger-adjustments` | M11 | Tuzatuvchi yozuvlar ro'yxati | `accounting.post` |
| 11 | `GET /reports/trial-balance` | M11 | Aylanma-saldo vedomosti | `reports.finance.view` |
| 12 | `GET /reports/profit-and-loss` | M11 | Foyda-zarar hisoboti | `reports.finance.view` |
| 13 | `GET /reports/balance-sheet` | M11 | Balans hisoboti | `reports.finance.view` |
| 14 | `GET /period-closings` | M11 | Yopilgan davrlar ro'yxati | `accounting.post` |
| 15 | `POST /period-closings` | M11 | Davrni yopish | `accounting.period.close` |
| 16 | `GET /period-closings/{period}/readiness` | M11 | Yopishga tayyormi (recost, fiskal, qurilma sinxroni tekshiruvi) | `accounting.post` |
| 17 | `GET /reports/dashboard` | M12 | Egasi/Menejer dashboard ma'lumoti | `reports.sales.view` |
| 18 | `GET /reports/sales` | M12 | Savdo hisoboti (filial/davr) | `reports.sales.view` |
| 19 | `GET /reports/top-products` | M12 | Eng ko'p/kam sotilgan tovarlar | `reports.sales.view` |
| 20 | `GET /reports/stock` | M12 | Qoldiq hisoboti | `stock.view` |
| 21 | `GET /reports/debts-aging` | M12 | Qarzdorlik "yosh" guruhlari (0-30/31-60/60+) | `reports.finance.view` yoki `debts.approve` |
| 22 | `POST /reports/{report-kod}/export` | M12 | Hisobotni Excel/PDF eksport qilish (job) | `reports.export` |
| 23 | `GET /reports/export-jobs/{job_id}` | M12 | Eksport job holati | `reports.export` |
| 24 | `GET /roles` | M13 | Rollar ro'yxati | `settings.users` |
| 25 | `POST /roles` | M13 | Yangi (maxsus) rol yaratish | `settings.users` |
| 26 | `PATCH /roles/{id}` | M13 | Rol nomini tahrirlash | `settings.users` |
| 27 | `GET /roles/{id}/permissions` | M13 | Rolning ruxsat/limit ro'yxati | `settings.users` |
| 28 | `PUT /roles/{id}/permissions` | M13 | Rol ruxsat/limitlarini belgilash | `settings.users` |
| 29 | `GET /permissions-catalog` | M13 | To'liq ruxsat kodlari katalogi (statik) | `settings.users` |
| 29a | `GET /devices` | M13 | Tenant qurilmalari ro'yxati (BO-11 «Qurilmalar» tabi) | `devices.revoke` |
| 29b | `POST /devices/{id}/revoke` | M13 | Qurilmani bekor qilish | `devices.revoke` |
| 30 | `GET /branches` | M14 | Filiallar ro'yxati | `—` |
| 31 | `POST /branches` | M14 | Yangi filial yaratish | `settings.branches` |
| 32 | `GET /branches/{id}` | M14 | Filial tafsiloti | `—` |
| 33 | `PATCH /branches/{id}` | M14 | Filialni tahrirlash | `settings.branches` |
| 34 | `GET /branches/{id}/tax-settings` | M14 | Aholi punkti toifasi tarixi | `—` |
| 35 | `POST /branches/{id}/tax-settings` | M14 | Yangi toifa qiymati qo'shish | `settings.branches` |
| 36 | `POST /branches/{id}/copy-pricing` | M14 | Narx/chegirma siyosatini boshqa filialga nusxalash | `prices.edit` |
| 37 | `GET /warehouses` | M14 | Omborlar ro'yxati | `—` |
| 37a | `PATCH /warehouses/{id}` | M14 | Ombor nomi va tovar hisobini (2910/2920) o'zgartirish | `settings.branches` |
| 38 | `GET /cash-registers` | M14 | Kassalar ro'yxati | `—` |
| 39 | `POST /cash-registers` | M14 | Yangi kassa qo'shish | `cash_register.manage` |
| 40 | `PATCH /cash-registers/{id}` | M14 | Kassani tahrirlash | `cash_register.manage` |
| 40a | `GET /tenant/settings` | M13a/M14 | Do'kon sozlamalari + integratsiya holati | `settings.tenant` |
| 40b | `PATCH /tenant/settings` | M13a/M14 | Do'kon nomi, yuridik shakli, bank hisobi va tenant siyosatlari | `settings.tenant` (`vat_diff_tolerance_amount` — yoki `tax.compare.review`) |
| 40c | `POST /tenant/tax-regimes` | M13a/M14 | Soliq rejimini o'zgartirish (keyingi oydan) | `settings.tenant` |
| 40d | `PUT /tenant/integrations/{provider}` | M13a/M14 | Integratsiya kalitlari (Faktura.uz, CRPT, Click/Payme/Uzum/UzQR merchant) | `settings.tenant` |
| 40e | `DELETE /tenant/integrations/{provider}` | M13a/M14 | Integratsiyani uzish | `settings.tenant` |
| 40f | `GET /sync-exceptions` | M13a/M14 | Sinxron istisnolari ro'yxati (BO-14) | `settings.tenant` yoki `accounting.post` |
| 40g | `POST /sync-exceptions/{id}/review` | M13a/M14 | Istisnoni «Ko'rib chiqildi» deb belgilash | `settings.tenant` yoki `accounting.post` |
| 40h | `POST /tenant/consents` | M13a/M14 | AI chegaradan tashqari uzatish roziligini qabul qilish/qaytarib olish | `settings.tenant` |
| 40i | `POST /cash-registers/{id}/archive` | M14 | Kassani arxivlash | `cash_register.manage` |
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
| 55a | `GET /bank-settlements` | M11/M16 | Bank tushumi tasdiqlari ro'yxati | `bank_settlements.manage` |
| 55b | `GET /bank-settlements/transit-balances` | M11/M16 | Yo'ldagi pul (5710) qoldig'i — filial × to'lov usuli | `bank_settlements.manage` |
| 55c | `POST /bank-settlements` | M11/M16 | Bank tushumi tasdig'i qoralamasini yaratish | `bank_settlements.manage` |
| 55d | `GET /bank-settlements/{id}` | M11/M16 | Hujjat tafsiloti (provodkalar bilan) | `bank_settlements.manage` |
| 55e | `POST /bank-settlements/{id}/post` | M11/M16 | O'tkazish: 5710 → 5110 + komissiya (9430 / inkassa — 9410) | `bank_settlements.manage` |
| 55f | `POST /bank-settlements/{id}/cancel` | M11/M16 | Bekor qilish (storno) | `bank_settlements.manage` |
| 55g | `POST /bank-settlements/imports` | M11/M16 | Bank ko'chirmasini (1CClientBankExchange .txt) import qilib qoralamalar yaratish | `bank_settlements.manage` |
| 55h | `PATCH /bank-settlements/{id}` | M11/M16 | Qoralamani tahrirlash | `bank_settlements.manage` |
| 56 | `GET /billing/plan` | M17 | Joriy tarif va limitlar | `—` |
| 57 | `GET /billing/subscription` | M17 | Obuna holati (status, muddat) | `—` |
| 58 | `GET /billing/addons` | M17 | Qo'shimcha xizmatlar katalogi | `—` |
| 59 | `POST /billing/addons` | M17 | Qo'shimcha kassa qo'shish | `billing.manage` |
| 60 | `POST /billing/addons/{addon_code}/reduce` | M17 | Qo'shimchadan voz kechish | `billing.manage` |
| 61 | `POST /billing/checkout` | M17 | To'lov checkout yaratish (Click/Payme) | `billing.manage` |
| 62 | `GET /billing/payments` | M17 | To'lovlar tarixi (qo'lda uzaytirishlar bilan) | `billing.manage` |
| 63 | `POST /billing/webhooks/click` | M17 | Click webhook (bizning billing) | `—` (imzo tekshiruvi) |
| 64 | `POST /billing/webhooks/payme` | M17 | Payme webhook (bizning billing) | `—` (imzo tekshiruvi) |
| 65 | `GET /billing/invoices/{payment_id}` | M17 | To'lov hujjati (kvitansiya PDF) | `billing.manage` |
| 65a | `POST`/`GET /billing/export-my-data` | M17 | Tenant to'liq eksporti (ZIP: CSV + `manifest.json`, qaror #51); lokautda OTP oqimi — `14-autentifikatsiya-oauth2.md` §16.5 | `billing.manage` yoki OTP eksport tokeni |
| — | `/platform/*` (10 endpoint) | M17 | Platforma admin — **to'liq sxema `14-autentifikatsiya-oauth2.md` §18.1** | `platform.admin` |
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
| — | `/onec-*` (W-01…W-55, 55 endpoint) | M19 | 1C integratsiyasi: agentlar, bazalar, moslashtirish, kunlik eksport partiyalari, solishtirish — **to'liq sxema `33-1c-integratsiya.md` §10** | `onec.*` (`15-xavfsizlik-va-audit.md` §2.1) |

---

## M10 — QQS

### 1. `GET /reports/vat-summary`

| | |
|---|---|
| Maqsad | Davr bo'yicha ichki QQS (yoki aylanma solig'i, tenant rejimiga qarab) hisob-kitobi — `vat_moves`dan agregatlangan: `output − input` (`13-provodka-qoidalari.md` §4.2) |
| Ruxsat | `tax.vat.view` |
| So'rov | `?period=2026-10` (majburiy, `YYYY-MM`), `?branch_id=` (ixtiyoriy) |
| Javob | `{period, regime: "vat"\|"turnover", output_vat, input_vat, net_vat, pending_credit_red_invoices, pending_credit_pct, turnover_base, turnover_rate_pct, turnover_amount, tax_settlement_id}` — `regime` tenant joriy oyi uchun `tenant_tax_regimes`dan; `pending_credit_*` faqat `regime=vat` bo'lsa (BO-07, US-M10-03, qizil e-fakturalar); `tax_settlement_id` — shu davr uchun `posted` `tax_settlements` hujjati (yo'q bo'lsa `null`, 8a–8d) |
| Xatolar | `VALIDATION_ERROR` (noto'g'ri `period` format) |
| Idempotency-Key | Kerak emas (`GET`) |
| Offline | Ishlamaydi — faqat online (server tomonida hisoblanadi, M10 offline xatti-harakati bo'yicha) |
| Bog'langan | US-M10-01, US-M10-04; BO-07 |

### 2. `GET /vat-moves`

| | |
|---|---|
| Maqsad | `vat_moves` registri — qator darajasida (hujjat, asos, QQS summasi) |
| Ruxsat | `tax.vat.view` |
| So'rov | Cursor pagination; filtr: `?kind=output\|input&period=2026-10&doc_type=sales\|goods_receipts\|returns\|supplier_returns\|write_offs\|supplier_payments&einvoice_id=` (`doc_type` qiymatlari — jadval nomlari) |
| Javob | `{items: [{id, kind, period, base_amount, vat_amount, doc_type, doc_id, einvoice_id, created_at}], next_cursor}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M10-01, US-M10-03; BO-07 |

### 3. `POST /state-reports`

| | |
|---|---|
| Maqsad | my.soliq.uz'dan qo'lda yuklab olingan davlat hisoboti faylini tizimga kiritish (`11-malumotlar-modeli.md` §9) |
| Ruxsat | `tax.compare.review` |
| So'rov | `multipart/form-data`: `file` (PDF/Excel, ≤5 MB), `tax_type` (`vat`\|`turnover`, majburiy; mol-mulk/yer/JShDS/ijtimoiy soliq hisobotlari MVP'dan tashqari — `05-mvp-chegarasi.md`), `period` (`YYYY-MM`, majburiy), `published_at` (ISO 8601 vaqt (`timestamptz`), davlat hisoboti e'lon qilingan vaqt, majburiy — 5 ish kunlik hisoblagich shundan boshlanadi) |
| Javob | `201 {id, tax_type, period, status: "uploaded", deadline_at}` — `deadline_at = min(published_at + 5 ish kuni, hisobot topshirish muddati)` (US-M10-02). Eslatmalar (M18 `state_report_diff`) — `published_at`dan **1-, 3-, 4-ish kuni**, `deadline_at`dan keyingi eslatma yuborilmaydi (qaror #50) |
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
| Javob | `{id, status: "match"\|"diff_found", diff_count, state_amount, our_amount, diff_amount, tolerance_amount}` — `status="diff_found"` faqat `abs(diff_amount) > tenants.settings.vat_diff_tolerance_amount` (standart `"1000.00"`, ichki UX chegarasi, qaror #50) bo'lsa; chegaradan kichik farqlar ham `diffs` ro'yxatida ko'rsatiladi. `our_amount` faqat `tax_type` = `vat`/`turnover` uchun hisoblanadi; boshqa turlarda `our_amount`, `diff_amount` — `null`, holat `compared` (solishtirilmaydi) |
| Xatolar | `DOC_INVALID_STATE` (status allaqachon `correction_sent`/`confirmed`/`auto_accepted` bo'lsa qayta solishtirish rad etiladi) |
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
| Javob | `{id, tax_type, period, status, published_at, deadline_at, state_amount, our_amount, diff_amount, file_url, correction_sent_at, correction_comment, correction_portal_ref, confirmed_at, confirmed_by}` — `status`: `uploaded\|compared\|match\|diff_found\|correction_sent\|confirmed\|auto_accepted` |
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

### 7a. `POST /state-reports/{id}/confirm`

| | |
|---|---|
| Maqsad | Davlat hisobotini tasdiqlangan deb qayd etish (farq yo'q yoki tolerance ichida) — BO-10 "Tasdiqlangan deb belgilash" |
| Ruxsat | `tax.correction.submit` — Buxgalter va Egasi (`15-xavfsizlik-va-audit.md` §2.2) |
| So'rov | `{comment?: string (≤1000)}` |
| Javob | `200 {id, status: "confirmed", confirmed_at}` — `confirmed_by` = joriy foydalanuvchi |
| Xatolar | `VALIDATION_ERROR`, `DOC_INVALID_STATE` (holat `match` yoki `diff_found` (`abs(diff_amount)` tolerance ichida) emas) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M10-02; BO-10; audit: `tax.correction.submit` (`15-xavfsizlik-va-audit.md` §6.1) |

### 8. `POST /state-reports/{id}/correction`

| | |
|---|---|
| Maqsad | Kabinetda kiritilgan tuzatishni qayd etish (imzosiz) — tuzatishning o'zi my.soliq.uz kabinetida kiritiladi, tizim faqat qayd etadi |
| Ruxsat | `tax.correction.submit` — Buxgalter va Egasi (`15-xavfsizlik-va-audit.md` §2.2) |
| So'rov | `{comment: string (majburiy, ≤1000), portal_ref?: string}` → `state_reports.correction_comment`, `correction_portal_ref` |
| Javob | `200 {id, status: "correction_sent", correction_sent_at}` |
| Xatolar | `VALIDATION_ERROR`, `DOC_INVALID_STATE` (holat `diff_found` emas yoki tuzatish allaqachon qayd etilgan) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M10-02; BO-10; audit: `tax.correction.submit` (`15-xavfsizlik-va-audit.md` §6.1) |

### Soliq hisob-kitobi hujjati (`tax_settlements`)

> Hujjat jadvali `tax_settlements` (`doc_sequences` kodi `ST`, `12-db-sxema.md`). Standart uch bosqichli hujjat (`17-api-umumiy.md` §9: `draft → post → cancel`); **faqat back-office**, sync voqeasi yo'q. `tax_kind`: `vat_offset` — davr kirim QQSni hisob-kitobga olish, `Dt 6410 / Kt 4410` (`13-provodka-qoidalari.md` §2.26); `turnover_tax` — aylanma solig'ini hisoblash, `Dt {expense_account} / Kt 6410` (§4.3; `expense_account` = `tenants.settings.turnover_tax_account`, standart `9430`, muqobil `9820` — buxgalter tasdiqlaydi). Byudjetga to'lov — alohida `expenses` (`tax_type`, `Dt 6410 / Kt 5110`, M15).

`TaxSettlement` obyekti: `{id, number, branch_id, doc_date, status ("draft"|"posted"|"cancelled"), tax_kind ("vat_offset"|"turnover_tax"), period ("YYYY-MM"), base_amount, rate, amount, expense_account, comment, created_by, created_at, posted_at, cancelled_at, cancel_reason}` — pul o'nlik satr; `expense_account` faqat `turnover_tax` da.

#### 8a. `GET /tax-settlements`

| | |
|---|---|
| Maqsad | Soliq hisob-kitobi hujjatlari ro'yxati (BO-07) |
| Ruxsat | `tax.vat.view` |
| So'rov | Cursor; filtr `?tax_kind=&period=&status=&branch_id=` |
| Javob | `{items: [TaxSettlement], next_cursor}` |
| Xatolar | `VALIDATION_ERROR`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish |
| Bog'langan | US-M10-01; BO-07 |

#### 8b. `POST /tax-settlements`

| | |
|---|---|
| Maqsad | Davr uchun qoralama — summani **server hisoblaydi**: `vat_offset` — `base_amount`/`amount` = davr `vat_moves` (`kind=input`, hisobga olinadigan, `pending_credit_*` dan tashqari); `turnover_tax` — `base_amount` = `turnover_base`, `rate` = `turnover_rate_pct`, `amount = base_amount × rate / 100` (`GET /reports/vat-summary` bilan bir xil hisob) |
| Ruxsat | `accounting.post` |
| So'rov | `{tax_kind: "vat_offset"\|"turnover_tax" (majburiy, tenant rejimiga mos), period: "YYYY-MM" (majburiy), branch_id: UUID (faqat `tax_kind='turnover_tax'` da majburiy — aylanma solig'i filial bo'yicha, SK 468-modda 2-qism; `vat_offset` da yuborilmaydi — server `branches.is_default = true` filialini yozadi), doc_date: date (standart — davrning oxirgi kuni), comment?: string}` — summa maydonlari tanadan qabul qilinmaydi. `vat_offset` — (tenant, davr) bo'yicha, `vat_moves` tenant bo'yicha yig'iladi (qaror #31 — 1 tenant = 1 STIR) |
| Javob | `201 TaxSettlement` (`status="draft"`) |
| Xatolar | `VALIDATION_ERROR` (`tax_kind` davrdagi `tenant_tax_regimes`ga mos emas; `vat_offset` — (tenant, davr), `turnover_tax` — (filial, davr) uchun `draft`/`posted` hujjat allaqachon bor — `params.existing_id`; `vat_offset` da `branch_id` yuborilgan), `PERIOD_CLOSED`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M10-01; BO-07; audit |

#### 8c. `POST /tax-settlements/{id}/post`

| | |
|---|---|
| Maqsad | O'tkazish: `vat_offset` → `Dt 6410 / Kt 4410 = amount` (§2.26); `turnover_tax` → `Dt {expense_account} / Kt 6410 = amount` (§4.3). Server summani `post` paytida qayta hisoblaydi; qoralamadan farq qilsa — yangilangan summa bilan o'tkaziladi va javobda `recalculated: true` |
| Ruxsat | `accounting.post` |
| So'rov | `{}` |
| Javob | `200 TaxSettlement` (`status="posted"`, `posted_at`) + `recalculated: bool` |
| Xatolar | `DOC_NOT_DRAFT`, `PERIOD_CLOSED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M10-01; BO-07; audit majburiy |

#### 8d. `POST /tax-settlements/{id}/cancel`

| | |
|---|---|
| Maqsad | Bekor qilish: `posted` — storno (`13-provodka-qoidalari.md` §5.2); `draft` — provodkasiz `cancelled`. Yopilgan davrdagi hujjat ham bekor qilinadi — storno joriy ochiq davr sanasida |
| Ruxsat | `accounting.post` |
| So'rov | `{reason: string (majburiy)}` |
| Javob | `200 TaxSettlement` (`status="cancelled"`) |
| Xatolar | `DOC_ALREADY_CANCELLED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-07; audit majburiy |

---

## M11 — Buxgalteriya

### 9. `GET /ledger-entries`

| | |
|---|---|
| Maqsad | Buxgalteriya jurnali (`ledger_entries`) — hisob rejasi bo'yicha filtr (`13-provodka-qoidalari.md` §1) |
| Ruxsat | `accounting.post` |
| So'rov | Cursor; filtr `?account_dt=&account_kt=&entry_date__gte=&entry_date__lte=&branch_id=&doc_type=&doc_id=` (filtr maydonlari ustun nomi bilan bir xil: `entry_date__*`, `branch_id`); filial cheklangan foydalanuvchi faqat o'z filiallari qatorlarini ko'radi (`branch_id` boshqa filial — `403 BRANCH_SCOPE_DENIED`) |
| Javob | `{items: [{id, entry_date, account_dt, account_kt, amount, branch_id, doc_type, doc_id, doc_number, analytics, reversal_of_id}], next_cursor}` (`doc_number` — hujjat raqami, bo'lmasa `null`) |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish (kesh) |
| Bog'langan | US-M11-01; BO-08 |

### 10. `POST /ledger-adjustments`

> Mustaqil hujjat jadvali `ledger_adjustments` (`doc_sequences` kodi `BX`) — `ledger_entries.doc_type/doc_id NOT NULL` har doim shu hujjatga ishora qiladi. **Bir bosqichli hujjat** (`17-api-umumiy.md` §9) — darhol `status="posted"` qaytaradi, `draft` bosqichi yo'q.

| | |
|---|---|
| Maqsad | Yopilgan davrdagi xatoni **joriy ochiq davrda** tuzatuvchi qo'lda yozuv (append-only, `13-provodka-qoidalari.md` §5.1) |
| Ruxsat | `accounting.post` |
| So'rov | `{branch_id: UUID (majburiy), doc_date (joriy ochiq davrda bo'lishi shart — `entry_date` emas; istisno: `account_dt` yoki `account_kt` = `0000` bo'lsa `go_live_date − 1` ruxsat, agar o'sha davr yopilmagan bo'lsa), account_dt, account_kt, amount, comment (majburiy), correction_of_period ("YYYY-MM", ixtiyoriy — qaysi yopilgan davrga tegishli), analytics (obyekt, ixtiyoriy — `ledger_entries.analytics` o'lchamlari: `counterparty_id`, `product_id`, `payment_method` va h.k., `13-provodka-qoidalari.md` §1)}` |
| Javob | `201 {id, status: "posted", branch_id, doc_date, account_dt, account_kt, amount, correction_of_period, analytics}` |
| Xatolar | `VALIDATION_ERROR`, `PERIOD_CLOSED` (`doc_date` yopilgan davrda bo'lsa), `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08; audit: `ledger_entries.manual_adjustment` majburiy |

### 10a. `POST /ledger-adjustments/{id}/cancel`

| | |
|---|---|
| Maqsad | Tuzatuvchi yozuvni bekor qilish (storno — alohida teskari hujjat yo'q, `01-qarorlar.md` #6). Yopilgan davrdagi hujjat ham bekor qilinadi — storno joriy ochiq davr sanasida (`13-provodka-qoidalari.md` §5.2) |
| Ruxsat | `accounting.post` |
| So'rov | `{reason: string (majburiy)}` |
| Javob | `200 {id, status: "cancelled", cancelled_at}` |
| Xatolar | `DOC_ALREADY_CANCELLED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08; audit majburiy |

### 10b. `GET /ledger-adjustments`

| | |
|---|---|
| Maqsad | Qo'lda kiritilgan tuzatuvchi yozuvlar ro'yxati |
| Ruxsat | `accounting.post` |
| So'rov | Cursor; filtr `?doc_date__gte=&doc_date__lte=&status=&branch_id=` |
| Javob | `{items: [{id, branch_id, doc_date, account_dt, account_kt, amount, correction_of_period, analytics, status, comment}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08 |

### 11. `GET /reports/trial-balance`

| | |
|---|---|
| Maqsad | Aylanma-saldo vedomosti (oborot-saldo) — har hisob bo'yicha boshlang'ich/aylanma/yakuniy qoldiq |
| Ruxsat | `reports.finance.view` |
| So'rov | `?period=2026-10&branch_id=` (`branch_id` bo'lmasa — konsolidatsiya, `13-provodka-qoidalari.md` §5.4) |
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
| Javob | `{period, revenue, returns, discounts, cogs, gross_profit, expenses_by_category: [{category, amount}], net_profit}` — `revenue` = `Kt 9020` aylanmasi; `returns` = `Dt 9040`; `discounts` = `Dt 9050` (`discount_posting='net'` rejimida — Σ `sale_lines.discount_amount` QQSsiz); `cogs` = `Dt 9120` (`13-provodka-qoidalari.md` §1) |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M11-03, US-M15-03; BO-02, BO-09 |

### 13. `GET /reports/balance-sheet`

| | |
|---|---|
| Maqsad | Balans hisoboti (aktiv/passiv/kapital, `13-provodka-qoidalari.md` §1 hisoblar bo'yicha) |
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
| Maqsad | Davrni yopish (`period_closings` yozuvi, 13-provodka-qoidalari.md §5.1) |
| Ruxsat | `accounting.period.close` |
| So'rov | `{period: "YYYY-MM"}` |
| Javob | `201 {period, closed_at, closed_by}` |
| Xatolar | `PERIOD_ALREADY_CLOSED` (davr allaqachon yopilgan), `PERIOD_CLOSE_OUT_OF_ORDER` (`409` — faqat **eng eski ochiq oy** yopiladi), `PERIOD_CLOSE_NOT_READY` (16-endpoint `blockers[]` bo'sh emas: `recost_pending`, `fiscal_pending`, `devices_unsynced`; `warnings[]` yopishni bloklamaydi) — davr yopilgach **qayta ochilmaydi** (qaror #23 — tavsiya #15); keyingi tuzatish faqat `POST /ledger-adjustments` (10-endpoint) bilan joriy ochiq davrda |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08; audit majburiy |

### 16. `GET /period-closings/{period}/readiness`

| | |
|---|---|
| Maqsad | Davrni yopishdan oldin tekshiruv (`23-backend-arxitekturasi.md` §2.4) |
| Ruxsat | `accounting.post` |
| So'rov | — (`period` path parametri `YYYY-MM`) |
| Javob | `{period, ready: bool, blockers: ["recost_pending"\|"fiscal_pending"\|"devices_unsynced"], warnings: ["tax_settlement_missing"\|"opening_0000_nonzero"\|"open_shifts"\|"drafts_in_period"\|"devices_not_synced_after_period_end"], pending_recost_jobs: int, pending_fiscal_receipts: int, unsynced_devices: [{device_id, cash_register_name, outbox_pending_count, outbox_oldest_pending_at}], opening_balance_unresolved: bool}` — `ready = (blockers = [])`. Shartlar: `recost_pending` (bloker) — `recost_jobs.status IN ('queued','running','failed') AND from_date ≤ period_end`; `fiscal_pending` (bloker) — davr cheklari `fiscal_receipts.status IN ('pending','sent','failed')`; `devices_unsynced` (bloker) — `devices.kind IN ('web','android') AND revoked_at IS NULL AND outbox_pending_count > 0 AND outbox_oldest_pending_at < period_end + 1 kun` (hal qilish — sinxronlash yoki qurilmani bekor qilish, `confirm_pending_loss`, `16-offline-sync.md` §9); `devices_not_synced_after_period_end` (ogohlantirish) — faol qurilmaning `last_sync_at < period_end + 1 kun`. Yopilgan davrga kech kelgan POS voqealari rad etilmaydi — registr yozuvlari birinchi ochiq davrda (`16-offline-sync.md` §3.4, qaror #69) |
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
| Maqsad | Savdo hisoboti — filial/davr bo'yicha jami savdo, chek soni, o'rtacha chek. `total_sales = Σ sales.total_amount (posted) − Σ returns.total` |
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
| Maqsad | Qarzdorlik "yosh" guruhlari (0-30 / 31-60 / 60+ kun), BO-06/BO-09 uchun manba. **Yagona/kanonik endpoint** (`18-api-kassa.md` §12.8 shu yerga havola qiladi); BO-04 "Men qarzdorman" tabi ham `direction=payable` bilan shu yerdan foydalanadi |
| Ruxsat | `reports.finance.view` **yoki** `debts.approve` |
| So'rov | `?direction=receivable\|payable&as_of=2026-10-15&branch_id=&bucket=0-30\|31-60\|60+&limit_exceeded_offline=` |
| Javob | `{rows: [{counterparty_id, name, balance, due_date, overdue_since, days_overdue, bucket: "0-30"\|"31-60"\|"60+", doubtful_flag: bool, limit_exceeded_offline: bool}]}` — `overdue_since = min(COALESCE(due_date, doc_date))` kontragentning ochiq hujjatlari bo'yicha; `due_date` — shu eng eski ochiq hujjat muddati (yo'q bo'lsa `null`); `days_overdue = max(0, as_of − overdue_since)`; `bucket` shundan |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish |
| Bog'langan | US-M12-01; BO-06, BO-09 |

### 22. `POST /reports/{report-kod}/export`

| | |
|---|---|
| Maqsad | Yuqoridagi hisobotlarning (shuningdek M10'dagi) Excel/PDF eksporti — asinxron job (`17-api-umumiy.md` §13) |
| Ruxsat | `reports.export` |
| So'rov parametrlari (path) | `report-kod` ∈ `{sales, top-products, stock, debts-aging, trial-balance, profit-and-loss, balance-sheet, vat-summary, ledger-entries, cash-history, state-report-diffs, vat-moves}` (so'nggi to'rttasi — BO-08/BO-09/BO-10 eksporti, US-M12-03/US-M16-03) |
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

> Foydalanuvchi (xodim) CRUD, taklif/bloklash/parol-PIN tiklash, sessiya/qurilma boshqaruvi — **`14-autentifikatsiya-oauth2.md` §18.2'da allaqachon to'liq**: `POST /admin/users`, `PATCH /admin/users/{id}`, `POST /admin/users/{id}/reset-pin`, `POST /admin/users/{id}/reset-password`, `POST /admin/users/{id}/revoke-sessions`, `POST /admin/users/{id}/sessions/{session_id}/revoke` (bitta sessiya), `GET /admin/users/{id}/sessions`, `GET /admin/users/{id}/devices`. Bu fayl ularni takrorlamaydi. Quyida **rol/ruxsat/limit** boshqaruvi (`15-xavfsizlik-va-audit.md` §2.1–2.2 katalogiga mos) va tenant kesimidagi qurilmalar ro'yxati — BO-11 «Qurilmalar» tabi (29a/29b, qaror #56).

### 24. `GET /roles`

| | |
|---|---|
| Maqsad | Rollar ro'yxati (5 standart + tenant maxsus rollari) |
| Ruxsat | `settings.users` |
| So'rov | Page pagination |
| Javob | `{items: [{id, name, is_system, system_code: "owner"\|"manager"\|"cashier"\|"storekeeper"\|"accountant"\|null, version}], total, page, size}` — tizim rolini nom emas, `system_code` bo'yicha aniqlang |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan ro'yxat (huquqlar faqat online o'zgaradi, `03-modullar-talablari.md` M13) |
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
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT`, `409 {code:"SYSTEM_ROLE_READONLY"}` (`is_system=true` bo'lsa nom o'zgartirish rad etiladi — faqat shu bitta kod) |
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
| Offline | Oxirgi sinxronlangan (huquq tekshiruvi uchun qurilmada keshlanadi, `16-offline-sync.md` §2) |
| Bog'langan | US-M13-03; BO-11 |

### 28. `PUT /roles/{id}/permissions`

| | |
|---|---|
| Maqsad | Rolning to'liq ruxsat/limit to'plamini almashtirish (standart limitlar — `15-xavfsizlik-va-audit.md` §2.3) |
| Ruxsat | `settings.users` |
| So'rov | `{permissions: [{code: string (kod — `15-xavfsizlik-va-audit.md` §2.1 ro'yxatidan), limit_value: string\|null (pul/foiz, kod `discount.give`/`returns.approve`/`cash.withdraw` kabi limitli kodlarda)}]}` |
| Javob | `200 {role_id, permissions: [...]}` |
| Xatolar | `VALIDATION_ERROR` (noma'lum kod yoki limit talab qilinmaydigan kodga limit berilsa; Egasi roli — `field="permissions"`, `validation.owner_role_readonly`; faqat-Egasi kodi boshqa rolga — `validation.owner_only_permission`). `version` tanada yo'q — har muvaffaqiyatli PUT `roles.version` ni oshiradi (17 §8 dan istisno: to'plam to'liq almashtiriladi) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M13-03; BO-11; audit: huquq/limit o'zgarishi majburiy (`15-xavfsizlik-va-audit.md` §6.1) |

### 29. `GET /permissions-catalog`

| | |
|---|---|
| Maqsad | To'liq ruxsat kodlari katalogi (statik, kod ichidan — `11-malumotlar-modeli.md` §3: "permissions (kod ichida, jadval emas)") |
| Ruxsat | `settings.users` |
| So'rov | — |
| Javob | `{items: [{code, module, description, requires_limit: bool}]}` — `15-xavfsizlik-va-audit.md` §2.1 bilan bir xil ro'yxat |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Statik, frontend bundle'da keshlanishi mumkin |
| Bog'langan | US-M13-03; BO-11 |

### 29a. `GET /devices`

| | |
|---|---|
| Maqsad | BO-11 «Qurilmalar» tabi (qaror #56): tenantning barcha qurilmalari — oxirgi sinxron va sinxronlanmagan voqealar soni bilan (`14-autentifikatsiya-oauth2.md` §18.2 `GET /admin/users/{id}/devices` — xodim kesimidagi ko'rinish, bu — tenant kesimi) |
| Ruxsat | `devices.revoke` (Egasi, Menejer — qaror #56) |
| So'rov | Page pagination; filtr `?branch_id=&kind=web\|android\|onec_agent&include_revoked=false` |
| Javob | `{items: [{id, kind, app_version, cash_register_id, cash_register_name, branch_id (kassa orqali), last_seen_at, last_sync_at, outbox_pending_count, outbox_oldest_pending_at, has_pending: bool, revoked_at}], total, page, size}` — `onec_agent` qurilmalari faqat ko'rinadi, bekor qilish — `33-1c-integratsiya.md` §10 |
| Xatolar | `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M13-07; BO-11; `16-offline-sync.md` §9 |

### 29b. `POST /devices/{id}/revoke`

| | |
|---|---|
| Maqsad | Qurilmani bekor qilish: `devices.revoked_at`, qurilmaning refresh/access/litsenziya tokenlari bekor, shu qurilmada PIN bilan kirgan xodimlar PIN'i majburiy almashtiriladi (`16-offline-sync.md` §9, `14-autentifikatsiya-oauth2.md` §7/§17). Sinxronlanmagan voqea bo'lsa (`has_pending=true`) — `confirm_pending_loss=true` talab qilinadi; UI avval qurilmada `sync.drain`ni taklif qiladi (qaror #56) |
| Ruxsat | `devices.revoke` (Egasi, Menejer — qaror #56) |
| So'rov | `{reason: string (majburiy), confirm_pending_loss: bool (standart false)}` |
| Javob | `200 {id, revoked_at, outbox_pending_count}` |
| Xatolar | `NOT_FOUND`, `VALIDATION_ERROR` (`has_pending=true` va `confirm_pending_loss=false` — `details[].field="confirm_pending_loss"`, `params.outbox_pending_count`), `409 {code:"RESOURCE_ARCHIVED"}` (allaqachon bekor qilingan); `kind='onec_agent'` qurilma — `VALIDATION_ERROR` (`field="id"`, `validation.onec_agent_device`; bekor qilish — `33-1c-integratsiya.md` §10) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M13-07; BO-11; audit majburiy |

---

## M14 — Filiallar

### 30. `GET /branches`

| | |
|---|---|
| Maqsad | Filiallar ro'yxati (`memberships.branch_ids` bo'yicha cheklangan) |
| Ruxsat | `—` (auth yetarli; natija `branch_ids` bo'yicha filtrlanadi) |
| So'rov | Page pagination |
| Javob | `{items: [{id, name, code, address, is_default, settlement_category, activity_type, version}], total, page, size}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan (`GET /sync/pull?scope=catalog`) |
| Bog'langan | US-M14-01; BO-12 |

### 31. `POST /branches`

| | |
|---|---|
| Maqsad | Yangi filial yaratish (US-M14-03) — avtomatik 1 ombor (`warehouse.type` bo'yicha tovar hisobi bilan) + sozlamalar bo'yicha kassa talabi |
| Ruxsat | `settings.branches` |
| So'rov | `{name: string (majburiy), address: string, code: string (ixtiyoriy — bo'sh bo'lsa server keyingi bo'sh ikki xonali raqamni beradi), settlement_category: "city_100k_plus"\|"other"\|"remote_mountain" (standart: `city_100k_plus`, US-M14-04), activity_type: "retail"\|"other", warehouse?: {type: "store"\|"stock"} (standart `store`)}` — server `warehouses.inventory_account` ni `type` dan qo'yadi: `store` (savdo zali) → `2920`, `stock` (ombor) → `2910` |
| Javob | `201 {id, name, address, code, settlement_category, activity_type, version: 1, warehouse: {id, type, inventory_account}}` — birga `warehouses` yozuvi avtomatik yaratiladi (MVP: 1 ombor/filial); `code` hujjat raqamidagi filial kodi (`11-malumotlar-modeli.md`). `settlement_category` yuborilmasa standart `city_100k_plus` qo'yiladi — UI shu holatda Egasiga "toifani tekshiring" eslatmasini ko'rsatadi (US-M14-04, QT-M14-04); kassalar alohida `POST /cash-registers` bilan |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M14-03, US-M14-04; BO-12 |

### 32. `GET /branches/{id}`

| | |
|---|---|
| Maqsad | Filial tafsiloti + konsolidatsiyalangan qisqa hisob (savdo/qoldiq): `today_sales` — bugungi (Toshkent) `doc_date` bilan o'tkazilgan `sales.total_amount` yig'indisi, `stock_value` — filial omborlari `stock_balances.value` yig'indisi |
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
| So'rov | `{name?, address?, settlement_category?, activity_type?, version: int (majburiy)}` — `activity_type` yoki `settlement_category` o'zgarsa `branch_tax_settings` ga `(branch_id, valid_from)` bo'yicha upsert (`valid_from` = joriy oyning 1-sanasi; bir oyda ikki marta o'zgarsa — oxirgisi amal qiladi, US-M14-04) |
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
| So'rov | `{valid_from: date (majburiy, oyning 1-sanasi; o'tgan oyga yozib bo'lmaydi), settlement_category, activity_type}` — `(branch_id, valid_from)` bo'yicha upsert (shu `valid_from` qatori bor bo'lsa — oxirgisi amal qiladi) |
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
| Javob | `{items: [{id, branch_id, name, type, inventory_account: "2910"\|"2920", version}]}` — sahifasiz ro'yxat `{items}` (`17-api-umumiy.md` §4 istisnosi); `inventory_account`: savdo zali (do'kon) — `2920`, ombor — `2910` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan (catalog scope) |
| Bog'langan | US-M14-01; BO-03, BO-12 |

### 37a. `PATCH /warehouses/{id}`

| | |
|---|---|
| Maqsad | Ombor nomi va tovar hisobini (`inventory_account`) o'zgartirish (BO-12) |
| Ruxsat | `settings.branches` |
| So'rov | `{inventory_account?: "2910"\|"2920", name?: string, version: int (majburiy)}` |
| Javob | `200 {id, name, type, inventory_account, version}` |
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT`, `NOT_FOUND`, `BRANCH_SCOPE_DENIED`, `409 {code:"WAREHOUSE_ACCOUNT_LOCKED"}` (omborda `stock_moves` bor — `inventory_account` o'zgartirilmaydi; `name` o'zgarishi ruxsat) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M14-01; BO-12; audit majburiy |

### 38. `GET /cash-registers`

| | |
|---|---|
| Maqsad | Kassalar ro'yxati (filial bo'yicha, obuna limiti bilan bog'liq — M17) |
| Ruxsat | `—` (branch scope) |
| So'rov | `?branch_id=&include_archived=false` |
| Javob | `{items: [{id, branch_id, name, kind, fiscal_module_id, txkm_contract_ref, fiscal_agent_id, fiscal_local_device_id, ofd_status, fm_state: "ok"\|"locked"\|"ack_overdue"\|"memory_full"\|"unknown", last_unacked_receipt_at, fm_receipts_pending, tax_registered_at, archived_at, version}]}` — sahifasiz ro'yxat `{items}` (`17-api-umumiy.md` §4 istisnosi); `fm_state != "ok"` bo'lsa POS sotuvi `FISCAL_DEVICE_LOCKED` bilan to'xtaydi; `last_unacked_receipt_at` 48 soatdan oshsa — `FISCAL_OFFLINE_48H_BLOCKED` (`18-api-kassa.md`, qaror #43) |
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
| Javob | `201 {id, branch_id, name, kind, ofd_status: "pending", version: 1}` |
| Xatolar | `VALIDATION_ERROR`, `ADDON_REQUIRED` (faol kassa soni limitdan oshadi — `tenant_addons.extra_register` sotib olinmagan) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M14-03, US-M17-02; BO-12 |

### 40. `PATCH /cash-registers/{id}`

| | |
|---|---|
| Maqsad | Kassani tahrirlash (nomi, lokal fiskal ko'prik agenti); arxivlash — alohida 40i |
| Ruxsat | `cash_register.manage` (`fiscal_agent_id`/`fiscal_local_device_id` — `settings.branches`) |
| So'rov | `{name?: string, fiscal_agent_id?: UUID\|null, fiscal_local_device_id?: string\|null, version: int (majburiy)}` — `fiscal_agent_id` (lokal ko'prik kassasiga xizmat qiluvchi Do'kon agenti, `onec_agents.id`) va `fiscal_local_device_id` (agent `capabilities.fiscal.devices[].local_id`) birga beriladi yoki birga `null` qilinadi (qaror #66); BO-12 kassa qatoridagi "Fiskal agent" `Select` |
| Javob | `200 {id, name, fiscal_agent_id, fiscal_local_device_id, version}` |
| Xatolar | `VALIDATION_ERROR` (`fiscal_agent_id` va `fiscal_local_device_id` juftligi buzilgan; agent topilmadi yoki `local_id` agent `capabilities` da yo'q), `VERSION_CONFLICT`, `409 {code:"RESOURCE_ARCHIVED"}` (arxivlangan kassa — `17-api-umumiy.md` §15) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M17-02 (chekka holat — qo'shimcha kassa kamaytirish); BO-12, BO-19 |

---

## M13a/M14 — Tenant sozlamalari va integratsiya kalitlari

> BO-14 ekraniga mos bo'lim. Ruxsat — `settings.tenant` (**faqat Egasi**); istisnolar har endpointda ko'rsatilgan (`vat_diff_tolerance_amount` — Buxgalter ham; sinxron istisnolari — Buxgalter ham).

`TenantSettings` obyekti (`tenants` ustunlari + `tenants.settings` JSONB kalitlari, nomlar DB bilan aynan):

| Maydon | Qiymat / standart | Manba |
|---|---|---|
| `name` | do'kon nomi | `tenants.name` (interfeys tili — `users.locale`, tenant sozlamasi emas) |
| `legal_form` | `"llc"\|"jsc"\|"private_enterprise"\|"sole_proprietor"` | `tenants.legal_form` |
| `go_live_date` | sana, faqat o'qish (ro'yxatdan o'tishda yoziladi — ro'yxatdan o'tgan kun, Toshkent) | `tenants.go_live_date` |
| `accepted_terms_version`, `accepted_terms_at` | faqat o'qish (ro'yxatdan o'tishda aksept, `14-autentifikatsiya-oauth2.md`) | `tenants` |
| `settings.bank_account`, `settings.bank_mfo` | tenantning **yagona** bank hisobi (20 raqam) va MFO — MVP'da bitta hisob, `cash_moves.bank_account_id` doim `NULL` (qaror #49); ko'chirma importi (55g) shu hisob bilan solishtiradi | `tenants.settings` |
| `settings.supplier_overpay_policy` | `"warn"\|"block"`, standart `"warn"` — `warn`: ortiqcha to'lov avans 4310 (`SUPPLIER_OVERPAY_ADVANCE`), `block`: `422 SUPPLIER_OVERPAY_BLOCKED` (qaror #47, `19-api-ombor.md` §11) | `tenants.settings` |
| `settings.vat_diff_tolerance_amount` | pul satri, standart `"1000.00"` (qaror #50) | `tenants.settings` |
| `settings.marking_precheck` | `"off"\|"warn"\|"block"`, standart `"warn"` — sotuvdan oldingi markirovka tekshiruvi; `warn` — `MARKING_PRECHECK_WARNING` + audit, sotuv davom etadi; `block` — `MARKING_VERIFY_FAILED`/`MARKING_VERIFY_UNAVAILABLE` bilan rad (qaror #62) | `tenants.settings` |
| `settings.discount_posting` | `"gross_9050"\|"net"`, standart `"gross_9050"` | `tenants.settings`, `13-provodka-qoidalari.md` |
| `settings.owner_withdrawal_account` | `"4890"\|"8720"` — ta'sischi olgan pul (M16 `owner_withdrawal`); standart `legal_form` dan: `sole_proprietor` → `"8720"`, qolganlari → `"4890"` | `tenants.settings` |
| `settings.payment_org_commission_account` | `"9430"\|"9410"`, standart `"9430"` — faqat `click`/`payme`/`uzum` to'lov tashkiloti komissiyasi (55e); `card`/`uzqr` komissiyasi — doim `9430` | `tenants.settings` |
| `settings.card_manual_fallback` | `"allow"\|"manager_approval"\|"forbid"`, standart `"manager_approval"` — karta rekvizitlarini qo'lda kiritish siyosati (qaror #71, BO-12) | `tenants.settings` |
| `settings.negative_stock_policy` | `"allow"\|"block"`, standart `"allow"` — manfiy qoldiqqa chiqim siyosati (`block` — `NEGATIVE_STOCK_NOT_ALLOWED`, `19-api-ombor.md`) | `tenants.settings` |
| `settings.transfer_overdue_hours` | `int` 1..720, standart `48` — `GET /transfers` `is_overdue` chegarasi (QT-M06-05) | `tenants.settings` |
| `settings.ai_training_consent` | bool — anonimlashtirilgan ma'lumotdan AI'ni yaxshilashda foydalanishga rozilik | `tenants.settings` |
| `settings.turnover_tax_account` | `"9430"\|"9820"`, standart `"9430"` — aylanma solig'i xarajati (8c) | `tenants.settings` |
| `settings.fiscal_policy` | `{debt_receipt_split: "single"\|"per_sale" (standart "single", qaror #45), credit_sale_receipt: "none"\|"credit_type" (standart "none")}` | `tenants.settings` |
| `settings.ai_cross_border_enabled` | bool, standart `false`; **faqat 40h orqali** o'zgaradi (qaror #61) | `tenants.settings` |

### 40a. `GET /tenant/settings`

| | |
|---|---|
| Maqsad | Do'kon sozlamalari + integratsiya holati umumiy ko'rinishi |
| Ruxsat | `settings.tenant` |
| So'rov | — |
| Javob | `TenantSettings` + `{tax_regime: {current, history: [...]}, integrations: {ofd: {status}, faktura_uz: {status, connected_at}, crpt: {status, key_last4}, click: {status, connected_at}, payme: {status, connected_at}, uzum: {status, connected_at}, uzqr: {status, connected_at, cash_register_ids: [...]}}, version}` — `status`: `"connected"\|"not_connected"`; `ofd.status` `cash_registers.ofd_status` (`registered`/`active`) dan hosila; sirlar hech qachon qaytmaydi |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan |
| Bog'langan | BO-14 |

### 40b. `PATCH /tenant/settings`

| | |
|---|---|
| Maqsad | Do'kon nomi (`tenants.name`), yuridik shakli, bank hisobi va tenant siyosatlarini (`tenants.settings`) yangilash; soliq rejimi — 40c, integratsiya kalitlari — 40d, AI roziligi — 40h orqali |
| Ruxsat | `settings.tenant`; tanada faqat `settings.vat_diff_tolerance_amount` bo'lsa — `tax.compare.review` ham yetarli (Buxgalter, qaror #50) |
| So'rov | `{name?, legal_form?, settings?: {bank_account?, bank_mfo?, supplier_overpay_policy?, vat_diff_tolerance_amount?, marking_precheck?, discount_posting?, owner_withdrawal_account?, payment_org_commission_account?, turnover_tax_account?, negative_stock_policy?, transfer_overdue_hours?, card_manual_fallback?, ai_training_consent?, fiscal_policy?: {debt_receipt_split?, credit_sale_receipt?}}, version: int (majburiy)}` — qisman yangilash (merge); `ai_cross_border_enabled`, `go_live_date`, `accepted_terms_*` qabul qilinmaydi |
| Javob | `200 TenantSettings` |
| Xatolar | `VALIDATION_ERROR` (enum tashqarisidagi qiymat, `vat_diff_tolerance_amount < 0`, `bank_account` 20 raqam emas, `bank_mfo` 5 raqam emas, `ai_cross_border_enabled`/`go_live_date`/`accepted_terms_*` tanada), `VERSION_CONFLICT` (`params.current_version`) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; audit majburiy |

### 40c. `POST /tenant/tax-regimes`

| | |
|---|---|
| Maqsad | Soliq rejimini (QQS/aylanma) o'zgartirish — faqat keyingi oy 1-sanasidan kuchga kiradi |
| Ruxsat | `settings.tenant` |
| So'rov | `{regime: "vat"\|"turnover", valid_from: date (aynan keyingi oyning 1-sanasi, Toshkent vaqti)}` |
| Javob | `201 {regime, valid_from}` |
| Xatolar | `VALIDATION_ERROR` (`valid_from` noto'g'ri sana) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; audit majburiy |

### 40d. `PUT /tenant/integrations/{provider}`

> `provider` ∈ `faktura-uz`, `crpt`, `click`, `payme`, `uzum`, `uzqr` → `tenant_secrets.kind` (`faktura_uz`, `crpt`, `click`, `payme`, `uzum`, `uzqr`). Sotuv to'lovlari merchant'i — **tenantning o'zi** (pul to'g'ridan-to'g'ri do'konga tushadi); platforma merchant kaliti faqat M17 billing uchun, bu endpoint orqali kiritilmaydi (qaror #46). `fiscal_partner`, `eimzo` sirlari — platforma boshqaradi (deploy konfiguratsiyasi), tenant API'si yo'q.

| | |
|---|---|
| Maqsad | Integratsiya kalitlarini kiritish/yangilash |
| Ruxsat | `settings.tenant` |
| So'rov | `faktura-uz`: `{login, password, client_id, client_secret}` (tenantning o'z Faktura.uz hisobi va kabinetida yaratilgan API mijozi); `crpt`: `{api_key}` (`crpt_api_key`, faqat qabul/tekshiruv/qaytarish/hisobdan chiqarish uchun — sotuvda kod fiskal chek ichida OFD orqali ketadi, qaror #62); `click`: `{merchant_id, service_id, secret_key, provider_autofiscal_disabled_confirmed: true}`; `payme`: `{merchant_id, key, provider_autofiscal_disabled_confirmed: true}`; `uzum`: `{merchant_id, login, password, provider_autofiscal_disabled_confirmed: true}` (webhook Basic Auth) — `click`/`payme`/`uzum` da `provider_autofiscal_disabled_confirmed: true` majburiy (provayder kabinetida avtofiskalizatsiya o'chirilganini tasdiqlash; server `settings.payment_providers.{provider}.autofiscal_off_confirmed_at = now()` yozadi); `uzqr`: `{cash_register_id?: UUID, merchant_id, terminal_id}` (`tenant_secrets.cash_register_id` — har kassa uchun alohida; statik QR hozir, dinamik QR — `UzqrPort` stub, qaror #64). Hammasi `tenant_secrets.ciphertext` da konvert-shifrlangan (KEK — o'z sir ombori, qaror #65), javobda hech qachon qaytmaydi |
| Javob | `200 {provider, status: "connected", connected_at}` — server provayderda tekshiradi (Faktura.uz — token olish, CRPT — kalit tekshiruvi, to'lov provayderlari — test so'rovi mavjud bo'lsa) |
| Xatolar | `503 {code:"EINVOICE_PROVIDER_UNAVAILABLE"}` (faktura-uz) / `503 {code:"MARKING_VERIFY_UNAVAILABLE"}` (crpt), `VALIDATION_ERROR` (noma'lum `provider`, maydon yetishmaydi, `cash_register_id` boshqa tenantniki, `click`/`payme`/`uzum` da `provider_autofiscal_disabled_confirmed` yo'q yoki `false`), `NOT_FOUND` (`cash_register_id`) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; `21-integratsiyalar.md` §2/§4/§9; audit majburiy (sir qiymatisiz) |

### 40e. `DELETE /tenant/integrations/{provider}`

| | |
|---|---|
| Maqsad | Integratsiyani uzish (`provider` — 40d ro'yxati; `uzqr` uchun `?cash_register_id=`) |
| Ruxsat | `settings.tenant` |
| So'rov | — |
| Javob | `204` |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; audit majburiy |

### 40f. `GET /sync-exceptions`

| | |
|---|---|
| Maqsad | BO-14 «Sinxron istisnolari» ro'yxati (qaror #56): offline sinxronda qabul qilingan, lekin ko'rib chiqishni talab qiladigan hodisalar (`sync_exceptions`, `16-offline-sync.md` §5 — chekdagi «qotirilgan» narx serverdagidan farq qiladi, sotuv vaqtida arxivlangan tovar va h.k.). Provodkaga ta'sir qilmaydi |
| Ruxsat | `settings.tenant` **yoki** `accounting.post` |
| So'rov | Cursor; filtr `?reviewed=true\|false&branch_id=&device_id=&created_at__gte=&created_at__lte=` |
| Javob | `{items: [{id, kind, device_id, branch_id, doc_type, doc_id, details, created_at, reviewed_at, reviewed_by, review_note}], next_cursor}` — `branch_id` hosila (`devices.cash_register_id → cash_registers.branch_id`; `sync_exceptions`da ustun yo'q) |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | BO-14; `16-offline-sync.md` §5 |

### 40g. `POST /sync-exceptions/{id}/review`

| | |
|---|---|
| Maqsad | Istisnoni «Ko'rib chiqildi» deb belgilash — `reviewed_at`, `reviewed_by`, `review_note` yoziladi; provodka/hujjat o'zgarmaydi (qaror #56) |
| Ruxsat | `settings.tenant` **yoki** `accounting.post` |
| So'rov | `{review_note: string (majburiy, 1–500 belgi)}` |
| Javob | `200 {id, reviewed_at, reviewed_by, review_note}` |
| Xatolar | `NOT_FOUND`, `VALIDATION_ERROR` (`review_note` bo'sh), `DOC_INVALID_STATE` (allaqachon ko'rib chiqilgan) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; audit majburiy |

### 40h. `POST /tenant/consents`

| | |
|---|---|
| Maqsad | Egasi tomonidan AI provayderiga (chegaradan tashqari) ma'lumot uzatish roziligini qabul qilish yoki qaytarib olish: `consents` yozuvi (`subject='tenant'`, `user_id`, `purpose`, `terms_version`, `accepted`, `ip`, `at`; append-only) + `tenants.settings.ai_cross_border_enabled` (qaror #61). Rozilik berilmaguncha AI-03 rasmlari yuborilmaydi (`AI_CONSENT_REQUIRED`); AI'ga yuboriladigan matnda shaxsiy maydonlarni maskalash rozilikdan qat'i nazar majburiy |
| Ruxsat | `settings.tenant` (**faqat Egasi**) |
| So'rov | `{purpose: "ai_cross_border" (majburiy), terms_version: string (majburiy — joriy `terms_versions` versiyasi), accepted: bool (majburiy; `false` — qaytarib olish)}` |
| Javob | `201 {purpose, terms_version, accepted, at, ai_cross_border_enabled}` (`at` = `consents.at`) |
| Xatolar | `VALIDATION_ERROR` (noma'lum `purpose`; `terms_version` joriy versiya emas — `params.current_version`; joriy versiya = `platform.terms_versions` dagi `kind = purpose` (`ai_cross_border`), `is_current` qatori, `GET /auth/terms`) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; AI-01/AI-03; `22-ai-qatlami.md` §7; audit majburiy (`ip` bilan) |

### 40i. `POST /cash-registers/{id}/archive`

> M14 kassa endpointi (38–40 davomi).

| | |
|---|---|
| Maqsad | Kassani arxivlash — `cash_registers.archived_at = now()`; faol kassalar sonidan chiqadi (M17 chekka holat — qo'shimcha kassa sonini kamaytirish, 60) |
| Ruxsat | `cash_register.manage` |
| So'rov | `{}` |
| Javob | `200 {id, archived_at}` |
| Xatolar | `NOT_FOUND`, `BRANCH_SCOPE_DENIED`, `409 {code:"RESOURCE_ARCHIVED"}` (allaqachon arxivlangan) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M17-02 (chekka holat); BO-12, BO-19; audit majburiy |

---

## M15 — Xarajatlar

### 41. `GET /expenses`

| | |
|---|---|
| Maqsad | Xarajatlar ro'yxati |
| Ruxsat | `expenses.create` |
| So'rov | Cursor; filtr `?category_id=&branch_id=&doc_date__gte=&doc_date__lte=&status=` |
| Javob | `{items: [{id, category_id, amount, source, tax_type, cash_register_id, shift_id, attachment_id, status, doc_date}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish (BO-17) |
| Bog'langan | US-M15-01; BO-17 |

### 42. `POST /expenses`

| | |
|---|---|
| Maqsad | Xarajat qoralamasi yaratish (10 soniyada, US-M15-01) |
| Ruxsat | `expenses.create` |
| So'rov | `{doc_date: date (majburiy, standart bugun), branch_id: UUID (majburiy, standart `X-Branch-Id`), category_id: UUID (majburiy), amount: string (majburiy, >0), source: "cash"\|"bank"\|"card" (majburiy), cash_register_id: UUID (source=cash bo'lsa majburiy), shift_id: UUID (source=cash bo'lsa majburiy), attachment_id: UUID (ixtiyoriy), comment: string (ixtiyoriy), recurring_rule_id: UUID (ixtiyoriy), tax_type: "vat"\|"turnover"\|"pit"\|"social"\|"property"\|"land"\|"other" (toifa `default_account="6410"` — soliq to'lovi — bo'lsa majburiy, aks holda yuborilmaydi)}` |
| Javob | `201 {id, status: "draft", doc_date, amount, category_id, tax_type}` |
| Xatolar | `VALIDATION_ERROR` (`tax_type` soliq toifasida yo'q yoki boshqa toifada berilgan) |
| Idempotency-Key | Majburiy |
| Offline | `source='cash'` — POS'dan `expense.created` voqeasi (`18-api-kassa.md` §13.2, POS-14 «Xarajat»; offline ham): payload maydonlari shu tana bilan bir xil + `{id, cash_register_id, shift_id, approval?}`; ruxsat `cash.withdraw` (limit) — Kassirda `expenses.create` yo'q; limitdan oshsa `approval` (`ApprovalRef`, `kind='cash_withdrawal_over_limit'`); server `ExpensePostingService` bilan `draft` yaratmasdan darhol `posted`. Boshqa manba (`bank`/`card`) — faqat shu endpoint, online |
| Bog'langan | US-M15-01; BO-17 |

### 43. `POST /expenses/{id}/post`

| | |
|---|---|
| Maqsad | Xarajatni o'tkazish — `ExpensePostingService` (`13-provodka-qoidalari.md` §2.17): `ledger_entries` (Dt = toifaning `default_account`: `9410`/`9420`/`9430`, soliq to'lovi — `6410` (`Dt 6410 / Kt 5110`)) + (agar `source=cash`) `cash_moves`; `source="bank"\|"card"` — Kt 5110 (MVP'da yagona bank hisobi, qaror #49) |
| Ruxsat | `expenses.create` (limit) — katta summa `expenses.approve` talab qiladi (`15-xavfsizlik-va-audit.md` §2.1) |
| So'rov | Tana yo'q |
| Javob | `200 {id, status: "posted", posted_at}` yoki limitdan oshsa `202 {status: "draft", approval_request_id}` (`APPROVAL_REQUIRED` — hujjat `draft`da qoladi, `pending_approval`ga o'tmaydi; `price_changes`dan farqli bu umumiy qoida) |
| Xatolar | `DOC_NOT_DRAFT`, `EXPENSE_LIMIT_EXCEEDED`, `PERIOD_CLOSED` |
| Idempotency-Key | Majburiy |
| Offline | `source=cash` bo'lsa offline postinglanadi, sinxronlashda serverga tushadi |
| Bog'langan | US-M15-01, US-M15-03; BO-17 |

### 44. `POST /expenses/{id}/cancel`

| | |
|---|---|
| Maqsad | Xarajatni bekor qilish (teskari yozuv, `13-provodka-qoidalari.md` §5.2). Yopilgan davrdagi hujjat ham bekor qilinadi — storno joriy ochiq davr sanasida |
| Ruxsat | `expenses.create` |
| So'rov | `{reason: string (majburiy)}` |
| Javob | `200 {id, status: "cancelled", cancelled_at}` |
| Xatolar | `DOC_ALREADY_CANCELLED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q (bekor qilish faqat online) |
| Bog'langan | M15 chekka holat ("xarajat bekor qilinsa — teskari yozuv"); BO-17; audit majburiy |

### 45. `GET /expense-categories`

| | |
|---|---|
| Maqsad | Xarajat toifalari ro'yxati (standart ro'yxat — `13-provodka-qoidalari.md` §2.17 seed xaritasi, 21 kod) |
| Ruxsat | `—` |
| So'rov | — |
| Javob | `{items: [{id, code, name, default_account: "9410"\|"9420"\|"9430"\|"6410", source_ref, archived_at}]}` — `default_account` xarajat provodkasining Dt hisobi (43-endpoint); `6410` — «Soliq to'lovi (byudjetga)» (`tax_payment`, `expenses.tax_type` majburiy); `code`/`source_ref` — seed/import manbasi (tizim toifalarida to'ldirilgan) |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan (catalog scope) |
| Bog'langan | US-M15-01; BO-17 |

### 46. `POST /expense-categories`

| | |
|---|---|
| Maqsad | Yangi toifa qo'shish |
| Ruxsat | `expenses.create` |
| So'rov | `{name: string (majburiy, 1-50 belgi), default_account: "9410"\|"9420"\|"9430"\|"6410" (majburiy)}` |
| Javob | `201 {id, code, name, default_account}` |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M15-01; BO-17 |

### 47. `PATCH /expense-categories/{id}`

| | |
|---|---|
| Maqsad | Toifani tahrirlash/arxivlash |
| Ruxsat | `expenses.create` |
| So'rov | `{name?: string, default_account?: "9410"\|"9420"\|"9430"\|"6410", archived?: bool, version: int (majburiy)}` — `default_account` o'zgarishi faqat keyingi xarajatlarga ta'sir qiladi |
| Javob | `200 {id, code, name, default_account, archived_at, version}` |
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M15-01; BO-17 |

### 48. `GET /recurring-expenses`

| | |
|---|---|
| Maqsad | Takrorlanuvchi xarajat qoidalari (US-M15-02, oylik ijara va h.k.) |
| Ruxsat | `expenses.create` |
| So'rov | Page pagination; `branch_id` — `X-Branch-Id` header orqali |
| Javob | `{items: [{id, name, category_id, amount, day_of_month, period, source, cash_register_id, next_due_date, last_triggered_at, is_active}], total, page, size}` |
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
| Javob | `201 {expense_id, status: "posted"}` yoki summa foydalanuvchining `expenses.create` limitidan oshsa `202 {expense_id, status: "draft", approval_request_id}` (`APPROVAL_REQUIRED` — `expenses.approve` egasi tasdiqlaydi, 43-endpoint bilan bir xil qoida) |
| Xatolar | `VALIDATION_ERROR`, `SHIFT_NOT_OPEN` (`source="cash"` bo'lgan qoidada ochiq smena bo'lmasa), `EXPENSE_LIMIT_EXCEEDED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q (eslatma M18 orqali keladi, tasdiq — online back-office) |
| Bog'langan | US-M15-02; BO-17, M18 eslatma |

---

## M16 — Kassa pul harakati

### 52. `GET /cash-movements`

| | |
|---|---|
| Maqsad | Kassa pul harakati ro'yxati (`cash_movements`) — ruxsat/ta'rif **yagona manba shu yerda**, `18-api-kassa.md` §13.3 shu yerga havola qiladi |
| Ruxsat | `reports.sales.view` **yoki** `cash.count.shift` (Omborchi/Buxgalter `cash.deposit`ga ega emas, kassir esa barcha kassalarni ko'rishi kerak) |
| So'rov | Cursor; filtr `?cash_register_id=&shift_id=&direction=in\|out&reason=` |
| Javob | `{items: [{id, cash_register_id, shift_id, direction, amount, reason, counterparty_id, created_by, doc_date}], next_cursor}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | To'liq offline ishlaydi (append-only jurnal, `16-offline-sync.md`) |
| Bog'langan | US-M16-01, US-M16-03; BO-11 (xodim audit), POS-15 |

### 53. `POST /cash-movements`

| | |
|---|---|
| Maqsad | Pul qo'yish/olish yozish (US-M16-01). **POS'dan — faqat `cash_movement.created` sync voqeasi; bu REST — back-office (masalan inkasso yozish)** |
| Ruxsat | `direction=in` → `cash.deposit`; `direction=out` → `cash.withdraw` (limit, standart 50 000 so'm, `15-xavfsizlik-va-audit.md` §2.3) |
| So'rov | `{cash_register_id: UUID (majburiy), shift_id: UUID (majburiy, faol smena), direction: "in"\|"out" (majburiy), amount: string (majburiy, >0), reason: "collection"\|"deposit"\|"owner_withdrawal"\|"other" (majburiy), account?: "9430"\|"9390"\|"6310"\|"4010"\|"4730" (faqat `reason="other"`; standart `out` → `9430`, `in` → `9390`), employee_id?: UUID (`account="4730"` da majburiy), counterparty_id?: UUID (`reason="owner_withdrawal"` da — `tenants.legal_form ≠ sole_proprietor` bo'lsa majburiy, `counterparties.is_founder=true` bo'lgan ta'sischi, provodka Dt `tenants.settings.owner_withdrawal_account`; `reason="other"` va `account ∈ {6310, 4010}` da majburiy), comment: string (`reason="other"`da majburiy), doc_date: date (majburiy)}`. `reason↔direction` juftligi: `collection`, `owner_withdrawal` → faqat `out`; `deposit` → faqat `in`; `other` → ikkalasi. Provodka (`13-provodka-qoidalari.md` §2.18): `other/out` → `Dt account / Kt 5010`, `other/in` → `Dt 5010 / Kt account`. `reason="collection"` (inkassa) — kassadan 5710 ga (`payment_method="collection"`), bank tasdig'i — 55c–55h |
| Javob | `201 {id, status: "posted", amount}` yoki limitdan oshsa `202 {status: "draft", approval_request_id}` (`APPROVAL_REQUIRED` — `kind="cash_withdrawal_over_limit"`, BO-16) |
| Xatolar | `VALIDATION_ERROR` (`reason↔direction` juftligi buzilgan; `account` `reason≠other` da berilgan yoki ro'yxatda yo'q; `employee_id` yoki `counterparty_id` talab qilinganda yo'q; `owner_withdrawal` da kontragent ta'sischi emas), `CASH_WITHDRAW_LIMIT_EXCEEDED` |
| Idempotency-Key | Majburiy (back-office'dan); POS'dan — `/sync/push` orqali `cash_movement.created` voqeasi (`16-offline-sync.md` §2) |
| Offline | To'liq offline (M01 bilan bir xil append-only, `03-modullar-talablari.md` M16) |
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
| Ruxsat | `cash.count.shift` **yoki** `reports.sales.view` (Egasida `cash.count.shift` yo'q, lekin US-M16-03 "Egasi sifatida" ko'rishni talab qiladi) |
| So'rov | `?date_from=&date_to=` |
| Javob | `{items: [{shift_id, opened_at, closed_at, opening_cash, expected_cash, counted_cash, variance, counted_card_total}]}` |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish |
| Bog'langan | US-M16-02, US-M16-03; BO-09 "Kassa/smena tarixi", eksport kodi `cash-history` |

---

## M11/M16 — Bank tushumi tasdig'i (`bank_settlements`)

> Hujjat jadvali `bank_settlements` (`doc_sequences` kodi `BT`, `12-db-sxema.md`), provodka — `13-provodka-qoidalari.md` §2.18a (qaror #42): 5710 (yo'ldagi pul) dagi tranzit summani bank hisobiga (5110) o'tkazadigan **yagona** hujjat. Komissiya hisobi `method` bo'yicha: `card`/`uzqr` (bank ekvayringi) — **9430**; `click`/`payme`/`uzum` (to'lov tashkiloti) — `tenants.settings.payment_org_commission_account` (standart `9430`); `collection` (inkassa xizmati) — **9410**. MVP'da tenantning **bitta** bank hisobi (5110, `tenants.settings.bank_account`; `cash_moves.bank_account_id` doim `NULL`, qaror #49). Standart uch bosqichli hujjat (`17-api-umumiy.md` §9: `draft → post → cancel`). **Faqat back-office**, sync voqeasi yo'q. `cash_moves` yozilmaydi — faqat `ledger_entries`. Modul papkasi `modules/cash` (`BankSettlementPostingService`), OpenAPI teg `cash`. Ekran — BO-24; jarayon — BP-15; hikoya — US-M11-04. `source='statement_import'` hujjatlari bank ko'chirmasi importidan (55g) `draft` holatida yaratiladi va xuddi shu 55e/55f bilan o'tkaziladi/bekor qilinadi — import hech qachon avtomatik `post` qilmaydi; 55c har doim `source='manual'` yaratadi.

`BankSettlement` obyekti (javoblarda): `{id, number, branch_id, doc_date, status ("draft"|"posted"|"cancelled"), source ("manual"|"statement_import"), method ("card"|"uzqr"|"click"|"payme"|"uzum"|"collection"), settled_from, settled_to, gross_amount, commission_amount, variance_amount, net_amount, bank_ref, attachment_id, statement_import_id, comment, created_by, created_at, posted_at, cancelled_at, cancelled_by, cancel_reason, version}` — pul o'nlik satr (`17-api-umumiy.md` §3); `variance_amount` — faqat `method="collection"` (standart `"0.00"`): inkassa summasi bilan bank sanog'i farqi, manfiy — kamomad (`Dt 5910`), musbat — ortiqcha (`Kt 9390`); `net_amount = gross_amount − commission_amount + variance_amount` (bank hisobiga tushgan summa, DB'da generated); `statement_import_id` — 55g importi (`source='statement_import'` da).

### 55a. `GET /bank-settlements`

| | |
|---|---|
| Maqsad | Bank tushumi tasdiqlari ro'yxati (BO-24) |
| Ruxsat | `bank_settlements.manage` |
| So'rov | Cursor (`?cursor=&limit=`); filtr `?branch_id=&method=&status=&source=&doc_date__gte=&doc_date__lte=`; sort `-doc_date` (standart) |
| Javob | `{items: [BankSettlement], next_cursor}` |
| Xatolar | `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish (PWA keshi) |
| Bog'langan | US-M11-04; BO-24; BP-15 |

### 55b. `GET /bank-settlements/transit-balances`

| | |
|---|---|
| Maqsad | BO-24 «yo'ldagi pul qoldig'i» paneli: 5710 qoldig'i filial × to'lov usuli bo'yicha (`ledger_entries`, analitika `payment_method`) — 55c/55e dagi tekshiruv bilan bir xil hisob |
| Ruxsat | `bank_settlements.manage` |
| So'rov | `?as_of=<date>` (standart — bugun, Toshkent), `?branch_id=` (ixtiyoriy) |
| Javob | `{as_of, items: [{branch_id, method, balance, oldest_unsettled_date, card_breakdown}]}` — faqat `balance ≠ "0.00"` qatorlar; `oldest_unsettled_date` — FIFO bo'yicha yopilmagan eng eski tushum sanasi (ma'lumot uchun); `card_breakdown` — faqat `method="card"` da (boshqasida `null`): `{integrated, manual}` — `balance` ning integratsiyalangan (`card_entry_mode='integrated'`, `rrn` bo'yicha moslashtiriladi) va terminalsiz (`manual`, summa/sana va filial/merchant bo'yicha moslashtiriladi) qismlari, to'lov qatorlaridan hisoblanadi, ma'lumot uchun (BO-24 "Karta (terminalsiz)" qatori; `21` §9.2) |
| Xatolar | `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M11-04; BO-24 paneli; `04-biznes-jarayonlar.md` BP-15 («Bank tushumi tasdiqlanmagan» holati) |

### 55c. `POST /bank-settlements`

| | |
|---|---|
| Maqsad | Bank ko'chirmasi / ekvayer hisob-kitob hisoboti bo'yicha qoralama yaratish (`source='manual'`) |
| Ruxsat | `bank_settlements.manage` |
| So'rov | `{branch_id: UUID (majburiy), doc_date: date (majburiy — bankka tushgan sana, provodka sanasi), method: "card"\|"uzqr"\|"click"\|"payme"\|"uzum"\|"collection" (majburiy), settled_from: date, settled_to: date (majburiy, settled_from ≤ settled_to ≤ doc_date), gross_amount: string (majburiy, > 0 — 5710 dan yopiladigan summa), commission_amount: string (standart "0.00", ≥ 0 va < gross_amount), variance_amount: string (standart "0.00"; faqat `method="collection"`; manfiy — kamomad, musbat — ortiqcha; `gross_amount − commission_amount + variance_amount > 0`), bank_ref: string (ixtiyoriy), attachment_id: UUID (ixtiyoriy, `attachments.kind='import'` — ko'chirma fayli, `17-api-umumiy.md` §12), comment: string (ixtiyoriy)}` |
| Javob | `201 BankSettlement` (`status="draft"`, `number` — `BT-{filial}-{yil}-{ketma-ket}`, `11-malumotlar-modeli.md`) |
| Xatolar | `VALIDATION_ERROR` (enum, sana tartibi, `commission_amount ≥ gross_amount`; `variance_amount ≠ 0` va `method ≠ "collection"`; `gross_amount` shu filial va usul bo'yicha `doc_date` holatidagi 5710 qoldig'idan katta — `details[].field="gross_amount"`, `details[].message_key="validation.bank_settlement_exceeds_in_transit"`, `params.available`), `PERIOD_CLOSED` (`doc_date` yopilgan davrda), `BRANCH_SCOPE_DENIED`, `NOT_FOUND` (`attachment_id`) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-04; BO-24 forma; BP-15; audit (`15-xavfsizlik-va-audit.md` §6.1) |

### 55d. `GET /bank-settlements/{id}`

| | |
|---|---|
| Maqsad | Hujjat tafsiloti |
| Ruxsat | `bank_settlements.manage` |
| So'rov | — |
| Javob | `BankSettlement` + `ledger_entries: [{account_dt, account_kt, amount, analytics}]` (`posted`/`cancelled` da; storno qatorlar ham) |
| Xatolar | `NOT_FOUND`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish |
| Bog'langan | US-M11-04; BO-24; «1C da» belgisi (W-54, 1C integratsiyasi yoqilgan tenantda) |

### 55e. `POST /bank-settlements/{id}/post`

| | |
|---|---|
| Maqsad | O'tkazish (`13-provodka-qoidalari.md` §2.18a): `Dt 5110 / Kt 5710 = net_amount`; komissiya > 0 bo'lsa `Dt {komissiya hisobi} / Kt 5710 = commission_amount` — `card`/`uzqr` → `9430`, `click`/`payme`/`uzum` → `payment_org_commission_account` (standart `9430`), `collection` → `9410`; inkassa farqi: kamomad (`variance_amount < 0`) `Dt 5910 / Kt 5710 = |variance_amount|`, ortiqcha (`variance_amount > 0`) `Dt 5710 / Kt 9390 = variance_amount` (analitika `payment_method`, filial, `bank_ref`); `Kt 5710` sof jami = `gross_amount` |
| Ruxsat | `bank_settlements.manage` |
| So'rov | `{}` |
| Javob | `200 BankSettlement` (`status="posted"`, `posted_at`) |
| Xatolar | `DOC_NOT_DRAFT`, `PERIOD_CLOSED`, `VALIDATION_ERROR` (`gross_amount` shu filial va usul bo'yicha `doc_date` holatidagi 5710 qoldig'idan oshadi — yakuniy tekshiruv `FOR UPDATE` ostida, `params.available`) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-04; BO-24 «O'tkazish»; QT-M11-07 (`31-qabul-testlari.md`) |

### 55f. `POST /bank-settlements/{id}/cancel`

| | |
|---|---|
| Maqsad | Bekor qilish: `posted` — storno qatorlar (`13-provodka-qoidalari.md` §5.2), yopilgan davrga tegmaydi (§5.1) — yopilgan davrdagi hujjat ham bekor qilinadi, storno joriy ochiq davr sanasida; `draft` — provodkasiz `cancelled` |
| Ruxsat | `bank_settlements.manage` |
| So'rov | `{reason: string (majburiy)}` |
| Javob | `200 BankSettlement` (`status="cancelled"`, `cancelled_at`, `cancel_reason`) |
| Xatolar | `DOC_ALREADY_CANCELLED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-04; BO-24 «Bekor qilish»; audit majburiy |

### 55g. `POST /bank-settlements/imports`

> Bank ko'chirmasi importi (`source='statement_import'`). Format — O'zbekiston bank-klient tizimlarining de-fakto standarti **1CClientBankExchange** (.txt); xml/Excel va ochiq banking API — keyin (ochiq banking normativ hujjati hali yo'q). Import faqat **qoralamalar** yaratadi — moslashtirishni Buxgalter tekshiradi va har birini 55e bilan o'zi o'tkazadi; hech narsa avtomatik `post` qilinmaydi.

| | |
|---|---|
| Maqsad | Ko'chirma faylini o'qish → kirim qatorlarini 5710 tranzit qoldiqlari bilan moslashtirish → `bank_settlements` **draft**lari |
| Ruxsat | `bank_settlements.manage` |
| So'rov | `multipart/form-data`: `file` (.txt, ≤ 10 MB, ≤ 20 000 qator — qaror #54), `branch_id` (UUID, ixtiyoriy — qator filialini to'lov maqsadidan aniqlab bo'lmasa ishlatiladi; tenantda bitta filial bo'lsa standart shu) |
| Parser | **Kodlash**: sarlavhadagi `Кодировка=` (`Windows` → windows-1251, `UTF-8`/`UTF8` → UTF-8); sarlavha yo'q bo'lsa — avval qat'iy UTF-8 (BOM bilan ham), muvaffaqiyatsiz bo'lsa windows-1251. Birinchi qator `1CClientBankExchange` bo'lishi shart. **`СекцияРасчСчет`** … `КонецРасчСчет`: `РасчСчет`, `ДатаНачала`, `ДатаКонца`, `НачальныйОстаток`, `ВсегоПоступило`, `ВсегоСписано`, `КонечныйОстаток`. **`СекцияДокумент=<вид>`** … `КонецДокумента`: `Номер`, `Дата`, `Сумма`, `ПлательщикСчет`, `Плательщик`/`Плательщик1`, `ПлательщикИНН`, `ПолучательСчет`, `Получатель`/`Получатель1`, `ПолучательИНН`, `ДатаПоступило`, `ДатаСписано`, `НазначениеПлатежа`. Faqat **kirim** qatorlari (`ПолучательСчет` = tenant hisobi) qayta ishlanadi; chiqimlar `ignored_outgoing` da sanaladi. `Сумма` — o'nlik satrga (`17-api-umumiy.md` §3), sana — `ДатаПоступило`, bo'lmasa `Дата` |
| Moslashtirish | Har kirim qatori uchun: (1) `method` — to'lovchi (ekvayer bank / Click / Payme / Uzum / inkassa) va `НазначениеПлатежа` kalit so'zlari bo'yicha; (2) filial — to'lov maqsadidagi terminal/merchant identifikatori bo'yicha, aks holda `branch_id`; (3) moslashtirish birligi — (filial, `method`, `entry_date`) kunlik 5710 debet yig'indisi; eng eski kundan boshlab `n` ta kun olinadi — `Σ ≥ kirim` va `(Σ − kirim) / Σ ≤ 5%` bo'lgan eng kichik `n`; har kun summasidan shu import ichida va ochiq `draft` larda allaqachon band qilingan summa ayiriladi (ikki marta band qilinmaydi); `gross_amount = Σ`, `settled_from`/`settled_to` — shu kunlar oralig'i, `doc_date` — kirim sanasi; karta (`method="card"`) kirimida moslashtirish summa va sana (filial/merchant) bo'yicha — ko'chirmada RRN yo'q; integratsiyalangan karta tushumining tranzaksiya darajasidagi `rrn` moslashtiruvi terminal settlement'i (`card_terminal_settlements.bank_settlement_id`, `21` §9.4) orqali, terminalsiz karta tushumi hech qachon RRN bo'yicha moslashtirilmaydi (`21` §9.2); (4) `commission_amount = gross_amount − kirim summasi`, `variance_amount = "0.00"` (inkassada kamomad/ortiqcha bo'lsa — Buxgalter qoralamani 55h bilan tahrirlaydi). `bank_ref` = `Номер`, `attachment_id` — yuklangan fayl (`attachments.kind='import'`). Mos tranzit topilmasa — qoralama yaratilmaydi, qator `unmatched_lines` ga tushadi (`reason:"no_transit_match"`); `commission_amount < 0` yoki `commission_amount ≥ gross_amount` — qoralama yaratilmaydi, `unmatched_lines` (`reason:"commission_invalid"`); Buxgalter 55c bilan qo'lda kiritadi |
| Javob | `201 {import_id, file_sha256, account, period_from, period_to, drafts_created: int, draft_ids: [UUID], duplicates: int, ignored_outgoing: int, unmatched_lines: [{line_no, number, date, amount, payer_name, purpose, reason: "no_transit_match"\|"unknown_method"\|"branch_ambiguous"\|"commission_invalid"}]}` — `import_id` — import yozuvining `id`si (`bank_settlements.statement_import_id` shunga ishora qiladi); qolgan nomlar `bank_statement_imports` ustunlari bilan bir xil; `draft_ids` hosila (`bank_settlements.statement_import_id = import_id`); `duplicates`: `bank_ref` + `doc_date` + summa bo'yicha avval yaratilgan (bekor qilinmagan) `bank_settlements` bilan mos qatorlar |
| Xatolar | `422 BANK_IMPORT_FILE_INVALID` (1CClientBankExchange sarlavhasi yo'q, kodlash aniqlanmadi, majburiy maydon yo'q yoki sintaksis xatosi — `params.line_no`), `422 BANK_IMPORT_ACCOUNT_MISMATCH` (`СекцияРасчСчет.РасчСчет` `tenants.settings.bank_account`ga teng emas, bir nechta hisob bor yoki tenant bank hisobi kiritilmagan — `params.file_account`), `409 BANK_IMPORT_DUPLICATE` (shu `file_sha256` bilan fayl allaqachon import qilingan — `params.import_id`), `FILE_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-04; BO-24 «Ko'chirmani yuklash»; BP-15; audit (`entity='bank_settlements'`, `import_id`) |

### 55h. `PATCH /bank-settlements/{id}`

| | |
|---|---|
| Maqsad | Qoralamani tahrirlash (BO-24) — import qoralamasida komissiya/inkassa farqini aniqlashtirish yoki qo'lda yaratilganini tuzatish; faqat `draft` |
| Ruxsat | `bank_settlements.manage` |
| So'rov | `{gross_amount?, commission_amount?, variance_amount?, settled_from?, settled_to?, bank_ref?, comment?, version: int (majburiy)}` — validatsiya 55c bilan bir xil (`variance_amount` faqat `method="collection"`; `gross_amount − commission_amount + variance_amount > 0`; `gross_amount` ≤ 5710 qoldig'i) |
| Javob | `200 BankSettlement` |
| Xatolar | `DOC_NOT_DRAFT`, `VERSION_CONFLICT`, `VALIDATION_ERROR`, `NOT_FOUND`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-04; BO-24; audit majburiy |

Xato kodlari — `17-api-umumiy.md` §15: mavjud umumiy kodlar + `BANK_IMPORT_FILE_INVALID`, `BANK_IMPORT_ACCOUNT_MISMATCH`, `BANK_IMPORT_DUPLICATE` (55g).

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
| **Lokaut** | **Ochiq** — `require_subscription_ok` middleware istisnosi, `restricted` holatida ham ishlaydi |

### 57. `GET /billing/subscription`

| | |
|---|---|
| Maqsad | Obuna holati (`subscriptions` — yagona manba, `11-malumotlar-modeli.md` §8) |
| Ruxsat | `—` |
| So'rov | — |
| Javob | `{status: "trial"\|"active"\|"grace"\|"restricted"\|"closed", period: "month"\|"year", current_period_end, grace_ends_at, active_cash_registers: int}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Mahalliy litsenziya tokenidan (`license`), server holatidan farqlanishi mumkin (`14-autentifikatsiya-oauth2.md` §17) |
| Bog'langan | US-M17-03; BO-01 (banner), BO-19 |
| **Lokaut** | **Ochiq** — `restricted`da ham ishlaydi |

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
| **Lokaut** | **Ochiq** — `restricted`da ham ishlaydi |

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

> `DELETE` o'rniga `POST .../reduce` ishlatiladi, chunki `DELETE` tana (`quantity`) bilan proksi/orval qatlamlarida ishonchli uzatilmaydi.

| | |
|---|---|
| Maqsad | Qo'shimchadan voz kechish (M17 chekka holat — kamaytirish, ortiqcha kassa arxivlanishi talab qilinadi) |
| Ruxsat | `billing.manage` — **faqat Egasi** |
| So'rov | `{quantity: int (majburiy, kamaytiriladigan miqdor)}` |
| Javob | `200 {addon_code, quantity, removed_at}` — agar faol kassalar soni yangi limitdan ko'p bo'lsa, javobda `requires_archiving: [cash_register_id, ...]` (arxivlash — 40i) |
| Xatolar | `VALIDATION_ERROR`, `403 OWNER_ONLY` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M17-02 chekka holat; BO-19 |

### 61. `POST /billing/checkout`

> **Lokautda ham ochiq**: `/billing/*` o'qish yo'llari + shu endpoint + `/billing/webhooks/*` — lokaut istisnolari ro'yxatida (`23-backend-arxitekturasi.md` §3, `14-autentifikatsiya-oauth2.md` §16.1/§20), chunki lokautdagi tenant to'lov qilib kirishni tiklashi kerak (qaror #15).
>
> **`restricted` holatida sessiya yo'q**: to'lov `14-autentifikatsiya-oauth2.md` §16.1.1 `GET /billing/pay` orqali — telefon+parol identifikatsiyasidan keyin qisqa muddatli `pay_token` beriladi, bu endpoint shu token bilan (`Authorization: PayToken ...`) chaqiriladi, faqat shu bir amal uchun ruxsat etiladi.

| | |
|---|---|
| Maqsad | To'lov checkout yaratish (Click/Payme) — obuna davrini uzaytirish uchun; to'lov **platformaning o'z merchant hisobiga** tushadi (tenant merchant kalitlari — faqat do'kon sotuvlari uchun, 40d; qaror #46) |
| Ruxsat | `billing.manage` (sessiya bilan) **yoki** `pay_token` (`restricted`, sessiyasiz) — **faqat Egasi** |
| So'rov | `{provider: "click"\|"payme", period: "month"\|"year"}` |
| Javob | `201 {payment_id, checkout_url, amount, amount_breakdown, period}` — `amount` server hisoblaydi: oy — `99000 + 39000 × extra_registers`; yil — `950400 + 39000 × 12 × extra_registers` (yillik chegirma faqat asosiy tarifga, qaror #70); `extra_registers` — `tenant_addons.extra_register` soni; `amount_breakdown = {plan, period, addons: [{code, qty, unit_price, months}], discount}` → `billing_payments.amount_breakdown`. Muvaffaqiyatli to'lovda `new_end = max(current_period_end, now()) + 1 oy \| 12 oy` (`subscriptions.current_period_end`), holat → `active`. Obuna holatlari: `trial` (30 kun) → `grace` (24 soat) → `restricted`; `closed` — faqat platforma admini amali, avtomatik emas (qaror #70). `provider_tx_id` checkout paytida noma'lum (Payme `CreateTransaction`da beradi): server `billing_payments(status="pending")` yozuvini `payment_id` bilan yaratadi, Click `merchant_trans_id` = shu `payment_id` (`billing_payment_by_id()`) |
| Xatolar | `VALIDATION_ERROR`, `OWNER_ONLY` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q (ro'yxatdan o'tish/to'lov faqat online, `03-modullar-talablari.md` M17) |
| Bog'langan | US-M17-02, US-M17-03; BO-19 |
| **Lokaut** | **Ochiq** — `restricted`da ham ishlaydi, `pay_token` orqali |

### 62. `GET /billing/payments`

| | |
|---|---|
| Maqsad | To'lovlar tarixi (`billing_payments`) — platforma admin qo'lda uzaytirishlari ham shu yerda ko'rinadi (qaror #56) |
| Ruxsat | `billing.manage` — **faqat Egasi** |
| So'rov | Cursor; filtr `?kind=payment\|manual_extension\|refund` |
| Javob | `{items: [{id, kind: "payment"\|"manual_extension"\|"refund", amount, amount_breakdown, provider, provider_tx_id, status, covers_from, covers_to, reason, paid_at, created_at}], next_cursor}` — `kind="manual_extension"`: `amount="0.00"`, `provider=null`, `reason` — platforma admin kiritgan sabab (`actor_user_id` tenantga ko'rsatilmaydi, faqat audit) |
| Xatolar | `403 OWNER_ONLY` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M17-02; BO-19 |
| **Lokaut** | **Ochiq** — `restricted`da ham ishlaydi |

### 63. `POST /billing/webhooks/click`

| | |
|---|---|
| Maqsad | Click webhook (bizning obuna billing'imiz, platformaning o'z merchant hisobi — qaror #46) — `17-api-umumiy.md` §14 naqshi |
| Ruxsat | `—` (MD5 imzo tekshiruvi) |
| So'rov | Click "Shop API" Prepare/Complete shakli (`action`, `click_trans_id`, `merchant_trans_id`, `amount`, `sign_time`, `sign_string`) |
| Javob | Click protokoliga mos JSON (`error: 0` muvaffaqiyat) |
| Xatolar | `WEBHOOK_SIGNATURE_INVALID` |
| Idempotency-Key | Kerak emas (`provider_tx_id` UNIQUE orqali dedupe) |
| Offline | — |
| Bog'langan | US-M17-02; `21-integratsiyalar.md` §9 |
| **Lokaut** | **Ochiq** (o'z imzo tekshiruvi bilan) |

### 64. `POST /billing/webhooks/payme`

| | |
|---|---|
| Maqsad | Payme webhook (JSON-RPC, bizning billing, platforma merchant hisobi — qaror #46) |
| Ruxsat | `—` (`Authorization: Basic` merchant login:key tekshiruvi) |
| So'rov | JSON-RPC: `method` (`CheckPerformTransaction`\|`CreateTransaction`\|`PerformTransaction`\|`CancelTransaction`\|`CheckTransaction`\|`GetStatement`), `params` |
| Javob | JSON-RPC natija (Payme protokoliga mos) |
| Xatolar | `WEBHOOK_SIGNATURE_INVALID` |
| Idempotency-Key | Kerak emas (`provider_tx_id` UNIQUE) |
| Offline | — |
| Bog'langan | US-M17-02; `21-integratsiyalar.md` §9 |
| **Lokaut** | **Ochiq** (o'z imzo tekshiruvi bilan) |

### 65. `GET /billing/invoices/{payment_id}`

| | |
|---|---|
| Maqsad | To'lov uchun hujjat (kvitansiya/invoys PDF, US-M17-02: "to'lov uchun hujjat beriladi") |
| Ruxsat | `billing.manage` — **faqat Egasi** |
| So'rov | — |
| Javob | `200 {payment_id, invoice_url (signed PDF, 24 soat)}` |
| Xatolar | `NOT_FOUND`, `403 OWNER_ONLY` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M17-02; BO-19 |

### 65a. `POST /billing/export-my-data` · `GET /billing/export-my-data`

| | |
|---|---|
| Maqsad | Tenant to'liq eksporti (qaror #51): **ZIP** — har jadval alohida CSV (UTF-8, sarlavha qatori, pul — o'nlik satr) + `manifest.json` (`schema_version`, `generated_at`, `tenant_id`, jadval → qatorlar soni) + ixtiyoriy hujjat PDF'lari. Tayyorlash — asinxron job (`17-api-umumiy.md` §13), ≤ 24 soat. `restricted`/`closed` (lokaut) holatida — faqat to'lov sahifasidagi OTP oqimi orqali (`14-autentifikatsiya-oauth2.md` §16.5, qaror #20): OTP (`purpose=data_export`) — Telegram birinchi, SMS zaxira (qaror #34); faqat Egasi |
| Ruxsat | `active`/`grace`: `billing.manage` (**faqat Egasi**, sessiya bilan); lokautda: `14-autentifikatsiya-oauth2.md` §16.5 bo'yicha Egasiga OTP bilan berilgan bir martalik eksport tokeni; boshqa rolga `403` |
| So'rov | `POST` — `{include_pdfs: bool (standart false)}`; `GET` — `?job_id=` (yoki lokautda `?token=`) |
| Javob | `POST` → `202 {job_id, status: "queued"}`; `GET` → `200 {job_id, status: "queued"\|"running"\|"done"\|"failed", file_url, expires_at}` — `17-api-umumiy.md` §13 naqshi; `file_url` (signed URL, **24 soat**) va `expires_at` faqat `status="done"` da, boshqa holatda `null` |
| Xatolar | `RATE_LIMITED` (tenant uchun **1 so'rov / 24 soat**, `Retry-After`), `403 OWNER_ONLY`, `NOT_FOUND` (`job_id`), `SUBSCRIPTION_RESTRICTED` (lokautda token'siz) |
| Idempotency-Key | `POST` — majburiy; `GET` — kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M17-03, US-M17-05; BO-19; `15-xavfsizlik-va-audit.md` §7.3; audit: `data_export` / lokautda `data_export_during_restriction` |
| **Lokaut** | Faqat `14-autentifikatsiya-oauth2.md` §16.5 OTP-token yo'li bilan ochiq |

### Platforma admin (`/platform/*`) — havola

To'liq sxema **`14-autentifikatsiya-oauth2.md` §18.1**da. Bu yerda faqat ro'yxat (ADM-01):

| Metod + yo'l | Maqsad |
|---|---|
| `GET /platform/tenants` | Tenantlar ro'yxati, filtr (holat, tarif) |
| `GET /platform/tenants/{id}` | Tafsilot: obuna, to'lov, AI sarfi, qurilmalar |
| `POST /platform/tenants/{id}/extend-subscription` | Muddatni qo'lda uzaytirish — `subscriptions.current_period_end` bilan birga `billing_payments(kind='manual_extension', amount="0.00", status='success', covers_from, covers_to, actor_user_id, reason)` yozuvini yaratadi; tenant uni `GET /billing/payments` (62) da ko'radi (qaror #56) |
| `POST /platform/tenants/{id}/revoke-all-sessions` | Insident javobi |
| `GET /platform/tenants/{id}/ai-usage` | AI sarfi |
| `POST /platform/tenants/{id}/owner/block`, `/unblock` | Egasi hisobini bloklash/blokdan chiqarish |
| `POST /platform/tenants/{id}/owner/reset-password` | Egasiga tiklash OTP yuborish |
| `GET /platform/tenants/{id}/owner/sessions`, `POST …/owner/sessions/{sid}/revoke` | Egasi sessiyalari |

Ruxsat — hammasi `platform.admin` (**faqat `platform_admins`**, majburiy TOTP, har kirish audit'da — `15-xavfsizlik-va-audit.md` §3.4). Bog'langan: US-M13-08, US-M17-04; ADM-01.

---

## M18 — Bildirishnomalar

### 66. `POST /notifications/telegram/link-start`

| | |
|---|---|
| Maqsad | Telegram ulash uchun bir martalik kod/havola generatsiya (US-M18-01); tugma — back-office **BO-20** ekranida (qaror #56) |
| Ruxsat | `telegram.link` |
| So'rov | Tana yo'q |
| Javob | `201 {link_code, bot_url, expires_at}` — `link_code` muddati **10 daqiqa** (standart, sozlanadi — qaror #54) |
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
| Maqsad | Ulanishni uzish (`telegram_links.revoked_at = now()`) |
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
| Javob | `{items: [{kind, enabled, time}]}` — `kind` ∈ `{daily_report, low_stock, cash_variance, over_limit_action, state_report_diff, offline_48h, subscription_due, subscription_grace, debt_due_today, debt_aging_60, debt_limit_exceeded_offline, expiry_soon}` (to'liq ro'yxat: `subscription_due` — 3/1/0 kun oldin; `subscription_grace` — darhol/12s/2s; `debt_due_today` — US-M08-09; `debt_aging_60` — US-M08-10; `debt_limit_exceeded_offline` — Egasiga offline oshib ketgan qarz ogohlantirishi; `expiry_soon` — US-M04-06) |
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

> **Umumiy AI qoidalari** (`22-ai-qatlami.md`): (1) AI provayderiga yuboriladigan matnda shaxsiy maydonlar (ism, telefon, STIR/PINFL, manzil, karta maskasi) **har doim maskalanadi** (qaror #61); (2) AI-03 rasmlari (va maskalab bo'lmaydigan har qanday ma'lumot) tenant `ai_cross_border_enabled=true` (40h rozilik) bo'lmaguncha yuborilmaydi → `403 AI_CONSENT_REQUIRED`; (3) xarajat so'mda — Markaziy bankning kunlik rasmiy kursi (`platform.fx_rates`, scheduler har kuni 09:30), har so'rovda `ai_requests.fx_rate_used` yoziladi, kurs olinmasa `ERP_FX_USD_UZS_FALLBACK = 12 500` (qaror #55); (4) `AI_LOW_CONFIDENCE` xato kodi emas — `200` javobda `low_confidence_fields[]` (qaror #55), OpenAPI'da xato javobi sifatida e'lon qilinmaydi.

### 72. `POST /ai/chat`

| | |
|---|---|
| Maqsad | AI-01 — umumiy biznes savol-javob chat ("kod hisoblaydi, AI tushuntiradi", `09-ai-funksiyalar.md`) |
| Ruxsat | `ai.chat.use` |
| So'rov | `{message: string (majburiy, ≤2000 belgi), history: [{role: "user"\|"assistant", content: string}] (ixtiyoriy, oxirgi ≤10 xabar — holat stateless, server saqlamaydi), locale: "uz"\|"ru"}` |
| Javob | `text/event-stream` (SSE): `event: token` (`data: {"text": "..."}`) ketma-ket, yakunda `event: done` (`data: {"citations": [{"metric": "net_profit", "value": "1240000.00", "source": "reports.profit_and_loss"}], "ai_request_id": "..."}`); AI xato bersa `event: error` (`data: {"code": "AI_PROVIDER_UNAVAILABLE"}`) |
| Xatolar | `AI_LIMIT_EXCEEDED` (oylik token budjeti), `AI_PROVIDER_UNAVAILABLE`, `VALIDATION_ERROR`, `429 RATE_LIMITED` — rate-limit: foydalanuvchiga **10 so'rov/daqiqa**, tenantga **300 so'rov/kun** (qaror #55), `Retry-After` header bilan |
| Idempotency-Key | Kerak emas (strim, qayta yuborish — yangi so'rov) |
| Offline | Ishlamaydi — internet/LLM API talab qiladi (BO-13) |
| Bog'langan | AI-01; BO-13, M18 Telegram bot (`22-ai-qatlami.md` §11, bitta huquq/budjet quvuri) |

> **AI-03 — yagona oqim**: `ai_ocr_jobs` jadvali — alohida OCR endpoint boshqa fayllarda yo'q. `doc_type_hint` ikki qiymatga ega — `purchase` (goods-receipts, BO-04), `catalog` (mahsulot katalogi + boshlang'ich qoldiq, BO-21 onboarding). Qaytarish (`returns`) OCR'i yo'q — qaytarish hujjati faqat POS sync voqeasi `return.created` orqali yaratiladi (`18-api-kassa.md` §7).

### 73. `POST /ai/ocr/jobs`

| | |
|---|---|
| Maqsad | AI-03 — qog'oz hujjat (yuk xati/faktura/chek) fotosini tahlilga yuborish (`22-ai-qatlami.md` §10) |
| Ruxsat | `ai.ocr.use` |
| So'rov | `{attachment_id: UUID (majburiy, avval `POST /attachments`ga yuklangan — `17-api-umumiy.md` §12, ≤10 MB), doc_type_hint: "purchase"\|"catalog" (majburiy)}` |
| Javob | `202 {job_id, status: "processing"}` |
| Xatolar | `VALIDATION_ERROR`, `AI_LIMIT_EXCEEDED`, `AI_PROVIDER_UNAVAILABLE`, `403 AI_CONSENT_REQUIRED` (tenant `ai_cross_border_enabled=false` — 40h rozilik berilmagan, qaror #61), `403 AI_FEATURE_DISABLED` (`params.feature="ocr"` — tenantda `ai.ocr_enabled=false`) |
| Idempotency-Key | Majburiy |
| Offline | Ishlamaydi (AI chaqiruvi online talab qiladi) |
| Bog'langan | AI-03; BO-04 (purchase), BO-21 (catalog) |

### 74. `GET /ai/ocr/jobs/{job_id}`

| | |
|---|---|
| Maqsad | OCR natijasini olish — maydon bo'yicha ishonch darajasi bilan (summa ≥95%, sana ≥90%, miqdor/nom ≥80% — `22-ai-qatlami.md` §10) |
| Ruxsat | `ai.ocr.use` |
| So'rov | — |
| Javob | `{job_id, status: "processing"\|"done"\|"confirmed"\|"failed"\|"expired", doc_type_hint, fields: {header: {<maydon>: {value, confidence (0..1)}, ...}, lines: [{<maydon>: {value, confidence}, ...}]}, low_confidence_fields: ["lines[0].product_name", ...], error_code}` — past ishonchli maydonlar xato emas: `200`, `low_confidence_fields[]` UI'da sariq belgilanadi (qaror #55) |
| Xatolar | `NOT_FOUND` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | AI-03; BO-04, BO-15, BO-21 |

### 75. `POST /ai/ocr/jobs/{job_id}/confirm`

| | |
|---|---|
| Maqsad | Foydalanuvchi tasdiqlagan/tuzatgan maydonlar bilan hujjat loyihasini **to'g'ridan-to'g'ri** yaratish (AI hech qachon o'zi hujjat yozmaydi — foydalanuvchi `fields`ni o'qib, tuzatib, hujjat shaklida yuboradi) |
| Ruxsat | `ai.ocr.use` **va** `doc_type_hint`ga mos modul ruxsati: `purchase` → `purchases.receive`; `catalog` → `catalog.manage` |
| So'rov | `doc_type_hint`ga qarab tana shakli: `purchase` — `POST /goods-receipts` (`19-api-ombor.md` §8) bilan **bir xil** (`supplier_id, warehouse_id, doc_date, paid_immediately, lines[...]`); `catalog` — `{products: [...]}` (+ miqdor ko'rsatilgan bo'lsa `stock_opening_lines: [...]`) |
| Javob | `201 {created_doc_type: "goods_receipts"\|"stock_openings"\|null, created_doc_id: UUID\|null, created_product_ids: [UUID], status}` — `purchase`: `created_doc_type="goods_receipts"`, `created_product_ids=[]`; `catalog`: yaratilgan mahsulotlar `created_product_ids` da, qoldiq berilgan bo'lsa `created_doc_type="stock_openings"`, aks holda `null`; hujjat `status="draft"` — yakuniy tasdiq/o'tkazish oddiy hujjat oqimi orqali (`POST /goods-receipts/{id}/post` va h.k., boshqa modul faylida) |
| Xatolar | `VALIDATION_ERROR`, `409 {code:"DOC_INVALID_STATE"}` (job allaqachon `confirmed`/`expired`) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | AI-03; BO-04, BO-15, BO-21; audit: AI hech qachon avtomatik tasdiqlamaydi (`09-ai-funksiyalar.md` Asosiy xulosa #3) |

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
| Ruxsat | `ai.chat.use` (loyiha chiqarish — ko'rish/matn) |
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
| Ruxsat | `debts.remind` (`ai.chat.use` emas: mijozga xabar yuborish AI huquqi bilan emas, alohida kod bilan himoyalanadi) |
| So'rov | `{counterparty_id: UUID (majburiy), message_text: string (majburiy — tasdiqlangan yakuniy matn), channel: "telegram"\|"sms" (majburiy, `counterparties.notify_consent=true` talab qiladi)}` |
| Javob | `201 {notification_log_id, status: "sent"\|"queued"}` |
| Xatolar | `422 {code:"NOTIFY_CONSENT_REQUIRED"}` (`notify_consent=false` bo'lsa — `17-api-umumiy.md` §15), `NOT_FOUND` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | AI-06; BO-06; audit: AI matnini odam tasdiqlashi majburiy (`09-ai-funksiyalar.md` Asosiy xulosa #3) |

### 79. `GET /ai/usage`

| | |
|---|---|
| Maqsad | Joriy oy AI token/so'rov sarfi va qolgan limit (`plans.limits.ai_monthly_tokens`, `22-ai-qatlami.md` §5) |
| Ruxsat | `ai.chat.use` |
| So'rov | — |
| Javob | `{period: "2026-10", tokens_used, tokens_limit, requests_by_feature: {"AI-01": int, "AI-03": int, "AI-05": int, "AI-06": int}, pct_used}` |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | `22-ai-qatlami.md` §5 (80% ogohlantirish); BO-13, BO-19 |

---

## M19 — 1C integratsiyasi API — `33-1c-integratsiya.md` §10

1C integratsiyasining veb API'si (BO-22, BO-23 uchun **55 endpoint, W-01…W-55**: `/onec-agents`, `/onec-bases`, `/onec-branch-bindings`, `/onec-settings`, `/onec-catalog-items`, `/onec-mappings`, `/onec-value-mappings`, `/onec-ref-create-requests`, `/onec-export-batches`, `/onec-reconciliations`, `/onec-object-refs`, `/onec-status`) — indeks, obyekt shakllari va har endpoint tafsiloti **faqat `33-1c-integratsiya.md` §10 da**; bu faylda takrorlanmaydi. Qisqacha qoidalar:

- Umumiy konventsiyalar (`17-api-umumiy.md`) to'liq amal qiladi: BFF cookie + `X-CSRF-Token`, barcha `POST/PUT/PATCH/DELETE` da `Idempotency-Key`, `require_subscription_ok`, xato konverti; ro'yxatlar — hujjat turidagilar cursor, ma'lumotnoma turidagilar page; OpenAPI teg `onec`; faqat onlayn.
- Ruxsatlar — 7 ta `onec.*` kod (`15-xavfsizlik-va-audit.md` §2.1–2.2); avto-tasdiqni yoqish — faqat Egasi.
- Xato kodlari — «1C integratsiyasi» domeni, 81 ta `ONEC_*` (`17-api-umumiy.md` §15).
- Agent ↔ server protokoli (`/api/v1/onec-agent/*`, A-01…A-10) bu seriyaga kirmaydi — alohida agent tokeni (`14-autentifikatsiya-oauth2.md` §2.3), `33-1c-integratsiya.md` §9.
- M19 — MVP'dan keyin, Bosqich 7 (qaror #37).

---

## Ochiq savollar

1. **Tashqi javob kerak** — ommaviy oferta va AI provayderiga (chegaradan tashqari) ma'lumot uzatish roziligi matni (`terms_versions` ning birinchi versiyasi), yurist — interim: `ai_cross_border_enabled=false` standart, 40h faqat joriy `terms_versions` versiyasini qabul qiladi, AI-03 rasmlari rozilikgacha yuborilmaydi — 26 #127 (OQ-042).

## Manbalar

- `spec/kod-uchun/17-api-umumiy.md` — konventsiyalar, xato kodlari katalogi (bu fayl shunga bog'liq).
- `spec/kod-uchun/03-modullar-talablari.md` — M10–M18 foydalanuvchi hikoyalari.
- `spec/kod-uchun/06-ekranlar-umumiy.md` — BO-07/08/09/10/11/12/13/16/17/19/20, ADM-01.
- `spec/kod-uchun/09-ai-funksiyalar.md`, `spec/kod-uchun/22-ai-qatlami.md` — AI-01/03/05/06 arxitektura qoidalari, model routing, limitlar.
- `spec/kod-uchun/11-malumotlar-modeli.md` — jadval/maydon nomlari (§2–10).
- `spec/kod-uchun/13-provodka-qoidalari.md` — M11/M15/M16 provodka qoidalari.
- `spec/kod-uchun/15-xavfsizlik-va-audit.md` §2.1–2.3 — ruxsat kodlari, standart limitlar.
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` §18 — `/admin/users`, `/platform/*` (takrorlanmadi, faqat havola).
- `spec/kod-uchun/21-integratsiyalar.md` §9 — Click/Payme webhook protokoli.
