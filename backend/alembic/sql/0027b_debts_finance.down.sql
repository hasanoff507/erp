-- 0027b debts_finance — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

DROP INDEX IF EXISTS app.idx_debt_payment_alloc_target;
DROP INDEX IF EXISTS app.idx_debt_writeoff_alloc_target;
DROP INDEX IF EXISTS app.idx_ctt_bank_settlement;
DROP TABLE IF EXISTS app.debt_writeoff_allocations CASCADE;

-- 0027b down
ALTER TABLE app.card_terminal_transactions DROP COLUMN IF EXISTS bank_settlement_id;

ALTER TABLE app.bank_settlements DROP COLUMN IF EXISTS version;
