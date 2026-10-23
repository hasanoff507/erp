-- 0009 counterparty_statement_links — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- mijozning ochiq qarz hisob-varag'i havolasi (US-M08-08); token o'zi saqlanmaydi
CREATE TABLE app.counterparty_statement_links (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  counterparty_id  UUID NOT NULL REFERENCES app.counterparties(id),
  token_hash       TEXT NOT NULL UNIQUE, -- token o'zi saqlanmaydi (SHA-256)
  expires_at       TIMESTAMPTZ NOT NULL, -- +30 kun (standart, qaror #54)
  revoked_at       TIMESTAMPTZ NULL,
  last_accessed_at TIMESTAMPTZ NULL,
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
