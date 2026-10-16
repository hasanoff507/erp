-- 0015 registers — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.supplier_returns (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  supplier_id     UUID NOT NULL REFERENCES app.counterparties(id),
  receipt_id      UUID NULL REFERENCES app.goods_receipts(id),
  reason          TEXT NOT NULL CHECK (reason IN ('expired','damaged','excess','other')), -- sarlavhada (19-api-ombor.md §12)
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

CREATE TABLE app.supplier_return_lines (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  supplier_return_id UUID NOT NULL REFERENCES app.supplier_returns(id),
  line_no          INT NOT NULL,
  receipt_line_id  UUID NOT NULL REFERENCES app.receipt_lines(id),
  lot_id           UUID NOT NULL, -- FK app.stock_lots(id) — 2.7-bo'limda ALTER bilan qo'shiladi
  qty              NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  cost             NUMERIC(18,4) NOT NULL,
  vat_amount       NUMERIC(18,2) NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (supplier_return_id, line_no)
);

CREATE TABLE app.stock_moves (
  id            UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id     UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id  UUID NOT NULL REFERENCES app.warehouses(id),
  product_id    UUID NOT NULL REFERENCES app.products(id),
  lot_id        UUID NULL, -- FK pastda (stock_lots yaratilgandan keyin)
  qty           NUMERIC(18,3) NOT NULL, -- ishorali: kirim +, chiqim -
  cost_amount   NUMERIC(18,2) NOT NULL DEFAULT 0,
  doc_type      TEXT NOT NULL,
  doc_id        UUID NOT NULL,
  line_id       UUID NULL,
  reversal_of_id UUID NULL REFERENCES app.stock_moves(id),
  moved_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                -- hujjat biznes vaqti: POS voqeasida effective_created_at (16 §8), back-office hujjatda posted_at;
                -- DEFAULT now() faqat zaxira
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_stock_moves_wh_prod ON app.stock_moves (tenant_id, warehouse_id, product_id, moved_at);

CREATE INDEX idx_stock_moves_doc ON app.stock_moves (tenant_id, doc_type, doc_id);

CREATE TABLE app.stock_lots (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id    UUID NOT NULL REFERENCES app.warehouses(id),
  product_id      UUID NOT NULL REFERENCES app.products(id),
  receipt_line_id UUID NULL REFERENCES app.receipt_lines(id), -- faqat source_doc_type='goods_receipt'
  source_doc_type TEXT NOT NULL CHECK (source_doc_type IN ('goods_receipts','stock_openings','transfers','stock_counts')),
                  -- aniqlashtirish #3; stock_counts — inventarizatsiya ortiqchasi partiyasi (13 §2.11)
  source_doc_id   UUID NOT NULL,
  source_line_id  UUID NOT NULL,
  received_at     TIMESTAMPTZ NOT NULL,
  qty_in          NUMERIC(18,3) NOT NULL CHECK (qty_in >= 0),
  qty_left        NUMERIC(18,3) NOT NULL CHECK (qty_left >= 0),
  unit_cost       NUMERIC(18,4) NOT NULL CHECK (unit_cost >= 0),
  blocked_qty     NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (blocked_qty >= 0 AND blocked_qty <= qty_left),
                  -- qaytarilgan muddati o'tgan tovar (restock=false, qaror #48): sotuvga chiqmaydi; write_offs
                  -- (expired_return) post'ida blocked_qty va qty_left birga kamayadi (13 §2.5)
  expiry_date     DATE NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- FIFO: ORDER BY received_at, id; sotuvga ochiq miqdor — qty_left − blocked_qty (13 §3.1)
CREATE INDEX idx_stock_lots_fifo ON app.stock_lots (tenant_id, warehouse_id, product_id, received_at, id)
  WHERE qty_left > blocked_qty;

ALTER TABLE app.stock_moves ADD CONSTRAINT fk_sm_lot FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);

ALTER TABLE app.supplier_return_lines ADD CONSTRAINT fk_srl_lot FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);

-- transfer_lines'da lot_id ustuni yo'q (lot_allocations JSONB ishlatiladi) — shuning uchun fk_tl_lot yo'q
ALTER TABLE app.write_off_lines       ADD CONSTRAINT fk_wol_lot FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);

CREATE TABLE app.avg_costs (
  tenant_id    UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id UUID NOT NULL REFERENCES app.warehouses(id),
  product_id   UUID NOT NULL REFERENCES app.products(id),
  avg_cost     NUMERIC(18,4) NOT NULL DEFAULT 0,
  qty          NUMERIC(18,3) NOT NULL DEFAULT 0,
  total_value  NUMERIC(18,2) NOT NULL DEFAULT 0, -- AVECO qiymat yig'indisi: avg = total_value / qty; qty ≤ 0 → 0 (13 §3.1)
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, warehouse_id, product_id)
);

CREATE TABLE app.stock_balances (
  tenant_id    UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id UUID NOT NULL REFERENCES app.warehouses(id),
  product_id   UUID NOT NULL REFERENCES app.products(id),
  qty          NUMERIC(18,3) NOT NULL DEFAULT 0,
  value        NUMERIC(18,2) NOT NULL DEFAULT 0,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, warehouse_id, product_id)
);

-- manfiy qoldiqlarni tezkor topish (offline overselling, `16` §5)
CREATE INDEX idx_stock_balances_negative ON app.stock_balances (tenant_id, warehouse_id, product_id) WHERE qty < 0;

CREATE TABLE app.debt_moves (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  direction       TEXT NOT NULL CHECK (direction IN ('receivable','payable')),
  amount          NUMERIC(18,2) NOT NULL, -- ishorali
  due_date        DATE NULL,
  limit_exceeded  BOOLEAN NOT NULL DEFAULT false, -- offline nasiya limitdan oshgan qator
  doc_type        TEXT NOT NULL,
  doc_id          UUID NOT NULL,
  reversal_of_id  UUID NULL REFERENCES app.debt_moves(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_debt_moves_cp ON app.debt_moves (tenant_id, counterparty_id, direction, created_at);

CREATE INDEX idx_debt_moves_due ON app.debt_moves (tenant_id, due_date) WHERE direction = 'receivable';

CREATE INDEX idx_debt_moves_limit_exceeded ON app.debt_moves (tenant_id) WHERE limit_exceeded;

CREATE TABLE app.debt_balances (
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  direction       TEXT NOT NULL CHECK (direction IN ('receivable','payable')),
  balance         NUMERIC(18,2) NOT NULL DEFAULT 0,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, counterparty_id, direction)
);

CREATE TABLE app.cash_moves (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  bank_account_id  UUID NULL, -- MVP: doim NULL — yagona yashirin bank hisobi 5110; ko'p bank hisobi (jadval) — backlog
  shift_id         UUID NULL REFERENCES app.shifts(id),
  amount           NUMERIC(18,2) NOT NULL, -- ishorali
  method           TEXT NOT NULL CHECK (method IN ('cash','card','uzqr','click','payme','uzum','bank')),
  doc_type         TEXT NOT NULL,
  doc_id           UUID NOT NULL,
  reversal_of_id   UUID NULL REFERENCES app.cash_moves(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (method <> 'cash' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL))
);

CREATE INDEX idx_cash_moves_shift ON app.cash_moves (shift_id) WHERE shift_id IS NOT NULL;

CREATE TABLE app.ledger_entries (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  entry_date     DATE NOT NULL,
  branch_id      UUID NULL REFERENCES app.branches(id), -- filial bo'yicha hisobot uchun indeksli ustun
  account_dt     TEXT NOT NULL CHECK (account_dt ~ '^[0-9]{4}$'), -- hisob kodi 13-provodka-qoidalari.md §1 ro'yxatidan (0000, 2910/2920, 5710 …)
  account_kt     TEXT NOT NULL CHECK (account_kt ~ '^[0-9]{4}$'),
  amount         NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  doc_type       TEXT NOT NULL,
  doc_id         UUID NOT NULL,
  analytics      JSONB NOT NULL DEFAULT '{}',
  reversal_of_id UUID NULL REFERENCES app.ledger_entries(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ledger_entries_period ON app.ledger_entries (tenant_id, entry_date);

CREATE INDEX idx_ledger_entries_doc ON app.ledger_entries (tenant_id, doc_type, doc_id);

CREATE INDEX idx_ledger_entries_accounts ON app.ledger_entries (tenant_id, account_dt, account_kt, entry_date);

CREATE INDEX idx_ledger_entries_branch ON app.ledger_entries (tenant_id, branch_id, entry_date);

CREATE TABLE app.vat_moves (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  period         DATE NOT NULL, -- oyning 1-sanasi
  kind           TEXT NOT NULL CHECK (kind IN ('output','input')),
  base_amount    NUMERIC(18,2) NOT NULL,
  vat_amount     NUMERIC(18,2) NOT NULL,
  doc_type       TEXT NOT NULL,
  doc_id         UUID NOT NULL,
  einvoice_id    UUID NULL, -- FK pastda (einvoices yaratilgandan keyin)
  reversal_of_id UUID NULL REFERENCES app.vat_moves(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_vat_moves_period ON app.vat_moves (tenant_id, period, kind);

-- 0015 registers
DO $$
DECLARE
  t TEXT;
  append_only_tables TEXT[] := ARRAY[
    'app.stock_moves', 'app.debt_moves', 'app.cash_moves',
    'app.ledger_entries', 'app.vat_moves', 'app.doc_approvals'
  ];
BEGIN
  FOREACH t IN ARRAY append_only_tables LOOP
    EXECUTE format('REVOKE UPDATE, DELETE ON %s FROM erp_app', t);
    EXECUTE format(
      'CREATE TRIGGER trg_no_update_delete BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation()',
      t
    );
  END LOOP;
END $$;

-- auth.login_attempts: UPDATE — hech kimga; DELETE — faqat erp_system (SECURITY DEFINER app.auth_purge_login_attempts)
CREATE OR REPLACE FUNCTION app.login_attempts_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' AND current_user = 'erp_system' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'append-only jadval: % operatsiyasi taqiqlangan (jadval: %)', TG_OP, TG_TABLE_NAME
    USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

REVOKE UPDATE ON auth.login_attempts FROM erp_system;

CREATE TRIGGER trg_login_attempts_guard BEFORE UPDATE OR DELETE ON auth.login_attempts
  FOR EACH ROW EXECUTE FUNCTION app.login_attempts_guard();
