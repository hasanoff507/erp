-- 0027b debts_finance — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- 0027b debts_finance
ALTER TABLE app.bank_settlements ADD COLUMN version INT NOT NULL DEFAULT 1;

ALTER TABLE app.card_terminal_transactions ADD COLUMN bank_settlement_id UUID NULL REFERENCES app.bank_settlements(id);

CREATE INDEX idx_ctt_bank_settlement ON app.card_terminal_transactions (bank_settlement_id)
  WHERE bank_settlement_id IS NOT NULL;

-- 0027b debts_finance
CREATE TABLE app.debt_writeoff_allocations (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  debt_writeoff_id UUID NOT NULL REFERENCES app.debt_writeoffs(id),
  target_doc_type  TEXT NOT NULL CHECK (target_doc_type IN ('sales','debt_openings')),
  target_doc_id    UUID NOT NULL,
  amount           NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_debt_writeoff_alloc_target ON app.debt_writeoff_allocations (tenant_id, target_doc_type, target_doc_id);

CREATE INDEX idx_debt_payment_alloc_target ON app.debt_payment_allocations (tenant_id, target_doc_type, target_doc_id);

ALTER TABLE app.debt_writeoff_allocations ENABLE ROW LEVEL SECURITY;

ALTER TABLE app.debt_writeoff_allocations FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON app.debt_writeoff_allocations
  USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id());

GRANT SELECT, INSERT ON app.debt_writeoff_allocations TO erp_app;
