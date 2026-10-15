# Qabul-6 — API katalogi (13-0…13-3) ↔ DB sxema (14) ↔ ma'lumotlar modeli (01) muvofiqligi

*2026-10-15 · Qabul agenti (Opus). Tekshirilgan: `13-api-katalog-0-umumiy.md`, `13-api-katalog-1-kassa.md`, `13-api-katalog-2-ombor.md`, `13-api-katalog-3-moliya-admin.md`, `14-db-sxema.md` (99 `CREATE TABLE`), `01-malumotlar-modeli.md`, `02-provodka-qoidalari.md`, `04-offline-sync.md`, `05-xavfsizlik-va-audit.md` §2.1–2.3, `09-backend-arxitekturasi.md` §3, `12-autentifikatsiya-oauth2.md` §16/§20, `tekshiruv/00-qarorlar.md`. Bu fayl faqat **o'zgarish ko'rsatmalari**; manba fayllar tahrirlanmagan.*

**Daraja**: **KRITIK** — shu holicha amalga oshirib bo'lmaydi yoki noto'g'ri pul/soliq natijasi beradi; **YUQORI** — ikki hujjat ziddiyati, implementator o'zi taxmin qilishga majbur; **O'RTA** — yetishmayotgan ustun/endpoint, aniqlik yo'q; **PAST** — nom/uslub/kosmetika.

## Asosiy xulosalar

1. **Eng og'ir 8 ta muammo (KRITIK; 8-si — chiquvchi e-faktura API'si yo'qligi, 3-band)**: (a) `sale.created`/`return.created` payload'ida **`receipt_seq` yo'q**, server esa uni javobda "beradi" — #12 qarorga (qurilma beradi) zid; (b) Z-hisobot `fiscal_receipts`ga yozilishi kerak, lekin DDL `CHECK (sale_id IS NOT NULL OR return_id IS NOT NULL)` buni taqiqlaydi; (c) `returns` jadvalida `shift_id`/`cash_register_id`/`refund_method` yo'q — qaytarishning kassa harakati va fiskal cheki yozib bo'lmaydi; (d) `debt_payments.method` faqat `cash`/`bank`, API esa `card`/`uzqr`/`click`/`payme`/`uzum` yuboradi; (e) `app.next_doc_number()` `p_branch_code` talab qiladi, `branches`da `code` ustuni **yo'q**; (f) qo'lda buxgalteriya tuzatishi (`POST /ledger-entries/adjustments`) uchun hujjat jadvali yo'q — `ledger_entries.doc_id NOT NULL` hech narsaga ishora qilmaydi; (g) obuna lokautida faqat `/billing/pay` ochiq — `POST /billing/checkout` bloklanadi, ya'ni lokautdagi tenant **to'lov qila olmaydi**.
2. **Takrorlangan/zid dizaynlar** (YUQORI): AI-03 OCR ikki marta (`/purchase-ocr-drafts` 13-2 vs `/ai/ocr/jobs` 13-3) → **`ai_ocr_jobs` + `/ai/ocr/jobs`** ga birlashtirildi; narx o'zgarishi tasdig'i ikki xil (`/price-changes/{id}/approve` 13-2 vs `/approval-requests/{id}/approve` 13-1) → **yagona `approval-requests`**; kontragent ikki resurs (`/counterparties` vs `/suppliers`) → **yagona `/counterparties`**; qarz eskirish hisoboti ikki yo'l (`/reports/debt-aging` vs `/reports/debts-aging`) → **`/reports/debts-aging`**; kassa pul harakati ikki faylda turli ruxsat bilan; webhook yo'li ikki xil (`/webhooks/{p}` vs `/payments/webhooks/{p}`).
3. **Chiquvchi e-faktura API umuman yo'q** (BP-03 B2B, BP-13/qaror #18) — 13-2 "sotuv katalogida" deydi, 13-1 da yo'q; katalogdagi `EINVOICE_ALREADY_LINKED`/`EINVOICE_AMOUNT_EXCEEDS_RECEIPT`/`EINVOICE_COUNTERPARTY_INCOMPLETE` kodlari hech qayerda ishlatilmaydi. Shuningdek `GET /sales`, `POST /attachments` aniqlanmagan.
4. **Ma'lumotlar modeli qo'shimchalari** (3 katalog + qabul topilmalari): 9 yangi jadval (`approval_requests`, `doc_approvals`, `payment_checkouts`, `ai_ocr_jobs`, `ledger_adjustments`, `counterparty_statement_links`, `valuation_method_history`, `platform.label_templates`; `purchase_ocr_drafts` **rad** — `ai_ocr_jobs`ga qo'shildi), 24 jadvalga ustun/CHECK o'zgarishi, 4 yangi `SECURITY DEFINER` funksiya. Rad etilganlar: `marking_codes.verify_source`, `fiscal_receipts.last_retry_*` (audit_log yetarli), alohida `billing_invoices` jadvali (ustun yetarli), `debt_moves.limit_exceeded` (registr append-only — bayroq `sales`ga ko'chirildi), har hujjatga alohida tasdiq ustunlari (`doc_approvals` bilan almashtirildi).
5. **Xato kodlari**: API fayllarida 70+ kod ishlatilgan, katalogda yo'q **36 tasi qo'shiladi** (2 tasi qayta nomlash), **~25 tasi umumiy kodga xaritalanadi** (`*_NOT_FOUND` → `NOT_FOUND`, `*_ALREADY_POSTED` → `DOC_NOT_DRAFT`, holat xatolari → yangi `DOC_INVALID_STATE`, `FORBIDDEN` → `PERMISSION_DENIED`, `AI_UNAVAILABLE` → `AI_PROVIDER_UNAVAILABLE`, `PIN_REQUIRED` → `APPROVAL_INVALID`/`PIN_INVALID`).
6. **Ruxsatlar**: 6 yangi kod — `catalog.manage`, `stock.opening.manage`, `valuation.settings.manage` (13-2 taklifi), `integrations.retry` (13-1 `billing.manage` noto'g'ri ishlatilgan), `einvoice.create` (chiquvchi e-faktura), `debts.remind` (AI-06 yuborish `ai.chat.use` bilan himoyalangan edi).
7. **Resurs nomlash — QAROR**: URL yo'li **kebab-case ko'plik**, JSON maydon/query/enum/`operation_id` — **snake_case**. `09` §3 matni almashtiriladi, `00-qarorlar.md`ga #24 qo'shiladi; 13-0 "ochiq savol #1" yopiladi.
8. **Sync voqealari**: 04 enum'iga 4 tur qo'shiladi — `counterparty.created`, `transfer.sent`, `transfer.received`, `expense.created` (POS-14 "Xarajat" sababi uchun). 13-2 dagi `transfer.created` nomi `transfer.sent`ga o'zgaradi; `stock_count.line_recorded` payload'i birinchi marta aniqlanadi.

---

## 0. Qabul qilingan qarorlar (barcha fayllarga ta'sir qiladi)

| # | Masala | Qaror | Asos |
|---|---|---|---|
| Q1 | URL nomlash | URL — kebab-case ko'plik (`/goods-receipts`); JSON/query/enum/`operation_id` — snake_case (DB ustuni bilan bir xil) | REST amaliyoti; JSON↔DB 1:1 xaritalash (Pydantic/SQLAlchemy alias yo'q) |
| Q2 | Xato konverti `details` | `details` — **har doim massiv** (maydon xatolari); biznes konteksti uchun yangi ixtiyoriy **`params` obyekt** (`{"limit":"500000.00","requested":"569000.00"}`, `{"resource":"products"}`, `{"reason":"..."}`) | 13-0 (massiv) vs 13-1/09 (obyekt) ziddiyati; zod/react-hook-form massivni kutadi |
| Q3 | Tasdiqlash modeli | `approval_requests` — masofaviy navbat (BO-16); `doc_approvals` — har qo'llangan tasdiqning append-only izi (`local_pin` ham, `remote_request` ham). Hujjatlar `pending_approval` holatiga **o'tmaydi** (istisno — `price_changes`, 01 §8da allaqachon bor): limitdan oshgan `post` → `202 APPROVAL_REQUIRED {approval_request_id}`, hujjat `draft`da qoladi, tasdiqlanganda server o'zi `post` qiladi. Bitta `approval_request` faqat **bir marta** ishlatiladi (`consumed`) | 13-1 #4/#5/#6/#7 takliflari (har jadvalga 3 ustun) o'rniga bitta jadval; replay himoyasi |
| Q4 | AI-03 OCR | Yagona `ai_ocr_jobs` jadvali va `/ai/ocr/jobs` (13-3) yo'li; 13-2 `/purchase-ocr-drafts` va `/goods-receipts/from-ocr-draft/{id}` **o'chiriladi**. Natija shakli — 13-2 dagi (sarlavha + `lines[]`, har maydonda `value`/`confidence` 0..1, `low_confidence_fields` yo'l ro'yxati). `doc_type_hint` faqat `purchase` (qaytarish faqat POS/sync orqali, 13-0 §9) | 13-0 §12 ikki bosqichli fayl naqshi; kirim qatorlari uchun ichma-ich `lines` shart |
| Q5 | Narx o'zgarishi egasi | `price-changes` — 13-2 §4 (M09) yagona manba; 13-1 §10 havolaga qisqartiriladi; tasdiq — `approval-requests` (kind=`price_change`) | Ikki faylda ikki xil oqim |
| Q6 | Kontragent resursi | Yagona `/counterparties` (`?is_customer=`/`?is_supplier=` filtr); `/suppliers` o'chiriladi | Bitta jadval, bitta CRUD; ruxsat qoidasi maydon darajasida |
| Q7 | `doc_type` qiymatlari | Registr/allokatsiya/`linked_doc_type`/`related_doc_type`dagi `doc_type` = **hujjat jadvali nomi** (ko'plik snake: `sales`, `goods_receipts`, `stock_openings`); ilovada yagona `DocType` enum | DDL `stock_lots.source_doc_type` birlik (`goods_receipt`), allokatsiya izohi birlik (`sale`), 13-3 ko'plik — uch xil |
| Q8 | Asinxron fayl ishlari | Hisobot eksporti va yorliq PDF — `outbox_jobs` (kind `report_export`/`label_pdf`) + 3 ustun; `GET /reports/export-jobs/{id}` va `GET /label-print-jobs/{id}` = `outbox_jobs.id` | 13-3 #1 taklifi, alohida jadval shart emas |
| Q9 | O'tkazilgan chekni bekor qilish | `POST /sales/{id}/cancel` **yo'q** — fiskallashtirilgan chek faqat `return` bilan tuzatiladi; `sales.void` — faqat to'lovdan oldingi qoralama (`sale.draft_voided`) | 13-0 §9 dagi `GET /sales/{id}/cancel` (GET bilan yozuv!) xato; OFD qoidasi |
| Q10 | Pagination | Ma'lumotnoma (`products`, `product-categories`, `counterparties`, `discount-rules`, `roles`, `branches`, `expense-categories`, `recurring-expenses`, `label-templates`) — **page**; hujjat/registr/log — **cursor** | 13-0 §4 qoidasi; 13-1/13-2 hamma joyda cursor ishlatgan |
| Q11 | Fiskal raqam | `receipt_seq` (chek) va `shift_no` (smena/Z-hisobot) — **qurilma beradi**, voqea payload'ida majburiy; server faqat UNIQUE tekshiradi | Qaror #12, 04 §2 |
| Q12 | Do'kon to'lov webhook yo'li | `POST /api/v1/payments/webhooks/{provider}` (13-0 §14); checkout resursi `POST /payments/checkouts`, `GET /payments/checkouts/{checkout_ref}` | 13-1 `/webhooks/{p}` va `/payments/{p}/checkout` 13-0 bilan zid |
| Q13 | Hujjatlarda `version` | Hujjat javoblarida `version` **yo'q** (13-0 §8); `draft`ni `PATCH` — butun qoralamani almashtiradi | 13-2 `price-changes`/`goods-receipts` javobida `version:1` qaytargan |
| Q14 | Narx aniqligi | Barcha narx/tannarx maydonlari (`price`, `cost`, `unit_cost`, `new_price`, `old_price`) — **4 xonali satr**; pul (`amount`, `*_total`, `*_amount`) — 2 xona | 13-0 §3; 13-1 `unit_price: Money`, 13-2 `new_price decimal(2dp)` noto'g'ri |

---

## 1. `14-db-sxema.md` — o'zgarishlar

### DB-01 · KRITIK · `fiscal_receipts` Z-hisobotni qabul qilmaydi
13-1 §3.2: smena yopilganda Z-hisobot "`fiscal_receipts.status=pending` bilan OFD navbatiga" — lekin DDL `CHECK (sale_id IS NOT NULL OR return_id IS NOT NULL)`. 2.8-bo'limdagi jadvalni almashtirish:
```sql
CREATE TABLE app.fiscal_receipts (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  kind             TEXT NOT NULL CHECK (kind IN ('sale','return','z_report')),
  sale_id          UUID NULL REFERENCES app.sales(id),
  return_id        UUID NULL REFERENCES app.returns(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  shift_id         UUID NOT NULL REFERENCES app.shifts(id),
  receipt_seq      INT  NULL,            -- qurilma beradi; z_report'da NULL (raqami = shifts.shift_no)
  payload          JSONB NOT NULL,
  fiscal_sign      TEXT NULL,
  qr_url           TEXT NULL,
  sent_at          TIMESTAMPTZ NULL,
  offline_since    TIMESTAMPTZ NULL,
  status           TEXT NOT NULL CHECK (status IN ('pending','sent','fiscalized','failed')) DEFAULT 'pending',
  attempts         INT NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
       (kind = 'sale'     AND sale_id IS NOT NULL AND return_id IS NULL AND receipt_seq IS NOT NULL)
    OR (kind = 'return'   AND return_id IS NOT NULL AND sale_id IS NULL AND receipt_seq IS NOT NULL)
    OR (kind = 'z_report' AND sale_id IS NULL AND return_id IS NULL AND receipt_seq IS NULL)
  ),
  UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)
);
CREATE UNIQUE INDEX uq_fiscal_z_per_shift ON app.fiscal_receipts (shift_id) WHERE kind = 'z_report';
CREATE INDEX idx_fiscal_receipts_pending ON app.fiscal_receipts (tenant_id) WHERE status IN ('pending','failed');
```

### DB-02 · KRITIK · `branches.code` yo'q, lekin raqam generatori talab qiladi
`app.next_doc_number(..., p_branch_code, ...)` va 01 §11 formati `K-01-2026-000154`. `app.branches`ga qo'shish:
```sql
  code TEXT NOT NULL CHECK (code ~ '^[0-9A-Z]{1,4}$'),   -- hujjat raqamidagi filial kodi, signup'da '01'
  -- jadval cheklovlari:
  UNIQUE (tenant_id, code)
```
5.2-bo'lim (provisioning) izohiga: "standart filial `code='01'`; keyingi filiallar — keyingi bo'sh ikki xonali raqam (API'da ixtiyoriy kiritiladi)".

### DB-03 · KRITIK · `returns`/`return_lines` — kassa va fiskal ustunlari yo'q
`ReturnPostingService` `cash_moves(shift_id)` va `fiscal_receipts(cash_register_id, shift_id)` yozadi, ammo `returns`da na smena, na kassa, na qaytarish usuli bor. `app.returns`ga:
```sql
  shift_id         UUID NOT NULL REFERENCES app.shifts(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  counterparty_id  UUID NULL REFERENCES app.counterparties(id),   -- refund_method='debt_adjustment' uchun
  reason           TEXT NOT NULL CHECK (reason IN ('defective','wrong_item','customer_changed_mind','other')),
  refund_method    TEXT NOT NULL CHECK (refund_method IN ('cash','card','debt_adjustment')),
  is_offline       BOOLEAN NOT NULL DEFAULT false,
  CHECK (refund_method <> 'debt_adjustment' OR counterparty_id IS NOT NULL),
  CHECK (sale_id IS NOT NULL OR approved_by IS NOT NULL)          -- chek topilmagan qaytarish — har doim tasdiq bilan
```
`app.return_lines`ga:
```sql
  vat_rate           NUMERIC(5,2) NOT NULL,
  vat_exemption_code TEXT NULL,
  marking_code       TEXT NULL,
  CHECK (marking_code IS NULL OR qty = 1)
```

### DB-04 · KRITIK · `debt_payments.method` API bilan mos emas
13-1 §12.2: `cash/card/uzqr/click/payme/uzum` + `terminal_ref`, `provider_tx_id`, `promise_date`. `app.debt_payments`dagi ustunlarni almashtirish/qo'shish:
```sql
  method           TEXT NOT NULL CHECK (method IN ('cash','card','uzqr','click','payme','uzum','bank')),
  terminal_ref     TEXT NULL,
  provider_tx_id   TEXT NULL,
  checkout_ref     UUID NULL REFERENCES app.payment_checkouts(checkout_ref),
  promise_date     DATE NULL,      -- qoldiq uchun yangi va'da sanasi (qarz daftari ko'rinishi oxirgisini oladi)
  CHECK (method NOT IN ('uzqr','click','payme','uzum') OR provider_tx_id IS NOT NULL)
  -- mavjud CHECK (method <> 'cash' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL)) saqlanadi
```

### DB-05 · YUQORI · `cash_moves` CHECK bank operatsiyalarida bajarilmaydi
`CHECK (cash_register_id IS NOT NULL OR bank_account_id IS NOT NULL)` — `bank_accounts` jadvali yo'q, `expenses(source='bank')`, `supplier_payments(method='bank')`, `debt_payments(method='bank')` postingida qator yozib bo'lmaydi. Qaror: MVP'da bank hisobi — bitta yashirin `5110` (jadval yo'q). Almashtirish:
```sql
  method TEXT NOT NULL CHECK (method IN ('cash','card','uzqr','click','payme','uzum','bank')),
  bank_account_id UUID NULL,   -- MVP: doim NULL; ko'p bank hisobi — backlog (bank_accounts jadvali bilan)
  CHECK (method <> 'cash' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL))
```

### DB-06 · YUQORI · `goods_receipts` — e-faktura bog'lanishi yo'q ("qizil" QQS kechiktirish ishlamaydi)
02 §2.8: "qizil" faktura bo'lsa `Dt 4410` to'lovgacha yozilmaydi — posting qaysi faktura ekanini bilishi kerak; `POST /goods-receipts/from-einvoice/{id}` ham bog'lanishni yo'qotadi. `app.goods_receipts`ga:
```sql
  source        TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','purchase_order','einvoice','ocr')),
  einvoice_id   UUID NULL,        -- FK 0015-revizionda: REFERENCES app.einvoices(id)
  ai_ocr_job_id UUID NULL,        -- FK 0017-revizionda: REFERENCES app.ai_ocr_jobs(id)
  ettn_ref      TEXT NULL,        -- qo'lda e-TTN belgisi (13-2 #4)
  poa_number    TEXT NULL,        -- qo'lda ishonchnoma raqami (13-2 #4)
  CHECK (source <> 'einvoice' OR einvoice_id IS NOT NULL)
```
```sql
ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_einvoice FOREIGN KEY (einvoice_id) REFERENCES app.einvoices(id);
CREATE UNIQUE INDEX uq_gr_einvoice_active ON app.goods_receipts (tenant_id, einvoice_id)
  WHERE einvoice_id IS NOT NULL AND status <> 'cancelled';
```
`app.receipt_lines`ga: `vat_exemption_code TEXT NULL` (13-2 `vat_rate` "imtiyoz kodi" qiymatini qabul qiladi; `products` dagi bo'linish bilan izchil).

### DB-07 · YUQORI · `shifts` — Z-hisobot ustunlari va smena raqami
13-1 §3 `variance`, `variance_note`, `counted_card_total`, `comment`, javobda `number` ishlatadi; DDL'da `diff_amount`, raqam yo'q. OFD chekida smena raqami majburiy rekvizit. 2.6-bo'limdagi `CREATE TABLE app.shifts` almashtiriladi:
```sql
CREATE TABLE app.shifts (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  branch_id          UUID NOT NULL REFERENCES app.branches(id),
  cash_register_id   UUID NOT NULL REFERENCES app.cash_registers(id),
  device_id          UUID NOT NULL REFERENCES app.devices(id),
  shift_no           INT  NOT NULL CHECK (shift_no > 0),     -- qurilma beradi, kassa ichida ketma-ket (Q11)
  status             TEXT NOT NULL CHECK (status IN ('open','closing','closed')) DEFAULT 'open',
  opened_by          UUID NOT NULL REFERENCES app.users(id),
  opened_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  closing_started_at TIMESTAMPTZ NULL,
  closed_by          UUID NULL REFERENCES app.users(id),
  closed_at          TIMESTAMPTZ NULL,
  opening_cash       NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (opening_cash >= 0),
  expected_cash      NUMERIC(18,2) NULL,                     -- server hisoblaydi: opening_cash + Σcash_moves(shift)
  counted_cash       NUMERIC(18,2) NULL,
  variance           NUMERIC(18,2) GENERATED ALWAYS AS (counted_cash - expected_cash) STORED,  -- eski diff_amount
  variance_note      TEXT NULL,
  counted_card_total NUMERIC(18,2) NULL,                     -- qo'lda belgilangan "karta" jami (POS-15)
  comment            TEXT NULL,
  client_event_id    UUID NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, client_event_id),
  UNIQUE (tenant_id, cash_register_id, shift_no),
  CHECK (status <> 'closed' OR (counted_cash IS NOT NULL AND expected_cash IS NOT NULL)),
  CHECK (counted_cash IS NULL OR expected_cash IS NULL OR counted_cash = expected_cash OR variance_note IS NOT NULL)
);
CREATE UNIQUE INDEX uq_shifts_one_open ON app.shifts (cash_register_id) WHERE status IN ('open','closing');
```

### DB-08 · YUQORI · `sales`/`sale_lines`/`sale_payments` — API maydonlari uchun ustunlar
`app.sales`ga:
```sql
  is_offline          BOOLEAN NOT NULL DEFAULT false,
  debt_limit_exceeded BOOLEAN NOT NULL DEFAULT false   -- offline nasiya limitdan oshgan (tavsiya #7) — xato emas, bayroq
```
```sql
CREATE INDEX idx_sales_debt_limit_exceeded ON app.sales (tenant_id) WHERE debt_limit_exceeded;
```
`app.sale_lines`ga (chegirma manbai — 13-1 #4; tasdiq izi `doc_approvals`da, DB-10):
```sql
  vat_exemption_code TEXT NULL,
  discount_pct       NUMERIC(5,2) NULL CHECK (discount_pct BETWEEN 0 AND 100),   -- ma'lumot uchun; manba — discount_amount
  discount_source    TEXT NULL CHECK (discount_source IN ('manual','standing_customer','rule')),
  discount_rule_id   UUID NULL REFERENCES app.discount_rules(id),
  CHECK ((discount_amount = 0) = (discount_source IS NULL)),
  CHECK (discount_source IS DISTINCT FROM 'rule' OR discount_rule_id IS NOT NULL)
```
`app.sale_payments`ga:
```sql
  due_date     DATE NULL,   -- method='debt': va'da sanasi → debt_moves.due_date manbai (hozir hech qayerda yo'q)
  checkout_ref UUID NULL REFERENCES app.payment_checkouts(checkout_ref),
  CHECK (method = 'debt' OR due_date IS NULL),
  CHECK (method NOT IN ('uzqr','click','payme','uzum') OR provider_tx_id IS NOT NULL)
```

### DB-09 · YUQORI · Yangi jadval `approval_requests` (13-1 #1, kengaytirilgan)
```sql
CREATE TABLE app.approval_requests (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  branch_id            UUID NOT NULL REFERENCES app.branches(id),
  kind                 TEXT NOT NULL CHECK (kind IN ('discount_over_limit','return_over_limit','return_no_receipt',
                         'debt_over_limit','cash_withdrawal_over_limit','price_change','expense_over_limit',
                         'write_off_over_limit')),
  permission_code      TEXT NOT NULL,           -- tasdiqlovchida bo'lishi shart kod (05 §2.3 xaritasi)
  requested_value      NUMERIC(18,4) NULL,      -- summa yoki foiz (role_permissions.limit_value bilan bir xil birlik)
  context              JSONB NOT NULL DEFAULT '{}',
  linked_doc_type      TEXT NULL,               -- Q7: jadval nomi ('price_changes','expenses',...)
  linked_doc_id        UUID NULL,
  device_id            UUID NULL REFERENCES app.devices(id),
  status               TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','approved','rejected','expired','consumed')),
  requested_by         UUID NOT NULL REFERENCES app.users(id),
  requested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at           TIMESTAMPTZ NOT NULL,    -- requested_at + 15 daqiqa (taxmin)
  resolved_by          UUID NULL REFERENCES app.users(id),
  resolved_at          TIMESTAMPTZ NULL,
  reject_reason        TEXT NULL,
  consumed_at          TIMESTAMPTZ NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status <> 'rejected' OR reject_reason IS NOT NULL),
  CHECK (status NOT IN ('approved','rejected','consumed') OR (resolved_by IS NOT NULL AND resolved_at IS NOT NULL)),
  CHECK (resolved_by IS NULL OR resolved_by <> requested_by)   -- o'zini o'zi tasdiqlay olmaydi
);
CREATE INDEX idx_approval_requests_pending ON app.approval_requests (tenant_id, branch_id, requested_at)
  WHERE status = 'pending';
CREATE INDEX idx_approval_requests_linked ON app.approval_requests (tenant_id, linked_doc_type, linked_doc_id)
  WHERE linked_doc_id IS NOT NULL;
```
`price_changes.approval_request_id` (13-1 #7) **qo'shilmaydi** — bog'lanish `linked_doc_type='price_changes'` orqali.

### DB-10 · YUQORI · Yangi jadval `doc_approvals` (13-1 #4/#5/#6 o'rniga)
```sql
CREATE TABLE app.doc_approvals (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  doc_type             TEXT NOT NULL,           -- 'sales','returns','cash_movements','expenses','write_offs','price_changes'
  doc_id               UUID NOT NULL,
  line_id              UUID NULL,               -- chegirma — sale_lines.id
  kind                 TEXT NOT NULL CHECK (kind IN ('discount_over_limit','return_over_limit','return_no_receipt',
                         'debt_over_limit','cash_withdrawal_over_limit','price_change','expense_over_limit',
                         'write_off_over_limit')),
  mode                 TEXT NOT NULL CHECK (mode IN ('local_pin','remote_request')),
  approved_by          UUID NOT NULL REFERENCES app.users(id),
  approval_request_id  UUID NULL REFERENCES app.approval_requests(id),
  pin_verified_locally BOOLEAN NOT NULL DEFAULT false,
  requested_value      NUMERIC(18,4) NULL,
  approved_at          TIMESTAMPTZ NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (mode <> 'remote_request' OR approval_request_id IS NOT NULL),
  CHECK (mode <> 'local_pin' OR pin_verified_locally)
);
CREATE UNIQUE INDEX uq_doc_approvals_request ON app.doc_approvals (approval_request_id) WHERE approval_request_id IS NOT NULL;
CREATE INDEX idx_doc_approvals_doc ON app.doc_approvals (tenant_id, doc_type, doc_id);
```
3-bo'limdagi `append_only_tables` massiviga `'app.doc_approvals'` qo'shiladi. Mavjud `returns.approved_by/approved_at`, `price_changes.approved_by`, `debt_writeoffs.approved_by` — hujjat sarlavhasidagi "yakuniy tasdiqlovchi" sifatida qoladi; batafsil iz — `doc_approvals`.

### DB-11 · YUQORI · Yangi jadval `payment_checkouts` (13-1 #2, faqat do'kon to'lovi)
`context='billing'` olib tashlandi — obuna checkout'i `billing_payments(status='pending')` (DB-18). `sale_id` FK yo'q (aylana bog'liqlik) — bog'lanish `sale_payments.checkout_ref` orqali.
```sql
CREATE TABLE app.payment_checkouts (
  checkout_ref     UUID PRIMARY KEY,           -- qurilma beradi (UUIDv7)
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  device_id        UUID NULL REFERENCES app.devices(id),
  provider         TEXT NOT NULL CHECK (provider IN ('uzqr','click','payme','uzum')),
  qr_type          TEXT NULL CHECK (qr_type IN ('static','dynamic')),
  amount           NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  provider_tx_id   TEXT NULL,
  status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','confirmed','failed','expired','consumed')),
  confirmed_at     TIMESTAMPTZ NULL,
  expires_at       TIMESTAMPTZ NOT NULL,
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (provider = 'uzqr' OR qr_type IS NULL),
  UNIQUE (provider, provider_tx_id)
);
CREATE INDEX idx_payment_checkouts_expiry ON app.payment_checkouts (expires_at) WHERE status = 'pending';
```
Webhook tenant kontekstisiz keladi → 4.5-bo'limga ikki `SECURITY DEFINER` funksiya (DB-30).

### DB-12 · KRITIK · Qo'lda buxgalteriya tuzatishi uchun hujjat jadvali + `ledger_entries.branch_id`
13-3 #10 `POST /ledger-entries/adjustments` (`comment`, `correction_of_period`) — `ledger_entries`da bu ustunlar yo'q va `doc_type/doc_id NOT NULL` uchun hujjat yo'q. Yangi hujjat (umumiy sarlavha bilan, `doc_sequences` kodi `BX`):
```sql
CREATE TABLE app.ledger_adjustments (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  branch_id            UUID NOT NULL REFERENCES app.branches(id),
  number               TEXT NULL,
  temp_number          TEXT NULL,
  doc_date             DATE NOT NULL,           -- = ledger_entries.entry_date, joriy ochiq davr
  status               TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  account_dt           TEXT NOT NULL,
  account_kt           TEXT NOT NULL,
  amount               NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  correction_of_period DATE NULL CHECK (correction_of_period IS NULL OR extract(day FROM correction_of_period) = 1),
  created_by           UUID NOT NULL REFERENCES app.users(id),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at            TIMESTAMPTZ NULL,
  cancelled_at         TIMESTAMPTZ NULL,
  cancelled_by         UUID NULL REFERENCES app.users(id),
  cancel_reason        TEXT NULL,
  client_event_id      UUID NULL,
  device_id            UUID NULL REFERENCES app.devices(id),
  comment              TEXT NOT NULL,           -- majburiy (13-3 #10)
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK (account_dt <> account_kt)
);
```
`app.ledger_entries`ga (02 §5.4 filial bo'yicha hisobot, 13-3 `?branch_id=` filtri — JSONB `analytics` bo'yicha indekssiz filtr taqiqlangan, 13-0 §5):
```sql
  branch_id UUID NULL REFERENCES app.branches(id)
```
```sql
CREATE INDEX idx_ledger_entries_branch ON app.ledger_entries (tenant_id, branch_id, entry_date);
```
2.9-bo'limdagi `doc_type` kodlari ro'yxatiga: `BX`=ledger_adjustments.

### DB-13 · YUQORI · Yangi jadval `ai_ocr_jobs` (13-2 `purchase_ocr_drafts` + 13-3 `ai_ocr_jobs` birlashmasi, Q4)
```sql
CREATE TABLE app.ai_ocr_jobs (
  id                    UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id             UUID NOT NULL REFERENCES app.tenants(id),
  branch_id             UUID NULL REFERENCES app.branches(id),
  created_by            UUID NOT NULL REFERENCES app.users(id),
  attachment_id         UUID NOT NULL REFERENCES app.attachments(id),
  doc_type_hint         TEXT NOT NULL DEFAULT 'purchase' CHECK (doc_type_hint IN ('purchase')),
  status                TEXT NOT NULL DEFAULT 'processing'
                          CHECK (status IN ('processing','done','failed','confirmed','expired')),
  fields                JSONB NULL,             -- {header:{supplier_name:{value,confidence},...}, lines:[{...}]}
  low_confidence_fields TEXT[] NOT NULL DEFAULT '{}',   -- masalan 'lines[0].product_name'
  error_code            TEXT NULL,              -- 'OCR_IMAGE_UNREADABLE', 'AI_PROVIDER_UNAVAILABLE'
  ai_request_id         UUID NULL REFERENCES app.ai_requests(id),
  created_doc_type      TEXT NULL,              -- 'goods_receipts'
  created_doc_id        UUID NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at           TIMESTAMPTZ NULL,
  confirmed_at          TIMESTAMPTZ NULL,
  expires_at            TIMESTAMPTZ NOT NULL,   -- created_at + 7 kun (taxmin), keyin 'expired' va fields tozalanadi
  CHECK (status <> 'confirmed' OR (created_doc_id IS NOT NULL AND confirmed_at IS NOT NULL))
);
CREATE INDEX idx_ai_ocr_jobs_expiry ON app.ai_ocr_jobs (expires_at) WHERE status IN ('processing','done');
ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_ocr_job FOREIGN KEY (ai_ocr_job_id) REFERENCES app.ai_ocr_jobs(id);
```

### DB-14 · YUQORI · `supplier_payments` — naqd to'lov uchun kassa/smena yo'q
13-2 §11 `cash_register_id`; `debt_payments`/`expenses` bilan izchil CHECK. `app.supplier_payments`ga:
```sql
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  shift_id         UUID NULL REFERENCES app.shifts(id),
  CHECK (method <> 'cash' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL))
```

### DB-15 · YUQORI · `purchase_orders.warehouse_id` yo'q; `po_lines.price` majburiy
13-2 §10 `warehouse_id` majburiy, `lines[].price` ixtiyoriy. `app.purchase_orders`ga `warehouse_id UUID NOT NULL REFERENCES app.warehouses(id)`; `app.po_lines.price` → `NUMERIC(18,4) NULL CHECK (price IS NULL OR price >= 0)`. `status` — **saqlanadigan** ustun sifatida qoladi (01 §8 "hisoblanadi, saqlanmaydi" matni M-17 da tuzatiladi): `GoodsReceiptPostingService` shu tranzaksiyada `partially_received`/`closed`ga yangilaydi.

### DB-16 · YUQORI · `transfers`/`transfer_lines` — ko'p partiyali jo'natish va holat vaqtlari
Bitta qator FIFO bo'yicha bir nechta partiyadan chiqishi mumkin — bitta `lot_id` yetarli emas; qoralamada `unit_cost` noma'lum. `app.transfer_lines`: `lot_id` ustuni va `fk_tl_lot` **olib tashlanadi**, o'rniga:
```sql
  unit_cost       NUMERIC(18,4) NULL,                 -- send'da to'ldiriladi (allokatsiyalarning o'rtachasi)
  lot_allocations JSONB NOT NULL DEFAULT '[]'         -- [{lot_id, qty, unit_cost}] — sale_lines bilan bir xil shakl
```
`app.transfers`ga:
```sql
  sent_at     TIMESTAMPTZ NULL,
  sent_by     UUID NULL REFERENCES app.users(id),
  received_at TIMESTAMPTZ NULL,
  received_by UUID NULL REFERENCES app.users(id),
  CHECK (branch_id = from_branch_id)
```

### DB-17 · O'RTA · `recurring_expenses` — to'liq qayta yozish (13-3 #2)
DDL `period CHECK (period='monthly')` 13-3 `month|quarter|year` bilan zid; `source`, `cash_register_id`, `next_due_*`, `created_by`, `version` yo'q. Almashtirish:
```sql
CREATE TABLE app.recurring_expenses (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  category_id       UUID NOT NULL REFERENCES app.expense_categories(id),
  name              TEXT NULL,                  -- bo'sh bo'lsa UI toifa nomini ko'rsatadi
  amount            NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  period            TEXT NOT NULL CHECK (period IN ('month','quarter','year')),
  day_of_month      INT  NOT NULL CHECK (day_of_month BETWEEN 1 AND 28),
  source            TEXT NOT NULL CHECK (source IN ('cash','bank','card')),
  cash_register_id  UUID NULL REFERENCES app.cash_registers(id),
  next_due_date     DATE NOT NULL,
  last_triggered_at TIMESTAMPTZ NULL,
  is_active         BOOLEAN NOT NULL DEFAULT true,
  created_by        UUID NOT NULL REFERENCES app.users(id),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  version           INT NOT NULL DEFAULT 1,
  CHECK (source <> 'cash' OR cash_register_id IS NOT NULL)
);
CREATE INDEX idx_recurring_expenses_due ON app.recurring_expenses (tenant_id, next_due_date) WHERE is_active;
```

### DB-18 · O'RTA · `billing_payments` — davr, kvitansiya, checkout oldidan yozuv (13-3 #3)
Click `merchant_trans_id` = bizning `billing_payments.id`; Payme tranzaksiya ID'si `CreateTransaction`da keladi — checkout paytida `provider_tx_id` noma'lum. O'zgarishlar:
```sql
  provider_tx_id        TEXT NULL,                  -- NOT NULL olib tashlanadi; UNIQUE (provider, provider_tx_id) qoladi
  status                TEXT NOT NULL CHECK (status IN ('pending','success','failed','cancelled')),
  period                TEXT NOT NULL CHECK (period IN ('month','year')),
  covers_from           DATE NULL,                  -- success'da to'ldiriladi
  covers_to             DATE NULL,
  amount_breakdown      JSONB NOT NULL DEFAULT '{}', -- {plan:"99000.00", addons:[{code,qty,price}]} snapshot
  invoice_number        TEXT NULL,
  invoice_attachment_id UUID NULL,                  -- FK 0013-revizionda → app.attachments(id)
  created_by            UUID NULL REFERENCES app.users(id)
```
```sql
CREATE UNIQUE INDEX uq_billing_invoice_number ON app.billing_payments (invoice_number) WHERE invoice_number IS NOT NULL;
```
Alohida `billing_invoices` jadvali — **rad** (1:1, ustun yetarli).

### DB-19 · O'RTA · `outbox_jobs` — eksport/yorliq ishlari (13-3 #1, Q8)
```sql
  kind TEXT NOT NULL CHECK (kind IN ('ofd_send','einvoice_send','einvoice_accept','ettn_send',
         'marking_verify','marking_sell','state_report_reminder','sms','telegram','ai',
         'report_export','label_pdf')),
  created_by           UUID NULL REFERENCES app.users(id),     -- eksport job'ini faqat yaratuvchi/Egasi ko'radi
  progress_pct         SMALLINT NULL CHECK (progress_pct BETWEEN 0 AND 100),
  result_attachment_id UUID NULL REFERENCES app.attachments(id),
  error_code           TEXT NULL                                -- 13-0 katalogidan (masalan EXPORT_JOB_FAILED)
```
API holati xaritasi: `retry` → API'da `running` sifatida ko'rsatiladi.

### DB-20 · O'RTA · `state_reports` — solishtirish yig'indilari va tuzatish
13-3 #4/#6/#8 javoblari (`state_amount`, `our_amount`, `diff_amount`, `correction_sent_at`) uchun:
```sql
  state_amount         NUMERIC(18,2) NULL,
  our_amount           NUMERIC(18,2) NULL,
  diff_amount          NUMERIC(18,2) NULL,
  compared_at          TIMESTAMPTZ NULL,
  correction_sent_at   TIMESTAMPTZ NULL,
  correction_signature TEXT NULL,          -- E-IMZO PKCS#7 (base64)
  uploaded_by          UUID NOT NULL REFERENCES app.users(id)
```
Tolerantlik — `tenants.settings.vat_diff_tolerance_amount` (13-3 #6, M-03).

### DB-21 · O'RTA · `einvoices` — holat CHECK, summalar, "bitta chekka bitta faktura"
02 §2.22 cheklovi (bitta chekka bitta faol chiquvchi faktura) DB'da yo'q; `status` CHECK'siz; 13-2 ro'yxati `amount`/`vat_amount` qaytaradi.
```sql
  status           TEXT NOT NULL CHECK (status IN ('draft','received','signed','sent','accepted','rejected','cancelled')),
  number           TEXT NULL,                 -- operator/faktura raqami
  doc_date         DATE NULL,
  total_amount     NUMERIC(18,2) NULL,
  vat_amount       NUMERIC(18,2) NULL,
  signed_by        UUID NULL REFERENCES app.users(id),
  CHECK (related_doc_type IS NULL OR related_doc_type IN ('sales','goods_receipts','supplier_returns'))
```
```sql
CREATE UNIQUE INDEX uq_einvoice_out_per_doc ON app.einvoices (tenant_id, related_doc_type, related_doc_id)
  WHERE direction = 'out' AND related_doc_id IS NOT NULL AND status <> 'cancelled';
CREATE UNIQUE INDEX uq_einvoice_operator_doc ON app.einvoices (tenant_id, operator, operator_doc_id)
  WHERE operator_doc_id IS NOT NULL;
```

### DB-22 · O'RTA · `attachments` — MIME va tur
13-0 §12 tur tekshiruvi (`415`) va imzolangan URL `Content-Type` uchun:
```sql
  content_type  TEXT NOT NULL,
  original_name TEXT NULL,
  sha256        TEXT NULL,
  kind          TEXT NOT NULL CHECK (kind IN ('expense_receipt','ocr_source','state_report','import','export',
                  'label_pdf','billing_invoice','einvoice','other'))
```

### DB-23 · O'RTA · `products.mxik_code` — API ixtiyoriy, DDL majburiy
13-2 §1: MXIK yaratishda bloklamaydi (sotuvdan oldin shart); DDL `NOT NULL CHECK (char_length=17)` va harf ham o'tkazib yuboradi. Almashtirish:
```sql
  mxik_code TEXT NULL CHECK (mxik_code IS NULL OR mxik_code ~ '^[0-9]{17}$'),
```
Sotuv voqeasida MXIK'siz tovar → `VALIDATION_ERROR` (`params.reason='mxik_missing'`); POS katalog pull'i MXIK'siz tovarni "sotib bo'lmaydi" belgisi bilan beradi.

### DB-24 · O'RTA · Qarz hujjatlari
- `app.debt_openings`ga `due_date DATE NULL` (13-1 §12.4 body'da bor).
- `app.debt_writeoffs`: `reason TEXT NOT NULL` qo'shiladi (13-1 §12.5 majburiy); `account_choice ... NOT NULL DEFAULT '9430'` (02 §2.15 "9430 standart"); `approved_by UUID NULL` + `CHECK (status <> 'posted' OR approved_by IS NOT NULL)` (qoralama tasdiqsiz yaratiladi).

### DB-25 · O'RTA · Ombor hujjatlari
- `app.supplier_returns`ga `reason TEXT NOT NULL CHECK (reason IN ('expired','damaged','excess','other'))` — **sarlavhada** (13-2 §12 API shunday; 13-2 #3 "qator darajasida" taklifi rad).
- `app.write_offs`ga `responsible_user_id UUID NULL REFERENCES app.users(id)` (02 §2.12: belgilansa 4730). `write_off_lines.reason` qator darajasida **qoladi** (API moslashtiriladi, A2-12).
- `app.count_lines.counted` → `NUMERIC(18,3) NULL` (13-2 `counted:null` bilan boshlanadi; `diff` generatsiyasi NULL beradi).
- `app.price_change_lines`ga `valid_from TIMESTAMPTZ NULL` (NULL = post paytidan; 13-1 qator darajasida yuboradi).

### DB-26 · O'RTA · Yangi jadval `valuation_method_history`
13-2 §17 `pending_change`/`effective_from` saqlash joyi yo'q; usul tarixi qayta hisoblash (`recost_jobs`) uchun kerak. `tenant_tax_regimes` naqshi:
```sql
CREATE TABLE app.valuation_method_history (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  valid_from DATE NOT NULL CHECK (extract(month FROM valid_from) = 1 AND extract(day FROM valid_from) = 1),
  method     TEXT NOT NULL CHECK (method IN ('fifo','aveco')),
  created_by UUID NOT NULL REFERENCES app.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, valid_from)
);
```
Signup: `valid_from = joriy yil 1-yanvar`, `method='aveco'` (yoki tanlangan). `tenants.settings.valuation_method` kaliti **olib tashlanadi**.

### DB-27 · O'RTA · Yangi global jadval `platform.label_templates` (13-2 #5)
```sql
CREATE TABLE platform.label_templates (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  code       TEXT NOT NULL UNIQUE,         -- '58x40_price', '40x30_barcode'
  name       TEXT NOT NULL,
  width_mm   NUMERIC(6,2) NOT NULL CHECK (width_mm > 0),
  height_mm  NUMERIC(6,2) NOT NULL CHECK (height_mm > 0),
  fields     JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
4.4-bo'lim `GRANT SELECT ... TO erp_app` ro'yxatiga va 6.2 CI `exempt` ro'yxatiga `platform.label_templates` qo'shiladi; 5.1 seed'ga kamida bitta 58×40 shablon.

### DB-28 · O'RTA · Yangi jadval `counterparty_statement_links` (13-1 #8)
```sql
CREATE TABLE app.counterparty_statement_links (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  counterparty_id  UUID NOT NULL REFERENCES app.counterparties(id),
  token_hash       TEXT NOT NULL UNIQUE,    -- token o'zi saqlanmaydi (SHA-256)
  expires_at       TIMESTAMPTZ NOT NULL,    -- +30 kun (taxmin)
  revoked_at       TIMESTAMPTZ NULL,
  last_accessed_at TIMESTAMPTZ NULL,
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### DB-29 · O'RTA · `import_jobs` — asinxron holatlar va natija
13-2 §6 `validate`/`commit` — `202`, oraliq holat kerak; `created_doc_ids` saqlanmaydi.
```sql
  status TEXT NOT NULL CHECK (status IN ('uploaded','validating','validated','committing','committed','failed')) DEFAULT 'uploaded',
  result JSONB NOT NULL DEFAULT '{}'      -- {"created_doc_ids":[...], "created_product_count":n}
```

### DB-30 · O'RTA · 4.5-bo'lim — yangi `SECURITY DEFINER` funksiyalar
Tenant kontekstisiz kiruvchi so'rovlar uchun (`billing_tenant_by_payment` naqshi bilan, `erp_system` egaligida, `SET search_path = app, pg_temp`, `REVOKE ... FROM PUBLIC`, `GRANT EXECUTE ... TO erp_app`):
```sql
CREATE OR REPLACE FUNCTION app.payments_checkout_by_provider_tx(p_provider text, p_provider_tx_id text)
RETURNS TABLE (tenant_id uuid, checkout_ref uuid, status text) LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT tenant_id, checkout_ref, status FROM app.payment_checkouts
  WHERE provider = p_provider AND provider_tx_id = p_provider_tx_id;
$$;

CREATE OR REPLACE FUNCTION app.payments_checkout_by_ref(p_checkout_ref uuid)
RETURNS TABLE (tenant_id uuid, provider text, status text, amount numeric) LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT tenant_id, provider, status, amount FROM app.payment_checkouts WHERE checkout_ref = p_checkout_ref;
$$;

CREATE OR REPLACE FUNCTION app.billing_payment_by_id(p_payment_id uuid)
RETURNS TABLE (tenant_id uuid, status text, amount numeric) LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT tenant_id, status, amount FROM app.billing_payments WHERE id = p_payment_id;
$$;

CREATE OR REPLACE FUNCTION app.public_statement_by_token(p_token_hash text)
RETURNS TABLE (tenant_id uuid, counterparty_id uuid, expires_at timestamptz) LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT tenant_id, counterparty_id, expires_at FROM app.counterparty_statement_links
  WHERE token_hash = p_token_hash AND revoked_at IS NULL AND expires_at > now();
$$;
```
6.2 CI tekshiruvidagi ro'yxatga shu 4 nom qo'shiladi, izoh "8 qator" → **"12 qator qaytishi shart"**. Telegram ulash kodi (13-3 #66) — DB emas, Redis `tg_link:{code}` (TTL 10 daqiqa) — 14'ga izoh sifatida.

### DB-31 · O'RTA · `sale_lines.marking_code` FK — posting tartibi
`fk_sl_marking` `marking_codes`da kod oldindan bo'lishini talab qiladi, lekin kirim API'si (13-2) markirovka kodlarini qabul qilmaydi — offline sotilgan kod serverda yo'q bo'ladi. 2.8-bo'lim FK izohiga qo'shish: "`SalePostingService` `sale_lines` dan **oldin**, shu tranzaksiyada `INSERT INTO marking_codes ... ON CONFLICT (tenant_id, code) DO UPDATE SET status=..., last_doc_id=...` bajaradi (online — `sold`, offline — `pending_verification`); FK `DEFERRABLE` shu tartibni kafolatlaydi."

### DB-32 · O'RTA · Migratsiya rejasi (6.1) va 7-bo'lim
6.1 jadvaliga: 0004 — `platform.label_templates`; 0005 — `valuation_method_history`; 0006 — `counterparty_statement_links`; 0007 — `payment_checkouts`, `approval_requests`, `doc_approvals` (**`sales`dan oldin**, `sale_payments.checkout_ref` FK uchun); 0011 — `ledger_entries.branch_id`; 0012 — `ledger_adjustments`; 0013 — `billing_payments.invoice_attachment_id` FK; 0015 — `fk_gr_einvoice`; 0016 — `outbox_jobs` yangi ustunlar; 0017 — `ai_ocr_jobs`, `fk_gr_ocr_job`; 0021 — DB-30 funksiyalari. 7-bo'limga aniqlashtirishlar **#17–#30** sifatida shu faylning DB-01…DB-31 qarorlari qisqa qatorlarda qo'shiladi.

### DB-33 · PAST · Mayda tuzatishlar
- `marking_codes`: jadval ichidagi `UNIQUE (tenant_id, code)` va keyingi `CREATE UNIQUE INDEX uq_marking_codes_tenant_code` — **takror**; indeks qatori o'chiriladi.
- `stock_lots.source_doc_type` CHECK → `('goods_receipts','stock_openings','transfers')` (Q7); `debt_payment_allocations.target_doc_type` izohi → `'sales' | 'debt_openings'`.
- `expense_categories`ga `version INT NOT NULL DEFAULT 1` (13-3 #47 `PATCH` `version` talab qiladi).
- `cash_registers.ofd_status` → `TEXT NOT NULL DEFAULT 'pending' CHECK (ofd_status IN ('pending','registered','active','suspended','deregistered'))` (qiymatlar — taxmin, OFD reyestr hujjati bilan tasdiqlanadi).
- `role_permissions.limit_value` izohiga: API'da 4 xonali satr (`"5.0000"`), UI foiz/so'mni `permission_code`ga qarab formatlaydi.

---

## 2. `01-malumotlar-modeli.md` — o'zgarishlar

**Umumiy qoida (M-00 · YUQORI)**: 14-db-sxema.md §7dagi 16 aniqlashtirish **kanonik** (barchasi asosli) — 01 ular bilan moslashtiriladi; quyidagi qatorlar faqat haqiqiy matn o'zgarishlari. Har qatorga `*(2026-10-15: qabul-6)*` belgisi.

| ID | Daraja | Joy | Yangi matn (qator/band) |
|---|---|---|---|
| M-01 | O'RTA | §1 jadvaliga yangi qator | `\| Sxemalar \| \`app\` (tenant biznes jadvallari), \`auth\` (login/token — faqat SECURITY DEFINER), \`platform\` (global: \`plans\`, \`addons\`, \`units\`, \`label_templates\`, \`oauth_clients\`, \`signing_keys\`, \`platform_admins\`) — DDL \`14-db-sxema.md\` §1 \|` |
| M-02 | PAST | §1 "Majburiy ustunlar" | "`tenant_id`, `created_at`, `updated_at` (o'zgaruvchan jadvallarda); `created_by` — hujjatlar, tarix jadvallari va audit talab qiladigan yozuvlarda (ma'lumotnomalarda o'zgarish izi — `audit_log`)" |
| M-03 | O'RTA | §2 `tenants` | "id, name, activity_type, stir (null), phone, settings JSONB — kalitlar (Pydantic `TenantSettings` sxemasi): `ai_training_consent`, `negative_stock_policy` (`allow`/`forbid`), `scale_barcode_prefix`, `scale_barcode_version`, `low_stock_check_enabled`, `expiry_warning_days` (standart 7), `vat_diff_tolerance_amount` (standart `"1000.00"`, taxmin), `supplier_payment_strict` (bool). **Baholash usuli bu yerda emas** — `valuation_method_history`" |
| M-04 | O'RTA | §2 `billing_payments` | "tenant_id, amount, provider (`click`/`payme`), provider_tx_id (null — checkout paytida; UNIQUE (provider, provider_tx_id)), status (`pending`/`success`/`failed`/`cancelled`), period (`month`/`year`), covers_from, covers_to, amount_breakdown JSONB, invoice_number, invoice_attachment_id, paid_at \| Bizning daromad; `POST /billing/checkout` `pending` qator yaratadi, uning `id`si Click `merchant_trans_id`; webhook idempotent; kvitansiya PDF — `invoice_attachment_id`" |
| M-05 | KRITIK | §3 `branches` | "tenant_id, **code** (hujjat raqamidagi filial kodi, `01`, UNIQUE per tenant), name, address, is_default, settlement_category, activity_type, archived_at, version" |
| M-06 | O'RTA | §3 `cash_registers` | "tenant_id, branch_id, name, kind (`web`/`android`), fiscal_module_id, ofd_status (`pending`/`registered`/`active`/`suspended`/`deregistered`), **archived_at** (qo'shimcha kassa kamaytirilganda), version" (13-3 #5 — DDL'da allaqachon bor) |
| M-07 | PAST | §3 `roles` | "tenant_id, name, is_system (bool), system_code (`owner`/`manager`/`cashier`/`storekeeper`/`accountant`, faqat tizim rollarida), archived_at, version" |
| M-08 | O'RTA | §4 `products` | "...mxik_code (17 raqam; **null ruxsat** — yaratishda bloklanmaydi, sotuvdan oldin shart), package_code, vat_rate (12/0, null) + vat_exemption_code (imtiyoz kodi) — kamida bittasi to'ldirilgan, ..." |
| M-09 | O'RTA | §4 yangi qator | `\| \`label_templates\` (global) \| code, name, width_mm, height_mm, fields JSONB \| Standart yorliq shablonlari (US-M09-04), tenant o'zgartirmaydi, RLS istisnosi \|` |
| M-10 | O'RTA | §4 `product_prices` | "valid_from TIMESTAMPTZ (kun ichida o'zgarishi mumkin); `price_change_lines.valid_from` (null = post paytidan)" |
| M-11 | O'RTA | §5 yangi band | "**`counterparty_statement_links`**: tenant_id, counterparty_id, token_hash, expires_at (+30 kun, taxmin), revoked_at, last_accessed_at, created_by — mijozning ochiq qarz hisob-varag'i havolasi (US-M08-08); token o'zi saqlanmaydi, qidiruv `public_statement_by_token()` orqali" |
| M-12 | YUQORI | §6 `shifts` qatori | "`shifts` \| — \| M01, M16 \| shift_no (qurilma beradi, kassa ichida ketma-ket — OFD smena raqami), opened_by/at, closed_by/at, opening_cash, expected_cash (server), counted_cash, variance (= counted − expected), variance_note (farq bo'lsa majburiy), counted_card_total. Yopilishda farq 02 §2.19 bo'yicha provodka; Z-hisobot — `fiscal_receipts(kind='z_report')`" |
| M-13 | YUQORI | §6 `sales` qatori | Sarlavhaga: "shift_id, cash_register_id, counterparty_id (nasiya), total_amount, is_offline, debt_limit_exceeded (offline limitdan oshgan nasiya bayrog'i, #7)"; `sale_lines`ga: "line_no, price (4 xona), discount_amount (+ discount_pct, discount_source `manual`/`standing_customer`/`rule`, discount_rule_id), vat_rate + vat_exemption_code, vat_amount, line_total, cost_amount"; `sale_payments`ga: "**due_date** (`method='debt'` — va'da sanasi, `debt_moves.due_date` manbai), checkout_ref" |
| M-14 | KRITIK | §6 `returns` qatori | "`returns` \| `return_lines` (sale_line_id (null = chek topilmagan), product_id, qty, price, vat_rate, vat_exemption_code, vat_amount, cost_amount, line_total, marking_code) \| M02 \| sarlavha: sale_id (null ruxsat), **shift_id, cash_register_id**, counterparty_id, reason (`defective`/`wrong_item`/`customer_changed_mind`/`other`), **refund_method** (`cash`/`card`/`debt_adjustment`), is_offline, approved_by/at; qoldiq +, kassa −/qarz −, QQS −, buxgalteriya, fiskal qaytarish cheki" |
| M-15 | YUQORI | §6 `goods_receipts` qatori | "`receipt_lines` (product, qty, cost (4 xona), vat_rate + vat_exemption_code, vat_amount, expiry_date) \| sarlavha: supplier_id, warehouse_id, po_id, **source** (`manual`/`purchase_order`/`einvoice`/`ocr`), **einvoice_id** ("qizil" QQS kechiktirish shu orqali aniqlanadi), ai_ocr_job_id, paid_immediately (02 §2.6/§2.8 yo'li), ettn_ref, poa_number" |
| M-16 | YUQORI | §6 `transfers`/`purchase_orders`/`supplier_returns`/`write_offs`/`stock_counts` | `purchase_orders`: "+ supplier_id, **warehouse_id**; `po_lines` (product, qty, price null)"; `transfers`: "`transfer_lines` (product, qty_sent, qty_received, unit_cost, **lot_allocations JSONB** — bir qator bir nechta partiyadan); sarlavha: from/to_branch_id, from/to_warehouse_id, sent_at/by, received_at/by"; `supplier_returns`: "sarlavhada **reason** (`expired`/`damaged`/`excess`/`other`)"; `write_offs`: "+ responsible_user_id (02 §2.12: 4730)"; `count_lines`: "counted null (sanash tugamaguncha)" |
| M-17 | YUQORI | §6 qarz/to'lov qatorlari | `debt_openings`: "counterparty, amount, direction, **due_date**"; `debt_payments`: "method (`cash`/`card`/`uzqr`/`click`/`payme`/`uzum`/`bank`), cash_register_id+shift_id (naqd), terminal_ref, provider_tx_id, checkout_ref, **promise_date**; `allocations` → `debt_payment_allocations(target_doc_type, target_doc_id, amount)`"; `debt_writeoffs`: "counterparty, amount, **reason**, account_choice (`9430` standart / `4910`), approved_by (faqat Egasi)"; `supplier_payments`: "method (`cash`/`bank`), cash_register_id+shift_id (naqd), allocations → `supplier_payment_allocations(target_doc_type='goods_receipts', …)`" |
| M-18 | YUQORI | §6 yangi qator (jadval oxiri) | `\| \`ledger_adjustments\` (qo'lda buxgalteriya tuzatishi) \| — (account_dt, account_kt, amount, correction_of_period, comment majburiy) \| M11 \| \`ledger_entries\` +; faqat joriy ochiq davrda (02 §5.1, #15 qaror) \|` |
| M-19 | O'RTA | §6 "Qo'shimcha" band | "`expense_categories` (name, is_system, archived_at, version), `recurring_expenses` (branch_id, category_id, name, amount, period `month`/`quarter`/`year`, day_of_month 1–28, source, cash_register_id, next_due_date, last_triggered_at, is_active, created_by, version — avtomatik to'lanmaydi, eslatma + qo'lda tasdiq), `attachments` (s3_key, content_type, original_name, kind, size_bytes, sha256, uploaded_by)" |
| M-20 | YUQORI | §6 yangi bo'lim "6.1 Tasdiqlash va to'lov seanslari" | "**`approval_requests`** — masofaviy tasdiq navbati (BO-16): kind, permission_code, requested_value, context JSONB, linked_doc_type/id, status (`pending`/`approved`/`rejected`/`expired`/`consumed`), requested_by/at, expires_at (+15 daqiqa, taxmin), resolved_by/at, reject_reason; bitta so'rov bir hujjatda bir marta ishlatiladi (`consumed`). **`doc_approvals`** — qo'llangan har tasdiqning append-only izi (local_pin yoki remote_request): doc_type, doc_id, line_id, kind, mode, approved_by, approval_request_id, pin_verified_locally, requested_value, approved_at. Limitdan oshgan hujjat `pending_approval` holatiga o'tmaydi (istisno — `price_changes`): `draft`da qoladi, tasdiqlanganda server o'zi o'tkazadi. **`payment_checkouts`** — UzQR/Click/Payme/Uzum to'lov seansi chekdan oldin: checkout_ref (qurilma beradi), provider, qr_type, amount, provider_tx_id, status (`pending`/`confirmed`/`failed`/`expired`/`consumed`), expires_at; `sale_payments.checkout_ref`/`debt_payments.checkout_ref` bilan bog'lanadi" |
| M-21 | O'RTA | §7 `cash_moves` | "tenant_id, cash_register_id (naqdda majburiy), bank_account_id (**MVP'da doim null** — yagona bank hisobi 5110, ko'p hisob — backlog), shift_id, amount (±), method, doc_type, doc_id" |
| M-22 | O'RTA | §7 `ledger_entries` | "tenant_id, entry_date, **branch_id** (filial hisobotlari uchun indeksli ustun), account_dt, account_kt, amount, doc_type, doc_id, analytics JSONB (product, counterparty)" |
| M-23 | O'RTA | §7 `stock_lots` | "tenant_id, warehouse_id, product_id, **source_doc_type** (`goods_receipts`/`stock_openings`/`transfers`), source_doc_id, source_line_id, receipt_line_id (faqat kirimda), received_at, qty_in, qty_left, unit_cost, expiry_date" + umumiy band: "**`doc_type` qiymati — hujjat jadvali nomi** (`sales`, `goods_receipts`, …) barcha registr/allokatsiya/bog'lanish ustunlarida" |
| M-24 | O'RTA | §7 yangi qator | `\| \`valuation_method_history\` \| tenant_id, valid_from (yil 1-yanvari), method (\`fifo\`/\`aveco\`), created_by \| Usul faqat yangi yil boshidan; joriy usul = eng oxirgi valid_from ≤ hujjat sanasi (US-M04-05) \|` |
| M-25 | YUQORI | §8 holat mashinalari | `purchase_orders`: "...holat **saqlanadi** (`status` ustuni), `GoodsReceiptPostingService` shu tranzaksiyada `partially_received`/`closed`ga yangilaydi" (avvalgi "saqlanadigan ustun emas" matni o'chiriladi). `E-faktura`: "chiquvchi: `draft` → `signed` → `sent` → `accepted`/`rejected`/`cancelled`; kiruvchi: `received` → `signed` → `accepted`/`rejected`". Yangi qatorlar: `approval_requests`: "`pending` → `approved` → `consumed` / `rejected` / `expired`"; `payment_checkouts`: "`pending` → `confirmed` → `consumed` / `failed` / `expired`"; `ai_ocr_jobs`: "`processing` → `done` → `confirmed` / `expired`; `failed`"; `import_jobs`: "`uploaded` → `validating` → `validated` → `committing` → `committed`; har bosqichdan `failed`"; Inventarizatsiya: "`counting` → `review` → `posted`; `counting`/`review`dan `cancelled`" |
| M-26 | KRITIK | §9 `fiscal_receipts` | "tenant_id, **kind** (`sale`/`return`/`z_report`), sale_id/return_id (kind'ga mos), cash_register_id, shift_id, receipt_seq (qurilma beradi; z_report'da null — raqami `shifts.shift_no`), payload, fiscal_sign, qr_url, sent_at, offline_since, status, attempts" |
| M-27 | O'RTA | §9 `einvoices`, `state_reports` | `einvoices`: "..., related_doc_type + related_doc_id (`sales`/`goods_receipts`/`supplier_returns`), number, doc_date, total_amount, vat_amount, signed_by; bitta hujjatga bitta faol chiquvchi faktura (UNIQUE, 02 §2.22)"; `state_reports`: "+ state_amount, our_amount, diff_amount, compared_at, correction_sent_at, correction_signature, uploaded_by" |
| M-28 | O'RTA | §10 `outbox_jobs` | "kind (... `ai`, **`report_export`**, **`label_pdf`**), ..., created_by, progress_pct, result_attachment_id, error_code — eksport/yorliq PDF job'lari ham shu navbatda (API `job_id` = `outbox_jobs.id`)" |
| M-29 | O'RTA | §10 yangi qator | `\| \`ai_ocr_jobs\` \| tenant_id, created_by, attachment_id, doc_type_hint (\`purchase\`), status, fields JSONB (sarlavha + lines, har maydon value/confidence), low_confidence_fields[], error_code, ai_request_id, created_doc_type/id, expires_at (+7 kun) \| AI-03 oraliq natijasi; AI hujjat yozmaydi — tasdiqdan keyin \`goods_receipts\` qoralamasi. \`purchase_ocr_drafts\` nomi ishlatilmaydi \|` |
| M-30 | O'RTA | §10 `import_jobs` | "status (`uploaded` → `validating` → `validated` → `committing` → `committed` / `failed`), ..., result JSONB (created_doc_ids)" |
| M-31 | PAST | §11 Raqamlash | Jadvalga qator: `\| Smena raqami \| Kassa ichida ketma-ket (\`shifts.shift_no\`) \| Qurilmada (offline ham), server faqat UNIQUE tekshiradi \|`; hujjat raqami qatoriga "`{tur}` kodlari — `14-db-sxema.md` §2.9 (+ `BX`=ledger_adjustments); `{filial kodi}` = `branches.code`" |

---

## 3. `13-api-katalog-0-umumiy.md` — o'zgarishlar

### A0-01 · YUQORI · Resurs nomlash — ochiq savol yopiladi (Q1)
Asosiy xulosa #2 dagi qavs ichidagi izoh va "Ochiq savollar" #1 o'rniga: "*(2026-10-15: qabul-6 — QAROR: URL — kebab-case ko'plik; JSON maydon/query parametr/enum/`operation_id` — snake_case. `09-backend-arxitekturasi.md` §3 shunga moslashtirildi, `00-qarorlar.md` #24.)*". §2 ga band: "**JSON maydonlari — snake_case**, DB ustun nomi bilan aynan bir xil (`cash_register_id`, `doc_date`); camelCase ishlatilmaydi (frontend orval tiplari shu nomlarni oladi)."

### A0-02 · YUQORI · Xato konverti `params` (Q2)
§7.1 misolini almashtirish:
```json
{"error": {"code": "DEBT_LIMIT_EXCEEDED", "message_key": "errors.debt_limit_exceeded",
  "params": {"limit": "500000.00", "requested": "569000.00"},
  "details": [{"field": "payments[0].amount", "message_key": "errors.field.exceeds_credit_limit"}],
  "request_id": "01933a1e-..."}}
```
Izoh: "`details` — har doim massiv (maydon xatolari, bo'sh bo'lishi mumkin); `params` — ixtiyoriy obyekt, biznes konteksti (limit, so'ralgan qiymat, `resource`, `reason`, `expected_status`), i18next interpolatsiyasi uchun."

### A0-03 · YUQORI · §9 — POS hujjatlari va bir bosqichli hujjatlar (Q9)
"Istisno" bandidagi "`GET /sales/{id}/cancel` — Menejer tasdig'i bilan back-office'dan `sales.void`" **o'chiriladi**, o'rniga: "`sales`/`returns` back-office'da faqat o'qiladi (`GET /sales`, `GET /sales/{id}`, `GET /returns`, `GET /returns/{id}`); o'tkazilgan chek **bekor qilinmaydi** — xato faqat `return.created` bilan tuzatiladi (fiskal chek o'zgarmaydi). `sales.void` — faqat to'lovdan oldingi qoralama (`sale.draft_voided`, audit)." Yangi band: "**Bir bosqichli hujjatlar**: `supplier-payments`, back-office `cash-movements`, `ledger-adjustments` — `POST /{resurs}` darhol `status=posted` (`201`) qaytaradi, `draft` bosqichi yo'q; `cancel` mavjud. **Limitdan oshgan post** (har qanday hujjat): `202` + `{"status":"draft","approval_request_id":...}` (kod `APPROVAL_REQUIRED`), tasdiqlanganda server o'zi o'tkazadi (Q3)."

### A0-04 · O'RTA · §4 Pagination ro'yxati aniq (Q10)
Ma'lumotnoma qatoriga to'liq ro'yxat: "`products`, `product-categories`, `counterparties`, `discount-rules`, `roles`, `branches`, `warehouses`, `cash-registers`, `expense-categories`, `recurring-expenses`, `label-templates`, `units` (sahifasiz)". 13-1/13-2 dagi shu resurslar cursor'dan page'ga o'tkaziladi (A1-15, A2-16).

### A0-05 · O'RTA · §3 Narx aniqligi (Q14) va davr
"Narx/tannarx/foiz" qatorini: "Narx/tannarx: `price`, `cost`, `unit_cost`, `avg_cost`, `old_price`, `new_price`, `limit_value`, `requested_value` — 4 xona (`"8333.3333"`); foiz (`discount_pct`, `standing_discount_pct`, `vat_rate`) — 2 xona (`"5.00"`)". "Davr (oy)" qatoriga: "API `"YYYY-MM"` ↔ DB `DATE` (oyning 1-sanasi) — `vat_moves.period`, `period_closings.period`, `state_reports.period`, `ledger_adjustments.correction_of_period`".

### A0-06 · O'RTA · §12 Fayl yuklash — endpoint aniqlanmagan
13-3 `POST /attachments`ga havola qiladi, lekin hech qayerda ta'riflanmagan. §12 ga qo'shish: "`POST /attachments` — `multipart/form-data` (`file`, `kind`: `expense_receipt`/`ocr_source`/`state_report`/`import`/`other`), ruxsat — autentifikatsiya + `kind`ga mos modul ruxsati (masalan `ocr_source` → `ai.ocr.use`), `Idempotency-Key` majburiy; javob `201 {id, url, content_type, size_bytes}`. `GET /attachments/{id}` → `{id, url (signed, 15 daqiqa), content_type, original_name}`." Turlar ro'yxatiga `text/csv` qo'shiladi; Excel/CSV chegarasi **10 MB** (13-2 import bilan izchil; 5 MB → 10 MB).

### A0-07 · O'RTA · §7.2 HTTP statuslar to'liq emas
Jadvalga qatorlar: "`423 Locked` — `ACCOUNT_LOCKED`"; "`502 Bad Gateway` — tashqi tizim xato javob berdi (`FISCAL_SEND_FAILED`, `PAYMENT_PROVIDER_ERROR`)"; `503` qatoriga "AI, CRPT (`MARKING_VERIFY_UNAVAILABLE`), EDO operatori (`EINVOICE_PROVIDER_UNAVAILABLE`)".

### A0-08 · PAST · §1/Asosiy xulosa #1 — sync/auth base path
"auth (`/oauth/*`, `/auth/*`) va sync (`/sync/*`)" → "OAuth protokol yo'llari — ildizda (`/oauth/*`, `/.well-known/*`); ilova auth va sync — `/api/v1/auth/*`, `/api/v1/sync/*`" (13-1 va 12 §20 `/api/v1/auth/csrf` bilan izchil).

### A0-09 · PAST · §2 misollar
`/state-report-diffs` → `/state-reports/{id}/diffs` (13-3 shunday); yangi namunalar: `/approval-requests`, `/payments/checkouts`, `/ledger-adjustments`.

### A0-10 · YUQORI · §15 — xato kodlari katalogiga qo'shiladigan qatorlar
Format §15 jadvallari bilan bir xil. Bo'lim bo'yicha joylashtiriladi.

**15.2 Validatsiya va holat** (qo'shish):

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `DOC_INVALID_STATE` | 409 | `errors.doc_invalid_state` | Hujjat bu amal uchun mos holatda emas | Документ не в подходящем статусе для этого действия | Umumiy holat mashinasi xatosi; `params.expected_status`, `params.actual_status` |
| `RESOURCE_ARCHIVED` | 409 | `errors.resource_archived` | Bu yozuv arxivlangan | Эта запись в архиве | Arxivlangan ma'lumotnomani tahrirlash/qayta arxivlash; `params.resource` |
| `SYSTEM_ROLE_READONLY` | 409 | `errors.system_role_readonly` | Tizim rolining nomini o'zgartirib bo'lmaydi | Нельзя переименовать системную роль | `PATCH /roles/{id}`, `is_system=true` |
| `BARCODE_DUPLICATE` | 409 | `errors.barcode_duplicate` | Bu shtrix-kod boshqa tovarda bor | Этот штрихкод уже у другого товара | `UNIQUE (tenant_id, barcode)` |
| `CATEGORY_HAS_PRODUCTS` | 409 | `errors.category_has_products` | Toifada faol tovarlar bor, avval ularni ko'chiring | В категории есть активные товары, сначала перенесите их | Kategoriya arxivlash |
| `MXIK_CODE_INVALID` | 422 | `errors.mxik_code_invalid` | MXIK kodi 17 raqamdan iborat bo'lishi kerak | Код ИКПУ должен состоять из 17 цифр | Format xatosi |

**15.3 Ruxsat va tasdiqlash** (qo'shish):

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `APPROVAL_INVALID` | 403 | `errors.approval_invalid` | Tasdiq yo'q yoki tasdiqlovchining huquqi yetarli emas | Нет подтверждения или у подтверждающего недостаточно прав | `ApprovalRef` kutilgan, kelmagan / `approved_by` limiti qoplamaydi / `approval_request` boshqa hujjatda ishlatilgan (13-1 `PIN_REQUIRED` o'rniga) |
| `APPROVAL_REQUEST_ALREADY_RESOLVED` | 409 | `errors.approval_request_already_resolved` | So'rov allaqachon ko'rib chiqilgan | Запрос уже рассмотрен | Qayta approve/reject |
| `APPROVAL_REQUEST_EXPIRED` | 409 | `errors.approval_request_expired` | Tasdiqlash so'rovi muddati o'tgan, qayta yuboring | Срок запроса на подтверждение истёк, отправьте заново | `expires_at` o'tgan |

**15.4 Limitlar** (qo'shish / qayta nomlash):

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `WRITE_OFF_LIMIT_EXCEEDED` | 403 | `errors.write_off_limit_exceeded` | Hisobdan chiqarish summasi limitdan oshdi, tasdiq kerak | Сумма списания превышает лимит, нужно подтверждение | `stock.writeoff` limit |
| `EXPENSE_LIMIT_EXCEEDED` | 403 | `errors.expense_limit_exceeded` | Xarajat summasi limitdan oshdi, tasdiq kerak | Сумма расхода превышает лимит, нужно подтверждение | **`EXPENSE_APPROVAL_REQUIRED` o'rniga** (oila nomlashi bilan izchil) |

**15.5 Ombor/qoldiq** (qo'shish; `INSUFFICIENT_STOCK` ta'rifi aniqlashtiriladi):

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `INSUFFICIENT_STOCK` *(ta'rif yangilanadi)* | 422 | `errors.insufficient_stock` | Partiyada/omborda yetarli miqdor yo'q | Недостаточно количества в партии/на складе | `qty > stock_lots.qty_left` (yetkazib beruvchiga qaytarish, hisobdan chiqarish, ko'chirish); `params.lot_id`, `params.available` — 13-2 `SUPPLIER_RETURN_QTY_EXCEEDED`, `WRITE_OFF_QTY_EXCEEDS_LOT` o'rniga. Tenant siyosati xatosi — `NEGATIVE_STOCK_NOT_ALLOWED` |
| `STOCK_NEGATIVE` | 200 *(ogohlantirish — `warnings[]`)* | `warnings.stock_negative` | Qoldiq manfiyga tushdi, kirimni tekshiring | Остаток ушёл в минус, проверьте приход | Offline overselling (04 §5) — sotuv qabul qilinadi |
| `LOT_ALREADY_CONSUMED` | 409 | `errors.lot_already_consumed` | Bu kirim partiyasidan allaqachon chiqim bo'lgan, bekor qilib bo'lmaydi | Из партии этого прихода уже было списание, отмена невозможна | Kirimni bekor qilish |
| `BARCODE_NOT_IN_CATALOG` | 422 | `errors.barcode_not_in_catalog` | Shtrix-kod katalogda topilmadi | Штрихкод не найден в каталоге | Inventarizatsiya skaneri |
| `VALUATION_METHOD_CHANGE_NOT_ALLOWED` | 409 | `errors.valuation_method_change_not_allowed` | Baholash usuli bu yil uchun allaqachon o'zgartirilgan | Метод оценки на этот год уже изменён | `PATCH /valuation-settings` |

**Yangi 15.5a Kassa va smena**:

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `SHIFT_NOT_OPEN` | 409 | `errors.shift_not_open` | Smena ochiq emas | Смена не открыта | Yopiq/yo'q smenaga sotuv/pul harakati/xarajat |
| `SHIFT_ALREADY_OPEN` | 409 | `errors.shift_already_open` | Bu kassada smena allaqachon ochiq | На этой кассе смена уже открыта | `shift.opened`, `uq_shifts_one_open` |

**15.7 Fiskal/markirovka** (qo'shish):

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `MARKING_VERIFY_UNAVAILABLE` | 503 | `errors.marking_verify_unavailable` | Asl belgisi tizimi javob bermayapti, offline qoidasi qo'llanadi | Система «Асл белгиси» не отвечает, применяется офлайн-правило | CRPT timeout |
| `MARKING_RETURN_REQUIRES_ONLINE` | 422 | `errors.marking_return_requires_online` | Markirovkalangan tovarni faqat internet bor paytda qaytarish mumkin | Возврат маркированного товара возможен только онлайн | Qaror #17, 04 §7 (13-1 `MARKING_CODE_INVALID`+`reason` o'rniga) |

13-1 dagi `MARKING_CODE_INVALID` + `details.reason="already_sold"` → mavjud **`MARKING_CODE_ALREADY_SOLD`** ishlatiladi.

**15.8 E-faktura** (qo'shish; qayta nomlash):

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `EIMZO_SIGN_FAILED` | 422 | `errors.eimzo_sign_failed` | E-IMZO imzosi yaroqsiz (sertifikat/muddat) | Подпись E-IMZO недействительна | **`EINVOICE_SIGN_FAILED` o'rniga** — e-faktura va davlat hisoboti tuzatishida bir xil |
| `EINVOICE_NOT_ACCEPTED` | 409 | `errors.einvoice_not_accepted` | Faqat qabul qilingan fakturadan kirim yaratiladi | Приход создаётся только из принятой счёт-фактуры | `from-einvoice` |
| `EINVOICE_NOT_SIGNED` | 409 | `errors.einvoice_not_signed` | Avval E-IMZO bilan imzolang | Сначала подпишите через E-IMZO | `accept`/`send` imzosiz |
| `EINVOICE_ALREADY_SIGNED` | 409 | `errors.einvoice_already_signed` | Faktura allaqachon imzolangan | Счёт-фактура уже подписана | Takror imzo |
| `EINVOICE_PROVIDER_UNAVAILABLE` | 503 | `errors.einvoice_provider_unavailable` | E-faktura operatori vaqtincha ishlamayapti | Оператор ЭСФ временно недоступен | Faktura.uz/Didox, STIR qidiruvi |

**Yangi 15.8a Do'kon to'lovlari va xarid**:

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `PAYMENT_PROVIDER_ERROR` | 502 | `errors.payment_provider_error` | To'lov tizimi xato qaytardi, boshqa usulni tanlang | Платёжная система вернула ошибку, выберите другой способ | Checkout yaratish |
| `PAYMENT_NOT_CONFIRMED` | 422 | `errors.payment_not_confirmed` | To'lov hali tasdiqlanmagan | Платёж ещё не подтверждён | `sale.created`/`debt_payment.created` `checkout_ref`i `confirmed` emas (13-1 `PAYMENT_TIMEOUT` o'rniga — muddat o'tishi checkout holati `expired`) |
| `PURCHASE_ORDER_CLOSED` | 409 | `errors.purchase_order_closed` | Xaridnoma yopilgan yoki bekor qilingan | Заказ поставщику закрыт или отменён | PO'ga kirim/tahrir |
| `SUPPLIER_PAYMENT_EXCEEDS_DEBT` | 422 | `errors.supplier_payment_exceeds_debt` | To'lov summasi qarzdan ko'p | Сумма платежа превышает задолженность | Faqat `supplier_payment_strict=true` tenantda |

**Yangi 15.8b Import**:

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `IMPORT_FILE_INVALID` | 422 | `errors.import_file_invalid` | Fayl formati yoki kodlashi noto'g'ri | Неверный формат или кодировка файла | CSV/XLSX o'qilmadi (hajm — `FILE_TOO_LARGE`) |
| `IMPORT_JOB_NOT_VALIDATED` | 409 | `errors.import_job_not_validated` | Avval faylni tekshiring | Сначала проверьте файл | `commit` `validated`dan oldin |
| `IMPORT_JOB_ALREADY_COMMITTED` | 409 | `errors.import_job_already_committed` | Import allaqachon bajarilgan | Импорт уже выполнен | Takror `commit` |

**15.10 Sinxronizatsiya** (qo'shish):

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `DEPENDENCY_NOT_SYNCED` | 422 | `errors.dependency_not_synced` | Bog'liq yozuv hali sinxronlanmagan, keyinroq qayta yuboriladi | Связанная запись ещё не синхронизирована, будет повторено | `retryable: true`; `params.entity` (`counterparties`, `transfers`, `shifts`) — boshqa qurilmadan kelgan bog'liqlik (masalan `transfer.received`) |

**15.12 Davr** (qo'shish):

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `PERIOD_ALREADY_CLOSED` | 409 | `errors.period_already_closed` | Bu davr allaqachon yopilgan | Этот период уже закрыт | `POST /period-closings` takror (13-3 `VALIDATION_ERROR` o'rniga) |
| `PERIOD_CLOSE_NOT_READY` | 409 | `errors.period_close_not_ready` | Davrni yopib bo'lmaydi: tugallanmagan qayta hisoblash yoki yuborilmagan cheklar bor | Нельзя закрыть период: есть незавершённый пересчёт или неотправленные чеки | `params.blockers` |

**15.13 AI / 15.14 umumiy** (qo'shish):

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `OCR_IMAGE_UNREADABLE` | 200 *(job `error_code`)* | `errors.ocr_image_unreadable` | Rasmdan ma'lumot o'qib bo'lmadi, aniqroq suratga oling | Не удалось распознать изображение, сделайте более чёткий снимок | `ai_ocr_jobs.status=failed` |
| `NOTIFY_CONSENT_REQUIRED` | 422 | `errors.notify_consent_required` | Mijoz xabar olishga rozilik bermagan | Клиент не дал согласия на уведомления | AI-06 yuborish, `notify_consent=false` |

**O'chiriladigan/xaritalanadigan kodlar** (API fayllarida almashtiriladi, katalogga **qo'shilmaydi**):

| Ishlatilgan kod | Fayl | O'rniga |
|---|---|---|
| `PRODUCT_NOT_FOUND`, `CATEGORY_NOT_FOUND`, `PRICE_CHANGE_NOT_FOUND`, `LABEL_TEMPLATE_NOT_FOUND`, `OCR_DRAFT_NOT_FOUND`, `SUPPLIER_NOT_FOUND`, `GOODS_RECEIPT_NOT_FOUND`, `EINVOICE_NOT_FOUND`, `PURCHASE_ORDER_NOT_FOUND`, `SUPPLIER_RETURN_NOT_FOUND`, `TRANSFER_NOT_FOUND`, `STOCK_COUNT_NOT_FOUND`, `WRITE_OFF_NOT_FOUND`, `STOCK_OPENING_NOT_FOUND`, `RECOST_JOB_NOT_FOUND`, `MXIK_CODE_NOT_FOUND`, `COUNTERPARTY_NOT_FOUND` | 13-1, 13-2 | `NOT_FOUND` + `params.resource` |
| `PRICE_CHANGE_ALREADY_POSTED`, `GOODS_RECEIPT_ALREADY_POSTED` | 13-2 | `DOC_NOT_DRAFT` |
| `PRICE_CHANGE_NOT_PENDING`, `STOCK_COUNT_NOT_IN_REVIEW`, `TRANSFER_ALREADY_RECEIVED`, `RECOST_JOB_NOT_RETRYABLE`, `OCR_DRAFT_NOT_READY` | 13-2 | `DOC_INVALID_STATE` |
| `DOC_NOT_DRAFT` (state-reports compare/correction), `DOC_ALREADY_CANCELLED` (OCR confirm, kassa arxivi) | 13-3 | `DOC_INVALID_STATE` / `RESOURCE_ARCHIVED` |
| `PRODUCT_ARCHIVED` | 13-2 | `RESOURCE_ARCHIVED` |
| `SUPPLIER_RETURN_QTY_EXCEEDED`, `WRITE_OFF_QTY_EXCEEDS_LOT` | 13-2 | `INSUFFICIENT_STOCK` |
| `IMPORT_FILE_TOO_LARGE` | 13-2 | `FILE_TOO_LARGE` |
| `AI_UNAVAILABLE` | 13-2 | `AI_PROVIDER_UNAVAILABLE` |
| `PIN_REQUIRED` | 13-1 | ApprovalRef yo'q/yetarsiz → `APPROVAL_INVALID`; noto'g'ri PIN (`approve`) → `PIN_INVALID` |
| `FORBIDDEN` | 13-1, 13-2 | `PERMISSION_DENIED` |
| `PAYMENT_TIMEOUT` | 13-1 | checkout `status=expired` / `PAYMENT_NOT_CONFIRMED` |
| `EXPENSE_APPROVAL_REQUIRED`, `EINVOICE_SIGN_FAILED` | 13-0 | qayta nomlandi (yuqorida) |
| `STOCK_OPENING_PRODUCT_ALREADY_HAS_STOCK` | 13-2 | ishlatilmaydi — matndan o'chiriladi |
| `DEBT_NOT_FOUND` | 13-0 | `NOT_FOUND` (katalogdan o'chiriladi — izchillik) |

---

## 4. `13-api-katalog-1-kassa.md` — o'zgarishlar

### 4.1 Maydon ↔ ustun nomuvofiqliklari (vazifa 1)

| ID | Daraja | Joy | API maydoni | DDL | Qaror |
|---|---|---|---|---|---|
| A1-01 | KRITIK | §4.1 `sale.created` | `receipt_seq` **yo'q**; §4.5 javobda `fiscal_receipt_seq` server beradi | `fiscal_receipts.receipt_seq INT NOT NULL` (qurilma) | Payload'ga `receipt_seq` (int, majburiy, smena ichida ketma-ket) qo'shiladi; javobdagi `fiscal_receipt_seq` — qurilmaniki aks-sadosi. 04 §2 "`fiscal.receipt_seq` qurilma beradi" bilan izchil |
| A1-02 | KRITIK | §7.1 `return.created` | `receipt_seq`, `cash_register_id`, `is_offline` yo'q; `counterparty_id` yo'q | DB-03 | Payload'ga `receipt_seq`, `cash_register_id`, `is_offline`, `counterparty_id` (`debt_adjustment`da majburiy); `lines[]`ga `vat_rate`, `vat_exemption_code` |
| A1-03 | KRITIK | §12.2 `debt_payment.created` | `method` 6 qiymat; `shift_id`/`cash_register_id`/`branch_id` yo'q | DB-04: `cash` → register+shift majburiy | Payload'ga `branch_id`, `cash_register_id`, `shift_id` (`method=cash`da majburiy), `checkout_ref` (elektron usulda); `note` → `comment` |
| A1-04 | YUQORI | §3.1 `shift.opened` | `shift_no` yo'q; `comment` | DB-07 | `shift_no` (int, majburiy, qurilma) qo'shiladi; javob `{id, shift_no}` |
| A1-05 | YUQORI | §3.2/§3.3 | javobda `number`; `variance` | `shifts`da `number` yo'q; `diff_amount` | `number` → `shift_no`; `variance` (DB-07 nomi shu) |
| A1-06 | YUQORI | §4.1 `lines[].unit_price` | `Money` (2 xona) | `sale_lines.price NUMERIC(18,4)` | `unit_price` → **`price`**, 4 xonali satr (Q14) |
| A1-07 | YUQORI | §4.1 `lines[].vat_rate` | "`12`/`0`/imtiyoz kodi" bitta maydon | `vat_rate` + `vat_exemption_code` | Ikki maydon: `vat_rate` (`"12.00"`/`"0.00"`), `vat_exemption_code` (string\|null) |
| A1-08 | YUQORI | §4.1 `discount_source` | `"rule:{discount_rule_id}"` satr | DB-08 | `discount_source` (`manual`/`standing_customer`/`rule`) + `discount_rule_id` (UUID\|null); `discount_pct` va `discount_amount` birga **kelishi mumkin** (server `discount_amount`ni manba deb oladi, `discount_pct` limit tekshiruvi uchun) |
| A1-09 | YUQORI | §4.1 `payments[]` | nasiya muddati yo'q | `debt_moves.due_date` manbasiz | `payments[].due_date` (ISO sana, `method=debt`da ixtiyoriy), `payments[].checkout_ref` |
| A1-10 | YUQORI | §4.3 | `debt_moves.limit_exceeded=true` | registr append-only, ustun yo'q | "`sales.debt_limit_exceeded=true`" deb o'zgartiriladi |
| A1-11 | O'RTA | §4.1 `lines[].unit_code` | — | `sale_lines`da yo'q | Hosila (faqat validatsiya, `products.unit_code`ga teng bo'lishi shart); saqlanmaydi — izoh qo'shiladi. `line_no` = massiv indeksi+1 (server), `line_total`/`vat_amount`/`cost_amount` — server hisoblaydi (qurilma qiymatini tekshiradi) |
| A1-12 | O'RTA | §12.1 `debt-ledger` | `entries[].promise_date`, `note`, `status` | `debt_payments.promise_date` (DB-04), `comment` | Hosila: `promise_date` — oxirgi `debt_payments.promise_date` yoki `sale_payments.due_date`; `status` — allokatsiyalardan (01 §8 nasiya mashinasi); `note` → `comment` |
| A1-13 | O'RTA | §12.2 javob | `allocations: [{debt_move_id, amount}]` | `debt_payment_allocations(target_doc_type, target_doc_id)` | `allocations: [{target_doc_type, target_doc_id, amount}]` |
| A1-14 | O'RTA | §12.4/§12.5 | `due_date`; `account_hint`; `reason` | DB-24 | `account_hint` → `account_choice` (standart `"9430"`); `reason` → `debt_writeoffs.reason`; `debt-openings` ruxsati — **`stock.opening.manage`** (aralash matn o'rniga) |
| A1-15 | O'RTA | §0, §8.2, §11.3 | cursor hamma joyda | — | `counterparties`, `discount-rules` — page pagination (Q10); vaqt misoli `+05:00` → UTC `Z` (13-0 §3) |
| A1-16 | O'RTA | §13.1 | `note` | `cash_movements.comment` | `note` → `comment` (`reason=other`da majburiy) |
| A1-17 | O'RTA | §9.1 sxema | `requested_by/at`, `kind` (6 tur) | DB-09 | `kind`ga `expense_over_limit`, `write_off_over_limit`; javob/so'rovga `permission_code` (server to'ldiradi), `requested_value`; `status`ga `consumed` |
| A1-18 | PAST | §11.2 | `notify_consent` | + `notify_consent_at` | Server `true` bo'lganda vaqtni yozadi (hosila) |

### 4.2 Dizayn ziddiyatlari

- **A1-19 · YUQORI · §10 narx o'zgarishi** — §10 to'liq matni o'rniga: "Narx o'zgarishi hujjati — `13-api-katalog-2-ombor.md` §4 (yagona manba). Limitdan katta o'zgarish `POST /price-changes/{id}/post` → `202 {status:"pending_approval", approval_request_id}`; tasdiq/rad — faqat 9-bo'lim (`approval-requests`, `kind=price_change`)."
- **A1-20 · YUQORI · §16 to'lov yo'llari (Q12)** — `POST /api/v1/payments/{provider}/checkout` → `POST /api/v1/payments/checkouts` (body'da `provider`); `GET /api/v1/payments/{provider}/{provider_tx_id}` → `GET /api/v1/payments/checkouts/{checkout_ref}`; `POST /api/v1/webhooks/{provider}` → `POST /api/v1/payments/webhooks/{provider}`; body'dan `context` olib tashlanadi (faqat do'kon); body'ga `cash_register_id`; javob `{checkout_ref, provider, provider_tx_id\|null, qr_payload\|checkout_url, status, expires_at}`. Webhook tenantni `payments_checkout_by_provider_tx()`/`payments_checkout_by_ref()` orqali topadi (DB-30).
- **A1-21 · YUQORI · §2.4 ApprovalRef** — "server validatsiyasi" bandiga: "`approval_request_id` faqat `status=approved` va hali `consumed` bo'lmagan bo'lsa qabul qilinadi; postingda `consumed` ga o'tadi va `doc_approvals` qatori yoziladi. Xato — `APPROVAL_INVALID`." `PIN_REQUIRED` hamma joyda → `APPROVAL_INVALID`; §9.4 noto'g'ri PIN → `PIN_INVALID`.
- **A1-22 · YUQORI · §9.3 navbat filtri — kind → tasdiqlovchi ruxsati xaritasi** (BO-16 kim nimani ko'radi):

| `kind` | Tasdiqlovchi ruxsati (`permission_code`) | Limit solishtiriladigan |
|---|---|---|
| `discount_over_limit` | `discount.approve` | foiz |
| `return_over_limit`, `return_no_receipt` | `returns.approve` | summa (no_receipt — limitsiz, har doim) |
| `debt_over_limit` | `debts.approve` | summa |
| `cash_withdrawal_over_limit` | `cash.withdraw` (so'ralgan summadan yuqori `limit_value` yoki limitsiz) | summa |
| `price_change` | `prices.approve` | foiz |
| `expense_over_limit` | `expenses.approve` | summa |
| `write_off_over_limit` | `stock.writeoff` (yuqori limit yoki limitsiz) | summa |

- **A1-23 · YUQORI · §1 indeks — yetishmayotgan endpoint'lar**: `GET /api/v1/sales` (filtr `branch_id`, `shift_id`, `doc_date__gte/lte`, `status`, `counterparty_id`; cursor; ruxsat `reports.sales.view`) va `GET /api/v1/sales/{id}` (qatorlar, to'lovlar, fiskal holat, qaytarilgan miqdorlar hosila). `POST /sales/{id}/cancel` **qo'shilmaydi** (Q9).
- **A1-24 · KRITIK · Chiquvchi e-faktura bo'limi yo'q** (BP-03 B2B nasiya, BP-13 / qaror #18, 02 §2.22). Yangi bo'lim "§15a Chiquvchi e-faktura":
  - `POST /api/v1/einvoices` — body `{direction:"out", counterparty_id, related_doc_type:"sales", related_doc_id, doc_date, lines?}` → `201 {id, status:"draft"}`; ruxsat `einvoice.create`; xatolar `EINVOICE_ALREADY_LINKED`, `EINVOICE_AMOUNT_EXCEEDS_RECEIPT`, `EINVOICE_COUNTERPARTY_INCOMPLETE`.
  - `POST /api/v1/einvoices/from-sale/{sale_id}` — chekdan oldindan to'ldirilgan qoralama (qaytarishlar ayirilgan holda); ruxsat `einvoice.create`.
  - `POST /einvoices/{id}/sign-challenge`, `POST /einvoices/{id}/submit-signed` — 13-2 §19 dagi bilan **bir xil** (umumiy, yo'nalishdan qat'i nazar); ruxsat `einvoice.sign`.
  - `POST /api/v1/einvoices/{id}/send` → `202`, `outbox_jobs(kind=einvoice_send)`; `POST /api/v1/einvoices/{id}/cancel` (operator qoidasi bo'yicha); `GET /api/v1/einvoices?direction=out`.
  - Provodka **yo'q** (02 §2.22); `uq_einvoice_out_per_doc` (DB-21).
- **A1-25 · O'RTA · §14.2 qayta urinish ruxsati** — `billing.manage` → **`integrations.retry`** (P-04); "Ochiq savollar" #2 yopiladi.
- **A1-26 · O'RTA · §12.8 vs 13-3 #21 takror** — `GET /api/v1/reports/debt-aging` o'chiriladi, 13-3 `GET /reports/debts-aging`ga havola; maydonlar birlashtiriladi (A3-08).
- **A1-27 · O'RTA · §13.2 vs 13-3 #52** — `GET /cash-movements` 13-3 da yagona ta'rif; ruxsat ikkalasida `reports.sales.view` **yoki** `cash.count.shift` (13-3 `cash.deposit` noto'g'ri — Omborchi/Buxgalter ko'ra olmaydi, kassir esa barcha kassalarni ko'radi).
- **A1-28 · O'RTA · §2.2 PushResultEntry** — jadvalga `warnings` (string[], katalog kodlari, masalan `STOCK_NEGATIVE`, `DEBT_LIMIT_EXCEEDED`) qatori; §4.3/§4.7 dagi `server.warnings` → entry darajasidagi `warnings`.
- **A1-29 · O'RTA · §15 markirovka yo'li** — `POST /api/v1/marking/verify` → `POST /api/v1/marking-codes/verify` (resurs nomi jadvaldan); javobdagi `details.reason` → mos alohida kodlar (`MARKING_CODE_ALREADY_SOLD`, `MARKING_CODE_INVALID`).
- **A1-30 · O'RTA · §18 "Ma'lumotlar modeliga qo'shimchalar"** bo'limi o'rniga: "Hal qilindi — `tekshiruv/qabul-6-api-db.md` DB-03, DB-04, DB-07…DB-11, DB-28; #9 (`verify_source`) va #10 (`last_retry_*`) **rad etildi** (audit_log yetarli)."
- **A1-31 · PAST · §19** — jadval 13-0 katalogiga havola bilan almashtiriladi (A0-10 xaritasi bo'yicha nomlar yangilanadi).

---

## 5. `13-api-katalog-2-ombor.md` — o'zgarishlar

| ID | Daraja | Joy | Muammo | O'zgarish |
|---|---|---|---|---|
| A2-01 | YUQORI | §8 `/purchase-ocr-drafts`, `/goods-receipts/from-ocr-draft/{id}` | 13-3 `/ai/ocr/jobs` bilan takror; 13-0 §12 ikki bosqichli naqshni buzadi (`multipart image` to'g'ridan-to'g'ri) | Ikkala endpoint **o'chiriladi**; "AI-03 — `13-api-katalog-3` #73–75 (`/ai/ocr/jobs`), `confirm` `goods_receipts` qoralamasini yaratadi" havolasi. Javob namunasidagi `fields` shakli 13-3 ga ko'chiriladi (Q4), `status:"ready"` → `"done"`. 2-band ("`purchase_ocr_drafts` jadvali") — rad, `ai_ocr_jobs` (DB-13) |
| A2-02 | YUQORI | §4 `/price-changes/{id}/approve`, `/reject` | 13-1 `approval-requests` bilan ikki xil oqim | O'chiriladi; `post` limitdan katta bo'lsa `202 {status:"pending_approval", approval_request_id}`; tasdiq — `POST /approval-requests/{id}/approve`. "Menejer ham" matni o'chiriladi (05 §2.2: `prices.approve` faqat Egasi) |
| A2-03 | YUQORI | §4 `POST /price-changes` | `new_price decimal(2dp)`; qator `valid_from` yo'q | `lines[].new_price` — 4 xonali (Q14); `lines[].valid_from` (timestamptz\|null); javobdan `version` olib tashlanadi (Q13) |
| A2-04 | YUQORI | §8 `POST /goods-receipts` | `paid_immediately` yo'q (02 §2.6/§2.8 yo'lini tanlaydi); `vat_rate` enum | Body'ga `paid_immediately` (bool, standart `false`), `lines[].vat_exemption_code`; `vat_rate` → `"12.00"`/`"0.00"`; `from-einvoice` `source='einvoice'`, `einvoice_id` saqlaydi (DB-06); javobdan `version` olib tashlanadi |
| A2-05 | PAST | §8 `post` javobi | `number:"K-01-2026-000154"` (K = sotuv) | `"M-01-2026-000154"` (14 §2.9: M = goods_receipts) |
| A2-06 | YUQORI | §9 `/suppliers` | `/counterparties` bilan takror CRUD (Q6) | Bo'lim "Yetkazib beruvchilar — `/counterparties?is_supplier=true`" ga qisqaradi: `POST /counterparties` (`is_supplier=true` → ruxsat `purchases.create`), `GET /counterparties/{id}/debt-balance` → `{payable, receivable}`, `POST /counterparties/lookup-by-stir` body `{stir}` (yaratishdan **oldin** ham ishlaydi; javob — taklif, saqlamaydi) |
| A2-07 | YUQORI | §10 `purchase-orders` | `warehouse_id` DDL'da yo'q; `price` ixtiyoriy | DB-15; javob `status` — **saqlangan** ustun (hisoblanadigan emas), `received_lines` hosila |
| A2-08 | YUQORI | §11 `supplier-payments` | `source`; `cash_register_id`; `allocations[].receipt_id` | `source` → **`method`**; `shift_id` (`method=cash`da majburiy); `allocations[]` → `{target_doc_type:"goods_receipts", target_doc_id, amount}`; bir bosqichli hujjat sifatida 13-0 §9 ga havola (A0-03) |
| A2-09 | O'RTA | §12 `supplier-returns` | `reason` sarlavhada (DDL'da yo'q); `lines[].lot_id` | DB-25 (`supplier_returns.reason`); qator `cost`/`vat_amount` — server asl kirim qatoridan oladi (hosila); xato `INSUFFICIENT_STOCK` |
| A2-10 | YUQORI | §13 `transfers` | REST body'da `client_event_id`; offline voqea nomi `transfer.created`; ko'p partiya | `client_event_id` REST'dan **o'chiriladi** (faqat sync voqeasi); voqealar `transfer.sent` / `transfer.received` (S-01) — payload: `transfer.sent` = `{id, temp_number, doc_date, from_warehouse_id, to_warehouse_id, lines:[{line_id, product_id, qty_sent}]}`; `transfer.received` = `{transfer_id, lines:[{transfer_line_id, qty_received}]}`; javobda `lines[].lot_allocations`, `unit_cost` (DB-16). Boshqa qurilmadagi jo'natma hali kelmagan bo'lsa — `DEPENDENCY_NOT_SYNCED` (retryable) |
| A2-11 | O'RTA | §14 `stock-counts` | `stock_count.line_recorded` payload hech qayerda ta'riflanmagan (13-1 "M04/M05 API hujjatida" deydi) | Yangi band: payload `{count_id, product_id, counted (Qty — shu qurilmadagi **mutlaq** son), barcode?, recorded_at}`; MVP: bitta inventarizatsiya — bitta qurilma (`stock_counts.device_id`), boshqa qurilmadan → `SHIFT_DEVICE_MISMATCH` o'rniga `DOC_INVALID_STATE` (`params.reason='count_device_mismatch'`). `post`da `expected` qayta hisoblanadi (sanash davomidagi sotuvlar uchun) — ochiq savolga qo'shiladi |
| A2-12 | O'RTA | §15 `write-offs` | `reason` sarlavhada, DDL qatorda; `lot_id` majburiy | `reason` → `lines[].reason`; `lines[].lot_id` **ixtiyoriy** (yo'q bo'lsa server FIFO bo'yicha taqsimlaydi); limitdan katta → `202 APPROVAL_REQUIRED` (`kind=write_off_over_limit`) — "Ochiq savollar" #1 yopiladi; `responsible_user_id` → DB-25 |
| A2-13 | O'RTA | §17 `valuation-settings` | `"AVECO"\|"FIFO"` katta harf (13-0 §3: enum = DB qiymati, kichik); saqlash joyi yo'q | `"aveco"`/`"fifo"`; `valuation_method_history` (DB-26); `GET` javobi `{current_method, effective_from, pending_change}` shu jadvaldan |
| A2-14 | O'RTA | §17 `stock-settings` | saqlash joyi aniqlanmagan | "`tenants.settings` kalitlari (M-03)"; `PATCH` `version` = `tenants.version` |
| A2-15 | O'RTA | §6 `import-jobs` | `validate` javobi `queued` — DDL holatlari yo'q; hajm 10 MB vs 13-0 5 MB | Holatlar `validating`/`committing` (DB-29); `commit` javobi `created_doc_ids` — `import_jobs.result`; 13-0 chegarasi 10 MB ga ko'tariladi (A0-06) |
| A2-16 | O'RTA | §1, §2, §5 | cursor pagination ma'lumotnomalarda | `products`, `product-categories`, `label-templates` — page (Q10) |
| A2-17 | O'RTA | §1 `Product` sxemasi | `vat_rate` enum "imtiyoz kodi" | `vat_rate` + `vat_exemption_code`; `mxik_code` null (DB-23); `POST /products` → `stock.view`ga emas, `catalog.manage`ga (bor) |
| A2-18 | O'RTA | §5 `label-print-jobs` | job jadvali yo'q | `outbox_jobs(kind=label_pdf)` (Q8, DB-19); `label-templates` → `platform.label_templates` (DB-27) |
| A2-19 | O'RTA | §8 `cancel` izohi | "Mobil skaner (POS-08) orqali qabul qilish `/sync/push` outbox yo'li bilan" — bunday voqea turi yo'q, Asosiy xulosa #7 ga zid | Jumla o'chiriladi: kirim — faqat online REST (POS-08 online rejimda shu REST'ni chaqiradi) |
| A2-20 | O'RTA | §19 `einvoices` | ro'yxatdagi `amount`, `vat_amount` | DB-21 (`total_amount`, `vat_amount`); `EINVOICE_SIGN_FAILED` → `EIMZO_SIGN_FAILED`; kiruvchi holat `received` |
| A2-21 | O'RTA | "Ma'lumotlar modeliga qo'shimchalar" | — | O'rniga: "Hal qilindi — qabul-6: #1 → P-01…P-03; #2 → rad, DB-13; #3 → sarlavha darajasida DB-25; #4 → DB-06; #5 → DB-27" |
| A2-22 | PAST | Xato kodlari jadvali | A0-10 xaritasi | Jadval 13-0 ga havola + faqat shu faylda ishlatiladigan kodlar ro'yxati (nomlari yangilangan) |

---

## 6. `13-api-katalog-3-moliya-admin.md` — o'zgarishlar

| ID | Daraja | Joy | Muammo | O'zgarish |
|---|---|---|---|---|
| A3-01 | KRITIK | M17 #61 + lokaut | `POST /billing/checkout` lokautda `require_subscription_ok` tomonidan bloklanadi — exempt ro'yxatida faqat `/billing/pay` (09 §3, 12 §16.1) | #56, #57, #58, #61 va `/billing/webhooks/*` jadvalidagi "Offline/izoh"ga: "**Lokautda ochiq** (`restricted` holatida ham) — `require_subscription_ok` istisnosi (09 §3, 12 §16.1)". B-02 bilan birga |
| A3-02 | YUQORI | #61 javobi | `provider_tx_id` checkout paytida noma'lum (Payme `CreateTransaction`da beradi) | Javob `201 {payment_id, checkout_url, amount, period}`; `billing_payments(status='pending')` yaratiladi; Click `merchant_trans_id` = `payment_id` (DB-18, `billing_payment_by_id()`) |
| A3-03 | YUQORI | M17 indeks | D2 qarori (#20) — `/billing/export-my-data` yo'q | Platforma admin havolasi kabi havola qatori: "`POST/GET /billing/export-my-data` — 12 §16.5 (SMS OTP, bir martalik token); lokautda ochiq" |
| A3-04 | YUQORI | #10 `POST /ledger-entries/adjustments` | hujjat yo'q (DB-12) | Yo'l → `POST /ledger-adjustments` (bir bosqichli, `201 status=posted`), `POST /ledger-adjustments/{id}/cancel`, `GET /ledger-adjustments`; body `{doc_date, account_dt, account_kt, amount, comment, correction_of_period?}` (`entry_date` → `doc_date`) |
| A3-05 | O'RTA | #9 `GET /ledger-entries` | filtr `doc_date__*` — ustun `entry_date` | `entry_date__gte/lte`; `branch_id` — DB-12 ustuni |
| A3-06 | YUQORI | #43, #53 | `202 {status:"pending_approval"}` — `expenses`/`cash_movements` holatlarida yo'q | Q3: `202 {status:"draft", approval_request_id}` (`APPROVAL_REQUIRED`); `EXPENSE_APPROVAL_REQUIRED` → `EXPENSE_LIMIT_EXCEEDED`; `kind=expense_over_limit` / `cash_withdrawal_over_limit` |
| A3-07 | YUQORI | #42 `POST /expenses` | `doc_date` yo'q (DDL NOT NULL); `branch_id` | Body'ga `doc_date` (majburiy, standart bugun); `branch_id` = `X-Branch-Id`; `source=cash` offline — `expense.created` voqeasi (S-01) |
| A3-08 | O'RTA | #21 `/reports/debts-aging` | 13-1 #26 bilan takror | Yagona; so'rov `?direction=&as_of=&branch_id=&limit_exceeded_offline=`; javob `rows[]`ga `overdue_since`, `limit_exceeded_offline`, `doubtful_flag`; ruxsat `reports.finance.view` **yoki** `debts.approve` |
| A3-09 | O'RTA | #48–#51 recurring | `period` qiymatlari, `active`, `next_due_at` | DB-17: `period` `month/quarter/year`; `active` → **`is_active`**; `next_due_at` → `next_due_date` (DATE); `name` ixtiyoriy; `branch_id` — header; #51 `source=cash` → ochiq smena kerak, aks holda `SHIFT_NOT_OPEN` |
| A3-10 | O'RTA | #47 `PATCH /expense-categories` | `version` — DDL'da yo'q | DB-33 (`version` qo'shiladi) |
| A3-11 | O'RTA | #40 `PATCH /cash-registers` | `version` yo'q; `archived` bool; xato `DOC_ALREADY_CANCELLED` | `version` majburiy; arxiv — `POST /cash-registers/{id}/archive` (13-2 naqshi); xato `RESOURCE_ARCHIVED`; `ofd_status` qiymatlari DB-33 |
| A3-12 | O'RTA | #60 `DELETE /billing/addons/{code}` tana bilan | DELETE tanasi HTTP'da semantikasiz, proksi/orval tashlab yuborishi mumkin | `POST /billing/addons/{addon_code}/reduce` body `{quantity}` |
| A3-13 | O'RTA | #73–#75 AI-03 | `doc_type_hint: "return"` (qaytarish faqat POS/sync, 13-0 §9); natija shakli 13-2 bilan farq; `confirm` body erkin | `doc_type_hint` faqat `"purchase"`; #74 javobi: `{job_id, status: processing\|done\|failed\|confirmed\|expired, fields: {header:{...}, lines:[...]}, low_confidence_fields:[...], error_code}` (`confidence` 0..1); #75 body — `POST /goods-receipts` shakli (`supplier_id, warehouse_id, doc_date, paid_immediately, lines[...]`), ruxsat `ai.ocr.use` **va** `purchases.receive`; javob `{created_doc_type:"goods_receipts", created_doc_id}`; takror → `DOC_INVALID_STATE` |
| A3-14 | O'RTA | #77–#78 AI-06 | `ai.chat.use` mijozga xabar yuborishni himoya qiladi | #77 — `ai.chat.use` + `debts.remind`; #78 — `debts.remind` (P-06); `notify_consent=false` → `NOTIFY_CONSENT_REQUIRED` |
| A3-15 | O'RTA | #4, #8 state-reports | `DOC_NOT_DRAFT` holat xatosi sifatida; `EINVOICE_SIGN_FAILED` | `DOC_INVALID_STATE`; `EIMZO_SIGN_FAILED`; javob maydonlari DB-20 ustunlaridan |
| A3-16 | O'RTA | #15 | allaqachon yopilgan → `VALIDATION_ERROR` | `PERIOD_ALREADY_CLOSED` |
| A3-17 | O'RTA | #26 | `DOC_NOT_DRAFT` *(...`SYSTEM_ROLE_READONLY`, yangi)* | Faqat `SYSTEM_ROLE_READONLY` |
| A3-18 | O'RTA | #31 `POST /branches` | `code` (DB-02) | Body'ga `code` (ixtiyoriy; bo'sh bo'lsa server keyingi ikki xonali raqamni beradi); javobda `code` |
| A3-19 | O'RTA | #55 cash-history | `diff`, `card_total` | `variance`, `counted_card_total` (DB-07) |
| A3-20 | O'RTA | #52 ruxsat | `cash.deposit` | `reports.sales.view` yoki `cash.count.shift` (A1-27) |
| A3-21 | O'RTA | #53 body | `comment` yo'q (`reason=other`da kerak) | `comment` (shartli majburiy), `doc_date` |
| A3-22 | PAST | #1, #2 yo'llari | `/vat/summary`, `/vat/moves` — 13-0 §2 qoidasidan tashqari | `/reports/vat-summary` (eksport kodi bilan bir xil), `/vat-moves`; `doc_type` filtri qiymatlari — jadval nomlari (Q7) |
| A3-23 | PAST | #22 report-kod | `debts-aging` | ro'yxat o'zgarmaydi; A3-08 bilan izchil |
| A3-24 | PAST | "Ma'lumotlar modeliga qo'shimchalar" | — | O'rniga: "Hal qilindi — qabul-6: #1 → DB-19; #2 → DB-17; #3 → DB-18 (ustunlar, alohida jadval rad); #4 → DB-13 (`purchase_ocr_drafts` bilan birlashtirildi); #5 → DDL'da allaqachon bor, 01 M-06; #6 → M-03 (`vat_diff_tolerance_amount`)" |

---

## 7. `05-xavfsizlik-va-audit.md` — ruxsatlar (vazifa 5)

API fayllarida ishlatilgan, §2.1 katalogida **yo'q** kodlar (va noto'g'ri ishlatilganlar o'rniga yangi kodlar).

### P-01…P-06 · YUQORI · §2.1 jadvaliga qo'shiladigan qatorlar
| Kod | Modul | Ma'nosi | Limit |
|---|---|---|---|
| `catalog.manage` | M09 | Mahsulot/kategoriya/shtrix-kod (ichki kod generatsiyasi) CRUD, mahsulot importi, ombor sozlamalari (`stock-settings`) *(2026-10-15: qabul-6)* | — |
| `stock.opening.manage` | M04, M08 | Boshlang'ich tovar qoldig'i va boshlang'ich qarz (qo'lda va `import-jobs`) *(qabul-6)* | — |
| `valuation.settings.manage` | M04, M11 | FIFO/AVECO usulini almashtirish (faqat keyingi yildan) *(qabul-6)* | — |
| `integrations.retry` | M01, M07, M10 | OFD/e-faktura/markirovka integratsiya ishini qo'lda qayta navbatga qo'yish (BO-14) *(qabul-6)* | — |
| `einvoice.create` | M01, M08, M10 | Chiquvchi e-faktura qoralamasini yaratish va yuborish (B2B, chekdan keyin — BP-03/BP-13) *(qabul-6)* | — |
| `debts.remind` | M08, AI-06 | Mijozga qarz eslatmasini yuborish (Telegram/SMS) *(qabul-6)* | — |

### §2.2 matritsaga qo'shiladigan qatorlar
| Ruxsat | Egasi | Menejer | Kassir | Omborchi | Buxgalter | Asos |
|---|---|---|---|---|---|---|
| `catalog.manage` | ✓ | ✓ | – | ✓ | – | Omborchi kirimda yangi tovar/shtrix-kod yaratadi (`purchases.receive` faqat unda); narxni o'zgartirmaydi (`prices.edit` yo'q) — 13-2 taklifidan farqli Omborchi qo'shildi |
| `stock.opening.manage` | ✓ | ✓ | – | – | ✓ | Boshlang'ich qarz — buxgalteriya kirishi (02 §2.13/§2.21) |
| `valuation.settings.manage` | ✓ | – | – | – | ✓ | 13-2 taklifi o'zgarishsiz |
| `integrations.retry` | ✓ | ✓ | – | – | ✓ | `billing.manage` (faqat Egasi) o'rniga — fiskal muammoni Menejer ham hal qilishi kerak |
| `einvoice.create` | ✓ | ✓ | – | – | ✓ | Imzo baribir `einvoice.sign` (Buxgalter) |
| `debts.remind` | ✓ | ✓ | – | – | ✓ | AI-06 "Menejer/Buxgalter tasdiqlaydi" (13-3 #78) |

### P-07 · O'RTA · §2.3 ga band — "Tasdiqlash turi → tasdiqlovchi ruxsati" jadvali
A1-22 dagi jadval §2.3 ning 3-bandi ostiga ko'chiriladi (yagona manba; 13-1 havola qiladi). Qo'shimcha qoida: "Tasdiqlovchi so'rovchining o'zi bo'la olmaydi; bitta `approval_request` bitta hujjatda bir marta ishlatiladi (`consumed`)."

### P-08 · PAST · Matritsa bo'shliqlari (qabul doirasidan tashqari, faqat qayd)
Egasi ustunida `sales.create`, `shift.open/close`, `cash.count.shift`, `stock.count.create`, `accounting.post` — `–`. Kichik do'konda Egasi ko'pincha o'zi sotadi; Egasi rolining "barcha ruxsat" bo'lishi (yoki kamida operatsion kodlar) mahsulot egasi bilan tasdiqlanishi tavsiya etiladi. API shu matritsaga bog'liq — o'zgarmasa, Egasi `GET /ledger-entries` (13-3 #9, `accounting.post`) ni ham ko'ra olmaydi.

---

## 8. `09-backend-arxitekturasi.md` (vazifa 6)

### B-01 · YUQORI · §3 "Resurs nomlash" qatori — **QAROR: kebab-case URL + snake_case JSON**
Joriy qator: `| Resurs nomlash | Ko'plik, kebab emas snake: \`/sales\`, \`/sale-returns\` emas \`/returns\` (hujjat turi bo'yicha, 01-malumotlar-modeli jadval nomlariga mos) |`

Almashtiriladigan matn:
```
| Resurs nomlash | URL yo'li — **kebab-case, ko'plik ot**, `01-malumotlar-modeli.md` jadval nomidan `_` → `-` (`goods_receipts` → `/goods-receipts`, `debt_writeoffs` → `/debt-writeoffs`); hujjat turi bo'yicha alohida resurs (`/returns`, `/sale-returns` emas). Holat o'tkazuvchi amallar — `/{resurs}/{id}/{fe'l}` (`post`, `cancel`, `receive`, `submit-for-review`). **JSON maydonlari, query parametrlari, enum qiymatlari va `operation_id` — snake_case**, DB ustun nomi bilan aynan bir xil (`cash_register_id`, `?doc_date__gte=`, `"posted"`, `goods_receipts_post`). Batafsil — `13-api-katalog-0-umumiy.md` §2 *(2026-10-15: qabul-6 — kebab URL qarori, 00-qarorlar #24)* |
```
Asos: URL'da kebab — REST/HTTP keng tarqalgan amaliyoti (Google AIP-122, Microsoft REST guidelines), brauzer/log o'qilishi; JSON'da snake — Pydantic modeli SQLAlchemy ustunlari bilan alias'siz 1:1, orval TypeScript tiplari ham shu nomlarni oladi; `operation_id` snake — Python funksiya nomi. Ikki qoida bir-biriga zid emas (turli qatlam).

### B-02 · KRITIK · §3 middleware tartibi — lokaut istisnolari
"(istisnolar: `/auth/*`, `/billing/pay`, ..." matni → "(istisnolar: `/auth/*`, `/billing/pay` (BFF sahifa), **`GET /billing/plan`, `GET /billing/subscription`, `GET /billing/addons`, `POST /billing/checkout`, `GET /billing/payments`, `/billing/webhooks/*`** (o'z imzo tekshiruvi bilan), `/billing/export-my-data` (OTP bilan, D2), `/sync/push` faqat `scope=sync.drain` ..." — aks holda lokautdagi tenant to'lov qila olmaydi. Xuddi shu ro'yxat `12-autentifikatsiya-oauth2.md` §16.1 (295-qator) va §20 jadvaliga ko'chiriladi.

### B-03 · O'RTA · §3 "Xato formati" qatori
`{"code": ..., "details": {...}}` → "`{"error": {"code", "message_key", "params", "details", "request_id"}}` — `details` har doim massiv (`[{"field","message_key"}]`), `params` — biznes konteksti obyekti; to'liq katalog — `13-api-katalog-0-umumiy.md` §15" (Q2).

### B-04 · PAST · §3 "Optimistik qulflash" qatori
"(faqat teskari hujjat)" → "(`posted`dan keyin — faqat `cancel` + storno qatorlar; alohida teskari hujjat yo'q, 00-qarorlar #6)".

---

## 9. `04-offline-sync.md` — voqea turlari (vazifa 8)

### S-01 · YUQORI · §2 `type` enum — yakuniy ro'yxat
13-1 ro'yxati 04 bilan solishtirildi: 04'da bor 9 tur 13-1 da bor; 13-1 `counterparty.created` qo'shadi; 13-2 `transfer.created`/`transfer.received` (04'da yo'q, 13-1 ro'yxatida ham yo'q); 13-3 `source=cash` xarajat "POS outbox bilan" (voqea turi yo'q; POS-14 "Xarajat" sababi bunga muhtoj, `cash_movements.reason` esa xarajatni taqiqlaydi). 60-qatordagi `type` qiymati almashtiriladi:

```
`shift.opened`, `shift.closed`, `sale.created`, `sale.draft_voided` (audit), `receipt.reprinted` (audit),
`return.created`, `debt_payment.created`, `cash_movement.created`, `counterparty.created` (tezkor mijoz, US-M08-05),
`transfer.sent`, `transfer.received` (o'z filiallari orasida, §7), `stock_count.line_recorded` (M05, bitta qurilma),
`expense.created` (faqat `source=cash`, POS-14 "Xarajat") — **yakuniy ro'yxat** (ochiq savol yopildi);
payload sxemalari: 13-api-katalog-1 (§3–§13), 13-api-katalog-2 (§13, §14), 13-api-katalog-3 (#42)
*(2026-10-15: qabul-6)*
```
`expense.created` payload = `POST /expenses` body + `{id, doc_date, cash_register_id, shift_id}` (`source='cash'` majburiy), server `ExpensePostingService` bilan draft yaratmasdan darhol o'tkazadi. 13-2 dagi `transfer.created` nomi `transfer.sent`ga o'zgaradi (offline'da qoralama mazmunsiz — jo'natish bilan bir voqea).

### S-02 · O'RTA · §2 `payload` qatori
"`sale.created`da `fiscal.receipt_seq`" → "`sale.created`/`return.created`da `receipt_seq` (payload ildizida, int), `shift.opened`da `shift_no` — qurilma beradi (Q11)". 13-1 bilan bir xil joy (ichma-ich `fiscal` obyekti emas).

### S-03 · O'RTA · §3.3 bog'liq voqealar
`SALE_NOT_FOUND` bandiga: "Boshqa bog'liqliklar (`counterparty.created`dan oldin kelgan sotuv boshqa qurilmadan, `transfer.received` jo'natma sinxronidan oldin) — `DEPENDENCY_NOT_SYNCED` (`retryable: true`, `params.entity`)."

### S-04 · PAST · `PushResultEntry`
04 §3 javob namunasiga `warnings: []` maydoni (A1-28).

---

## 10. `02-provodka-qoidalari.md` — posting qamrovi (vazifa 7)

Har 02 hujjat turi ↔ DDL jadval ↔ API post yo'li:

| 02 band | Hujjat (DDL) | API post yo'li | Holat |
|---|---|---|---|
| 2.1–2.4 | `sales` | `sale.created` (sync) | ✓ (A1-01 tuzatish bilan) |
| 2.5 | `returns` | `return.created` | ✓ (DB-03/A1-02 bilan) |
| 2.6–2.8 | `goods_receipts` | `POST /goods-receipts/{id}/post` | ✓ (`paid_immediately`, `einvoice_id` qo'shilgach — A2-04, DB-06) |
| 2.9–2.10 | `transfers` | `/send`, `/receive` + `transfer.sent/received` | ✓ |
| 2.11 | `stock_counts` | `POST /stock-counts/{id}/post` | ✓ |
| 2.12 | `write_offs` | `POST /write-offs/{id}/post` | ✓ |
| 2.13 | `debt_openings` | `POST /debt-openings/{id}/post` + import | ✓ |
| 2.14 | `debt_payments` | `debt_payment.created` + `POST /debt-payments/{id}/post` | ✓ (DB-04) |
| 2.15 | `debt_writeoffs` | `POST /debt-writeoffs/{id}/post` | ✓ |
| 2.16 | `supplier_payments` | `POST /supplier-payments` (bir bosqichli) | ✓ |
| 2.17 | `expenses` | `POST /expenses/{id}/post` + `expense.created` | ✓ (S-01) |
| 2.18 | `cash_movements` | `cash_movement.created` + `POST /cash-movements` | ✓ |
| 2.19 | `shifts` (farq provodkasi) | `shift.closed` | ✓ — **X-01** quyida |
| 2.20 | `supplier_returns` | `POST /supplier-returns/{id}/post` | ✓ |
| 2.21 | `stock_openings` | `POST /stock-openings/{id}/post` + import | ✓ |
| 2.22 | `einvoices(out)` (provodkasiz) | — | **yo'q edi** → A1-24 |
| §5.1 tuzatish | `ledger_adjustments` | — | **yo'q edi** → DB-12/A3-04 |
| — | `price_changes` (registr: `product_prices`) | `POST /price-changes/{id}/post` | ✓ (13-1/13-2 takrori A1-19/A2-02 bilan hal) |
| — | `purchase_orders` | registrga ta'sir yo'q (`send`/`cancel`) | ✓ |

- **X-01 · O'RTA · 2.19** — "Smena yopilganda aniqlangan farq 2.11 qoidasi bo'yicha" — `doc_type='shifts'`, `doc_id=shifts.id` ekanini va farq `shifts.variance` (DB-07) dan olinishini aniq yozish; `cash_moves`ga smena ochilishida `opening_cash` qatori **yozilmaydi** (aks holda `expected_cash = opening_cash + Σcash_moves` ikki marta hisoblaydi) — 13-1 §3.2 formulasi bilan izchil bo'lishi uchun bitta jumla qo'shiladi.
- **X-02 · PAST · Ochiq savollar** — 13-2 A2-11 dagi "inventarizatsiya davomidagi sotuv `expected`ni o'zgartiradi" savoli 02 §2.11 ga qo'shiladi.

---

## 11. `12-autentifikatsiya-oauth2.md`

- **Z-01 · KRITIK** — §16.1 (295-qator) va §20 jadvali: lokaut istisnolari B-02 dagi ro'yxat bilan kengaytiriladi (`POST /api/v1/billing/checkout` va o'qish yo'llari, webhook'lar). Aks holda #15 qarori ("to'lov darhol kirishni tiklaydi") amalga oshmaydi.

---

## 12. `spec/tekshiruv/00-qarorlar.md` — qo'shiladigan qator

```
| 24 | API nomlash, xato konverti, tasdiqlash modeli | qabul-6 (13-0 ochiq savol #1; 13-0 vs 09 §3; 13-1 vs 13-2) | URL — **kebab-case ko'plik** (`/goods-receipts`), JSON/query/enum/`operation_id` — **snake_case** (DB ustuni bilan bir xil); xato konverti `{"error":{code, message_key, params, details[], request_id}}`; limitdan oshgan amal — `approval_requests` (masofaviy) + `doc_approvals` (iz), hujjat `draft`da qoladi (istisno `price_changes`); AI-03 — yagona `ai_ocr_jobs`/`/ai/ocr/jobs`; kontragent — yagona `/counterparties`; `doc_type` = jadval nomi; o'tkazilgan chek bekor qilinmaydi — faqat qaytarish; `receipt_seq`/`shift_no` — qurilma beradi. To'liq: `tekshiruv/qabul-6-api-db.md` |
```

---

## Daraja bo'yicha hisob

| Daraja | Soni | ID'lar |
|---|---|---|
| KRITIK | 15 | DB-01, DB-02, DB-03, DB-04, DB-12, M-05, M-14, M-26, A1-01, A1-02, A1-03, A1-24, A3-01, B-02, Z-01 |
| YUQORI | 57 | DB-05…DB-11, DB-13…DB-16 (11); M-00, M-12, M-13, M-15, M-16, M-17, M-18, M-20, M-25 (9); A0-01, A0-02, A0-03, A0-10 (4); A1-04…A1-10, A1-19…A1-23 (12); A2-01…A2-04, A2-06, A2-07, A2-08, A2-10 (8); A3-02, A3-03, A3-04, A3-06, A3-07 (5); P-01…P-06 (6); B-01; S-01 |
| O'RTA | 82 | DB-17…DB-32 (16); M-01, M-03, M-04, M-06, M-08…M-11, M-19, M-21…M-24, M-27…M-30 (17); A0-04…A0-07 (4); A1-11…A1-17, A1-25…A1-30 (13); A2-09, A2-11…A2-21 (12); A3-05, A3-08…A3-21 (15); P-07; B-03; S-02, S-03; X-01 |
| PAST | 17 | DB-33, M-02, M-07, M-31, A0-08, A0-09, A1-18, A1-31, A2-05, A2-22, A3-22, A3-23, A3-24, P-08, B-04, S-04, X-02 |
| **Jami** | **171** | |

*KRITIK 15 ID — bir muammoning turli fayllardagi tomonlari; **noyob KRITIK muammolar — 8 ta**: (1) Z-hisobot `fiscal_receipts` CHECK'iga sig'maydi (DB-01, M-26); (2) `branches.code` yo'q (DB-02, M-05); (3) `returns`da smena/kassa/qaytarish usuli yo'q va payload'da `receipt_seq` yo'q (DB-03, M-14, A1-02); (4) `debt_payments.method` API'ga mos emas (DB-04, A1-03); (5) buxgalteriya tuzatishi uchun hujjat jadvali yo'q (DB-12); (6) `sale.created`da `receipt_seq` yo'q (A1-01); (7) chiquvchi e-faktura API'si yo'q (A1-24); (8) lokautda to'lov endpoint'i bloklanadi (A3-01, B-02, Z-01).*

## Ochiq qolgan savollar (qabul-6 hal qilmadi)

1. `approval_requests.expires_at` (15 daqiqa) va POS poll (3 s) — taxmin, pilotda.
2. `vat_diff_tolerance_amount` standart qiymati (`"1000.00"`) — buxgalter tasdig'i.
3. `cash_registers.ofd_status` qiymatlar to'plami — OFD/virtual kassa reyestri hujjati bilan.
4. Ko'p bank hisobi (`bank_accounts`) — MVP'dan keyin; hozir yagona 5110.
5. Inventarizatsiya davomida sotuv bo'lsa `expected` qayta hisoblash qoidasi (X-02).
6. Egasi rolining operatsion ruxsatlari (P-08) — mahsulot egasi qarori.
