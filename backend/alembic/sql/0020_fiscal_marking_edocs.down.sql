-- 0020 fiscal_marking_edocs — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

DROP INDEX IF EXISTS app.uq_gr_einvoice_active;
ALTER TABLE IF EXISTS app.goods_receipts DROP CONSTRAINT IF EXISTS fk_gr_poa;
ALTER TABLE IF EXISTS app.goods_receipts DROP CONSTRAINT IF EXISTS fk_gr_einvoice;
ALTER TABLE IF EXISTS app.vat_moves DROP CONSTRAINT IF EXISTS fk_vm_einvoice;
ALTER TABLE IF EXISTS app.sale_lines DROP CONSTRAINT IF EXISTS fk_sl_marking;
DROP TABLE IF EXISTS app.state_report_diffs CASCADE;
DROP TABLE IF EXISTS app.state_reports CASCADE;
DROP TABLE IF EXISTS app.ettn_documents CASCADE;
DROP TABLE IF EXISTS app.powers_of_attorney CASCADE;
DROP TABLE IF EXISTS app.einvoices CASCADE;
DROP TABLE IF EXISTS app.marking_codes CASCADE;
DROP TABLE IF EXISTS app.fiscal_receipts CASCADE;
