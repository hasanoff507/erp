-- 0024 audit_periods — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.audit_log (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  user_id    UUID NULL REFERENCES app.users(id),
  action     TEXT NOT NULL,
  entity     TEXT NOT NULL,
  entity_id  UUID NULL,
  before     JSONB NULL,
  after      JSONB NULL,
  ip         INET NULL,
  device_id  UUID NULL,
  at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_log_tenant_time ON app.audit_log (tenant_id, at DESC);

CREATE INDEX idx_audit_log_entity ON app.audit_log (tenant_id, entity, entity_id);

CREATE TABLE app.period_closings (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  period     DATE NOT NULL,
  closed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_by  UUID NOT NULL REFERENCES app.users(id),
  UNIQUE (tenant_id, period)
);

-- 0024 audit_periods
REVOKE UPDATE, DELETE ON app.audit_log FROM erp_app;

CREATE TRIGGER trg_no_update_delete BEFORE UPDATE OR DELETE ON app.audit_log
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
