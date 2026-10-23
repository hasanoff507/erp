-- 0028 store_agent — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

REVOKE SELECT ON app.onec_agents FROM erp_system;
ALTER TABLE IF EXISTS app.card_terminals DROP CONSTRAINT IF EXISTS fk_ct_agent;
ALTER TABLE IF EXISTS app.cash_registers DROP CONSTRAINT IF EXISTS fk_cr_fiscal_agent;
DROP TABLE IF EXISTS auth.onec_device_authorizations CASCADE;
DROP TABLE IF EXISTS app.onec_task_results CASCADE;
DROP TABLE IF EXISTS app.onec_agent_tasks CASCADE;
DROP TABLE IF EXISTS app.onec_agents CASCADE;
DROP FUNCTION IF EXISTS app.onec_agent_credentials CASCADE;
DROP FUNCTION IF EXISTS app.onec_device_auth_poll CASCADE;
DROP FUNCTION IF EXISTS app.onec_device_auth_deny CASCADE;
DROP FUNCTION IF EXISTS app.onec_device_auth_approve CASCADE;
DROP FUNCTION IF EXISTS app.onec_device_auth_lookup CASCADE;
DROP FUNCTION IF EXISTS app.onec_device_auth_start CASCADE;
