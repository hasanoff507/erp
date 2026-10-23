# API katalogi — 3. Moliya va Admin (M10–M18, AI; M19 — havola)

**Maqsad:** QQS, buxgalteriya, hisobotlar, huquqlar, filiallar, tenant sozlamalari, xarajatlar, kassa pul harakati, bank tushumi tasdig'i, obuna/billing, bildirishnomalar va AI endpoint'lari uchun API kontrakti; 1C integratsiyasi (M19) API'siga havola.
**Kim uchun:** Backend/frontend ishlab chiquvchilar, QA.
**Bog'liq fayllar:** `17-api-umumiy.md` (base path, ID/pul/sana format, pagination, headerlar, xato konverti, hujjat hayot sikli, xato kodlari katalogi — bu faylda takrorlanmaydi, faqat qo'llaniladi), `14-autentifikatsiya-oauth2.md` §18/§20 (auth/platforma admin/sync, bu faylda faqat havola), `16-offline-sync.md` §3, `03-modullar-talablari.md` (M10–M18), `06-ekranlar-umumiy.md`, `09-ai-funksiyalar.md`, `22-ai-qatlami.md`, `11-malumotlar-modeli.md`, `13-provodka-qoidalari.md` (§2.18a `bank_settlements`, §2.26/§4.3 `tax_settlements`), `15-xavfsizlik-va-audit.md` §2.1–2.2, `33-1c-integratsiya.md` §10 (1C integratsiyasi veb API — W-01…W-55).
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. **109 ta indeks qatori** 12 guruhda (+ `/platform/*` havolasi): M10 QQS (13: hisobot/registr 2, davlat hisoboti 7, `tax-settlements` 4 ta), M11 Buxgalteriya (8 + `ledger-adjustments` 2 ta + `stock-as-of` 1 — jami 11), M12 Hisobotlar (8), M13 Huquqlar (8: rol/ruxsat 6 + tenant qurilmalari 2 — BO-11 «Qurilmalar» tabi; foydalanuvchi CRUD'i `14-autentifikatsiya-oauth2.md`da), M14 Filiallar (13: filial 7, ombor 2, kassa 4), M13a/M14 Tenant sozlamalari (8: sozlamalar, soliq rejimi, integratsiya kalitlari, sinxron istisnolari, AI rozilik), M15 Xarajatlar (11), M16 Kassa pul harakati (4), M11/M16 Bank tushumi tasdig'i (8, `/bank-settlements` + ko'chirma importi), M17 Obuna (10 + `/billing/export-my-data` (65a) + platforma admin havolasi), M18 Bildirishnomalar (6), AI (8). M19 «1C integratsiyasi» (55 endpoint, W-01…W-55) — bu faylda **takrorlanmaydi**, faqat havola bo'limi (`33-1c-integratsiya.md` §10).
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
| 13a | `GET /reports/stock-as-of` | M11 | Hujjat sanasi bo'yicha tovar qoldig'i va 2910/2920 bilan solishtirish | `reports.finance.view` |
| 14 | `GET /period-closings` | M11 | Yopilgan davrlar ro'yxati | `accounting.post` |
| 15 | `POST /period-closings` | M11 | Davrni yopish | `accounting.period.close` |
| 16 | `GET /period-closings/{period}/readiness` | M11 | Yopishga tayyormi (recost, fiskal, qurilma sinxroni tekshiruvi) | `accounting.post` |
| 17 | `GET /reports/dashboard` | M12 | Egasi/Menejer dashboard ma'lumoti | `reports.sales.view` |
| 18 | `GET /reports/sales` | M12 | Savdo hisoboti (filial/davr) | `reports.sales.view` |
| 19 | `GET /reports/top-products` | M12 | Eng ko'p/kam sotilgan tovarlar | `reports.sales.view` |
| 19a | `GET /reports/discounts` | M12 | Chegirmalar summasi va ularning marjaga ta'siri (US-M03-03) | `reports.finance.view` |
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
| 40m | `GET /cloud-printers` · `POST /cloud-printers` | M14 | Bulut printerlar ro'yxati (BO-14, POS-16 `printer.cloud_id`) / ro'yxatga olish | `GET` — `cash_register.manage` yoki `sales.create`; `POST` — `cash_register.manage` |
| 40n | `PATCH /cloud-printers/{id}` | M14 | Bulut printerni tahrirlash, o'chirish/arxivlash | `cash_register.manage` |
| 40o | `POST /cloud-printers/{id}/secret` | M14 | Printer maxfiy kalitini almashtirish | `cash_register.manage` |
| 40p | `GET /cloud-printers/{id}/status` | M14 | Printer holati (`CloudPrintApi.status`) | `cash_register.manage` yoki `sales.create` |
| 40q | `POST /print-jobs` · `GET /print-jobs/{id}` | M01 | Chop etish ishini bulut printer navbatiga qo'yish / holati | `receipt`/`test` — `sales.create`; `label` — `labels.print` |
| 40r | `POST/GET/DELETE /print/cloudprnt` | M01 | Star CloudPRNT printer so'rov yo'li (`/api/v1` prefiksisiz) | printer `id` + maxfiy kalit (HTTP Basic), sessiyasiz |
| 40s | `POST /print/epson-sdp` | M01 | Epson Server Direct Print printer so'rov yo'li (`/api/v1` prefiksisiz) | printer `id` + maxfiy kalit (HTTP Basic), sessiyasiz |
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
| So'rov | `?period=2026-10` (majburiy, `YYYY-MM`), `?branch_id=` (ixtiyoriy). Filial cheklovi (`15-xavfsizlik-va-audit.md` §2.4): filialga cheklangan foydalanuvchi faqat o'z filialini so'raydi (boshqasi — `403 PERMISSION_DENIED`), `branch_id` siz aylanma faqat uning filiallari bo'yicha yig'iladi; QQS rejimi (tenant ko'rsatkichi) faqat cheklanmagan foydalanuvchiga |
| Javob | `{period, regime: "vat"\|"turnover", output_vat, input_vat, net_vat, pending_credit_red_invoices, pending_credit_pct, pending_credit_invoices: [{einvoice_id, number, doc_date, counterparty_id, counterparty_name, risk_flag, total_amount, vat_amount, credited_vat, pending_vat, credit_status}], turnover_base, turnover_rate_pct, turnover_amount, tax_settlement_id}` — `regime` davr oxirgi kunida amaldagi `tenant_tax_regimes` qatoridan (qator yo'q — `vat`); boshqa rejim maydonlari `null`. `regime=vat`: QQS tenant ko'rsatkichi (qaror #31), `branch_id` uni toraytirmaydi; `pending_credit_red_invoices` — davrdagi kiruvchi e-fakturalar (`risk_flag IN ('red','unknown')`, QQS > 0, krediti hali to'liq ochilmagan: `pending_vat = vat_amount − Σ shu fakturaning input vat_moves` > 0, 13 §2.8, §2.16) soni, `pending_credit_pct` = Σ `pending_vat` ÷ (`input_vat` + Σ `pending_vat`) × 100; `pending_credit_invoices` — shu fakturalar alohida ro'yxatda (`credited_vat` — to'lov bilan ochilgan qism, `credit_status`: `pending` — kredit hali tasdiqlanmagan, `partial` — qisman ochilgan), `doc_date, id` tartibida (BO-07 «Riskli kiruvchi e-fakturalar», BO-10, US-M10-03, QT-M10-04); `regime=turnover` da — `null`. `regime=turnover`: filial bo'yicha `turnover_base` (13 §4.3 formulasi, `ledger_entries` davr oborotlari; rejim almashgan oyda faqat `turnover` amal qilgan kunlar), tamaki ulushi `tobacco` stavkasida, qolgani filial stavkasida; `turnover_rate_pct` — bitta filial tamakisiz bo'lsa filial stavkasi, aks holda samarali stavka (`turnover_amount ÷ turnover_base × 100`); `tax_settlement_id` — shu davr uchun `posted` `tax_settlements` hujjati (yo'q bo'lsa `null`, 8a–8d) |
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
| Javob | `{items: [{id, kind, period, base_amount, vat_amount, doc_type, doc_id, einvoice_id, created_at}], next_cursor}` — registr tenant bo'yicha (filial ustuni yo'q), shuning uchun faqat filialga cheklanmagan foydalanuvchiga (aks holda `403 PERMISSION_DENIED`) |
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
| So'rov | Cursor; filtr `?tax_kind=&period=&status=&branch_id=` (filialga cheklangan foydalanuvchi — faqat o'z filiallari) |
| Javob | `{items: [TaxSettlement], next_cursor}` (yangisi birinchi); bitta hujjat — `GET /tax-settlements/{id}` (`TaxSettlement`, `tax.vat.view`) |
| Xatolar | `VALIDATION_ERROR`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish |
| Bog'langan | US-M10-01; BO-07 |

#### 8b. `POST /tax-settlements`

| | |
|---|---|
| Maqsad | Davr uchun qoralama — summani **server hisoblaydi**: `vat_offset` — `base_amount`/`amount` = davr `vat_moves` (`kind=input`, hisobga olinadigan, `pending_credit_*` dan tashqari); `turnover_tax` — `base_amount` = `turnover_base`, `rate` = `turnover_rate_pct`, `amount = base_amount × rate / 100` (`GET /reports/vat-summary` bilan bir xil hisob) |
| Ruxsat | `accounting.post` |
| So'rov | `{tax_kind: "vat_offset"\|"turnover_tax" (majburiy, tenant rejimiga mos), period: "YYYY-MM" (majburiy), branch_id: UUID (faqat `tax_kind='turnover_tax'` da majburiy — aylanma solig'i filial bo'yicha, SK 468-modda 2-qism; `vat_offset` da yuborilmaydi — server `branches.is_default = true` filialini yozadi), doc_date: date (standart — davrning oxirgi kuni; davr ichida va ≤ bugun bo'lishi shart — `validation.doc_date_outside_period` / `validation.doc_date_in_future`), comment?: string}` — summa maydonlari tanadan qabul qilinmaydi. `turnover_tax` da `rate` — filial stavkasi (tamaki ulushi bo'lsa samarali stavka, `amount` guruhlar bo'yicha aniq yig'indi). `vat_offset` — tenant ko'rsatkichi, faqat filialga cheklanmagan foydalanuvchi yaratadi/o'tkazadi/bekor qiladi (aks holda `PERMISSION_DENIED`). `vat_offset` — (tenant, davr) bo'yicha, `vat_moves` tenant bo'yicha yig'iladi (qaror #31 — 1 tenant = 1 STIR) |
| Javob | `201 TaxSettlement` (`status="draft"`) |
| Xatolar | `VALIDATION_ERROR` (`tax_kind` davrdagi `tenant_tax_regimes`ga mos emas — davrning birorta kunida ham shu rejim amalda bo'lmagan (rejim almashgan oyda `turnover_tax` ham, `vat_offset` ham qabul qilinadi, `13-provodka-qoidalari.md` §2.26) — `validation.tax_kind_regime_mismatch`; `vat_offset` — (tenant, davr), `turnover_tax` — (filial, davr) uchun `draft`/`posted` hujjat allaqachon bor — `validation.tax_settlement_exists`, `params.existing_id`; `vat_offset` da `branch_id` yuborilgan — `validation.branch_not_allowed_for_vat_offset`), `PERIOD_CLOSED`, `BRANCH_SCOPE_DENIED`, `PERMISSION_DENIED` |
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
| Javob | `201 LedgerAdjustment` = `{id, number ("BX-…"), status: "posted", branch_id, doc_date, account_dt, account_kt, amount, correction_of_period, analytics, comment, created_by, created_at, posted_at, cancelled_at, cancel_reason}` — bitta `ledger_entries` qatori `Dt account_dt / Kt account_kt = amount`, `entry_date = doc_date`, `analytics` + `correction_of_period`; 4010/6010 bo'lsa shu tranzaksiyada `debt_moves` (`receivable`/`payable`, `doc_type='ledger_adjustments'`, `13-provodka-qoidalari.md` §2.14); `cash_moves` yozilmaydi (kassadagi naqd — faqat kassa hujjatlari) |
| Xatolar | `VALIDATION_ERROR` — `validation.account_not_allowed` (hisob rejada yo'q yoki ishlatilmaydi, 13 §1), `validation.account_register_managed` (2910/2920/2970 — tovar qiymati faqat ombor hujjatlari bilan), `validation.same_account`, `validation.positive`, `validation.required` (`comment`; 4010/6010/6310 da `analytics.counterparty_id`), `validation.not_allowed` (13 §1 dan tashqari `analytics` kaliti), `validation.doc_date_in_future`, `validation.opening_entry_date` (`0000` yozuvi `go_live_date − 1` dan boshqa sanada, `params.expected`; `go_live_date` yo'q — `validation.go_live_date_missing`), `validation.correction_period_not_closed` (`correction_of_period` yopilmagan oy), `validation.adjustment_exceeds_balance` (`params.available`, `params.balance` = `receivable`\|`payable`\|`advance_6310`: Kt 4010 > mijozning debitorlik qoldig'i, Dt 6010 > kreditorlik qoldig'i, Dt 6310 > mijozning 6310 kredit qoldig'i — BO-06 «Keyingi qarzga hisoblash»), `validation.branch_not_found`; `PERIOD_CLOSED` (`doc_date` yopilgan davrda bo'lsa), `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-06 («Keyingi qarzga hisoblash» — `Dt 6310 / Kt 4010`, `analytics.counterparty_id`), BO-08; audit: `ledger_adjustment.posted` (`entity='ledger_adjustments'`) majburiy |

### 10a. `POST /ledger-adjustments/{id}/cancel`

| | |
|---|---|
| Maqsad | Tuzatuvchi yozuvni bekor qilish (storno — alohida teskari hujjat yo'q, `01-qarorlar.md` #6). Yopilgan davrdagi hujjat ham bekor qilinadi — storno joriy ochiq davr sanasida (`13-provodka-qoidalari.md` §5.2) |
| Ruxsat | `accounting.post` |
| So'rov | `{reason: string (majburiy)}` |
| Javob | `200 {id, status: "cancelled", cancelled_at}` — storno qatori (Dt/Kt almashgan, `reversal_of_id`) va `debt_moves` stornosi; audit `ledger_adjustment.cancelled` |
| Xatolar | `DOC_ALREADY_CANCELLED`, `NOT_FOUND`, `VALIDATION_ERROR` (`validation.adjustment_exceeds_balance` — storno qoldiqni manfiyga tushirsa, masalan iste'mol qilingan 6310 avansini qaytarish) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08; audit majburiy |

### 10b. `GET /ledger-adjustments`

| | |
|---|---|
| Maqsad | Qo'lda kiritilgan tuzatuvchi yozuvlar ro'yxati |
| Ruxsat | `accounting.post` |
| So'rov | Cursor; filtr `?doc_date__gte=&doc_date__lte=&status=&branch_id=` |
| Javob | `{items: [LedgerAdjustment], next_cursor}` (`doc_date DESC, id DESC`; filialga cheklangan foydalanuvchi — faqat o'z filiallari, boshqa `branch_id` → `403 BRANCH_SCOPE_DENIED`) |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08 |

### 11. `GET /reports/trial-balance`

| | |
|---|---|
| Maqsad | Aylanma-saldo vedomosti (oborot-saldo) — har hisob bo'yicha boshlang'ich/aylanma/yakuniy qoldiq |
| Ruxsat | `reports.finance.view` |
| So'rov | `?period=2026-10&branch_id=&account=` (`branch_id` bo'lmasa — foydalanuvchi filiallari, cheklanmagan foydalanuvchida konsolidatsiya, `13-provodka-qoidalari.md` §5.4; boshqa filial → `403 BRANCH_SCOPE_DENIED`; `account` — bitta hisob, 4 raqam) |
| Javob | `{period, date_from, date_to, branch_id, rows: [{account, name, type, opening_balance, debit_turnover, credit_turnover, closing_balance, by_tax_type}], totals: {debit_turnover, credit_turnover}}` — qoldiq ishorasi **debet-musbat** (`Σ Dt − Σ Kt`; passiv hisob qoldig'i manfiy), `opening_balance` — davr boshigacha, `closing_balance = opening + debit − credit`; faqat harakati yoki qoldig'i bor hisoblar; 4410/6410 qatorlarida `by_tax_type: [{tax_type (analytics.tax_type, yo'q bo'lsa "other"), …shu ko'rsatkichlar}]` (boshqa hisoblarda `null`) — BO-07 «Soliq hisob-kitobi (ST)» kartasidagi o'tkazishdan keyingi 6410 qoldig'i shu qatordan; `totals` — Σ debet = Σ kredit |
| Xatolar | `VALIDATION_ERROR` (`validation.period_format`), `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat oxirgi keshlangan hisobot |
| Bog'langan | US-M11-02; BO-08, BO-09 |

### 12. `GET /reports/profit-and-loss`

| | |
|---|---|
| Maqsad | Foyda-zarar hisoboti (daromad − COGS − xarajat, M15 bilan birga, US-M15-03) |
| Ruxsat | `reports.finance.view` |
| So'rov | `?period=2026-10&branch_id=` yoki `?date_from=&date_to=&branch_id=` (≤ 366 kun); ikkalasi ham bo'lmasa — joriy oy (Asia/Tashkent). `branch_id` bo'lmasa — foydalanuvchi filiallari (cheklanmagan foydalanuvchida konsolidatsiya, `13-provodka-qoidalari.md` §5.4); boshqa filial `branch_id` → `403 BRANCH_SCOPE_DENIED` |
| Javob | `{period, date_from, date_to, branch_id, discount_posting, revenue, returns, discounts, net_revenue, cogs, gross_profit, gross_margin_pct, other_income, expenses_by_category: [{category_id, category, account, source, amount}], expenses_total, net_profit, by_branch: [{branch_id, name, …shu ko'rsatkichlar}], unsynced_devices, data_complete}` — `ledger_entries` (`entry_date` davrda) aylanmalari, storno bilan sof: `revenue` = `Kt−Dt 9020`; `returns` = `Dt−Kt 9040`; `discounts` = `Dt−Kt 9050` (`discount_posting='net'` rejimida — Σ `sale_lines.discount_amount` QQSsiz, faqat ma'lumot uchun: 9020 allaqachon chegirmali); `net_revenue = revenue − returns − (Dt−Kt 9050)`; `cogs` = `Dt−Kt 9120` (qaytarishda tannarx qaytadi); `gross_profit = net_revenue − cogs`; `other_income` = `Kt−Dt 9390` (ortiqcha, hisobdan chiqarilgan qarz qaytishi va h.k.); `expenses_by_category` — `Dt−Kt 9410/9420/9430/9820`: `expenses` hujjatlari toifa bo'yicha (`source='expenses'`), qolganlari (hisobdan chiqarish, qarzni kechish, komissiya, aylanma solig'i) toifasiz, `source` = `doc_type`; `net_profit = gross_profit − expenses_total + other_income` (`13-provodka-qoidalari.md` §1, §5.1); soliq to'lovi (`tax_payment`, 6410) xarajat emas — kirmaydi; `by_branch` — faqat konsolidatsiyada (bir nechta filial); `data_complete=false` — sinxronlanmagan POS qurilmalari bor (§18) |
| Xatolar | `VALIDATION_ERROR` (`validation.period_format`, `validation.date_range`, `validation.date_range_too_long`), `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M11-03, US-M15-03; BO-02, BO-09 |

### 13. `GET /reports/balance-sheet`

| | |
|---|---|
| Maqsad | Balans hisoboti (aktiv/passiv/kapital, `13-provodka-qoidalari.md` §1 hisoblar bo'yicha) |
| Ruxsat | `reports.finance.view` |
| So'rov | `?as_of=2026-10-31&branch_id=` |
| Javob | `{as_of, branch_id, assets: [{account, name, amount}], liabilities: [...], equity: [...], total_assets, total_liabilities_and_equity, opening_balance_unresolved, opening_0000_balance, warnings: ["opening_0000_nonzero"]}` — `as_of` standart — bugun; qoldiq = `Σ Dt − Σ Kt` (`entry_date ≤ as_of`): aktiv — A va KA hisoblar (4910 — manfiy qator, 13 §2.15a), majburiyat — 6xxx (`−qoldiq`), kapital — 8xxx (`−qoldiq`) + `9910` «joriy natija» (`−Σ` 9xxx tranzit hisoblar qoldig'i — oylik yopish ularni nolga tushirmaydi, 13 §5.1) + `0000` (nol bo'lmasa, 13 §5.5 — `warnings` da `opening_0000_nonzero`, «Boshlang'ich qoldiqlar to'liq kiritilmagan»); `total_assets = total_liabilities_and_equity` har doim (QT-M11-12). Filial cheklovi #11 bilan bir xil |
| Xatolar | `VALIDATION_ERROR` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M11-02; BO-09 |

### 13a. `GET /reports/stock-as-of`

| | |
|---|---|
| Maqsad | Hujjat sanasi (`doc_date`) bo'yicha tovar qoldig'i va uning 2910/2920 buxgalteriya qoldig'i bilan solishtiruvi — back-office hujjati omborni `posted_at` da, provodkani `doc_date` da yozadi (`13-provodka-qoidalari.md` §3.3), shuning uchun o'tgan sanali kirim davr oxiri qoldig'ida faqat shu hisobotda ko'rinadi |
| Ruxsat | `reports.finance.view` |
| So'rov | `?as_of=2026-10-31` (majburiy, ≤ bugun — aks holda `validation.date_in_future`), `branch_id`, `warehouse_id` (ixtiyoriy) |
| Javob | `{as_of, basis: "doc_date", branch_id, warehouse_id, items: [{product_id, name, warehouse_id, branch_id, qty, value}], accounts: [{account, stock_value, ledger_value, difference}]}` — har `stock_moves` qatori o'z hujjatining `doc_date` ida (storno qatorlari va `transfers` — o'z biznes sanasida, Asia/Tashkent) hisoblanadi; `ledger_value` — shu sanagacha 2910/2920 qoldig'i, `difference = ledger_value − stock_value` (`warehouse_id` berilganda `null`) |
| Xatolar | `VALIDATION_ERROR`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08, BO-09 |

### 14. `GET /period-closings`

| | |
|---|---|
| Maqsad | Yopilgan davrlar ro'yxati |
| Ruxsat | `accounting.post` |
| So'rov | Cursor |
| Javob | `{items: [{period, closed_at, closed_by}], next_cursor}` (yangisi birinchi, `period DESC`) |
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
| Xatolar | `PERIOD_ALREADY_CLOSED` (davr ≤ oxirgi yopilgan oy), `PERIOD_CLOSE_OUT_OF_ORDER` (`409` — faqat **eng eski ochiq oy** yopiladi: oxirgi yopilgan oydan keyingi oy, hali yopilgan oy bo'lmasa — birinchi buxgalteriya faoliyati oyi (eng erta `ledger_entries.entry_date` yoki `go_live_date − 1`); `params.expected_period`), `VALIDATION_ERROR` (`validation.period_format`; `validation.period_not_ended` — oyning oxirgi kuni ≥ bugun (Asia/Tashkent)), `PERIOD_CLOSE_NOT_READY` (16-endpoint `blockers[]` bo'sh emas: `recost_pending`, `fiscal_pending`, `devices_unsynced`, `params.blockers`; `warnings[]` yopishni bloklamaydi; yopish tenantning davr-yopish qulfini eksklyuziv oladi — har posting uni umumiy (shared) ushlaydi, ~10 s ichida bo'shamasa `params.blockers = ["postings_in_progress"]`; tayyorlik shu qulf ostida qayta tekshiriladi) — davr yopilgach **qayta ochilmaydi** (qaror #23 — tavsiya #15); keyingi tuzatish faqat `POST /ledger-adjustments` (10-endpoint) bilan joriy ochiq davrda |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M11-02; BO-08; audit majburiy |

### 16. `GET /period-closings/{period}/readiness`

| | |
|---|---|
| Maqsad | Davrni yopishdan oldin tekshiruv (`23-backend-arxitekturasi.md` §2.4) |
| Ruxsat | `accounting.post` |
| So'rov | — (`period` path parametri `YYYY-MM`) |
| Javob | `{period, ready: bool, blockers: ["recost_pending"\|"fiscal_pending"\|"devices_unsynced"], warnings: ["tax_settlement_missing"\|"tax_settlement_stale"\|"opening_0000_nonzero"\|"open_shifts"\|"drafts_in_period"\|"devices_not_synced_after_period_end"\|"ledger_stock_mismatch"], pending_recost_jobs: int, pending_fiscal_receipts: int, unsynced_devices: [{device_id, cash_register_name, outbox_pending_count, outbox_oldest_pending_at}], opening_balance_unresolved: bool, opening_0000_balance, stale_tax_settlements: [{id, tax_kind, branch_id, amount, current_amount}], ledger_stock_mismatches: [{account, ledger_balance, stock_value, difference}]}` — `ready = (blockers = [])`. Shartlar: `recost_pending` (bloker) — `recost_jobs.status IN ('queued','running','failed') AND from_date ≤ period_end`; `fiscal_pending` (bloker) — davr cheklari (`fiscal_receipts.created_at` ning Asia/Tashkent sanasi davrda) `status IN ('pending','sent','failed')` yoki `status='fiscalized' AND ofd_acked_at IS NULL` (z_report'dan tashqari) — b5 fiskal `fiscal_readiness`; `pending_fiscal_receipts` — ularning soni; `devices_unsynced` (bloker) — `devices.kind IN ('web','android') AND revoked_at IS NULL AND outbox_pending_count > 0 AND outbox_oldest_pending_at < period_end + 1 kun` (hal qilish — sinxronlash yoki qurilmani bekor qilish, `confirm_pending_loss`, `16-offline-sync.md` §9); `devices_not_synced_after_period_end` (ogohlantirish) — davr tugashidan oldin ro'yxatdan o'tgan faol qurilmaning `last_sync_at` (yo'q yoki) `< period_end + 1 kun`; `tax_settlement_missing` (ogohlantirish) — davrda amalda bo'lgan rejim uchun `posted` hujjat yo'q (QQS: davrda hisobga olinadigan kiruvchi QQS bor; aylanma: bazasi ≠ 0 filial); `tax_settlement_stale` (ogohlantirish) — davrning `posted` `tax_settlements.amount` joriy figuradan farq qiladi (`stale_tax_settlements` — `amount` va qayta hisoblangan `current_amount`; `13-provodka-qoidalari.md` §5.1); `opening_0000_nonzero` — 0000 qoldig'i ≠ 0 (13 §5.5); `open_shifts` — davr tugashidan oldin ochilgan va hali ochiq smenalar; `drafts_in_period` — davr sanali `draft` (inventarizatsiyada `counting`/`review`) posting hujjatlari; `ledger_stock_mismatch` (ACC-09) — 2910/2920 buxgalteriya qoldig'i shu hisobga bog'langan omborlar `Σ stock_balances.value` dan farq qiladi (`ledger_stock_mismatches`; davr bo'yicha tafsilot — 13a). Yopilgan davrga kech kelgan POS voqealari rad etilmaydi — registr yozuvlari birinchi ochiq davrda (`16-offline-sync.md` §3.4, qaror #69) |
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
| So'rov | `?period=today\|week\|month&branch_id=` — `today` (standart); `week` — joriy kalendar hafta dushanbadan bugungacha; `month` — oyning 1-sanasidan bugungacha (Asia/Tashkent). `branch_id` bo'lmasa — foydalanuvchi filiallari (bir nechta filialga kirishi bo'lsa «Barchasi», US-M14-01); boshqa filial → `403 BRANCH_SCOPE_DENIED` |
| Javob | `{period, date_from, date_to, branch_id, total_sales, gross_sales, returns_total, receipt_count, avg_receipt, previous_total_sales, net_profit, expenses_total, cash_on_hand, by_branch: [{branch_id, name, sales, receipt_count, avg_receipt, profit, cash_on_hand, low_stock_count}], top_products: [{product_id, name, unit_code, qty}], receivables: {total, debtors_count, overdue_count, overdue_amount}, stock: {value, positions, low_stock_count, expiring_lots}, alerts: [{type, message_key, severity, count, amount, route}], unsynced_devices, data_complete}` — savdo formulalari §18 bilan bir xil; `previous_total_sales` — shu uzunlikdagi oldingi davr («kecha bilan»); `net_profit`/`profit` = §12 `net_profit` (US-M15-03), `expenses_total` = §12 `expenses_total` (US-M11-03 — aylanma, xarajat, sof foyda sodda raqamlar), ikkalasi ham `reports.finance.view` bo'lmasa `null`; `cash_on_hand` — davr oxirida kassadagi naqd (har kassaning oxirgi smenasi: yopilgan bo'lsa `counted_cash`, aks holda `opening_cash + Σ cash_moves(cash)`); `receivables` — ochiq debitorlik hujjatlari (allokatsiyalar va qaytarishlar hisobga olingan, `debt_balances` ga eng eskisidan moslashtirilgan, `13-provodka-qoidalari.md` §2.14); `overdue_*` va `alerts.overdue_debts` — muddati o'tganlikning yagona ta'rifi #21 bo'yicha (va'da sanasi hisobga olinmaydi), `debts.payment.accept` yoki `reports.finance.view` bo'lmasa `null`; `stock` — `stock.view` bo'lmasa `null`. `alerts[]` — BO-02 «Diqqat talab qiladi» va topbar qo'ng'irog'ining yagona manbai (`06-ekranlar-umumiy.md` §1.9), muhimlik tartibida, faqat `count > 0`: `fiscal_unacked` (critical; OFD tasdig'isiz 24 soatdan eski chekli kassalar soni) → `/app/settings/branches`; `state_report_diff` (critical; `tax.compare.review`\|`tax.vat.view`) → `/app/tax/reconciliation`; `unsynced_devices` (warning) → `/app/settings/users?tab=devices`; `cash_variance` (warning; davrda farq bilan yopilgan smenalar, `amount` = Σ\|farq\|) → `/app/reports?report=cash-history`; `overdue_debts` (warning; `debts.payment.accept`\|`reports.finance.view`) → `/app/debts`; `low_stock` (warning; `stock.view`; `qty ≤ min_stock`, US-M04-02) → `/app/warehouse/stock?lowStockOnly=1`; `expiring_lots` (warning; `stock.view`; `expiry_warning_days` ichida) → `/app/warehouse/stock?expiringWithinDays=7`; `sync_exceptions` (warning; `settings.tenant`\|`accounting.post`) → `/app/settings/tenant?tab=sync-exceptions`; `pending_approvals` (info; foydalanuvchi limiti yetadigan `permission_code`lar) → `/app/approvals`; `einvoices_awaiting_signature` (info; `einvoice.sign`) → `/app/einvoices`. `message_key` = `reports.alerts.<type>`. Filial o'lchovi yo'q (tenant bo'yicha) ogohlantirishlar faqat filial bilan cheklanmagan foydalanuvchiga ko'rsatiladi |
| Xatolar | `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan ma'lumot, `"N daqiqa oldin"` belgisi bilan (BO-02) |
| Bog'langan | US-M12-01; BO-02 |

### 18. `GET /reports/sales`

| | |
|---|---|
| Maqsad | Savdo hisoboti — filial/davr bo'yicha jami savdo, chek soni, o'rtacha chek. `total_sales = Σ sales.total_amount (posted) − Σ returns.total` |
| Ruxsat | `reports.sales.view` |
| So'rov | `?date_from=&date_to=&branch_id=&group_by=day\|branch\|cashier` — sanalar standarti bugun (Asia/Tashkent, `doc_date`), davr ≤ 366 kun; `group_by` standarti `day` |
| Javob | `{date_from, date_to, branch_id, group_by, rows: [{group_key, group_label, total_sales, gross_sales, returns_total, receipt_count, avg_receipt}], total: {…}, unsynced_devices, data_complete}` — `gross_sales` = Σ `sales.total_amount` (posted), `returns_total` = Σ `return_lines.line_total` (posted qaytarishlar, qaytarish sanasi bo'yicha), `total_sales = gross_sales − returns_total`, `receipt_count` — posted sotuvlar soni, `avg_receipt = gross_sales ÷ receipt_count` (o'rtacha chek — qaytarish uni kamaytirmaydi); `group_by=day` — davrning har kuni (savdosiz kun nol bilan), `branch` — `group_label` = filial nomi, `cashier` — `sales.created_by` (`group_label` = xodim ismi); `data_complete=false` va `unsynced_devices` — scope'dagi POS qurilmalarida yuborilmagan voqealar bor (`devices.outbox_pending_count > 0`, QT-M12-04 «faqat sinxronlangan ma'lumot») |
| Xatolar | `VALIDATION_ERROR` (`validation.date_range`, `validation.date_range_too_long`), `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M12-01; BO-02, BO-09 |

### 19. `GET /reports/top-products`

| | |
|---|---|
| Maqsad | Eng ko'p/kam sotiladigan tovarlar (US-M12-02) |
| Ruxsat | `reports.sales.view` |
| So'rov | `?date_from=&date_to=&branch_id=&order=top\|bottom&limit=20` (`limit` 1–200; sanalar — §18 kabi) |
| Javob | `{date_from, date_to, branch_id, order, items: [{product_id, name, unit_code, qty_sold, revenue}], unsynced_devices, data_complete}` — davrda sotilgan tovarlar, qaytarishlar ayirilgan: `qty_sold` = Σ `sale_lines.qty` − Σ `return_lines.qty`, `revenue` = Σ `line_total` (QQS bilan, chegirmadan keyin) − qaytarishlar; `top` — `qty_sold` kamayish tartibida (teng bo'lsa `revenue`, nom), `bottom` — o'sish tartibida |
| Xatolar | `VALIDATION_ERROR`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M12-02; BO-09 |

### 19a. `GET /reports/discounts`

| | |
|---|---|
| Maqsad | Berilgan chegirmalar summasi va ular tufayli kamaygan marja (US-M03-03, QT-M03-03) |
| Ruxsat | `reports.finance.view` (tannarx va marja) |
| So'rov | `?date_from=&date_to=&branch_id=&group_by=day\|branch\|cashier\|product` (sanalar — §18 kabi; `group_by` standarti `day`) |
| Javob | `{date_from, date_to, branch_id, group_by, rows: [{group_key, group_label, sales_total, discount_total, discount_net, revenue_net, cost, margin, margin_without_discounts, margin_pct, margin_pct_without_discounts}], total: {…}, unsynced_devices, data_complete}` — posted sotuv qatorlari, qaytarishlar ayirilgan: `sales_total` = Σ `line_total`; `discount_total` = Σ `discount_amount` (QQS bilan; qaytarishda qaytarilgan miqdorga proporsional ulushi ayiriladi); `discount_net` — chegirma QQSsiz (`× 100/(100+stavka)`), chegirma tufayli yo'qotilgan marja (`gross_9050` rejimidagi `Dt 9050` bilan bir xil, `13-provodka-qoidalari.md` §2.1a); `revenue_net` = Σ (`line_total − vat_amount`); `cost` = Σ `cost_amount`; `margin = revenue_net − cost`; `margin_without_discounts = margin + discount_net`; foizlar — `margin ÷ revenue_net` va `margin_without_discounts ÷ (revenue_net + discount_net)` |
| Xatolar | `VALIDATION_ERROR`, `BRANCH_SCOPE_DENIED` |
| Idempotency-Key | Kerak emas |
| Offline | Faqat kesh |
| Bog'langan | US-M03-03; BO-09 |

### 20. `GET /reports/stock`

| | |
|---|---|
| Maqsad | Qoldiq hisoboti (ombor/filial bo'yicha, minimal daraja belgisi) |
| Ruxsat | `stock.view` |
| So'rov | `?branch_id=&warehouse_id=&below_min_only=true&search=&category_id=` — `branch_id` bo'sh = foydalanuvchi filiallari bo'yicha konsolidatsiya (BO-03 «Barchasi», US-M04-03); `search` — nom/ruscha nom (qism) yoki shtrix-kod (aniq), ≤ 64 |
| Javob | `{branch_id, consolidated, items: [{product_id, name, name_ru, unit_code, category_id, category_name, barcode, is_marked, is_weighed, min_stock, qty, value, avg_cost, below_min, by_branch: [{branch_id, branch_name, qty, value, below_min}]}], branches: [{branch_id, name, value, positions, below_min_count}], total: {value, positions, below_min_count}}` — `stock_balances` (ombor → filial) yig'indisi; qatorda birlik, kategoriya, asosiy shtrix-kod (EAN, keyin ichki) va markirovka belgisi bor — veb tovar kartalarini alohida so'ramaydi; `below_min` — `qty ≤ products.min_stock` (filial qatorida o'z omborlari bo'yicha, tovar qatorida — biror filialda); arxivlangan tovar nol qoldiq bilan chiqmaydi |
| Xatolar | `VALIDATION_ERROR`, `BRANCH_SCOPE_DENIED` (boshqa filial yoki boshqa filial ombori) |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish, IndexedDB'dagi oxirgi nusxa (BO-03) |
| Bog'langan | US-M12-01; BO-03, BO-09 |

### 21. `GET /reports/debts-aging`

| | |
|---|---|
| Maqsad | Qarzdorlik "yosh" guruhlari (0-30 / 31-60 / 60+ kun), BO-06/BO-09 uchun manba. **Yagona/kanonik endpoint** (`18-api-kassa.md` §12.8 shu yerga havola qiladi); BO-04 "Men qarzdorman" tabi ham `direction=payable` bilan shu yerdan foydalanadi |
| Ruxsat | `reports.finance.view` **yoki** `debts.approve` |
| So'rov | `?direction=receivable\|payable&as_of=2026-10-15&branch_id=&bucket=0-30\|31-60\|60+&limit_exceeded_offline=` |
| Javob | `{as_of, direction, summary: {total, count, buckets: [{bucket, count, amount}]}, rows: [{counterparty_id, name, phone, balance, credit_limit, due_date, overdue_since, days_overdue, bucket: "0-30"\|"31-60"\|"60+", promise_date, open_docs, doubtful_flag: bool, doubtful_flag_id, limit_exceeded_offline: bool, last_payment_amount, last_payment_date}]}` — qatorlar: balansi musbat kontragentlar (`days_overdue` kamayishi, so'ng `balance` bo'yicha); `overdue_since = min(COALESCE(due_date, doc_date))` kontragentning ochiq hujjatlari bo'yicha (`receivable` — `sales`/`debt_openings` ochiq qoldiqlari allokatsiyalardan, receivable balansiga moslashtirilgan — `13-provodka-qoidalari.md` §2.14; `payable` — balansni eng yangi kirimlar/boshlang'ich qarzlar tashkil qiladi deb, FIFO). **Muddati o'tganlik — tizim bo'yicha yagona ta'rif**: debitorlik hujjati `as_of` kuni muddati o'tgan, agar `COALESCE(due_date, doc_date) < as_of`; mijozning va'da sanasi (`counterparties.debt_due_date`) muddatni **surmaydi** (yosh guruhlari 60+ shubhali qarz ko'rigi va yil oxiri rezerv inventarizatsiyasiga xizmat qiladi; 26 #185). Dashboard (#17), `21-integratsiyalar.md` §11 Telegram kunlik hisoboti va `18-api-kassa.md` §12.1 shu ta'rifga havola qiladi; va'da sanasi faqat ko'rsatiladi va `debt_due_today` eslatmasini (`va'da ?? eng eski ochiq due_date ≤ bugun`) qo'zg'atadi; `due_date` — shu eng eski ochiq hujjat muddati (yo'q bo'lsa `null`); `days_overdue = max(0, as_of − overdue_since)`; `bucket` shundan; `as_of` (≤ bugun) — yosh hisoblanadigan sana, qoldiqlar joriy (`doc_date > as_of` hujjatlar olinmaydi); `branch_id` berilsa `balance` — shu filial ochiq hujjatlari yig'indisi; filialga cheklangan foydalanuvchi (`Scope`): `branch_id` ruxsat etilmagan filial bo'lsa — `403 BRANCH_SCOPE_DENIED`, `branch_id`siz — ochiq hujjatlar ruxsat etilgan filiallar bo'yicha filtrlanadi, `balance` = filtrlangan hujjatlar yig'indisi (`branch_id` filtri bilan bir xil yo'l); `summary` — `bucket`/`limit_exceeded_offline` filtrlaridan oldingi jami (tab hisoblagichlari); `promise_date` — `counterparties.debt_due_date` (faqat ko'rsatiladi) |
| Xatolar | `VALIDATION_ERROR`, `BRANCH_SCOPE_DENIED` |
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
| Maqsad | Qurilmani bekor qilish: `devices.revoked_at`, qurilmaga bog'langan barcha sessiya/refresh oilalari va ularning tirik access tokenlari darhol, litsenziya tokeni bekor; shu qurilmada ishlagan xodimlar PIN'i majburiy almashtiriladi — tenant-lokal: faqat shu tenant xodimi bo'lsa kredensial PIN'i, boshqa tenantda ham faol bo'lsa faqat shu tenantdagi `memberships.pin_reset_at` (`16-offline-sync.md` §9, `14-autentifikatsiya-oauth2.md` §7.2/§17). Sinxronlanmagan voqea bo'lsa (`has_pending=true`) — `confirm_pending_loss=true` talab qilinadi; UI avval qurilmada `sync.drain`ni taklif qiladi (qaror #56) |
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
| Xatolar | `VALIDATION_ERROR` (`fiscal_agent_id` va `fiscal_local_device_id` juftligi buzilgan — `validation.fiscal_agent_pair`; agent shu tenantda topilmadi — `validation.not_found`; agent `revoked` — `validation.fiscal_agent_inactive`; `capabilities.fiscal.enabled` `true` emas — `validation.fiscal_capability_disabled`; `local_id` agentning `capabilities.fiscal.devices[]` ida yo'q — `validation.fiscal_local_device_unknown`; shu agent + `local_id` boshqa faol kassaga bog'langan (bitta FM — bitta kassa) — `validation.fiscal_local_device_taken`), `VERSION_CONFLICT`, `409 {code:"RESOURCE_ARCHIVED"}` (arxivlangan kassa — `17-api-umumiy.md` §15) |
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
| Javob | `TenantSettings` + `{tax_regime: {current, history: [...]}, integrations: {ofd: {status}, faktura_uz: {status, connected_at}, didox: {status, connected_at}, crpt: {status, key_last4}, click: {status, connected_at}, payme: {status, connected_at}, uzum: {status, connected_at}, uzqr: {status, connected_at, cash_register_ids: [...]}}, version}` — `status`: `"connected"\|"not_connected"`; `ofd.status` `cash_registers.ofd_status` (`registered`/`active`) dan hosila; kalitli integratsiyalarda qo'shimcha `last_ok_at`, `last_error`, `last_error_at` — shu kalit bilan oxirgi tashqi chaqiruv natijasi (`tenant_secrets`, xato matnida sir yo'q); sirlar hech qachon qaytmaydi |
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

> `provider` ∈ `faktura-uz`, `didox`, `crpt`, `click`, `payme`, `uzum`, `uzqr` → `tenant_secrets.kind` (`faktura_uz`, `didox`, `crpt`, `click`, `payme`, `uzum`, `uzqr`). Sotuv to'lovlari merchant'i — **tenantning o'zi** (pul to'g'ridan-to'g'ri do'konga tushadi); platforma merchant kaliti faqat M17 billing uchun, bu endpoint orqali kiritilmaydi (qaror #46). `fiscal_partner`, `eimzo` sirlari — platforma boshqaradi (deploy konfiguratsiyasi), tenant API'si yo'q.

| | |
|---|---|
| Maqsad | Integratsiya kalitlarini kiritish/yangilash |
| Ruxsat | `settings.tenant` |
| So'rov | `faktura-uz`: `{login, password, client_id, client_secret}` (tenantning o'z Faktura.uz hisobi va kabinetida yaratilgan API mijozi); `didox`: `{login, password}` (tenantning STIR/JShShIR'i va paroli; hamkor tokeni — platforma konfiguratsiyasi); `crpt`: `{api_key}` (`crpt_api_key`, faqat qabul/tekshiruv/qaytarish/hisobdan chiqarish uchun — sotuvda kod fiskal chek ichida OFD orqali ketadi, qaror #62); `click`: `{merchant_id, service_id, secret_key, merchant_user_id?, provider_autofiscal_disabled_confirmed: true}` (`merchant_id`/`service_id`/`merchant_user_id` — raqamlar); `payme`: `{merchant_id, key, test_mode?: bool, provider_autofiscal_disabled_confirmed: true}` (`test_mode` — `checkout.test.paycom.uz`, kalit — kabinetdagi `TEST_KEY`); `uzum`: `{merchant_id, login, password, dynamic_qr_service_id?, dynamic_qr_user_id?, dynamic_qr_secret_key?, provider_autofiscal_disabled_confirmed: true}` (`merchant_id` — Merchant API `serviceId`, `login`/`password` — webhook Basic Auth; `dynamic_qr_*` — Uzum Dynamic QR kredensiallari, uchalasi birga, kassa QR'i uchun shart) — `click`/`payme`/`uzum` da `provider_autofiscal_disabled_confirmed: true` majburiy (provayder kabinetida avtofiskalizatsiya o'chirilganini tasdiqlash; server `settings.payment_providers.{provider}.autofiscal_off_confirmed_at = now()` yozadi); `uzqr`: `{cash_register_id?: UUID, merchant_id, terminal_id, api_key?}` (`tenant_secrets.cash_register_id` — har kassa uchun alohida; `api_key` — kassaning dinamik QR API kaliti, faqat `cash_register_id` bilan; statik QR hozir, dinamik QR — `UzqrPort` stub, qaror #64). Payme `key` va Uzum `login`+`password` boshqa tenantda ulangan bo'lsa — `VALIDATION_ERROR` (`validation.integration_key_in_use`): webhook tenantni shu kredensial barmoq izi bilan topadi (`18-api-kassa.md` §16.4). Hammasi `tenant_secrets.ciphertext` da konvert-shifrlangan (KEK — o'z sir ombori, qaror #65), javobda hech qachon qaytmaydi |
| Javob | `200 {provider, status: "connected", connected_at}` — server provayderda tekshiradi (Faktura.uz — token olish, CRPT — kalit tekshiruvi, to'lov provayderlari — test so'rovi mavjud bo'lsa) |
| Xatolar | `503 {code:"EINVOICE_PROVIDER_UNAVAILABLE"}` (faktura-uz, didox) / `503 {code:"MARKING_VERIFY_UNAVAILABLE"}` (crpt), `VALIDATION_ERROR` (noma'lum `provider` — `validation.invalid_choice`, provayderga tegishli bo'lmagan maydon — `validation.extra_forbidden`, maydon yetishmaydi — `validation.required`, `click`/`payme`/`uzum` da `provider_autofiscal_disabled_confirmed` yo'q yoki `false` — `validation.autofiscal_confirmation_required`, `validation.integration_key_in_use`), `NOT_FOUND` (`cash_register_id` — boshqa tenantniki yoki arxivlangan) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | BO-14; `21-integratsiyalar.md` §2/§4/§9; audit majburiy (sir qiymatisiz): `tenant_integration.connected` / `tenant_integration.updated` (`after`: provayder, kassa, maydon **nomlari**) |

### 40e. `DELETE /tenant/integrations/{provider}`

| | |
|---|---|
| Maqsad | Integratsiyani uzish (`provider` — 40d ro'yxati; `uzqr` uchun `?cash_register_id=`); audit `tenant_integration.disconnected` |
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
| Javob | `{items: [{id, kind, device_id, branch_id, client_event_id, doc_type, doc_id, details, created_at, reviewed_at, reviewed_by, review_note}], next_cursor}` (yangisi birinchi; filialga cheklangan foydalanuvchi faqat o'z filiallari qatorlarini ko'radi) — `branch_id` hosila (`devices.cash_register_id → cash_registers.branch_id`; `sync_exceptions`da ustun yo'q) |
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

### 40m–40s. Bulut printerlar va chop etish navbati (qaror #21)

> Modul `modules/integrations/cloud_print`, OpenAPI teg `cloud_print`; DDL — `12-db-sxema.md` §2.5a (`cloud_printers`, `print_jobs`, `0028a fiscal_edocs`); klient — `24-frontend-arxitekturasi.md` §6.1 `CloudPrintAdapter` (`CloudPrintApi.submit` → 40q, `CloudPrintApi.status` → 40p). Printer serverni o'zi so'raydi (do'konda kiruvchi port kerak emas); printer sozlamasida URL = `https://<api-domen>` + `poll_path`, foydalanuvchi = printer `id`, parol = maxfiy kalit.

`CloudPrinter` obyekti: `{id, branch_id, name, protocol ("star_cloudprnt"|"epson_sdp"), model, status ("active"|"disabled"|"archived"), poll_path ("/print/cloudprnt"|"/print/epson-sdp"), printer_mac, last_poll_at, last_status, online, version}` — `online` = oxirgi so'rov 60 s ichida.

| Endpoint | Tafsilot |
|---|---|
| 40m `GET /cloud-printers` | `?branch_id=&status=&page=&size=` → `{items: [CloudPrinter], total, page, size}` (page pagination; arxivlanganlar `status=archived` bilan); filial doirasi bo'yicha. Kassir (`sales.create`) POS-16 da `printer.cloud_id`ni shu ro'yxatdan tanlaydi |
| 40m `POST /cloud-printers` | `{branch_id, name, protocol, model?}` → `201 CloudPrinter + secret` — `secret` (32 bayt tasodifiy, base64url) **faqat shu javobda** ko'rsatiladi, bazada `secret_hash` (SHA-256); Idempotency-Key majburiy; audit `cloud_printer.created` |
| 40n `PATCH /cloud-printers/{id}` | `{name?, model?, status?, version}` — `VERSION_CONFLICT`; arxivlangan printer o'zgarmaydi (`validation.cloud_printer_archived`); `disabled`/`archived` printer so'rovi `401` oladi; audit `cloud_printer.updated` / `cloud_printer.archived` |
| 40o `POST /cloud-printers/{id}/secret` | yangi `secret` (bir marta), eskisi darhol ishlamaydi; audit `cloud_printer.secret_rotated` |
| 40p `GET /cloud-printers/{id}/status` | `{id, online, status, last_poll_at, last_status, pending}` (`pending` — `queued`+`printing` ishlar) |
| 40q `POST /print-jobs` | `{id (UUIDv7, klient), cloud_printer_id, kind ("receipt"\|"test"\|"label"), raster: {width_dots (8–1024), height_dots (1–20000), data_base64}}` — 1 bit/piksel, qator `ceil(width_dots/8)` bayt, chap piksel — eng katta bit, `1` — qora; `ceil(w/8)·h ≤ 600000` bayt; mos kelmasa `422 VALIDATION_ERROR` (`raster`, `validation.print_raster_invalid`). Printer faol va joriy filialda bo'lishi shart (`validation.cloud_printer_inactive`, `validation.cloud_printer_other_branch`). Javob `201 {id, cloud_printer_id, kind, status: "queued", result_code}`; **idempotent `id` bo'yicha**: shu `id`, printer, `kind` va raster bilan takror → `200` saqlangan ish; boshqa mazmun → `422` (`id`, `validation.print_job_id_reused`); Idempotency-Key ham majburiy (umumiy qoida). Ish 30 daqiqada olinmasa → `failed` (`result_code='expired'`) |
| 40q `GET /print-jobs/{id}` | `{id, cloud_printer_id, kind, status ("queued"\|"printing"\|"done"\|"failed"), result_code}` |
| 40r `/print/cloudprnt` | Star CloudPRNT HTTP: `POST` — printer holati JSON (`printerMAC`, `statusCode`, …) → `{"jobReady": false}` yoki `{"jobReady": true, "mediaTypes": ["image/png"], "jobToken": "<job id>"}` (navbatdagi eng eski ish; `printing` ish bor bo'lsa — `false`, bir vaqtda bitta); `GET ?mac=&type=image/png&token=` → 1 bitli PNG (`queued` → `printing`); `DELETE ?mac=&code=&token=` (yoki `deleteMethod=GET` varianti — `GET …&delete`) — `code` `2xx` → `done`, `520` (yuklash taymauti) → yana `queued`, boshqasi → `failed` (`result_code` = kod). Manba: Star Micronics «CloudPRNT Protocol Guide» ([star-m.jp](https://www.star-m.jp/products/s_print/CloudPRNTSDK/Documentation/en/developerguide/index.html)), mos server namunasi [github.com/star-micronics/cloudprnt-sdk](https://github.com/star-micronics/cloudprnt-sdk) `ExampleServers/php_queue/cloudprnt.php` |
| 40s `/print/epson-sdp` | Epson Server Direct Print: `POST` `application/x-www-form-urlencoded` — `ConnectionType=GetRequest` → `PrintRequestInfo Version="2.00"` (har ish — `<ePOSPrint>`: `Parameter/devid=local_printer`, `timeout`, `printjobid` = ish `id`; `PrintData` — ePOS-Print XML `<image width height color="color_1" mode="mono">` raster + `feed`, `cut`; ≤ 5 ish) yoki bo'sh javob; `ConnectionType=SetResponse` + `ResponseFile` (`PrintResponseInfo` 1.00 — natijalar so'rov tartibida, 2.00 — `printjobid` bo'yicha; `success="true"` → `done`, aks holda `failed`, `code`); javob berilmagan ish → `failed` (`no_result`). Manba: Seiko Epson «Server Direct Print User's Manual» va namuna dasturi (Server Direct Print Sample Program 5.0.0E) |

Printer so'rovi: HTTP Basic (`username` = printer `id`, `password` = maxfiy kalit) → `app.cloud_printer_by_secret` (`12-db-sxema.md` §4.5) tenantni aniqlaydi, keyin oddiy RLS ostida; noma'lum printer, noto'g'ri kalit, `active` bo'lmagan printer yoki boshqa protokol yo'li → `401` (`WWW-Authenticate: Basic`), tafsilotsiz. `/print/*` — `/api/v1` dan tashqarida, Idempotency-Key yo'q (`23-backend-arxitekturasi.md` §3: dedupe — ish `id`/`jobToken`). Ish printerga bir marta beriladi (`queued → printing`); tasdiqlanmagan `printing` ish 5 daqiqadan keyin `failed` (`unconfirmed`) — **hech qachon avtomatik qayta chop etilmaydi** (chek ikki marta chiqmasligi uchun). Yakuniy holatda `print_jobs.data` `NULL` qilinadi.

---

## M15 — Xarajatlar

### 41. `GET /expenses`

| | |
|---|---|
| Maqsad | Xarajatlar ro'yxati |
| Ruxsat | `expenses.create` |
| So'rov | Cursor (`doc_date`, `id` kamayish tartibida); filtr `?category_id=&branch_id=&source=&doc_date__gte=&doc_date__lte=&status=` |
| Javob | `{items: [Expense], next_cursor, totals: {posted, draft}}` — `Expense` = `{id, number, branch_id, doc_date, status, category_id, category_name, account, amount, source, tax_type, cash_register_id, shift_id, attachment_id, recurring_rule_id, comment, created_by, created_at, posted_at, cancelled_at, cancel_reason, device_id, approval_request_id, approval_status}`; `account` — Dt hisobi (o'tkazilganda provodkadagi, qoralamada toifaning joriy `default_account`i); `approval_status` — oxirgi `expense_over_limit` so'rovi holati (BO-17 «Tasdiq kutmoqda»); `totals` — filtr bo'yicha `posted` va `draft` jamlari (bekor qilinganlar kirmaydi) |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish (BO-17) |
| Bog'langan | US-M15-01; BO-17 |

### 42. `POST /expenses`

| | |
|---|---|
| Maqsad | Xarajat qoralamasi yaratish (10 soniyada, US-M15-01) |
| Ruxsat | `expenses.create` |
| So'rov | `{doc_date: date (majburiy, standart bugun), branch_id: UUID (majburiy, standart `X-Branch-Id`), category_id: UUID (majburiy), amount: string (majburiy, >0), source: "cash"\|"bank"\|"card" (majburiy), cash_register_id: UUID (source=cash bo'lsa majburiy), shift_id: UUID (source=cash bo'lsa majburiy), attachment_id: UUID (ixtiyoriy), comment: string (ixtiyoriy), recurring_rule_id: UUID (ixtiyoriy), tax_type: "vat"\|"turnover"\|"pit"\|"social"\|"property"\|"land"\|"other" (toifa `default_account="6410"` — soliq to'lovi — bo'lsa majburiy, aks holda yuborilmaydi; MVP'da 6410 ga faqat `vat`/`turnover` hisoblanadi — boshqa qiymat rad etiladi, mol-mulk/yer/boshqa soliqlar `period_taxes` (9430), ijtimoiy soliq/JShDS — ish haqi toifalari, `13-provodka-qoidalari.md` §2.26)}` |
| Javob | `201 Expense` (41-endpoint obyekti, `status: "draft"`) |
| Xatolar | `VALIDATION_ERROR` (`tax_type` soliq toifasida yo'q — `validation.required`, boshqa toifada berilgan — `validation.must_be_null`, 6410 toifasida `vat`/`turnover` emas — `validation.tax_type_not_accrued` (yaratish, tahrir, `post`, takroriy xarajat, `expense.created`); `doc_date` kelajakda; toifa arxivlangan — `validation.archived`; `source=cash` da `cash_register_id`/`shift_id` yo'q yoki boshqa manbada berilgan), `NOT_FOUND` (`expense_category`), `SHIFT_NOT_OPEN`, `PERIOD_CLOSED` |
| Idempotency-Key | Majburiy |
| Offline | `source='cash'` — POS'dan `expense.created` voqeasi (`18-api-kassa.md` §13.2, POS-14 «Xarajat»; offline ham): payload — `18-api-kassa.md` §13.2 maydonlari (`id`, `doc_date`, `branch_id`, `cash_register_id`, `shift_id`, `category_id`, `amount`, `comment?`, `tax_type?`, `approval?`; `source` yuborilmaydi — har doim `cash`, `attachment_id`/`recurring_rule_id` yo'q); ruxsat `cash.withdraw` (limit) — Kassirda `expenses.create` yo'q; limitdan oshsa `approval` (`ApprovalRef`, `kind='cash_withdrawal_over_limit'`); server `ExpensePostingService` bilan `draft` yaratmasdan darhol `posted`. Boshqa manba (`bank`/`card`) — faqat shu endpoint, online |
| Bog'langan | US-M15-01; BO-17 |

### 43. `POST /expenses/{id}/post`

| | |
|---|---|
| Maqsad | Xarajatni o'tkazish — `ExpensePostingService` (`13-provodka-qoidalari.md` §2.17): `ledger_entries` (Dt = toifaning `default_account`: `9410`/`9420`/`9430`, soliq to'lovi — `6410` (`Dt 6410 / Kt 5110`)) + (agar `source=cash`) `cash_moves`; `source="bank"\|"card"` — Kt 5110 (MVP'da yagona bank hisobi, qaror #49) |
| Ruxsat | `expenses.create`; summa o'tkazuvchining `expenses.approve` `limit_value`idan oshsa tasdiq kerak (`15-xavfsizlik-va-audit.md` §2.1, §2.3; Egasi — limitsiz; `expenses.approve` kodi yo'q rol — har summada tasdiq) |
| So'rov | Tana yo'q |
| Javob | `200 {id, status: "posted", number, posted_at}` yoki limitdan oshsa `202 {id, status: "draft", approval_request_id}` (`APPROVAL_REQUIRED`, `approval_requests(kind='expense_over_limit', linked_doc_type='expenses')` + `over_limit_action` xabari — hujjat `draft`da qoladi, `pending_approval`ga o'tmaydi; `price_changes`dan farqli bu umumiy qoida). Kutilayotgan so'rov bo'lsa qayta `post` o'sha `approval_request_id`ni qaytaradi. BO-16 da tasdiqlanganda server qoralamani shu tranzaksiyada o'tkazadi (so'rov `consumed`, `doc_approvals(mode='remote_request')`); tasdiqlangan, hali ishlatilmagan so'rov bo'lsa keyingi `post` ham uni ishlatib o'tkazadi. Toifaning **o'tkazish paytidagi** `default_account`i va `tax_type` qoidasi qo'llanadi |
| Xatolar | `DOC_NOT_DRAFT`, `PERIOD_CLOSED`, `SHIFT_NOT_OPEN` (`source=cash`, smena yopilgan), `VALIDATION_ERROR` (`tax_type`), `APPROVAL_REQUEST_ALREADY_RESOLVED` |
| Idempotency-Key | Majburiy |
| Offline | `source=cash` bo'lsa offline postinglanadi, sinxronlashda serverga tushadi |
| Bog'langan | US-M15-01, US-M15-03; BO-17 |

### 44. `POST /expenses/{id}/cancel`

| | |
|---|---|
| Maqsad | Xarajatni bekor qilish (teskari yozuv, `13-provodka-qoidalari.md` §5.2). Yopilgan davrdagi hujjat ham bekor qilinadi — storno joriy ochiq davr sanasida |
| Ruxsat | `expenses.create` |
| So'rov | `{reason: string (majburiy, 3–500 belgi)}` |
| Javob | `200 {id, status: "cancelled", cancelled_at}` — `draft` → `cancelled`; `posted` → ledger storno + (naqd) teskari `cash_moves` qatori (`reversal_of_id`); yozuv o'chirilmaydi |
| Xatolar | `DOC_ALREADY_CANCELLED`; `DOC_INVALID_STATE` — `source=cash` xarajatining smenasi yopilgan (yopilgan smenaning kutilgan naqdi o'zgarmaydi, 54-endpoint bilan bir xil; tuzatish — ochiq smenada kassaga pul qo'yish) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q (bekor qilish faqat online) |
| Bog'langan | M15 chekka holat ("xarajat bekor qilinsa — teskari yozuv"); BO-17; audit majburiy |

### 45. `GET /expense-categories`

| | |
|---|---|
| Maqsad | Xarajat toifalari ro'yxati (standart ro'yxat — `13-provodka-qoidalari.md` §2.17 seed xaritasi, 21 kod) |
| Ruxsat | `—` |
| So'rov | `?include_archived=true\|false` (standart `true`; POS-14 keshi faqat arxivlanmaganlarni ishlatadi) |
| Javob | `{items: [{id, code, name, default_account: "9410"\|"9420"\|"9430"\|"6410", source_ref, is_system, archived_at, version}]}` — `default_account` xarajat provodkasining Dt hisobi (43-endpoint); `6410` — «Soliq to'lovi (byudjetga)» (`tax_payment`, `expenses.tax_type` majburiy); `code`/`source_ref` — seed/import manbasi (tizim toifalarida to'ldirilgan) |
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
| Javob | `201 {id, code, name, default_account, source_ref, is_system, archived_at, version}` (`code`/`source_ref` = `null`, `is_system=false`) |
| Xatolar | `VALIDATION_ERROR` (nom takrori — `validation.duplicate`, katta-kichik harf farqsiz) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M15-01; BO-17 |

### 47. `PATCH /expense-categories/{id}`

| | |
|---|---|
| Maqsad | Toifani tahrirlash/arxivlash |
| Ruxsat | `expenses.create` |
| So'rov | `{name?: string, default_account?: "9410"\|"9420"\|"9430"\|"6410", archived?: bool, version: int (majburiy)}` — `default_account` o'zgarishi faqat keyingi xarajatlarga ta'sir qiladi; `default_account` xarajat hisobi (`94xx`) va `6410` (soliq to'lovi) orasida o'zgarmaydi (`422 validation.not_allowed` — `tax_type` ma'nosi o'zgarib qolmasligi uchun; tizim `tax_payment` toifasi har doim `6410`) |
| Javob | `200 {id, code, name, default_account, source_ref, is_system, archived_at, version}` |
| Xatolar | `VALIDATION_ERROR`, `VERSION_CONFLICT` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M15-01; BO-17 |

### 48. `GET /recurring-expenses`

| | |
|---|---|
| Maqsad | Takrorlanuvchi xarajat qoidalari (US-M15-02, oylik ijara va h.k.) |
| Ruxsat | `expenses.create` |
| So'rov | Page pagination; `branch_id` — `X-Branch-Id` header orqali; `?is_active=` |
| Javob | `{items: [{id, name, branch_id, category_id, amount, day_of_month, period, source, cash_register_id, next_due_date, last_triggered_at, is_active, is_due, version}], total, page, size}` — `is_due` = faol va `next_due_date ≤ bugun` (BO-17 eslatma banneri); `last_triggered_at` — oxirgi eslatma vaqti |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Faqat ko'rish |
| Bog'langan | US-M15-02; BO-17 |

### 49. `POST /recurring-expenses`

| | |
|---|---|
| Maqsad | Yangi takrorlanuvchi qoida yaratish |
| Ruxsat | `expenses.create` |
| So'rov | `{name?: string (bo'sh bo'lsa UI toifa nomini ko'rsatadi), category_id: UUID (majburiy), amount: string (majburiy), day_of_month: int 1-28 (majburiy), period: "month"\|"quarter"\|"year" (majburiy), source: "cash"\|"bank"\|"card" (majburiy), cash_register_id?: UUID (`source="cash"` bo'lsa majburiy, boshqa manbada yuborilmaydi; qoida filialining kassasi), branch_id?: UUID (standart `X-Branch-Id`)}`. `next_due_date` — bugundan boshlab birinchi `day_of_month`. `6410` toifali (soliq to'lovi) qoida yaratilmaydi — soliq summasi har davr o'zgaradi, `tax_type` bilan oddiy xarajat sifatida yoziladi |
| Javob | `201 {id, name, branch_id, category_id, amount, day_of_month, period, source, cash_register_id, next_due_date, last_triggered_at, is_active: true, is_due, version}` |
| Xatolar | `VALIDATION_ERROR` (`6410` toifa — `validation.not_allowed`, arxivlangan toifa, kassa boshqa filialda), `NOT_FOUND` |
| Idempotency-Key | Majburiy |
| Offline | Yo'q |
| Bog'langan | US-M15-02; BO-17 |

### 50. `PATCH /recurring-expenses/{id}`

| | |
|---|---|
| Maqsad | Qoidani tahrirlash/o'chirish (faollikni o'chirish) |
| Ruxsat | `expenses.create` |
| So'rov | `{name?, amount?, day_of_month?, is_active?: bool, version: int (majburiy)}` — `day_of_month` o'zgarsa joriy `next_due_date` shu davr ichida ko'chadi (muddati kelgan to'lov o'tkazib yuborilmaydi); qayta faollashtirilganda `next_due_date` bugungacha davrlar bo'yicha oldinga suriladi (to'xtatilgan davrlar uchun eslatma yo'q) |
| Javob | `200` — 48-endpoint qoida obyekti |
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
| Javob | `201 {expense_id, status: "posted"}` yoki summa qoidani tasdiqlayotgan foydalanuvchining `expenses.approve` limitidan oshsa `202 {expense_id, status: "draft", approval_request_id}` (`APPROVAL_REQUIRED` — 43-endpoint bilan bir xil qoida). Xarajat: `doc_date` = bugun, qoida filiali/toifasi/manbasi, `recurring_rule_id`, `comment` = qoida nomi; `source="cash"` — kassaning ochiq smenasida. Qoidaning `next_due_date`i bir davr oldinga suriladi. Faqat muddati kelgan (`next_due_date ≤ bugun`) faol qoida tasdiqlanadi. Eslatma: kunlik cron (09:00 Toshkent) muddati kelgan har faol qoida uchun bir marta (qoida × muddat) `recurring_expense_due` bildirishnomasini yozadi (`text`: «Ijara to'lash vaqti: 3 000 000 so'm»), xarajat avtomatik yaratilmaydi |
| Xatolar | `VALIDATION_ERROR` (`validation.recurring_expense_not_due`, `validation.recurring_expense_inactive`), `SHIFT_NOT_OPEN` (`source="cash"` bo'lgan qoidada ochiq smena bo'lmasa) |
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
| So'rov | `{cash_register_id: UUID (majburiy), shift_id: UUID (majburiy, faol smena), direction: "in"\|"out" (majburiy), amount: string (majburiy, >0), reason: "collection"\|"deposit"\|"owner_withdrawal"\|"other" (majburiy), account?: "9430"\|"9390"\|"6310"\|"4010"\|"4730" (faqat `reason="other"`; standart `out` → `9430`, `in` → `9390`), employee_id?: UUID (`account="4730"` da majburiy), counterparty_id?: UUID (`reason="owner_withdrawal"` da — `tenants.legal_form ≠ sole_proprietor` bo'lsa majburiy, `counterparties.is_founder=true` bo'lgan ta'sischi, provodka Dt `tenants.settings.owner_withdrawal_account`; `reason="other"` va `account ∈ {6310, 4010}` da majburiy), comment: string (`reason="other"`da majburiy), doc_date: date (majburiy)}`. `reason↔direction` juftligi: `collection`, `owner_withdrawal` → faqat `out`; `deposit` → faqat `in`; `other` → ikkalasi. Provodka (`13-provodka-qoidalari.md` §2.18): `other/out` → `Dt account / Kt 5010`, `other/in` → `Dt 5010 / Kt account`. `reason="collection"` (inkassa) — kassadan 5710 ga (`payment_method="collection"`), bank tasdig'i — 55c–55h. `doc_date` kelajakda bo'lmaydi (`validation.doc_date_in_future`), yopilgan davrda — `409 PERIOD_CLOSED` |
| Javob | `201 {id, status: "posted", amount, approval_request_id: null}` yoki limitdan oshsa `202 {id, status: "draft", amount, approval_request_id}` (`APPROVAL_REQUIRED` — `kind="cash_withdrawal_over_limit"`, BO-16; hujjat `draft` da, registrlarga yozilmaydi). So'rov BO-16 da tasdiqlanganda server qoralamani o'sha tranzaksiyada o'tkazadi (so'rov `consumed`, `doc_approvals(mode='remote_request')`; smena yopilgan bo'lsa tasdiqlash `409 SHIFT_NOT_OPEN`) |
| Xatolar | `VALIDATION_ERROR` (`reason↔direction` juftligi buzilgan; `account` `reason≠other` da berilgan yoki ro'yxatda yo'q; `employee_id` yoki `counterparty_id` talab qilinganda yo'q; `owner_withdrawal` da kontragent ta'sischi emas; `direction=in` + `account=4010` — `field=account`, `validation.cash_movement_debt_repayment` (mijoz qarzi faqat qarz to'lovi orqali, `18-api-kassa.md` §12.2/§12.3); `direction=out` + `account=4010` va `amount` mijozning 4010 kreditidan (`max(−receivable_balance, 0)`, `debt_balances` qulfi ostida) katta — `field=amount`, `validation.cash_movement_exceeds_customer_credit`, `params.available`; `13-provodka-qoidalari.md` §2.18), `CASH_WITHDRAW_LIMIT_EXCEEDED` |
| Idempotency-Key | Majburiy (back-office'dan); POS'dan — `/sync/push` orqali `cash_movement.created` voqeasi (`16-offline-sync.md` §2) |
| Offline | To'liq offline (M01 bilan bir xil append-only, `03-modullar-talablari.md` M16) |
| Bog'langan | US-M16-01; POS ekrani, BO-16 (limitdan oshganda) |

### 54. `POST /cash-movements/{id}/cancel`

| | |
|---|---|
| Maqsad | Harakatni bekor qilish: `posted` — ledger storno + teskari `cash_moves` qatori (`reversal_of_id`), faqat smena ochiq bo'lsa; `draft` (tasdiq kutayotgan) — faqat `cancelled` |
| Ruxsat | Yaratuvchi huquqi (`cash.deposit`/`cash.withdraw`); bekor qilish — teskari yo'nalish huquqi va limiti: `posted` `in` (qo'yilgan pul) ni bekor qilish pulni kassadan oladi — `cash.withdraw` va uning limiti (`ApprovalGate`, `kind='cash_withdrawal_over_limit'`; limitdan oshsa `403 CASH_WITHDRAW_LIMIT_EXCEEDED`, Egasi — limitsiz) |
| So'rov | `{reason: string (majburiy)}` |
| Javob | `200 {id, status: "cancelled"}` |
| Xatolar | `DOC_ALREADY_CANCELLED`; `DOC_INVALID_STATE` — smena yopilgan (yopilgan smenaning kutilgan naqdi o'zgarmaydi; tuzatish — yangi harakat ochiq smenada) |
| Idempotency-Key | Majburiy |
| Offline | Yo'q (faqat online) |
| Bog'langan | US-M16-01; audit majburiy |

### 55. `GET /cash-registers/{id}/cash-history`

| | |
|---|---|
| Maqsad | Smena/kassa bo'yicha naqd tarixi: boshlanish, sotuvlar, qo'yilgan/olingan, kutilgan vs sanalgan, farq (US-M16-03) |
| Ruxsat | `cash.count.shift` **yoki** `reports.sales.view` (Egasida `cash.count.shift` yo'q, lekin US-M16-03 "Egasi sifatida" ko'rishni talab qiladi) |
| So'rov | `?date_from=&date_to=` |
| Javob | `{items: [{shift_id, shift_no, status, opened_at, closed_at, opening_cash, cash_sales, cash_in, cash_out, expected_cash, counted_cash, variance, variance_note, counted_card_total}]}` — `cash_sales` — smena sotuvlarining naqd to'lovlari, `cash_in`/`cash_out` — `posted` kassa pul harakatlari; ochiq smenada `expected_cash` joriy hisob, `counted_cash`/`variance` `null`; `date_from`/`date_to` — smena ochilgan sana (Toshkent) bo'yicha |
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
| Maqsad | BO-24 «yo'ldagi pul qoldig'i» paneli: 5710 qoldig'i filial × to'lov usuli bo'yicha (`ledger_entries`: `account_dt='5710'` summalari minus `account_kt='5710'` summalari, `entry_date ≤ as_of`, guruhlash `branch_id` × `analytics.payment_method`; storno qatorlari ham kiradi) — 55c/55e dagi tekshiruv bilan bir xil hisob (5710 ga yozadigan har bir provodka `analytics.payment_method` ni to'ldiradi) |
| Ruxsat | `bank_settlements.manage` |
| So'rov | `?as_of=<date>` (standart — bugun, Toshkent), `?branch_id=` (ixtiyoriy) |
| Javob | `{as_of, items: [{branch_id, method, balance, oldest_unsettled_date, card_breakdown}]}` — faqat `balance ≠ "0.00"` qatorlar; `oldest_unsettled_date` — FIFO bo'yicha yopilmagan eng eski tushum sanasi (ma'lumot uchun); `card_breakdown` — faqat `method="card"` da (boshqasida `null`): `{integrated, manual}` — `balance` ning integratsiyalangan (`card_entry_mode='integrated'`, `rrn` bo'yicha moslashtiriladi) va terminalsiz (`manual`, summa/sana va filial/merchant bo'yicha moslashtiriladi) qismlari, ma'lumot uchun: `integrated` = 5710 `card` qatorlaridan `analytics.rrn` borlari (faqat integratsiyalangan to'lov provodkasida bo'ladi, `13` §2.2) sof yig'indisi minus `rrn` bo'yicha moslashtirilib `post` qilingan tranzaksiyalar `approved_amount`i, `[0, balance]` oralig'iga cheklangan; `manual = balance − integrated` (BO-24 "Karta (terminalsiz)" qatori; `21` §9.2) |
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
| Xatolar | `VALIDATION_ERROR` (enum, sana tartibi — `validation.date_range`, `doc_date` kelajakda — `validation.doc_date_in_future`, `commission_amount ≥ gross_amount` — `validation.bank_commission_ge_gross`; `variance_amount ≠ 0` va `method ≠ "collection"` — `validation.not_allowed`; `net_amount ≤ 0` — `validation.must_be_positive`; `gross_amount` shu filial va usul bo'yicha `doc_date` holatidagi 5710 qoldig'idan katta — `details[].field="gross_amount"`, `details[].message_key="validation.bank_settlement_exceeds_in_transit"`, `params.available`), `PERIOD_CLOSED` (`doc_date` yopilgan davrda), `BRANCH_SCOPE_DENIED`, `NOT_FOUND` (`attachment_id`) |
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
| Xatolar | `DOC_NOT_DRAFT`, `PERIOD_CLOSED`, `VALIDATION_ERROR` (`gross_amount` shu filial va usul bo'yicha `doc_date` holatidagi va joriy 5710 qoldig'ining kichigidan oshadi — yakuniy tekshiruv hujjat qatori `FOR UPDATE` va (filial, usul) tranzaksiya advisory qulfi ostida, `params.available`) |
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
| Moslashtirish | Har kirim qatori uchun: (1) `method` — to'lovchi (ekvayer bank / Click / Payme / Uzum / inkassa) va `НазначениеПлатежа` kalit so'zlari bo'yicha; (2) filial — to'lov maqsadidagi terminal/merchant identifikatori bo'yicha, aks holda `branch_id`; (3) moslashtirish birligi — (filial, `method`, `entry_date`) kunlik 5710 sof kirimi (`bank_settlements` dan boshqa barcha hujjatlarning `Dt 5710 − Kt 5710` i: sotuv minus kartaga qaytarish va h.k.); har kun summasidan `posted` va ochiq `draft` `bank_settlements` (shu import ichida yaratilganlari ham) band qilgan summa ayiriladi — har hujjat avval o'z `settled_from`…`settled_to` kunlaridan (eskisidan), qolgani eng eski kunlardan (ikki marta band qilinmaydi); qolgan kunlardan eng eskisidan boshlab `n` ta kun olinadi — `Σ ≥ kirim` va `(Σ − kirim) / Σ ≤ 5%` bo'lgan eng kichik `n`; `gross_amount = Σ`, `settled_from`/`settled_to` — shu kunlar oralig'i, `doc_date` — kirim sanasi; karta (`method="card"`) kirimida: `НазначениеПлатежа` ekvayer reestrini bersa (`RRN` kalit so'zidan keyin vergul/bo'sh joy bilan ajratilgan RRN ro'yxati, masalan `RRN: 000000000001, 000000000002`) — shu filialning hali hech bir bank tushumi tasdig'iga bog'lanmagan `approved` integratsiyalangan xaridlari `card_terminal_transactions.rrn` bo'yicha moslashtiriladi (`gross_amount` = ularning `approved_amount` yig'indisi, `settled_from`/`settled_to` — ularning biznes kunlari; tranzaksiyalarga qoralama yaratilganda `card_terminal_transactions.bank_settlement_id` yoziladi, hujjat bekor qilinganda tozalanadi; shu kunlardagi reestrda yo'q integratsiyalangan xaridlar javobda `unmatched_card_transactions`), reestr bo'lmasa, lekin `НазначениеПлатежа`da terminal TID/MID (`card_terminals.tid`/`mid`) bo'lsa — avval shu terminal(lar)ning hali bank tushumiga bog'lanmagan, `failed` bo'lmagan va ochiq qoralama davriga tushmagan settlement partiyalari (`card_terminal_settlements`, eng eski `business_date`dan, `business_date ≤ kirim sanasi`) bo'yicha: `Σ net_total ≥ kirim` va `(Σ − kirim) / Σ ≤ 5%` bo'lgan eng kichik prefiks — `gross_amount = Σ net_total`, `settled_from`/`settled_to` — partiyalar sanalari, partiyalarga qoralama yaratilganda `card_terminal_settlements.bank_settlement_id` yoziladi (`post`da boshqa partiyalar qo'shilmaydi, bekor qilinganda tozalanadi; `13-provodka-qoidalari.md` §2.18a); mos partiya bo'lmasa — summa va sana (filial/merchant) bo'yicha yuqoridagi qoida; `post` da shu filialning moslashtirilgan tranzaksiyalari partiyalari (reestrsiz — `settled_from`…`settled_to` dagi ochiq partiyalar) `card_terminal_settlements.bank_settlement_id` oladi (`21` §9.4); terminalsiz karta tushumi hech qachon RRN bo'yicha moslashtirilmaydi (`21` §9.2); (4) `commission_amount = gross_amount − kirim summasi`, `variance_amount = "0.00"` (inkassada kamomad/ortiqcha bo'lsa — Buxgalter qoralamani 55h bilan tahrirlaydi). `bank_ref` = `Номер`, `attachment_id` — yuklangan fayl (`attachments.kind='import'`). Mos tranzit topilmasa — qoralama yaratilmaydi, qator `unmatched_lines` ga tushadi (`reason:"no_transit_match"`); `commission_amount < 0` yoki `commission_amount ≥ gross_amount` — qoralama yaratilmaydi, `unmatched_lines` (`reason:"commission_invalid"`); Buxgalter 55c bilan qo'lda kiritadi |
| Javob | `201 {import_id, file_sha256, account, period_from, period_to, drafts_created: int, draft_ids: [UUID], duplicates: int, ignored_outgoing: int, unmatched_lines: [{line_no, number, date, amount, payer_name, purpose, reason: "no_transit_match"\|"unknown_method"\|"branch_ambiguous"\|"commission_invalid"}], unmatched_card_transactions: [{card_terminal_transaction_id, rrn, amount, business_date}]}` — `import_id` — import yozuvining `id`si (`bank_settlements.statement_import_id` shunga ishora qiladi); qolgan nomlar `bank_statement_imports` ustunlari bilan bir xil; `draft_ids` hosila (`bank_settlements.statement_import_id = import_id`); `duplicates`: `bank_ref` (= `Номер`) + `doc_date` (= kirim sanasi) + `net_amount` (= kirim summasi) bo'yicha avval yaratilgan (bekor qilinmagan) `bank_settlements` bilan mos qatorlar; `unmatched_card_transactions` — RRN reestri bilan moslashtirilgan kunlardagi reestrda yo'q integratsiyalangan xaridlar (5710 da qoladi, ma'lumot uchun) |
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
| Javob | `201 {link_code, bot_url, expires_at}` — `link_code` muddati **10 daqiqa** (standart, sozlanadi — qaror #54), bir martalik; `bot_url` = `https://t.me/<bot>?start=<link_code>`; yangi kod shu foydalanuvchining oldingi ishlatilmagan kodini bekor qiladi. Bog'lash — botda `/start <link_code>` (Telegram webhook'i `POST /notifications/telegram/webhook`, `21-integratsiyalar.md` §11) |
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
| Maqsad | Joriy foydalanuvchining ogohlantirish turlari sozlamalari (US-M18-03: kam qoldiq, smena farqi, limitdan katta amal, davlat hisoboti farqi, offline 48 soat, obuna eslatmalari) — sozlama har foydalanuvchiga alohida (`notification_settings (tenant_id, user_id, kind)`), yozuvi yo'q tur yoqilgan hisoblanadi |
| Ruxsat | `notifications.manage` |
| So'rov | — |
| Javob | `{items: [{kind, enabled, time}]}` — `kind` ∈ `{daily_report, low_stock, cash_variance, over_limit_action, state_report_diff, offline_48h, subscription_due, subscription_grace, debt_due_today, debt_aging_60, debt_limit_exceeded_offline, expiry_soon, card_settlement_mismatch, recurring_expense_due, marking_alert, marking_acceptance_due, late_in_closed_period, onec_agent_paired, onec_base_error}` — har doim barcha turlar; `time` faqat `daily_report` uchun (standart `"21:00"`, Toshkent vaqti), boshqa turlarda `null` (to'liq ro'yxat: `subscription_due` — 3/1/0 kun oldin; `subscription_grace` — darhol/12s/2s; `debt_due_today` — US-M08-09; `debt_aging_60` — US-M08-10; `debt_limit_exceeded_offline` — Egasiga offline oshib ketgan qarz ogohlantirishi; `expiry_soon` — US-M04-06; `card_settlement_mismatch` — terminal settlement ↔ Z-hisobot farqi, `18-api-kassa.md` §16a.6, qaror #71; `recurring_expense_due` — takroriy xarajat eslatmasi, US-M15-02; `marking_alert` — markirovka kodi muammosi: FM imzolagan chekda takroriy kod, offline sotilgan kod keyingi CRPT tekshiruvida yaroqsiz, CRPT xabarnomani rad etdi yoki tasdiqlangan xabarnoma hujjati bekor qilindi (`16-offline-sync.md` §7, `21-integratsiyalar.md` §4); `marking_acceptance_due` — markirovkali kirim qabul xabarnomasi muddati 24 soatdan kam qoldi yoki o'tdi, `21-integratsiyalar.md` §4; `late_in_closed_period` — yopilgan davrga kech POS voqeasi (`sync_exceptions(kind='late_in_closed_period')`, `16-offline-sync.md` §3.4, `13-provodka-qoidalari.md` §5.1); `onec_agent_paired` — Do'kon agenti ulandi/uzildi (W-04, W-05, A-10), `onec_base_error` — agent ogohlantirishi (`machine_hash` o'zgarishi, rad etilgan vazifa; 1C baza xatolari — Bosqich 7), `33-1c-integratsiya.md` §13.3 |
| Xatolar | — |
| Idempotency-Key | Kerak emas |
| Offline | Oxirgi sinxronlangan |
| Bog'langan | US-M18-02, US-M18-03; BO-20 |

### 70. `PATCH /notification-settings`

| | |
|---|---|
| Maqsad | Sozlamalarni (yoqish/o'chirish, vaqt) yangilash |
| Ruxsat | `notifications.manage` |
| So'rov | `{items: [{kind: string, enabled: bool, time?: "HH:mm"}]}` — faqat o'z sozlamalari; `time` yuborilmasa saqlangan vaqt o'zgarmaydi |
| Javob | `200 {items: [...]}` (#69 dagi to'liq ro'yxat) |
| Xatolar | `VALIDATION_ERROR` (`items[i].kind` — `validation.invalid_choice` / `validation.duplicate`; `items[i].time` — `validation.invalid_format`, `daily_report`dan boshqa turda — `validation.not_allowed`) |
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
