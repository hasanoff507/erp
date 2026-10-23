-- 0018 docs_expenses_cash — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

ALTER TABLE IF EXISTS app.card_terminal_transactions DROP CONSTRAINT IF EXISTS fk_ctt_settlement;
ALTER TABLE IF EXISTS app.billing_payments DROP CONSTRAINT IF EXISTS fk_bp_invoice_attachment;
DROP TABLE IF EXISTS app.tax_settlements CASCADE;
DROP TABLE IF EXISTS app.card_terminal_settlements CASCADE;
DROP TABLE IF EXISTS app.bank_settlements CASCADE;
DROP TABLE IF EXISTS app.bank_statement_imports CASCADE;
DROP TABLE IF EXISTS app.cash_movements CASCADE;
DROP TABLE IF EXISTS app.expenses CASCADE;
DROP TABLE IF EXISTS app.attachments CASCADE;
DROP TABLE IF EXISTS app.recurring_expenses CASCADE;
DROP TABLE IF EXISTS app.expense_categories CASCADE;
