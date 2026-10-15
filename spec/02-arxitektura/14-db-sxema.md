# DB sxemasi (PostgreSQL 16) — amalga oshirishga tayyor spetsifikatsiya

*2026-10-15 · Asos: `01-malumotlar-modeli.md` (barcha jadval/ustun/holatlar), `02-provodka-qoidalari.md` (registrlar, hisob raqamlari), `12-autentifikatsiya-oauth2.md` §19 (auth jadvallari), `05-xavfsizlik-va-audit.md` §3 (RLS qoidalari, istisnolar, SECURITY DEFINER), §2.1–2.2 (huquqlar/limitlar), §6.2 (audit_log o'zgarmasligi), `04-offline-sync.md` (`sync_receipts`, `devices`, `client_event_id`), `09-backend-arxitekturasi.md` (`tenant_transaction`, `idempotency_keys`, posting naqshi), `07-ai-qatlami.md` (`ai_requests` maydonlari), `spec/tekshiruv/00-qarorlar.md`. Loyiha ildizi: `E:/Project/erp`.*

Bu hujjat — `01-malumotlar-modeli.md`da tasvirlangan kontseptual modelni **ishga tushirish mumkin bo'lgan PostgreSQL 16 DDL**ga aylantiradi. 01-hujjatdagi jadval/ustun nomlari **o'zgarishsiz** saqlanadi; qayerda 01 noaniq/ziddiyatli bo'lsa — aniq qaror qabul qilinadi va oxirgi bo'limda ("01 bilan farqlar / aniqlashtirishlar") ro'yxatga olinadi, 01-hujjatning o'zi tahrirlanmaydi.

**Sxema tashkiloti**: uch PostgreSQL sxemasi — `app` (tenant-scoped biznes jadvallari + `tenants`/`users`/`memberships` kabi "yarim-global" jadvallar maxsus RLS siyosati bilan), `auth` (login/token jadvallari — ilova roliga to'g'ridan-to'g'ri kirish yo'q, faqat `SECURITY DEFINER` funksiyalar orqali), `platform` (tenant'siz, haqiqiy global ma'lumotnomalar: tariflar, qo'shimchalar, birliklar, OAuth mijozlari, imzolash kalitlari, platforma adminlari).

---

## 0. Rollar (oldindan)

Barcha quyidagi DDL'dan oldin uch DB rol mavjud bo'lishi kerak (parollar — muhit sirlari, bu yerda ko'rsatilmaydi):

```sql
-- Alembic migratsiyalarini ishga tushiruvchi, barcha ob'ektlarning egasi
CREATE ROLE erp_migrator LOGIN NOSUPERUSER CREATEDB NOCREATEROLE;

-- FastAPI/worker/scheduler/bot ulanadigan rol — BYPASSRLS YO'Q (05-xavfsizlik §3.2)
CREATE ROLE erp_app LOGIN NOSUPERUSER NOBYPASSRLS;

-- SECURITY DEFINER funksiyalarning egasi — BYPASSRLS, lekin LOGIN emas
-- (hech kim to'g'ridan-to'g'ri shu rol bilan ulanmaydi, faqat funksiya ichida "ishlaydi")
CREATE ROLE erp_system NOLOGIN BYPASSRLS;
```

`erp_app` RLS siyosatlariga **to'liq bo'ysunadi** (bu — tenant izolyatsiyasining asosiy DB darajasidagi mexanizmi, `05-xavfsizlik-va-audit.md` Asosiy xulosa 3). `erp_system` — faqat quyida 4-bo'limda ro'yxatlangan `SECURITY DEFINER` funksiyalarning egasi; bu funksiyalar ichida ishlayotgan SQL `erp_system`ning `BYPASSRLS` huquqidan vaqtincha foydalanadi (login/billing kabi tenant-kontekstisiz amallar uchun yagona qonuniy yo'l).

---

## 1. Konventsiyalar

### 1.1 Sxemalar va kengaytmalar

```sql
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS platform;

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_bytes/gen_random_uuid — uuidv7() va parol-siz tasodifiy qiymatlar uchun
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- mahsulot/kontragent nomi bo'yicha qidiruv indeksi (01-model §1)

ALTER SCHEMA app OWNER TO erp_migrator;
ALTER SCHEMA auth OWNER TO erp_migrator;
ALTER SCHEMA platform OWNER TO erp_migrator;

GRANT USAGE ON SCHEMA app TO erp_app, erp_system;
GRANT USAGE ON SCHEMA platform TO erp_app, erp_system;
-- auth sxemasiga erp_app'ga USAGE HECH QACHON berilmaydi (05-xavfsizlik §3.3, 12-auth §19)
GRANT USAGE ON SCHEMA auth TO erp_system;

ALTER ROLE erp_app SET search_path = app, platform, public;
ALTER ROLE erp_system SET search_path = app, auth, platform, public;
```

`search_path`da `auth` yo'q — `erp_app` ulanishida `auth.*` nomlari hatto tasodifan ham ko'rinmaydi; faqat `SECURITY DEFINER` funksiyalar o'z `SET search_path` bilan ichkarida `auth`ga kiradi (4-bo'lim).

### 1.2 Kalitlar — UUIDv7 (qaror va asos)

**Qaror**: ID'lar **ilova tomonida** generatsiya qilinadi (backend — `uuid-utils`, veb-kassa/Android — JS/Kotlin UUIDv7 polyfill), DB ustun `DEFAULT`i esa **zaxira (fallback)** sifatida saqlanadi. Sabab — `01-malumotlar-modeli.md` Asosiy xulosa 2: *"offline qurilmada ham yaratiladi — kassa serverni kutmasdan ID beradi"*. Agar ID faqat DB tomonida berilsa, offline qurilma hujjatni serverga yetkazmasdan hech qanday ID bilan ishlay olmaydi — bu butun offline-first me'morchilikka zid (`04-offline-sync.md`). Shuning uchun: (a) ilova har doim ID'ni **oldindan** generatsiya qiladi va INSERT'da aniq yuboradi; (b) DB ustunida baribir `DEFAULT app.uuidv7()` turadi — to'g'ridan-to'g'ri `psql`/seed/migratsiya skriptlari uchun xavfsizlik to'ri, ID unutilsa ham jadval buzilmaydi.

PostgreSQL 16'da native `uuidv7()` yo'q (PG18'da qo'shiladi) — shuning uchun o'z funksiyamiz:

```sql
CREATE OR REPLACE FUNCTION app.uuidv7() RETURNS uuid
LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  unix_ts_ms bytea;
  uuid_bytes bytea;
BEGIN
  unix_ts_ms := substring(int8send(floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3 FOR 6);
  uuid_bytes := unix_ts_ms || gen_random_bytes(10);
  -- versiya = 0111 (7), 7-baytning yuqori nibble'i
  uuid_bytes := set_byte(uuid_bytes, 6, (x'70'::int | (get_byte(uuid_bytes, 6) & x'0F'::int)));
  -- variant = 10, 9-baytning yuqori ikki biti
  uuid_bytes := set_byte(uuid_bytes, 8, (x'80'::int | (get_byte(uuid_bytes, 8) & x'3F'::int)));
  RETURN encode(uuid_bytes, 'hex')::uuid;
END;
$$;

COMMENT ON FUNCTION app.uuidv7() IS
  'Vaqt bo''yicha tartiblangan UUIDv7 — faqat DB-darajasidagi zaxira DEFAULT; ilova ID''ni odatda oldindan o''zi beradi (offline-first talabi).';
```

### 1.3 Son/vaqt turlari

| Ma'no | Tip | Qaysi ustunlarda |
|---|---|---|
| Pul summasi (so'm, tiyingacha) | `NUMERIC(18,2)` | `amount`, `*_total`, `cost_amount`, `vat_amount`, `balance`, `price_month`, hisob-kitob yig'indilari |
| Miqdor (dona/kg/l) | `NUMERIC(18,3)` | `qty`, `qty_in`, `qty_left`, `qty_sent`, `qty_received` |
| Birlik narx/tannarx | `NUMERIC(18,4)` | `price`, `unit_cost`, `avg_cost`, `old_price`/`new_price` |
| Foiz | `NUMERIC(5,2)` | `vat_rate`, `standing_discount_pct` |
| Vaqt | `TIMESTAMPTZ` | barcha `*_at` ustunlar (UTC saqlanadi) |
| Sana (hisob kuni) | `DATE` | `doc_date`, `valid_from`, `period`, `expiry_date` |

Float/double hech qachon ishlatilmaydi (`01-malumotlar-modeli.md` band 3).

### 1.4 Umumiy ustunlar va trigger'lar

```sql
CREATE OR REPLACE FUNCTION app.set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;
```

Har bir `updated_at` ustuniga ega jadvalga shu trigger avtomatik qo'llanadi — 2-bo'lim oxirida bitta `DO $$ ... $$` bloki orqali (barcha jadvallar yaratilgandan keyin, qo'lda 90 marta yozish o'rniga). `version INT NOT NULL DEFAULT 1` — faqat ma'lumotnomalarda (optimistik qulflash, `01-model` band 27); hujjatlarda shart emas (`posted`dan keyin umuman o'zgarmaydi).

### 1.5 Enum strategiyasi — CHECK, PG ENUM emas, lookup jadval emas

**Qaror**: holat/tur ustunlari uchun `TEXT + CHECK (col IN (...))`, PostgreSQL native `ENUM` tipi **ishlatilmaydi**, alohida lookup-jadval ham yaratilmaydi (faqat haqiqiy ma'lumotnoma bo'lgan hollar — `units`, `expense_categories`, `roles` — bundan mustasno, ular allaqachon jadval).

Asos:
1. **Migratsiya qulayligi** (`09-backend-arxitekturasi.md` §10, expand-contract siyosati): `ALTER TYPE ... ADD VALUE` tranzaksiya ichida boshqa DDL bilan birga bajarilmaydi va eski qiymatni olib tashlash umuman mumkin emas — `CHECK` cheklovini esa oddiy `DROP CONSTRAINT` + `ADD CONSTRAINT` bilan bitta Alembic revizionda, boshqa jadvallarga ta'sir qilmasdan almashtirish mumkin.
2. **Qayta ishlatish**: bir xil qiymatlar to'plami (`draft/posted/cancelled` kabi) bir nechta jadvalda ishlatiladi, lekin har birining o'z evolyutsiyasi bo'lishi mumkin — umumiy `ENUM` tipi ularni sun'iy bog'lab qo'yadi.
3. **Tezlik**: hot-path (chek postingi) uchun qo'shimcha JOIN (lookup jadval) kerak emas, `CHECK` cheklovi insert/update vaqtida bepul tekshiriladi.

---

## 2. To'liq DDL

> Quyidagi jadvallar **01-malumotlar-modeli.md bo'lim tartibida** (o'qish qulayligi uchun) berilgan. Haqiqiy ijro (Alembic revizion) tartibi FK bog'liqligini hisobga oladi — 6-bo'lim.

### 2.1 Platforma — global jadvallar (`platform` sxemasi)

```sql
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

CREATE TABLE platform.oauth_clients (
  id                  UUID PRIMARY KEY DEFAULT app.uuidv7(),
  client_id           TEXT NOT NULL UNIQUE,
  client_type         TEXT NOT NULL CHECK (client_type IN ('confidential','public')),
  name                TEXT NOT NULL,
  client_secret_encrypted TEXT NULL,   -- public mijozda NULL
  redirect_uris       TEXT[] NOT NULL DEFAULT '{}',
  allowed_grant_types TEXT[] NOT NULL DEFAULT '{}',
  allowed_scopes      TEXT[] NOT NULL DEFAULT '{}',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (client_type = 'public' OR client_secret_encrypted IS NOT NULL)
);

CREATE TABLE platform.signing_keys (
  kid                     UUID PRIMARY KEY DEFAULT app.uuidv7(),
  algorithm               TEXT NOT NULL CHECK (algorithm IN ('EdDSA','ES256')),
  purpose                 TEXT NOT NULL CHECK (purpose IN ('access','license')),
  public_key              TEXT NOT NULL,
  private_key_encrypted   TEXT NOT NULL,
  status                  TEXT NOT NULL CHECK (status IN ('next','active','retired')),
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at            TIMESTAMPTZ NULL,
  retired_at              TIMESTAMPTZ NULL
);
-- har (purpose) uchun bir vaqtda faqat bitta 'active' kalit
CREATE UNIQUE INDEX uq_signing_keys_active ON platform.signing_keys (purpose) WHERE status = 'active';
```

`platform_admins` — `app.users`ga FK bergani uchun 2.3-bo'limdan keyin (`users` yaratilgandan so'ng) joylashtiriladi.

### 2.2 `auth` sxemasi — login/token jadvallari

`05-xavfsizlik-va-audit.md` §3.3 va `12-autentifikatsiya-oauth2.md` §19: bu jadvallarga `erp_app`ning **hech qanday** to'g'ridan-to'g'ri ruxsati yo'q (na RLS, na GRANT) — faqat 4-bo'limdagi `SECURITY DEFINER` funksiyalar orqali.

```sql
CREATE TABLE auth.user_credentials (
  user_id              UUID PRIMARY KEY,             -- FK app.users(id), pastda ALTER bilan qo'shiladi
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
  user_id               UUID NOT NULL,                -- FK app.users(id), pastda
  tenant_id             UUID NULL,                     -- FK app.tenants(id), pastda; tenant tanlanmagan bo'lsa NULL
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
  user_id              UUID NOT NULL,                  -- FK app.users(id)
  tenant_id            UUID NULL,                       -- FK app.tenants(id)
  device_id            UUID NULL,                       -- FK app.devices(id)
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
  id                      UUID PRIMARY KEY DEFAULT app.uuidv7(),  -- = sid
  user_id                 UUID NOT NULL,                           -- FK app.users(id)
  tenant_id               UUID NULL,                                -- FK app.tenants(id)
  client_id               UUID NOT NULL REFERENCES platform.oauth_clients(id),
  device_id               UUID NULL,                                -- FK app.devices(id)
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
```

Barcha `auth.*` jadvallarda RLS **o'chirilgan holatda qoladi** (yoqilmaydi) — bu jadvallar DB darajasida tenant kontekstidan tashqarida qidiriladi; himoya DB-GRANT yo'qligi + `SECURITY DEFINER` funksiya qamrovi bilan ta'minlanadi (4-bo'lim, CI tekshiruvi 6-bo'lim).

### 2.3 Tashkilot, foydalanuvchilar, huquqlar (`app` sxemasi)

```sql
CREATE TABLE app.tenants (
  id            UUID PRIMARY KEY DEFAULT app.uuidv7(),
  name          TEXT NOT NULL,
  activity_type TEXT NULL,
  stir          TEXT NULL,
  phone         TEXT NOT NULL,
  settings      JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  version       INT NOT NULL DEFAULT 1
);

CREATE TABLE app.users (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  phone      TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  locale     TEXT NOT NULL DEFAULT 'uz',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  version    INT NOT NULL DEFAULT 1
);

-- endi auth.* va platform.* jadvallardagi "pastda qo'shiladi" deb belgilangan FK'lar:
ALTER TABLE auth.user_credentials      ADD CONSTRAINT fk_uc_user      FOREIGN KEY (user_id) REFERENCES app.users(id);
ALTER TABLE auth.authorization_codes   ADD CONSTRAINT fk_ac_user      FOREIGN KEY (user_id) REFERENCES app.users(id);
ALTER TABLE auth.authorization_codes   ADD CONSTRAINT fk_ac_tenant    FOREIGN KEY (tenant_id) REFERENCES app.tenants(id);
ALTER TABLE auth.refresh_tokens        ADD CONSTRAINT fk_rt_user      FOREIGN KEY (user_id) REFERENCES app.users(id);
ALTER TABLE auth.refresh_tokens        ADD CONSTRAINT fk_rt_tenant    FOREIGN KEY (tenant_id) REFERENCES app.tenants(id);
ALTER TABLE auth.sessions              ADD CONSTRAINT fk_se_user      FOREIGN KEY (user_id) REFERENCES app.users(id);
ALTER TABLE auth.sessions              ADD CONSTRAINT fk_se_tenant    FOREIGN KEY (tenant_id) REFERENCES app.tenants(id);

CREATE TABLE app.branches (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  name                 TEXT NOT NULL,
  address              TEXT NULL,
  is_default           BOOLEAN NOT NULL DEFAULT false,
  settlement_category  TEXT NOT NULL CHECK (settlement_category IN ('city_100k_plus','other','remote_mountain')),
  activity_type        TEXT NOT NULL CHECK (activity_type IN ('retail','other')),
  archived_at          TIMESTAMPTZ NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  version              INT NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX uq_branches_one_default ON app.branches (tenant_id) WHERE is_default AND archived_at IS NULL;

CREATE TABLE app.branch_tax_settings (
  id                  UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id           UUID NOT NULL REFERENCES app.tenants(id),
  branch_id           UUID NOT NULL REFERENCES app.branches(id),
  valid_from          DATE NOT NULL,
  settlement_category TEXT NOT NULL CHECK (settlement_category IN ('city_100k_plus','other','remote_mountain')),
  activity_type       TEXT NOT NULL CHECK (activity_type IN ('retail','other')),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by          UUID NOT NULL REFERENCES app.users(id),
  UNIQUE (branch_id, valid_from)
);

CREATE TABLE app.warehouses (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  branch_id   UUID NOT NULL REFERENCES app.branches(id),
  name        TEXT NOT NULL,
  type        TEXT NOT NULL CHECK (type IN ('store','stock')),
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1
);

CREATE TABLE app.cash_registers (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  name             TEXT NOT NULL,
  kind             TEXT NOT NULL CHECK (kind IN ('web','android')),
  fiscal_module_id TEXT NULL,
  ofd_status       TEXT NULL,
  archived_at      TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          INT NOT NULL DEFAULT 1
);

CREATE TABLE app.devices (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  kind             TEXT NOT NULL CHECK (kind IN ('web','android')),
  app_version      TEXT NULL,
  revoked_at       TIMESTAMPTZ NULL,
  revoked_by       UUID NULL REFERENCES app.users(id),
  last_seen_at     TIMESTAMPTZ NULL,
  last_sync_at     TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE auth.refresh_tokens ADD CONSTRAINT fk_rt_device FOREIGN KEY (device_id) REFERENCES app.devices(id);
ALTER TABLE auth.sessions       ADD CONSTRAINT fk_se_device FOREIGN KEY (device_id) REFERENCES app.devices(id);

CREATE TABLE app.memberships (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  user_id    UUID NOT NULL REFERENCES app.users(id),
  role_ids   UUID[] NOT NULL DEFAULT '{}',
  branch_ids UUID[] NOT NULL DEFAULT '{}',   -- bo'sh = barcha filial
  status     TEXT NOT NULL CHECK (status IN ('active','blocked')) DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  version    INT NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, user_id)
);

CREATE TABLE app.roles (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  name        TEXT NOT NULL,
  is_system   BOOLEAN NOT NULL DEFAULT false,
  system_code TEXT NULL CHECK (system_code IN ('owner','manager','cashier','storekeeper','accountant')),
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, name)
);

CREATE TABLE app.role_permissions (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  role_id         UUID NOT NULL REFERENCES app.roles(id),
  permission_code TEXT NOT NULL,
  limit_value     NUMERIC(18,4) NULL,   -- ma'nosi permission_code'ga bog'liq: foiz YOKI summa (3-bo'lim, aniqlashtirish #11)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (role_id, permission_code)
);

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

CREATE TABLE app.billing_payments (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  amount         NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  provider       TEXT NOT NULL CHECK (provider IN ('click','payme')),
  provider_tx_id TEXT NOT NULL,
  status         TEXT NOT NULL CHECK (status IN ('pending','success','failed')),
  paid_at        TIMESTAMPTZ NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_tx_id)
);

CREATE TABLE app.tenant_tax_regimes (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  valid_from DATE NOT NULL,       -- har doim oyning 1-sanasi
  regime     TEXT NOT NULL CHECK (regime IN ('vat','turnover')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES app.users(id),
  UNIQUE (tenant_id, valid_from)
);
```

### 2.4 Katalog va narxlar

```sql
CREATE TABLE app.product_categories (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  parent_id   UUID NULL REFERENCES app.product_categories(id),
  name        TEXT NOT NULL,
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1
);

CREATE TABLE app.products (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  name             TEXT NOT NULL,
  category_id      UUID NULL REFERENCES app.product_categories(id),
  unit_code        TEXT NOT NULL REFERENCES platform.units(code),
  mxik_code        TEXT NOT NULL CHECK (char_length(mxik_code) = 17),
  package_code     TEXT NULL,
  vat_rate         NUMERIC(5,2) NULL,          -- 12.00 / 0.00 (aniqlashtirish #10: vat_exemption_code bilan birga)
  vat_exemption_code TEXT NULL,                -- imtiyoz kodi, vat_rate o'rniga/bilan
  is_marked        BOOLEAN NOT NULL DEFAULT false,
  is_weighed       BOOLEAN NOT NULL DEFAULT false,
  min_stock        NUMERIC(18,3) NULL,
  archived_at      TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          INT NOT NULL DEFAULT 1,
  CHECK (vat_rate IS NOT NULL OR vat_exemption_code IS NOT NULL)
);
CREATE INDEX idx_products_name_trgm ON app.products USING gin (name gin_trgm_ops);
CREATE INDEX idx_products_tenant_archived ON app.products (tenant_id) WHERE archived_at IS NULL;

CREATE TABLE app.product_barcodes (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  product_id        UUID NOT NULL REFERENCES app.products(id),
  barcode           TEXT NOT NULL,
  kind              TEXT NOT NULL CHECK (kind IN ('ean','internal','weighed_prefix')),
  units_per_barcode NUMERIC(18,3) NOT NULL DEFAULT 1 CHECK (units_per_barcode > 0),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, barcode)
);

CREATE TABLE app.product_prices (
  id                  UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id           UUID NOT NULL REFERENCES app.tenants(id),
  product_id          UUID NOT NULL REFERENCES app.products(id),
  branch_id           UUID NULL REFERENCES app.branches(id),   -- null = hamma filial
  price               NUMERIC(18,4) NOT NULL CHECK (price >= 0),
  valid_from          TIMESTAMPTZ NOT NULL DEFAULT now(),
  set_by              UUID NULL REFERENCES app.users(id),
  price_change_doc_id UUID NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_product_prices_current ON app.product_prices (tenant_id, product_id, branch_id, valid_from DESC);

CREATE TABLE app.label_print_queue (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  product_id UUID NOT NULL REFERENCES app.products(id),
  reason     TEXT NOT NULL CHECK (reason IN ('price_changed','new')),
  printed_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_label_queue_pending ON app.label_print_queue (tenant_id) WHERE printed_at IS NULL;

CREATE TABLE app.internal_barcode_seq (
  tenant_id  UUID PRIMARY KEY REFERENCES app.tenants(id),
  next_value BIGINT NOT NULL DEFAULT 2000000000
);

CREATE TABLE app.discount_rules (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  name        TEXT NOT NULL,
  scope       TEXT NOT NULL CHECK (scope IN ('product','category','all')),
  target_ids  UUID[] NOT NULL DEFAULT '{}',
  kind        TEXT NOT NULL CHECK (kind IN ('percent','amount','n_plus_m')),
  value       NUMERIC(18,4) NOT NULL,   -- kind='percent' bo'lsa foiz, aks holda summa (aniqlashtirish #12)
  branch_ids  UUID[] NOT NULL DEFAULT '{}',  -- bo'sh = hammasi
  valid_from  DATE NOT NULL,
  valid_to    DATE NULL,
  priority    INT NOT NULL DEFAULT 0,
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1
);
CREATE INDEX idx_discount_rules_active ON app.discount_rules (tenant_id, priority DESC) WHERE archived_at IS NULL;
```

### 2.5 Kontragentlar

```sql
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
  credit_limit          NUMERIC(18,2) NULL,   -- null = limitsiz
  standing_discount_pct NUMERIC(5,2) NULL CHECK (standing_discount_pct BETWEEN 0 AND 100),
  notify_consent        BOOLEAN NOT NULL DEFAULT false,
  notify_consent_at     TIMESTAMPTZ NULL,
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
  flagged_by      UUID NOT NULL REFERENCES app.users(id),  -- faqat Egasi (ilova darajasida tekshiriladi)
  reason          TEXT NOT NULL,
  flagged_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  unflagged_at    TIMESTAMPTZ NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_debt_doubtful_active ON app.debt_doubtful_flags (tenant_id, counterparty_id) WHERE unflagged_at IS NULL;
```

### 2.6 Hujjatlar

**Umumiy sarlavha** (`01-malumotlar-modeli.md` §6, yagona ro'yxat) — har bir hujjat jadvalida takrorlanadi: `id, tenant_id, branch_id, number, temp_number, doc_date, status, created_by, created_at, updated_at, posted_at, cancelled_at, cancelled_by, cancel_reason, client_event_id, device_id, comment`, `UNIQUE (tenant_id, device_id, temp_number)`, `UNIQUE (tenant_id, client_event_id)`. `shifts` bundan mustasno — raqamlanmaydi (11-bo'lim), o'z maxsus sarlavhasiga ega.

```sql
CREATE TABLE app.shifts (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  cash_register_id  UUID NOT NULL REFERENCES app.cash_registers(id),
  device_id         UUID NOT NULL REFERENCES app.devices(id),   -- bitta smena — bitta qurilma
  status            TEXT NOT NULL CHECK (status IN ('open','closing','closed')) DEFAULT 'open',
  opened_by         UUID NOT NULL REFERENCES app.users(id),
  opened_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  closing_started_at TIMESTAMPTZ NULL,
  closed_by         UUID NULL REFERENCES app.users(id),
  closed_at         TIMESTAMPTZ NULL,
  opening_cash      NUMERIC(18,2) NOT NULL DEFAULT 0,
  counted_cash      NUMERIC(18,2) NULL,
  expected_cash     NUMERIC(18,2) NULL,
  diff_amount       NUMERIC(18,2) NULL,
  client_event_id   UUID NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, client_event_id)
);
-- bitta kassada bir vaqtda faqat bitta ochiq/yopilayotgan smena
CREATE UNIQUE INDEX uq_shifts_one_open ON app.shifts (cash_register_id) WHERE status IN ('open','closing');

CREATE TABLE app.sales (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  number           TEXT NULL,
  temp_number      TEXT NULL,
  doc_date         DATE NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  shift_id         UUID NOT NULL REFERENCES app.shifts(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  counterparty_id  UUID NULL REFERENCES app.counterparties(id),   -- nasiya/qarzga sotuvda
  total_amount     NUMERIC(18,2) NULL,         -- hisoblangan jami (aniqlashtirish #13 — tezkor o'qish uchun qo'shimcha)
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at        TIMESTAMPTZ NULL,
  cancelled_at     TIMESTAMPTZ NULL,
  cancelled_by     UUID NULL REFERENCES app.users(id),
  cancel_reason    TEXT NULL,
  client_event_id  UUID NULL,
  device_id        UUID NULL REFERENCES app.devices(id),
  comment          TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);
CREATE INDEX idx_sales_branch_date ON app.sales (tenant_id, branch_id, doc_date);
CREATE INDEX idx_sales_shift ON app.sales (shift_id);

CREATE TABLE app.sale_lines (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  sale_id         UUID NOT NULL REFERENCES app.sales(id),
  line_no         INT NOT NULL,
  product_id      UUID NOT NULL REFERENCES app.products(id),
  qty             NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  price           NUMERIC(18,4) NOT NULL CHECK (price >= 0),
  discount_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  vat_rate        NUMERIC(5,2) NOT NULL,
  vat_amount      NUMERIC(18,2) NOT NULL DEFAULT 0,
  line_total      NUMERIC(18,2) NOT NULL,
  cost_amount     NUMERIC(18,2) NOT NULL DEFAULT 0,
  marking_code    TEXT NULL,
  lot_allocations JSONB NOT NULL DEFAULT '[]',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (sale_id, line_no),
  CHECK (marking_code IS NULL OR qty = 1)   -- markirovkalangan tovarda qty=1 majburiy
);
CREATE INDEX idx_sale_lines_product ON app.sale_lines (tenant_id, product_id);

CREATE TABLE app.sale_payments (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  sale_id        UUID NOT NULL REFERENCES app.sales(id),
  method         TEXT NOT NULL CHECK (method IN ('cash','card','uzqr','click','payme','uzum','debt')),
  amount         NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  provider_tx_id TEXT NULL,
  terminal_ref   TEXT NULL,
  qr_type        TEXT NULL CHECK (qr_type IN ('static','dynamic')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sale_payments_sale ON app.sale_payments (sale_id);

CREATE TABLE app.returns (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  sale_id         UUID NULL REFERENCES app.sales(id),   -- null = chek topilmagan qaytarish
  approved_by     UUID NULL REFERENCES app.users(id),
  approved_at     TIMESTAMPTZ NULL,
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.return_lines (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  return_id   UUID NOT NULL REFERENCES app.returns(id),
  line_no     INT NOT NULL,
  sale_line_id UUID NULL REFERENCES app.sale_lines(id),   -- null = chek topilmagan
  product_id  UUID NOT NULL REFERENCES app.products(id),
  qty         NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  price       NUMERIC(18,4) NOT NULL,
  vat_amount  NUMERIC(18,2) NOT NULL DEFAULT 0,
  cost_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
  line_total  NUMERIC(18,2) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (return_id, line_no)
);
CREATE INDEX idx_return_lines_sale_line ON app.return_lines (sale_line_id) WHERE sale_line_id IS NOT NULL;

CREATE TABLE app.purchase_orders (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','sent','partially_received','closed','cancelled')) DEFAULT 'draft',
  supplier_id     UUID NOT NULL REFERENCES app.counterparties(id),
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.po_lines (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  po_id      UUID NOT NULL REFERENCES app.purchase_orders(id),
  line_no    INT NOT NULL,
  product_id UUID NOT NULL REFERENCES app.products(id),
  qty        NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  price      NUMERIC(18,4) NOT NULL CHECK (price >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (po_id, line_no)
);

CREATE TABLE app.goods_receipts (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  number           TEXT NULL,
  temp_number      TEXT NULL,
  doc_date         DATE NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  supplier_id      UUID NOT NULL REFERENCES app.counterparties(id),
  po_id            UUID NULL REFERENCES app.purchase_orders(id),
  warehouse_id     UUID NOT NULL,   -- FK app.warehouses(id)
  paid_immediately BOOLEAN NOT NULL DEFAULT false,  -- aniqlashtirish #14: 2.6/2.8-provodka yo'lini tanlaydi
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at        TIMESTAMPTZ NULL,
  cancelled_at     TIMESTAMPTZ NULL,
  cancelled_by     UUID NULL REFERENCES app.users(id),
  cancel_reason    TEXT NULL,
  client_event_id  UUID NULL,
  device_id        UUID NULL REFERENCES app.devices(id),
  comment          TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);
ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

CREATE TABLE app.receipt_lines (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  receipt_id  UUID NOT NULL REFERENCES app.goods_receipts(id),
  line_no     INT NOT NULL,
  product_id  UUID NOT NULL REFERENCES app.products(id),
  qty         NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  cost        NUMERIC(18,4) NOT NULL CHECK (cost >= 0),
  vat_rate    NUMERIC(5,2) NOT NULL,
  vat_amount  NUMERIC(18,2) NOT NULL DEFAULT 0,
  expiry_date DATE NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (receipt_id, line_no)
);

CREATE TABLE app.supplier_returns (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  supplier_id     UUID NOT NULL REFERENCES app.counterparties(id),
  receipt_id      UUID NULL REFERENCES app.goods_receipts(id),
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.supplier_return_lines (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  supplier_return_id UUID NOT NULL REFERENCES app.supplier_returns(id),
  line_no          INT NOT NULL,
  receipt_line_id  UUID NOT NULL REFERENCES app.receipt_lines(id),
  lot_id           UUID NOT NULL,   -- FK app.stock_lots(id) — 2.7-bo'limda ALTER bilan qo'shiladi
  qty              NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  cost             NUMERIC(18,4) NOT NULL,
  vat_amount       NUMERIC(18,2) NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (supplier_return_id, line_no)
);

CREATE TABLE app.transfers (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),   -- aniqlashtirish: jo'natuvchi filial sifatida ishlatiladi
  number           TEXT NULL,
  temp_number      TEXT NULL,
  doc_date         DATE NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('draft','sent','received','discrepancy','cancelled')) DEFAULT 'draft',
  from_branch_id   UUID NOT NULL REFERENCES app.branches(id),
  to_branch_id     UUID NOT NULL REFERENCES app.branches(id),
  from_warehouse_id UUID NOT NULL,   -- FK app.warehouses(id)
  to_warehouse_id   UUID NOT NULL,   -- FK app.warehouses(id)
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at        TIMESTAMPTZ NULL,
  cancelled_at     TIMESTAMPTZ NULL,
  cancelled_by     UUID NULL REFERENCES app.users(id),
  cancel_reason    TEXT NULL,
  client_event_id  UUID NULL,
  device_id        UUID NULL REFERENCES app.devices(id),
  comment          TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK (from_branch_id <> to_branch_id)
);
ALTER TABLE app.transfers ADD CONSTRAINT fk_tr_from_wh FOREIGN KEY (from_warehouse_id) REFERENCES app.warehouses(id);
ALTER TABLE app.transfers ADD CONSTRAINT fk_tr_to_wh   FOREIGN KEY (to_warehouse_id)   REFERENCES app.warehouses(id);

CREATE TABLE app.transfer_lines (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  transfer_id UUID NOT NULL REFERENCES app.transfers(id),
  line_no     INT NOT NULL,
  product_id  UUID NOT NULL REFERENCES app.products(id),
  qty_sent    NUMERIC(18,3) NOT NULL CHECK (qty_sent > 0),
  qty_received NUMERIC(18,3) NULL CHECK (qty_received IS NULL OR qty_received >= 0),
  lot_id      UUID NULL,   -- FK app.stock_lots(id) — 2.7-bo'limda qo'shiladi
  unit_cost   NUMERIC(18,4) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (transfer_id, line_no)
);

CREATE TABLE app.stock_counts (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('counting','review','posted','cancelled')) DEFAULT 'counting',
  warehouse_id    UUID NOT NULL,   -- FK app.warehouses(id)
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);
ALTER TABLE app.stock_counts ADD CONSTRAINT fk_sc_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

CREATE TABLE app.count_lines (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  count_id   UUID NOT NULL REFERENCES app.stock_counts(id),
  line_no    INT NOT NULL,
  product_id UUID NOT NULL REFERENCES app.products(id),
  expected   NUMERIC(18,3) NOT NULL,
  counted    NUMERIC(18,3) NOT NULL,
  diff       NUMERIC(18,3) GENERATED ALWAYS AS (counted - expected) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (count_id, line_no)
);

CREATE TABLE app.write_offs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  warehouse_id    UUID NOT NULL,   -- FK app.warehouses(id)
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);
ALTER TABLE app.write_offs ADD CONSTRAINT fk_wo_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

CREATE TABLE app.write_off_lines (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  write_off_id UUID NOT NULL REFERENCES app.write_offs(id),
  line_no     INT NOT NULL,
  product_id  UUID NOT NULL REFERENCES app.products(id),
  lot_id      UUID NULL,   -- FK app.stock_lots(id) — 2.7-bo'limda qo'shiladi
  qty         NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  reason      TEXT NOT NULL CHECK (reason IN ('expired','damaged','gift','other')),
  cost_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (write_off_id, line_no)
);

CREATE TABLE app.price_changes (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','pending_approval','posted','rejected','cancelled')) DEFAULT 'draft',
  approved_by     UUID NULL REFERENCES app.users(id),
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.price_change_lines (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  price_change_id UUID NOT NULL REFERENCES app.price_changes(id),
  line_no        INT NOT NULL,
  product_id     UUID NOT NULL REFERENCES app.products(id),
  branch_id      UUID NULL REFERENCES app.branches(id),
  old_price      NUMERIC(18,4) NOT NULL,
  new_price      NUMERIC(18,4) NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (price_change_id, line_no)
);

CREATE TABLE app.stock_openings (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  warehouse_id    UUID NOT NULL,   -- FK app.warehouses(id)
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);
ALTER TABLE app.stock_openings ADD CONSTRAINT fk_so_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

CREATE TABLE app.opening_lines (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  opening_id  UUID NOT NULL REFERENCES app.stock_openings(id),
  line_no     INT NOT NULL,
  product_id  UUID NOT NULL REFERENCES app.products(id),
  qty         NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  unit_cost   NUMERIC(18,4) NOT NULL CHECK (unit_cost >= 0),
  expiry_date DATE NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (opening_id, line_no)
);

CREATE TABLE app.debt_openings (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  direction       TEXT NOT NULL CHECK (direction IN ('receivable','payable')),
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.debt_payments (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  method          TEXT NOT NULL CHECK (method IN ('cash','bank')),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  shift_id        UUID NULL REFERENCES app.shifts(id),
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK (method <> 'cash' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL))
);

CREATE TABLE app.debt_payment_allocations (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  debt_payment_id UUID NOT NULL REFERENCES app.debt_payments(id),
  target_doc_type TEXT NOT NULL,   -- polimorfik: 'sale' | 'debt_opening' | ...
  target_doc_id   UUID NOT NULL,
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.debt_writeoffs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  account_choice  TEXT NOT NULL CHECK (account_choice IN ('9430','4910')),
  approved_by     UUID NOT NULL REFERENCES app.users(id),   -- faqat Egasi
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.supplier_payments (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  supplier_id     UUID NOT NULL REFERENCES app.counterparties(id),
  method          TEXT NOT NULL CHECK (method IN ('cash','bank')),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.supplier_payment_allocations (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  supplier_payment_id UUID NOT NULL REFERENCES app.supplier_payments(id),
  target_doc_type    TEXT NOT NULL,
  target_doc_id      UUID NOT NULL,
  amount             NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.expense_categories (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  name        TEXT NOT NULL,
  is_system   BOOLEAN NOT NULL DEFAULT false,
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE app.recurring_expenses (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  category_id UUID NOT NULL REFERENCES app.expense_categories(id),
  name        TEXT NOT NULL,
  amount      NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  day_of_month INT NOT NULL CHECK (day_of_month BETWEEN 1 AND 28),
  period      TEXT NOT NULL CHECK (period = 'monthly'),
  branch_id   UUID NULL REFERENCES app.branches(id),
  is_active   BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.attachments (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  s3_key      TEXT NOT NULL,
  kind        TEXT NOT NULL,
  size_bytes  BIGINT NOT NULL CHECK (size_bytes >= 0),
  uploaded_by UUID NOT NULL REFERENCES app.users(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.expenses (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  number            TEXT NULL,
  temp_number       TEXT NULL,
  doc_date          DATE NOT NULL,
  status            TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  category_id       UUID NOT NULL REFERENCES app.expense_categories(id),
  amount            NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  source            TEXT NOT NULL CHECK (source IN ('cash','bank','card')),
  cash_register_id  UUID NULL REFERENCES app.cash_registers(id),
  shift_id          UUID NULL REFERENCES app.shifts(id),
  attachment_id     UUID NULL REFERENCES app.attachments(id),
  recurring_rule_id UUID NULL REFERENCES app.recurring_expenses(id),
  created_by        UUID NOT NULL REFERENCES app.users(id),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at         TIMESTAMPTZ NULL,
  cancelled_at      TIMESTAMPTZ NULL,
  cancelled_by      UUID NULL REFERENCES app.users(id),
  cancel_reason     TEXT NULL,
  client_event_id   UUID NULL,
  device_id         UUID NULL REFERENCES app.devices(id),
  comment           TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id),
  CHECK (source <> 'cash' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL))
);

CREATE TABLE app.cash_movements (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  shift_id        UUID NOT NULL REFERENCES app.shifts(id),
  direction       TEXT NOT NULL CHECK (direction IN ('in','out')),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  reason          TEXT NOT NULL CHECK (reason IN ('collection','deposit','owner_withdrawal','other')),
  created_by      UUID NOT NULL REFERENCES app.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_at       TIMESTAMPTZ NULL,
  cancelled_at    TIMESTAMPTZ NULL,
  cancelled_by    UUID NULL REFERENCES app.users(id),
  cancel_reason   TEXT NULL,
  client_event_id UUID NULL,
  device_id       UUID NULL REFERENCES app.devices(id),
  comment         TEXT NULL,
  UNIQUE (tenant_id, device_id, temp_number),
  UNIQUE (tenant_id, client_event_id)
);
```

### 2.7 Registrlar

`stock_moves`, `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves` — **haqiqiy append-only** (3-bo'limda `REVOKE`+trigger bilan mahkamlanadi). `stock_lots`, `avg_costs`, `stock_balances`, `debt_balances` — "balans/ishchi" jadvallar: qiymatlari shu registrlardan hisoblanadi, lekin qatorlari FIFO/AVECO qulfi ostida **UPDATE** qilinadi (aniqlashtirish #1 — 01-model bu jadvallarni "Registrlar" sarlavhasi ostida bersa ham, `stock_lots.qty_left` jismonan mutatsiya qilinadi, `09-backend-arxitekturasi.md` §2.1).

```sql
CREATE TABLE app.stock_moves (
  id            UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id     UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id  UUID NOT NULL REFERENCES app.warehouses(id),
  product_id    UUID NOT NULL REFERENCES app.products(id),
  lot_id        UUID NULL,     -- FK pastda (stock_lots yaratilgandan keyin)
  qty           NUMERIC(18,3) NOT NULL,     -- ishorali: kirim +, chiqim -
  cost_amount   NUMERIC(18,2) NOT NULL DEFAULT 0,
  doc_type      TEXT NOT NULL,
  doc_id        UUID NOT NULL,
  line_id       UUID NULL,
  reversal_of_id UUID NULL REFERENCES app.stock_moves(id),
  moved_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_stock_moves_wh_prod ON app.stock_moves (tenant_id, warehouse_id, product_id, moved_at);
CREATE INDEX idx_stock_moves_doc ON app.stock_moves (tenant_id, doc_type, doc_id);

CREATE TABLE app.stock_lots (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id    UUID NOT NULL REFERENCES app.warehouses(id),
  product_id      UUID NOT NULL REFERENCES app.products(id),
  receipt_line_id UUID NULL REFERENCES app.receipt_lines(id),   -- faqat source_doc_type='goods_receipt'
  source_doc_type TEXT NOT NULL CHECK (source_doc_type IN ('goods_receipt','stock_opening','transfer')),  -- aniqlashtirish #2
  source_doc_id   UUID NOT NULL,
  source_line_id  UUID NOT NULL,
  received_at     TIMESTAMPTZ NOT NULL,
  qty_in          NUMERIC(18,3) NOT NULL CHECK (qty_in >= 0),
  qty_left        NUMERIC(18,3) NOT NULL CHECK (qty_left >= 0),
  unit_cost       NUMERIC(18,4) NOT NULL CHECK (unit_cost >= 0),
  expiry_date     DATE NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- FIFO: eng eski faol partiya birinchi — qisman indeks faqat qty_left>0 qatorlarni qamraydi
CREATE INDEX idx_stock_lots_fifo ON app.stock_lots (tenant_id, warehouse_id, product_id, received_at)
  WHERE qty_left > 0;

ALTER TABLE app.stock_moves ADD CONSTRAINT fk_sm_lot FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);
ALTER TABLE app.supplier_return_lines ADD CONSTRAINT fk_srl_lot FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);
ALTER TABLE app.transfer_lines        ADD CONSTRAINT fk_tl_lot  FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);
ALTER TABLE app.write_off_lines       ADD CONSTRAINT fk_wol_lot FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);

CREATE TABLE app.avg_costs (
  tenant_id    UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id UUID NOT NULL REFERENCES app.warehouses(id),
  product_id   UUID NOT NULL REFERENCES app.products(id),
  avg_cost     NUMERIC(18,4) NOT NULL DEFAULT 0,
  qty          NUMERIC(18,3) NOT NULL DEFAULT 0,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, warehouse_id, product_id)
);

CREATE TABLE app.stock_balances (
  tenant_id    UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id UUID NOT NULL REFERENCES app.warehouses(id),
  product_id   UUID NOT NULL REFERENCES app.products(id),
  qty          NUMERIC(18,3) NOT NULL DEFAULT 0,
  value        NUMERIC(18,2) NOT NULL DEFAULT 0,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, warehouse_id, product_id)
);
-- manfiy qoldiqlarni tezkor topish (offline overselling, 04-offline-sync §5)
CREATE INDEX idx_stock_balances_negative ON app.stock_balances (tenant_id, warehouse_id, product_id) WHERE qty < 0;

CREATE TABLE app.debt_moves (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  direction       TEXT NOT NULL CHECK (direction IN ('receivable','payable')),
  amount          NUMERIC(18,2) NOT NULL,   -- ishorali
  due_date        DATE NULL,
  doc_type        TEXT NOT NULL,
  doc_id          UUID NOT NULL,
  reversal_of_id  UUID NULL REFERENCES app.debt_moves(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_debt_moves_cp ON app.debt_moves (tenant_id, counterparty_id, direction, created_at);
CREATE INDEX idx_debt_moves_due ON app.debt_moves (tenant_id, due_date) WHERE direction = 'receivable';

CREATE TABLE app.debt_balances (
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  direction       TEXT NOT NULL CHECK (direction IN ('receivable','payable')),
  balance         NUMERIC(18,2) NOT NULL DEFAULT 0,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, counterparty_id, direction)
);

CREATE TABLE app.cash_moves (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  bank_account_id  UUID NULL,
  shift_id         UUID NULL REFERENCES app.shifts(id),
  amount           NUMERIC(18,2) NOT NULL,   -- ishorali
  method           TEXT NOT NULL,
  doc_type         TEXT NOT NULL,
  doc_id           UUID NOT NULL,
  reversal_of_id   UUID NULL REFERENCES app.cash_moves(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (cash_register_id IS NOT NULL OR bank_account_id IS NOT NULL)
);
CREATE INDEX idx_cash_moves_shift ON app.cash_moves (shift_id) WHERE shift_id IS NOT NULL;

CREATE TABLE app.ledger_entries (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  entry_date     DATE NOT NULL,
  account_dt     TEXT NOT NULL,
  account_kt     TEXT NOT NULL,
  amount         NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  doc_type       TEXT NOT NULL,
  doc_id         UUID NOT NULL,
  analytics      JSONB NOT NULL DEFAULT '{}',
  reversal_of_id UUID NULL REFERENCES app.ledger_entries(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ledger_entries_period ON app.ledger_entries (tenant_id, entry_date);
CREATE INDEX idx_ledger_entries_doc ON app.ledger_entries (tenant_id, doc_type, doc_id);
CREATE INDEX idx_ledger_entries_accounts ON app.ledger_entries (tenant_id, account_dt, account_kt, entry_date);

CREATE TABLE app.vat_moves (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  period         DATE NOT NULL,   -- oyning 1-sanasi
  kind           TEXT NOT NULL CHECK (kind IN ('output','input')),
  base_amount    NUMERIC(18,2) NOT NULL,
  vat_amount     NUMERIC(18,2) NOT NULL,
  doc_type       TEXT NOT NULL,
  doc_id         UUID NOT NULL,
  einvoice_id    UUID NULL,   -- FK pastda (einvoices yaratilgandan keyin)
  reversal_of_id UUID NULL REFERENCES app.vat_moves(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vat_moves_period ON app.vat_moves (tenant_id, period, kind);
```

**Balans jadvallarining upsert naqshi** (posting xizmati ichida, `09-backend-arxitekturasi.md` §2.1 qulfi ostida):

```sql
INSERT INTO app.stock_balances (tenant_id, warehouse_id, product_id, qty, value, updated_at)
VALUES (:tenant_id, :warehouse_id, :product_id, :delta_qty, :delta_value, now())
ON CONFLICT (tenant_id, warehouse_id, product_id)
DO UPDATE SET
  qty        = app.stock_balances.qty + EXCLUDED.qty,
  value      = app.stock_balances.value + EXCLUDED.value,
  updated_at = now();

INSERT INTO app.debt_balances (tenant_id, counterparty_id, direction, balance, updated_at)
VALUES (:tenant_id, :counterparty_id, :direction, :delta_amount, now())
ON CONFLICT (tenant_id, counterparty_id, direction)
DO UPDATE SET balance = app.debt_balances.balance + EXCLUDED.balance, updated_at = now();
```

### 2.8 Fiskal, markirovka, e-hujjatlar, davlat hisoboti

```sql
CREATE TABLE app.fiscal_receipts (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  sale_id          UUID NULL REFERENCES app.sales(id),
  return_id        UUID NULL REFERENCES app.returns(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  shift_id         UUID NOT NULL REFERENCES app.shifts(id),
  receipt_seq      INT NOT NULL,         -- qurilma beradi
  payload          JSONB NOT NULL,
  fiscal_sign      TEXT NULL,
  qr_url           TEXT NULL,
  sent_at          TIMESTAMPTZ NULL,
  offline_since    TIMESTAMPTZ NULL,
  status           TEXT NOT NULL CHECK (status IN ('pending','sent','fiscalized','failed')) DEFAULT 'pending',
  attempts         INT NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (sale_id IS NOT NULL OR return_id IS NOT NULL),
  UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)
);
CREATE INDEX idx_fiscal_receipts_pending ON app.fiscal_receipts (tenant_id) WHERE status IN ('pending','failed');

CREATE TABLE app.marking_codes (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  code        TEXT NOT NULL,     -- DataMatrix
  product_id  UUID NOT NULL REFERENCES app.products(id),
  status      TEXT NOT NULL CHECK (status IN ('in_stock','sold','returned','written_off','returned_to_supplier','pending_verification')),
  last_doc_id UUID NULL,
  verified_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, code)
);
CREATE INDEX idx_marking_codes_pending_verif ON app.marking_codes (tenant_id) WHERE status = 'pending_verification';

ALTER TABLE app.sale_lines ADD CONSTRAINT fk_sl_marking
  FOREIGN KEY (tenant_id, marking_code) REFERENCES app.marking_codes(tenant_id, code) DEFERRABLE INITIALLY DEFERRED;
CREATE UNIQUE INDEX uq_marking_codes_tenant_code ON app.marking_codes (tenant_id, code);

CREATE TABLE app.einvoices (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  direction       TEXT NOT NULL CHECK (direction IN ('in','out')),
  operator        TEXT NOT NULL CHECK (operator IN ('didox','faktura')),
  operator_doc_id TEXT NULL,
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  related_doc_type TEXT NULL,
  related_doc_id  UUID NULL,
  status          TEXT NOT NULL,
  risk_flag       TEXT NULL CHECK (risk_flag IN ('green','red')),
  signed_at       TIMESTAMPTZ NULL,
  payload         JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE app.vat_moves ADD CONSTRAINT fk_vm_einvoice FOREIGN KEY (einvoice_id) REFERENCES app.einvoices(id);

CREATE TABLE app.ettn_documents (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  einvoice_id     UUID NOT NULL REFERENCES app.einvoices(id),
  status          TEXT NOT NULL,
  operator_doc_id TEXT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.state_reports (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  tax_type           TEXT NOT NULL CHECK (tax_type IN ('vat','turnover','property','land','pit','social')),
  period             DATE NOT NULL,
  published_at       TIMESTAMPTZ NULL,
  deadline_at        TIMESTAMPTZ NULL,
  file_attachment_id UUID NULL REFERENCES app.attachments(id),
  status             TEXT NOT NULL CHECK (status IN ('uploaded','compared','match','diff_found','correction_sent','auto_accepted')),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.state_report_diffs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  state_report_id UUID NOT NULL REFERENCES app.state_reports(id),
  indicator       TEXT NOT NULL,
  state_value     NUMERIC(18,2) NULL,
  our_value       NUMERIC(18,2) NULL,
  diff            NUMERIC(18,2) NULL,
  explanation     TEXT NULL,
  resolved        BOOLEAN NOT NULL DEFAULT false,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2.9 Integratsiya navbati, sync, bildirishnoma, AI, audit, raqamlash

```sql
CREATE TABLE app.outbox_jobs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  kind            TEXT NOT NULL CHECK (kind IN ('ofd_send','einvoice_send','einvoice_accept','ettn_send',
                     'marking_verify','marking_sell','state_report_reminder','sms','telegram','ai')),
  payload         JSONB NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('queued','running','done','retry','failed')) DEFAULT 'queued',
  attempts        INT NOT NULL DEFAULT 0,
  next_run_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_error      TEXT NULL,
  idempotency_key TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX idx_outbox_jobs_due ON app.outbox_jobs (next_run_at) WHERE status IN ('queued','retry');

CREATE TABLE app.sync_receipts (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  device_id       UUID NOT NULL REFERENCES app.devices(id),
  client_event_id UUID NOT NULL,
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  result          JSONB NOT NULL,
  UNIQUE (tenant_id, client_event_id)
);

CREATE TABLE app.idempotency_keys (
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  key             TEXT NOT NULL,
  request_hash    TEXT NOT NULL,
  response_status INT NOT NULL,
  response_body   JSONB NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, key)
);
CREATE INDEX idx_idempotency_keys_cleanup ON app.idempotency_keys (created_at);

CREATE TABLE app.recost_jobs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id    UUID NOT NULL REFERENCES app.warehouses(id),
  product_id      UUID NOT NULL REFERENCES app.products(id),
  from_date       DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('queued','running','done','failed','rejected_period_closed')) DEFAULT 'queued',
  reason_doc_type TEXT NOT NULL,
  reason_doc_id   UUID NOT NULL,
  attempts        INT NOT NULL DEFAULT 0,
  last_error      TEXT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at     TIMESTAMPTZ NULL
);
-- bitta (tenant, warehouse, product) uchun bir vaqtda faqat bitta "queued" job
CREATE UNIQUE INDEX uq_recost_jobs_queued ON app.recost_jobs (tenant_id, warehouse_id, product_id) WHERE status = 'queued';

CREATE TABLE app.import_jobs (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  kind       TEXT NOT NULL CHECK (kind IN ('products','opening_stock','opening_debts')),
  attachment_id UUID NOT NULL REFERENCES app.attachments(id),
  status     TEXT NOT NULL CHECK (status IN ('uploaded','validated','committed','failed')) DEFAULT 'uploaded',
  total_rows INT NOT NULL DEFAULT 0,
  ok_rows    INT NOT NULL DEFAULT 0,
  errors     JSONB NOT NULL DEFAULT '[]',
  created_by UUID NOT NULL REFERENCES app.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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

CREATE TABLE app.ai_requests (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  user_id           UUID NULL REFERENCES app.users(id),
  feature           TEXT NOT NULL,
  model             TEXT NOT NULL,
  prompt_version    TEXT NULL,
  input_tokens      INT NOT NULL DEFAULT 0,
  output_tokens     INT NOT NULL DEFAULT 0,
  cache_read_tokens INT NOT NULL DEFAULT 0,
  cost_usd          NUMERIC(12,6) NOT NULL DEFAULT 0,
  fx_rate_used      NUMERIC(12,4) NULL,
  cost_uzs          NUMERIC(18,2) NULL,
  latency_ms        INT NULL,
  guard_result      TEXT NULL,
  status            TEXT NOT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_requests_tenant_month ON app.ai_requests (tenant_id, created_at);

CREATE TABLE app.ai_training_samples (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NULL,   -- anonimlashtirilgandan keyin olib tashlanadi
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

CREATE TABLE app.doc_sequences (
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  branch_id  UUID NOT NULL REFERENCES app.branches(id),
  doc_type   TEXT NOT NULL,
  year       INT NOT NULL,
  next_value BIGINT NOT NULL DEFAULT 1,
  PRIMARY KEY (tenant_id, branch_id, doc_type, year)
);
```

**Hujjat raqami generatori** (aniqlashtirish #15 — 01-model faqat `K-01-2026-000154` namunasini beradi, to'liq `doc_type` kod jadvali ro'yxatlanmagan):

```sql
CREATE OR REPLACE FUNCTION app.next_doc_number(
  p_tenant_id uuid, p_branch_id uuid, p_branch_code text, p_doc_type text, p_year int
) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE v_next bigint;
BEGIN
  INSERT INTO app.doc_sequences (tenant_id, branch_id, doc_type, year, next_value)
  VALUES (p_tenant_id, p_branch_id, p_doc_type, p_year, 2)
  ON CONFLICT (tenant_id, branch_id, doc_type, year)
  DO UPDATE SET next_value = app.doc_sequences.next_value + 1
  RETURNING next_value - 1 INTO v_next;
  RETURN format('%s-%s-%s-%s', p_doc_type, p_branch_code, p_year, lpad(v_next::text, 6, '0'));
END;
$$;
```

Taklif qilingan `doc_type` kodlari (aniqlashtirish #15): `K`=sales, `V`=returns, `Z`=purchase_orders, `M`=goods_receipts, `MV`=supplier_returns, `P`=transfers, `I`=stock_counts, `L`=write_offs, `C`=price_changes, `OO`=stock_openings, `OD`=debt_openings, `DP`=debt_payments, `DW`=debt_writeoffs, `SP`=supplier_payments, `E`=expenses, `CM`=cash_movements.

### 2.10 `updated_at` trigger'larini ommaviy ulash

Barcha jadvallar yaratilgandan so'ng, bitta martalik migratsiya qadami:

```sql
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT DISTINCT c.relname, n.nspname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'updated_at' AND NOT a.attisdropped
    WHERE n.nspname IN ('app', 'platform') AND c.relkind = 'r'
  LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON %I.%I FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()',
      r.nspname, r.relname
    );
  END LOOP;
END $$;
```

---

## 3. Registrlar: append-only mahkamlash

Haqiqiy append-only registrlar — **faqat** `stock_moves`, `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves`, `audit_log`, `sync_receipts`, `auth.login_attempts`. Ikki qatlamli himoya: (a) `erp_app`dan `UPDATE`/`DELETE` huquqi **olib tashlanadi**, (b) trigger — kod xatosi yoki boshqa (masalan `erp_migrator`) rol bilan ulanish ham qatorni o'zgartira olmasligi uchun.

```sql
CREATE OR REPLACE FUNCTION app.forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'append-only jadval: % operatsiyasi taqiqlangan (jadval: %)', TG_OP, TG_TABLE_NAME
    USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

DO $$
DECLARE
  t TEXT;
  append_only_tables TEXT[] := ARRAY[
    'app.stock_moves', 'app.debt_moves', 'app.cash_moves',
    'app.ledger_entries', 'app.vat_moves', 'app.audit_log', 'app.sync_receipts'
  ];
BEGIN
  FOREACH t IN ARRAY append_only_tables LOOP
    EXECUTE format('REVOKE UPDATE, DELETE ON %s FROM erp_app', t);
    EXECUTE format(
      'CREATE TRIGGER trg_no_update_delete BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation()',
      t
    );
  END LOOP;
END $$;

REVOKE UPDATE, DELETE ON auth.login_attempts FROM erp_system;
CREATE TRIGGER trg_no_update_delete BEFORE UPDATE OR DELETE ON auth.login_attempts
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
```

`stock_lots`/`avg_costs`/`stock_balances`/`debt_balances` — **UPDATE ruxsat etilgan** (balans-keshi, 2.7-bo'limdagi upsert naqshi); ularning yaxlitligi FK + `CHECK (qty_left >= 0)` kabi cheklovlar va posting xizmatining `FOR UPDATE` qulfi bilan ta'minlanadi, DB darajasidagi `REVOKE` emas. `fiscal_receipts`, `marking_codes`, `outbox_jobs`, `recost_jobs`, `import_jobs`, `einvoices`, `ettn_documents`, `state_reports`, `state_report_diffs`, `refresh_tokens`, `sessions`, `otp_challenges` — holat-mashinasi jadvallari, `UPDATE` tabiiy ravishda kerak (status o'tishlari), append-only emas.

---

## 4. Row-Level Security

### 4.1 Tenant kontekst funksiyalari

```sql
CREATE OR REPLACE FUNCTION app.current_tenant_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;
```

`current_setting(..., true)` parametr o'rnatilmagan bo'lsa xato tashlamay `NULL` qaytaradi; `NULLIF(...,'')` bo'sh satrni ham `NULL`ga aylantiradi — natijada kontekstsiz so'rov **hech qanday qator qaytarmaydi** (fail-closed, `05-xavfsizlik-va-audit.md` §3.2).

### 4.2 Siyosat shabloni — barcha oddiy tenant jadvallari

```sql
DO $$
DECLARE
  r RECORD;
  excluded_tables TEXT[] := ARRAY['tenants', 'users', 'memberships'];  -- maxsus siyosat, pastda
BEGIN
  FOR r IN
    SELECT DISTINCT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
    WHERE n.nspname = 'app' AND c.relkind = 'r' AND c.relname <> ALL (excluded_tables)
  LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', r.relname);
    EXECUTE format('ALTER TABLE app.%I FORCE ROW LEVEL SECURITY', r.relname);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON app.%I USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id())',
      r.relname
    );
  END LOOP;
END $$;
```

Bu blok — **bitta martalik** ijro (boshlang'ich migratsiyada, barcha jadvallar yaratilgandan keyin). Keyingi migratsiyalarda qo'shilgan har bir yangi `tenant_id`li jadval uchun **aniq** `ENABLE`/`FORCE`/`CREATE POLICY` uchligi o'z revizionida yozilishi shart — CI tekshiruvi (6-bo'lim) buni tasdiqlaydi.

### 4.3 Maxsus siyosatlar

```sql
-- tenants: faqat o'z yozuvi (id = joriy tenant)
ALTER TABLE app.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_self ON app.tenants
  USING (id = app.current_tenant_id())
  WITH CHECK (id = app.current_tenant_id());

-- users: o'z yozuvi (ro'yxatdan o'tish/tenant tanlashda ham ishlashi uchun) YOKI joriy tenant'da membership bor
ALTER TABLE app.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_self_or_membership ON app.users
  USING (
    id = app.current_user_id()
    OR EXISTS (
      SELECT 1 FROM app.memberships m
      WHERE m.user_id = app.users.id AND m.tenant_id = app.current_tenant_id()
    )
  )
  WITH CHECK (id = app.current_user_id());
  -- INSERT: ilova yangi foydalanuvchi id'sini oldindan generatsiya qilib `app.user_id`ni
  -- shu qiymatga o'rnatadi (1.2-bo'lim), shundan keyin INSERT qiladi — WITH CHECK shu yo'l bilan qanoatlanadi.

-- memberships: joriy tenant doirasidagi barcha a'zolik (Egasi/BO-11 uchun) YOKI o'zining istalgan tenantdagi a'zoligi
-- (tenant-almashtirish ekrani uchun, auth_list_memberships SECURITY DEFINER'siz oddiy o'qish yo'li)
ALTER TABLE app.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY memberships_scope ON app.memberships
  USING (
    tenant_id = app.current_tenant_id()
    OR user_id = app.current_user_id()
  )
  WITH CHECK (tenant_id = app.current_tenant_id());
```

### 4.4 Global/platforma jadvallari — RLS o'rniga GRANT cheklovi

`plans`, `addons`, `units`, `oauth_clients`, `signing_keys` — `tenant_id`siz, RLS **yoqilmaydi**; o'rniga faqat `SELECT` beriladi (yozish — faqat `erp_migrator`/admin yo'li orqali). `platform_admins` — `erp_app`ga **umuman** grant yo'q (platforma admin BFF alohida, yuqori ishonchli yo'l orqali ishlaydi, `05-xavfsizlik-va-audit.md` §3.4).

```sql
GRANT SELECT ON platform.plans, platform.addons, platform.units,
                platform.oauth_clients, platform.signing_keys
  TO erp_app;
-- platform.platform_admins — erp_app'ga HECH QANDAY grant yo'q
REVOKE ALL ON platform.platform_admins FROM erp_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO erp_app;
-- 3-bo'limdagi REVOKE UPDATE/DELETE append-only jadvallar uchun yuqorida alohida qo'llanadi (tartib muhim: shundan keyin ishga tushiriladi)

REVOKE ALL ON SCHEMA auth FROM PUBLIC, erp_app;
GRANT ALL ON ALL TABLES IN SCHEMA auth TO erp_system;
```

### 4.5 `SECURITY DEFINER` funksiyalar

Faqat shu to'rt funksiya tenant-kontekstidan **oldin** ishlaydigan amallarni qamrab oladi (login, scheduler fan-out, billing webhook). Barchasi `erp_system` egaligida, `SET search_path` bilan (search_path hijack'dan himoya — chaqiruvchi sessiyaning `search_path`i e'tiborga olinmaydi).

```sql
CREATE OR REPLACE FUNCTION app.auth_find_user_by_phone(p_phone text)
RETURNS TABLE (
  user_id uuid, password_hash text, password_algo text,
  failed_login_count int, locked_until timestamptz
)
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT u.id, c.password_hash, c.password_algo, c.failed_login_count, c.locked_until
  FROM app.users u
  JOIN auth.user_credentials c ON c.user_id = u.id
  WHERE u.phone = p_phone;
$$;

CREATE OR REPLACE FUNCTION app.auth_list_memberships(p_user_id uuid)
RETURNS TABLE (
  tenant_id uuid, tenant_name text, role_ids uuid[], branch_ids uuid[], status text
)
LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
  SELECT m.tenant_id, t.name, m.role_ids, m.branch_ids, m.status
  FROM app.memberships m
  JOIN app.tenants t ON t.id = m.tenant_id
  WHERE m.user_id = p_user_id AND m.status = 'active';
$$;

CREATE OR REPLACE FUNCTION app.list_active_tenant_ids()
RETURNS SETOF uuid
LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
  SELECT tenant_id FROM app.subscriptions WHERE status IN ('trial','active','grace','restricted');
$$;

CREATE OR REPLACE FUNCTION app.billing_tenant_by_payment(p_provider text, p_provider_tx_id text)
RETURNS TABLE (tenant_id uuid, payment_id uuid, status text)
LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
  SELECT tenant_id, id, status
  FROM app.billing_payments
  WHERE provider = p_provider AND provider_tx_id = p_provider_tx_id;
$$;

ALTER FUNCTION app.auth_find_user_by_phone(text) OWNER TO erp_system;
ALTER FUNCTION app.auth_list_memberships(uuid) OWNER TO erp_system;
ALTER FUNCTION app.list_active_tenant_ids() OWNER TO erp_system;
ALTER FUNCTION app.billing_tenant_by_payment(text, text) OWNER TO erp_system;

REVOKE ALL ON FUNCTION app.auth_find_user_by_phone(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_list_memberships(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.list_active_tenant_ids() FROM PUBLIC;
REVOKE ALL ON FUNCTION app.billing_tenant_by_payment(text, text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.auth_find_user_by_phone(text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_list_memberships(uuid) TO erp_app;
GRANT EXECUTE ON FUNCTION app.list_active_tenant_ids() TO erp_app;
GRANT EXECUTE ON FUNCTION app.billing_tenant_by_payment(text, text) TO erp_app;
```

`12-autentifikatsiya-oauth2.md` §19'da nomlangan qo'shimcha `SECURITY DEFINER` funksiyalar (`auth_consume_code`, `auth_rotate_refresh`, `auth_revoke_tenant`, `auth_suspend_tenant`) — xuddi shu naqsh bilan (`erp_system` egaligida, `SET search_path = app, auth, pg_temp`), `auth.*` jadvallarni yozadi/o'qiydi; imzolari:

```sql
-- CREATE FUNCTION app.auth_consume_code(p_code_hash text) RETURNS TABLE (...);
-- CREATE FUNCTION app.auth_rotate_refresh(p_token_hash text) RETURNS TABLE (...);
-- CREATE FUNCTION app.auth_revoke_tenant(p_tenant_id uuid) RETURNS void;
-- CREATE FUNCTION app.auth_suspend_tenant(p_tenant_id uuid) RETURNS void;
```

To'liq tanasi `auth` modulining ishga tushirish bosqichida yoziladi (bu — DB-sxema hujjati, auth-oqim logikasi `12-autentifikatsiya-oauth2.md`da).

---

## 5. Seed data

### 5.1 Global (bir martalik, barcha tenantlar uchun umumiy)

```sql
INSERT INTO platform.units (code, is_fractional) VALUES
  ('pcs', false), ('kg', true), ('l', true), ('m', true), ('box', false);

INSERT INTO platform.plans (code, price_month, price_year, limits) VALUES
  ('standard', 99000.00, 950400.00,   -- 950 400 = 99 000 × 12 × 0,8 (−20% yillik chegirma)
   '{"included_cash_registers": 1, "ai_monthly_tokens": 200000}'::jsonb);
   -- ai_monthly_tokens — taxmin, 06-mvp-chegarasi.md'da yakunlanadi (01-model §2 izohi)

INSERT INTO platform.addons (code, name, price_month) VALUES
  ('extra_register', 'Qo''shimcha virtual kassa', 39000.00);

INSERT INTO platform.oauth_clients (client_id, client_type, name, allowed_grant_types, allowed_scopes) VALUES
  ('web-bff',      'confidential', 'Veb BFF (back-office + veb-kassa)', ARRAY['authorization_code','refresh_token'], ARRAY['*']),
  ('admin-bff',    'confidential', 'Platforma admin BFF',               ARRAY['authorization_code','refresh_token'], ARRAY['platform.admin']),
  ('android-pos',  'public',       'Android POS',                       ARRAY['authorization_code','refresh_token'], ARRAY['*','sync','pos']),
  ('telegram-bot', 'confidential', 'Telegram bot',                      ARRAY['client_credentials'],                 ARRAY['bot.internal']);
-- client_secret_encrypted — deploy vaqtida KEK orqali to'ldiriladi (05-xavfsizlik §4.2), bu yerda bo'sh qoldiriladi

-- signing_keys — haqiqiy kalit juftligi deploy skriptida (joserfc) generatsiya qilinadi, DB'ga faqat natija yoziladi:
-- INSERT INTO platform.signing_keys (algorithm, purpose, public_key, private_key_encrypted, status, activated_at)
--   VALUES ('EdDSA', 'access', :pub, :enc_priv, 'active', now());
-- INSERT INTO platform.signing_keys (algorithm, purpose, public_key, private_key_encrypted, status, activated_at)
--   VALUES ('EdDSA', 'license', :pub2, :enc_priv2, 'active', now());
```

### 5.2 Tenant-provisioning shabloni (har ro'yxatdan o'tishda qo'llaniladi, global emas)

`05-xavfsizlik-va-audit.md` §1.5: `roles`/`role_permissions`/`expense_categories`/`doc_sequences` **tenant-scoped** jadvallar — bular bir martalik global seed emas, balki **har signup tranzaksiyasida** ilova kodi tomonidan quyidagi shablon bo'yicha yaratiladi (aniqlashtirish #16).

```sql
-- 5 standart rol (parametr :tenant_id)
INSERT INTO app.roles (tenant_id, name, is_system, system_code) VALUES
  (:tenant_id, 'Egasi',      true, 'owner'),
  (:tenant_id, 'Menejer',    true, 'manager'),
  (:tenant_id, 'Kassir',     true, 'cashier'),
  (:tenant_id, 'Omborchi',   true, 'storekeeper'),
  (:tenant_id, 'Buxgalter',  true, 'accountant');

-- standart limitlar (05-xavfsizlik §2.3) — faqat Kassir rolига namuna; to'liq matritsa §2.2'dan ilova kodida yuklanadi
INSERT INTO app.role_permissions (tenant_id, role_id, permission_code, limit_value) VALUES
  (:tenant_id, :cashier_role_id, 'discount.give',    5.00),       -- foiz
  (:tenant_id, :cashier_role_id, 'returns.approve',  100000.00),  -- so'm
  (:tenant_id, :cashier_role_id, 'cash.withdraw',    50000.00),   -- so'm
  (:tenant_id, :cashier_role_id, 'sales.void',       NULL);       -- limitsiz, audit bilan

-- standart xarajat toifalari (09-backend §11, 11-backlog.md ro'yxati)
INSERT INTO app.expense_categories (tenant_id, name, is_system) VALUES
  (:tenant_id, 'Ijara', true), (:tenant_id, 'Kommunal', true), (:tenant_id, 'Ish haqi', true),
  (:tenant_id, 'Transport', true), (:tenant_id, 'Soliq va yig''imlar', true),
  (:tenant_id, 'Ta''mirlash', true), (:tenant_id, 'Boshqa', true);

-- doc_sequences — birinchi hujjat yaratilganda ON CONFLICT bilan o'zi paydo bo'ladi (next_doc_number, 2.9-bo'lim),
-- oldindan INSERT shart emas (ixtiyoriy, hisobot uchun 0-qatorlar kerak bo'lsa):
-- INSERT INTO app.doc_sequences (tenant_id, branch_id, doc_type, year, next_value) VALUES (:tenant_id, :branch_id, 'K', :year, 1)
--   ON CONFLICT DO NOTHING;
```

---

## 6. Migratsiya tartibi va CI tekshiruvi

### 6.1 Alembic revizion rejasi

| № | Revizion | Mazmuni |
|---|---|---|
| 0001 | `extensions_roles_schemas` | Sxemalar, kengaytmalar, rollar, `app.uuidv7()`, `app.set_updated_at()`, `app.forbid_mutation()` |
| 0002 | `core_tenant_user` | `tenants`, `users`, `branches`, `branch_tax_settings`, `warehouses`, `cash_registers`, `devices`, `memberships`, `roles`, `role_permissions` |
| 0003 | `auth_schema` | `auth.*` (6 jadval) + ularning `app.users`/`tenants`/`devices`ga FK'lari, `app.license_tokens` |
| 0004 | `platform_global` | `platform.plans`, `addons`, `units`, `oauth_clients`, `signing_keys`, `platform_admins` + `app.subscriptions`, `tenant_addons`, `billing_payments`, `tenant_tax_regimes` |
| 0005 | `catalog_pricing` | `product_categories`, `products`, `product_barcodes`, `product_prices`, `label_print_queue`, `internal_barcode_seq`, `discount_rules` |
| 0006 | `counterparties` | `counterparties`, `debt_doubtful_flags` |
| 0007 | `docs_sales` | `shifts`, `sales`, `sale_lines`, `sale_payments` |
| 0008 | `docs_returns` | `returns`, `return_lines` |
| 0009 | `docs_purchasing` | `purchase_orders`, `po_lines`, `goods_receipts`, `receipt_lines` |
| 0010 | `docs_inventory` | `transfers`, `transfer_lines`, `stock_counts`, `count_lines`, `write_offs`, `write_off_lines`, `stock_openings`, `opening_lines` |
| 0011 | `registers` | `stock_moves`, `stock_lots` (+ `supplier_returns`/`supplier_return_lines` endi yaratiladi — `receipt_lines`ga bog'liq), `avg_costs`, `stock_balances`, `debt_moves`, `debt_balances`, `cash_moves`, `ledger_entries`, `vat_moves`; append-only `REVOKE`+trigger (3-bo'lim) |
| 0012 | `docs_pricing_debts` | `price_changes`, `price_change_lines`, `debt_openings`, `debt_payments`, `debt_payment_allocations`, `debt_writeoffs`, `supplier_payments`, `supplier_payment_allocations` |
| 0013 | `docs_expenses_cash` | `expense_categories`, `recurring_expenses`, `attachments`, `expenses`, `cash_movements` |
| 0014 | `doc_sequences` | `doc_sequences`, `app.next_doc_number()` |
| 0015 | `fiscal_marking_edocs` | `fiscal_receipts`, `marking_codes`, `einvoices`, `ettn_documents`, `state_reports`, `state_report_diffs` |
| 0016 | `integration_sync` | `outbox_jobs`, `sync_receipts`, `idempotency_keys`, `recost_jobs`, `import_jobs` |
| 0017 | `notifications_ai` | `telegram_links`, `notification_settings`, `notifications_log`, `ai_requests`, `ai_training_samples`, `ai_feedback`, `tenant_glossary` |
| 0018 | `audit_periods` | `audit_log`, `period_closings` |
| 0019 | `updated_at_triggers` | 2.10-bo'limdagi `DO` bloki |
| 0020 | `rls_policies` | 4.2–4.4-bo'limlardagi `DO` bloki + maxsus siyosatlar + GRANT/REVOKE |
| 0021 | `security_definer_functions` | 4.5-bo'limdagi 4 funksiya + `auth_consume_code`/`auth_rotate_refresh`/`auth_revoke_tenant`/`auth_suspend_tenant` |

Seed (5-bo'lim) — **Alembic revizion emas** (`09-backend-arxitekturasi.md` §11: "bazani versiyalash bilan aralashtirmaslik uchun"), `migrate` konteyneridan keyin alohida `scripts/seed.py` bosqichi, faqat 5.1 (global) qismini bir marta ishga tushiradi; 5.2 (tenant-provisioning) — har signup'da ilova kodi tomonidan.

> Diqqat: yuqoridagi tartib 2-bo'limning **o'qish tartibidan** farq qiladi (masalan `supplier_returns`/`supplier_return_lines` 2-bo'limda purchasing ostida ko'rsatilgan, lekin `stock_lots`ga FK'i borligi sababli 0011-revizionda, registrlardan keyin yaratiladi). Bu — FK bog'liqligini hal qilish uchun zarur qayta tartiblash, 01-model mazmuniga ta'sir qilmaydi.

### 6.2 CI tekshiruvi — RLS'siz jadvallar

```sql
WITH exempt AS (
  SELECT unnest(ARRAY[
    'platform.plans', 'platform.addons', 'platform.units',
    'platform.oauth_clients', 'platform.signing_keys', 'platform.platform_admins',
    'auth.user_credentials', 'auth.otp_challenges', 'auth.login_attempts',
    'auth.authorization_codes', 'auth.refresh_tokens', 'auth.sessions'
  ]) AS qualified_name
)
SELECT
  n.nspname || '.' || c.relname AS table_name,
  c.relrowsecurity   AS rls_enabled,
  c.relforcerowsecurity AS rls_forced,
  COALESCE(p.policy_count, 0) AS policy_count
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN (
  SELECT polrelid, COUNT(*) AS policy_count FROM pg_policy GROUP BY polrelid
) p ON p.polrelid = c.oid
WHERE n.nspname IN ('app', 'auth', 'platform')
  AND c.relkind = 'r'
  AND (n.nspname || '.' || c.relname) NOT IN (SELECT qualified_name FROM exempt)
  AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity OR COALESCE(p.policy_count, 0) = 0);
-- bo'sh natija = yashil. Har bir qaytgan qator — CI'ni qizil qiladi.
```

Qo'shimcha, `auth`-sxema istisnosini tasdiqlovchi tekshiruv (`05-xavfsizlik-va-audit.md` §3.3):

```sql
-- erp_app auth.*ga hech qanday GRANT'ga ega bo'lmasligi shart (bo'sh natija kutiladi)
SELECT table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'erp_app' AND table_schema = 'auth';

-- talab qilinadigan SECURITY DEFINER funksiyalar mavjudligi
SELECT p.proname
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'app' AND p.prosecdef
  AND p.proname IN ('auth_find_user_by_phone','auth_list_memberships',
                     'list_active_tenant_ids','billing_tenant_by_payment',
                     'auth_consume_code','auth_rotate_refresh',
                     'auth_revoke_tenant','auth_suspend_tenant');
-- 8 qator qaytishi shart; kamroq bo'lsa CI qizil.
```

---

## 7. 01 bilan farqlar / aniqlashtirishlar

01-malumotlar-modeli.md jadval/ustun nomlarini o'zgartirmagan holda, DDL yozish uchun quyidagi aniq qarorlar qabul qilindi (01 tahrirlanmadi):

1. **UUID generatsiyasi**: ilova tomonida (offline-first talabi, §1.2), DB `DEFAULT app.uuidv7()` — faqat zaxira.
2. **`stock_lots`/`avg_costs`/`stock_balances`/`debt_balances`ning append-only emasligi**: 01 §7 ularni "Registrlar (append-only)" sarlavhasi ostida bersa ham, bular jismoniy mutatsiya qilinadigan balans-keshlari; haqiqiy append-only — `stock_moves`/`debt_moves`/`cash_moves`/`ledger_entries`/`vat_moves` (3-bo'lim).
3. **`stock_lots.receipt_line_id`ning umumlashtirilishi**: 01 faqat `receipt_line_id`ni ko'rsatadi, lekin `stock_openings`/`transfers` ham yangi partiya yaratadi (goods_receipt'siz). Shuning uchun `receipt_line_id` (faqat kirim uchun, nullable) ustiga `source_doc_type`/`source_doc_id`/`source_line_id` polimorfik ustunlari qo'shildi.
4. **Sxema taqsimoti** (`app`/`auth`/`platform`): 01'da umuman yo'q — bu hujjat tomonidan kiritildi, `05-xavfsizlik-va-audit.md` §3.3/§19'dagi RLS istisnolari mantiqiga mos ravishda.
5. **Hisob-kitob ustunlarining aniq `NUMERIC` kategoriyasi**: 01 faqat uchta umumiy kategoriya beradi (pul/miqdor/narx-tannarx); har bir aniq ustun (masalan `sale_lines.price` → narx 18,4; `sale_lines.line_total` → pul 18,2; `sale_lines.cost_amount` → pul 18,2, chunki bu qatorning **jami** tannarxi, birlik tannarxi emas) shu uchta toifaga ushbu hujjat tomonidan taqsimlangan.
6. **`role_permissions.limit_value` birligi**: 01 aniqlashtirmaydi (foiz yoki summa) — bu hujjat yagona `NUMERIC(18,4)` ustunni tanladi, ma'no `permission_code` konvensiyasi orqali aniqlanadi (masalan `discount.give` = foiz, `cash.withdraw` = so'm); alohida `limit_unit` ustuni **qo'shilmadi** (ilova darajasida kod-konstanta sifatida saqlanadi).
7. **`discount_rules.value`**: xuddi shunday, `kind='percent'` bo'lsa foiz, aks holda summa — bitta `NUMERIC(18,4)` ustun.
8. **`products.vat_rate`**: 01 "12/0/imtiyoz kodi" deydi — bitta ustunda son va kod aralashishi mumkin emas, shuning uchun `vat_rate NUMERIC(5,2) NULL` + `vat_exemption_code TEXT NULL` ikkiga ajratildi (`CHECK` — kamida bittasi to'ldirilgan bo'lishi shart).
9. **`goods_receipts.paid_immediately`**: 01'da yo'q, lekin `02-provodka-qoidalari.md` §2.6/§2.8 ikki xil provodka yo'li (nasiyaga / darhol to'langan) borligini aytadi — bu bayroq shu tanlovni saqlash uchun qo'shildi.
10. **`sales.total_amount`**: 01'da yo'q, tezkor o'qish/hisobot uchun hisoblangan ustun sifatida qo'shildi (qatorlar yig'indisidan posting vaqtida to'ldiriladi, manba emas).
11. **`debt_payment_allocations`/`supplier_payment_allocations`**: 01 faqat "`allocations` (qaysi qarzni yopdi)" deydi, alohida jadval nomini bermaydi — polimorfik `target_doc_type`/`target_doc_id` naqshi bilan modellashtirildi (registrlardagi `doc_type`/`doc_id` naqshiga mos).
12. **`doc_sequences.doc_type` kodlari**: 01 faqat `K-01-2026-000154` namunasini beradi, to'liq kod jadvalini bermaydi — 2.9-bo'limda taklif qilingan ro'yxat shu hujjat tomonidan qo'shildi (buxgalter/mahsulot jamoasi bilan tasdiqlanishi tavsiya etiladi).
13. **Global seed vs tenant-provisioning**: 01 `roles`/`role_permissions`/`expense_categories`/`doc_sequences`ni "seed" sifatida tilga oladi, lekin bu jadvallar `tenant_id NOT NULL` — demak **global** bir martalik seed emas, balki `05-xavfsizlik-va-audit.md` §1.5'dagi tenant-provisioning tranzaksiyasining bir qismi (5.2-bo'lim shu farqni aniq ajratadi).
14. **`marking_codes` ↔ `sale_lines.marking_code` FK**: 01'da bu bog'lanish aniq FK sifatida ko'rsatilmagan — `(tenant_id, code)` composite UNIQUE + `DEFERRABLE` FK qo'shildi (chek va kod bir xil tranzaksiyada, lekin ikkisining yozilish tartibi ilova mantiqiga bog'liq bo'lishi mumkin, shuning uchun kechiktirilgan tekshiruv).
15. **`shifts`ning umumiy hujjat sarlavhasidan mustasnoligi**: 01 §11 (raqamlash) shiftlarga `number` berilishini aytmaydi — shuning uchun `shifts` boshqa hujjatlardan farqli, `number`/`temp_number`siz maxsus sarlavha oldi.
16. **`branch_tax_settings`/`tenant_tax_regimes.created_by`**: 01'da yo'q, audit izlanishi uchun qo'shildi (boshqa barcha hujjat/ma'lumotnoma yozuvlarida bor konvensiyaga moslashtirildi).

---

## Yakuniy eslatma

Bu hujjat — `01-malumotlar-modeli.md`ning DDL proyeksiyasi; 01 o'zi o'zgarmadi. Buxgalteriya hisob raqamlari (`account_dt`/`account_kt` qiymatlari) `02-provodka-qoidalari.md` boshidagi ogohlantirishga ko'ra **buxgalter tomonidan rasmiy manba bilan tasdiqlanishi shart** — bu hujjat ularni `TEXT` ustun sifatida saqlaydi, raqamlarning to'g'riligini tekshirmaydi (ilova darajasidagi konstanta ro'yxati orqali).

