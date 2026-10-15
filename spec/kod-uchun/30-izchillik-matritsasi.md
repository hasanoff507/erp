# Izchillik matritsasi (traceability) — US → BP → Ekran → API → Jadval → Provodka → Ruxsat → Bosqich

**Maqsad:** har bir foydalanuvchi hikoyasi (US-Mxx-nn)dan implementatsiya uchun kerakli hamma narsaga (biznes jarayon, ekran, API/voqea, DB jadval, provodka qoidasi, ruxsat kodi, backlog bosqichi) bitta qatordan borish va bo'shliqlarni aniqlash.
**Kim uchun:** hammasi.
**Bog'liq fayllar:** `03-modullar-talablari.md`, `04-biznes-jarayonlar.md`, `05-mvp-chegarasi.md`, `07-ekran-tafsilotlari.md`, `12-db-sxema.md`, `13-provodka-qoidalari.md`, `15-xavfsizlik-va-audit.md`, `16-offline-sync.md`, `17-api-umumiy.md`–`20-api-moliya-admin.md`, `27-backlog.md`.
**Holat:** joriy, 2026-10-15.

## Belgilar

- **MVP**: `Must`/`Should`/`Could` — `05-mvp-chegarasi.md` §1.1 jadvalidan; `Keyin` — MVP'dan keyinga aniq surilgan (qaror #33); **— (gap)** — 05'da bu US yo'q (hozir bunday qator qolmagan).
- **BP**: `04-biznes-jarayonlar.md`dagi BP-01…13; **—** — bu US/modul uchun hech qanday BP yo'q (04 faqat 13 ta tranzaksion oqimni modellashtiradi — narx, hisobot, huquq, filial boshqaruvi, xarajat, kassa pul harakati, obuna, bildirishnoma kabi butun modullar BP qatlamida yo'q); **"?"** — modul BP'da bor, lekin bu aniq US BP matnida tilga olinmagan (xulosa chiqarilgan).
- **Bosqich**: `27-backlog.md`dagi 0–6 bosqich yoki "MVP'dan keyin"; **"?"** — US aniq nomlanmagan, modul darajasidan xulosa qilingan.
- **Ruxsat**: `15-xavfsizlik-va-audit.md` §2.1 kodi; **—** — ruxsatsiz ochiq amal (masalan autentifikatsiyasiz endpoint) yoki tegishli kod topilmadi.

---

## 1. Asosiy matritsa

### M01 — Kassa (POS)

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M01-01 | Chek yaratish va to'lov qabul qilish | Must | BP-02, BP-05 | POS-02, POS-03, POS-04 | voqea `sale.created` (`18-api-kassa.md` §4); `GET /api/v1/sales` (chek qidiruv, §4.8) | `app.sales`, `app.sale_lines`, `app.sale_payments`, `app.stock_moves`, `app.stock_lots`, `app.vat_moves`, `app.ledger_entries`, `app.fiscal_receipts` | §2.1–2.4 | `sales.create` | 3 |
| US-M01-02 | Offline savdo + avtomatik sinxronlanish | Must | BP-02 (offline variant) | POS-02, POS-12 | `POST /api/v1/sync/push`, `GET /api/v1/sync/pull` (§17, `16-offline-sync.md`) | `app.sync_receipts`, `app.idempotency_keys` | §2.1–2.4 | `sales.create` | 3 |
| US-M01-03 | Markirovkalangan tovar kodini tekshirish | Must | BP-02 (qadam 5) | POS-02 | `POST /api/v1/marking-codes/verify` (§15) | `app.marking_codes` | §2.1–2.4 (sale_lines ichida) | — (CRPT integratsiyasiga `integrations.retry` tegishli, sotuvda alohida kod yo'q) | 3 (UI) / 5 (CRPT backend) |
| US-M01-04 | Smena ochish va yopish (Z-hisobot) | Must | **— (gap, BP yo'q)** | POS-01, POS-07 | voqea `shift.opened`/`shift.closed`; `GET /api/v1/shifts/{id}/z-report` (§3) | `app.shifts`, `app.cash_moves` | §2.19 (X-01) | `shift.open` / `shift.close` | 3 |
| US-M01-05 | UzQR to'lov (yuridik shaxs, 2026-07-01'dan majburiy) | Must | BP-05 | POS-03 | `POST /api/v1/payments/checkouts`, `GET /{checkout_ref}`, `POST /payments/webhooks/{provider}` (§16) | `app.payment_checkouts`, `app.sale_payments` | §2.2 | `sales.create` | 3 |
| US-M01-06 | Chekdan keyin chiquvchi e-faktura (B2B) | Must | BP-13 | POS-06, BO-15 | `POST /api/v1/einvoices` (`direction=out`), `POST /einvoices/from-receipt` (§14a) | `app.einvoices` | §2.22 (provodkasiz) | `einvoice.create` | 5 |

### M02 — Qaytarish

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M02-01 | Asl chek bo'yicha qaytarish | Must | BP-04 | POS-05 | voqea `return.created` (§7.1); `GET /api/v1/returns` (§7.2) | `app.returns`, `app.return_lines`, `app.stock_moves`, `app.vat_moves`, `app.ledger_entries` | §2.5 | `returns.create` | 3 |
| US-M02-02 | Menejer limitdan yuqori qaytarishni tasdiqlash | Should | BP-04 | POS-05, BO-16 | `POST /api/v1/approval-requests`, `POST /{id}/approve`\|`/reject` (§9) | `app.approval_requests`, `app.doc_approvals` | §2.5 | `returns.approve` | 3 |
| US-M02-03 | QQS tuzatish (qaytarishda avtomatik) | Must | BP-04 | BO-09 | `GET /api/v1/vat-moves?doc_type=returns` (BO-09 manbai) | `app.vat_moves` | §2.5 | `tax.vat.view` | 3 |

### M03 — Chegirma

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M03-01 | Kassir chegirma (limit ichida) | Must | BP-02 "?" | POS-02, BO-16 | voqea `sale.created` (chegirma qatorida, §8.1); limitdan oshsa `POST /approval-requests` | `app.sale_lines` (discount), `app.approval_requests` | §2.1–2.4 | `discount.give` | 3 |
| US-M03-02 | Avtomatik chegirma qoidalari | Keyin (post-MVP) | BP-02 "?" | BO-05 | `GET/POST /api/v1/discount-rules`, `PATCH /{id}`, `POST /{id}/archive` (§8.2) | `app.discount_rules` | — (registrga ta'siri yo'q, qoida o'zi) | `discount.rule.manage` | MVP'dan keyin |
| US-M03-03 | Chegirmalarning margin'ga ta'sirini hisobotda ko'rish | Could | **— (gap, BP yo'q)** | **— (GAP: hech qaysi ekranda yo'q)** | `GET /api/v1/reports/sales` "?" (aniq margin-hisobot endpointi yo'q) | `app.sale_lines`, `app.vat_moves` | — | `reports.sales.view` "?" | **— (gap, 27'da ham yo'q)** |

### M04 — Ombor qoldig'i

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M04-01 | Kirimda balans avto yangilanish | Must | BP-01 | POS-08, BO-03 | `POST /goods-receipts`, `POST /{id}/post` (§8) | `app.goods_receipts`, `app.receipt_lines`, `app.stock_moves`, `app.stock_lots`, `app.stock_balances`, `app.ledger_entries` | §2.6–2.8 | `purchases.post` | 2 |
| US-M04-02 | Minimal zaxira chegarasida ogohlantirish | Should | **— (gap)** | BO-03 | `GET /api/v1/stock-balances?low_stock=` (§7) | `app.stock_balances` | — | `stock.view` | 4 |
| US-M04-03 | Ko'p filial konsolidatsiyalangan qoldiq | Should | **— (gap)** | BO-03 | `GET /api/v1/reports/stock?branch_id=` (20 #20) | `app.stock_balances` | — | `stock.view` | 4 |
| US-M04-04 | Boshlang'ich katalog/qoldiq kiritish (qo'lda/import/AI-03) | Must | **— (gap, onboarding, BP yo'q)** | BO-21 | `POST /api/v1/import-jobs` (`kind=products`/`opening_stock`), `POST /stock-openings`→`/post`, `POST /ai/ocr/jobs`→`/confirm` (AI-03 yo'li) | `app.import_jobs`, `app.stock_openings`, `app.opening_lines`, `app.ai_ocr_jobs` | §2.21 | `catalog.manage`, `stock.opening.manage` | 1 (yo'l 1–2) / 6 (yo'l 3 = AI-03) |
| US-M04-05 | Tannarx usulini (FIFO/AVECO) tanlash | Must | **— (gap, BP yo'q)** | BO-14 | `GET/PATCH /api/v1/valuation-settings` (§17) | `app.valuation_method_history` | `13-provodka-qoidalari.md` §3 (COGS: FIFO/AVECO) | `valuation.settings.manage` | 2 (27, M04 qatorida) |
| US-M04-06 | Yaroqlilik muddati ogohlantirish + hisobdan chiqarish | Should | **— (gap)** "?" (BP-10'ga yaqin) | BO-03 | `POST /write-offs`, `POST /{id}/post` (§15) | `app.write_offs`, `app.write_off_lines`, `app.stock_lots` | §2.12 | `stock.writeoff` | 2 |

### M05 — Inventarizatsiya

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M05-01 | Sanash varag'i / haqiqiy son kiritish | Must | BP-10 | POS-10 | `POST /stock-counts`, `POST /{id}/lines` (voqea `stock_count.line_recorded`, §14) | `app.stock_counts`, `app.count_lines` | §2.11 | `stock.count.create` | 2 |
| US-M05-02 | Farqni (ortiqcha/kamomad) tasdiqlash | Must | BP-10 | BO-03 | `POST /stock-counts/{id}/submit-for-review`, `POST /{id}/post` (§14) | `app.stock_counts`, `app.count_lines` | §2.11 | `stock.count.post` | 2 |
| US-M05-03 | Kamomad/ortiqchani buxgalteriya yozuviga aks ettirish | Must | BP-10 | BO-03 | `POST /stock-counts/{id}/post` (§14) | `app.ledger_entries`, `app.stock_moves` | §2.11 | `stock.count.post` | 2 |

### M06 — Ko'chirish

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M06-01 | Ko'chirish hujjatini yaratish (yuborish) | Must | BP-09 | POS-09 | `POST /transfers`, `POST /{id}/send` (voqea `transfer.sent`, §13) | `app.transfers`, `app.transfer_lines`, `app.stock_moves` | §2.9 | `transfer.create` | 2 |
| US-M06-02 | Kelgan tovarni tasdiqlab qabul qilish | Must | BP-09 | POS-09 | `POST /transfers/{id}/receive` (voqea `transfer.received`, §13) | `app.transfers`, `app.stock_moves`, `app.stock_lots` | §2.10 | `transfer.receive` | 2 |
| US-M06-03 | Ko'chirishlar tarixi va bajarilish vaqti | Should | BP-09 | BO-03 | `GET /transfers`, `GET /{id}` (§13) | `app.transfers`, `app.transfer_lines` | — | `stock.view` "?" | 2 |

### M07 — Xarid

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M07-01 | Yetkazib beruvchiga xaridnoma yaratish | Must | BP-01 | BO-04 | `POST /purchase-orders`, `POST /{id}/send` (§10) | `app.purchase_orders`, `app.po_lines` | — (provodkasiz, "ta'sir yo'q") | `purchases.create` | 2 |
| US-M07-02 | Kelgan tovarni xaridnoma bilan solishtirib qabul qilish | Must | BP-01 | POS-08, BO-04 | `POST /goods-receipts`, `POST /{id}/post` (§8) | `app.goods_receipts`, `app.receipt_lines` | §2.6–2.8 | `purchases.receive` / `purchases.post` | 2 |
| US-M07-03 | Yetkazib beruvchi e-fakturasini kiritib QQS kreditini hisoblash | Must | BP-01, BP-12 | BO-04, BO-15 | `GET /einvoices?direction=in`, `POST /{id}/accept`, `POST /goods-receipts/from-einvoice/{id}` (§19) | `app.einvoices`, `app.goods_receipts` | §2.6 | `einvoice.sign` / `purchases.post` | 5 |
| US-M07-04 | Yetkazib beruvchiga kreditorlik qarzini to'lash | Must | BP-12 | BO-04 | `POST /supplier-payments` (§11) | `app.supplier_payments`, `app.supplier_payment_allocations`, `app.ledger_entries` | §2.16 | `purchases.pay` | 4 (ikkinchi mezoni — 5) |
| US-M07-05 | Yetkazib beruvchiga tovar qaytarish | Should | **— (gap, BP yo'q)** | BO-04 | `POST /supplier-returns`, `POST /{id}/post` (§12) | `app.supplier_returns`, `app.supplier_return_lines`, `app.stock_moves` | §2.20 | `purchases.return` | 2 |

### M08 — Nasiya (mijoz qarzi)

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M08-01 | Mijozga limit ichida nasiyaga sotish | Must | BP-03 | POS-03, POS-06, BO-16 | voqea `sale.created` (`sale_payments.method=debt`, §4) | `app.sales`, `app.debt_moves`, `app.debt_balances` | §2.3 | `debts.create` | 3/4 (sotuv oqimi ichida) |
| US-M08-02 | Mijoz kredit limitini belgilash/o'zgartirish | Must | **— (gap, setup)** | POS-06 | `PATCH /api/v1/counterparties/{id}` (§11.4) | `app.counterparties` | — | `debts.limit.manage` | 4 "?" |
| US-M08-03 | Muddati o'tgan qarzlar uchun avtomatik AI eslatma matni | Should | BP-11 | BO-06 | `POST /ai/debt-reminders/draft` (20 #77) | `app.ai_requests` | — | `ai.chat.use` (yuborishda `debts.remind`) | 6 |
| US-M08-04 | Mijozning nasiya qarzini (qisman/to'liq) to'lashini qabul qilish | Must | BP-11 | BO-06 | voqea `debt_payment.created`; `POST /debt-payments`→`/post` (§12.2–12.3) | `app.debt_payments`, `app.debt_payment_allocations`, `app.debt_moves`, `app.fiscal_receipts` | §2.14 | `debts.payment.accept` | 4 |
| US-M08-05 | Qarzga berishni 2–3 soniyada (offline) yozish | Must | BP-03 | POS-13 | voqea `sale.created` (`method=debt`) / voqea `counterparty.created` | `app.sales`, `app.counterparties` | §2.3 | `debts.create` | 4 |
| US-M08-06 | Mijozning qarz daftarini qog'oz daftardek ko'rish | Must | BP-11 "?" | POS-13, BO-06 | `GET /counterparties/{id}/debt-ledger` (§12.1) | `app.debt_moves`, `app.debt_balances` | — | `debts.create`/`debts.payment.accept` yoki `reports.sales.view` | 4 |
| US-M08-07 | Eski qog'oz daftardagi qarzlarni tizimga ko'chirish | Must | **— (gap, onboarding)** | BO-21 | `POST /debt-openings`→`/post`; `POST /import-jobs` (`kind=opening_debts`) (§12.4) | `app.debt_openings` | §2.13 | `stock.opening.manage` | 1 |
| US-M08-08 | Mijozga SMS/Telegram qarz xabari | Keyin (post-MVP) | BP-11 "?" | **— (GAP: ekran yo'q)** | `POST /ai/debt-reminders/send` (20 #78) | `app.notifications_log` | — | `debts.remind` | MVP'dan keyin |
| US-M08-09 | Qarzlarni o'z vaqtida qaytarib olish (va'da sanasi, eslatma) | Must | BP-11 | POS-13, BO-06 | `PATCH /counterparties/{id}` / `debt_payments.promise_date` (§12.1) | `app.debt_moves` | — | `debts.payment.accept` | 4 |
| US-M08-10 | Qarzlar holatini bir qarashda ko'rish | Must | BP-11 "?" | BO-06 | `GET /reports/debts-aging?direction=receivable` (§12.8 → 20 #21) | `app.debt_balances` | — | `reports.finance.view` | 4 |
| US-M08-11 | Yetkazib beruvchilarga qarzni ham daftar kabi yuritish | Must | BP-12 "?" | POS-13, BO-04, BO-06 | `GET /reports/debts-aging?direction=payable` (BO-04 manbai) | `app.counterparties`, `app.supplier_payments` | §2.16 | `purchases.pay` | 4 |

### M09 — Narxlar *(modul darajasida BP yo'q — bo'shliq, pastga qarang)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M09-01 | Narxni yangilash, eski narx tarixda saqlanishi | Must | **— (gap)** | BO-05 | `GET /products/{id}/prices`, `POST /price-changes`→`/post` (§4) | `app.product_prices`, `app.price_changes`, `app.price_change_lines` | §2.25 (price_changes posting) | `prices.edit` | 1 |
| US-M09-02 | Katta narx o'zgarishini tasdiqlash | Should | **— (gap)** | BO-05, BO-16 | `POST /price-changes` (`pending_approval`) + `approval-requests` (§4) | `app.price_changes`, `app.approval_requests` | — | `prices.approve` | 6 |
| US-M09-03 | Kassada joriy narxni ko'rish (o'zgartirib bo'lmaydi) | Must | **— (gap)** | POS-02, POS-11 | `GET /products/{id}/prices` yoki lokal kesh (Dexie `prices`) | `app.product_prices` | — | — (faqat o'qish) | 1 |
| US-M09-04 | Narxi o'zgargan tovarlarning yorliqlarini qayta chop etish | Should | **— (gap)** | BO-18 | `GET /label-print-queue`, `GET /label-templates`, `POST /label-print-jobs` (§5) | `app.label_print_queue`, `platform.label_templates` | — | `labels.print` | 6 |
| US-M09-05 | Shtrix-kodi yo'q tovarga ichki shtrix-kod berish | Should | **— (gap)** | BO-18 | `POST /products/{id}/barcodes/internal-generate` (§1) | `app.product_barcodes`, `app.internal_barcode_seq` | — | `catalog.manage` | 1 |
| US-M09-06 | Tarozida tortilgan tovarni bitta skanerlash bilan sotish | Should | **— (gap)** | BO-14 | lokal: tarozi shtrix-kod formati `tenants.settings`dan (Dexie `settings`) | `app.products` (og'irlik qatori, lokal parsing) | — | `catalog.manage` (format sozlash) | 1 |
| US-M09-07 | Doimiy/ulgurji mijozga standart chegirma % (mijoz kartasida) | Should | **— (gap)** | POS-02 | `PATCH /counterparties/{id}` "?" (`loyalty_discount_percent` kabi maydon katalogda aniq ko'rsatilmagan) | `app.counterparties` | — | `prices.edit` "?" | **— (gap, hech qaysi bosqichda yo'q)** |

### M10 — QQS

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M10-01 | Har bir sotuvdan QQS avtomatik hisoblash | Must | BP-07 | BO-07 | voqea `sale.created` (QQS qatori); `GET /vat-moves`, `GET /reports/vat-summary` (20 #1–2) | `app.vat_moves` | §2.1–2.4 | `tax.vat.view` | 2/3 (sotuv oqimi ichida) |
| US-M10-02 | Davlat QQS hisobotini 5 kalendar kun ichida solishtirish | Must | BP-08 | BO-10 | `POST /state-reports`, `POST /{id}/compare`, `GET /{id}/diffs`, `POST /{id}/correction` (20 #3–8) | `app.state_reports`, `app.state_report_diffs` | `13-provodka-qoidalari.md` §4 | `tax.compare.review` / `tax.correction.submit` | 6 |
| US-M10-03 | Yuqori xavfli ("qizil") fakturalarning QQS kreditiga ta'siri | Should | BP-07, BP-12 "?" | BO-07, BO-15 | `GET /einvoices?risk_flag=` (§19) | `app.einvoices` | — | `tax.compare.review` | 5 |
| US-M10-04 | QQS to'lamaydigan (aylanma solig'i) biznes uchun davlat hisobotini solishtirish | Must | BP-08 "?" | BO-10 | `POST /state-reports` (`tax_type=turnover` taxmin, 20 #3) | `app.state_reports` | §4 | `tax.compare.review` | 6 |

### M11 — Buxgalteriya

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M11-01 | Har bir sotuv/xariddan avtomatik provodka | Must | BP-06 | BO-08 | `GET /ledger-entries` (20 #9) — provodka posting paytida avtomatik yoziladi | `app.ledger_entries` | §2.1–2.21 (barcha hujjat turlari) | `accounting.post` | 2 |
| US-M11-02 | Oy yakunida balans va daromad-xarajat hisoboti | Must | BP-06 "?" | BO-08 | `POST /period-closings`, `GET /reports/trial-balance`\|`/profit-and-loss`\|`/balance-sheet` (20 #11–16) | `app.period_closings`, `app.ledger_entries` | `13-provodka-qoidalari.md` §5 (davr yopish) | `accounting.period.close` | 5 |
| US-M11-03 | Asosiy moliyaviy ko'rsatkichlarni sodda ko'rinishda ko'rish | Should | **— (gap)** | BO-02 | `GET /reports/dashboard` (20 #17) | `app.ledger_entries` (hosila) | — | `reports.sales.view` | 4 |

### M12 — Hisobotlar *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M12-01 | Kunlik savdo hisoboti (umumiy va filial bo'yicha) | Must | **— (gap)** | BO-02, BO-09 | `GET /reports/dashboard`, `GET /reports/sales` (20 #17–18) | `app.sales` (hosila) | — | `reports.sales.view` | 4 |
| US-M12-02 | Eng ko'p/kam sotiladigan tovarlar hisoboti | Should | **— (gap)** | BO-09 | `GET /reports/top-products` (20 #19) | `app.sale_lines` (hosila) | — | `reports.sales.view` | 4 "?" |
| US-M12-03 | QQS va davlat solishtirish hisobotini eksport qilish | Must | **— (gap)** | BO-09 | `POST /reports/{report-kod}/export`, `GET /export-jobs/{job_id}` (20 #22–23) | — (eksport fayli, `attachments`) | — | `reports.export` | 6 "?" |

### M13 — Huquqlar *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M13-01 | Xodim qo'shib, rol(lar) belgilash | Must | **— (gap)** | BO-11 | `POST /admin/users` (14 §20); `PUT /roles/{id}/permissions` (20 #28) | `app.users`, `app.memberships`, `app.role_permissions` | — | `settings.users` | 1 |
| US-M13-02 | Kichik do'konda bitta xodimga bir nechta rol | Must | **— (gap)** | BO-11 | `POST /admin/users` (`roleIds` multi) | `app.memberships` | — | `settings.users` | 1 |
| US-M13-03 | Operatsiya limitlarini rolga/shaxsga bog'lab sozlash | Should | **— (gap)** | BO-11 | `GET/PUT /roles/{id}/permissions` (20 #27–28) | `app.role_permissions` | — | `settings.users` | 1 |
| US-M13-04 | Xodimni admin panel orqali to'liq ma'lumoti bilan qo'shish | Must | **— (gap)** | BO-11 | `POST /admin/users` (`purpose=invite`) (14 §20) | `app.users`, `auth.otp_challenges` | — | `settings.users` | 1 |
| US-M13-05 | Xodimni vaqtincha bloklash/blokdan chiqarish | Must | **— (gap)** | BO-11 | `PATCH /admin/users/{id}` | `app.users` (blocked_at) | — | `settings.users` | 1 |
| US-M13-06 | Xodimning parolini/PIN kodini qayta tiklash | Must | **— (gap)** | POS-01, BO-01, BO-11 | `POST /admin/users/{id}/reset-password`, `/reset-pin` (BO-11 manbai) | `auth.user_credentials`, `auth.otp_challenges` | — | `settings.users` | 1 |
| US-M13-07 | Xodim sessiyalarini ko'rish va bekor qilish | Must | **— (gap)** | BO-11 | `GET /admin/users/{id}/sessions`, `GET /{id}/devices`, `POST /{id}/revoke-sessions` | `auth.sessions`, `app.devices` | — | `settings.users` | 1 "?" |
| US-M13-08 | Platforma admini: tenant va Egasi hisobini boshqarish | Must | **— (gap)** | ADM-01, BO-11 | `GET/POST /platform/tenants/{id}/owner/...` (14 §18.1) | `platform.platform_admins`, `app.users` | — | `platform.admin` | 6 |

### M14 — Filiallar

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M14-01 | Barcha filiallar bo'yicha konsolidatsiyalangan ko'rinish | Should | BP-09 "?" | BO-12 | `GET /reports/stock?branch_id=` (bo'sh = konsolidatsiya) | `app.stock_balances`, `app.branches` | — | `stock.view` | 4 |
| US-M14-02 | Filialdan filialga narx/chegirma siyosatini nusxalash | Keyin (post-MVP) | **— (gap)** | **— (GAP: ekran yo'q)** | `POST /branches/{id}/copy-pricing` (20 #36) | `app.product_prices`, `app.discount_rules` | — | `prices.edit` | MVP'dan keyin |
| US-M14-03 | Yangi filial (do'kon) qo'shish | Must | BP-09 "?" | BO-12 | `POST /branches` (20 #31) | `app.branches`, `app.warehouses`, `app.cash_registers` | — | `settings.branches` | 1 |
| US-M14-04 | Filial uchun "aholi punkti toifasi"ni belgilash (aylanma solig'i) | Must | BP-09 "?" | BO-12 | `GET/POST /branches/{id}/tax-settings` (20 #34–35) | `app.branch_tax_settings` | — | `settings.branches` | 1 |

### M15 — Xarajatlar *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M15-01 | Xarajatni 10 soniyada yozish | Must | **— (gap)** | BO-17 | `POST /expenses`, `POST /{id}/post` (20 #42–43) | `app.expenses`, `app.ledger_entries` | §2.17 | `expenses.create` | 4 |
| US-M15-02 | Doimiy xarajatlarni har oy qayta kiritmaslik | Should | **— (gap)** | BO-17 | `GET/POST /recurring-expenses`, `POST /{id}/confirm` (20 #48–51) | `app.recurring_expenses` | §2.17 | `expenses.create` | 4 |
| US-M15-03 | Haqiqiy sof foydani ko'rish | Must | **— (gap)** | BO-17 | `GET /reports/profit-and-loss` (20 #12) | `app.expenses`, `app.ledger_entries` | — | `reports.finance.view` | 4 |

### M16 — Kassa pul harakati (naqd pul) *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M16-01 | Kassaga pul qo'yish/olishni sabab bilan yozish | Must | **— (gap)** "?" (BP-05'ga yaqin) | POS-14, BO-16 | voqea `cash_movement.created`; `POST /cash-movements` (§13, 20 #53) | `app.cash_movements`, `app.cash_moves` | §2.18 | `cash.deposit` / `cash.withdraw` | 3 |
| US-M16-02 | Smena yopilganda kassadagi pulni sanab kiritish | Must | **— (gap)** | POS-15 | voqea `shift.closed` (`counted_cash`) (§3.2) | `app.shifts` | §2.19 (X-01) | `cash.count.shift` | 3 |
| US-M16-03 | Har bir smena/kassa bo'yicha naqd pul tarixini ko'rish | Must | **— (gap)** | BO-09 | `GET /cash-registers/{id}/cash-history` (20 #55) | `app.cash_moves` | — | `reports.sales.view` yoki `cash.count.shift` | 3 |

### M17 — Obuna va ro'yxatdan o'tish (platforma) *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M17-01 | 2 daqiqada ro'yxatdan o'tish | Must | **— (gap)** | BO-21 | `POST /auth/signup` (14 §4/§20) | `app.tenants`, `app.subscriptions`, `app.memberships`, `app.branches`, `app.warehouses`, `app.cash_registers`, `app.roles`, `app.doc_sequences` | — | — (autentifikatsiyasiz) | 1 |
| US-M17-02 | Tarifni tanlash va to'lash | Must | **— (gap)** | BO-19 | `GET /billing/plan`, `POST /billing/checkout` (20 #56, #61) | `app.subscriptions`, `app.billing_payments` | — | `billing.manage` | 6 |
| US-M17-03 | To'lov muddatini unutmaslik, muddat o'tsa ham darhol to'xtamaslik | Must | **— (gap)** | POS-01, BO-01, BO-19 | `GET /auth/session`, `GET /billing/pay` (14 §16) | `app.subscriptions` | — | — (sessiya darajasida; to'lovda `billing.manage`) | 6 |
| US-M17-04 | Platforma admini: tenantlar/obunalar/to'lovlarni ko'rish | Must | **— (gap)** | ADM-01 | `GET /platform/tenants...` (14 §18.1) | `platform.platform_admins`, `app.tenants` | — | `platform.admin` | 6 |
| US-M17-05 | Xizmatdan chiqishda barcha ma'lumotni olib ketish | Keyin (post-MVP, Could) | **— (gap)** | **— (GAP: ekran yo'q)** | `POST/GET /billing/export-my-data` (14 §16.5, 20 #65a) | — (eksport fayli) | — | — (SMS OTP, bir martalik token) | MVP'dan keyin |

### M18 — Bildirishnomalar va Egasi uchun Telegram bot *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M18-01 | Telegram akkauntini do'konga ulash | Must | **— (gap)** | BO-20 | `POST /notifications/telegram/link-start` (20 #66) | `app.telegram_links` | — | `telegram.link` | 4 |
| US-M18-02 | Har kuni kechqurun qisqa hisobot | Must | **— (gap)** | BO-20 | `GET/PATCH /notification-settings` (20 #69–70) | `app.notification_settings`, `app.notifications_log` | — | `notifications.manage` | 4 |
| US-M18-03 | Muhim hodisalar haqida darhol xabar | Should | **— (gap)** | BO-20 | `PATCH /notification-settings` (20 #70) | `app.notification_settings`, `app.notifications_log` | — | `notifications.manage` | 6 |
| US-M18-04 | Botdan oddiy savol so'rash (AI-01) | Could | **— (gap)** | BO-13 | `POST /ai/chat` (20 #72) | `app.ai_requests` | — | `ai.chat.use` | 6 |

**Jami: 84 ta US** (M01=6, M02=3, M03=3, M04=6, M05=3, M06=3, M07=5, M08=11, M09=7, M10=4, M11=3, M12=3, M13=8, M14=4, M15=3, M16=3, M17=5, M18=4).

---

## 2. Teskari indekslar

### 2a. Ekran → US

Manba: `07-ekran-tafsilotlari.md` har bir ekrandagi **"Bog'liq US"** qatori (so'zma-so'z, grep bilan tekshirilgan — 38 ta ekranning har birida bitta shunday qator bor).

| Ekran | Bog'liq US |
|---|---|
| POS-01 | US-M01-04, US-M17-03, US-M13-06 |
| POS-02 | US-M01-01, US-M01-02, US-M01-03, US-M03-01, US-M09-03, US-M09-07 |
| POS-03 | US-M01-01, US-M01-05, US-M08-01 |
| POS-04 | US-M01-01 |
| POS-05 | US-M02-01, US-M02-02 |
| POS-06 | US-M08-01, US-M08-02, US-M01-06 |
| POS-07 | US-M01-04 |
| POS-08 | US-M07-02, US-M04-01 |
| POS-09 | US-M06-01, US-M06-02 |
| POS-10 | US-M05-01 |
| POS-11 | US-M09-03 |
| POS-12 | US-M01-02 |
| POS-13 | US-M08-05, US-M08-06, US-M08-09, US-M08-11 |
| POS-14 | US-M16-01 |
| POS-15 | US-M16-02 |
| BO-01 | US-M13-06, US-M17-03 |
| BO-02 | US-M12-01, US-M11-03 |
| BO-03 | US-M04-01, US-M04-02, US-M04-03, US-M06-03, US-M04-06, US-M05-02, US-M05-03 |
| BO-04 | US-M07-01, US-M07-02, US-M07-03, US-M07-04, US-M07-05, US-M08-11 |
| BO-05 | US-M09-01, US-M09-02, US-M03-02 |
| BO-06 | US-M08-03, US-M08-04, US-M08-06, US-M08-09, US-M08-10, US-M08-11 |
| BO-07 | US-M10-01, US-M10-03 |
| BO-08 | US-M11-01, US-M11-02 |
| BO-09 | US-M12-01, US-M12-02, US-M12-03, US-M16-03, US-M02-03 |
| BO-10 | US-M10-02, US-M10-04, AI-05 |
| BO-11 | US-M13-01…08 (barcha 8 tasi) |
| BO-12 | US-M14-01, US-M14-03, US-M14-04 |
| BO-13 | AI-01, US-M18-04 |
| BO-14 | US-M04-05, US-M09-06 |
| BO-15 | US-M07-03, US-M01-06, US-M10-03 |
| BO-16 | US-M02-02, US-M03-01, US-M08-01, US-M09-02, US-M16-01 |
| BO-17 | US-M15-01, US-M15-02, US-M15-03 |
| BO-18 | US-M09-04, US-M09-05 |
| BO-19 | US-M17-02, US-M17-03 |
| BO-20 | US-M18-01, US-M18-02, US-M18-03 |
| BO-21 | US-M17-01, US-M04-04, US-M08-07 |
| UX-INSTALL (`/install`) | — (37 ta "biznes ekran"ga kirmaydi, o'z sarlavhasida aniq yozilgan; yordamchi route) |
| ADM-01 | US-M13-08, US-M17-04 |

**US→Ekran bo'shliqlari** (quyidagi US'larning hech bir ekranning "Bog'liq US" qatorida yo'qligi tasdiqlandi): **US-M03-03, US-M08-08, US-M14-02, US-M17-05** — batafsil §3da.

### 2b. Endpoint → US

Har bir fayl o'zining endpoint indeksidagi tartib raqami bilan berilgan (`18-api-kassa.md` §1, `20-api-moliya-admin.md` "Endpoint indeksi", `14-autentifikatsiya-oauth2.md` §20; `19-api-ombor.md`da rasmiy raqamlangan indeks yo'q — bo'lim raqami bilan ko'rsatilgan). **"— (gap)"** — hech qanday US-Mxx-nn topilmadi (aniq tekshirilgan, taxmin emas); **"?"** — modul orqali xulosa.

#### 14-autentifikatsiya-oauth2.md (§20, 26 qator)

| Endpoint | US |
|---|---|
| `/.well-known/*`, `/oauth/*`, `/auth/login`, `/auth/otp/*`, `/auth/google/*`, `/auth/logout`, `/auth/sessions/revoke-all`, `/auth/pin/verify`, `/auth/session`, `/auth/license` | — (gap: infratuzilma — barcha US'larga xizmat qiladi, maxsus US yo'q) |
| `POST /auth/signup` | US-M17-01 |
| `GET /billing/pay` | US-M17-03 |
| `POST /billing/checkout` | US-M17-02 |
| `GET /billing/plan`\|`/subscription`\|`/addons`\|`/payments` | US-M17-02 |
| `POST /billing/webhooks/{provider}` | US-M17-02 |
| `POST/GET /billing/export-my-data` | US-M17-05 |
| `/platform/tenants...` | US-M17-04 |
| `/platform/tenants/{id}/owner/...` | US-M13-08 |
| `/admin/users...` | US-M13-01, US-M13-02, US-M13-04, US-M13-05 |
| `/admin/users/{id}/reset-password` | US-M13-06 |

#### 18-api-kassa.md (§1, 37 qator)

| Endpoint/voqea | US |
|---|---|
| `shift.opened`, `shift.closed` | US-M01-04, US-M16-02 |
| `GET /shifts`, `/shifts/{id}`, `/shifts/{id}/z-report` | US-M01-04, US-M16-03 |
| `sale.created` | US-M01-01, US-M01-03, US-M01-05, US-M03-01, US-M08-01, US-M08-05, US-M10-01 |
| `sale.draft_voided` | — (gap: audit maqsadi, maxsus US yo'q) |
| `receipt.reprinted` | — (gap: audit maqsadi, maxsus US yo'q) |
| `return.created` | US-M02-01 |
| `GET /returns`, `/returns/{id}` | US-M02-01, US-M02-03 |
| `discount-rules` CRUD | US-M03-02 |
| `POST/GET /approval-requests`, `/approve`, `/reject` | US-M02-02, US-M03-01, US-M09-02 |
| `price-changes` → `/post` | US-M09-01, US-M09-02 |
| `counterparties` CRUD | US-M08-02, US-M08-05 |
| `counterparty.created` | US-M08-05 |
| `GET /counterparties/{id}/debt-ledger` | US-M08-06 |
| `POST /counterparties/{id}/statement-link` | US-M08-06 "?" |
| `debt_payment.created`, `POST /debt-payments`→`/post` | US-M08-04 |
| `POST /debt-openings`→`/post` | US-M08-07 |
| `POST /debt-writeoffs`→`/post` | **— (gap: `debts.forgive` ruxsati bor, lekin "qarzni kechish" uchun hech qanday US-M08-xx yo'q)** |
| `POST /debt-doubtful-flags`, `/unflag` | **— (gap: shubhali qarz belgisi uchun US yo'q)** |
| `GET /reports/debts-aging?direction=receivable` | US-M08-10 |
| `cash_movement.created`, `GET /cash-movements` | US-M16-01, US-M16-03 |
| `GET /fiscal-receipts`, `/{id}` | **— (gap: fiskal chek monitoringi uchun US yo'q)** |
| `POST /fiscal-receipts/{id}/retry` | **— (gap: `integrations.retry` bor, US yo'q)** |
| `einvoices` (direction=out) guruhi | US-M01-06 |
| `POST /marking-codes/verify` | US-M01-03 |
| `payments/checkouts`, `/{ref}`, `/webhooks/{provider}` | US-M01-05 |
| `sync/push`, `sync/pull` | US-M01-02 |
| `GET /sales`, `/{id}` | US-M01-01, US-M02-01 |

#### 19-api-ombor.md (bo'lim raqami bilan, ~89 endpoint)

| Resurs guruhi | US |
|---|---|
| `products`, `product-categories`, `units` (asosiy CRUD: ism, kategoriya, birlik) | **— (gap: umumiy katalog CRUD'i uchun maxsus US yo'q — faqat narx/shtrix-kod/import qamrab olingan)** |
| `products/{id}/barcodes/internal-generate` | US-M09-05 |
| `MXIK qidiruv/tekshirish` | — (gap, yordamchi funksiya, BO-04/M09 orqali xizmat qiladi) |
| `prices`, `price-changes` | US-M09-01, US-M09-02 |
| `label-print-queue`, `label-templates`, `label-print-jobs` | US-M09-04 |
| `import-jobs` | US-M04-04 |
| `stock-balances`, `stock-lots`, `stock-moves` (GET) | US-M04-01, US-M04-02, US-M04-03 |
| `goods-receipts` | US-M04-01, US-M07-02, US-M07-03 |
| `counterparties?is_supplier=true` (yetkazib beruvchi directoryi) | **— (gap: yetkazib beruvchi master-data boshqaruvi uchun maxsus US yo'q)** |
| `purchase-orders` | US-M07-01 |
| `supplier-payments` | US-M07-04 |
| `supplier-returns` | US-M07-05 |
| `transfers` | US-M06-01, US-M06-02, US-M06-03 |
| `stock-counts` | US-M05-01, US-M05-02, US-M05-03 |
| `write-offs` | US-M04-06 |
| `stock-openings` | US-M04-04 |
| `valuation-settings` | US-M04-05 |
| `stock-settings` | US-M04-02 "?" (kam qoldiq chegarasi shu yerda sozlanadi) |
| `recost-jobs` | **— (gap: qayta hisoblash monitoringi uchun maxsus US yo'q)** |
| `einvoices` (direction=in) | US-M07-03 |

#### 20-api-moliya-admin.md ("Endpoint indeksi", 88 qator)

| # | Endpoint | US |
|---|---|---|
| 1–2 | `GET /reports/vat-summary`, `/vat-moves` | US-M10-01, US-M02-03 |
| 3–8 | `state-reports` guruhi | US-M10-02, US-M10-04 |
| 9 | `GET /ledger-entries` | US-M11-01 |
| 10, 10a, 10b | `ledger-adjustments` guruhi | **— (gap: DB-12/A3-04 qo'lda tuzatish, mos US yo'q)** |
| 11–13 | `trial-balance`, `profit-and-loss`, `balance-sheet` | US-M11-02, US-M15-03 |
| 14–16 | `period-closings` guruhi | US-M11-02 |
| 17 | `GET /reports/dashboard` | US-M12-01, US-M11-03 |
| 18 | `GET /reports/sales` | US-M12-01 |
| 19 | `GET /reports/top-products` | US-M12-02 |
| 20 | `GET /reports/stock` | US-M04-03, US-M14-01 |
| 21 | `GET /reports/debts-aging` | US-M08-10, US-M08-11 |
| 22–23 | `reports/{kod}/export`, `export-jobs` | US-M12-03 |
| 24 | `GET /roles` | US-M13-01, US-M13-02, US-M13-03 |
| 25–26 | `POST /roles`, `PATCH /roles/{id}` (maxsus rol yaratish/tahrirlash) | **— (gap: rol ta'rifini yaratish/tahrirlash uchun maxsus US yo'q, faqat tayinlash/limit bor)** |
| 27–29 | `roles/{id}/permissions`, `permissions-catalog` | US-M13-03 |
| 30–33 | `branches` CRUD | US-M14-03 |
| 34–35 | `branches/{id}/tax-settings` | US-M14-04 |
| 36 | `POST /branches/{id}/copy-pricing` | US-M14-02 |
| 37 | `GET /warehouses` | US-M14-03 "?" |
| 38–40 | `cash-registers` CRUD | **— (gap: kassa qurilmasini sozlash uchun maxsus US yo'q, US-M14-03 ichida yashirin)** |
| 40a–40e | `tenant/settings`, `/tax-regimes`, `/integrations/*` | **— (gap: do'kon sozlamalari/integratsiya kaliti uchun maxsus US yo'q)** |
| 41–47 | `expenses`, `expense-categories` | US-M15-01 |
| 48–51 | `recurring-expenses` | US-M15-02 |
| 52–54 | `cash-movements` | US-M16-01, US-M16-03 |
| 55 | `cash-registers/{id}/cash-history` | US-M16-03 |
| 56–58 | `billing/plan`, `/subscription`, `/addons` (GET) | US-M17-02 |
| 59–60 | `billing/addons` (POST qo'shish/kamaytirish) | **— (gap: qo'shimcha kassa sotib olish uchun maxsus US yo'q, US-M17-02 umumiy)** |
| 61–65 | `billing/checkout`, `/payments`, `/webhooks/*`, `/invoices/{id}` | US-M17-02 |
| 65a | `billing/export-my-data` | US-M17-05 |
| — | `/platform/*` (9 endpoint, to'liq ro'yxat 14 §18.1'da) | US-M17-04, US-M13-08 |
| 66–68 | `notifications/telegram/*` | US-M18-01 |
| 69–70 | `notification-settings` | US-M18-02, US-M18-03 |
| 71 | `GET /notifications-log` | **— (gap: yuborilgan xabarlar tarixi uchun maxsus US yo'q)** |
| 72 | `POST /ai/chat` | US-M18-04 |
| 73–75 | `ai/ocr/jobs` | US-M04-04 |
| 76 | `ai/vat-diffs/{id}/explain` | US-M10-02 |
| 77–78 | `ai/debt-reminders/draft`\|`/send` | US-M08-03, US-M08-08 |
| 79 | `GET /ai/usage` | **— (gap: umumiy AI sarfi, maxsus US yo'q)** |

### 2c. Jadval → endpoints/US

Asos — `13-provodka-qoidalari.md` §2.25 "Posting qamrovi" jadvali (hujjat↔API post yo'li, so'zma-so'z) + qolgan (hujjat bo'lmagan) jadvallar uchun qo'shimcha xulosa.

| Jadval guruhi | Yozuvchi endpoint | US |
|---|---|---|
| `app.sales`, `app.sale_lines`, `app.sale_payments` | voqea `sale.created` | US-M01-01, US-M01-02, US-M01-03, US-M01-05, US-M03-01, US-M08-01, US-M08-05, US-M10-01 |
| `app.returns`, `app.return_lines` | voqea `return.created` | US-M02-01, US-M02-03 |
| `app.goods_receipts`, `app.receipt_lines` | `POST /goods-receipts/{id}/post` | US-M04-01, US-M07-02, US-M07-03 |
| `app.transfers`, `app.transfer_lines` | `/send`, `/receive` | US-M06-01, US-M06-02, US-M06-03 |
| `app.stock_counts`, `app.count_lines` | `POST /stock-counts/{id}/post` | US-M05-01, US-M05-02, US-M05-03 |
| `app.write_offs`, `app.write_off_lines` | `POST /write-offs/{id}/post` | US-M04-06 |
| `app.debt_openings` | `POST /debt-openings/{id}/post` + import | US-M08-07 |
| `app.debt_payments`, `app.debt_payment_allocations` | voqea `debt_payment.created` + `/post` | US-M08-04 |
| `app.debt_writeoffs` | `POST /debt-writeoffs/{id}/post` | **— (gap, §3 (b) da ham ko'rsatilgan)** |
| `app.supplier_payments`, `app.supplier_payment_allocations` | `POST /supplier-payments` | US-M07-04 |
| `app.expenses` | `POST /expenses/{id}/post` + voqea `expense.created` | US-M15-01 |
| `app.cash_movements`, `app.cash_moves` | voqea `cash_movement.created` + `POST /cash-movements` | US-M16-01 |
| `app.shifts` (farq provodkasi) | voqea `shift.closed` | US-M01-04, US-M16-02 |
| `app.supplier_returns`, `app.supplier_return_lines` | `POST /supplier-returns/{id}/post` | US-M07-05 |
| `app.stock_openings`, `app.opening_lines` | `POST /stock-openings/{id}/post` + import | US-M04-04 |
| `app.einvoices` (`direction=out`) | `POST /einvoices`, `/from-receipt` (provodkasiz) | US-M01-06 |
| `app.ledger_adjustments` | `POST /ledger-adjustments` | **— (gap, maxsus US yo'q)** |
| `app.product_prices`, `app.price_changes`, `app.price_change_lines` | `POST /price-changes/{id}/post` | US-M09-01, US-M09-02 |
| `app.purchase_orders`, `app.po_lines` | `POST /purchase-orders` (registrga ta'sir yo'q) | US-M07-01 |
| `app.stock_moves`, `app.stock_lots`, `app.avg_costs`, `app.stock_balances` (registrlar) | yuqoridagi barcha ombor hujjatlarining `/post`'i orqali (bevosita yozuvchi endpoint yo'q, faqat `GET`) | US-M04-01…06, M05, M06, M07 |
| `app.debt_moves`, `app.debt_balances` (registr) | nasiya/to'lov hujjatlari `/post`'i orqali | M08 barcha |
| `app.cash_moves` (registr) | `cash_movement.created`, `shift.closed`, `debt_payment.created` (naqd qism) | US-M16-01, US-M16-02 |
| `app.ledger_entries` (registr) | barcha posting endpointlari orqali (umumiy) | M01, M02, M04–M08, M11, M15 |
| `app.vat_moves` (registr) | `sale.created`, `return.created`, `einvoices` (`accept`) orqali | US-M10-01, US-M02-03, US-M07-03 |
| `app.fiscal_receipts` | `sale.created`, `debt_payment.created` ichida avtomatik + `POST /{id}/retry` | US-M01-01, US-M08-04; retry — **gap (US yo'q)** |
| `app.marking_codes` | `POST /marking-codes/verify`, `sale.created` ichida | US-M01-03 |
| `app.approval_requests`, `app.doc_approvals` | `POST /approval-requests`, `/approve`, `/reject` | US-M02-02, US-M03-01, US-M09-02 |
| `app.payment_checkouts` | `POST /payments/checkouts` | US-M01-05 |
| `app.discount_rules` | `discount-rules` CRUD | US-M03-02 |
| `app.counterparties`, `app.debt_doubtful_flags`, `app.counterparty_statement_links` | `counterparties` CRUD, `debt-doubtful-flags`, `statement-link` | US-M08-02, US-M08-05, US-M08-06; doubtful-flags — **gap (US yo'q)** |
| `app.products`, `app.product_categories`, `app.product_barcodes`, `app.internal_barcode_seq` | `products`/`product-categories` CRUD, `barcodes/internal-generate` | US-M09-05; umumiy CRUD — **gap (US yo'q)** |
| `app.label_print_queue` | `label-print-jobs`, `mark-printed` | US-M09-04 |
| `app.valuation_method_history` | `PATCH /valuation-settings` | US-M04-05 |
| `app.recost_jobs` | `POST /recost-jobs/{id}/retry` (ichki, valuation o'zgarishidan keyin) | **— (gap, US yo'q)** |
| `app.import_jobs` | `POST /import-jobs` → `/validate` → `/commit` | US-M04-04, US-M08-07 |
| `app.state_reports`, `app.state_report_diffs` | `state-reports` guruhi | US-M10-02, US-M10-04 |
| `app.ettn_documents` | — **(gap: 12'da jadval bor, 14/18/19/20'da yozuvchi endpoint topilmadi — e-TTN MVP'dan keyin, BP-01 ochiq savol)** |
| `app.period_closings` | `POST /period-closings` | US-M11-02 |
| `app.branches`, `app.warehouses`, `app.cash_registers`, `app.branch_tax_settings` | `branches`/`cash-registers` CRUD, `/tax-settings` | US-M14-03, US-M14-04; cash-registers CRUD'ning o'zi — **gap (US yo'q)** |
| `app.roles`, `app.role_permissions` | `roles` CRUD, `roles/{id}/permissions` | US-M13-01, US-M13-03; rol yaratish/tahrirlash o'zi — **gap (US yo'q)** |
| `app.users`, `app.memberships`, `app.devices` | `admin/users` guruhi | US-M13-01, US-M13-02, US-M13-04, US-M13-05, US-M13-07 |
| `auth.user_credentials`, `auth.otp_challenges`, `auth.sessions`, `auth.refresh_tokens`, `auth.authorization_codes`, `auth.login_attempts` | `/oauth/*`, `/auth/*` | **— (gap: infratuzilma, maxsus US yo'q — M13/M17 orqali bilvosita)** |
| `app.tenants`, `app.subscriptions`, `app.tenant_addons`, `app.billing_payments`, `app.tenant_tax_regimes` | `POST /auth/signup`, `billing/*`, `tenant/tax-regimes` | US-M17-01, US-M17-02, US-M14-04 |
| `app.telegram_links`, `app.notification_settings`, `app.notifications_log` | `notifications/telegram/*`, `notification-settings` | US-M18-01, US-M18-02, US-M18-03 |
| `app.ai_requests`, `app.ai_ocr_jobs` | `ai/chat`, `ai/ocr/jobs`, `ai/debt-reminders/*` | US-M18-04, US-M04-04, US-M08-03/08 |
| `app.ai_training_samples`, `app.ai_feedback` | **— (gap: 14/18/19/20'ning birortasida ham yozuvchi endpoint topilmadi)** |
| `app.tenant_glossary` | **— (gap: hech qanday endpointda tilga olinmagan)** |
| `app.audit_log` | barcha state-change endpointlari (yon ta'sir sifatida, `15-xavfsizlik-va-audit.md` §6) | hammasi |
| `app.outbox_jobs`, `app.sync_receipts`, `app.idempotency_keys`, `app.doc_sequences` | ko'plab endpointlar ichida ichki (OFD/e-faktura/marking retry, sync) | infratuzilma |
| `app.attachments` | `POST /attachments` (BO-04/BO-17/AI-03 oqimlarida) | US-M04-04, US-M07-03, US-M15-01 |
| `platform.label_templates` | — **(gap: faqat `GET`, yozuvchi endpoint yo'q — "tenant o'zgartira olmaydi", MVP uchun qasddan, 19 §5)** |
| `platform.plans`, `platform.addons`, `platform.oauth_clients`, `platform.signing_keys`, `platform.platform_admins` | — **(gap: 14/18/19/20'ning birortasida ham ochiq yozuvchi endpoint yo'q — ehtimol seed/migratsiya/ops orqali boshqariladi, lekin bu hujjatda tasdiqlanmagan)** |

**Qamrab olingan jadvallar**: 108 tadan ≈ 95 tasi kamida bitta endpoint/voqea bilan yoziladi (to'g'ridan-to'g'ri yoki registr sifatida); ≈ 13 tasi yuqorida ro'yxatlangan bo'shliqlar.

---

## 3. Bo'shliqlar ro'yxati

### A. US stories — MVP tier yo'q (05-mvp-chegarasi.md §1.1 jadvalida yo'q)

**Hal qilindi** — 11 ta hikoya (US-M01-05/06, US-M04-04/05, US-M09-07, US-M13-04…08, US-M14-04) `05-mvp-chegarasi.md` §1.1 jadvaliga qo'shildi (US-M09-07 — Should, qolganlari — Must).

### B. US stories — Bosqich (27-backlog.md) hech qaerda yo'q

US-M03-03 — **1 ta** (US-M09-07 Bosqich 6 ga qo'shildi; US-M03-03 Bosqich 4 hisobotlariga qo'shildi). Qolganlari modul darajasida bosqichga tegishli (masalan "M01 kassa (onlayn)" — 3-bosqich — barcha US-M01-xx shu yerga kiradi), lekin aniq ID bilan sanalmagan — bu "?" bilan belgilangan ~20 ta qator uchun aniqlashtirish tavsiya etiladi. **Tavsiya:** `27-backlog.md`ga har bosqich ichida aniq US-ID ro'yxatini qo'shish (hozir faqat modul nomi yoki ayrim ID bor).

### C. US stories — ekran yo'q

US-M03-03 (Could, lekin ekran umuman yo'q), US-M08-08, US-M14-02, US-M17-05 (uchalasi ham post-MVP, shuning uchun past ustuvorlik, lekin baribir ekran mavjud emas) — **4 ta**. **Tavsiya:** `07-ekran-tafsilotlari.md`ga margin-hisobot (US-M03-03) uchun BO-09 ichiga qo'shimcha blok, qolgan uchtasi uchun MVP'dan keyin bosqichida ekran loyihalash.

### D. Biznes jarayon (BP) qamrovi — tizimli bo'shliq

`04-biznes-jarayonlar.md` faqat 13 ta tranzaksion oqimni (BP-01…13) modellashtiradi. Quyidagi **butun modullar** hech qaysi BP'da ishtirok etmaydi: **M09 (narxlar), M12 (hisobotlar), M13 (huquqlar), M15 (xarajatlar), M16 (kassa pul harakati), M17 (obuna), M18 (bildirishnomalar)** — jami shu modullardagi **35 ta US** (jadval 1'dagi "— (gap)" BP ustunlari). Bundan tashqari M01/M04/M07/M08/M10/M11/M14 ichida ham alohida "setup/reporting" stilidagi stories (masalan US-M01-04 smena, US-M04-02/03/05/06, US-M07-05, US-M08-02/06/07/08/10, US-M11-03, US-M14-01/02/03/04) hech qaysi BP qadamida aniq tilga olinmagan. **Tavsiya:** yo `04-biznes-jarayonlar.md`ga bu modullar uchun qo'shimcha BP-14…BP-1x qo'shish (masalan "Xarajat yozish", "Kassa pul harakati", "Obuna/to'lov sikli"), yoki hujjatning boshida ochiq tan olish: "BP-01…13 faqat tranzaksion hujjat oqimlarini qamrab oladi; sozlama/hisobot/ro'l boshqaruvi kabi modullar qasddan tashqarida."

### E. Endpointlar — mos US yo'q (haqiqiy, modul/ekran bilan tasdiqlangan)

1. `POST /debt-writeoffs`→`/post` (`debts.forgive`, `13-provodka-qoidalari.md` §2.15) — "qarzni kechish" uchun M08'da hech qanday US yo'q.
2. `POST /debt-doubtful-flags`, `/unflag` — "shubhali qarz belgisi" uchun US yo'q.
3. `GET /fiscal-receipts`, `POST /{id}/retry` (`integrations.retry`) — fiskal chek monitoringi/qayta urinish uchun US yo'q.
4. `POST /roles`, `PATCH /roles/{id}` — maxsus rol yaratish/tahrirlashning o'zi uchun US yo'q (faqat tayinlash — US-M13-01/02 va limit — US-M13-03 bor).
5. `GET/PATCH /tenant/settings`, `POST /tenant/tax-regimes`, `PUT/DELETE /tenant/integrations/*` (20 #40a–e) — do'kon umumiy sozlamalari/integratsiya kaliti uchun US yo'q.
6. `GET/POST/PATCH /cash-registers` (20 #38–40) — kassa qurilmasini sozlashning o'zi uchun US yo'q.
7. `GET/POST /billing/addons`, `POST /{code}/reduce` (20 #58–60) — qo'shimcha kassa sotib olish/kamaytirish uchun US yo'q.
8. `GET /notifications-log` (20 #71) — yuborilgan xabarlar tarixi uchun US yo'q.
9. `GET /ai/usage` (20 #79) — umumiy AI sarfi ko'rinishi uchun US yo'q.
10. `sale.draft_voided`, `receipt.reprinted` voqealari (18 §5–6) — audit maqsadli, mos US yo'q (bu ikkisi uchun qasddan "faqat audit" deb yozilgan, shuning uchun past ustuvorlikdagi bo'shliq).
11. `products`/`product-categories`/`units` umumiy CRUD (19 §1–3) va `counterparties?is_supplier=true` directoryi (19 §9) — asosiy katalog/yetkazib beruvchi ma'lumotini yaratish/tahrirlashning o'zi uchun US yo'q (faqat import, narx, shtrix-kod qamrab olingan).
12. `GET /recost-jobs`, `/{id}/retry` (19 §18) — qayta hisoblash monitoringi uchun US yo'q.
13. `POST /ledger-adjustments`, `/cancel`, `GET` (20 #10/10a/10b, DB-12) — qo'lda buxgalteriya tuzatishi uchun US yo'q.

**Tavsiya:** `03-modullar-talablari.md`ga shu 13 funksiya guruhi uchun yo yangi US qo'shish, yoki ularni ataylab "infratuzilma/admin funksiyasi, alohida US kerak emas" deb belgilash (hozir hujjatda bu qaror aniq yozilmagan).

### F. Ekranlar — mos US yo'q

Yo'q — barcha 37 "biznes ekran"ning har birida kamida bitta `Bog'liq US` bor (§2a tasdiqlangan). `UX-INSTALL` o'zi ataylab istisno qilingan.

### G. Jadvallar — hech qanday endpoint tomonidan yozilmaydi

`app.ai_training_samples`, `app.ai_feedback`, `app.tenant_glossary`, `app.ettn_documents`, `platform.label_templates` (faqat `GET`), `platform.plans`, `platform.addons`, `platform.oauth_clients`, `platform.signing_keys`, `platform.platform_admins` — **9 ta jadval + 1 faqat-o'qish jadval** (`14-autentifikatsiya-oauth2.md`, `18-api-kassa.md`, `19-api-ombor.md`, `20-api-moliya-admin.md` to'liq grep qilindi, hech birida yozuvchi endpoint topilmadi). **Tavsiya:** `12-db-sxema.md`ga izoh qo'shish — bu jadvallar seed/migratsiya/ops orqali to'ldiriladimi, yoki `AI qatlami`/`platform admin` API'lariga yetishmayotgan endpointlarni qo'shish kerakmi, aniqlashtirilsin (`22-ai-qatlami.md` bilan solishtirish tavsiya etiladi — `ai_training_samples`/`ai_feedback` balki o'sha hujjatda tavsiflangan bo'lishi mumkin, bu matritsa faqat 12/14/18/19/20'ni tekshirdi).

### H. Ruxsat kodlari — endpoint tomonidan ishlatiladi, lekin 15-katalogda yo'q / aksincha

Tekshiruv (`15-xavfsizlik-va-audit.md` §2.1, 58 ta kod) va 18/19/20'dagi barcha `Ruxsat`/backtick-kod mentionlari solishtirildi — **nomuvofiqlik topilmadi**: 18 va 19'da ishlatilgan barcha ruxsat kodlari (`sales.*`, `returns.*`, `discount.*`, `stock.*`, `transfer.*`, `purchases.*`, `debts.*`, `prices.*`, `tax.*`, `catalog.manage`, `stock.opening.manage`, `valuation.settings.manage`, `labels.print`) 15-katalogda bor; 20'dagi barcha `Ruxsat` ustuni qiymatlari (`accounting.*`, `reports.*`, `settings.*`, `expenses.*`, `cash.*`, `billing.manage`, `notifications.manage`, `telegram.link`, `ai.*`, `platform.admin`) ham bor. **Hech qanday gap yo'q bu bo'limda** — ijobiy natija, alohida ta'kidlanadi.

### I. MVP Must stories — hech qaysi backlog bosqichida yo'q

Tekshirildi: barcha "Must" tegidagi US (05'da ro'yxatlangan 59 ta) `27-backlog.md`da kamida modul darajasida joy topadi (0–6 bosqich ichida). To'g'ridan-to'g'ri bo'shliq yo'q, lekin **band B** (aniq ID bilan sanalmagan ~20 ta "?" qator) shu yerga ham tegishli — ID darajasidagi aniqlik yetishmaydi, mazmun darajasida emas.

---

## Yakuniy hisob

- **US stories:** 84/84 jadvalga kiritilgan.
- **Ekranlar:** 38/38 (37 biznes + `/install`) — barchasi kamida bitta US'ga bog'langan (`/install`dan tashqari, bu qasddan).
- **Endpointlar:** `14` (26), `18` (37, index qatorlari), `19` (~89, bo'lim bo'yicha), `20` (88, index qatorlari) — **jami ≈ 240** endpoint/voqea, hammasi §2b'da ro'yxatlangan.
- **Jadvallar:** 108/108 — ~95 tasi kamida bitta endpoint/registr orqali yoziladi, ~13 tasi §3-G'da bo'shliq sifatida belgilangan.
- **Ruxsat kodlari:** 58 (15-katalog) — nomuvofiqlik topilmadi.
- **Sinxron voqea turlari:** 13 (`16-offline-sync.md` §2, yakuniy ro'yxat) — barchasi §1 va §2b'da US/endpoint bilan bog'langan.

**Bo'shliqlar soni turlar bo'yicha:** A) MVP tier yo'q — 11; B) Bosqich yo'q (to'liq) — 2 (+ ~20 "?" aniqlashtirish kerak); C) Ekran yo'q — 4; D) BP qamrovi — 7 butun modul + ~15 qo'shimcha US; E) Endpoint→US yo'q — 13 funksiya guruhi; F) Ekran→US yo'q — 0; G) Jadval→endpoint yo'q — 9 jadval + 1 faqat-o'qish; H) Ruxsat kod nomuvofiqligi — 0; I) Must→bosqich yo'q — 0 to'g'ridan-to'g'ri.
