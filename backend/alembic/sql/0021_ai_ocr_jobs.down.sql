-- 0021 ai_ocr_jobs — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

ALTER TABLE IF EXISTS app.goods_receipts DROP CONSTRAINT IF EXISTS fk_gr_ocr_job;
DROP TABLE IF EXISTS app.ai_ocr_jobs CASCADE;
DROP TABLE IF EXISTS app.ai_requests CASCADE;
