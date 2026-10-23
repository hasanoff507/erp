-- 0028a fiscal_edocs — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

REVOKE SELECT ON app.cloud_printers FROM erp_system;
DROP INDEX IF EXISTS app.uq_onec_tasks_dedupe;
DROP INDEX IF EXISTS app.uq_tenant_secrets_lookup;
DROP INDEX IF EXISTS app.idx_edoc_signatures_entity;
DROP INDEX IF EXISTS app.idx_print_jobs_queue;
DROP INDEX IF EXISTS app.idx_cloud_printers_branch;
ALTER TABLE IF EXISTS app.sync_exceptions DROP CONSTRAINT IF EXISTS sync_exceptions_kind_check;
ALTER TABLE IF EXISTS app.tenant_secrets DROP CONSTRAINT IF EXISTS tenant_secrets_kind_check;
DROP TABLE IF EXISTS app.onec_agent_logs CASCADE;
DROP TABLE IF EXISTS app.edoc_signatures CASCADE;
DROP TABLE IF EXISTS app.print_jobs CASCADE;
DROP TABLE IF EXISTS app.cloud_printers CASCADE;
DROP TABLE IF EXISTS platform.agent_signed_artifacts CASCADE;
DROP FUNCTION IF EXISTS app.payments_tenant_by_credential CASCADE;
DROP FUNCTION IF EXISTS app.cloud_printer_by_secret CASCADE;

-- 0028a down
ALTER TABLE app.payment_checkouts DROP COLUMN IF EXISTS provider_data;

-- 0028a down
ALTER TABLE app.receipt_lines DROP COLUMN IF EXISTS net_amount;

-- 0028a down
ALTER TABLE app.write_off_lines DROP COLUMN IF EXISTS marking_codes;

ALTER TABLE app.supplier_return_lines DROP COLUMN IF EXISTS marking_codes;

-- 0028a down
REVOKE SELECT (tenant_id, kind, lookup_hash) ON app.tenant_secrets FROM erp_system;

DROP INDEX IF EXISTS app.uq_tenant_secrets_lookup;

ALTER TABLE app.tenant_secrets DROP COLUMN IF EXISTS last_error_at;

ALTER TABLE app.tenant_secrets DROP COLUMN IF EXISTS last_error;

ALTER TABLE app.tenant_secrets DROP COLUMN IF EXISTS last_ok_at;

ALTER TABLE app.tenant_secrets DROP COLUMN IF EXISTS key_last4;

ALTER TABLE app.tenant_secrets DROP COLUMN IF EXISTS lookup_hash;

ALTER TABLE app.tenant_secrets DROP CONSTRAINT IF EXISTS tenant_secrets_kind_check;

ALTER TABLE app.tenant_secrets ADD CONSTRAINT tenant_secrets_kind_check
  CHECK (kind IN ('faktura_uz','crpt','click','payme','uzum','uzqr','fiscal_partner','eimzo',
                  'card_terminal_vendor')) NOT VALID;

-- 0028a down
DELETE FROM app.sync_exceptions WHERE kind = 'marking_code_duplicate';

ALTER TABLE app.sync_exceptions DROP CONSTRAINT IF EXISTS sync_exceptions_kind_check;

ALTER TABLE app.sync_exceptions ADD CONSTRAINT sync_exceptions_kind_check CHECK (kind IN ('price_mismatch','archived_product','stock_negative',
    'debt_limit_exceeded_offline','approval_limit_exceeded_offline','receipt_seq_conflict',
    'debt_overpayment_offline','debt_allocation_mismatch','late_in_closed_period','cost_unknown',
    'count_late_move','card_result_mismatch','card_orphan_transaction',
    'actor_unverified','late_in_closed_shift'));

-- 0028a down
ALTER TABLE app.onec_agent_tasks DROP COLUMN IF EXISTS dedupe_key;

-- 0028a down
DROP FUNCTION IF EXISTS app.payments_tenant_by_credential(text, bytea);
