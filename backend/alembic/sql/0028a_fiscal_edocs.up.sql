-- 0028a fiscal_edocs — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- 0028a fiscal_edocs
CREATE TABLE platform.agent_signed_artifacts (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  kind        TEXT NOT NULL CHECK (kind IN ('task_keyset','update_manifest')),
  channel     TEXT NULL CHECK (channel IN ('stable','pilot')),
  version     TEXT NOT NULL CHECK (length(version) BETWEEN 1 AND 64), -- task_keyset: ver; update_manifest: SemVer
  body        TEXT NOT NULL,      -- task_keyset: compact JWS; update_manifest: base64(manifest JSON baytlari)
  signature   TEXT NULL,          -- update_manifest: base64(Ed25519 imzo); task_keyset: NULL (imzo JWS ichida)
  kid         TEXT NOT NULL,      -- agent_update ildiz kalitining RFC 7638 thumbprint'i
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((kind = 'update_manifest') = (channel IS NOT NULL)),
  CHECK ((kind = 'update_manifest') = (signature IS NOT NULL)),
  UNIQUE NULLS NOT DISTINCT (kind, channel, version)
);

GRANT SELECT ON platform.agent_signed_artifacts TO erp_app;

-- 0028a fiscal_edocs
ALTER TABLE app.payment_checkouts ADD COLUMN provider_data JSONB NOT NULL DEFAULT '{}'::jsonb;

-- 0028a fiscal_edocs
CREATE TABLE app.cloud_printers (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  name             TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  protocol         TEXT NOT NULL CHECK (protocol IN ('star_cloudprnt','epson_sdp')),
  model            TEXT NULL CHECK (model IS NULL OR length(model) <= 100), -- 'Star TSP143IV', 'Epson TM-m30III'
  secret_hash      TEXT NOT NULL CHECK (secret_hash ~ '^[0-9a-f]{64}$'),   -- SHA-256(maxfiy kalit), kalitning o'zi saqlanmaydi
  status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','archived')),
  printer_mac      TEXT NULL,          -- Star so'rovidagi printerMAC (oxirgi), ma'lumot uchun
  last_poll_at     TIMESTAMPTZ NULL,   -- oxirgi so'rov — "onlayn" belgisi (60 s ichida)
  last_status      TEXT NULL,          -- printer xabar qilgan holat (Star statusCode, Epson natija kodi), ≤ 200 belgi
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          INT NOT NULL DEFAULT 1
);

CREATE INDEX idx_cloud_printers_branch ON app.cloud_printers (tenant_id, branch_id) WHERE status <> 'archived';

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON app.cloud_printers
  FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

ALTER TABLE app.cloud_printers ENABLE ROW LEVEL SECURITY;

ALTER TABLE app.cloud_printers FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON app.cloud_printers
  USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id());

GRANT SELECT, INSERT, UPDATE ON app.cloud_printers TO erp_app;

CREATE TABLE app.print_jobs (
  id               UUID PRIMARY KEY,   -- klient UUIDv7 (idempotentlik kaliti)
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  cloud_printer_id UUID NOT NULL REFERENCES app.cloud_printers(id),
  kind             TEXT NOT NULL CHECK (kind IN ('receipt','test','label')),
  width_dots       INT NOT NULL CHECK (width_dots BETWEEN 8 AND 1024),
  height_dots      INT NOT NULL CHECK (height_dots BETWEEN 1 AND 20000),
  data             BYTEA NULL,         -- 1 bit/piksel, qator = ceil(width_dots/8) bayt, MSB — chap, 1 — qora
  data_sha256      TEXT NOT NULL CHECK (data_sha256 ~ '^[0-9a-f]{64}$'), -- takroriy POST mazmuni solishtiriladi
  status           TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','printing','done','failed')),
  result_code      TEXT NULL,          -- printer natijasi (Star DELETE code, Epson code) yoki 'expired'
  attempts         INT NOT NULL DEFAULT 0 CHECK (attempts >= 0), -- printer ishni necha marta olgan
  expires_at       TIMESTAMPTZ NOT NULL, -- shu vaqtgacha olinmagan 'queued' ish → 'failed' ('expired')
  device_id        UUID NULL REFERENCES app.devices(id),
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  printing_at      TIMESTAMPTZ NULL,
  finished_at      TIMESTAMPTZ NULL,
  CHECK ((status IN ('queued','printing')) = (data IS NOT NULL)),
  CHECK ((status IN ('done','failed')) = (finished_at IS NOT NULL))
);

CREATE INDEX idx_print_jobs_queue ON app.print_jobs (cloud_printer_id, id) WHERE status IN ('queued','printing');

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON app.print_jobs
  FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

ALTER TABLE app.print_jobs ENABLE ROW LEVEL SECURITY;

ALTER TABLE app.print_jobs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON app.print_jobs
  USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id());

GRANT SELECT, INSERT, UPDATE ON app.print_jobs TO erp_app;

-- 0028a fiscal_edocs
ALTER TABLE app.receipt_lines ADD COLUMN net_amount NUMERIC(18,2) NULL CHECK (net_amount IS NULL OR net_amount >= 0);

-- 0028a fiscal_edocs
ALTER TABLE app.supplier_return_lines ADD COLUMN marking_codes TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE app.write_off_lines ADD COLUMN marking_codes TEXT[] NOT NULL DEFAULT '{}';

-- 0028a fiscal_edocs
CREATE TABLE app.edoc_signatures (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  entity             TEXT NOT NULL CHECK (entity IN ('einvoices','ettn_documents','powers_of_attorney')),
  entity_id          UUID NOT NULL,
  action             TEXT NOT NULL CHECK (action IN ('sign','accept','reject')),
  document_hash      TEXT NOT NULL,
  signature_pkcs7    TEXT NOT NULL, -- base64 PKCS#7 (attached), E-IMZO brauzerda yaratgan
  certificate_serial TEXT NULL,
  signer_tin         TEXT NULL,     -- sertifikatdagi STIR/JShShIR (tekshiruv natijasi)
  signed_by          UUID NOT NULL REFERENCES app.users(id),
  signed_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_edoc_signatures_entity ON app.edoc_signatures (tenant_id, entity, entity_id);

ALTER TABLE app.edoc_signatures ENABLE ROW LEVEL SECURITY;

ALTER TABLE app.edoc_signatures FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON app.edoc_signatures
  USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id());

GRANT SELECT, INSERT ON app.edoc_signatures TO erp_app;

-- 0028a fiscal_edocs
ALTER TABLE app.tenant_secrets DROP CONSTRAINT tenant_secrets_kind_check;

ALTER TABLE app.tenant_secrets ADD CONSTRAINT tenant_secrets_kind_check
  CHECK (kind IN ('faktura_uz','didox','crpt','click','payme','uzum','uzqr','fiscal_partner','eimzo',
                  'card_terminal_vendor'));

ALTER TABLE app.tenant_secrets ADD COLUMN lookup_hash BYTEA NULL;

ALTER TABLE app.tenant_secrets ADD COLUMN key_last4 TEXT NULL;

ALTER TABLE app.tenant_secrets ADD COLUMN last_ok_at TIMESTAMPTZ NULL;

ALTER TABLE app.tenant_secrets ADD COLUMN last_error TEXT NULL;

ALTER TABLE app.tenant_secrets ADD COLUMN last_error_at TIMESTAMPTZ NULL;

CREATE UNIQUE INDEX uq_tenant_secrets_lookup ON app.tenant_secrets (kind, lookup_hash) WHERE lookup_hash IS NOT NULL;

-- 0028a fiscal_edocs
ALTER TABLE app.sync_exceptions DROP CONSTRAINT sync_exceptions_kind_check;

ALTER TABLE app.sync_exceptions ADD CONSTRAINT sync_exceptions_kind_check CHECK (kind IN ('price_mismatch','archived_product','stock_negative',
    'debt_limit_exceeded_offline','approval_limit_exceeded_offline','receipt_seq_conflict',
    'debt_overpayment_offline','debt_allocation_mismatch','late_in_closed_period','cost_unknown',
    'count_late_move','card_result_mismatch','card_orphan_transaction',
    'actor_unverified','late_in_closed_shift','marking_code_duplicate'));

-- 0028a fiscal_edocs
ALTER TABLE app.onec_agent_tasks ADD COLUMN dedupe_key TEXT NULL
  CHECK (dedupe_key IS NULL OR length(dedupe_key) BETWEEN 1 AND 200);

CREATE UNIQUE INDEX uq_onec_tasks_dedupe ON app.onec_agent_tasks (agent_id, dedupe_key)
  WHERE dedupe_key IS NOT NULL AND status IN ('queued','leased');

-- 0028a fiscal_edocs
CREATE TABLE app.onec_agent_logs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  agent_id        UUID NOT NULL REFERENCES app.onec_agents(id),
  client_log_id   UUID NOT NULL,          -- agent beradi (takror yuborishda dedupe)
  base_id         UUID NULL,              -- FK fk_onec_logs_base (0029)
  task_id         UUID NULL,
  at              TIMESTAMPTZ NOT NULL,   -- agent vaqti (server_time ofseti bilan tuzatilgan)
  level           TEXT NOT NULL CHECK (level IN ('debug','info','warn','error')),
  code            TEXT NULL,
  message         TEXT NOT NULL CHECK (length(message) <= 4000),
  context         JSONB NOT NULL DEFAULT '{}',
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (agent_id, client_log_id)
);

CREATE INDEX idx_onec_agent_logs_agent_time ON app.onec_agent_logs (agent_id, at DESC);

ALTER TABLE app.onec_agent_logs ENABLE ROW LEVEL SECURITY;

ALTER TABLE app.onec_agent_logs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON app.onec_agent_logs
  USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id());

GRANT SELECT, INSERT, DELETE ON app.onec_agent_logs TO erp_app;

-- 0028a fiscal_edocs
GRANT CREATE ON SCHEMA app TO erp_system;

CREATE OR REPLACE FUNCTION app.cloud_printer_by_secret(p_printer_id uuid, p_secret_hash text)
RETURNS TABLE (tenant_id uuid, branch_id uuid, protocol text) LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT p.tenant_id, p.branch_id, p.protocol FROM app.cloud_printers p
  WHERE p.id = p_printer_id AND p.secret_hash = p_secret_hash AND p.status = 'active';
$$;

GRANT SELECT ON app.cloud_printers TO erp_system;

ALTER FUNCTION app.cloud_printer_by_secret(uuid, text) OWNER TO erp_system;

REVOKE ALL ON FUNCTION app.cloud_printer_by_secret(uuid, text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.cloud_printer_by_secret(uuid, text) TO erp_app;

REVOKE CREATE ON SCHEMA app FROM erp_system;

-- 0028a fiscal_edocs
GRANT CREATE ON SCHEMA app TO erp_system;

CREATE OR REPLACE FUNCTION app.payments_tenant_by_credential(p_kind text, p_lookup_hash bytea)
RETURNS TABLE (tenant_id uuid) LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT s.tenant_id FROM app.tenant_secrets s
  WHERE s.kind = p_kind AND s.kind IN ('payme','uzum') AND s.lookup_hash = p_lookup_hash;
$$;

GRANT SELECT (tenant_id, kind, lookup_hash) ON app.tenant_secrets TO erp_system;

ALTER FUNCTION app.payments_tenant_by_credential(text, bytea) OWNER TO erp_system;

REVOKE ALL ON FUNCTION app.payments_tenant_by_credential(text, bytea) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.payments_tenant_by_credential(text, bytea) TO erp_app;

REVOKE CREATE ON SCHEMA app FROM erp_system;
