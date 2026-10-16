# Izchillik matritsasi (traceability) — US → BP → Ekran → API → Jadval → Provodka → Ruxsat → Bosqich

**Maqsad:** har bir foydalanuvchi hikoyasi (US-Mxx-nn)dan implementatsiya uchun kerakli hamma narsaga (biznes jarayon, ekran, API/voqea, DB jadval, provodka qoidasi, ruxsat kodi, backlog bosqichi) bitta qatordan borish va bo'shliqlarni aniqlash.
**Kim uchun:** hammasi.
**Bog'liq fayllar:** `03-modullar-talablari.md`, `04-biznes-jarayonlar.md`, `05-mvp-chegarasi.md`, `07-ekran-tafsilotlari.md`, `12-db-sxema.md`, `13-provodka-qoidalari.md`, `15-xavfsizlik-va-audit.md`, `16-offline-sync.md`, `17-api-umumiy.md`–`20-api-moliya-admin.md`, `27-backlog.md`, `33-1c-integratsiya.md` (M19), `01-qarorlar.md` (#43–#71), `26-ochiq-savollar-reestri.md`, `research_notes/ochiq-savollar/02-db-nomlar.md` (ustun/enum nomlari).
**Holat:** joriy, 2026-10-16.

## Belgilar

- **MVP**: `Must`/`Should`/`Could` — `05-mvp-chegarasi.md` §1.1 jadvalidan; `Keyin` — MVP'dan keyinga aniq surilgan (qaror #33); **— (gap)** — 05'da bu US yo'q (hozir bunday qator qolmagan).
- **BP**: `04-biznes-jarayonlar.md`dagi BP-01…15 (BP-14 — kunni 1C ga yuborish, BP-15 — bank tushumi tasdig'i); **—** — bu US/modul uchun hech qanday BP yo'q (04 faqat 15 ta tranzaksion oqimni modellashtiradi — narx, hisobot, huquq, filial boshqaruvi, xarajat, kassa pul harakati, obuna, bildirishnoma kabi butun modullar BP qatlamida yo'q); **"?"** — modul BP'da bor, lekin bu aniq US BP matnida tilga olinmagan (xulosa chiqarilgan).
- **Bosqich**: `27-backlog.md`dagi 0–7 bosqich (7 — 1C integratsiyasi, MVP'dan keyin) yoki "MVP'dan keyin"; **"?"** — US aniq nomlanmagan, modul darajasidan xulosa qilingan.
- **Ruxsat**: `15-xavfsizlik-va-audit.md` §2.1 kodi; **—** — ruxsatsiz ochiq amal (masalan autentifikatsiyasiz endpoint) yoki tegishli kod topilmadi.
- **infratuzilma/admin** — US talab qilmaydigan funksiya (qaror #58 b): monitoring, sozlama, seed/ops yoki ichki quvur; bo'shliq hisoblanmaydi.
- Tashqi javob kutayotgan bandlar — "26 #N (OQ-0xx)".

---

## 1. Asosiy matritsa

### M01 — Kassa (POS)

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M01-01 | Chek yaratish va to'lov qabul qilish | Must | BP-02, BP-05 | POS-02, POS-03, POS-04 | voqea `sale.created` (`18-api-kassa.md` §4); `GET /api/v1/sales` (chek qidiruv, §4.8); fiskal chek — `FiscalPort` (hamkor bulut API yoki Do'kon agenti → FM → OFD, qaror #60; MVP'da `FISCAL_PROVIDER=fake`); bloklar `409 FISCAL_OFFLINE_48H_BLOCKED` (qaror #43), `409 FISCAL_DEVICE_LOCKED` | `app.sales`, `app.sale_lines`, `app.sale_payments` (`card_type`, `card_mask`, `rrn`, `card_entry_mode`, `qr_type`, `provider_tx_id` — qaror #64, #71), `app.stock_moves`, `app.stock_lots`, `app.vat_moves`, `app.ledger_entries`, `app.fiscal_receipts` (`fm_terminal_id`, `fm_receipt_seq`, `fiscal_at`, `ofd_acked_at`, `payment_form`, `delivery` — qaror #12, #43), `app.cash_registers` (`fm_state`, `last_unacked_receipt_at`, `fm_receipts_pending`) | §2.1–2.4 (naqdsiz → 5710, qaror #42) | `sales.create` | 3 (fiskal real adapter — 5, 26 #109 (OQ-012)) |
| US-M01-02 | Offline savdo + avtomatik sinxronlanish | Must | BP-02 (offline variant) | POS-02, POS-12 | `POST /api/v1/sync/push`, `GET /api/v1/sync/pull` (§17, `16-offline-sync.md`) | `app.sync_receipts`, `app.idempotency_keys` | §2.1–2.4 | `sales.create` | 3 |
| US-M01-03 | Markirovkalangan tovar kodini tekshirish | Must | BP-02 (qadam 5) | POS-02 | kod chek ichida OFD'ga (`FiscalPort` `items[].marking_codes`, qaror #17, #62); sotuvdan oldin `POST /api/v1/marking-codes/verify` (§15) — `MARKING_PRECHECK=warn` + lokal takror-kod tekshiruvi | `app.marking_codes`, `app.fiscal_receipts` | §2.1–2.4 (sale_lines ichida) | — (CRPT integratsiyasiga `integrations.retry` tegishli, sotuvda alohida kod yo'q) | 5 (sotuv UI va `MARKING_PRECHECK` — Bosqich 3 vazifasi; CRPT `verify`/`writeoff` real adapteri — 26 #40 (OQ-025)) |
| US-M01-04 | Smena ochish va yopish (Z-hisobot) | Must | **— (gap, BP yo'q)** | POS-01, POS-07 | voqea `shift.opened`/`shift.closed`; `GET /api/v1/shifts/{id}/z-report` (§3) | `app.shifts`, `app.cash_moves` | §2.19 (X-01) | `shift.open` / `shift.close` | 3 |
| US-M01-05 | UzQR to'lov (yuridik shaxs, 2026-07-01'dan majburiy) | Must | BP-05 | POS-03 | statik UzQR — kassir qo'lda tasdiqlaydi (`qr_type='static'`, faqat online); dinamik — `POST /api/v1/payments/checkouts`, `GET /{checkout_ref}`, `POST /payments/webhooks/{provider}` (§16), `UzqrPort` stub (qaror #64) | `app.payment_checkouts`, `app.sale_payments` (`qr_type`, `provider_tx_id` faqat `dynamic`da), `app.tenant_secrets` (`cash_register_id` — kassa UzQR kaliti) | §2.2 | `sales.create` | 3 (statik) / 5 (dinamik — 26 #49 (OQ-032)) |
| US-M01-06 | Chekdan keyin chiquvchi e-faktura (B2B) | Must | BP-13 | POS-06, BO-15 | `POST /api/v1/einvoices` (`direction=out`), `POST /einvoices/from-receipt` (§14a) | `app.einvoices` | §2.22 (provodkasiz) | `einvoice.create` | 5 |
| US-M01-07 | Kassada chek printeri va tarozini bir marta sozlash, sinov chek (qaror #60) | Must | **— (setup, BP yo'q)** | POS-16, POS-01, POS-04, BO-14 | qurilma-lokal (WebUSB/Web Serial/Web Bluetooth, tizim printeri); LAN 9100 printer va tarozi — Do'kon agenti lokal API (`127.0.0.1`); tarozi shablonlari — `PATCH /tenant/settings` (20 #40b) | `app.tenants` (`settings.weight_barcode_templates`); printer sozlamasi — qurilmada (Dexie) | — | — (sozlash; shablon — `settings.tenant`) | 3 (agent orqali LAN/tarozi — 5); transport sinovi — 26 #139 (OQ-060) |
| US-M01-08 | Integratsiyalangan karta terminali: summa terminalga, natija avtomatik; qo'lda zaxira tasdiq bilan (qaror #71) | Must | BP-05 (karta oqimi), BP-04, BP-11, BP-15 | POS-03, POS-16, BO-12 | Do'kon agenti lokal API `127.0.0.1:47110/v1/card/*` (`purchase`, `tx/{attempt_id}`, `cancel-pending`, `refund`, `void`, `settlement`, `terminals`, `health`; imkoniyat `card_terminal`); `POST /api/v1/card-terminal-transactions` (upsert, `id = attempt_id`), `GET /api/v1/card-terminal-transactions/{id}`; `GET/POST /api/v1/card-terminals`, `PATCH /api/v1/card-terminals/{id}`; `POST /api/v1/card-terminal-settlements` (`18-api-kassa.md` §16a, #42–#46); voqealar `sale.created` (`payments[].card_result`), `return.created` (`refund_card`), `debt_payment.created` (`card_result`), `shift.closed` (`card_settlements[]`, `z_report.card_split`); `PATCH /tenant/settings` (`card_manual_fallback`); xatolar `CARD_TERMINAL_UNREACHABLE`, `CARD_TERMINAL_BUSY`, `CARD_TERMINAL_TIMEOUT`, `CARD_DECLINED`, `CARD_OUTCOME_UNKNOWN`, `CARD_AMOUNT_MISMATCH`, `CARD_MANUAL_NOT_ALLOWED`, `CARD_MANUAL_APPROVAL_REQUIRED`, `CARD_VOID_FAILED`, `CARD_TRANSACTION_MISMATCH` | `app.card_terminals`, `app.card_terminal_transactions`, `app.card_terminal_settlements`, `platform.card_bin_rules`, `app.sale_payments`/`app.debt_payments`/qaytarish to'lovlari (`card_entry_mode`, `card_terminal_transaction_id`, `approval_code`, `card_scheme`, `card_type_source`, `manual_reason`), `app.tenants` (`settings.card_manual_fallback`), tasdiqlar (`kind='card_manual_entry'`) | §2.1–2.4 (5710), §2.18a (`rrn` bo'yicha moslashtirish) | `sales.create`; `card.manual_entry.approve`; `cash_register.manage` (terminal reyestri); `settings.tenant` (siyosat) | 3 (port, `FakeCardTerminalAdapter`, POS UI, zaxira siyosati) / 5 (agent `card_terminal`, BO-12, BO-24 `rrn`); real vendor drayveri — 26 #172–#174 |

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
| US-M03-03 | Chegirmalarning margin'ga ta'sirini hisobotda ko'rish | Could | **— (gap, BP yo'q)** | **— (GAP: hech qaysi ekranda yo'q)** | `GET /api/v1/reports/sales` "?" (aniq margin-hisobot endpointi yo'q) | `app.sale_lines`, `app.vat_moves` | — | `reports.sales.view` "?" | 4 |

### M04 — Ombor qoldig'i

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M04-01 | Kirimda balans avto yangilanish | Must | BP-01 | POS-08, BO-03 | `POST /goods-receipts`, `POST /{id}/post` (§8) | `app.goods_receipts`, `app.receipt_lines`, `app.stock_moves`, `app.stock_lots`, `app.stock_balances`, `app.ledger_entries` | §2.6–2.8 | `purchases.post` | 2 |
| US-M04-02 | Minimal zaxira chegarasida ogohlantirish | Should | **— (gap)** | BO-03 | `GET /api/v1/stock-balances?low_stock=` (§7) | `app.stock_balances` | — | `stock.view` | 4 |
| US-M04-03 | Ko'p filial konsolidatsiyalangan qoldiq | Should | **— (gap)** | BO-03 | `GET /api/v1/reports/stock?branch_id=` (20 #20) | `app.stock_balances` | — | `stock.view` | 4 |
| US-M04-04 | Boshlang'ich katalog/qoldiq kiritish (qo'lda/import/AI-03) | Must | **— (gap, onboarding, BP yo'q)** | BO-21 | `POST /api/v1/import-jobs` (`kind=products`/`opening_stock`), `POST /stock-openings`→`/post`, `POST /ai/ocr/jobs`→`/confirm` (AI-03 yo'li) | `app.import_jobs`, `app.stock_openings`, `app.opening_lines`, `app.ai_ocr_jobs` | §2.21 | `catalog.manage`, `stock.opening.manage` | 1 (yo'l 1–2) / 6 (yo'l 3 = AI-03) |
| US-M04-05 | Tannarx usulini (FIFO/AVECO) tanlash | Must | **— (gap, BP yo'q)** | BO-14 | `GET/PATCH /api/v1/valuation-settings` (§17) | `app.valuation_method_history` | `13-provodka-qoidalari.md` §3 (COGS: FIFO/AVECO) | `valuation.settings.manage` | 2 |
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
| US-M06-01 | Ko'chirish hujjatini yaratish (yuborish) | Must | BP-09 | POS-09, BO-03 | `POST /transfers`, `POST /{id}/post` (e-TTN "Ombordan omborga" yaratiladi, qaror #63), `POST /ettn-documents/{id}/sign-challenge`→`/submit-signed` yoki `/register-manual` (§20), `POST /{id}/send` (`transport_mode='vehicle'` bo'lsa e-TTN `registered` shart — `409 ETTN_REQUIRED`; voqea `transfer.sent`, §13) | `app.transfers` (`transport_mode`, `ettn_ref`), `app.transfer_lines`, `app.ettn_documents` (`transfer_id`, `transport_type`, `direction`), `app.stock_moves` | §2.9 | `transfer.create` | 2 (e-TTN operator yo'li — 5) |
| US-M06-02 | Kelgan tovarni tasdiqlab qabul qilish | Must | BP-09 | POS-09 | `POST /transfers/{id}/receive` (voqea `transfer.received`, §13); qabul tomoni e-TTN'ni tasdiqlaydi — `POST /ettn-documents/{id}/accept`\|`/reject` (§20) | `app.transfers`, `app.ettn_documents`, `app.stock_moves`, `app.stock_lots` | §2.10 | `transfer.receive` | 2 (e-TTN — 5) |
| US-M06-03 | Ko'chirishlar tarixi va bajarilish vaqti | Should | BP-09 | BO-03 | `GET /transfers`, `GET /{id}` (§13) | `app.transfers`, `app.transfer_lines` | — | `stock.view` "?" | 2 |

### M07 — Xarid

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M07-01 | Yetkazib beruvchiga xaridnoma yaratish | Must | BP-01 | BO-04 | `POST /purchase-orders`, `POST /{id}/send` (§10) | `app.purchase_orders`, `app.po_lines` | — (provodkasiz, "ta'sir yo'q") | `purchases.create` | 2 |
| US-M07-02 | Kelgan tovarni xaridnoma bilan solishtirib qabul qilish | Must | BP-01 | POS-08, BO-04 | `POST /goods-receipts`, `POST /{id}/post` (§8) | `app.goods_receipts`, `app.receipt_lines` | §2.6–2.8 | `purchases.receive` / `purchases.post` | 2 |
| US-M07-03 | Yetkazib beruvchi e-fakturasini kiritib QQS kreditini hisoblash | Must | BP-01, BP-12 | BO-04, BO-15 | `GET /einvoices?direction=in`, `POST /{id}/accept` (birlashtirilgan e-TTN ham tasdiqlanadi), `POST /goods-receipts/from-einvoice/{einvoice_id}` (§19); alohida kiruvchi e-TTN — `POST /ettn-documents/{id}/accept`\|`/reject` (§20) | `app.einvoices` (`risk_flag` standart `unknown` — 26 #47 (OQ-019), `factura_type`, `related_einvoice_id`), `app.ettn_documents`, `app.goods_receipts` | §2.6 | `einvoice.sign` / `purchases.post` | 5 |
| US-M07-04 | Yetkazib beruvchiga kreditorlik qarzini to'lash | Must | BP-12 | BO-04 | `POST /supplier-payments` (§11) | `app.supplier_payments`, `app.supplier_payment_allocations`, `app.ledger_entries` | §2.16 | `purchases.pay` | 4 (ikkinchi mezoni — 5) |
| US-M07-05 | Yetkazib beruvchiga tovar qaytarish | Should | **— (gap, BP yo'q)** | BO-04 | `POST /supplier-returns`, `POST /{id}/post` (§12) | `app.supplier_returns`, `app.supplier_return_lines`, `app.stock_moves`, `app.einvoices` (`factura_type='additional'` — QQS qo'shimcha EHF qabul qilinganda, 26 #115) | §2.20 | `purchases.return` (qoralama) + `purchases.post` (o'tkazish) | 2 |

### M08 — Nasiya (mijoz qarzi)

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M08-01 | Mijozga limit ichida nasiyaga sotish | Must | BP-03 | POS-03, POS-06, BO-16 | voqea `sale.created` (`sale_payments.method=debt`, §4); sotuvda chek yo'q (`FiscalPolicy.credit_sale_receipt='none'`; `credit_sale` cheki — 26 #9 (OQ-002)) | `app.sales`, `app.debt_moves`, `app.debt_balances`, `app.fiscal_receipts` (`kind='credit_sale'` — faqat `credit_type` rejimida) | §2.3 (daromad/QQS sotuv kuni, qaror #30) | `debts.create` | 4 (to'lov turi sotuv oqimida — 3) |
| US-M08-02 | Mijoz kredit limitini belgilash/o'zgartirish | Must | **— (gap, setup)** | BO-06 | `PATCH /api/v1/counterparties/{id}` (§11.4) | `app.counterparties` | — | `debts.limit.manage` | 4 |
| US-M08-03 | Muddati o'tgan qarzlar uchun avtomatik AI eslatma matni | Should | BP-11 | BO-06 | `POST /ai/debt-reminders/draft` (20 #77) | `app.ai_requests` | — | `ai.chat.use` (yuborishda `debts.remind`) | 6 |
| US-M08-04 | Mijozning nasiya qarzini (qisman/to'liq) to'lashini qabul qilish | Must | BP-11 | BO-06 | voqea `debt_payment.created`; `POST /debt-payments`→`/post` (§12.2–12.3); ortiqcha summa — `422` `debt_payment_exceeds_balance` (qaror #45) | `app.debt_payments` (`card_type`, `card_mask`, `rrn`, `qr_type` — qaror #64), `app.debt_payment_allocations` (`target_doc_type`), `app.debt_moves`, `app.fiscal_receipts` (bitta `debt_settlement` chek, qaror #45) | §2.14 | `debts.payment.accept` | 4 |
| US-M08-05 | Qarzga berishni 2–3 soniyada (offline) yozish | Must | BP-03 | POS-13 | voqea `sale.created` (`method=debt`) / voqea `counterparty.created` | `app.sales`, `app.counterparties` | §2.3 | `debts.create` | 4 |
| US-M08-06 | Mijozning qarz daftarini qog'oz daftardek ko'rish | Must | BP-11 "?" | POS-13, BO-06 | `GET /counterparties/{id}/debt-ledger` (§12.1) | `app.debt_moves`, `app.debt_balances` | — | `debts.create`/`debts.payment.accept` yoki `reports.sales.view` | 4 |
| US-M08-07 | Eski qog'oz daftardagi qarzlarni tizimga ko'chirish | Must | **— (gap, onboarding)** | BO-21 | `POST /debt-openings`→`/post`; `POST /import-jobs` (`kind=opening_debts`) (§12.4) | `app.debt_openings` | §2.13 | `stock.opening.manage` | 4 |
| US-M08-08 | Mijozga SMS/Telegram qarz xabari | Keyin (post-MVP) | BP-11 "?" | **— (GAP: ekran yo'q)** | `POST /api/v1/counterparties/{id}/statement-link` (§12.7) | `app.counterparty_statement_links` | — | `debts.create` / `debts.payment.accept` | MVP'dan keyin |
| US-M08-09 | Qarzlarni o'z vaqtida qaytarib olish (va'da sanasi, eslatma) | Must | BP-11 | POS-13, BO-06 | `PATCH /counterparties/{id}` / `debt_payments.promise_date` (§12.1) | `app.debt_moves` | — | `debts.limit.manage` (`PATCH /counterparties`) / `debts.payment.accept` | 4 |
| US-M08-10 | Qarzlar holatini bir qarashda ko'rish | Must | BP-11 "?" | BO-06 | `GET /reports/debts-aging?direction=receivable` (§12.8 → 20 #21) | `app.debt_balances` | — | `reports.finance.view` | 4 |
| US-M08-11 | Yetkazib beruvchilarga qarzni ham daftar kabi yuritish | Must | BP-12 "?" | POS-13, BO-04, BO-06 | `GET /reports/debts-aging?direction=payable` (BO-04 manbai) | `app.counterparties`, `app.supplier_payments` | §2.16 | `purchases.pay` | 4 |

### M09 — Narxlar *(modul darajasida BP yo'q — bo'shliq, pastga qarang)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M09-01 | Narxni yangilash, eski narx tarixda saqlanishi | Must | **— (gap)** | BO-05 | `GET /products/{id}/prices`, `POST /price-changes`→`/post` (§4) | `app.product_prices`, `app.price_changes`, `app.price_change_lines` | §2.25 (price_changes posting) | `prices.edit` | 1 |
| US-M09-02 | Katta narx o'zgarishini tasdiqlash | Should | **— (gap)** | BO-05, BO-16 | `POST /price-changes` (`pending_approval`) + `approval-requests` (§4) | `app.price_changes`, `app.approval_requests` | — | `prices.approve` | 6 |
| US-M09-03 | Kassada joriy narxni ko'rish (o'zgartirib bo'lmaydi) | Must | **— (gap)** | POS-02, POS-11 | `GET /products/{id}/prices` yoki lokal kesh (Dexie `prices`) | `app.product_prices` | — | — (faqat o'qish) | 3 |
| US-M09-04 | Narxi o'zgargan tovarlarning yorliqlarini qayta chop etish | Should | **— (gap)** | BO-18 | `GET /label-print-queue`, `GET /label-templates`, `POST /label-print-jobs` (§5) | `app.label_print_queue`, `platform.label_templates` | — | `labels.print` | 6 |
| US-M09-05 | Shtrix-kodi yo'q tovarga ichki shtrix-kod berish | Should | **— (gap)** | BO-18 | `POST /products/{id}/barcodes/internal-generate` (§1) | `app.product_barcodes`, `app.internal_barcode_seq` | — | `catalog.manage` | 1 |
| US-M09-06 | Tarozida tortilgan tovarni bitta skanerlash bilan sotish | Should | **— (gap)** | BO-14 | lokal: tarozi shtrix-kod formati `tenants.settings`dan (Dexie `settings`) | `app.products` (og'irlik qatori, lokal parsing) | — | `catalog.manage` (format sozlash) | 3 |
| US-M09-07 | Doimiy/ulgurji mijozga standart chegirma % (mijoz kartasida) | Should | **— (gap)** | POS-02 | `PATCH /counterparties/{id}` (`standing_discount_pct`, 18 §11) | `app.counterparties` (`standing_discount_pct`) | — | `prices.edit` "?" | 6 |

### M10 — QQS

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M10-01 | Har bir sotuvdan QQS avtomatik hisoblash | Must | BP-07 | BO-07 | voqea `sale.created` (QQS qatori); `GET /vat-moves`, `GET /reports/vat-summary` (20 #1–2); oylik hisobga olish — `GET/POST /tax-settlements`, `/{id}/post`, `/{id}/cancel` (20 #8a–8d, `tax_kind='vat_offset'`) | `app.vat_moves`, `app.tax_settlements` | §2.1–2.4; §2.26 (`Dt 6410 / Kt 4410`) | `tax.vat.view`; `tax_settlements` — `accounting.post` | 3; `tax_settlements` — 4 |
| US-M10-02 | Davlat QQS hisobotini 5 ish kuni ichida solishtirish (qaror #50) | Must | BP-08 | BO-10 | `POST /state-reports`, `POST /{id}/compare`, `GET /{id}/diffs`, `POST /{id}/correction` (20 #3–8) | `app.state_reports`, `app.state_report_diffs` | `13-provodka-qoidalari.md` §4 | `tax.compare.review` / `tax.correction.submit` | 6 |
| US-M10-03 | Yuqori xavfli ("qizil") fakturalarning QQS kreditiga ta'siri | Should | BP-07, BP-12 "?" | BO-07, BO-15 | `GET /einvoices?risk_flag=` (§19) | `app.einvoices` | — | `tax.compare.review` | 5 |
| US-M10-04 | QQS to'lamaydigan (aylanma solig'i) biznes uchun davlat hisobotini solishtirish | Must | BP-08 "?" | BO-10, BO-07 | `POST /state-reports` (`tax_type=turnover`, 20 #3); oylik aylanma solig'i — `POST /tax-settlements` (`tax_kind='turnover_tax'`) → `/post` (20 #8b–8c) | `app.state_reports`, `app.tax_settlements` | §4, §4.3 (`Dt 9430\|9820 / Kt 6410` — `settings.turnover_tax_account`) | `tax.compare.review`; `tax_settlements` — `accounting.post` | 6 (`tax_settlements` — 4) |

### M11 — Buxgalteriya

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M11-01 | Har bir sotuv/xariddan avtomatik provodka | Must | BP-06 | BO-08 | `GET /ledger-entries` (20 #9) — provodka posting paytida avtomatik yoziladi | `app.ledger_entries` | §2.1–2.21 (barcha hujjat turlari) | `accounting.post` | 2 |
| US-M11-02 | Oy yakunida balans va daromad-xarajat hisoboti | Must | BP-06 "?" | BO-08 | `POST /period-closings`, `GET /reports/trial-balance`\|`/profit-and-loss`\|`/balance-sheet` (20 #11–16) | `app.period_closings`, `app.ledger_entries` | `13-provodka-qoidalari.md` §5 (davr yopish) | `accounting.period.close` | 5 |
| US-M11-03 | Asosiy moliyaviy ko'rsatkichlarni sodda ko'rinishda ko'rish | Should | **— (gap)** | BO-02 | `GET /reports/dashboard` (20 #17) | `app.ledger_entries` (hosila) | — | `reports.sales.view` | 5 |
| US-M11-04 | Bank tushumi tasdig'i: yo'ldagi pul (5710) → bank (5110) + komissiya (qaror #42) | Must | BP-15 | BO-24 | `GET/POST /bank-settlements`, `GET /bank-settlements/{id}`, `POST /bank-settlements/{id}/post`, `POST /bank-settlements/{id}/cancel`, `GET /bank-settlements/transit-balances` (5710 qoldig'i — filial × usul), `POST /bank-settlements/imports` (1CClientBankExchange `.txt` → qoralamalar) (20 #55a–55g; faqat back-office, sync voqeasi yo'q) | `app.bank_settlements` (`source='manual'\|'statement_import'`, `variance_amount` — faqat inkassa), `app.ledger_entries`, `app.attachments`, `app.doc_sequences` (`BT`) | §2.18a (komissiya `Dt 9430 / Kt 5710`, inkassa — 9410) | `bank_settlements.manage` | 4 |

### M12 — Hisobotlar *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M12-01 | Kunlik savdo hisoboti (umumiy va filial bo'yicha) | Must | **— (gap)** | BO-02, BO-09 | `GET /reports/dashboard`, `GET /reports/sales` (20 #17–18) | `app.sales` (hosila) | — | `reports.sales.view` | 4 |
| US-M12-02 | Eng ko'p/kam sotiladigan tovarlar hisoboti | Should | **— (gap)** | BO-09 | `GET /reports/top-products` (20 #19) | `app.sale_lines` (hosila) | — | `reports.sales.view` | 4 |
| US-M12-03 | QQS va davlat solishtirish hisobotini eksport qilish | Must | **— (gap)** | BO-09 | `POST /reports/{report-kod}/export`, `GET /reports/export-jobs/{job_id}` (20 #22–23) | — (eksport fayli, `attachments`) | — | `reports.export` | 6 |

### M13 — Huquqlar *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M13-01 | Xodim qo'shib, rol(lar) belgilash | Must | **— (gap)** | BO-11 | `POST /admin/users` (14 §20); `PUT /roles/{id}/permissions` (20 #28) | `app.users`, `app.memberships`, `app.role_permissions` | — | `settings.users` | 1 |
| US-M13-02 | Kichik do'konda bitta xodimga bir nechta rol | Must | **— (gap)** | BO-11 | `POST /admin/users` (`roleIds` multi) | `app.memberships` | — | `settings.users` | 1 |
| US-M13-03 | Operatsiya limitlarini rolga/shaxsga bog'lab sozlash | Should | **— (gap)** | BO-11 | `GET/PUT /roles/{id}/permissions` (20 #27–28) | `app.role_permissions` | — | `settings.users` | 1 |
| US-M13-04 | Xodimni admin panel orqali to'liq ma'lumoti bilan qo'shish | Must | **— (gap)** | BO-11 | `POST /admin/users` (`purpose=invite`) (14 §20) | `app.users`, `auth.otp_challenges` | — | `settings.users` | 1 |
| US-M13-05 | Xodimni vaqtincha bloklash/blokdan chiqarish | Must | **— (gap)** | BO-11 | `PATCH /admin/users/{id}` | `app.users` (blocked_at) | — | `settings.users` | 1 |
| US-M13-06 | Xodimning parolini/PIN kodini qayta tiklash | Must | **— (gap)** | POS-01, BO-01, BO-11 | `POST /admin/users/{id}/reset-password`, `/reset-pin` (BO-11 manbai) | `auth.user_credentials`, `auth.otp_challenges` | — | `settings.users` | 1 |
| US-M13-07 | Xodim sessiyalarini ko'rish va bekor qilish | Must | **— (gap)** | BO-11 ("Qurilmalar" tabi, qaror #56 a) | `GET /admin/users/{id}/sessions`, `GET /{id}/devices`, `POST /{id}/revoke-sessions`; `GET /devices`, `POST /devices/{id}/revoke` (20 #29a–29b) | `auth.sessions`, `app.devices` | — | `settings.users`; qurilmalar — `devices.revoke` | 1 |
| US-M13-08 | Platforma admini: tenant va Egasi hisobini boshqarish | Must | **— (gap)** | ADM-01, BO-11 | `GET/POST /platform/tenants/{id}/owner/...` (14 §18.1) | `platform.platform_admins`, `app.users` | — | `platform.admin` | 6 |

### M14 — Filiallar

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M14-01 | Barcha filiallar bo'yicha konsolidatsiyalangan ko'rinish | Should | BP-09 "?" | BO-12 | `GET /reports/stock?branch_id=` (bo'sh = konsolidatsiya) | `app.stock_balances`, `app.branches` | — | `stock.view` | 4 |
| US-M14-02 | Filialdan filialga narx/chegirma siyosatini nusxalash | Keyin (post-MVP) | **— (gap)** | **— (GAP: ekran yo'q)** | `POST /branches/{id}/copy-pricing` (20 #36) | `app.product_prices`, `app.discount_rules` | — | `prices.edit` | MVP'dan keyin |
| US-M14-03 | Yangi filial (do'kon) qo'shish | Must | BP-09 "?" | BO-12 | `POST /branches` (20 #31); kassalar — `cash-registers` (20 #38–40) | `app.branches`, `app.warehouses` (`inventory_account` — do'kon 2920, ombor 2910), `app.cash_registers` (`tax_registered_at`, `outlet_address_snapshot`, `txkm_contract_ref`, `fm_state`) | — | `settings.branches`; kassa — `cash_register.manage` | 1 |
| US-M14-04 | Filial uchun "aholi punkti toifasi"ni belgilash (aylanma solig'i) | Must | BP-09 "?" | BO-12 | `GET/POST /branches/{id}/tax-settings` (20 #34–35) | `app.branch_tax_settings` | — | `settings.branches` | 1 |

### M15 — Xarajatlar *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M15-01 | Xarajatni 10 soniyada yozish | Must | **— (gap)** | BO-17, POS-14 | `POST /expenses`, `POST /{id}/post` (20 #42–43); POS kassa xarajati — voqea `expense.created` (`18`, `cash.withdraw`) | `app.expenses`, `app.ledger_entries` | §2.17 | `expenses.create` | 4 |
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
| US-M17-01 | 2 daqiqada ro'yxatdan o'tish | Must | **— (gap)** | BO-21, BO-14 | `POST /auth/signup` (14 §4/§20) — foydalanish shartlari aksepti majburiy; AI chegaradan tashqari uzatish roziligi — `POST /tenant/consents` (20 #40h) (qaror #61; matn — 26 #127 (OQ-042)) | `app.tenants` (`legal_form`, `accepted_terms_version`, `accepted_terms_at`, `accepted_terms_ip`, `settings.ai_cross_border_enabled`), `app.subscriptions`, `app.memberships`, `app.branches`, `app.warehouses`, `app.cash_registers`, `app.roles`, `app.doc_sequences` | — | — (autentifikatsiyasiz) | 1 |
| US-M17-02 | Tarifni tanlash va to'lash | Must | **— (gap)** | BO-19 | `GET /billing/plan`, `POST /billing/checkout` (20 #56, #61) | `app.subscriptions`, `app.billing_payments` | — | `billing.manage` | 6 |
| US-M17-03 | To'lov muddatini unutmaslik, muddat o'tsa ham darhol to'xtamaslik | Must | **— (gap)** | POS-01, BO-01, BO-19 | `GET /auth/session`, `GET /billing/pay` (14 §16) | `app.subscriptions` | — | — (sessiya darajasida; to'lovda `billing.manage`) | 6 |
| US-M17-04 | Platforma admini: tenantlar/obunalar/to'lovlarni ko'rish | Must | **— (gap)** | ADM-01 | `GET /platform/tenants...` (14 §18.1) | `platform.platform_admins`, `app.tenants` | — | `platform.admin` | 6 |
| US-M17-05 | Xizmatdan chiqishda barcha ma'lumotni olib ketish | Keyin (post-MVP, Could) | **— (gap)** | **— (GAP: ekran yo'q)** | `POST/GET /billing/export-my-data` (14 §16.5, 20 #65a) — endpoint MVP'da (lokaut, qaror #20, Bosqich 6); faqat `closed` holatdan chiqish eksporti (US-M17-05) — MVP'dan keyin | — (eksport fayli) | — | — (SMS OTP, bir martalik token) | MVP'dan keyin |

### M18 — Bildirishnomalar va Egasi uchun Telegram bot *(modul darajasida BP yo'q)*

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M18-01 | Telegram akkauntini do'konga ulash | Must | **— (gap)** | BO-20 | `POST /notifications/telegram/link-start` (20 #66) | `app.telegram_links` | — | `telegram.link` | 4 |
| US-M18-02 | Har kuni kechqurun qisqa hisobot | Must | **— (gap)** | BO-20 | `GET/PATCH /notification-settings` (20 #69–70) | `app.notification_settings`, `app.notifications_log` | — | `notifications.manage` | 4 |
| US-M18-03 | Muhim hodisalar haqida darhol xabar | Should | **— (gap)** | BO-20 | `PATCH /notification-settings` (20 #70) | `app.notification_settings`, `app.notifications_log` | — | `notifications.manage` | 4 |
| US-M18-04 | Botdan oddiy savol so'rash (AI-01) | Could | **— (gap)** | BO-13 | `POST /ai/chat` (20 #72) | `app.ai_requests` | — | `ai.chat.use` | 6 |

### M19 — 1C integratsiyasi (MVP'dan keyin, Bosqich 7; manba — `33-1c-integratsiya.md`)

Barcha qatorlar: MVP — `Keyin` (Bosqich 7, qaror #37); BP — BP-14; provodka — **yo'q** (1C'ga provodka, QQS registri, tannarx yuborilmaydi — qaror #39; 1C hujjatni o'zi o'tkazadi). W-xx — `33` §10 veb API (`/api/v1/onec-*`), A-xx — `33` §9.3 agent API (`/api/v1/onec-agent/*`, ruxsat kodi emas, agent tokeni scope `onec.agent`). Ko'rish har doim `onec.view`.

| US-id | Qisqa nomi | MVP | BP | Ekran(lar) | API | Jadvallar | Provodka | Ruxsat | Bosqich |
|---|---|---|---|---|---|---|---|---|---|
| US-M19-01 | Do'kon kompyuterini (agent) xavfsiz ulash | Keyin | BP-14 (sozlash) | BO-22 | `/oauth/device_authorization` (14), W-03, W-04, W-05; A-01, A-10 | `app.onec_agents`, `app.devices` (`kind='onec_agent'`), `auth.onec_device_authorizations` | — | `onec.settings.manage` | 7 |
| US-M19-02 | 1C bazasi yaroqliligini bir ekranda ko'rish (onboarding tekshiruvlari) | Keyin | BP-14 (sozlash) | BO-22 | A-02, W-09, W-10, W-11, W-12, W-13 | `app.onec_bases`, `app.onec_metadata_snapshots`, `app.onec_agent_tasks` | — | `onec.settings.manage` | 7 |
| US-M19-03 | Filial → 1C bazasi, sana va rejimni belgilash | Keyin | BP-14 (sozlash) | BO-22 | W-16, W-17, W-18, W-19, W-20 | `app.onec_branch_bindings`, `app.onec_settings` | — | `onec.settings.manage` | 7 |
| US-M19-04 | ERP ↔ 1C moslashtirish (tovar, kassa, to'lov turi, kontragent) | Keyin | BP-14 (sozlash) | BO-22 | W-21…W-29 | `app.onec_catalog_items`, `app.onec_mappings`, `app.onec_value_mappings` | — | `onec.mapping.edit` | 7 |
| US-M19-05 | 1C'da yangi element faqat tasdiqdan keyin yaratiladi | Keyin | BP-14 | BO-22 | W-30, W-31, W-32, W-33 | `app.onec_ref_create_requests`, `app.onec_mappings` | — | `onec.mapping.edit` (taklif), `onec.refs.create` (tasdiq) | 7 |
| US-M19-06 | Kun yopilgach preview va tayyorlik | Keyin | BP-14 | BO-23 | W-34…W-38, W-40, W-41, W-42 | `app.onec_export_batches`, `app.onec_export_items`, `app.onec_export_item_sources`, `app.devices` (`outbox_*`) | — | `onec.export.prepare`; istisno — `onec.export.approve` | 7 |
| US-M19-07 | Preview'ni bir tugma bilan 1C ga yuborish | Keyin | BP-14 | BO-23 | W-43 (`preview_hash`, `acknowledged_warnings`), W-51; A-03, A-04, A-05 | `app.onec_export_batches`, `app.onec_agent_tasks`, `app.onec_task_results`, `app.onec_object_refs` | — | `onec.export.approve` | 7 |
| US-M19-08 | Takror bosish / uzilishda dublikat yo'q | Keyin | BP-14 | BO-23 | W-43, W-48; A-05 | `app.onec_object_refs`, `app.onec_export_items` | — | `onec.export.approve` | 7 |
| US-M19-09 | Yozilmagan hujjat sababini ko'rib qayta yuborish | Keyin | BP-14 | BO-23 | W-39, W-45, W-46 | `app.onec_export_items`, `app.onec_agent_tasks` | — | `onec.export.correct` | 7 |
| US-M19-10 | Jamlarni avtomatik solishtirish (`read_totals`) | Keyin | BP-14 | BO-23 | W-47, W-50, W-52, W-53 | `app.onec_reconciliations`, `app.onec_export_batches` | — | `onec.export.prepare` (solishtirish), `onec.export.correct` (qabul) | 7 |
| US-M19-11 | Kech offline chek yuborilgan kunni yangilaydi | Keyin | BP-14 (+ BP-02 offline) | BO-23 | `POST /sync/push` → `OneCChangeTracker`; W-48 | `app.onec_export_batches` (`needs_resync`, `revision`), `app.onec_export_items` | — | `onec.export.correct` | 7 |
| US-M19-12 | Yopiq 1C davri — faqat tuzatuvchi hujjat | Keyin | BP-14 | BO-23 | W-49 | `app.onec_export_batches`, `app.onec_export_items` | — | `onec.export.correct` | 7 |
| US-M19-13 | Avto-tayyorlash va (Egasi yoqsa) avto-tasdiq | Keyin | BP-14 | BO-22 | W-20 | `app.onec_settings`, `app.onec_export_batches` | — | `onec.settings.manage`; `auto_approve` — faqat Egasi (`OWNER_ONLY`) | 7 |
| US-M19-14 | Telegram natija/muammo xabarlari | Keyin | BP-14 | BO-20, BO-23 | `GET/PATCH /notification-settings` (20 #69–70) | `app.notification_settings`, `app.outbox_jobs` (`kind='telegram'`), `app.onec_settings` (`notify_user_ids`) | — | `onec.view`, `notifications.manage` | 7 |
| US-M19-15 | Kompyuter o'chiq bo'lsa ham hech narsa yo'qolmaydi | Keyin | BP-14 | BO-23, BO-14 | A-03; W-55 | `app.onec_agent_tasks`, `app.onec_agents`, `app.onec_export_batches` | — | `onec.view` | 7 |
| US-M19-16 | ERP'da bekor qilingan hujjat 1C'da ham aks etadi | Keyin | BP-14 | BO-23 | W-48, W-43 | `app.onec_export_items`, `app.onec_object_refs` | — | `onec.export.correct`, `onec.export.approve` | 7 |
| US-M19-17 | Kompyuter almashtirilganda tarix saqlanadi | Keyin | BP-14 (sozlash) | BO-22 | W-05, W-14, W-15; A-02 | `app.onec_bases`, `app.onec_agents`, `app.onec_object_refs` | — | `onec.settings.manage` | 7 |
| US-M19-18 | 1C'da qo'lda o'zgartirilgan/o'chirilgan hujjatni bilish (drift) | Keyin | BP-14 | BO-22 (Jurnal), BO-23 | W-08, W-51, W-52, W-54 | `app.onec_reconciliations`, `app.onec_events`, `app.onec_object_refs` | — | `onec.view` | 7 |

**Jami: 105 ta US** (M01=8, M02=3, M03=3, M04=6, M05=3, M06=3, M07=5, M08=11, M09=7, M10=4, M11=4, M12=3, M13=8, M14=4, M15=3, M16=3, M17=5, M18=4, M19=18).

---

## 2. Teskari indekslar

### 2a. Ekran → US

Manba: `07-ekran-tafsilotlari.md` har bir ekrandagi **"Bog'liq US"** qatori (so'zma-so'z, grep bilan tekshirilgan).

| Ekran | Bog'liq US |
|---|---|
| POS-01 | US-M01-04, US-M01-07, US-M17-03, US-M13-06 |
| POS-02 | US-M01-01, US-M01-02, US-M01-03, US-M03-01, US-M09-03, US-M09-07 |
| POS-03 | US-M01-01, US-M01-05, US-M01-08, US-M08-01 |
| POS-04 | US-M01-01, US-M01-07 |
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
| POS-16 | US-M01-07, US-M09-06, US-M01-08 |
| BO-01 | US-M13-06, US-M17-03 |
| BO-02 | US-M12-01, US-M11-03 |
| BO-03 | US-M04-01, US-M04-02, US-M04-03, US-M06-03, US-M04-06, US-M05-02, US-M05-03 |
| BO-04 | US-M07-01, US-M07-02, US-M07-03, US-M07-04, US-M07-05, US-M08-11 |
| BO-05 | US-M09-01, US-M09-02, US-M03-02 |
| BO-06 | US-M08-03, US-M08-04, US-M08-06, US-M08-09, US-M08-10, US-M08-11 |
| BO-07 | US-M10-01, US-M10-03, US-M10-04, US-M11-01 (`tax_settlements`) |
| BO-08 | US-M11-01, US-M11-02; "Qayta hisoblash navbati" bloki — infratuzilma/admin (qaror #56 c) |
| BO-09 | US-M12-01, US-M12-02, US-M12-03, US-M16-03, US-M02-03 |
| BO-10 | US-M10-02, US-M10-04, AI-05 |
| BO-11 | US-M13-01…08 (barcha 8 tasi) |
| BO-12 | US-M14-01, US-M14-03, US-M14-04, US-M01-08 |
| BO-13 | AI-01, US-M18-04 |
| BO-14 | US-M04-05, US-M09-06, US-M01-03, US-M01-07, US-M17-01, US-M19-15 («1C» qatori, W-55); "Sinxron istisnolari" bloki — infratuzilma/admin (qaror #56 b) |
| BO-15 | US-M07-03, US-M07-05, US-M01-06, US-M10-03 |
| BO-16 | US-M02-02, US-M03-01, US-M08-01, US-M09-02, US-M16-01 |
| BO-17 | US-M15-01, US-M15-02, US-M15-03 |
| BO-18 | US-M09-04, US-M09-05, US-M09-06 |
| BO-19 | US-M17-02, US-M17-03 |
| BO-20 | US-M18-01, US-M18-02, US-M18-03, US-M19-14 |
| BO-21 | US-M17-01, US-M04-04, US-M08-07 |
| BO-22 | US-M19-01, -02, -03, -04, -05, -13, -17, -18 («Jurnal» — drift) (`33` §13.1) |
| BO-23 | US-M19-06…-12, -14, -15, -16, -18 (`33` §13.2) |
| BO-24 | US-M11-04 |
| UX-INSTALL (`/install`) | — (41 ekran ro'yxatiga kirmaydi; yordamchi route) |
| ADM-01 | US-M13-08, US-M17-04 |

**US→Ekran bo'shliqlari** (quyidagi US'larning hech bir ekranning "Bog'liq US" qatorida yo'qligi tasdiqlandi): **US-M03-03, US-M08-08, US-M14-02, US-M17-05** — batafsil §3da.

### 2b. Endpoint → US

Har bir fayl o'zining endpoint indeksidagi tartib raqami bilan berilgan (`18-api-kassa.md` §1, `20-api-moliya-admin.md` "Endpoint indeksi", `14-autentifikatsiya-oauth2.md` §20; `19-api-ombor.md`da rasmiy raqamlangan indeks yo'q — bo'lim raqami bilan ko'rsatilgan). **"— (gap)"** — hech qanday US-Mxx-nn topilmadi (aniq tekshirilgan, taxmin emas); **"?"** — modul orqali xulosa.

#### 14-autentifikatsiya-oauth2.md (§20, 29 qator)

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

#### 18-api-kassa.md (§1, 46 qator)

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
| `debt_payment.created`, `POST /debt-payments`→`/post` | US-M08-04 (karta rekvizitlari — qaror #64) |
| `POST /debt-openings`→`/post` | US-M08-07 |
| `GET /debt-payments`, `/{id}`, `POST /debt-payments/{id}/cancel` | US-M08-04 (BO-06; `debts.payment.accept`) |
| `GET /debt-openings`, `/{id}`, `POST /debt-openings/{id}/cancel` | US-M08-07 (BO-06; `stock.opening.manage` yoki `debts.limit.manage`) |
| `POST /debt-writeoffs`→`/post` | **— (gap: `debts.forgive` ruxsati bor, lekin "qarzni kechish" uchun hech qanday US-M08-xx yo'q)** |
| `GET /debt-writeoffs`, `/{id}`, `POST /debt-writeoffs/{id}/cancel` | **— (gap: qarzni kechish US'i yo'q)** (BO-06; `debts.forgive`) |
| `POST /debt-doubtful-flags`, `/unflag` | **— (gap: shubhali qarz belgisi uchun US yo'q)** |
| `GET /reports/debts-aging?direction=receivable` | US-M08-10 |
| `cash_movement.created`, `GET /cash-movements` | US-M16-01, US-M16-03 |
| `expense.created` (POS kassa xarajati) | US-M15-01, US-M16-01 |
| `GET /fiscal-receipts`, `/{id}` | infratuzilma/admin (fiskal chek monitoringi; qaror #58 b) |
| `POST /fiscal-receipts/{id}/retry` | infratuzilma/admin (`integrations.retry`; qaror #58 b) |
| `einvoices` (direction=out) guruhi | US-M01-06 |
| `POST /marking-codes/verify` | US-M01-03 (`MARKING_PRECHECK`, qaror #62) |
| `payments/checkouts`, `/{ref}`, `/webhooks/{provider}` | US-M01-05 |
| `sync/push`, `sync/pull` | US-M01-02 |
| `GET /sales`, `/{id}` | US-M01-01, US-M02-01 |
| `POST /card-terminal-transactions`, `GET /card-terminal-transactions/{id}` (#42–#43) | US-M01-08, US-M02-01, US-M08-04 (qaror #71) |
| `GET/POST /card-terminals`, `PATCH /card-terminals/{id}` (#44–#45) | US-M01-08 (BO-12, POS-16; `cash_register.manage`) |
| `POST /card-terminal-settlements` (#46) | US-M01-08, US-M16-02 |

#### 19-api-ombor.md (bo'lim raqami bilan, 102 endpoint)

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
| `powers-of-attorney` (§8a: `POST`, `GET`, `GET /{id}`, `sign-challenge`, `submit-signed`, `cancel`) | US-M07-02 (BO-04, POS-08, BO-15; `purchases.create`, imzo — `einvoice.sign`; qaror #63) |
| `counterparties?is_supplier=true` (yetkazib beruvchi directoryi) | **— (gap: yetkazib beruvchi master-data boshqaruvi uchun maxsus US yo'q)** |
| `purchase-orders` | US-M07-01 |
| `supplier-payments` | US-M07-04 |
| `supplier-returns` | US-M07-05 |
| `transfers` (`post` — e-TTN yaratadi) | US-M06-01, US-M06-02, US-M06-03 |
| `stock-counts` | US-M05-01, US-M05-02, US-M05-03 |
| `write-offs` | US-M04-06 |
| `stock-openings` | US-M04-04 |
| `valuation-settings` | US-M04-05 |
| `stock-settings` | US-M04-02 "?" (kam qoldiq chegarasi shu yerda sozlanadi) |
| `recost-jobs` | infratuzilma/admin — BO-08 "Qayta hisoblash navbati" (qaror #56 c, #58 b) |
| `einvoices` (direction=in) | US-M07-03 |
| `ettn-documents` (§20: `sign-challenge`, `submit-signed`, `register-manual`, `accept`, `reject`) | US-M06-01, US-M06-02, US-M07-03 (qaror #63) |

#### 20-api-moliya-admin.md ("Endpoint indeksi", 107 raqamli qator + `/platform/*` 10 + `/onec-*` 55)

| # | Endpoint | US |
|---|---|---|
| 1–2 | `GET /reports/vat-summary`, `/vat-moves` | US-M10-01, US-M02-03 |
| 3–8 | `state-reports` guruhi | US-M10-02, US-M10-04 |
| 7a | `POST /state-reports/{id}/confirm` | US-M10-02 (BO-10; `tax.correction.submit`) |
| 8a–8d | `tax-settlements` (GET, POST, `/{id}/post`, `/{id}/cancel`) | US-M10-01 (`vat_offset`), US-M10-04 (`turnover_tax`) |
| 9 | `GET /ledger-entries` | US-M11-01 |
| 10, 10a, 10b | `ledger-adjustments` guruhi | infratuzilma/admin (qo'lda buxgalteriya tuzatishi; qaror #58 b) |
| 11–13 | `trial-balance`, `profit-and-loss`, `balance-sheet` | US-M11-02, US-M15-03 |
| 14–16 | `period-closings` guruhi | US-M11-02 |
| 17 | `GET /reports/dashboard` | US-M12-01, US-M11-03 |
| 18 | `GET /reports/sales` | US-M12-01 |
| 19 | `GET /reports/top-products` | US-M12-02 |
| 20 | `GET /reports/stock` | US-M04-03, US-M14-01 |
| 21 | `GET /reports/debts-aging` | US-M08-10, US-M08-11 |
| 22–23 | `reports/{report-kod}/export`, `reports/export-jobs/{job_id}` | US-M12-03 |
| 24 | `GET /roles` | US-M13-01, US-M13-02, US-M13-03 |
| 25–26 | `POST /roles`, `PATCH /roles/{id}` (maxsus rol yaratish/tahrirlash) | infratuzilma/admin (US-M13-01/03 ga yordamchi; qaror #58 b) |
| 27–29 | `roles/{id}/permissions`, `permissions-catalog` | US-M13-03 |
| 29a–29b | `GET /devices`, `POST /devices/{id}/revoke` | US-M13-07 (BO-11 "Qurilmalar", qaror #56 a) |
| 30–33 | `branches` CRUD | US-M14-03 |
| 34–35 | `branches/{id}/tax-settings` | US-M14-04 |
| 36 | `POST /branches/{id}/copy-pricing` | US-M14-02 |
| 37 | `GET /warehouses` | US-M14-03 "?" |
| 37a | `PATCH /warehouses/{id}` | US-M14-03 (BO-12; `settings.branches`) |
| 38–40 | `cash-registers` CRUD (`fm_state`, soliq ro'yxati maydonlari) | US-M14-03; qolgani infratuzilma/admin (qaror #58 b) |
| 40i | `POST /cash-registers/{id}/archive` | US-M14-03 (BO-12; `cash_register.manage`) |
| 40a–40e | `tenant/settings`, `/tax-regimes`, `/integrations/*` | infratuzilma/admin (qaror #58 b); `weight_barcode_templates` — US-M01-07, US-M09-06 |
| 40f–40g | `GET /sync-exceptions`, `POST /sync-exceptions/{id}/review` | infratuzilma/admin — BO-14 "Sinxron istisnolari" (qaror #56 b) |
| 40h | `POST /tenant/consents` | US-M17-01 (qaror #61) |
| 41–47 | `expenses`, `expense-categories` | US-M15-01 |
| 48–51 | `recurring-expenses` | US-M15-02 |
| 52–54 | `cash-movements` | US-M16-01, US-M16-03 |
| 55 | `cash-registers/{id}/cash-history` | US-M16-03 |
| 56–58 | `billing/plan`, `/subscription`, `/addons` (GET) | US-M17-02 |
| 59–60 | `billing/addons` (POST qo'shish/kamaytirish) | US-M17-02 (umumiy); alohida — infratuzilma/admin (qaror #58 b) |
| 61–65 | `billing/checkout`, `/payments` (`kind='manual_extension'` ham, qaror #56 e), `/webhooks/*`, `/invoices/{id}` | US-M17-02 |
| 65a | `billing/export-my-data` | US-M17-05 |
| — | `/platform/*` (10 endpoint, to'liq ro'yxat 14 §18.1'da) | US-M17-04, US-M13-08 |
| 66–68 | `notifications/telegram/*` | US-M18-01 |
| 69–70 | `notification-settings` | US-M18-02, US-M18-03 |
| 71 | `GET /notifications-log` | infratuzilma/admin (qaror #58 b) |
| 72 | `POST /ai/chat` | US-M18-04 |
| 73–75 | `ai/ocr/jobs` | US-M04-04 |
| 76 | `ai/vat-diffs/{id}/explain` | US-M10-02 |
| 77–78 | `ai/debt-reminders/draft`\|`/send` | US-M08-03, US-M08-08 |
| 79 | `GET /ai/usage` | infratuzilma/admin (qaror #58 b) |
| — | scheduler `fetch_fx_rates` (endpoint yo'q, `platform.fx_rates`) | infratuzilma (qaror #55 a) |

#### 33-1c-integratsiya.md (§10 W-01…W-55, §9.3 A-01…A-10)

| Endpoint | US |
|---|---|
| W-01…W-05 (`onec-agents`, ulash/uzish) | US-M19-01, US-M19-17 |
| W-06, W-07, W-08 (bazalarni qidirish, diagnostika, loglar) | US-M19-02, US-M19-18 |
| W-09…W-15 (`onec-bases`, tekshiruvlar, reassign, archive) | US-M19-02, US-M19-17 |
| W-16…W-20 (`onec-branch-bindings`, `onec-settings`) | US-M19-03, US-M19-13 |
| W-21…W-29 (katalog keshi, moslashtirish, qiymatlar) | US-M19-04 |
| W-30…W-33 (`onec-ref-create-requests`) | US-M19-05 |
| W-34…W-42 (partiyalar, kalendar, preview, rebuild, istisno) | US-M19-06 |
| W-43, W-44 (approve, cancel) | US-M19-07, US-M19-08, US-M19-16 |
| W-45, W-46 (resend-failed, skip) | US-M19-09 |
| W-47, W-50, W-52, W-53 (accept, reconcile, reconciliations) | US-M19-10 |
| W-48 (new-revision) | US-M19-08, US-M19-11, US-M19-16 |
| W-49 (correction) | US-M19-12 |
| W-51 (events), W-54 (`onec-object-refs`) | US-M19-07, US-M19-18 |
| W-55 (`onec-status`) | US-M19-15 |
| A-01…A-10 (`/onec-agent/*`: hello, bases, poll, heartbeat, result, logs, diagnostics, task-keys, update-manifest, unpair) | US-M19-01, -02, -07, -08, -15, -17 (agent tomoni — `34-1c-agent.md`) |

#### Bank tushumi tasdig'i (`13-provodka-qoidalari.md` §2.18a)

| Endpoint | US |
|---|---|
| `GET/POST /bank-settlements`, `GET /bank-settlements/{id}`, `POST /{id}/post`, `POST /{id}/cancel` | US-M11-04 |
| `GET /bank-settlements/transit-balances` (20 #55b) | US-M11-04 (BO-24 tranzit qoldig'i) |
| `POST /bank-settlements/imports` (20 #55g) | US-M11-04 (ko'chirma importi → qoralamalar) |
| `PATCH /bank-settlements/{id}` (20 #55h) | US-M11-04 (BO-24 qoralamani tahrirlash; `bank_settlements.manage`) |

#### Do'kon agenti (qaror #60, `34-1c-agent.md`)

| Endpoint | US |
|---|---|
| Agent lokal API karta terminali (`127.0.0.1:47110/v1/card/*`, imkoniyat `card_terminal`, qaror #71) | US-M01-08; Bosqich 5 (MVP'da `FakeCardTerminalAdapter`, Bosqich 3) |
| Agent lokal API (`127.0.0.1`): fiskal ko'prik (POS → agent → FM → OFD), LAN 9100 printer, tarozi | US-M01-01 (fiskal chek), US-M01-07 (printer/tarozi); Bosqich 5 |
| Agent bulut API (`/onec-agent/*`, A-01, A-03…A-10; ulash W-01…W-05, W-07, W-08) | US-M01-01, US-M01-07 — agent infratuzilmasi Bosqich 5 (qaror #66); A-02 va 1C vazifalari — M19 (Bosqich 7) |

### 2c. Jadval → endpoints/US

Asos — `13-provodka-qoidalari.md` §2.25 "Posting qamrovi" jadvali (hujjat↔API post yo'li, so'zma-so'z) + qolgan (hujjat bo'lmagan) jadvallar uchun qo'shimcha xulosa.

| Jadval guruhi | Yozuvchi endpoint | US |
|---|---|---|
| `app.card_terminals` | `GET/POST /card-terminals`, `PATCH /card-terminals/{id}` (`cash_register.manage`, BO-12, POS-16); `health_status` — agent `card.status` vazifasi | US-M01-08 |
| `app.card_terminal_transactions` | `POST /card-terminal-transactions` (upsert), voqealar `sale.created` (`payments[].card_result`) / `return.created` (`refund_card.card_result`) / `debt_payment.created` (`card_result`) | US-M01-08, US-M02-01, US-M08-04 |
| `app.card_terminal_settlements` | `POST /card-terminal-settlements` (smena yopilishi; agent vazifasi `card.settlement`) | US-M01-08, US-M16-02 |
| `platform.card_bin_rules` | seed/ops (platforma ma'lumotnomasi; erp_app — faqat SELECT) | US-M01-08 |
| `app.sales`, `app.sale_lines`, `app.sale_payments` (`card_type`, `card_mask`, `rrn`, `card_entry_mode`, `card_terminal_transaction_id`, `qr_type`) | voqea `sale.created` | US-M01-01, US-M01-02, US-M01-03, US-M01-05, US-M01-08, US-M03-01, US-M08-01, US-M08-05, US-M10-01 |
| `app.returns`, `app.return_lines` | voqea `return.created` | US-M02-01, US-M02-03 |
| `app.goods_receipts`, `app.receipt_lines` | `POST /goods-receipts/{id}/post` | US-M04-01, US-M07-02, US-M07-03 |
| `app.transfers`, `app.transfer_lines` | `/send`, `/receive` | US-M06-01, US-M06-02, US-M06-03 |
| `app.stock_counts`, `app.count_lines` | `POST /stock-counts/{id}/post` | US-M05-01, US-M05-02, US-M05-03 |
| `app.write_offs`, `app.write_off_lines` | `POST /write-offs/{id}/post` | US-M04-06 |
| `app.debt_openings` | `POST /debt-openings/{id}/post` + import | US-M08-07 |
| `app.debt_payments` (`card_type`, `card_mask`, `rrn`, `qr_type`), `app.debt_payment_allocations` | voqea `debt_payment.created` + `/post` | US-M08-04 |
| `app.debt_writeoffs` (`tax_writeoff_basis`) | `POST /debt-writeoffs/{id}/post` | **— (gap: US yo'q, §3-E 1)** |
| `app.supplier_payments`, `app.supplier_payment_allocations` | `POST /supplier-payments` | US-M07-04 |
| `app.expenses` | `POST /expenses/{id}/post` + voqea `expense.created` | US-M15-01 |
| `app.cash_movements`, `app.cash_moves` | voqea `cash_movement.created` + `POST /cash-movements` | US-M16-01 |
| `app.shifts` (farq provodkasi) | voqea `shift.closed` | US-M01-04, US-M16-02 |
| `app.supplier_returns`, `app.supplier_return_lines` | `POST /supplier-returns/{id}/post` | US-M07-05 |
| `app.stock_openings`, `app.opening_lines` | `POST /stock-openings/{id}/post` + import | US-M04-04 |
| `app.einvoices` (`direction=out`) | `POST /einvoices`, `/from-receipt` (provodkasiz) | US-M01-06 |
| `app.ledger_adjustments` | `POST /ledger-adjustments` | **— (gap, maxsus US yo'q)** |
| `app.bank_settlements` | `POST /bank-settlements`, `POST /bank-settlements/imports`, `POST /bank-settlements/{id}/post`, `/cancel` | US-M11-04 |
| `app.tax_settlements` | `POST /tax-settlements`, `/{id}/post`, `/{id}/cancel` | US-M10-01, US-M10-04 |
| `app.sync_exceptions` | `POST /sync/push` (istisno yaratadi), `POST /sync-exceptions/{id}/review` | US-M01-02; ko'rib chiqish — infratuzilma/admin (qaror #56 b) |
| `platform.fx_rates` | scheduler `fetch_fx_rates` (ichki quvur) | infratuzilma (qaror #55 a) |
| `app.onec_agents`, `auth.onec_device_authorizations` | W-04, W-05, A-01, A-10 | US-M19-01, US-M19-17 |
| `app.onec_bases`, `app.onec_metadata_snapshots` | A-02, W-11, W-12, W-14, W-15 | US-M19-02, US-M19-17 |
| `app.onec_settings`, `app.onec_branch_bindings` | W-17, W-18, W-20 | US-M19-03, US-M19-13 |
| `app.onec_catalog_items`, `app.onec_mappings`, `app.onec_value_mappings` | W-21, W-25, W-26, W-27, W-29 | US-M19-04 |
| `app.onec_ref_create_requests` | W-31, W-32, W-33 | US-M19-05 |
| `app.onec_export_batches`, `app.onec_export_items`, `app.onec_export_item_sources` | W-36, W-41…W-49 | US-M19-06…-12, -16 |
| `app.onec_agent_tasks`, `app.onec_task_results`, `app.onec_object_refs` | A-03, A-04, A-05 (dispetcher) | US-M19-07, -08, -15 |
| `app.onec_reconciliations` | W-50, W-53, `onec_verify_batch`, `onec_drift_check` | US-M19-10, US-M19-18 |
| `app.onec_events`, `app.onec_agent_logs` | barcha `onec_*` o'tishlari (yon ta'sir), A-06 | US-M19-18 |
| `app.product_prices`, `app.price_changes`, `app.price_change_lines` | `POST /price-changes/{id}/post` | US-M09-01, US-M09-02 |
| `app.purchase_orders`, `app.po_lines` | `POST /purchase-orders` (registrga ta'sir yo'q) | US-M07-01 |
| `app.stock_moves`, `app.stock_lots`, `app.avg_costs`, `app.stock_balances` (registrlar) | yuqoridagi barcha ombor hujjatlarining `/post`'i orqali (bevosita yozuvchi endpoint yo'q, faqat `GET`) | US-M04-01…06, M05, M06, M07 |
| `app.debt_moves`, `app.debt_balances` (registr) | nasiya/to'lov hujjatlari `/post`'i orqali | M08 barcha |
| `app.cash_moves` (registr) | `cash_movement.created`, `shift.closed`, `debt_payment.created` (naqd qism) | US-M16-01, US-M16-02 |
| `app.ledger_entries` (registr) | barcha posting endpointlari orqali (umumiy) | M01, M02, M04–M08, M11, M15 |
| `app.vat_moves` (registr) | `sale.created`, `return.created`, `einvoices` (`accept`) orqali | US-M10-01, US-M02-03, US-M07-03 |
| `app.fiscal_receipts` (`fm_terminal_id`, `fm_receipt_seq`, `fiscal_at`, `ofd_acked_at`, `payment_form`, `delivery`) | `sale.created`, `return.created`, `debt_payment.created` ichida `FiscalPort` orqali avtomatik + `POST /{id}/retry` | US-M01-01, US-M02-01, US-M08-01, US-M08-04; retry — infratuzilma/admin (qaror #58 b) |
| `app.marking_codes` | `POST /marking-codes/verify`, `sale.created` ichida | US-M01-03 |
| `app.approval_requests`, `app.doc_approvals` | `POST /approval-requests`, `/approve`, `/reject` | US-M02-02, US-M03-01, US-M09-02 |
| `app.payment_checkouts` | `POST /payments/checkouts` | US-M01-05 |
| `app.discount_rules` | `discount-rules` CRUD | US-M03-02 |
| `app.counterparties`, `app.debt_doubtful_flags`, `app.counterparty_statement_links` | `counterparties` CRUD, `debt-doubtful-flags`, `statement-link` | US-M08-02, US-M08-05, US-M08-06; doubtful-flags — **gap (US yo'q)** |
| `app.products`, `app.product_categories`, `app.product_barcodes`, `app.internal_barcode_seq` | `products`/`product-categories` CRUD, `barcodes/internal-generate` | US-M09-05; umumiy CRUD — **gap (US yo'q)** |
| `app.label_print_queue` | `label-print-jobs`, `mark-printed` | US-M09-04 |
| `app.valuation_method_history` | `PATCH /valuation-settings` | US-M04-05 |
| `app.recost_jobs` | ichki quvur (valuation o'zgarishi, kech hujjat) + `POST /recost-jobs/{id}/retry` | infratuzilma/admin — BO-08 "Qayta hisoblash navbati" (qaror #56 c) |
| `app.import_jobs` | `POST /import-jobs` → `/validate` → `/commit` | US-M04-04, US-M08-07 |
| `app.state_reports`, `app.state_report_diffs` | `state-reports` guruhi | US-M10-02, US-M10-04 |
| `app.ettn_documents` | `POST /transfers/{id}/post` (chiquvchi "Ombordan omborga"), `/ettn-documents/{id}/submit-signed`\|`/register-manual`\|`/accept`\|`/reject`, `POST /einvoices/{id}/accept` (birlashtirilgan EHF+TTN) | US-M06-01, US-M06-02, US-M07-03 (qaror #63) |
| `app.period_closings` | `POST /period-closings` | US-M11-02 |
| `app.branches`, `app.warehouses`, `app.cash_registers`, `app.branch_tax_settings` | `branches`/`cash-registers` CRUD, `/tax-settings`; `cash_registers.fm_state`/`last_unacked_receipt_at`/`fm_receipts_pending` — `FiscalPort` holat sinxroni (ichki) | US-M14-03, US-M14-04; cash-registers CRUD va FM holati — infratuzilma/admin (qaror #58 b) |
| `app.roles`, `app.role_permissions` | `roles` CRUD, `roles/{id}/permissions` | US-M13-01, US-M13-03; rol yaratish/tahrirlash o'zi — infratuzilma/admin (qaror #58 b) |
| `app.users`, `app.memberships`, `app.devices` | `admin/users` guruhi, `POST /devices/{id}/revoke` | US-M13-01, US-M13-02, US-M13-04, US-M13-05, US-M13-07 |
| `auth.user_credentials`, `auth.otp_challenges`, `auth.sessions`, `auth.refresh_tokens`, `auth.authorization_codes`, `auth.login_attempts` | `/oauth/*`, `/auth/*` | infratuzilma (M13/M17 orqali bilvosita; qaror #58 b) |
| `app.tenants` (`legal_form`, `accepted_terms_*`, `settings.*`), `app.subscriptions`, `app.tenant_addons`, `app.billing_payments` (`kind`), `app.tenant_tax_regimes` | `POST /auth/signup`, `POST /tenant/consents`, `PATCH /tenant/settings`, `billing/*`, `tenant/tax-regimes`, platforma `extend-subscription` | US-M17-01, US-M17-02, US-M14-04 |
| `app.telegram_links`, `app.notification_settings`, `app.notifications_log` | `notifications/telegram/*`, `notification-settings` | US-M18-01, US-M18-02, US-M18-03 |
| `app.ai_requests`, `app.ai_ocr_jobs` | `ai/chat`, `ai/ocr/jobs`, `ai/debt-reminders/*` | US-M18-04, US-M04-04, US-M08-03/08 |
| `app.ai_training_samples`, `app.ai_feedback` | ichki AI quvuri (`22-ai-qatlami.md`; `12` izohi — qaror #58 b) | infratuzilma |
| `app.tenant_glossary` | ichki AI quvuri — maskalash xaritasi (qaror #61, #58 b) | infratuzilma |
| `app.audit_log` | barcha state-change endpointlari (yon ta'sir sifatida, `15-xavfsizlik-va-audit.md` §6) | hammasi |
| `app.outbox_jobs`, `app.sync_receipts`, `app.idempotency_keys`, `app.doc_sequences` | ko'plab endpointlar ichida ichki (OFD/e-faktura/marking retry, sync) | infratuzilma |
| `app.attachments` | `POST /attachments` (BO-04/BO-17/AI-03 oqimlarida) | US-M04-04, US-M07-03, US-M15-01 |
| `platform.label_templates` | seed (faqat `GET`; tenant o'zgartira olmaydi, 19 §5; qaror #58 b) | US-M09-04 |
| `platform.plans`, `platform.addons`, `platform.oauth_clients`, `platform.signing_keys`, `platform.platform_admins` | seed/migratsiya/ops (`12` izohi; `devices.kind`/`signing_keys.purpose` kengaytmasi — Bosqich 0, qaror #58 c) | infratuzilma |

**Qamrab olingan jadvallar**: barcha jadvallar yozuvchiga ega — endpoint/voqea (to'g'ridan-to'g'ri yoki registr sifatida), ichki quvur yoki seed/ops (qaror #58 b); yozuvchisiz jadval yo'q (`tax_settlements`, `sync_exceptions`, `platform.fx_rates` ham).

---

## 3. Bo'shliqlar ro'yxati

### A. US stories — MVP tier yo'q (05-mvp-chegarasi.md §1.1 jadvalida yo'q)

Bo'shliq yo'q — M01–M18 ning 87 ta US'i: 83 tasi `05-mvp-chegarasi.md` §1.1 jadvalida (62 Must, 19 Should, 2 Could), 4 tasi MVP'dan keyin (US-M03-02, US-M08-08, US-M14-02, US-M17-05 — §1.1 jadval ostidagi izoh, qaror #33); M19 ning 18 tasi — `Keyin` (Bosqich 7).

### B. US stories — Bosqich (27-backlog.md) hech qaerda yo'q

Bo'shliq yo'q (qaror #58 b, 26 #164 (OQ-099)): `27-backlog.md` har bosqichida aniq US-ID ro'yxati bor; jadval 1 ning "Bosqich" ustuni shu ro'yxat bilan bir xil. MVP'dan keyingi 4 ta US (US-M03-02, US-M08-08, US-M14-02, US-M17-05 — qaror #33) `27` ning "MVP'dan keyin" bo'limida.

### C. US stories — ekran yo'q

US-M03-03 (Could, lekin ekran umuman yo'q), US-M08-08, US-M14-02, US-M17-05 (uchalasi ham post-MVP, shuning uchun past ustuvorlik, lekin baribir ekran mavjud emas) — **4 ta**. **Tavsiya:** `07-ekran-tafsilotlari.md`ga margin-hisobot (US-M03-03) uchun BO-09 ichiga qo'shimcha blok, qolgan uchtasi uchun MVP'dan keyin bosqichida ekran loyihalash.

### D. Biznes jarayon (BP) qamrovi

**Bo'shliq emas (qaror #58 b):** `04-biznes-jarayonlar.md` boshida qayd etilgan — BP-01…15 faqat tranzaksion hujjat oqimlarini qamraydi; sozlama/hisobot/admin modullari (M09, M12, M13, M15, M16, M17, M18) va setup/hisobot stilidagi hikoyalar (US-M01-04, US-M01-07, US-M04-02/03/05/06, US-M07-05, US-M08-02/06/07/08/10, US-M11-03, US-M14-01…04) qasddan BP'siz. Jadval 1 dagi "— (gap)" BP qiymatlari shu ma'noda o'qiladi.

### E. Endpointlar — mos US yo'q

Qaror #58 b bo'yicha quyidagilar **infratuzilma/admin funksiyasi** deb belgilangan (alohida US talab qilinmaydi, §2b da shu belgi bilan): `GET /fiscal-receipts`, `/{id}/retry`; `POST /roles`, `PATCH /roles/{id}`; `tenant/settings`, `/tax-regimes`, `/integrations/*` (20 #40a–40e); `sync-exceptions` (20 #40f–40g, BO-14, qaror #56 b); `cash-registers` CRUD (20 #38–40); `billing/addons` (20 #59–60); `GET /notifications-log` (20 #71); `GET /ai/usage` (20 #79); `recost-jobs` (19 §18 — BO-08 "Qayta hisoblash navbati", qaror #56 c); `ledger-adjustments` (20 #10/10a/10b); `sale.draft_voided`, `receipt.reprinted` (audit); `products`/`product-categories`/`units` CRUD va yetkazib beruvchi directoryi (19 §1–3, §9 — master-data); scheduler `fetch_fx_rates` (qaror #55 a).

Mahsulot funksiyasi sifatida hali US'ga ega bo'lmaganlar (`03` egasiga taklif, MVP'ni bloklamaydi):
1. `POST /debt-writeoffs`→`/post` (`debts.forgive`, `13` §2.15) — "qarzni kechish".
2. `POST /debt-doubtful-flags`, `/unflag` — shubhali qarz belgisi (qaror #23 #9).

### F. Ekranlar — mos US yo'q

Yo'q — barcha 41 ekranning (39 MVP + BO-22, BO-23) har birida kamida bitta `Bog'liq US` bor (§2a tasdiqlangan). `UX-INSTALL` o'zi ataylab istisno qilingan.

### G. Jadvallar — hech qanday endpoint tomonidan yozilmaydi

Bo'shliq yo'q: `app.ettn_documents` — yozuvchi `POST /transfers/{id}/post` va `/ettn-documents/*` (qaror #63). Qolganlari `12-db-sxema.md` izohi bilan "seed/ops/ichki quvur yozadi" deb belgilangan (qaror #58 b): `app.ai_training_samples`, `app.ai_feedback`, `app.tenant_glossary` (ichki AI quvuri, qaror #61), `platform.fx_rates` (scheduler, qaror #55), `platform.label_templates` (seed, faqat `GET`), `platform.plans`, `platform.addons`, `platform.oauth_clients`, `platform.signing_keys`, `platform.platform_admins` (seed/migratsiya/ops). Yozuvchisiz jadval qolmagan.

### H. Ruxsat kodlari — endpoint tomonidan ishlatiladi, lekin 15-katalogda yo'q / aksincha

Tekshiruv (`15-xavfsizlik-va-audit.md` §2.1, 66 qator — 68 ta kod: `shift.open`/`shift.close` va `cash.deposit`/`cash.withdraw` bittadan qatorda) va 18/19/20'dagi barcha `Ruxsat`/backtick-kod mentionlari solishtirildi — **nomuvofiqlik topilmadi**: 18 va 19'da ishlatilgan barcha ruxsat kodlari (`sales.*`, `returns.*`, `discount.*`, `stock.*`, `transfer.*`, `purchases.*`, `debts.*`, `prices.*`, `tax.*`, `catalog.manage`, `stock.opening.manage`, `valuation.settings.manage`, `labels.print`, `card.manual_entry.approve`, `cash_register.manage`) 15-katalogda bor; 20'dagi barcha `Ruxsat` ustuni qiymatlari (`accounting.*`, `reports.*`, `settings.*`, `expenses.*`, `cash.*`, `billing.manage`, `notifications.manage`, `telegram.link`, `ai.*`, `platform.admin`) ham bor. **Hech qanday gap yo'q bu bo'limda** — ijobiy natija, alohida ta'kidlanadi.

### H2. 1C integratsiyasi, bank tushumi va yangi qarorlar — izchillik tekshiruvi

M19 ning 18 ta US'i BO-22/BO-23 ning «Bog'liq US» qatorlari (`33` §13), W-xx endpointlari (`33` §10), `onec_*` jadvallari (`33` §5), `onec.*` ruxsatlari (`15` §2.1 = `33` §11.1) va Bosqich 7 (`27`) bilan to'liq bog'langan. US-M11-04 → BP-15 → BO-24 → `/bank-settlements` (+ `/transit-balances`, `/imports`) → `app.bank_settlements` → `bank_settlements.manage` → Bosqich 4 zanjiri to'liq. Qarorlar #43–#71 zanjirlari: 48 soat blok (#43) — US-M01-01 → `18` §4.6 → `fiscal_receipts.ofd_acked_at` → `FISCAL_OFFLINE_48H_BLOCKED`; karta rekvizitlari (#64) — US-M01-01/M08-04 → `sale_payments`/`debt_payments`; markirovka (#62) — US-M01-03 → `FiscalPort`; E-TTN (#63) — US-M06-01/02 → `ettn_documents`; QQS/aylanma hisob-kitobi — US-M10-01/04 → `tax_settlements` → `13` §2.26/§4.3; rozilik (#61) — US-M17-01 → `tenants.accepted_terms_*`, `/tenant/consents`; Do'kon agenti (#60, #66) — US-M01-01/07 → agent lokal API va A-API, `onec_agents`/`onec_agent_tasks`, `cash_registers.fiscal_agent_id` (Bosqich 5); qarz to'lovi cheki (#67) — US-M08-04 → `debt_payment.created` (POS-13) / `POST /debt-payments` `method='bank'` (BO-06) → `debt_payments.receipt_seq`/`unallocated_amount`, `sale_lines.settled_amount`; POS fiskal natija (#68) — US-M01-01 → `sale.created.fiscal_result` → `fiscal_receipts.ofd_acked_at`; kech POS voqealari (#69) — US-M11-02 → `GET /period-closings/{period}/readiness` (`devices_unsynced`) → `analytics.correction_of_period`; obuna to'lovi (#70) — US-M17-02/03 → `POST /billing/checkout` → `billing_payments.amount_breakdown`; integratsiyalangan karta terminali (#71) — US-M01-08 → BP-05 karta oqimi → POS-03/POS-16/BO-12 → agent `/v1/card/*` va `POST /card-terminal-transactions` → `card_terminals`/`card_terminal_transactions`/`card_terminal_settlements`, `sale_payments.card_entry_mode` → `card.manual_entry.approve`, `cash_register.manage` → Bosqich 3/5. Bo'shliq yo'q.

### I. MVP Must stories — hech qaysi backlog bosqichida yo'q

Tekshirildi: barcha "Must" tegidagi US (05'da ro'yxatlangan 62 ta) `27-backlog.md` 1–6 bosqichlarining US-ID ro'yxatlarida aniq ID bilan bor. Bo'shliq yo'q.

---

## Yakuniy hisob

- **US stories:** 105/105 jadvalga kiritilgan (M01 — 8, US-M01-07 printer/tarozi sozlamasi, US-M01-08 integratsiyalangan karta terminali; M19 — 18 ta, Bosqich 7; US-M11-04 — bank tushumi tasdig'i).
- **Ekranlar:** 41 (POS-01…16, BO-01…24, ADM-01; 39 tasi MVP, BO-22/BO-23 — Bosqich 7) + yordamchi route `/install` — 41 ekranning barchasi kamida bitta US'ga bog'langan.
- **Endpointlar:** `14` (29), `18` (46, index qatorlari), `19` (102, bo'lim bo'yicha, `ettn-documents` va `powers-of-attorney` bilan), `20` (107 raqamli index qatori: `state-reports/{id}/confirm` 7a, `tax-settlements` 8a–8d, `devices` 29a–29b, `warehouses/{id}` 37a, `sync-exceptions` 40f–40g, `tenant/consents` 40h, `cash-registers/{id}/archive` 40i, `bank-settlements` 55a–55h; + `/platform/*` 10) — hammasi §2b'da US yoki "infratuzilma/admin" belgisi bilan; qo'shimcha `33` (W-01…W-55, A-01…A-10) va Do'kon agenti lokal API.
- **Jadvallar:** barchasi yozuvchiga ega (endpoint/voqea, ichki quvur yoki seed/ops — §2c).
- **Ruxsat kodlari:** 15 §2.1 katalogi (66 qator, 68 ta kod; `onec.*` 7 ta, `bank_settlements.manage`, `cash_register.manage`, `card.manual_entry.approve`, `devices.revoke` bilan) — nomuvofiqlik topilmadi.
- **1C jadvallari:** 18 ta `app.onec_*` + `auth.onec_device_authorizations` — barchasi W/A endpointlari yoki `onec_*` job'lari orqali yoziladi (§2c).
- **Sinxron voqea turlari:** `16-offline-sync.md` §2 ro'yxati — barchasi §1 va §2b'da US/endpoint bilan bog'langan.

**Bo'shliqlar soni turlar bo'yicha:** A) MVP tier yo'q — 0; B) Bosqich yo'q — 0; C) Ekran yo'q — 4 (US-M03-03; post-MVP US-M08-08, US-M14-02, US-M17-05); D) BP qamrovi — bo'shliq emas (qaror #58 b); E) Endpoint→US yo'q — 2 mahsulot funksiyasi (qarzni kechish, shubhali qarz belgisi), qolganlari infratuzilma/admin; F) Ekran→US yo'q — 0; G) Jadval→yozuvchi yo'q — 0; H) Ruxsat kod nomuvofiqligi — 0; I) Must→bosqich yo'q — 0.
