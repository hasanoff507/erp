-- 0017 docs_pricing_debts — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.price_changes (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','pending_approval','posted','rejected','cancelled')) DEFAULT 'draft',
  approved_by     UUID NULL REFERENCES app.users(id),
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
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.price_change_lines (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  price_change_id UUID NOT NULL REFERENCES app.price_changes(id),
  line_no        INT NOT NULL,
  product_id     UUID NOT NULL REFERENCES app.products(id),
  branch_id      UUID NULL REFERENCES app.branches(id),
  old_price      NUMERIC(18,4) NOT NULL,
  new_price      NUMERIC(18,4) NOT NULL,
  valid_from     TIMESTAMPTZ NULL, -- NULL = post paytidan
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (price_change_id, line_no)
);

CREATE TABLE app.debt_openings (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  direction       TEXT NOT NULL CHECK (direction IN ('receivable','payable')),
  due_date        DATE NULL,
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
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.debt_payments (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  method          TEXT NOT NULL CHECK (method IN ('cash','card','uzqr','click','payme','uzum','bank')),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  shift_id        UUID NULL REFERENCES app.shifts(id),
  terminal_ref    TEXT NULL,
  provider_tx_id  TEXT NULL,
  card_type       TEXT NULL CHECK (card_type IN ('personal','corporate','social','unknown')), -- sale_payments bilan bir xil qoida
  card_mask       TEXT NULL CHECK (card_mask IS NULL OR card_mask ~ '^[0-9]{4}[*]+[0-9]{4}$'),
  rrn             TEXT NULL,
  qr_type         TEXT NULL CHECK (qr_type IN ('static','dynamic')),
  checkout_ref    UUID NULL REFERENCES app.payment_checkouts(checkout_ref),
  card_entry_mode  TEXT NULL CHECK (card_entry_mode IN ('integrated','manual')), -- qaror #71, sale_payments bilan bir xil qoida
  card_terminal_transaction_id UUID NULL REFERENCES app.card_terminal_transactions(id),
  approval_code    TEXT NULL CHECK (approval_code IS NULL OR approval_code ~ '^[0-9A-Za-z]{1,12}$'),
  card_scheme      TEXT NULL CHECK (card_scheme IN ('uzcard','humo','visa','mastercard','unionpay','mir','other')),
  card_type_source TEXT NULL CHECK (card_type_source IN ('terminal','bin_table')),
  manual_reason    TEXT NULL CHECK (manual_reason IN ('terminal_offline','terminal_error','unknown_result','standalone_terminal')),
  promise_date    DATE NULL, -- qoldiq uchun yangi va'da sanasi (qarz daftari ko'rinishi oxirgisini oladi)
  receipt_seq     INT NULL CHECK (receipt_seq IS NULL OR receipt_seq > 0),
                  -- debt_settlement cheki raqami — qurilma beradi, smena ichida ketma-ket (qaror #12); bank'da NULL
  unallocated_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (unallocated_amount >= 0),
                  -- offline ortiqcha summa (qarzdan katta, FM chekni imzolagan): Kt 6310 olingan bo'nak (13 §2.14, qaror #67)
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
  -- bank — kassasiz, fiskal cheksiz (faqat back-office POST /debt-payments); qolgan usullar — faqat POS
  -- debt_payment.created voqeasi, ochiq smenali kassa va debt_settlement cheki bilan (qaror #67)
  CHECK ((method = 'bank') = (cash_register_id IS NULL AND shift_id IS NULL AND receipt_seq IS NULL)),
  CHECK (method NOT IN ('click','payme','uzum') OR provider_tx_id IS NOT NULL),
  CHECK (method <> 'uzqr' OR qr_type IS NOT NULL),
  CHECK (method <> 'uzqr' OR qr_type = 'static' OR provider_tx_id IS NOT NULL),
  CHECK (qr_type IS NULL OR method = 'uzqr'),
  -- karta — sale_payments bilan bir xil qoida (qaror #64, #71): manual — rekvizitsiz
  CHECK (method <> 'card' OR terminal_ref IS NULL OR card_entry_mode = 'integrated'),
  CHECK ((method = 'card') = (card_entry_mode IS NOT NULL)),
  CHECK ((card_type IS NULL) = (card_type_source IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'integrated' OR (card_terminal_transaction_id IS NOT NULL
         AND rrn IS NOT NULL AND card_mask IS NOT NULL AND card_type IS NOT NULL AND manual_reason IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'manual' OR (card_terminal_transaction_id IS NULL AND manual_reason IS NOT NULL
         AND card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL AND card_scheme IS NULL)),
  CHECK (method = 'card' OR (card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL
         AND card_scheme IS NULL AND manual_reason IS NULL AND card_terminal_transaction_id IS NULL)),
  CHECK (unallocated_amount <= amount)
);

CREATE UNIQUE INDEX uq_debt_payments_card_tx ON app.debt_payments (card_terminal_transaction_id)
  WHERE card_terminal_transaction_id IS NOT NULL;

CREATE TABLE app.debt_payment_allocations (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  debt_payment_id UUID NOT NULL REFERENCES app.debt_payments(id),
  target_doc_type TEXT NOT NULL CHECK (target_doc_type IN ('sales','debt_openings','debt_writeoffs')),
                  -- polimorfik; 'debt_writeoffs' — ilgari hisobdan chiqarilgan qarz qaytdi → Kt 9390, debt_moves yozilmaydi (13 §2.14)
  target_doc_id   UUID NOT NULL,
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.debt_writeoffs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  reason          TEXT NOT NULL, -- majburiy (18-api-kassa.md §12.5)
  account_choice  TEXT NOT NULL DEFAULT '9430' CHECK (account_choice IN ('9430','4910')), -- 13-provodka-qoidalari.md §2.15 "9430 standart"
  tax_writeoff_basis TEXT NULL CHECK (tax_writeoff_basis IN ('court','bankruptcy','liquidation','death','limitation','none')),
                  -- SK 313-modda asosi (Buxgalter belgilaydi, faqat hisobotga chiqadi)
  approved_by     UUID NULL REFERENCES app.users(id), -- faqat Egasi; qoralama tasdiqsiz yaratiladi
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
  CHECK (status <> 'posted' OR approved_by IS NOT NULL)
);

CREATE TABLE app.supplier_payments (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  supplier_id     UUID NOT NULL REFERENCES app.counterparties(id),
  method          TEXT NOT NULL CHECK (method IN ('cash','bank')),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  shift_id        UUID NULL REFERENCES app.shifts(id),
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
  CHECK (method <> 'cash' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL))
);

CREATE TABLE app.supplier_payment_allocations (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  supplier_payment_id UUID NOT NULL REFERENCES app.supplier_payments(id),
  target_doc_type    TEXT NOT NULL CHECK (target_doc_type IN ('goods_receipts','debt_openings')),
                     -- amount − Σallocations = avans (4310, qaror #47; 13 §2.16)
  target_doc_id      UUID NOT NULL,
  amount             NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
