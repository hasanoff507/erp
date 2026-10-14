# Ma'lumotlar modeli

*2026-10-14 · Asos: `spec/01-mahsulot/02-modullar-talablari.md` (M01–M18), `03-biznes-jarayonlar.md` (BP-01…12), `research_notes/texnik/01-erp-modullar-va-malumot-modeli.md` (hujjat → o'tkazma → registr), `04-arxitektura-va-stack.md`.*

## Asosiy xulosalar

1. **Uch qatlam**: (a) **ma'lumotnomalar** (tovarlar, mijozlar, filiallar…) — tahrirlanadi, o'chirilmaydi (arxivlanadi); (b) **hujjatlar** (chek, kirim, qaytarish, qarz, xarajat…) — o'tkazilgandan keyin **o'zgarmaydi**, faqat teskari hujjat bilan bekor qilinadi; (c) **registrlar** (qoldiq, partiyalar, qarz, kassa, buxgalteriya) — faqat hujjat o'tkazilganda yoziladigan **append-only harakatlar** + ulardan hisoblangan balanslar.
2. Har jadvalda `tenant_id` (RLS); filialga tegishli jadvallarda `branch_id`. Kalitlar — **UUIDv7** (vaqt bo'yicha tartiblangan, offline qurilmada ham yaratiladi — kassa serverni kutmasdan ID beradi).
3. Pul — `NUMERIC(18,2)` (so'm, tiyin bilan), miqdor — `NUMERIC(18,3)` (kg/l uchun), narx/tannarx — `NUMERIC(18,4)`. Float ishlatilmaydi.
4. Hujjat o'tkazish (posting) **bitta DB tranzaksiya**: hujjat holati + barcha registr harakatlari + buxgalteriya provodkasi birga yoziladi yoki birga bekor bo'ladi.
5. Tannarx uchun kirimlar har doim **partiya** (`stock_lots`) sifatida saqlanadi — FIFO ham, AVECO ham shu ma'lumotdan hisoblanadi (US-M04-05).
6. Offline'da yaratilgan har hujjatda `client_event_id` (qurilma generatsiya qilgan UUID) — server uni ikkinchi marta qabul qilmaydi (idempotentlik).
7. Hujjat raqamlari tenant + filial + hujjat turi + yil bo'yicha ketma-ket; fiskal chek raqami — kassa + smena ichida ketma-ket (OFD talabi).

---

## 1. Umumiy qoidalar

| Qoida | Tafsilot |
|---|---|
| Kalit | `id UUID` (v7). Offline qurilma o'zi yaratadi |
| Majburiy ustunlar | `tenant_id`, `created_at`, `created_by`, `updated_at`; hujjatlarda yana `branch_id`, `number`, `doc_date`, `status`, `posted_at`, `reversed_by_id`, `client_event_id`, `device_id` |
| O'chirish | Ma'lumotnomalar: `archived_at` (soft). Hujjatlar: hech qachon — `status=cancelled` + teskari hujjat. Registrlar: hech qachon |
| Vaqt | `TIMESTAMPTZ`, UTC saqlanadi; UI'da Toshkent vaqti (UTC+5). Hisob sanasi — `doc_date DATE` (Toshkent bo'yicha) |
| Matn | Nomlar lotin/kirill/rus aralash bo'lishi mumkin; qidiruv uchun `pg_trgm` indeks |
| Tenant izolyatsiyasi | Har jadvalda RLS siyosati: `tenant_id = current_setting('app.tenant_id')` (`05-xavfsizlik-va-audit.md`) |
| Versiya | Ma'lumotnomalarda `version INT` — optimistik qulflash (ikki kishi bir vaqtda tahrirlasa) |

## 2. Platforma (M17)

| Jadval | Asosiy maydonlar | Izoh |
|---|---|---|
| `tenants` | id, name, activity_type, stir (null), phone, status (`trial`/`active`/`grace`/`restricted`/`closed`), trial_ends_at, settings JSONB | Bitta do'kon/kompaniya |
| `plans` | id, code (`start`/`biznes`/`pro`), price_month, price_year, limits JSONB (`max_registers`, `max_branches`, `ai_monthly_tokens`, …) | Tariflar (`06-mvp-chegarasi.md` 3.3) |
| `subscriptions` | tenant_id, plan_id, period (`month`/`year`), current_period_end, status | Holat mashinasi 8-bo'limda |
| `billing_payments` | tenant_id, amount, provider (`click`/`payme`), provider_tx_id (unique), status, paid_at | Bizning daromad; webhook idempotent |
| `platform_admins` | id, email, role | Ichki admin (ADM-01), tenantlarga RLS'siz kiradi — faqat audit bilan |

## 3. Tashkilot, foydalanuvchilar, huquqlar (M13, M14)

| Jadval | Asosiy maydonlar | Izoh |
|---|---|---|
| `branches` | tenant_id, name, address, is_default | Filial (M14) |
| `warehouses` | tenant_id, branch_id, name, type (`store`/`stock`) | MVP: har filialda 1 ta ombor (avtomatik) |
| `cash_registers` | tenant_id, branch_id, name, kind (`web`/`android`), fiscal_module_id, ofd_status | Kassa (virtual kassa ID shu yerda) |
| `devices` | tenant_id, cash_register_id, kind, last_seen_at, last_sync_at, app_version | Offline sync uchun |
| `users` | id, phone (unique global), name, password_hash/pin_hash, locale | Bir odam bir nechta tenantda ishlashi mumkin |
| `memberships` | tenant_id, user_id, role_ids[], branch_ids[] (bo'sh = hammasi), status | Kim qaysi do'konda, qaysi filialda |
| `roles` | tenant_id, name, is_system (`owner`/`manager`/`cashier`/`storekeeper`/`accountant`) | Standart 5 rol + o'zinikini yaratish |
| `role_permissions` | role_id, permission_code, limit_value (null) | Masalan `discount.give` limit 10%, `cash.withdraw` limit 500 000 |
| `permissions` (kod ichida, jadval emas) | `sales.create`, `returns.approve`, `debts.forgive`, `prices.edit`, … | Ro'yxat `05-xavfsizlik-va-audit.md` da |

## 4. Katalog va narxlar (M09)

| Jadval | Asosiy maydonlar | Izoh |
|---|---|---|
| `product_categories` | tenant_id, parent_id, name | Daraxt |
| `units` | code (`pcs`, `kg`, `l`, `m`, `box`), is_fractional | Global ro'yxat |
| `products` | tenant_id, name, category_id, unit_code, mxik_code (17 belgi), package_code, vat_rate (12 / 0 / imtiyoz kodi), is_marked (Asl belgisi), is_weighed, min_stock, archived_at, version | MXIK — chekning majburiy rekviziti |
| `product_barcodes` | tenant_id, product_id, barcode (unique per tenant), kind (`ean`/`internal`/`weighed_prefix`), units_per_barcode | Bir tovarga bir nechta kod (dona/quti) |
| `product_prices` | tenant_id, product_id, branch_id (null = hamma), price, valid_from, set_by, price_change_doc_id | Tarix saqlanadi (US-M09-01) |
| `label_print_queue` | tenant_id, product_id, reason (`price_changed`/`new`), printed_at | US-M09-04 |
| `internal_barcode_seq` | tenant_id, next_value | Ichki kodlar diapazoni (masalan `2000000…`) — tashqi EAN bilan to'qnashmaydi |

## 5. Kontragentlar (M07, M08)

| Jadval | Asosiy maydonlar | Izoh |
|---|---|---|
| `counterparties` | tenant_id, kind (`person`/`company`), name, phone, stir (yuridik), is_customer, is_supplier, credit_limit (null = limitsiz), notify_consent (bool + sana), telegram_chat_id, note | Mijoz ham, yetkazib beruvchi ham bitta jadvalda |

## 6. Hujjatlar

Barcha hujjatlarda umumiy sarlavha: `id, tenant_id, branch_id, number, doc_date, status, author_id, posted_at, cancelled_at, reversal_of_id, client_event_id (unique per tenant), device_id, comment`.

| Hujjat (jadval) | Qatorlar | Modul | Nimani o'zgartiradi (registrlar) |
|---|---|---|---|
| `shifts` | — | M01, M16 | ochilish/yopilish, boshlang'ich va sanalgan naqd |
| `sales` (chek) | `sale_lines` (product, qty, price, discount, vat_rate, vat_amount, marking_code, lot allocations), `sale_payments` (method: `cash`/`card`/`click`/`payme`/`uzum`/`debt`, amount, provider_tx_id) | M01, M03, M08 | qoldiq −, tannarx, kassa naqd +, qarz + (nasiya), QQS, buxgalteriya |
| `returns` | `return_lines` (sale_line_id, qty) | M02 | qoldiq +, kassa −/qarz −, QQS −, buxgalteriya |
| `purchase_orders` | `po_lines` | M07 | — (rejalashtirish, registrga ta'sir yo'q) |
| `goods_receipts` (kirim) | `receipt_lines` (product, qty, cost, vat) | M07 | yangi partiya (lot), qoldiq +, yetkazib beruvchiga qarz + (nasiya bo'lsa), kirish QQS |
| `transfers` | `transfer_lines` | M06 | jo'natuvchi qoldiq −, yo'lda; qabul qiluvchi qoldiq + (tannarx partiya bilan ko'chadi) |
| `stock_counts` (inventarizatsiya) | `count_lines` (expected, counted) | M05 | farq bo'yicha qoldiq ±, kamomad xarajat / ortiqcha daromad |
| `write_offs` (hisobdan chiqarish) | `write_off_lines` | M04, M05 | qoldiq −, xarajat |
| `price_changes` | `price_change_lines` | M09 | `product_prices`, yorliq navbati |
| `debt_openings` (boshlang'ich qarz) | — (counterparty, amount, direction) | M08 | qarz registri (chek yo'q, US-M08-07) |
| `debt_payments` (qarz to'lovi) | `allocations` (qaysi qarzni yopdi) | M08 | qarz −, kassa/bank + |
| `debt_writeoffs` (kechish) | — | M08 | qarz −, xarajat (shubhali qarz), faqat Egasi |
| `supplier_payments` | `allocations` | M07, M08 | yetkazib beruvchiga qarz −, kassa/bank − |
| `expenses` | — (category_id, amount, source: `cash`/`bank`/`card`, attachment_id, recurring_rule_id) | M15 | kassa/bank −, xarajat |
| `cash_movements` (kassa pul harakati) | — (direction `in`/`out`, reason, expense_id) | M16 | kassa naqd ± |

Qo'shimcha: `expense_categories`, `recurring_expenses` (rule: summa, kun, davr), `attachments` (S3 kaliti, turi, hajmi).

## 7. Registrlar (append-only)

| Registr | Maydonlar | Balans qanday olinadi |
|---|---|---|
| `stock_moves` | tenant_id, warehouse_id, product_id, lot_id, qty (±), cost_amount (±), doc_type, doc_id, line_id, moved_at | `stock_balances` (warehouse, product) — trigger/ilova tomonidan yangilanadigan jamlama jadval; tekshirish uchun `SUM(stock_moves)` |
| `stock_lots` (partiyalar) | tenant_id, warehouse_id, product_id, receipt_line_id, received_at, qty_in, qty_left, unit_cost, expiry_date | FIFO: `qty_left > 0` eng eskisidan; AVECO: `avg_costs` jadvali (warehouse, product, avg_cost, qty) har kirimda qayta hisoblanadi |
| `debt_moves` | tenant_id, counterparty_id, direction (`receivable` — bizga qarz / `payable` — bizning qarz), amount (±), due_date, doc_type, doc_id | `debt_balances` (counterparty, direction); qarz daftari = shu harakatlar ro'yxati |
| `cash_moves` | tenant_id, cash_register_id (yoki `bank_account_id`), shift_id, amount (±), method, doc_type, doc_id | Kutilgan naqd = smena bo'yicha `SUM` (US-M16-02) |
| `ledger_entries` (buxgalteriya) | tenant_id, entry_date, account_dt, account_kt, amount, doc_type, doc_id, analytics JSONB (product, counterparty, branch) | Aylanma va qoldiq vedomosti; hisob raqamlari `02-provodka-qoidalari.md` |
| `vat_moves` | tenant_id, period (oy), kind (`output`/`input`), base_amount, vat_amount, doc_type, doc_id, einvoice_id | QQS ichki hisob (M10) va davlat hisoboti bilan solishtirish |

**Tannarx hisoblash** (`stock_lots` + `tenants.settings.valuation_method`):
- Sotuv/chiqim o'tkazilganda: FIFO — eski partiyalardan `qty_left` kamaytiriladi, `sale_lines.lot_allocations` ga yoziladi; AVECO — joriy `avg_cost` olinadi (partiyalar ham FIFO tartibida kamaytiriladi — kelajakda usul almashtirish uchun).
- **O'tgan sanali hujjat** kelganda (kech sinxron, kech kirim): shu sana va keyingi chiqimlar uchun tannarx **qayta hisoblash ishi** navbatga qo'yiladi (`recost_jobs`: tenant, warehouse, product, from_date). Yopilgan davr (`period_closings`) ga tegsa — rad etiladi.
- Manfiy qoldiqda sotuv (offline to'qnashuv): `stock_lots` dan yetmagan qism `pending_cost` sifatida oxirgi ma'lum narxda yoziladi va keyingi kirimda qayta hisoblanadi.

## 8. Holat mashinalari

| Obyekt | Holatlar |
|---|---|
| Chek (`sales`) | `draft` (faqat qurilmada) → `completed` (o'tkazilgan) → fiskal: `fiscal_pending` → `fiscalized` / `fiscal_failed` (qayta urinish); qaytarilganda `returned_partial` / `returned_full` |
| Kirim (`goods_receipts`) | `draft` → `posted` → (`cancelled` — teskari hujjat bilan) |
| Ko'chirish | `draft` → `sent` (jo'natuvchida chiqim) → `received` (qabul qiluvchida kirim) / `discrepancy` (farq bilan qabul) |
| Inventarizatsiya | `counting` → `review` → `posted` |
| Smena | `open` → `closing` (naqd sanalmoqda) → `closed` (Z-hisobot) |
| E-faktura | `draft` → `signed` → `sent` → `accepted` / `rejected` / `cancelled`; xavf belgisi `green`/`red` (VM 830) |
| Davlat hisoboti (`state_reports`) | `uploaded` → `compared` → `match` / `diff_found` → `correction_sent` / `auto_accepted` (5 kalendar kun o'tdi) |
| Obuna | `trial` → `active` → `grace` (**24 soat**, eslatmalar: −3 kun, −1 kun, to'lov kuni, 0 / 12 / 2 soat qolganda) → `restricted` (kassa ishlaydi) → `active` (to'lov) / `closed` |
| Integratsiya ishi (`outbox_jobs`) | `queued` → `running` → `done` / `retry` (backoff) → `failed` (qo'lda ko'rish) |

## 9. Fiskal, markirovka, e-hujjatlar, davlat hisoboti

| Jadval | Asosiy maydonlar |
|---|---|
| `fiscal_receipts` | sale_id/return_id, cash_register_id, shift_id, receipt_seq (smena ichida ketma-ket), payload JSONB, fiscal_sign, qr_url, sent_at, offline_since, status, attempts |
| `marking_codes` | tenant_id, code (DataMatrix), product_id, status (`in_stock`/`sold`/`returned`/`written_off`), last_doc_id, verified_at | 
| `einvoices` | tenant_id, direction (`in`/`out`), operator (`didox`/`faktura`), operator_doc_id, counterparty_id, related_doc (receipt/sale), status, risk_flag, signed_at, payload |
| `ettn_documents` | tenant_id, einvoice_id, status, operator_doc_id | 
| `state_reports` | tenant_id, tax_type (`vat`/`turnover`/`property`/`land`/`pit`/`social`), period, published_at, deadline_at (= min(published_at + 5 kalendar kun, filing deadline)), file_attachment_id, status |
| `state_report_diffs` | state_report_id, indicator, state_value, our_value, diff, explanation (AI-05), resolved |

## 10. Integratsiya navbati, sync, bildirishnoma, AI, audit

| Jadval | Asosiy maydonlar | Hujjat |
|---|---|---|
| `outbox_jobs` | tenant_id, kind (`ofd_send`, `einvoice_send`, `marking_sell`, `sms`, `telegram`, `ai`), payload, status, attempts, next_run_at, last_error, idempotency_key | `03-integratsiyalar.md` |
| `sync_receipts` | tenant_id, device_id, client_event_id (unique), received_at, result | `04-offline-sync.md` |
| `telegram_links` | tenant_id, user_id, chat_id, linked_at | M18 |
| `notification_settings` | tenant_id, user_id, kind, enabled, time | M18 |
| `notifications_log` | tenant_id, channel (`telegram`/`sms`), recipient, template, status, cost | M08, M18 |
| `ai_requests` | tenant_id, user_id, feature (`AI-01`…), model, prompt_version, input_tokens, output_tokens, cache_read_tokens, cost_usd, fx_rate_used, cost_uzs, latency_ms, guard_result, status | `07-ai-qatlami.md` |
| `ai_training_samples` (keyin) | tenant_id (anonimlashtirilgandan keyin olib tashlanadi), feature, input_redacted, output_corrected, consent_ref, created_at | Faqat rozilik bilan, kelajakdagi o'qitish uchun (`07-ai-qatlami.md`) |
| `ai_feedback` | ai_request_id, rating, correction (foydalanuvchi tuzatgan qiymat), consent_for_training | Kelajakdagi o'qitish uchun (rozilik bilan) |
| `tenant_glossary` | tenant_id, term, meaning ("kola" → mahsulot) | AI uchun do'kon "xotirasi" |
| `audit_log` | tenant_id, user_id, action, entity, entity_id, before JSONB, after JSONB, ip, device_id, at | `05-xavfsizlik-va-audit.md` |
| `period_closings` | tenant_id, period, closed_at, closed_by | Yopilgan davrga yozish taqiqlanadi |

## 11. Raqamlash

| Nima | Format | Qayerda yaratiladi |
|---|---|---|
| Hujjat raqami | `{tur}-{filial kodi}-{yil}-{ketma-ket}` masalan `K-01-2026-000154` | Serverda (`doc_sequences`: tenant, branch, type, year → next). Offline hujjatga vaqtincha raqam: `{qurilma}-{lokal ketma-ket}`, sinxronda doimiy raqam beriladi, vaqtinchalik raqam saqlanadi |
| Fiskal chek raqami | Kassa + smena ichida ketma-ket | Qurilmada (offline ham), OFD talabi (`research_notes/texnik/04-arxitektura-va-stack.md`, 2.2) |
| Ichki shtrix-kod | `2` + tenant ichidagi ketma-ket + EAN-13 nazorat raqami (taxmin — tarozi og'irlik kodlari bilan diapazon ajratiladi) | Serverda |

## 12. ER diagramma (soddalashtirilgan)

```mermaid
erDiagram
  TENANT ||--o{ BRANCH : has
  TENANT ||--o{ MEMBERSHIP : has
  USER ||--o{ MEMBERSHIP : in
  BRANCH ||--o{ WAREHOUSE : has
  BRANCH ||--o{ CASH_REGISTER : has
  CASH_REGISTER ||--o{ SHIFT : opens
  SHIFT ||--o{ SALE : contains
  SALE ||--|{ SALE_LINE : has
  SALE ||--|{ SALE_PAYMENT : paid_by
  SALE ||--o| FISCAL_RECEIPT : fiscalized_as
  PRODUCT ||--o{ SALE_LINE : sold
  PRODUCT ||--o{ PRODUCT_BARCODE : has
  PRODUCT ||--o{ STOCK_LOT : stocked_in
  GOODS_RECEIPT ||--|{ RECEIPT_LINE : has
  RECEIPT_LINE ||--|| STOCK_LOT : creates
  COUNTERPARTY ||--o{ SALE : buys
  COUNTERPARTY ||--o{ DEBT_MOVE : owes
  SALE ||--o{ DEBT_MOVE : creates
  DEBT_PAYMENT ||--o{ DEBT_MOVE : closes
  SALE ||--o{ STOCK_MOVE : moves
  SALE ||--o{ LEDGER_ENTRY : posts
  SALE ||--o{ CASH_MOVE : moves
  EXPENSE ||--o{ LEDGER_ENTRY : posts
  STATE_REPORT ||--o{ STATE_REPORT_DIFF : has
```

## Ochiq savollar

1. Bitta chekda bir nechta QQS stavkasi (12% va 0%/imtiyozli tovar) — chek va e-faktura formatida qanday ko'rsatiladi — OFD hujjatlari bilan tekshiriladi.
2. Kassa pul harakatini (M16) OFD'ga yuborish kerakmi — ochiq (M16).
3. Tarozi og'irlik shtrix-kodi formati (prefiks, og'irlik/narx joylashuvi) — pilot tarozilarida aniqlanadi.
4. Ko'p ombor bitta filialda (masalan alohida sklad) — MVP'da bitta, model esa bir nechtasini qo'llaydi.
5. `stock_balances` ni trigger bilanmi yoki ilova kodida yangilash — `09-backend-arxitekturasi.md` da qaror (taklif: ilova kodida, posting xizmati ichida, bitta tranzaksiyada).

## Manbalar

- `spec/01-mahsulot/02-modullar-talablari.md` — M01–M18, US-M04-05 (partiyalar, qayta hisoblash), US-M08-05…11 (qarz daftari).
- `spec/01-mahsulot/03-biznes-jarayonlar.md` — BP-01…12 (hujjat oqimlari va buxgalteriya ta'siri).
- `research_notes/texnik/01-erp-modullar-va-malumot-modeli.md` — hujjat/registr modeli, MXIK, BHMS-4, NSBU 21.
- `research_notes/texnik/02-kassa-ofd-markirovka.md` — fiskal chek rekvizitlari, 48 soat, markirovka.
- `research_notes/texnik/04-arxitektura-va-stack.md` — multi-tenant RLS, event-log, fiskal ketma-ketlik.
