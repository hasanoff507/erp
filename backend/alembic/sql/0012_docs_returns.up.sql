-- 0012 docs_returns — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.returns (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  number           TEXT NULL,
  temp_number      TEXT NULL,
  doc_date         DATE NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  sale_id          UUID NULL REFERENCES app.sales(id), -- null = chek topilmagan qaytarish
  shift_id         UUID NOT NULL REFERENCES app.shifts(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  counterparty_id  UUID NULL REFERENCES app.counterparties(id), -- refund_method='debt_adjustment' uchun
  reason           TEXT NOT NULL CHECK (reason IN ('defective','wrong_item','customer_changed_mind','other')),
  refund_method    TEXT NOT NULL CHECK (refund_method IN ('cash','card','uzqr','click','payme','uzum','debt_adjustment')),
                   -- standart — asl to'lov usuli; qarzli sotuvda avval sotuvning ochiq qarzi kamayadi (debt_adjustment
                   -- qismi, chek yo'q), qolgani pul bilan (13 §2.5). Click/Payme/Uzum qaytarish — provayder kabinetida qo'lda
  -- refund_method='card' rekvizitlari (qaror #71): integrated — shu terminalda refund (settlement'gacha void) natijasi;
  -- manual — karta qaytarish terminalsiz (ilovadan tashqarida) amalga oshirilgan: faqat summa + manual_reason, karta
  -- rekvizitlari NULL (faol terminal bog'langan kassada card_manual_fallback siyosati bo'yicha)
  card_entry_mode  TEXT NULL CHECK (card_entry_mode IN ('integrated','manual')),
  card_terminal_transaction_id UUID NULL REFERENCES app.card_terminal_transactions(id),
  card_type        TEXT NULL CHECK (card_type IN ('personal','corporate','social','unknown')),
  card_mask        TEXT NULL CHECK (card_mask IS NULL OR card_mask ~ '^[0-9]{4}[*]+[0-9]{4}$'),
  rrn              TEXT NULL,
  approval_code    TEXT NULL CHECK (approval_code IS NULL OR approval_code ~ '^[0-9A-Za-z]{1,12}$'),
  card_scheme      TEXT NULL CHECK (card_scheme IN ('uzcard','humo','visa','mastercard','unionpay','mir','other')),
  manual_reason    TEXT NULL CHECK (manual_reason IN ('terminal_offline','terminal_error','unknown_result','standalone_terminal')),
  is_offline       BOOLEAN NOT NULL DEFAULT false,
  approved_by      UUID NULL REFERENCES app.users(id),
  approved_at      TIMESTAMPTZ NULL,
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
  UNIQUE (tenant_id, client_event_id),
  CHECK (refund_method <> 'debt_adjustment' OR counterparty_id IS NOT NULL),
  CHECK (sale_id IS NOT NULL OR approved_by IS NOT NULL), -- chek topilmagan qaytarish — har doim tasdiq bilan
  CHECK ((refund_method = 'card') = (card_entry_mode IS NOT NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'integrated' OR (card_terminal_transaction_id IS NOT NULL
         AND rrn IS NOT NULL AND card_mask IS NOT NULL AND manual_reason IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'manual' OR (card_terminal_transaction_id IS NULL AND manual_reason IS NOT NULL
         AND card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL AND card_scheme IS NULL)),
  CHECK (refund_method = 'card' OR (card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL
         AND card_scheme IS NULL AND manual_reason IS NULL AND card_terminal_transaction_id IS NULL))
);

CREATE UNIQUE INDEX uq_returns_card_tx ON app.returns (card_terminal_transaction_id)
  WHERE card_terminal_transaction_id IS NOT NULL;

CREATE TABLE app.return_lines (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  return_id          UUID NOT NULL REFERENCES app.returns(id),
  line_no            INT NOT NULL,
  sale_line_id       UUID NULL REFERENCES app.sale_lines(id), -- null = chek topilmagan
  product_id         UUID NOT NULL REFERENCES app.products(id),
  qty                NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  price              NUMERIC(18,4) NOT NULL,
  vat_rate           NUMERIC(5,2) NOT NULL,
  vat_exemption_code TEXT NULL,
  marking_code       TEXT NULL,
  vat_amount         NUMERIC(18,2) NOT NULL DEFAULT 0,
  cost_amount        NUMERIC(18,2) NOT NULL DEFAULT 0,
  line_total         NUMERIC(18,2) NOT NULL,
  restock            BOOLEAN NOT NULL DEFAULT true,
                     -- false — tovar sotuvga qaytmaydi: muddati o'tgan tovar (qaror #48) — majburan false,
                     -- shu tranzaksiyada write_offs qoralamasi (reason='expired_return') yaratiladi
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (return_id, line_no),
  CHECK (marking_code IS NULL OR qty = 1)
);

CREATE INDEX idx_return_lines_sale_line ON app.return_lines (sale_line_id) WHERE sale_line_id IS NOT NULL;
