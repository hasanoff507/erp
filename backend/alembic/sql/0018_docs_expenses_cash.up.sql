-- 0018 docs_expenses_cash — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.expense_categories (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  code        TEXT NULL, -- seed toifa kodi (13 §2.17: 'rent_store', 'payroll_admin', 'tax_payment', ...); foydalanuvchi toifasida NULL
  name        TEXT NOT NULL,
  default_account TEXT NOT NULL DEFAULT '9430' CHECK (default_account IN ('9410','9420','9430','6410')),
              -- Dt hisobi (13 §2.17); '6410' — faqat byudjetga soliq to'lovi (expenses.tax_type majburiy)
  source_ref  TEXT NULL, -- normativ asos ('VMQ-54 2.1.2.3', 'S1 §410')
  is_system   BOOLEAN NOT NULL DEFAULT false,
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1, -- 20-api-moliya-admin.md #47 PATCH version talab qiladi
  UNIQUE (tenant_id, name)
);

CREATE UNIQUE INDEX uq_expense_categories_code ON app.expense_categories (tenant_id, code) WHERE code IS NOT NULL;

-- period 'month'/'quarter'/'year' qiymatlarini oladi (20-api-moliya-admin.md bilan mos).
CREATE TABLE app.recurring_expenses (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  category_id       UUID NOT NULL REFERENCES app.expense_categories(id),
  name              TEXT NULL, -- bo'sh bo'lsa UI toifa nomini ko'rsatadi
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

CREATE TABLE app.attachments (
  id            UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id     UUID NOT NULL REFERENCES app.tenants(id),
  s3_key        TEXT NOT NULL,
  content_type  TEXT NOT NULL, -- 17-api-umumiy.md §12 tur tekshiruvi (415) va signed URL Content-Type uchun
  original_name TEXT NULL,
  sha256        TEXT NULL,
  kind          TEXT NOT NULL CHECK (kind IN ('expense_receipt','ocr_source','state_report','import','export',
                  'label_pdf','billing_invoice','einvoice','onec_diagnostics','other')),
                  -- onec_diagnostics — 1C agenti diagnostika paketi (33-1c-integratsiya.md A-07)
  size_bytes    BIGINT NOT NULL CHECK (size_bytes >= 0),
  uploaded_by   UUID NOT NULL REFERENCES app.users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- billing_payments.invoice_attachment_id shu yerda FK bilan bog'lanadi (attachments jadvali yuqorida yaratilgan):
ALTER TABLE app.billing_payments ADD CONSTRAINT fk_bp_invoice_attachment FOREIGN KEY (invoice_attachment_id) REFERENCES app.attachments(id);

CREATE TABLE app.expenses (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  number            TEXT NULL,
  temp_number       TEXT NULL,
  doc_date          DATE NOT NULL,
  status            TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  category_id       UUID NOT NULL REFERENCES app.expense_categories(id),
  amount            NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  source            TEXT NOT NULL CHECK (source IN ('cash','bank','card')),
  tax_type          TEXT NULL CHECK (tax_type IN ('vat','turnover','pit','social','property','land','other')),
                    -- toifa default_account='6410' (soliq to'lovi) bo'lsa majburiy (ilova tekshiradi) → ledger analytics.tax_type
  cash_register_id  UUID NULL REFERENCES app.cash_registers(id),
  shift_id          UUID NULL REFERENCES app.shifts(id),
  attachment_id     UUID NULL REFERENCES app.attachments(id),
  recurring_rule_id UUID NULL REFERENCES app.recurring_expenses(id),
  created_by        UUID NOT NULL REFERENCES app.users(id),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at         TIMESTAMPTZ NULL,
  cancelled_at      TIMESTAMPTZ NULL,
  cancelled_by      UUID NULL REFERENCES app.users(id),
  cancel_reason     TEXT NULL,
  client_event_id   UUID NULL,
  device_id         UUID NULL REFERENCES app.devices(id),
  comment           TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK (source <> 'cash' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL))
);

CREATE TABLE app.cash_movements (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  shift_id        UUID NOT NULL REFERENCES app.shifts(id),
  direction       TEXT NOT NULL CHECK (direction IN ('in','out')),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  reason          TEXT NOT NULL CHECK (reason IN ('collection','deposit','owner_withdrawal','other')),
  counterparty_id UUID NULL REFERENCES app.counterparties(id),
                  -- owner_withdrawal: ta'sischi (counterparties.is_founder) — legal_form ≠ sole_proprietor bo'lsa majburiy (ilova), Dt 4890 analitikasi;
                  -- other: account 6310/4010 da majburiy
  account         TEXT NULL CHECK (account IS NULL OR account IN ('9430','9390','6310','4010','4730')),
                  -- faqat reason='other' (Buxgalter/Egasi tanlaydi): out → Dt account / Kt 5010 (standart 9430);
                  -- in → Dt 5010 / Kt account (standart 9390) — 13 §2.18
  employee_id     UUID NULL REFERENCES app.users(id), -- account='4730' (xodim bilan hisob-kitob) da majburiy
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK (reason IN ('owner_withdrawal','other') OR counterparty_id IS NULL),
  CHECK (reason = 'other' OR account IS NULL),
  -- reason↔direction juftligi: collection/owner_withdrawal → out, deposit → in, other → ikkalasi
  CHECK ((reason IN ('collection','owner_withdrawal') AND direction = 'out') OR (reason = 'deposit' AND direction = 'in') OR reason = 'other'),
  CHECK (account IS DISTINCT FROM '4730' OR employee_id IS NOT NULL),
  CHECK (account IS NULL OR account NOT IN ('6310','4010') OR counterparty_id IS NOT NULL)
);

-- bank ko'chirmasi importi (POST /bank-settlements/imports, 1CClientBankExchange .txt) — sinxron; natija
-- bank_settlements(source='statement_import', status='draft') qoralamalari, hech narsa avtomatik post qilinmaydi
CREATE TABLE app.bank_statement_imports (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  branch_id          UUID NULL REFERENCES app.branches(id), -- so'rovdagi standart filial
  attachment_id      UUID NOT NULL REFERENCES app.attachments(id), -- attachments.kind='import'
  file_sha256        TEXT NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
  format             TEXT NOT NULL DEFAULT '1c_client_bank_exchange' CHECK (format IN ('1c_client_bank_exchange')),
  account            TEXT NULL,             -- СекцияРасчСчет.РасчСчет
  period_from        DATE NULL,
  period_to          DATE NULL,
  status             TEXT NOT NULL CHECK (status IN ('parsed','failed')),
  rows_total         INT NOT NULL DEFAULT 0,
  drafts_created     INT NOT NULL DEFAULT 0,
  duplicates         INT NOT NULL DEFAULT 0, -- takror qatorlar (bank_ref + doc_date + summa bo'yicha)
  ignored_outgoing   INT NOT NULL DEFAULT 0,
  unmatched_lines    JSONB NOT NULL DEFAULT '[]',
  error_code         TEXT NULL,
  parsed_at          TIMESTAMPTZ NULL,
  created_by         UUID NOT NULL REFERENCES app.users(id),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, file_sha256)            -- BANK_IMPORT_DUPLICATE
);

-- bank tushumi tasdig'i (qaror #42): 5710 (yo'ldagi pul) → 5110 (bank) o'tkazmasi va komissiya,
-- 13-provodka-qoidalari.md §2.18a. Faqat back-office (sync voqeasi yo'q), doc_sequences kodi 'BT'.
CREATE TABLE app.bank_settlements (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  number            TEXT NULL,
  temp_number       TEXT NULL,
  doc_date          DATE NOT NULL, -- bank hisobiga tushgan sana (provodka sanasi)
  status            TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  source            TEXT NOT NULL CHECK (source IN ('manual','statement_import')) DEFAULT 'manual',
  method            TEXT NOT NULL CHECK (method IN ('card','uzqr','click','payme','uzum','collection')),
  settled_from      DATE NOT NULL, -- qamralgan tranzit tushumlar oralig'i
  settled_to        DATE NOT NULL,
  gross_amount      NUMERIC(18,2) NOT NULL CHECK (gross_amount > 0), -- 5710 dan yopiladigan summa
  commission_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (commission_amount >= 0),
                    -- Dt hisobi: card/uzqr → 9430; click/payme/uzum → settings.payment_org_commission_account; collection → 9410
  variance_amount   NUMERIC(18,2) NOT NULL DEFAULT 0, -- faqat collection: <0 inkassa kamomadi (Dt 5910), >0 ortiqcha (Kt 9390)
  net_amount        NUMERIC(18,2) GENERATED ALWAYS AS (gross_amount - commission_amount + variance_amount) STORED, -- Dt 5110
  bank_ref          TEXT NULL, -- bank ko'chirmasi / to'lov topshirig'i raqami
  statement_import_id UUID NULL REFERENCES app.bank_statement_imports(id), -- source='statement_import' da majburiy
  attachment_id     UUID NULL REFERENCES app.attachments(id), -- ko'chirma fayli (attachments.kind='import')
  created_by        UUID NOT NULL REFERENCES app.users(id),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at         TIMESTAMPTZ NULL,
  cancelled_at      TIMESTAMPTZ NULL,
  cancelled_by      UUID NULL REFERENCES app.users(id),
  cancel_reason     TEXT NULL,
  client_event_id   UUID NULL,
  device_id         UUID NULL REFERENCES app.devices(id),
  comment           TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK (settled_from <= settled_to),
  CHECK (commission_amount < gross_amount),
  CHECK (method = 'collection' OR variance_amount = 0),
  CHECK ((source = 'statement_import') = (statement_import_id IS NOT NULL)),
  CHECK (gross_amount - commission_amount + variance_amount > 0)
);

CREATE INDEX idx_bank_settlements_branch_date ON app.bank_settlements (tenant_id, branch_id, doc_date);

-- Terminal settlement'i («сверка итогов», kunni yopish; qaror #71): smena yopilishida POS/agent settlement()
-- chaqiradi (POS yopiq bo'lsa — agent vazifasi card.settlement). Terminal jamlari bizning integrated tranzaksiyalar
-- jami (expected_*) bilan solishtiriladi; farq — status='mismatch' + BO-14 ogohlantirishi. Bank ko'chirmasi
-- (bank_settlements, method='card') shu partiyaga bank_settlement_id orqali bog'lanadi (13 §2.18a). Provodka yo'q.
CREATE TABLE app.card_terminal_settlements (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  card_terminal_id  UUID NOT NULL REFERENCES app.card_terminals(id),
  shift_id          UUID NULL REFERENCES app.shifts(id),
  batch_no          TEXT NULL,                     -- terminal partiya raqami
  business_date     DATE NOT NULL,
  settled_at        TIMESTAMPTZ NOT NULL,          -- terminal vaqti
  purchase_count    INT NOT NULL DEFAULT 0 CHECK (purchase_count >= 0),
  purchase_total    NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (purchase_total >= 0),
  refund_count      INT NOT NULL DEFAULT 0 CHECK (refund_count >= 0),
  refund_total      NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (refund_total >= 0),
  net_total         NUMERIC(18,2) GENERATED ALWAYS AS (purchase_total - refund_total) STORED,
  expected_count    INT NOT NULL DEFAULT 0,        -- server: shu terminal partiyasidagi approved purchase soni
  expected_total    NUMERIC(18,2) NOT NULL DEFAULT 0, -- server: Σ approved purchase − Σ approved refund
  variance          NUMERIC(18,2) GENERATED ALWAYS AS (purchase_total - refund_total - expected_total) STORED,
  status            TEXT NOT NULL CHECK (status IN ('matched','mismatch','failed')),
  bank_settlement_id UUID NULL REFERENCES app.bank_settlements(id), -- bank tushumi tasdig'i bilan moslashtirilgach
  terminal_response JSONB NOT NULL DEFAULT '{}',
  client_event_id   UUID NULL,
  device_id         UUID NULL REFERENCES app.devices(id),
  created_by        UUID NULL REFERENCES app.users(id), -- NULL — agent vazifasi (card.settlement)
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, client_event_id),
  CHECK (status <> 'matched' OR (purchase_total - refund_total) = expected_total)
);

CREATE UNIQUE INDEX uq_cts_batch ON app.card_terminal_settlements (card_terminal_id, batch_no) WHERE batch_no IS NOT NULL;

CREATE INDEX idx_cts_terminal_date ON app.card_terminal_settlements (tenant_id, card_terminal_id, business_date);

CREATE INDEX idx_cts_unmatched_bank ON app.card_terminal_settlements (tenant_id, business_date)
  WHERE bank_settlement_id IS NULL AND status <> 'failed';

ALTER TABLE app.card_terminal_transactions ADD CONSTRAINT fk_ctt_settlement
  FOREIGN KEY (settlement_id) REFERENCES app.card_terminal_settlements(id);

-- soliq davr hisob-kitobi (13-provodka-qoidalari.md §2.26, §4.3), doc_sequences kodi 'ST'. Faqat back-office.
-- vat_offset: Dt 6410 / Kt 4410 — (tenant, davr) bo'yicha, vat_moves tenant bo'yicha yig'iladi (qaror #31 — 1 tenant = 1 STIR);
-- branch_id = tenantning is_default filiali (server yozadi). turnover_tax: Dt expense_account / Kt 6410 —
-- (filial, davr) bo'yicha, branch_id majburiy (SK 468-modda 2-qism).
CREATE TABLE app.tax_settlements (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL, -- odatda davr oxirgi kuni (provodka sanasi)
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  tax_kind        TEXT NOT NULL CHECK (tax_kind IN ('vat_offset','turnover_tax')),
  period          DATE NOT NULL CHECK (extract(day FROM period) = 1),
  base_amount     NUMERIC(18,2) NOT NULL CHECK (base_amount >= 0), -- vat_offset: Σ kiruvchi QQS; turnover_tax: (9020−9040−9050)+9390+8530 (13 §4.3)
  rate            NUMERIC(5,2) NULL CHECK (rate IS NULL OR rate BETWEEN 0 AND 100), -- faqat turnover_tax
  amount          NUMERIC(18,2) NOT NULL CHECK (amount >= 0),
  expense_account TEXT NULL CHECK (expense_account IN ('9430','9820')), -- faqat turnover_tax (settings.turnover_tax_account)
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK ((tax_kind = 'turnover_tax') = (rate IS NOT NULL AND expense_account IS NOT NULL))
);

-- bitta (tenant, davr) uchun bitta faol vat_offset; bitta (filial, davr) uchun bitta faol turnover_tax
CREATE UNIQUE INDEX uq_tax_settlements_vat_offset ON app.tax_settlements (tenant_id, period)
  WHERE tax_kind = 'vat_offset' AND status <> 'cancelled';

CREATE UNIQUE INDEX uq_tax_settlements_turnover ON app.tax_settlements (tenant_id, branch_id, period)
  WHERE tax_kind = 'turnover_tax' AND status <> 'cancelled';
