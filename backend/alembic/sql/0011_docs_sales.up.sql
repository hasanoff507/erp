-- 0011 docs_sales — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- shift_no — qurilma beradi, OFD smena raqami; variance — generated ustun (counted_cash - expected_cash).
CREATE TABLE app.shifts (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  branch_id          UUID NOT NULL REFERENCES app.branches(id),
  cash_register_id   UUID NOT NULL REFERENCES app.cash_registers(id),
  device_id          UUID NOT NULL REFERENCES app.devices(id), -- bitta smena — bitta qurilma
  shift_no           INT  NOT NULL CHECK (shift_no > 0), -- qurilma beradi, kassa ichida ketma-ket (qaror #12)
  status             TEXT NOT NULL CHECK (status IN ('open','closed')) DEFAULT 'open',
  opened_by          UUID NOT NULL REFERENCES app.users(id),
  opened_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_by          UUID NULL REFERENCES app.users(id),
  closed_at          TIMESTAMPTZ NULL,
  opening_cash       NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (opening_cash >= 0),
  expected_cash      NUMERIC(18,2) NULL, -- server hisoblaydi: opening_cash + Σcash_moves(shift)
  counted_cash       NUMERIC(18,2) NULL,
  variance           NUMERIC(18,2) GENERATED ALWAYS AS (counted_cash - expected_cash) STORED,
  variance_note      TEXT NULL,
  counted_card_total NUMERIC(18,2) NULL, -- qo'lda belgilangan "karta" jami (POS-15)
  comment            TEXT NULL,
  client_event_id    UUID NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, client_event_id),
  UNIQUE (tenant_id, cash_register_id, shift_no),
  CHECK (status <> 'closed' OR (counted_cash IS NOT NULL AND expected_cash IS NOT NULL)),
  CHECK (counted_cash IS NULL OR expected_cash IS NULL OR counted_cash = expected_cash OR variance_note IS NOT NULL)
);

-- bitta kassada bir vaqtda faqat bitta ochiq smena
CREATE UNIQUE INDEX uq_shifts_one_open ON app.shifts (cash_register_id) WHERE status = 'open';

CREATE TABLE app.sales (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  number           TEXT NULL,
  temp_number      TEXT NULL,
  doc_date         DATE NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  shift_id         UUID NOT NULL REFERENCES app.shifts(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  counterparty_id  UUID NULL REFERENCES app.counterparties(id), -- nasiya/qarzga sotuvda
  total_amount     NUMERIC(18,2) NULL, -- hisoblangan jami (aniqlashtirish #10 — tezkor o'qish uchun qo'shimcha)
  is_offline          BOOLEAN NOT NULL DEFAULT false,
  debt_limit_exceeded BOOLEAN NOT NULL DEFAULT false, -- offline nasiya limitdan oshgan (tavsiya #7) — xato emas, bayroq
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at        TIMESTAMPTZ NULL,
  cancelled_at     TIMESTAMPTZ NULL,
  cancelled_by     UUID NULL REFERENCES app.users(id),
  cancel_reason    TEXT NULL,
  client_event_id  UUID NULL,
  device_id        UUID NULL REFERENCES app.devices(id),
  comment          TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);

CREATE INDEX idx_sales_branch_date ON app.sales (tenant_id, branch_id, doc_date);

CREATE INDEX idx_sales_shift ON app.sales (shift_id);

CREATE INDEX idx_sales_debt_limit_exceeded ON app.sales (tenant_id) WHERE debt_limit_exceeded;

CREATE TABLE app.sale_lines (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  sale_id            UUID NOT NULL REFERENCES app.sales(id),
  line_no            INT NOT NULL,
  product_id         UUID NOT NULL REFERENCES app.products(id),
  qty                NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  price              NUMERIC(18,4) NOT NULL CHECK (price >= 0),
  discount_amount    NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  vat_rate           NUMERIC(5,2) NOT NULL,
  vat_exemption_code TEXT NULL,
  discount_pct       NUMERIC(5,2) NULL CHECK (discount_pct BETWEEN 0 AND 100), -- ma'lumot uchun; manba — discount_amount
  discount_source    TEXT NULL CHECK (discount_source IN ('manual','standing_customer','rule')),
  discount_rule_id   UUID NULL REFERENCES app.discount_rules(id),
  vat_amount         NUMERIC(18,2) NOT NULL DEFAULT 0,
  line_total         NUMERIC(18,2) NOT NULL,
  cost_amount        NUMERIC(18,2) NOT NULL DEFAULT 0,
  marking_code       TEXT NULL,
  lot_allocations    JSONB NOT NULL DEFAULT '[]',
  settled_amount     NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (settled_amount >= 0),
                     -- qarz to'lovi (debt_settlement) va aralash to'lovli sotuvning birinchi chekida fiskallangan
                     -- kumulyativ summa; server posting'da yangilaydi (18 §12.2, qaror #67)
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (sale_id, line_no),
  CHECK (settled_amount <= line_total),
  CHECK (marking_code IS NULL OR qty = 1), -- markirovkalangan tovarda qty=1 majburiy
  CHECK ((discount_amount = 0) = (discount_source IS NULL)),
  CHECK (discount_source IS DISTINCT FROM 'rule' OR discount_rule_id IS NOT NULL)
);

CREATE INDEX idx_sale_lines_product ON app.sale_lines (tenant_id, product_id);

-- Karta terminali tranzaksiyalari (qaror #71). id = attempt_id: POS/qurilma beradi (UUIDv7), terminalga ERN/order
-- ref sifatida uzatiladi — idempotentlik kaliti (agent jurnalida ham UNIQUE). Qator har bir urinishga bitta (kind):
-- purchase (xarid), refund (qaytarish), void (shu kun, settlement'gacha bekor qilish). Holat so'rovi
-- (get_status/get_last_transaction) yangi qator emas — shu qatorning status/resolved_by ustunlarini yangilaydi;
-- settlement — card_terminal_settlements. Online: POS natijani POST /card-terminal-transactions bilan darhol yozadi;
-- offline: natija sale.created / return.created / debt_payment.created payload'idagi card_result ichida (payments[] / refund_card / ildiz)
-- keladi va server qatorni shu voqeadan upsert qiladi (16 §2.1, 18 §2.7). PAN/track/CVV hech qachon yozilmaydi.
-- doc_type/doc_id — tranzaksiya qaysi hujjatga yopilgani (polimorfik). Sotuvsiz qolgan approved purchase avtomatik void
-- qilinmaydi: 24 soatdan keyin sync_exceptions(kind='card_orphan_transaction') — qo'lda ko'rib chiqiladi (16 §2.1).
CREATE TABLE app.card_terminal_transactions (
  id                      UUID PRIMARY KEY,               -- = attempt_id, har doim qurilma beradi
  tenant_id               UUID NOT NULL REFERENCES app.tenants(id),
  branch_id               UUID NOT NULL REFERENCES app.branches(id),
  card_terminal_id        UUID NOT NULL REFERENCES app.card_terminals(id),
  cash_register_id        UUID NULL REFERENCES app.cash_registers(id),
  shift_id                UUID NULL REFERENCES app.shifts(id),
  device_id               UUID NULL REFERENCES app.devices(id),
  kind                    TEXT NOT NULL CHECK (kind IN ('purchase','refund','void')),
  original_transaction_id UUID NULL REFERENCES app.card_terminal_transactions(id), -- refund/void: asl purchase
  amount                  NUMERIC(18,2) NOT NULL CHECK (amount > 0),  -- so'ralgan summa
  approved_amount         NUMERIC(18,2) NULL CHECK (approved_amount IS NULL OR approved_amount > 0), -- terminal tasdiqlagani
  currency                TEXT NOT NULL DEFAULT 'UZS' CHECK (currency = 'UZS'),
  status                  TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','approved','declined','unknown','voided')),
                            -- pending — terminalga yuborildi, javob kutilmoqda; unknown — taymaut/aloqa uzildi, natija
                            -- noma'lum (yangi purchase bloklanadi); voided — approved purchase keyin void bilan bekor qilindi.
                            -- CardTxResult.status xaritasi: approved → approved; declined/cancelled/error → declined
                            -- (decline_code = 'cancelled'/'error'/bank kodi); timeout/unknown → unknown; holat so'rovi
                            -- natijasi not_found → declined (decline_code='not_found')
  approval_code           TEXT NULL CHECK (approval_code IS NULL OR approval_code ~ '^[0-9A-Za-z]{1,12}$'),
  rrn                     TEXT NULL CHECK (rrn IS NULL OR rrn ~ '^[0-9A-Za-z]{6,32}$'),
  stan                    TEXT NULL,
  card_mask               TEXT NULL CHECK (card_mask IS NULL OR card_mask ~ '^[0-9]{4}[*]+[0-9]{4}$'), -- normallashtirilgan 4+4
  card_scheme             TEXT NULL CHECK (card_scheme IN ('uzcard','humo','visa','mastercard','unionpay','mir','other')),
  card_type               TEXT NULL CHECK (card_type IN ('personal','corporate','social','unknown')),
  card_type_source        TEXT NULL CHECK (card_type_source IN ('terminal','bin_table')),
  entry_mode              TEXT NULL CHECK (entry_mode IN ('chip','contactless','magstripe','fallback')), -- kartani o'qish usuli
  tid                     TEXT NULL,
  mid                     TEXT NULL,
  acquirer                TEXT NULL,
  decline_code            TEXT NULL,
  decline_message         TEXT NULL,
  resolved_by             TEXT NULL CHECK (resolved_by IN ('auto','status_query','manager')),
                          -- auto — terminal javobi; status_query — get_status/get_last_transaction;
                          -- manager — unknown'ni menejer terminal chekiga qarab yopdi (card.manual_entry.approve):
                          -- faqat "o'tdi / o'tmadi" tasdig'i, hech qanday karta rekviziti kiritilmaydi — approved'da
                          -- rrn/card_mask/approval_code/card_type NULL qoladi, to'lov qatori card_entry_mode='manual',
                          -- manual_reason='unknown_result' (rekvizitsiz), tranzaksiya hujjatga doc_type/doc_id orqali bog'lanadi
  resolved_by_user_id     UUID NULL REFERENCES app.users(id),
  terminal_response       JSONB NOT NULL DEFAULT '{}',    -- adapterning sanitizatsiyalangan xom javobi (PAN/track yo'q)
  slip_text               TEXT NULL,                      -- terminal cheki matni (ixtiyoriy)
  client_event_id         UUID NULL,                      -- bog'langan sale/return/debt_payment voqeasi
  doc_type                TEXT NULL CHECK (doc_type IN ('sales','returns','debt_payments')),
  doc_id                  UUID NULL,
  settlement_id           UUID NULL,                      -- FK 0018 da: fk_ctt_settlement → card_terminal_settlements
  requested_at            TIMESTAMPTZ NOT NULL,           -- qurilma soati
  tx_at                   TIMESTAMPTZ NULL,               -- terminal bergan tranzaksiya vaqti
  resolved_at             TIMESTAMPTZ NULL,
  created_by              UUID NOT NULL REFERENCES app.users(id),
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (kind <> 'void' OR original_transaction_id IS NOT NULL),  -- void doim asl purchase'ga bog'liq
  CHECK (kind <> 'purchase' OR original_transaction_id IS NULL),
  CHECK (kind = 'purchase' OR status <> 'voided'),
  -- tasdiqlangan purchase/refund: terminal natijasida RRN va niqob majburiy (fiskal chek rekviziti, qaror #64);
  -- menejer yopgan unknown (resolved_by='manager') — rekvizitsiz
  CHECK (status NOT IN ('approved','voided') OR kind = 'void' OR (approved_amount IS NOT NULL
         AND (resolved_by = 'manager' OR (rrn IS NOT NULL AND card_mask IS NOT NULL)))),
  CHECK (resolved_by IS DISTINCT FROM 'manager' OR (rrn IS NULL AND card_mask IS NULL AND approval_code IS NULL
         AND card_type IS NULL)),
  CHECK ((card_type IS NULL) = (card_type_source IS NULL)),
  CHECK (status IN ('pending','unknown') OR resolved_at IS NOT NULL),
  CHECK (resolved_by IS DISTINCT FROM 'manager' OR resolved_by_user_id IS NOT NULL),
  CHECK ((doc_type IS NULL) = (doc_id IS NULL))
);

CREATE UNIQUE INDEX uq_ctt_purchase_rrn ON app.card_terminal_transactions (tenant_id, tid, rrn)
  WHERE kind = 'purchase' AND rrn IS NOT NULL AND tid IS NOT NULL;

-- bitta terminalda bir vaqtda bitta ochiq urinish (agent DeviceLane FIFO bilan bir xil qoida)
CREATE UNIQUE INDEX uq_ctt_one_pending ON app.card_terminal_transactions (card_terminal_id) WHERE status = 'pending';

CREATE INDEX idx_ctt_unresolved ON app.card_terminal_transactions (tenant_id, card_terminal_id)
  WHERE status IN ('pending','unknown');

CREATE INDEX idx_ctt_orphans ON app.card_terminal_transactions (tenant_id, created_at)
  WHERE status = 'approved' AND doc_id IS NULL;

CREATE INDEX idx_ctt_shift ON app.card_terminal_transactions (shift_id) WHERE shift_id IS NOT NULL;

CREATE INDEX idx_ctt_original ON app.card_terminal_transactions (original_transaction_id) WHERE original_transaction_id IS NOT NULL;

CREATE TABLE app.sale_payments (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  sale_id        UUID NOT NULL REFERENCES app.sales(id),
  method         TEXT NOT NULL CHECK (method IN ('cash','card','uzqr','click','payme','uzum','debt')),
  amount         NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  provider_tx_id TEXT NULL,
  terminal_ref   TEXT NULL, -- statik UzQR to'lov raqami (ixtiyoriy) / integrated kartada server card_result.tid'dan to'ldiradi
  card_type      TEXT NULL CHECK (card_type IN ('personal','corporate','social','unknown')), -- chek rekviziti (VMQ-943 1-ilova 7-band), faqat integrated
  card_mask      TEXT NULL CHECK (card_mask IS NULL OR card_mask ~ '^[0-9]{4}[*]+[0-9]{4}$'), -- birinchi va oxirgi 4 raqam, faqat integrated
  rrn            TEXT NULL, -- terminal tranzaksiyasining noyob raqami (RRN), faqat integrated
  qr_type        TEXT NULL CHECK (qr_type IN ('static','dynamic')),
  due_date       DATE NULL, -- method='debt': va'da sanasi → debt_moves.due_date manbasi
  checkout_ref   UUID NULL REFERENCES app.payment_checkouts(checkout_ref),
  -- karta kiritish usuli (qaror #64, #71): integrated — rekvizitlar faqat terminal natijasidan avtomatik;
  -- manual — karta terminalsiz (ilovadan tashqarida) qabul qilingan: faqat summa + manual_reason, hech qanday karta rekviziti yo'q
  card_entry_mode  TEXT NULL CHECK (card_entry_mode IN ('integrated','manual')),
  card_terminal_transaction_id UUID NULL REFERENCES app.card_terminal_transactions(id),
  approval_code    TEXT NULL CHECK (approval_code IS NULL OR approval_code ~ '^[0-9A-Za-z]{1,12}$'),
  card_scheme      TEXT NULL CHECK (card_scheme IN ('uzcard','humo','visa','mastercard','unionpay','mir','other')),
  card_type_source TEXT NULL CHECK (card_type_source IN ('terminal','bin_table')),
  manual_reason    TEXT NULL CHECK (manual_reason IN ('terminal_offline','terminal_error','unknown_result','standalone_terminal')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (method = 'debt' OR due_date IS NULL),
  CHECK (method NOT IN ('click','payme','uzum') OR provider_tx_id IS NOT NULL),
  -- UzQR: qr_type majburiy; provider_tx_id faqat dinamik QR'da (statik — kassir qo'lda tasdiqlaydi)
  CHECK (method <> 'uzqr' OR qr_type IS NOT NULL),
  CHECK (method <> 'uzqr' OR qr_type = 'static' OR provider_tx_id IS NOT NULL),
  CHECK (qr_type IS NULL OR method = 'uzqr'),
  CHECK (method <> 'card' OR terminal_ref IS NULL OR card_entry_mode = 'integrated'), -- terminalsiz kartada raqam kiritilmaydi
  -- karta (qaror #64, #71): kiritish usuli majburiy; integrated — tranzaksiya, RRN, niqob, karta turi (terminal yoki
  -- BIN jadvali; topilmasa 'unknown') majburiy, sabab yo'q; manual — tranzaksiyasiz, sabab majburiy, barcha karta
  -- rekvizitlari NULL (ilovada karta ma'lumoti qo'lda kiritilmaydi)
  CHECK ((method = 'card') = (card_entry_mode IS NOT NULL)),
  CHECK ((card_type IS NULL) = (card_type_source IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'integrated' OR (card_terminal_transaction_id IS NOT NULL
         AND rrn IS NOT NULL AND card_mask IS NOT NULL AND card_type IS NOT NULL AND manual_reason IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'manual' OR (card_terminal_transaction_id IS NULL AND manual_reason IS NOT NULL
         AND card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL AND card_scheme IS NULL)),
  CHECK (method = 'card' OR (card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL
         AND card_scheme IS NULL AND manual_reason IS NULL AND card_terminal_transaction_id IS NULL))
);

CREATE INDEX idx_sale_payments_sale ON app.sale_payments (sale_id);

-- bitta tasdiqlangan terminal tranzaksiyasi — bitta to'lov qatori
CREATE UNIQUE INDEX uq_sale_payments_card_tx ON app.sale_payments (card_terminal_transaction_id)
  WHERE card_terminal_transaction_id IS NOT NULL;
