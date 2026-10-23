-- 0015 registers — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

DROP TRIGGER IF EXISTS trg_no_update_delete ON app.doc_approvals;
DROP TRIGGER IF EXISTS trg_login_attempts_guard ON auth.login_attempts;
ALTER TABLE IF EXISTS app.write_off_lines DROP CONSTRAINT IF EXISTS fk_wol_lot;
DROP TABLE IF EXISTS app.vat_moves CASCADE;
DROP TABLE IF EXISTS app.ledger_entries CASCADE;
DROP TABLE IF EXISTS app.cash_moves CASCADE;
DROP TABLE IF EXISTS app.debt_balances CASCADE;
DROP TABLE IF EXISTS app.debt_moves CASCADE;
DROP TABLE IF EXISTS app.stock_balances CASCADE;
DROP TABLE IF EXISTS app.avg_costs CASCADE;
DROP TABLE IF EXISTS app.stock_lots CASCADE;
DROP TABLE IF EXISTS app.stock_moves CASCADE;
DROP TABLE IF EXISTS app.supplier_return_lines CASCADE;
DROP TABLE IF EXISTS app.supplier_returns CASCADE;
DROP FUNCTION IF EXISTS app.login_attempts_guard CASCADE;
