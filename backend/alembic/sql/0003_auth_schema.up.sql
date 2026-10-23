-- 0003 auth_schema — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE platform.oauth_clients (
  id                  UUID PRIMARY KEY DEFAULT app.uuidv7(),
  client_id           TEXT NOT NULL UNIQUE,
  client_type         TEXT NOT NULL CHECK (client_type IN ('confidential','public')),
  name                TEXT NOT NULL,
  client_secret_encrypted TEXT NULL, -- public mijozda NULL
  redirect_uris       TEXT[] NOT NULL DEFAULT '{}',
  allowed_grant_types TEXT[] NOT NULL DEFAULT '{}',
  allowed_scopes      TEXT[] NOT NULL DEFAULT '{}',
  status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','pending_secret','disabled')),
  -- pending_secret — seed qilingan maxfiy mijoz, sir deploy vaqtida yoziladi (5.1); AS bunday mijozni rad etadi
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (client_type = 'public' OR client_secret_encrypted IS NOT NULL OR status = 'pending_secret')
);

CREATE TABLE auth.user_credentials (
  user_id              UUID PRIMARY KEY, -- FK app.users(id), pastda ALTER bilan qo'shiladi
  password_hash        TEXT NULL,
  password_algo        TEXT NOT NULL DEFAULT 'argon2id',
  password_updated_at  TIMESTAMPTZ NULL,
  pin_hash             TEXT NULL,
  pin_updated_at       TIMESTAMPTZ NULL,
  failed_login_count   INT NOT NULL DEFAULT 0,
  locked_until         TIMESTAMPTZ NULL,
  must_change_password BOOLEAN NOT NULL DEFAULT false,
  must_change_pin      BOOLEAN NOT NULL DEFAULT false,
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE auth.otp_challenges (
  id           UUID PRIMARY KEY DEFAULT app.uuidv7(),
  phone        TEXT NOT NULL,
  purpose      TEXT NOT NULL CHECK (purpose IN ('signup','recovery','invite','admin_reset','pin_reset','data_export')),
  channel      TEXT NOT NULL CHECK (channel IN ('telegram','sms')) DEFAULT 'telegram', -- (qaror #34) qaysi kanal orqali yuborilgani
  code_hash    TEXT NOT NULL,
  attempts     INT NOT NULL DEFAULT 0,
  max_attempts INT NOT NULL DEFAULT 5,
  expires_at   TIMESTAMPTZ NOT NULL,
  verified_at  TIMESTAMPTZ NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_otp_challenges_phone ON auth.otp_challenges (phone, purpose, created_at DESC);

CREATE TABLE auth.login_attempts (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  phone          TEXT NOT NULL,
  ip             INET NULL,
  success        BOOLEAN NOT NULL,
  failure_reason TEXT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_login_attempts_phone ON auth.login_attempts (phone, created_at DESC);

CREATE INDEX idx_login_attempts_ip ON auth.login_attempts (ip, created_at DESC);

CREATE TABLE auth.authorization_codes (
  code_hash             TEXT PRIMARY KEY,
  client_id             UUID NOT NULL REFERENCES platform.oauth_clients(id),
  user_id               UUID NOT NULL, -- FK app.users(id), pastda
  tenant_id             UUID NULL, -- FK app.tenants(id), pastda; tenant tanlanmagan bo'lsa NULL
  code_challenge        TEXT NOT NULL,
  code_challenge_method TEXT NOT NULL DEFAULT 'S256' CHECK (code_challenge_method = 'S256'),
  redirect_uri          TEXT NOT NULL,
  scope                 TEXT NOT NULL,
  expires_at            TIMESTAMPTZ NOT NULL,
  used_at               TIMESTAMPTZ NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE auth.refresh_tokens (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  token_hash           TEXT NOT NULL UNIQUE,
  family_id            UUID NOT NULL,
  client_id            UUID NOT NULL REFERENCES platform.oauth_clients(id),
  user_id              UUID NOT NULL, -- FK app.users(id)
  tenant_id            UUID NULL, -- FK app.tenants(id)
  device_id            UUID NULL, -- FK app.devices(id)
  scope                TEXT NOT NULL,
  issued_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at           TIMESTAMPTZ NOT NULL,
  used_at              TIMESTAMPTZ NULL,
  replaced_by_id       UUID NULL REFERENCES auth.refresh_tokens(id),
  revoked_at           TIMESTAMPTZ NULL,
  revoked_reason       TEXT NULL,
  suspended_at         TIMESTAMPTZ NULL
);

CREATE INDEX idx_refresh_tokens_family ON auth.refresh_tokens (family_id);

CREATE INDEX idx_refresh_tokens_device ON auth.refresh_tokens (device_id) WHERE device_id IS NOT NULL;

CREATE TABLE auth.sessions (
  id                      UUID PRIMARY KEY DEFAULT app.uuidv7(), -- = sid
  user_id                 UUID NOT NULL, -- FK app.users(id)
  tenant_id               UUID NULL, -- FK app.tenants(id)
  client_id               UUID NOT NULL REFERENCES platform.oauth_clients(id),
  device_id               UUID NULL, -- FK app.devices(id)
  current_refresh_token_id UUID NULL REFERENCES auth.refresh_tokens(id),
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  idle_expires_at         TIMESTAMPTZ NOT NULL,
  absolute_expires_at     TIMESTAMPTZ NOT NULL,
  revoked_at              TIMESTAMPTZ NULL,
  revoked_reason          TEXT NULL,
  ip                      INET NULL,
  user_agent              TEXT NULL
);

CREATE INDEX idx_sessions_user ON auth.sessions (user_id);

-- (qaror #34) Google bilan kirish — tashqi OIDC identity provider bog'lash
-- (`14-autentifikatsiya-oauth2.md` §2.2). `users` kabi tenant-mustaqil (global), RLS yo'q — auth.* jadvallar
-- qatorida emas, lekin shu sababli ham ilova darajasida faqat user_id orqali filtrlanadi.
CREATE TABLE app.user_identities (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  user_id           UUID NOT NULL REFERENCES app.users(id),
  provider          TEXT NOT NULL CHECK (provider IN ('google')),
  provider_user_id  TEXT NOT NULL, -- Google `sub`
  email             TEXT NULL,
  email_verified    BOOLEAN NOT NULL DEFAULT false,
  linked_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_user_id)
);

CREATE INDEX idx_user_identities_user ON app.user_identities (user_id);

-- auth.* va platform.* jadvallardagi "pastda qo'shiladi" deb belgilangan FK'lar:
ALTER TABLE auth.user_credentials      ADD CONSTRAINT fk_uc_user      FOREIGN KEY (user_id) REFERENCES app.users(id);

ALTER TABLE auth.authorization_codes   ADD CONSTRAINT fk_ac_user      FOREIGN KEY (user_id) REFERENCES app.users(id);

ALTER TABLE auth.authorization_codes   ADD CONSTRAINT fk_ac_tenant    FOREIGN KEY (tenant_id) REFERENCES app.tenants(id);

ALTER TABLE auth.refresh_tokens        ADD CONSTRAINT fk_rt_user      FOREIGN KEY (user_id) REFERENCES app.users(id);

ALTER TABLE auth.refresh_tokens        ADD CONSTRAINT fk_rt_tenant    FOREIGN KEY (tenant_id) REFERENCES app.tenants(id);

ALTER TABLE auth.sessions              ADD CONSTRAINT fk_se_user      FOREIGN KEY (user_id) REFERENCES app.users(id);

ALTER TABLE auth.sessions              ADD CONSTRAINT fk_se_tenant    FOREIGN KEY (tenant_id) REFERENCES app.tenants(id);

ALTER TABLE auth.refresh_tokens ADD CONSTRAINT fk_rt_device FOREIGN KEY (device_id) REFERENCES app.devices(id);

ALTER TABLE auth.sessions       ADD CONSTRAINT fk_se_device FOREIGN KEY (device_id) REFERENCES app.devices(id);

CREATE TABLE app.license_tokens (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  device_id   UUID NOT NULL REFERENCES app.devices(id),
  issued_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_until TIMESTAMPTZ NOT NULL,
  jti         UUID NOT NULL UNIQUE,
  server_time TIMESTAMPTZ NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
