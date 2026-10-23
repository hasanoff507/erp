-- 0022 integration_sync — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

DROP TABLE IF EXISTS app.import_jobs CASCADE;
DROP TABLE IF EXISTS app.recost_jobs CASCADE;
DROP TABLE IF EXISTS app.idempotency_keys CASCADE;
DROP TABLE IF EXISTS app.sync_exceptions CASCADE;
DROP TABLE IF EXISTS app.sync_receipts CASCADE;
DROP TABLE IF EXISTS app.outbox_jobs CASCADE;
DROP TABLE IF EXISTS app.tenant_secrets CASCADE;
