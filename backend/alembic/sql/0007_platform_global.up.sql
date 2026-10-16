-- 0007 platform_global — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE platform.units (
  code          TEXT PRIMARY KEY,
  is_fractional BOOLEAN NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE platform.plans (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  code        TEXT NOT NULL UNIQUE,
  price_month NUMERIC(18,2) NOT NULL CHECK (price_month >= 0),
  price_year  NUMERIC(18,2) NOT NULL CHECK (price_year >= 0),
  limits      JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE platform.addons (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  code        TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  price_month NUMERIC(18,2) NOT NULL CHECK (price_month >= 0),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE platform.signing_keys (
  kid                     UUID PRIMARY KEY DEFAULT app.uuidv7(),
  algorithm               TEXT NOT NULL CHECK (algorithm IN ('EdDSA','ES256')),
  purpose                 TEXT NOT NULL CHECK (purpose IN ('access','license','onec_task','agent_update')),
  -- onec_task — 1C agentiga beriladigan vazifa paketlari imzosi; agent_update — 1C agenti yangilanish manifesti imzosi
  -- (qaror #38, `33-1c-integratsiya.md`, `34-1c-agent.md`)
  public_key              TEXT NOT NULL,
  private_key_encrypted   TEXT NOT NULL,
  status                  TEXT NOT NULL CHECK (status IN ('next','active','retired')),
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at            TIMESTAMPTZ NULL,
  retired_at              TIMESTAMPTZ NULL
);

-- har (purpose) uchun bir vaqtda faqat bitta 'active' kalit
CREATE UNIQUE INDEX uq_signing_keys_active ON platform.signing_keys (purpose) WHERE status = 'active';

-- (qaror #55) Markaziy bankning kunlik rasmiy kursi — scheduler `fetch_fx_rates` har kuni 09:30 (Toshkent)
-- cbu.uz JSON'dan yozadi; global, tenant ma'lumoti emas (RLS istisnosi). Kurs olinmasa ERP_FX_USD_UZS_FALLBACK.
CREATE TABLE platform.fx_rates (
  rate_date  DATE NOT NULL,
  currency   TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'), -- 'USD'
  rate       NUMERIC(18,4) NOT NULL CHECK (rate > 0),      -- 1 birlik valyuta = rate so'm
  source     TEXT NOT NULL DEFAULT 'cbu',
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (rate_date, currency)
);

-- (qaror #61) foydalanish shartlari (ommaviy oferta) va rozilik matnlari versiyalari — global, yozish faqat admin yo'li;
-- birinchi versiya yurist imzolagan matn bilan yuklanadi (26 #127 (OQ-042))
CREATE TABLE platform.terms_versions (
  version        TEXT PRIMARY KEY,           -- 'v1', 'v2' ...
  kind           TEXT NOT NULL CHECK (kind IN ('terms','privacy','ai_cross_border')),
  text_url       TEXT NOT NULL,              -- matn (statik sahifa/PDF) havolasi
  text_sha256    TEXT NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
  effective_from TIMESTAMPTZ NOT NULL,
  is_current     BOOLEAN NOT NULL DEFAULT false,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_terms_versions_current ON platform.terms_versions (kind) WHERE is_current;

-- Aylanma solig'i stavkalari (13 §4.3) — global ma'lumotnoma (RLS istisnosi), seed 5.1; erp_app — faqat SELECT.
-- code: retail_<branches.settlement_category> (chakana), general, tobacco (products.turnover_tax_group),
-- sole_proprietor (tenants.legal_form). Stavka o'zgarsa — yangi valid_from qatori.
CREATE TABLE platform.turnover_tax_rates (
  code       TEXT NOT NULL,
  rate_pct   NUMERIC(5,2) NOT NULL CHECK (rate_pct BETWEEN 0 AND 100),
  valid_from DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (code, valid_from)
);

-- Karta BIN qoidalari (qaror #71) — global ma'lumotnoma (RLS istisnosi); erp_app — faqat SELECT, yozish — platforma
-- admin yo'li. Integratsiyalangan terminal natijasida card_type bo'lmasa, terminal bergan BIN (PAN'ning birinchi
-- 6–8 raqami) shu jadvaldan eng uzun prefiks bo'yicha qidiriladi; topilmasa — card_type='unknown' (card_type_source='bin_table'); kassir karta turini tanlamaydi.
-- To'liq PAN hech qachon saqlanmaydi: BIN faqat qidiruv paytida ishlatiladi, to'lov qatoriga card_mask (4+4) yoziladi.
CREATE TABLE platform.card_bin_rules (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  bin_prefix  TEXT NOT NULL CHECK (bin_prefix ~ '^[0-9]{6,8}$'),
  card_type   TEXT NOT NULL CHECK (card_type IN ('personal','corporate','social')),
  card_scheme TEXT NULL CHECK (card_scheme IN ('uzcard','humo','visa','mastercard','unionpay','mir','other')),
  issuer      TEXT NULL,          -- emitent bank nomi (ma'lumot uchun)
  source      TEXT NOT NULL,      -- ro'yxat manbasi (ekvayer bank / Uzcard / Humo xati raqami va sanasi)
  valid_from  DATE NOT NULL,
  valid_to    DATE NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (bin_prefix, valid_from),
  CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE platform.platform_admins (
  id                  UUID PRIMARY KEY DEFAULT app.uuidv7(),
  user_id             UUID NOT NULL UNIQUE REFERENCES app.users(id),
  role                TEXT NOT NULL,
  mfa_secret_encrypted TEXT NOT NULL,
  allowed_ips         CIDR[] NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.subscriptions (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL UNIQUE REFERENCES app.tenants(id),
  plan_id            UUID NOT NULL REFERENCES platform.plans(id),
  period             TEXT NOT NULL CHECK (period IN ('month','year')),
  current_period_end TIMESTAMPTZ NOT NULL,
  grace_ends_at      TIMESTAMPTZ NULL,
  status             TEXT NOT NULL CHECK (status IN ('trial','active','grace','restricted','closed')) DEFAULT 'trial',
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  version            INT NOT NULL DEFAULT 1
);

CREATE TABLE app.tenant_addons (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  addon_code           TEXT NOT NULL REFERENCES platform.addons(code),
  quantity             INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
  price_month_snapshot NUMERIC(18,2) NOT NULL,
  added_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  removed_at           TIMESTAMPTZ NULL
);

CREATE INDEX idx_tenant_addons_active ON app.tenant_addons (tenant_id) WHERE removed_at IS NULL;

-- Payme CreateTransaction'da provider_tx_id checkout paytida noma'lum bo'lishi mumkin — NULL ruxsat etiladi.
-- Alohida billing_invoices jadvali yo'q — davr/kvitansiya ustunlari shu jadvalda yetarli.
CREATE TABLE app.billing_payments (
  id                    UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id             UUID NOT NULL REFERENCES app.tenants(id),
  kind                  TEXT NOT NULL DEFAULT 'payment' CHECK (kind IN ('payment','manual_extension','refund')),
                        -- manual_extension — platforma admin qo'lda uzaytirdi (qaror #56): amount=0, provider NULL, reason majburiy
  amount                NUMERIC(18,2) NOT NULL CHECK (amount >= 0),
  provider              TEXT NULL CHECK (provider IN ('click','payme')),
  provider_tx_id        TEXT NULL, -- checkout paytida noma'lum bo'lishi mumkin; UNIQUE (provider, provider_tx_id)
  reason                TEXT NULL,
  actor_user_id         UUID NULL REFERENCES app.users(id), -- manual_extension: platforma admini (tenantga ko'rsatilmaydi, audit)
  status                TEXT NOT NULL CHECK (status IN ('pending','success','failed','cancelled')),
  period                TEXT NOT NULL CHECK (period IN ('month','year')),
  covers_from           DATE NULL, -- success'da to'ldiriladi
  covers_to             DATE NULL,
  amount_breakdown      JSONB NOT NULL DEFAULT '{}', -- {plan, period, addons:[{code, qty, unit_price, months}], discount} snapshot
                        -- (qaror #70: oy = 99000 + 39000 × extra; yil = 950400 + 39000 × 12 × extra — chegirma faqat asosiy tarifga)
  invoice_number        TEXT NULL,
  invoice_attachment_id UUID NULL, -- FK pastda (attachments yaratilgandan keyin) → app.attachments(id)
  created_by            UUID NULL REFERENCES app.users(id),
  paid_at               TIMESTAMPTZ NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_tx_id),
  CHECK (kind = 'manual_extension' OR (provider IS NOT NULL AND amount > 0)),
  CHECK (kind <> 'manual_extension' OR (provider IS NULL AND amount = 0 AND reason IS NOT NULL AND actor_user_id IS NOT NULL))
);

CREATE UNIQUE INDEX uq_billing_invoice_number ON app.billing_payments (invoice_number) WHERE invoice_number IS NOT NULL;

CREATE TABLE app.tenant_tax_regimes (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  valid_from DATE NOT NULL, -- ixtiyoriy o'tish — oy 1-sanasi; 1 mlrd chegarasi/import — shu kundan (SK 462-modda 7, 13-qism; 13 §4.3)
  regime     TEXT NOT NULL CHECK (regime IN ('vat','turnover')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES app.users(id),
  UNIQUE (tenant_id, valid_from)
);

-- (qaror #61) tenant roziliklari — append-only izi (berish va qaytarib olish alohida qator); joriy holat
-- tenants.settings.ai_cross_border_enabled va tenants.accepted_terms_* da (POST /tenant/consents)
CREATE TABLE app.consents (
  id            UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id     UUID NOT NULL REFERENCES app.tenants(id),
  subject       TEXT NOT NULL DEFAULT 'tenant' CHECK (subject IN ('tenant','user')),
  user_id       UUID NULL REFERENCES app.users(id), -- rozilikni bergan/qaytargan shaxs (Egasi)
  purpose       TEXT NOT NULL CHECK (purpose IN ('terms','ai_cross_border','ai_training')),
  terms_version TEXT NOT NULL REFERENCES platform.terms_versions(version),
  accepted      BOOLEAN NOT NULL,             -- false — qaytarib olish
  ip            INET NULL,
  at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_consents_tenant_purpose ON app.consents (tenant_id, purpose, at DESC);
