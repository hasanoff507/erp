-- 0006 counterparties — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.counterparties (
  id                    UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id             UUID NOT NULL REFERENCES app.tenants(id),
  kind                  TEXT NOT NULL CHECK (kind IN ('person','company')),
  name                  TEXT NOT NULL,
  phone                 TEXT NULL,
  stir                  TEXT NULL,
  legal_address         TEXT NULL,
  bank_account          TEXT NULL,
  bank_mfo              TEXT NULL,
  vat_payer             BOOLEAN NULL,
  vat_payer_checked_at  TIMESTAMPTZ NULL,
  is_customer           BOOLEAN NOT NULL DEFAULT false,
  is_supplier           BOOLEAN NOT NULL DEFAULT false,
  is_founder            BOOLEAN NOT NULL DEFAULT false, -- ta'sischi/egasi — "Egasi oldi" 4890 analitikasi (13 §2.18)
  credit_limit          NUMERIC(18,2) NULL, -- null = limitsiz
  standing_discount_pct NUMERIC(5,2) NULL CHECK (standing_discount_pct BETWEEN 0 AND 100),
  notify_consent        BOOLEAN NOT NULL DEFAULT false,
  notify_consent_at     TIMESTAMPTZ NULL,
  debt_due_date         DATE NULL, -- yagona joriy va'da sanasi (o'zgaruvchan; debt_moves append-only, bu yerda yangilanadi)
  telegram_chat_id      TEXT NULL,
  note                  TEXT NULL,
  archived_at           TIMESTAMPTZ NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  version               INT NOT NULL DEFAULT 1
);

CREATE INDEX idx_counterparties_name_trgm ON app.counterparties USING gin (name gin_trgm_ops);

CREATE TABLE app.debt_doubtful_flags (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  flagged_by      UUID NOT NULL REFERENCES app.users(id), -- faqat Egasi (ilova darajasida tekshiriladi)
  reason          TEXT NOT NULL,
  flagged_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  unflagged_at    TIMESTAMPTZ NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_debt_doubtful_active ON app.debt_doubtful_flags (tenant_id, counterparty_id) WHERE unflagged_at IS NULL;
