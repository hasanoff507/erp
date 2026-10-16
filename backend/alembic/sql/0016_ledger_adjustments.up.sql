-- 0016 ledger_adjustments — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- qo'lda buxgalteriya tuzatishi uchun hujjat; bir bosqichli (post darhol
-- status=posted qaytaradi, draft bosqichi yo'q), doc_sequences kodi 'BX'.
CREATE TABLE app.ledger_adjustments (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  branch_id            UUID NOT NULL REFERENCES app.branches(id),
  number               TEXT NULL,
  temp_number          TEXT NULL,
  doc_date             DATE NOT NULL, -- = ledger_entries.entry_date, joriy ochiq davr; istisno — account_dt yoki account_kt
                       -- = '0000' bo'lgan boshlang'ich balans yozuvi: go_live_date − 1 (shu davr yopilmagan bo'lsa; 13 §2.23)
  status               TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  account_dt           TEXT NOT NULL CHECK (account_dt ~ '^[0-9]{4}$'),
  account_kt           TEXT NOT NULL CHECK (account_kt ~ '^[0-9]{4}$'),
  amount               NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  analytics            JSONB NOT NULL DEFAULT '{}', -- ledger_entries.analytics ga ko'chiriladi (counterparty_id, employee_id, tax_type …)
  correction_of_period DATE NULL CHECK (correction_of_period IS NULL OR extract(day FROM correction_of_period) = 1),
  created_by           UUID NOT NULL REFERENCES app.users(id),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at            TIMESTAMPTZ NULL,
  cancelled_at         TIMESTAMPTZ NULL,
  cancelled_by         UUID NULL REFERENCES app.users(id),
  cancel_reason        TEXT NULL,
  client_event_id      UUID NULL,
  device_id            UUID NULL REFERENCES app.devices(id),
  comment              TEXT NOT NULL, -- majburiy (20-api-moliya-admin.md #10)
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK (account_dt <> account_kt)
);
