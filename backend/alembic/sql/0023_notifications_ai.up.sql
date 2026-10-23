-- 0023 notifications_ai — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.telegram_links (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  user_id    UUID NOT NULL REFERENCES app.users(id),
  chat_id    TEXT NOT NULL,
  linked_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ NULL,
  UNIQUE (tenant_id, user_id)
);

CREATE TABLE app.notification_settings (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  user_id    UUID NOT NULL REFERENCES app.users(id),
  kind       TEXT NOT NULL,
  enabled    BOOLEAN NOT NULL DEFAULT true,
  time       TIME NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id, kind)
);

CREATE TABLE app.notifications_log (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  channel    TEXT NOT NULL CHECK (channel IN ('telegram','sms')),
  recipient  TEXT NOT NULL,
  template   TEXT NOT NULL,
  status     TEXT NOT NULL,
  cost       NUMERIC(18,2) NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.ai_training_samples (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NULL, -- anonimlashtirilgandan keyin olib tashlanadi
  feature         TEXT NOT NULL,
  input_redacted  JSONB NOT NULL,
  output_corrected JSONB NULL,
  consent_ref     UUID NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.ai_feedback (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  ai_request_id        UUID NOT NULL REFERENCES app.ai_requests(id),
  rating               SMALLINT NULL CHECK (rating IN (-1, 1)),
  correction           TEXT NULL,
  consent_for_training BOOLEAN NOT NULL DEFAULT false,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.tenant_glossary (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  term       TEXT NOT NULL,
  meaning    TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, term)
);
