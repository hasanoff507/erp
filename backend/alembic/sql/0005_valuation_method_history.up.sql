-- 0005 valuation_method_history — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- baholash usuli (FIFO/AVECO) tarixi — faqat yil boshidan o'zgaradi;
-- tenants.settings da valuation_method kaliti yo'q, manba shu jadval. Signup: valid_from = joriy yil
-- 1-yanvar, method='aveco' (yoki tanlangan).
CREATE TABLE app.valuation_method_history (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  valid_from DATE NOT NULL CHECK (extract(month FROM valid_from) = 1 AND extract(day FROM valid_from) = 1),
  method     TEXT NOT NULL CHECK (method IN ('fifo','aveco')),
  created_by UUID NOT NULL REFERENCES app.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, valid_from)
);
