# DB sxemasi (PostgreSQL 16) — amalga oshirishga tayyor spetsifikatsiya

**Maqsad:** `11-malumotlar-modeli.md`da tasvirlangan kontseptual modelni ishga tushirish mumkin bo'lgan to'liq PostgreSQL 16 DDL'ga aylantirish — barcha jadval, ustun, cheklov, indeks, RLS siyosati, `SECURITY DEFINER` funksiya, seed ma'lumot va migratsiya tartibi bilan.
**Kim uchun:** Backend dasturchilar (Alembic migratsiyalarini yozuvchilar), DBA.
**Bog'liq fayllar:** `11-malumotlar-modeli.md` (barcha jadval/ustun/holatlar), `13-provodka-qoidalari.md` (registrlar, hisob raqamlari), `14-autentifikatsiya-oauth2.md` §19 (auth jadvallari), `15-xavfsizlik-va-audit.md` §3 (RLS qoidalari, istisnolar, SECURITY DEFINER), §2.1–2.2 (huquqlar/limitlar), §6.2 (audit_log o'zgarmasligi), `16-offline-sync.md` (`sync_receipts`, `devices`, `client_event_id`), `23-backend-arxitekturasi.md` (`tenant_transaction`, `idempotency_keys`, posting naqshi), `22-ai-qatlami.md` (`ai_requests` maydonlari), `33-1c-integratsiya.md` §5 (`onec_*` jadvallari, 2.11-bo'lim), `01-qarorlar.md`.
**Holat:** joriy, 2026-10-16.

Loyiha ildizi: `E:/Project/erp`. Bu faylda "11", "11-model" — `11-malumotlar-modeli.md`ning qisqa nomi. 11 dagi jadval/ustun nomlari **o'zgarishsiz** saqlanadi; 11 umumiy qoidani bergan joyda DDL uchun qabul qilingan aniq qaror oxirgi bo'limda ("11 bilan aniqlashtirishlar") ro'yxatga olingan.

**Sxema tashkiloti**: uch PostgreSQL sxemasi — `app` (tenant-scoped biznes jadvallari + `tenants`/`users`/`memberships` kabi "yarim-global" jadvallar maxsus RLS siyosati bilan), `auth` (login/token jadvallari — ilova roliga to'g'ridan-to'g'ri kirish yo'q, faqat `SECURITY DEFINER` funksiyalar orqali), `platform` (tenant'siz, haqiqiy global ma'lumotnomalar: tariflar, qo'shimchalar, birliklar, OAuth mijozlari, imzolash kalitlari, platforma adminlari).

---

## 0. Rollar (oldindan)

Barcha quyidagi DDL'dan oldin uch DB rol mavjud bo'lishi kerak. `erp_migrator` — `NOCREATEROLE`, ya'ni rol yarata olmaydi va `ALTER ROLE … SET` bajara olmaydi; shuning uchun rollarni Alembic emas, **DBA bootstrap bosqichi** superuser (yoki DBaaS admin) huquqi bilan, birinchi migratsiyadan oldin bir marta yaratadi. Lokal/CI muhitda bu — `backend/docker/postgres/initdb.sh` (postgres konteynerining `/docker-entrypoint-initdb.d` skripti, bo'sh ma'lumotlar katalogida bir marta ishlaydi); UzCloud DBaaS'da xuddi shu SQL'ni DBA admin hisobidan ishga tushiradi. Parollar — muhit sirlari (`ERP_MIGRATOR_PASSWORD`, `ERP_APP_PASSWORD`; baza nomi `ERP_DB_NAME`, standart `erp`), psql o'zgaruvchisi sifatida beriladi:

```sql
-- DBA bootstrap (superuser, `postgres` bazasida; migratsiyadan oldin, bir marta)
-- Alembic migratsiyalarini ishga tushiruvchi, barcha ob'ektlarning egasi
CREATE ROLE erp_migrator LOGIN NOSUPERUSER CREATEDB NOCREATEROLE PASSWORD :'migrator_pw';

-- FastAPI/worker/scheduler/bot ulanadigan rol — BYPASSRLS YO'Q (`15` §3.2)
CREATE ROLE erp_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD :'app_pw';

-- SECURITY DEFINER funksiyalarning egasi — BYPASSRLS, lekin LOGIN emas
-- (hech kim to'g'ridan-to'g'ri shu rol bilan ulanmaydi, faqat funksiya ichida "ishlaydi")
CREATE ROLE erp_system NOLOGIN BYPASSRLS;

-- migrator funksiyalarni erp_system'ga topshira olishi uchun (ALTER FUNCTION … OWNER TO erp_system, 4.5-bo'lim)
-- shu rol a'zosi bo'lishi shart; BYPASSRLS — rol atributi, a'zolik orqali meros qilinmaydi
GRANT erp_system TO erp_migrator;

ALTER ROLE erp_app SET search_path = app, platform, public;
ALTER ROLE erp_system SET search_path = app, auth, platform, public;

CREATE DATABASE :"db" OWNER erp_migrator;
```

`0001` revizioni rollarni **faqat** migratsiyani ishga tushirayotgan rol bunga ruxsatga ega bo'lsa (superuser yoki `CREATEROLE`) va rol hali yo'q bo'lsa yaratadi (parolsiz — parolni DBA beradi); `erp_migrator` bilan ishlaganda bu blok hech narsa qilmaydi. `erp_app`/`erp_system` topilmasa revizion xato bilan to'xtaydi — bootstrap bajarilmagan:

```sql
DO $$
DECLARE
  can_manage boolean := (SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user);
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_migrator') AND can_manage THEN
    CREATE ROLE erp_migrator LOGIN NOSUPERUSER CREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_app') AND can_manage THEN
    CREATE ROLE erp_app LOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_system') AND can_manage THEN
    CREATE ROLE erp_system NOLOGIN BYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('erp_app', 'erp_system') HAVING count(*) = 2) THEN
    RAISE EXCEPTION 'roles erp_app/erp_system are missing: run the DBA bootstrap first (backend/docker/postgres/initdb.sh or the 12 §0 SQL)';
  END IF;
END $$;
```

`erp_app` RLS siyosatlariga **to'liq bo'ysunadi** (bu — tenant izolyatsiyasining asosiy DB darajasidagi mexanizmi, `15-xavfsizlik-va-audit.md` Asosiy xulosa 3). `erp_system` — faqat quyida 4-bo'limda ro'yxatlangan `SECURITY DEFINER` funksiyalarning egasi; bu funksiyalar ichida ishlayotgan SQL `erp_system`ning `BYPASSRLS` huquqidan vaqtincha foydalanadi (login/billing kabi tenant-kontekstisiz amallar uchun yagona qonuniy yo'l).

---

## 1. Konventsiyalar

### 1.1 Sxemalar va kengaytmalar

```sql
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS platform;

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_bytes/gen_random_uuid — uuidv7() va parol-siz tasodifiy qiymatlar uchun
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- mahsulot/kontragent nomi bo'yicha qidiruv indeksi (11-model §1)

ALTER SCHEMA app OWNER TO erp_migrator;
ALTER SCHEMA auth OWNER TO erp_migrator;
ALTER SCHEMA platform OWNER TO erp_migrator;

GRANT USAGE ON SCHEMA app TO erp_app, erp_system;
GRANT USAGE ON SCHEMA platform TO erp_app, erp_system;
-- auth sxemasiga erp_app'ga USAGE HECH QACHON berilmaydi (`15` §3.3, `14` §19)
GRANT USAGE ON SCHEMA auth TO erp_system;

-- search_path asosan DBA bootstrap'da o'rnatiladi (0-bo'lim); ALTER ROLE … SET CREATEROLE talab qiladi,
-- shuning uchun 0001 uni faqat migratsiya roli bunga ruxsatga ega bo'lsa takrorlaydi
DO $$
BEGIN
  IF (SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user) THEN
    ALTER ROLE erp_app SET search_path = app, platform, public;
    ALTER ROLE erp_system SET search_path = app, auth, platform, public;
  END IF;
END $$;
```

`search_path`da `auth` yo'q — `erp_app` ulanishida `auth.*` nomlari hatto tasodifan ham ko'rinmaydi; faqat `SECURITY DEFINER` funksiyalar o'z `SET search_path` bilan ichkarida `auth`ga kiradi (4-bo'lim).

### 1.2 Kalitlar — UUIDv7 (qaror va asos)

**Qaror**: ID'lar **ilova tomonida** generatsiya qilinadi (backend — `uuid-utils`, veb-kassa/Android — JS/Kotlin UUIDv7 polyfill), DB ustun `DEFAULT`i esa **zaxira (fallback)** sifatida saqlanadi. Sabab — `11-malumotlar-modeli.md` Asosiy xulosa 2: *"offline qurilmada ham yaratiladi — kassa serverni kutmasdan ID beradi"*. Agar ID faqat DB tomonida berilsa, offline qurilma hujjatni serverga yetkazmasdan hech qanday ID bilan ishlay olmaydi — bu butun offline-first me'morchilikka zid (`16-offline-sync.md`). Shuning uchun: (a) ilova har doim ID'ni **oldindan** generatsiya qiladi va INSERT'da aniq yuboradi; (b) DB ustunida baribir `DEFAULT app.uuidv7()` turadi — to'g'ridan-to'g'ri `psql`/seed/migratsiya skriptlari uchun xavfsizlik to'ri, ID unutilsa ham jadval buzilmaydi.

PostgreSQL 16'da native `uuidv7()` yo'q (PG18'da qo'shiladi) — shuning uchun o'z funksiyamiz:

```sql
CREATE OR REPLACE FUNCTION app.uuidv7() RETURNS uuid
LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  unix_ts_ms bytea;
  uuid_bytes bytea;
BEGIN
  unix_ts_ms := substring(int8send(floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3 FOR 6);
  -- sxema bilan: SECURITY DEFINER funksiyalar (SET search_path = app, auth, pg_temp) ichidagi DEFAULT ham topadi
  uuid_bytes := unix_ts_ms || public.gen_random_bytes(10);
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

Float/double hech qachon ishlatilmaydi (`11-malumotlar-modeli.md` band 3).

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

Har bir `updated_at` ustuniga ega jadvalga shu trigger avtomatik qo'llanadi — 2-bo'lim oxirida bitta `DO $$ ... $$` bloki orqali (barcha jadvallar yaratilgandan keyin, qo'lda 90 marta yozish o'rniga). `version INT NOT NULL DEFAULT 1` — faqat ma'lumotnomalarda (optimistik qulflash, `11-model` band 27); hujjatlarda shart emas (`posted`dan keyin umuman o'zgarmaydi).

### 1.5 Enum strategiyasi — CHECK, PG ENUM emas, lookup jadval emas

**Qaror**: holat/tur ustunlari uchun `TEXT + CHECK (col IN (...))`, PostgreSQL native `ENUM` tipi **ishlatilmaydi**, alohida lookup-jadval ham yaratilmaydi (faqat haqiqiy ma'lumotnoma bo'lgan hollar — `units`, `expense_categories`, `roles` — bundan mustasno, ular allaqachon jadval).

Asos:
1. **Migratsiya qulayligi** (`23-backend-arxitekturasi.md` §10, expand-contract siyosati): `ALTER TYPE ... ADD VALUE` tranzaksiya ichida boshqa DDL bilan birga bajarilmaydi va eski qiymatni olib tashlash umuman mumkin emas — `CHECK` cheklovini esa oddiy `DROP CONSTRAINT` + `ADD CONSTRAINT` bilan bitta Alembic revizionda, boshqa jadvallarga ta'sir qilmasdan almashtirish mumkin.
2. **Qayta ishlatish**: bir xil qiymatlar to'plami (`draft/posted/cancelled` kabi) bir nechta jadvalda ishlatiladi, lekin har birining o'z evolyutsiyasi bo'lishi mumkin — umumiy `ENUM` tipi ularni sun'iy bog'lab qo'yadi.
3. **Tezlik**: hot-path (chek postingi) uchun qo'shimcha JOIN (lookup jadval) kerak emas, `CHECK` cheklovi insert/update vaqtida bepul tekshiriladi.

---

## 2. To'liq DDL

> Quyidagi jadvallar **11-malumotlar-modeli.md bo'lim tartibida** (o'qish qulayligi uchun) berilgan. Haqiqiy ijro (Alembic revizion) tartibi FK bog'liqligini hisobga oladi — 6-bo'lim.

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

-- standart yorliq shablonlari (US-M09-04), tenant o'zgartirmaydi, RLS istisnosi
CREATE TABLE platform.label_templates (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  code       TEXT NOT NULL UNIQUE, -- '58x40_price', '40x30_barcode'
  name       TEXT NOT NULL,
  width_mm   NUMERIC(6,2) NOT NULL CHECK (width_mm > 0),
  height_mm  NUMERIC(6,2) NOT NULL CHECK (height_mm > 0),
  fields     JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- (qaror #63) Markirovkalangan tovar guruhlari — egalik o'tishi xabarnomasi (kirimda qabul) muddati guruhga bog'liq:
-- umumiy — 3 ish kuni (VM 833 66–67-band), suv/ichimlik (VM 631), dori (VM 149), o'simlik yog'i (VM 23) — 72 soat.
-- Global ma'lumotnoma (RLS istisnosi), seed 5.1; products.marking_group_code shu yerga ishora qiladi.
CREATE TABLE platform.marking_product_groups (
  code                TEXT PRIMARY KEY, -- 'general','water_beverages','medicines','vegetable_oil'
  name                TEXT NOT NULL,
  acceptance_deadline TEXT NOT NULL CHECK (acceptance_deadline IN ('3_business_days','72_hours')),
  legal_ref           TEXT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
```

`platform_admins` — `app.users`ga FK bergani uchun 2.3-bo'limdan keyin (`users` yaratilgandan so'ng) joylashtiriladi.

### 2.2 `auth` sxemasi — login/token jadvallari

`15-xavfsizlik-va-audit.md` §3.3 va `14-autentifikatsiya-oauth2.md` §19: bu jadvallarga `erp_app`ning **hech qanday** to'g'ridan-to'g'ri ruxsati yo'q (na RLS, na GRANT) — faqat 4-bo'limdagi `SECURITY DEFINER` funksiyalar orqali.

```sql
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
  legal_form    TEXT NOT NULL DEFAULT 'llc' CHECK (legal_form IN ('llc','jsc','private_enterprise','sole_proprietor')),
                -- "Egasi oldi" hisobini belgilaydi (13-provodka-qoidalari.md §2.18): llc/jsc/private_enterprise → 4890, sole_proprietor → 8720
  go_live_date  DATE NULL, -- tizimda ishlash boshlangan sana; boshlang'ich qoldiqlar entry_date = go_live_date - 1 (13 §2.13, §2.21, §5.5)
  accepted_terms_version TEXT NULL,        -- qabul qilingan foydalanish shartlari versiyasi (aksept)
  accepted_terms_at      TIMESTAMPTZ NULL,
  accepted_terms_ip      INET NULL,
  settings      JSONB NOT NULL DEFAULT '{}', -- TenantSettings kalitlari (11-malumotlar-modeli.md §2):
  -- ai_training_consent, ai_cross_border_enabled (standart false — rozilik berilmaguncha AI'ga chegaradan tashqari
  -- uzatish yo'q), negative_stock_policy (allow/block), transfer_overdue_hours (48), stock_valuation (ichki: qo'llangan baholash usuli), weight_barcode_templates[] (standart 22=WEIGHT, 21=AMOUNT),
  -- low_stock_check_enabled, expiry_warning_days (standart 7), vat_diff_tolerance_amount (standart "1000.00", qaror #50),
  -- supplier_overpay_policy ('warn'|'block', standart 'warn', qaror #47), discount_posting ('gross_9050'|'net', standart
  -- 'gross_9050'), owner_withdrawal_account ('4890'|'8720', standart legal_form'dan), payment_org_commission_account
  -- ('9430'|'9410', standart '9430'), turnover_tax_account ('9430'|'9820', standart '9430'), fiscal_policy
  -- {debt_receipt_split: 'single'|'per_sale' (standart 'single', qaror #45), credit_sale_receipt: 'none'|'credit_type'
  -- (standart 'none')}, marking_precheck ('off'|'warn'|'block', standart 'warn', qaror #62), bank_account (20 raqam),
  -- bank_mfo — tenantning yagona bank hisobi (qaror #49), payment_providers.{click|payme|uzum}.autofiscal_off_confirmed_at
  -- (ISO vaqt — provayder avtofiskalizatsiyasi o'chirilgani tasdig'i, 20 #40d), card_manual_fallback ('allow'|
  -- 'manager_approval'|'forbid' — faol card_terminals bog'langan kassada karta to'lovini terminalsiz (rekvizitsiz)
  -- qabul qilish siyosati, qaror #71; kalit yo'q bo'lsa 'manager_approval'; terminal bog'lanmagan kassada qo'llanmaydi —
  -- u yerda karta = faqat summa, manual_reason='standalone_terminal', har doim ruxsat). Baholash usuli BU YERDA EMAS — valuation_method_history
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  version       INT NOT NULL DEFAULT 1
);
-- (qaror #31) Bitta tenant = bitta yuridik shaxs (STIR), ko'p filial/kassa/faoliyat turi
-- (branches.activity_type) bitta tenant ichida; ko'p yuridik shaxsli egalar har bir shaxs uchun alohida tenant
-- ochadi va memberships orqali ular o'rtasida almashadi (tasdiqlandi — 13-provodka-qoidalari.md §5.4).

CREATE TABLE app.users (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  phone      TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  locale     TEXT NOT NULL DEFAULT 'uz',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  version    INT NOT NULL DEFAULT 1
);

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

CREATE TABLE app.branches (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  code                 TEXT NOT NULL CHECK (code ~ '^[0-9A-Z]{1,4}$'), -- hujjat raqamidagi filial kodi, signup'da '01'
  name                 TEXT NOT NULL,
  address              TEXT NULL,
  is_default           BOOLEAN NOT NULL DEFAULT false,
  settlement_category  TEXT NOT NULL CHECK (settlement_category IN ('city_100k_plus','other','remote_mountain')),
  activity_type        TEXT NOT NULL CHECK (activity_type IN ('retail','other')),
  archived_at          TIMESTAMPTZ NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  version              INT NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, code)
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
  inventory_account TEXT NOT NULL CHECK (inventory_account IN ('2910','2920')),
              -- tovar hisobi (13 §1 inv_acct): yaratishda type='store' → '2920', type='stock' → '2910' (ilova qo'yadi);
              -- omborda stock_moves bo'lgach o'zgartirilmaydi (409 WAREHOUSE_ACCOUNT_LOCKED)
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
  ofd_status       TEXT NOT NULL DEFAULT 'pending' CHECK (ofd_status IN ('pending','registered','active','suspended','deregistered')),
                   -- soliq ro'yxati holati; 'registered'/'active' bo'lmagan kassada fiskal chek chiqarilmaydi.
                   -- Fiskal hamkor holat kodlari adapterda shu qiymatlarga xaritalanadi (26 #89 (OQ-008))
  fm_state         TEXT NOT NULL DEFAULT 'unknown' CHECK (fm_state IN ('ok','locked','ack_overdue','memory_full','unknown')),
                   -- fiskal modul holati (FiscalPort.get_device_status); != 'ok' → FISCAL_DEVICE_LOCKED
  last_unacked_receipt_at TIMESTAMPTZ NULL, -- FM xabar qilgan eng eski OFD tasdiqlamagan chek vaqti
  fm_receipts_pending     INT NULL CHECK (fm_receipts_pending IS NULL OR fm_receipts_pending >= 0),
  tax_registered_at       TIMESTAMPTZ NULL, -- TXKM orqali soliq organida ro'yxatga olingan vaqt (VMQ-943 1-ilova 16–20-band)
  outlet_address_snapshot TEXT NULL,        -- ro'yxatdagi savdo shoxobchasi manzili (o'zgarsa 3 ish kunida qayta ariza)
  txkm_contract_ref       TEXT NULL,        -- TXKM bilan xizmat shartnomasi raqami
  fiscal_agent_id         UUID NULL,        -- lokal fiskal ko'prik kassasiga xizmat qiluvchi Do'kon agenti (qaror #66);
                                            -- FK 0028 store_agent da: fk_cr_fiscal_agent → app.onec_agents(id)
  fiscal_local_device_id  TEXT NULL,        -- agent capabilities.fiscal.devices[].local_id
  archived_at      TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          INT NOT NULL DEFAULT 1,
  CHECK (fiscal_agent_id IS NULL OR fiscal_local_device_id IS NOT NULL)
);

CREATE TABLE app.devices (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  kind             TEXT NOT NULL CHECK (kind IN ('web','android','onec_agent')), -- onec_agent — mijoz kompyuteridagi 1C agenti (qaror #36/#38)
  app_version      TEXT NULL,
  revoked_at       TIMESTAMPTZ NULL,
  revoked_by       UUID NULL REFERENCES app.users(id),
  last_seen_at     TIMESTAMPTZ NULL,
  last_sync_at     TIMESTAMPTZ NULL,
  -- POST /sync/push outbox_state'idan (16-offline-sync.md §3.1): push qayta ishlangach last_sync_at bilan
  -- bitta tranzaksiyada yoziladi; faqat 1C eksporti tayyorligi uchun (33-1c-integratsiya.md §7.3 devices_synced).
  -- onec_agent qurilmasida doim NULL.
  outbox_pending_count     INT NULL,         -- outbox_state.pending_count + shu so'rovda rad etilgan voqealar soni
  outbox_oldest_pending_at TIMESTAMPTZ NULL, -- min(oldest_pending_created_at, rad etilganlarning created_at) — qurilma soati
  outbox_reported_at       TIMESTAMPTZ NULL, -- = now() o'sha push tranzaksiyasida
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (kind <> 'onec_agent' OR cash_register_id IS NULL)
  -- 'onec_agent' — Do'kon agenti (qaror #60): fiskal ko'prik, printer, tarozi va 1C imkoniyatlari shu qurilmada;
  -- kassaga bog'lanish cash_registers.fiscal_agent_id orqali (qaror #66)
);

ALTER TABLE auth.refresh_tokens ADD CONSTRAINT fk_rt_device FOREIGN KEY (device_id) REFERENCES app.devices(id);
ALTER TABLE auth.sessions       ADD CONSTRAINT fk_se_device FOREIGN KEY (device_id) REFERENCES app.devices(id);

CREATE TABLE app.memberships (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  user_id    UUID NOT NULL REFERENCES app.users(id),
  role_ids   UUID[] NOT NULL DEFAULT '{}',
  branch_ids UUID[] NOT NULL DEFAULT '{}', -- bo'sh = barcha filial
  status     TEXT NOT NULL CHECK (status IN ('active','blocked','invited')) DEFAULT 'active',
  -- 'invited' — BO-11 boshqa tenantda allaqachon mavjud foydalanuvchini taklif qilgan, u hali kod bilan
  -- qabul qilmagan (14 §18.2): login/tenant tanlovi/switch-tenant/sessiya profili uni e'tiborsiz qoldiradi
  invited_name TEXT NULL,
  -- taklif qiluvchi kiritgan ism: qabul qilinmaguncha (NOT NULL = hali qabul qilinmagan) BO-11 ro'yxatida
  -- users.name o'rniga ko'rsatiladi; qabulda NULL bo'ladi. Qabul qilinmagan a'zolik bloklansa, blokdan
  -- chiqarish uni 'invited'ga qaytaradi ('active'ga emas)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  version    INT NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, user_id),
  CHECK (status <> 'invited' OR invited_name IS NOT NULL)
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
  limit_value     NUMERIC(18,4) NULL, -- ma'nosi permission_code'ga bog'liq: foiz YOKI summa (3-bo'lim, aniqlashtirish #6);
  -- API'da 4 xonali satr ("5.0000"), UI foiz/so'mni permission_code'ga qarab formatlaydi
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
  name_ru          TEXT NULL, -- (qaror #29) ixtiyoriy, chek/UI ikkinchi til qatori ("name / name_ru")
  category_id      UUID NULL REFERENCES app.product_categories(id),
  unit_code        TEXT NOT NULL REFERENCES platform.units(code),
  mxik_code        TEXT NULL CHECK (mxik_code IS NULL OR mxik_code ~ '^[0-9]{17}$'), -- yaratishda bloklamaydi, sotuvdan oldin shart
  package_code     TEXT NULL CHECK (package_code IS NULL OR length(package_code) <= 20),
                   -- tasnif.soliq.uz qadoq kodi; mxik_code kabi yaratishda bloklamaydi, fiskal chekdan oldin shart (OFD PackageCode)
  vat_rate         NUMERIC(5,2) NULL, -- 12.00 / 0.00 (aniqlashtirish #8: vat_exemption_code bilan birga)
  vat_exemption_code TEXT NULL, -- imtiyoz kodi, vat_rate o'rniga/bilan
  is_marked        BOOLEAN NOT NULL DEFAULT false,
  marking_group_code TEXT NULL REFERENCES platform.marking_product_groups(code), -- is_marked=true bo'lsa majburiy (qabul muddati, qaror #63)
  is_weighed       BOOLEAN NOT NULL DEFAULT false,
  turnover_tax_group TEXT NOT NULL DEFAULT 'general' CHECK (turnover_tax_group IN ('general','tobacco')),
                   -- aylanma solig'i stavka guruhi (13 §4.3, platform.turnover_tax_rates); tamaki — alohida stavka
  min_stock        NUMERIC(18,3) NULL,
  archived_at      TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          INT NOT NULL DEFAULT 1,
  CHECK (vat_rate IS NOT NULL OR vat_exemption_code IS NOT NULL),
  CHECK (NOT is_marked OR marking_group_code IS NOT NULL)
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
  UNIQUE (tenant_id, barcode),
  CHECK (kind <> 'internal' OR barcode ~ '^04[0-9]{11}$') -- internal_barcode_seq diapazoni (GS1 RCN 040–049)
);

CREATE TABLE app.product_prices (
  id                  UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id           UUID NOT NULL REFERENCES app.tenants(id),
  product_id          UUID NOT NULL REFERENCES app.products(id),
  branch_id           UUID NULL REFERENCES app.branches(id), -- null = hamma filial
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

-- Ichki shtrix-kod (US-M09-05): EAN-13 = lpad(next_value, 12, '0') || nazorat raqami → '04' + 10 raqam + K.
-- GS1 RCN-13 diapazoni 040–049 (kompaniya ichida ishlatish) — real GTIN'lar bilan ham, tarozi prefikslari
-- (weight_barcode_templates, 20–29) bilan ham kesishmaydi.
CREATE TABLE app.internal_barcode_seq (
  tenant_id  UUID PRIMARY KEY REFERENCES app.tenants(id),
  next_value BIGINT NOT NULL DEFAULT 40000000000
             CHECK (next_value BETWEEN 40000000000 AND 49999999999) -- 040000000000…049999999999
);

CREATE TABLE app.discount_rules (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  name        TEXT NOT NULL,
  scope       TEXT NOT NULL CHECK (scope IN ('product','category','all')),
  target_ids  UUID[] NOT NULL DEFAULT '{}',
  kind        TEXT NOT NULL CHECK (kind IN ('percent','amount','n_plus_m')),
  value       NUMERIC(18,4) NOT NULL, -- kind='percent' bo'lsa foiz, aks holda summa (aniqlashtirish #7)
  branch_ids  UUID[] NOT NULL DEFAULT '{}', -- bo'sh = hammasi
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
```

### 2.5a Tasdiqlash va to'lov seanslari

```sql
-- masofaviy tasdiq navbati (BO-16)
CREATE TABLE app.approval_requests (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  branch_id            UUID NOT NULL REFERENCES app.branches(id),
  kind                 TEXT NOT NULL CHECK (kind IN ('discount_over_limit','return_over_limit','return_no_receipt',
                         'debt_over_limit','cash_withdrawal_over_limit','price_change','expense_over_limit',
                         'write_off_over_limit','card_manual_entry')), -- card_manual_entry — qaror #71
  permission_code      TEXT NOT NULL, -- tasdiqlovchida bo'lishi shart kod (`15-xavfsizlik-va-audit.md` §2.3 xaritasi)
  requested_value      NUMERIC(18,4) NULL, -- summa yoki foiz (role_permissions.limit_value bilan bir xil birlik)
  context              JSONB NOT NULL DEFAULT '{}',
  linked_doc_type      TEXT NULL, -- jadval nomi ('price_changes','expenses',...)
  linked_doc_id        UUID NULL,
  device_id            UUID NULL REFERENCES app.devices(id),
  status               TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','approved','rejected','expired','consumed')),
  requested_by         UUID NOT NULL REFERENCES app.users(id),
  requested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at           TIMESTAMPTZ NOT NULL, -- requested_at + 15 daqiqa (standart, sozlanadi — 26 #87)
  resolved_by          UUID NULL REFERENCES app.users(id),
  resolved_at          TIMESTAMPTZ NULL,
  reject_reason        TEXT NULL,
  consumed_at          TIMESTAMPTZ NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status <> 'rejected' OR reject_reason IS NOT NULL),
  CHECK (status NOT IN ('approved','rejected','consumed') OR (resolved_by IS NOT NULL AND resolved_at IS NOT NULL)),
  CHECK (resolved_by IS NULL OR resolved_by <> requested_by) -- o'zini o'zi tasdiqlay olmaydi
);
CREATE INDEX idx_approval_requests_pending ON app.approval_requests (tenant_id, branch_id, requested_at)
  WHERE status = 'pending';
CREATE INDEX idx_approval_requests_linked ON app.approval_requests (tenant_id, linked_doc_type, linked_doc_id)
  WHERE linked_doc_id IS NOT NULL;
-- price_changes.approval_request_id qo'shilmaydi — bog'lanish linked_doc_type='price_changes' orqali.

-- qo'llangan har tasdiqning append-only izi
CREATE TABLE app.doc_approvals (
  id                   UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id            UUID NOT NULL REFERENCES app.tenants(id),
  doc_type             TEXT NOT NULL, -- 'sales','returns','cash_movements','expenses','write_offs','price_changes','debt_payments'
  doc_id               UUID NOT NULL,
  line_id              UUID NULL, -- chegirma — sale_lines.id; card_manual_entry — sale_payments.id (debt_payments/returns'da NULL)
  kind                 TEXT NOT NULL CHECK (kind IN ('discount_over_limit','return_over_limit','return_no_receipt',
                         'debt_over_limit','cash_withdrawal_over_limit','price_change','expense_over_limit',
                         'write_off_over_limit','card_manual_entry')), -- card_manual_entry — qaror #71
  mode                 TEXT NOT NULL CHECK (mode IN ('local_pin','remote_request')),
  approved_by          UUID NOT NULL REFERENCES app.users(id),
  approval_request_id  UUID NULL REFERENCES app.approval_requests(id),
  pin_verified_locally BOOLEAN NOT NULL DEFAULT false,
  requested_value      NUMERIC(18,4) NULL,
  approved_at          TIMESTAMPTZ NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (mode <> 'remote_request' OR approval_request_id IS NOT NULL),
  CHECK (mode <> 'local_pin' OR pin_verified_locally)
);
CREATE UNIQUE INDEX uq_doc_approvals_request ON app.doc_approvals (approval_request_id) WHERE approval_request_id IS NOT NULL;
CREATE INDEX idx_doc_approvals_doc ON app.doc_approvals (tenant_id, doc_type, doc_id);
-- Mavjud returns.approved_by/approved_at, price_changes.approved_by, debt_writeoffs.approved_by —
-- hujjat sarlavhasidagi "yakuniy tasdiqlovchi" sifatida qoladi; batafsil iz — doc_approvals.

-- UzQR/Click/Payme/Uzum to'lov seansi (faqat do'kon to'lovi; billing checkout — billing_payments)
CREATE TABLE app.payment_checkouts (
  checkout_ref     UUID PRIMARY KEY, -- qurilma beradi (UUIDv7)
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  device_id        UUID NULL REFERENCES app.devices(id),
  provider         TEXT NOT NULL CHECK (provider IN ('uzqr','click','payme','uzum')),
  qr_type          TEXT NULL CHECK (qr_type IN ('static','dynamic')),
  amount           NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  provider_tx_id   TEXT NULL,
  status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','confirmed','failed','expired','consumed')),
  confirmed_at     TIMESTAMPTZ NULL,
  expires_at       TIMESTAMPTZ NOT NULL,
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (provider = 'uzqr' OR qr_type IS NULL),
  CHECK (provider <> 'uzqr' OR qr_type = 'dynamic'), -- statik UzQR seanssiz: sale_payments'da kassir qo'lda tasdiqlaydi
  UNIQUE (provider, provider_tx_id)
);
CREATE INDEX idx_payment_checkouts_expiry ON app.payment_checkouts (expires_at) WHERE status = 'pending';
-- Webhook tenant kontekstisiz keladi → 4.5-bo'limdagi SECURITY DEFINER funksiyalar.

-- Integratsiyalangan bank karta terminallari reyestri (qaror #71). Bitta terminal — bitta filial; kassaga bog'lash
-- ixtiyoriy (bir kassada bir nechta terminal bo'lishi mumkin, is_default — POS avtomatik tanlaydigani).
-- adapter (21 §9.4): agent_ecr — AgentEcrAdapter, Do'kon agenti (127.0.0.1:47110/v1/card/*) orqali LAN/Wi-Fi'dagi
-- terminal; cloud — CloudTerminalAdapter, server ↔ vendor bulut API (terminal ID bo'yicha); android_intent — Kotlin POS
-- shu smart-terminaldagi vendor to'lov ilovasi (Intent/AIDL/SDK); softpos — SoftPosAdapter (NFC, MayaSoft SDK);
-- fake — FakeCardTerminalAdapter (dev/test/staging va demo-tenant, prod guard; real pul yo'q).
-- agent_id FK — 0028 store_agent da (fk_ct_agent), cash_registers.fiscal_agent_id naqshi.
CREATE TABLE app.card_terminals (
  id                       UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id                UUID NOT NULL REFERENCES app.tenants(id),
  branch_id                UUID NOT NULL REFERENCES app.branches(id),
  cash_register_id         UUID NULL REFERENCES app.cash_registers(id),
  name                     TEXT NOT NULL,                  -- BO-12 da ko'rinadigan nom ("Kassa 1 — Humo P3")
  vendor                   TEXT NOT NULL CHECK (vendor ~ '^[a-z0-9_]{2,32}$'), -- 'rahmat','era','humo','smartone','mayasoft','fake'
  model                    TEXT NULL,                      -- 'Sunmi P3', 'PAX A930' ...
  adapter                  TEXT NOT NULL CHECK (adapter IN ('agent_ecr','cloud','android_intent','softpos','fake')),
  driver                   TEXT NOT NULL CHECK (driver ~ '^[a-z0-9_]{2,40}$'), -- 'rahmat_lan','era_lan','arcus2_tcp','era_cloud','sunmi_intent','mayasoft_softpos','fake'
  agent_id                 UUID NULL,                      -- adapter='agent_ecr': xizmat qiluvchi Do'kon agenti
  local_id                 TEXT NULL,                      -- agent capabilities.card_terminal.devices[].local_id
  host                     INET NULL,                      -- terminalning LAN manzili (faqat xususiy tarmoq)
  port                     INT NULL CHECK (port IS NULL OR port BETWEEN 1 AND 65535),
  vendor_terminal_ref      TEXT NULL,                      -- adapter='cloud': vendor bulutidagi terminal ID
  tid                      TEXT NULL CHECK (tid IS NULL OR tid ~ '^[0-9A-Za-z]{1,16}$'), -- bank terminal ID (TID)
  mid                      TEXT NULL CHECK (mid IS NULL OR mid ~ '^[0-9A-Za-z]{1,20}$'), -- merchant ID (MID)
  acquirer_counterparty_id UUID NULL REFERENCES app.counterparties(id), -- ekvayer bank (bank_settlements solishtirish)
  status                   TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','archived')),
  is_default               BOOLEAN NOT NULL DEFAULT false,
  capabilities             JSONB NOT NULL DEFAULT '{}',
                           -- {refund, void, status_query, last_transaction, settlement, contactless, returns_card_type,
                           --  returns_bin} — adapter/agent hello'dan; POS faqat true bo'lgan amallarni taklif qiladi.
                           -- status — boshqaruv holati (BO-12); jonli holat — health_status (agent card.status vazifasi,
                           -- har 5 daqiqa, yoki POS health() natijasi)
  health_status            TEXT NOT NULL DEFAULT 'unknown' CHECK (health_status IN ('online','busy','offline','error','unknown')),
  health_checked_at        TIMESTAMPTZ NULL,
  created_by               UUID NOT NULL REFERENCES app.users(id),
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  version                  INT NOT NULL DEFAULT 1,
  CHECK (adapter <> 'agent_ecr' OR (agent_id IS NOT NULL AND local_id IS NOT NULL AND host IS NOT NULL)),
  CHECK (adapter <> 'cloud' OR vendor_terminal_ref IS NOT NULL),
  CHECK (adapter = 'agent_ecr' OR (agent_id IS NULL AND local_id IS NULL)),
  CHECK ((adapter = 'fake') = (driver = 'fake')),
  -- ixtiyoriy host yo'q: faqat RFC 1918 xususiy IPv4 (printer qoidasi kabi, 34 §14.3)
  CHECK (host IS NULL OR host << inet '10.0.0.0/8' OR host << inet '172.16.0.0/12' OR host << inet '192.168.0.0/16'),
  CHECK (adapter = 'fake' OR status <> 'active' OR tid IS NOT NULL),
  CHECK (NOT is_default OR cash_register_id IS NOT NULL)
);
CREATE UNIQUE INDEX uq_card_terminals_agent_local ON app.card_terminals (agent_id, local_id)
  WHERE agent_id IS NOT NULL AND status <> 'archived';
CREATE UNIQUE INDEX uq_card_terminals_tid ON app.card_terminals (tenant_id, tid)
  WHERE tid IS NOT NULL AND status <> 'archived';
CREATE UNIQUE INDEX uq_card_terminals_default ON app.card_terminals (cash_register_id)
  WHERE is_default AND status = 'active';
CREATE INDEX idx_card_terminals_register ON app.card_terminals (tenant_id, cash_register_id) WHERE status = 'active';
```

### 2.6 Hujjatlar

**Umumiy sarlavha** (`11-malumotlar-modeli.md` §6, yagona ro'yxat) — har bir hujjat jadvalida takrorlanadi: `id, tenant_id, branch_id, number, temp_number, doc_date, status, created_by, created_at, updated_at, posted_at, cancelled_at, cancelled_by, cancel_reason, client_event_id, device_id, comment`, `UNIQUE (tenant_id, device_id, temp_number)`, `UNIQUE (tenant_id, client_event_id)`. `shifts` bundan mustasno — raqamlanmaydi (11-bo'lim), o'z maxsus sarlavhasiga ega.

```sql
-- shift_no — qurilma beradi, OFD smena raqami; variance — generated ustun (counted_cash - expected_cash).
CREATE TABLE app.shifts (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  branch_id          UUID NOT NULL REFERENCES app.branches(id),
  cash_register_id   UUID NOT NULL REFERENCES app.cash_registers(id),
  device_id          UUID NOT NULL REFERENCES app.devices(id), -- bitta smena — bitta qurilma
  shift_no           INT  NOT NULL CHECK (shift_no > 0), -- qurilma beradi, kassa ichida ketma-ket (qaror #12)
  status             TEXT NOT NULL CHECK (status IN ('open','closed')) DEFAULT 'open',
  opened_by          UUID NOT NULL REFERENCES app.users(id),
  opened_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_by          UUID NULL REFERENCES app.users(id),
  closed_at          TIMESTAMPTZ NULL,
  opening_cash       NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (opening_cash >= 0),
  expected_cash      NUMERIC(18,2) NULL, -- server hisoblaydi: opening_cash + Σcash_moves(shift)
  counted_cash       NUMERIC(18,2) NULL,
  variance           NUMERIC(18,2) GENERATED ALWAYS AS (counted_cash - expected_cash) STORED,
  variance_note      TEXT NULL,
  counted_card_total NUMERIC(18,2) NULL, -- qo'lda belgilangan "karta" jami (POS-15)
  comment            TEXT NULL,
  client_event_id    UUID NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, client_event_id),
  UNIQUE (tenant_id, cash_register_id, shift_no),
  CHECK (status <> 'closed' OR (counted_cash IS NOT NULL AND expected_cash IS NOT NULL)),
  CHECK (counted_cash IS NULL OR expected_cash IS NULL OR counted_cash = expected_cash OR variance_note IS NOT NULL)
);
-- bitta kassada bir vaqtda faqat bitta ochiq smena
CREATE UNIQUE INDEX uq_shifts_one_open ON app.shifts (cash_register_id) WHERE status = 'open';

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
  counterparty_id  UUID NULL REFERENCES app.counterparties(id), -- nasiya/qarzga sotuvda
  total_amount     NUMERIC(18,2) NULL, -- hisoblangan jami (aniqlashtirish #10 — tezkor o'qish uchun qo'shimcha)
  is_offline          BOOLEAN NOT NULL DEFAULT false,
  debt_limit_exceeded BOOLEAN NOT NULL DEFAULT false, -- offline nasiya limitdan oshgan (tavsiya #7) — xato emas, bayroq
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
CREATE INDEX idx_sales_debt_limit_exceeded ON app.sales (tenant_id) WHERE debt_limit_exceeded;

CREATE TABLE app.sale_lines (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  sale_id            UUID NOT NULL REFERENCES app.sales(id),
  line_no            INT NOT NULL,
  product_id         UUID NOT NULL REFERENCES app.products(id),
  qty                NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  price              NUMERIC(18,4) NOT NULL CHECK (price >= 0),
  discount_amount    NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  vat_rate           NUMERIC(5,2) NOT NULL,
  vat_exemption_code TEXT NULL,
  discount_pct       NUMERIC(5,2) NULL CHECK (discount_pct BETWEEN 0 AND 100), -- ma'lumot uchun; manba — discount_amount
  discount_source    TEXT NULL CHECK (discount_source IN ('manual','standing_customer','rule')),
  discount_rule_id   UUID NULL REFERENCES app.discount_rules(id),
  vat_amount         NUMERIC(18,2) NOT NULL DEFAULT 0,
  line_total         NUMERIC(18,2) NOT NULL,
  cost_amount        NUMERIC(18,2) NOT NULL DEFAULT 0,
  marking_code       TEXT NULL,
  lot_allocations    JSONB NOT NULL DEFAULT '[]',
  settled_amount     NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (settled_amount >= 0),
                     -- qarz to'lovi (debt_settlement) va aralash to'lovli sotuvning birinchi chekida fiskallangan
                     -- kumulyativ summa; server posting'da yangilaydi (18 §12.2, qaror #67)
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (sale_id, line_no),
  CHECK (settled_amount <= line_total),
  CHECK (marking_code IS NULL OR qty = 1), -- markirovkalangan tovarda qty=1 majburiy
  CHECK ((discount_amount = 0) = (discount_source IS NULL)),
  CHECK (discount_source IS DISTINCT FROM 'rule' OR discount_rule_id IS NOT NULL)
);
CREATE INDEX idx_sale_lines_product ON app.sale_lines (tenant_id, product_id);

-- Karta terminali tranzaksiyalari (qaror #71). id = attempt_id: POS/qurilma beradi (UUIDv7), terminalga ERN/order
-- ref sifatida uzatiladi — idempotentlik kaliti (agent jurnalida ham UNIQUE). Qator har bir urinishga bitta (kind):
-- purchase (xarid), refund (qaytarish), void (shu kun, settlement'gacha bekor qilish). Holat so'rovi
-- (get_status/get_last_transaction) yangi qator emas — shu qatorning status/resolved_by ustunlarini yangilaydi;
-- settlement — card_terminal_settlements. Online: POS natijani POST /card-terminal-transactions bilan darhol yozadi;
-- offline: natija sale.created / return.created / debt_payment.created payload'idagi card_result ichida (payments[] / refund_card / ildiz)
-- keladi va server qatorni shu voqeadan upsert qiladi (16 §2.1, 18 §2.7). PAN/track/CVV hech qachon yozilmaydi.
-- doc_type/doc_id — tranzaksiya qaysi hujjatga yopilgani (polimorfik). Sotuvsiz qolgan approved purchase avtomatik void
-- qilinmaydi: 24 soatdan keyin sync_exceptions(kind='card_orphan_transaction') — qo'lda ko'rib chiqiladi (16 §2.1).
CREATE TABLE app.card_terminal_transactions (
  id                      UUID PRIMARY KEY,               -- = attempt_id, har doim qurilma beradi
  tenant_id               UUID NOT NULL REFERENCES app.tenants(id),
  branch_id               UUID NOT NULL REFERENCES app.branches(id),
  card_terminal_id        UUID NOT NULL REFERENCES app.card_terminals(id),
  cash_register_id        UUID NULL REFERENCES app.cash_registers(id),
  shift_id                UUID NULL REFERENCES app.shifts(id),
  device_id               UUID NULL REFERENCES app.devices(id),
  kind                    TEXT NOT NULL CHECK (kind IN ('purchase','refund','void')),
  original_transaction_id UUID NULL REFERENCES app.card_terminal_transactions(id), -- refund/void: asl purchase
  amount                  NUMERIC(18,2) NOT NULL CHECK (amount > 0),  -- so'ralgan summa
  approved_amount         NUMERIC(18,2) NULL CHECK (approved_amount IS NULL OR approved_amount > 0), -- terminal tasdiqlagani
  currency                TEXT NOT NULL DEFAULT 'UZS' CHECK (currency = 'UZS'),
  status                  TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','approved','declined','unknown','voided')),
                            -- pending — terminalga yuborildi, javob kutilmoqda; unknown — taymaut/aloqa uzildi, natija
                            -- noma'lum (yangi purchase bloklanadi); voided — approved purchase keyin void bilan bekor qilindi.
                            -- CardTxResult.status xaritasi: approved → approved; declined/cancelled/error → declined
                            -- (decline_code = 'cancelled'/'error'/bank kodi); timeout/unknown → unknown; holat so'rovi
                            -- natijasi not_found → declined (decline_code='not_found')
  approval_code           TEXT NULL CHECK (approval_code IS NULL OR approval_code ~ '^[0-9A-Za-z]{1,12}$'),
  rrn                     TEXT NULL CHECK (rrn IS NULL OR rrn ~ '^[0-9A-Za-z]{6,32}$'),
  stan                    TEXT NULL,
  card_mask               TEXT NULL CHECK (card_mask IS NULL OR card_mask ~ '^[0-9]{4}[*]+[0-9]{4}$'), -- normallashtirilgan 4+4
  card_scheme             TEXT NULL CHECK (card_scheme IN ('uzcard','humo','visa','mastercard','unionpay','mir','other')),
  card_type               TEXT NULL CHECK (card_type IN ('personal','corporate','social','unknown')),
  card_type_source        TEXT NULL CHECK (card_type_source IN ('terminal','bin_table')),
  entry_mode              TEXT NULL CHECK (entry_mode IN ('chip','contactless','magstripe','fallback')), -- kartani o'qish usuli
  tid                     TEXT NULL,
  mid                     TEXT NULL,
  acquirer                TEXT NULL,
  decline_code            TEXT NULL,
  decline_message         TEXT NULL,
  resolved_by             TEXT NULL CHECK (resolved_by IN ('auto','status_query','manager')),
                          -- auto — terminal javobi; status_query — get_status/get_last_transaction;
                          -- manager — unknown'ni menejer terminal chekiga qarab yopdi (card.manual_entry.approve):
                          -- faqat "o'tdi / o'tmadi" tasdig'i, hech qanday karta rekviziti kiritilmaydi — approved'da
                          -- rrn/card_mask/approval_code/card_type NULL qoladi, to'lov qatori card_entry_mode='manual',
                          -- manual_reason='unknown_result' (rekvizitsiz), tranzaksiya hujjatga doc_type/doc_id orqali bog'lanadi
  resolved_by_user_id     UUID NULL REFERENCES app.users(id),
  terminal_response       JSONB NOT NULL DEFAULT '{}',    -- adapterning sanitizatsiyalangan xom javobi (PAN/track yo'q)
  slip_text               TEXT NULL,                      -- terminal cheki matni (ixtiyoriy)
  client_event_id         UUID NULL,                      -- bog'langan sale/return/debt_payment voqeasi
  doc_type                TEXT NULL CHECK (doc_type IN ('sales','returns','debt_payments')),
  doc_id                  UUID NULL,
  settlement_id           UUID NULL,                      -- FK 0018 da: fk_ctt_settlement → card_terminal_settlements
  requested_at            TIMESTAMPTZ NOT NULL,           -- qurilma soati
  tx_at                   TIMESTAMPTZ NULL,               -- terminal bergan tranzaksiya vaqti
  resolved_at             TIMESTAMPTZ NULL,
  created_by              UUID NOT NULL REFERENCES app.users(id),
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (kind <> 'void' OR original_transaction_id IS NOT NULL),  -- void doim asl purchase'ga bog'liq
  CHECK (kind <> 'purchase' OR original_transaction_id IS NULL),
  CHECK (kind = 'purchase' OR status <> 'voided'),
  -- tasdiqlangan purchase/refund: terminal natijasida RRN va niqob majburiy (fiskal chek rekviziti, qaror #64);
  -- menejer yopgan unknown (resolved_by='manager') — rekvizitsiz
  CHECK (status NOT IN ('approved','voided') OR kind = 'void' OR (approved_amount IS NOT NULL
         AND (resolved_by = 'manager' OR (rrn IS NOT NULL AND card_mask IS NOT NULL)))),
  CHECK (resolved_by IS DISTINCT FROM 'manager' OR (rrn IS NULL AND card_mask IS NULL AND approval_code IS NULL
         AND card_type IS NULL)),
  CHECK ((card_type IS NULL) = (card_type_source IS NULL)),
  CHECK (status IN ('pending','unknown') OR resolved_at IS NOT NULL),
  CHECK (resolved_by IS DISTINCT FROM 'manager' OR resolved_by_user_id IS NOT NULL),
  CHECK ((doc_type IS NULL) = (doc_id IS NULL))
);
CREATE UNIQUE INDEX uq_ctt_purchase_rrn ON app.card_terminal_transactions (tenant_id, tid, rrn)
  WHERE kind = 'purchase' AND rrn IS NOT NULL AND tid IS NOT NULL;
-- bitta terminalda bir vaqtda bitta ochiq urinish (agent DeviceLane FIFO bilan bir xil qoida)
CREATE UNIQUE INDEX uq_ctt_one_pending ON app.card_terminal_transactions (card_terminal_id) WHERE status = 'pending';
CREATE INDEX idx_ctt_unresolved ON app.card_terminal_transactions (tenant_id, card_terminal_id)
  WHERE status IN ('pending','unknown');
CREATE INDEX idx_ctt_orphans ON app.card_terminal_transactions (tenant_id, created_at)
  WHERE status = 'approved' AND doc_id IS NULL;
CREATE INDEX idx_ctt_shift ON app.card_terminal_transactions (shift_id) WHERE shift_id IS NOT NULL;
CREATE INDEX idx_ctt_original ON app.card_terminal_transactions (original_transaction_id) WHERE original_transaction_id IS NOT NULL;

CREATE TABLE app.sale_payments (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  sale_id        UUID NOT NULL REFERENCES app.sales(id),
  method         TEXT NOT NULL CHECK (method IN ('cash','card','uzqr','click','payme','uzum','debt')),
  amount         NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  provider_tx_id TEXT NULL,
  terminal_ref   TEXT NULL, -- statik UzQR to'lov raqami (ixtiyoriy) / integrated kartada server card_result.tid'dan to'ldiradi
  card_type      TEXT NULL CHECK (card_type IN ('personal','corporate','social','unknown')), -- chek rekviziti (VMQ-943 1-ilova 7-band), faqat integrated
  card_mask      TEXT NULL CHECK (card_mask IS NULL OR card_mask ~ '^[0-9]{4}[*]+[0-9]{4}$'), -- birinchi va oxirgi 4 raqam, faqat integrated
  rrn            TEXT NULL, -- terminal tranzaksiyasining noyob raqami (RRN), faqat integrated
  qr_type        TEXT NULL CHECK (qr_type IN ('static','dynamic')),
  due_date       DATE NULL, -- method='debt': va'da sanasi → debt_moves.due_date manbasi
  checkout_ref   UUID NULL REFERENCES app.payment_checkouts(checkout_ref),
  -- karta kiritish usuli (qaror #64, #71): integrated — rekvizitlar faqat terminal natijasidan avtomatik;
  -- manual — karta terminalsiz (ilovadan tashqarida) qabul qilingan: faqat summa + manual_reason, hech qanday karta rekviziti yo'q
  card_entry_mode  TEXT NULL CHECK (card_entry_mode IN ('integrated','manual')),
  card_terminal_transaction_id UUID NULL REFERENCES app.card_terminal_transactions(id),
  approval_code    TEXT NULL CHECK (approval_code IS NULL OR approval_code ~ '^[0-9A-Za-z]{1,12}$'),
  card_scheme      TEXT NULL CHECK (card_scheme IN ('uzcard','humo','visa','mastercard','unionpay','mir','other')),
  card_type_source TEXT NULL CHECK (card_type_source IN ('terminal','bin_table')),
  manual_reason    TEXT NULL CHECK (manual_reason IN ('terminal_offline','terminal_error','unknown_result','standalone_terminal')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (method = 'debt' OR due_date IS NULL),
  CHECK (method NOT IN ('click','payme','uzum') OR provider_tx_id IS NOT NULL),
  -- UzQR: qr_type majburiy; provider_tx_id faqat dinamik QR'da (statik — kassir qo'lda tasdiqlaydi)
  CHECK (method <> 'uzqr' OR qr_type IS NOT NULL),
  CHECK (method <> 'uzqr' OR qr_type = 'static' OR provider_tx_id IS NOT NULL),
  CHECK (qr_type IS NULL OR method = 'uzqr'),
  CHECK (method <> 'card' OR terminal_ref IS NULL OR card_entry_mode = 'integrated'), -- terminalsiz kartada raqam kiritilmaydi
  -- karta (qaror #64, #71): kiritish usuli majburiy; integrated — tranzaksiya, RRN, niqob, karta turi (terminal yoki
  -- BIN jadvali; topilmasa 'unknown') majburiy, sabab yo'q; manual — tranzaksiyasiz, sabab majburiy, barcha karta
  -- rekvizitlari NULL (ilovada karta ma'lumoti qo'lda kiritilmaydi)
  CHECK ((method = 'card') = (card_entry_mode IS NOT NULL)),
  CHECK ((card_type IS NULL) = (card_type_source IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'integrated' OR (card_terminal_transaction_id IS NOT NULL
         AND rrn IS NOT NULL AND card_mask IS NOT NULL AND card_type IS NOT NULL AND manual_reason IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'manual' OR (card_terminal_transaction_id IS NULL AND manual_reason IS NOT NULL
         AND card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL AND card_scheme IS NULL)),
  CHECK (method = 'card' OR (card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL
         AND card_scheme IS NULL AND manual_reason IS NULL AND card_terminal_transaction_id IS NULL))
);
CREATE INDEX idx_sale_payments_sale ON app.sale_payments (sale_id);
-- bitta tasdiqlangan terminal tranzaksiyasi — bitta to'lov qatori
CREATE UNIQUE INDEX uq_sale_payments_card_tx ON app.sale_payments (card_terminal_transaction_id)
  WHERE card_terminal_transaction_id IS NOT NULL;

CREATE TABLE app.returns (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  number           TEXT NULL,
  temp_number      TEXT NULL,
  doc_date         DATE NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  sale_id          UUID NULL REFERENCES app.sales(id), -- null = chek topilmagan qaytarish
  shift_id         UUID NOT NULL REFERENCES app.shifts(id),
  cash_register_id UUID NOT NULL REFERENCES app.cash_registers(id),
  counterparty_id  UUID NULL REFERENCES app.counterparties(id), -- refund_method='debt_adjustment' uchun
  reason           TEXT NOT NULL CHECK (reason IN ('defective','wrong_item','customer_changed_mind','other')),
  refund_method    TEXT NOT NULL CHECK (refund_method IN ('cash','card','uzqr','click','payme','uzum','debt_adjustment')),
                   -- standart — asl to'lov usuli; qarzli sotuvda avval sotuvning ochiq qarzi kamayadi (debt_adjustment
                   -- qismi, chek yo'q), qolgani pul bilan (13 §2.5). Click/Payme/Uzum qaytarish — provayder kabinetida qo'lda
  -- refund_method='card' rekvizitlari (qaror #71): integrated — shu terminalda refund (settlement'gacha void) natijasi;
  -- manual — karta qaytarish terminalsiz (ilovadan tashqarida) amalga oshirilgan: faqat summa + manual_reason, karta
  -- rekvizitlari NULL (faol terminal bog'langan kassada card_manual_fallback siyosati bo'yicha)
  card_entry_mode  TEXT NULL CHECK (card_entry_mode IN ('integrated','manual')),
  card_terminal_transaction_id UUID NULL REFERENCES app.card_terminal_transactions(id),
  card_type        TEXT NULL CHECK (card_type IN ('personal','corporate','social','unknown')),
  card_mask        TEXT NULL CHECK (card_mask IS NULL OR card_mask ~ '^[0-9]{4}[*]+[0-9]{4}$'),
  rrn              TEXT NULL,
  approval_code    TEXT NULL CHECK (approval_code IS NULL OR approval_code ~ '^[0-9A-Za-z]{1,12}$'),
  card_scheme      TEXT NULL CHECK (card_scheme IN ('uzcard','humo','visa','mastercard','unionpay','mir','other')),
  manual_reason    TEXT NULL CHECK (manual_reason IN ('terminal_offline','terminal_error','unknown_result','standalone_terminal')),
  is_offline       BOOLEAN NOT NULL DEFAULT false,
  approved_by      UUID NULL REFERENCES app.users(id),
  approved_at      TIMESTAMPTZ NULL,
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
  CHECK (refund_method <> 'debt_adjustment' OR counterparty_id IS NOT NULL),
  CHECK (sale_id IS NOT NULL OR approved_by IS NOT NULL), -- chek topilmagan qaytarish — har doim tasdiq bilan
  CHECK ((refund_method = 'card') = (card_entry_mode IS NOT NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'integrated' OR (card_terminal_transaction_id IS NOT NULL
         AND rrn IS NOT NULL AND card_mask IS NOT NULL AND manual_reason IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'manual' OR (card_terminal_transaction_id IS NULL AND manual_reason IS NOT NULL
         AND card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL AND card_scheme IS NULL)),
  CHECK (refund_method = 'card' OR (card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL
         AND card_scheme IS NULL AND manual_reason IS NULL AND card_terminal_transaction_id IS NULL))
);
CREATE UNIQUE INDEX uq_returns_card_tx ON app.returns (card_terminal_transaction_id)
  WHERE card_terminal_transaction_id IS NOT NULL;

CREATE TABLE app.return_lines (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  return_id          UUID NOT NULL REFERENCES app.returns(id),
  line_no            INT NOT NULL,
  sale_line_id       UUID NULL REFERENCES app.sale_lines(id), -- null = chek topilmagan
  product_id         UUID NOT NULL REFERENCES app.products(id),
  qty                NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  price              NUMERIC(18,4) NOT NULL,
  vat_rate           NUMERIC(5,2) NOT NULL,
  vat_exemption_code TEXT NULL,
  marking_code       TEXT NULL,
  vat_amount         NUMERIC(18,2) NOT NULL DEFAULT 0,
  cost_amount        NUMERIC(18,2) NOT NULL DEFAULT 0,
  line_total         NUMERIC(18,2) NOT NULL,
  restock            BOOLEAN NOT NULL DEFAULT true,
                     -- false — tovar sotuvga qaytmaydi: muddati o'tgan tovar (qaror #48) — majburan false,
                     -- shu tranzaksiyada write_offs qoralamasi (reason='expired_return') yaratiladi
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (return_id, line_no),
  CHECK (marking_code IS NULL OR qty = 1)
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
  warehouse_id    UUID NOT NULL, -- FK app.warehouses(id), ALTER bilan pastda
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
ALTER TABLE app.purchase_orders ADD CONSTRAINT fk_po_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);

CREATE TABLE app.po_lines (
  id         UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  po_id      UUID NOT NULL REFERENCES app.purchase_orders(id),
  line_no    INT NOT NULL,
  product_id UUID NOT NULL REFERENCES app.products(id),
  qty        NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  price      NUMERIC(18,4) NULL CHECK (price IS NULL OR price >= 0), -- ixtiyoriy
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
  warehouse_id     UUID NOT NULL, -- FK app.warehouses(id)
  paid_immediately BOOLEAN NOT NULL DEFAULT false, -- aniqlashtirish #9: 2.6/2.8-provodka yo'lini tanlaydi
  kind             TEXT NOT NULL DEFAULT 'purchase' CHECK (kind IN ('purchase','gratuitous')),
                   -- gratuitous — tekin olingan tovar: Dt inv_acct / Kt 8530 bozor qiymatida, QQS va kreditorlik yo'q (13 §2.6a)
  source           TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','purchase_order','einvoice','ocr')),
  einvoice_id      UUID NULL, -- FK pastda; "qizil" faktura QQS kechiktirish shu orqali aniqlanadi
  ai_ocr_job_id    UUID NULL, -- FK pastda → app.ai_ocr_jobs(id)
  ettn_ref         TEXT NULL, -- qo'lda e-TTN belgisi
  poa_id           UUID NULL, -- FK pastda (powers_of_attorney yaratilgach, 0020) → app.powers_of_attorney(id)
  poa_number       TEXT NULL, -- e-ishonchnoma raqami (powers_of_attorney.number dan yoki qo'lda)
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
  CHECK (source <> 'einvoice' OR einvoice_id IS NOT NULL),
  CHECK (kind <> 'gratuitous' OR NOT paid_immediately)
);
ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_warehouse FOREIGN KEY (warehouse_id) REFERENCES app.warehouses(id);
-- fk_gr_einvoice / uq_gr_einvoice_active — einvoices yaratilgandan keyin, 2.8-bo'limda (0020-revizion)

CREATE TABLE app.receipt_lines (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  receipt_id         UUID NOT NULL REFERENCES app.goods_receipts(id),
  line_no            INT NOT NULL,
  product_id         UUID NOT NULL REFERENCES app.products(id),
  qty                NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  cost               NUMERIC(18,4) NOT NULL CHECK (cost >= 0),
  vat_rate           NUMERIC(5,2) NOT NULL,
  vat_exemption_code TEXT NULL, -- imtiyoz kodi, products bo'linishi bilan izchil
  vat_amount         NUMERIC(18,2) NOT NULL DEFAULT 0,
  expiry_date        DATE NULL,
  discrepancy_reason TEXT NULL CHECK (discrepancy_reason IN ('short','excess','damaged','wrong_item','other')),
                     -- PO/e-faktura miqdoridan farq sababi (POS-08)
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
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
  reason          TEXT NOT NULL CHECK (reason IN ('expired','damaged','excess','other')), -- sarlavhada (19-api-ombor.md §12)
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
  lot_id           UUID NOT NULL, -- FK app.stock_lots(id) — 2.7-bo'limda ALTER bilan qo'shiladi
  qty              NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  cost             NUMERIC(18,4) NOT NULL,
  vat_amount       NUMERIC(18,2) NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (supplier_return_id, line_no)
);

CREATE TABLE app.transfers (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id), -- aniqlashtirish: jo'natuvchi filial sifatida ishlatiladi
  number           TEXT NULL,
  temp_number      TEXT NULL,
  doc_date         DATE NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('draft','posted','sent','received','discrepancy','cancelled')) DEFAULT 'draft',
                   -- posted = hujjat o'tkazildi + e-TTN yaratildi (qoldiq o'zgarmaydi); sent = stock_moves jo'natuvchida −
  from_branch_id   UUID NOT NULL REFERENCES app.branches(id),
  to_branch_id     UUID NOT NULL REFERENCES app.branches(id),
  from_warehouse_id UUID NOT NULL, -- FK app.warehouses(id)
  to_warehouse_id   UUID NOT NULL, -- FK app.warehouses(id)
  sent_at          TIMESTAMPTZ NULL,
  sent_by          UUID NULL REFERENCES app.users(id),
  received_at      TIMESTAMPTZ NULL,
  received_by      UUID NULL REFERENCES app.users(id),
  transport_mode   TEXT NOT NULL DEFAULT 'vehicle' CHECK (transport_mode IN ('vehicle','on_foot_or_public')),
                   -- vehicle — e-TTN ("Ombordan omborga") majburiy; on_foot_or_public — e-TTN talab qilinmaydi
  ettn_ref         TEXT NULL, -- operator kabinetida rasmiylashtirilgan e-TTN raqami; send — transport_mode='vehicle' da
                   -- e-TTN registered bo'lmaguncha rad (409 ETTN_REQUIRED)
  vehicle_plate    TEXT NULL, -- e-TTN rekviziti; transport_mode='vehicle' bo'lsa post'da shart (ilova tekshiradi)
  driver_name      TEXT NULL, -- e-TTN rekviziti
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
  CHECK (from_branch_id <> to_branch_id),
  CHECK (branch_id = from_branch_id)
);
ALTER TABLE app.transfers ADD CONSTRAINT fk_tr_from_wh FOREIGN KEY (from_warehouse_id) REFERENCES app.warehouses(id);
ALTER TABLE app.transfers ADD CONSTRAINT fk_tr_to_wh   FOREIGN KEY (to_warehouse_id)   REFERENCES app.warehouses(id);

-- bitta qator FIFO bo'yicha bir nechta partiyadan chiqishi mumkin — bitta lot_id yetarli emas,
-- shuning uchun lot_allocations JSONB ishlatiladi (sale_lines bilan bir xil shakl), alohida lot_id ustuni yo'q.
CREATE TABLE app.transfer_lines (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  transfer_id UUID NOT NULL REFERENCES app.transfers(id),
  line_no     INT NOT NULL,
  product_id  UUID NOT NULL REFERENCES app.products(id),
  qty_sent    NUMERIC(18,3) NOT NULL CHECK (qty_sent > 0),
  qty_received NUMERIC(18,3) NULL CHECK (qty_received IS NULL OR qty_received >= 0),
  unit_cost       NUMERIC(18,4) NULL, -- send'da to'ldiriladi (allokatsiyalarning o'rtachasi)
  lot_allocations JSONB NOT NULL DEFAULT '[]', -- [{lot_id, qty, unit_cost}] — sale_lines bilan bir xil shakl
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
  warehouse_id    UUID NOT NULL, -- FK app.warehouses(id)
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(), -- snapshot vaqti (qaror #53)
  responsible_user_id UUID NULL REFERENCES app.users(id), -- ko'rsatilsa kamomad → 4730, aks holda 5910 (13 §2.11)
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
  snapshot_qty NUMERIC(18,3) NOT NULL, -- stock_counts.started_at holatidagi qoldiq
  expected   NUMERIC(18,3) NOT NULL, -- yaratishda = snapshot_qty; post'da qayta hisoblanadi (qaror #53, 13 X-02):
             -- snapshot_qty + Σ stock_moves.qty (started_at < moved_at <= counted_at)
  counted    NUMERIC(18,3) NULL, -- sanash tugamaguncha NULL (19-api-ombor.md `counted:null`)
  counted_at TIMESTAMPTZ NULL, -- counted kiritilgan vaqt (qaror #53): qurilma vaqti (offline sanashda ham —
             -- voqeaning recorded_at'i, server_time ofseti bilan tuzatilgan), online kiritishda — server vaqti;
             -- counted NULL bo'lsa NULL
  diff       NUMERIC(18,3) GENERATED ALWAYS AS (counted - expected) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (count_id, line_no),
  CHECK ((counted IS NULL) = (counted_at IS NULL))
);

CREATE TABLE app.write_offs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  warehouse_id    UUID NOT NULL, -- FK app.warehouses(id)
  responsible_user_id UUID NULL REFERENCES app.users(id), -- belgilansa 4730 (13-provodka-qoidalari.md §2.12)
  promo_order_ref TEXT NULL, -- reklama aksiyasi buyrug'i raqami; gift_kind='promo_justified' qatori bo'lsa majburiy (ilova tekshiradi)
  source_return_id UUID NULL REFERENCES app.returns(id), -- muddati o'tgan tovar qaytarilganda avtomatik qoralama (qaror #48)
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
  lot_id      UUID NULL, -- FK app.stock_lots(id) — 2.7-bo'limda qo'shiladi
  qty         NUMERIC(18,3) NOT NULL CHECK (qty > 0),
  reason      TEXT NOT NULL CHECK (reason IN ('expired','damaged','gift','expired_return','other')),
  gift_kind   TEXT NULL CHECK (gift_kind IN ('promo_justified','other')), -- 13 §2.12: promo_justified → 9410, QQSsiz; other → 9430 + QQS
  cost_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (write_off_id, line_no),
  CHECK ((reason = 'gift') = (gift_kind IS NOT NULL))
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
  valid_from     TIMESTAMPTZ NULL, -- NULL = post paytidan
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
  warehouse_id    UUID NOT NULL, -- FK app.warehouses(id)
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
  due_date        DATE NULL,
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
  method          TEXT NOT NULL CHECK (method IN ('cash','card','uzqr','click','payme','uzum','bank')),
  amount          NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  cash_register_id UUID NULL REFERENCES app.cash_registers(id),
  shift_id        UUID NULL REFERENCES app.shifts(id),
  terminal_ref    TEXT NULL,
  provider_tx_id  TEXT NULL,
  card_type       TEXT NULL CHECK (card_type IN ('personal','corporate','social','unknown')), -- sale_payments bilan bir xil qoida
  card_mask       TEXT NULL CHECK (card_mask IS NULL OR card_mask ~ '^[0-9]{4}[*]+[0-9]{4}$'),
  rrn             TEXT NULL,
  qr_type         TEXT NULL CHECK (qr_type IN ('static','dynamic')),
  checkout_ref    UUID NULL REFERENCES app.payment_checkouts(checkout_ref),
  card_entry_mode  TEXT NULL CHECK (card_entry_mode IN ('integrated','manual')), -- qaror #71, sale_payments bilan bir xil qoida
  card_terminal_transaction_id UUID NULL REFERENCES app.card_terminal_transactions(id),
  approval_code    TEXT NULL CHECK (approval_code IS NULL OR approval_code ~ '^[0-9A-Za-z]{1,12}$'),
  card_scheme      TEXT NULL CHECK (card_scheme IN ('uzcard','humo','visa','mastercard','unionpay','mir','other')),
  card_type_source TEXT NULL CHECK (card_type_source IN ('terminal','bin_table')),
  manual_reason    TEXT NULL CHECK (manual_reason IN ('terminal_offline','terminal_error','unknown_result','standalone_terminal')),
  promise_date    DATE NULL, -- qoldiq uchun yangi va'da sanasi (qarz daftari ko'rinishi oxirgisini oladi)
  receipt_seq     INT NULL CHECK (receipt_seq IS NULL OR receipt_seq > 0),
                  -- debt_settlement cheki raqami — qurilma beradi, smena ichida ketma-ket (qaror #12); bank'da NULL
  unallocated_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (unallocated_amount >= 0),
                  -- offline ortiqcha summa (qarzdan katta, FM chekni imzolagan): Kt 6310 olingan bo'nak (13 §2.14, qaror #67)
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
  -- bank — kassasiz, fiskal cheksiz (faqat back-office POST /debt-payments); qolgan usullar — faqat POS
  -- debt_payment.created voqeasi, ochiq smenali kassa va debt_settlement cheki bilan (qaror #67)
  CHECK ((method = 'bank') = (cash_register_id IS NULL AND shift_id IS NULL AND receipt_seq IS NULL)),
  CHECK (method NOT IN ('click','payme','uzum') OR provider_tx_id IS NOT NULL),
  CHECK (method <> 'uzqr' OR qr_type IS NOT NULL),
  CHECK (method <> 'uzqr' OR qr_type = 'static' OR provider_tx_id IS NOT NULL),
  CHECK (qr_type IS NULL OR method = 'uzqr'),
  -- karta — sale_payments bilan bir xil qoida (qaror #64, #71): manual — rekvizitsiz
  CHECK (method <> 'card' OR terminal_ref IS NULL OR card_entry_mode = 'integrated'),
  CHECK ((method = 'card') = (card_entry_mode IS NOT NULL)),
  CHECK ((card_type IS NULL) = (card_type_source IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'integrated' OR (card_terminal_transaction_id IS NOT NULL
         AND rrn IS NOT NULL AND card_mask IS NOT NULL AND card_type IS NOT NULL AND manual_reason IS NULL)),
  CHECK (card_entry_mode IS DISTINCT FROM 'manual' OR (card_terminal_transaction_id IS NULL AND manual_reason IS NOT NULL
         AND card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL AND card_scheme IS NULL)),
  CHECK (method = 'card' OR (card_type IS NULL AND card_mask IS NULL AND rrn IS NULL AND approval_code IS NULL
         AND card_scheme IS NULL AND manual_reason IS NULL AND card_terminal_transaction_id IS NULL)),
  CHECK (unallocated_amount <= amount)
);
CREATE UNIQUE INDEX uq_debt_payments_card_tx ON app.debt_payments (card_terminal_transaction_id)
  WHERE card_terminal_transaction_id IS NOT NULL;

CREATE TABLE app.debt_payment_allocations (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  debt_payment_id UUID NOT NULL REFERENCES app.debt_payments(id),
  target_doc_type TEXT NOT NULL CHECK (target_doc_type IN ('sales','debt_openings','debt_writeoffs')),
                  -- polimorfik; 'debt_writeoffs' — ilgari hisobdan chiqarilgan qarz qaytdi → Kt 9390, debt_moves yozilmaydi (13 §2.14)
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
  reason          TEXT NOT NULL, -- majburiy (18-api-kassa.md §12.5)
  account_choice  TEXT NOT NULL DEFAULT '9430' CHECK (account_choice IN ('9430','4910')), -- 13-provodka-qoidalari.md §2.15 "9430 standart"
  tax_writeoff_basis TEXT NULL CHECK (tax_writeoff_basis IN ('court','bankruptcy','liquidation','death','limitation','none')),
                  -- SK 313-modda asosi (Buxgalter belgilaydi, faqat hisobotga chiqadi)
  approved_by     UUID NULL REFERENCES app.users(id), -- faqat Egasi; qoralama tasdiqsiz yaratiladi
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
  CHECK (status <> 'posted' OR approved_by IS NOT NULL)
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

CREATE TABLE app.supplier_payment_allocations (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  supplier_payment_id UUID NOT NULL REFERENCES app.supplier_payments(id),
  target_doc_type    TEXT NOT NULL CHECK (target_doc_type IN ('goods_receipts','debt_openings')),
                     -- amount − Σallocations = avans (4310, qaror #47; 13 §2.16)
  target_doc_id      UUID NOT NULL,
  amount             NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.expense_categories (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  code        TEXT NULL, -- seed toifa kodi (13 §2.17: 'rent_store', 'payroll_admin', 'tax_payment', ...); foydalanuvchi toifasida NULL
  name        TEXT NOT NULL,
  default_account TEXT NOT NULL DEFAULT '9430' CHECK (default_account IN ('9410','9420','9430','6410')),
              -- Dt hisobi (13 §2.17); '6410' — faqat byudjetga soliq to'lovi (expenses.tax_type majburiy)
  source_ref  TEXT NULL, -- normativ asos ('VMQ-54 2.1.2.3', 'S1 §410')
  is_system   BOOLEAN NOT NULL DEFAULT false,
  archived_at TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  version     INT NOT NULL DEFAULT 1, -- 20-api-moliya-admin.md #47 PATCH version talab qiladi
  UNIQUE (tenant_id, name)
);
CREATE UNIQUE INDEX uq_expense_categories_code ON app.expense_categories (tenant_id, code) WHERE code IS NOT NULL;

-- period 'month'/'quarter'/'year' qiymatlarini oladi (20-api-moliya-admin.md bilan mos).
CREATE TABLE app.recurring_expenses (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  category_id       UUID NOT NULL REFERENCES app.expense_categories(id),
  name              TEXT NULL, -- bo'sh bo'lsa UI toifa nomini ko'rsatadi
  amount            NUMERIC(18,2) NOT NULL CHECK (amount > 0),
  period            TEXT NOT NULL CHECK (period IN ('month','quarter','year')),
  day_of_month      INT  NOT NULL CHECK (day_of_month BETWEEN 1 AND 28),
  source            TEXT NOT NULL CHECK (source IN ('cash','bank','card')),
  cash_register_id  UUID NULL REFERENCES app.cash_registers(id),
  next_due_date     DATE NOT NULL,
  last_triggered_at TIMESTAMPTZ NULL,
  is_active         BOOLEAN NOT NULL DEFAULT true,
  created_by        UUID NOT NULL REFERENCES app.users(id),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  version           INT NOT NULL DEFAULT 1,
  CHECK (source <> 'cash' OR cash_register_id IS NOT NULL)
);
CREATE INDEX idx_recurring_expenses_due ON app.recurring_expenses (tenant_id, next_due_date) WHERE is_active;

CREATE TABLE app.attachments (
  id            UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id     UUID NOT NULL REFERENCES app.tenants(id),
  s3_key        TEXT NOT NULL,
  content_type  TEXT NOT NULL, -- 17-api-umumiy.md §12 tur tekshiruvi (415) va signed URL Content-Type uchun
  original_name TEXT NULL,
  sha256        TEXT NULL,
  kind          TEXT NOT NULL CHECK (kind IN ('expense_receipt','ocr_source','state_report','import','export',
                  'label_pdf','billing_invoice','einvoice','onec_diagnostics','other')),
                  -- onec_diagnostics — 1C agenti diagnostika paketi (33-1c-integratsiya.md A-07)
  size_bytes    BIGINT NOT NULL CHECK (size_bytes >= 0),
  uploaded_by   UUID NOT NULL REFERENCES app.users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- billing_payments.invoice_attachment_id shu yerda FK bilan bog'lanadi (attachments jadvali yuqorida yaratilgan):
ALTER TABLE app.billing_payments ADD CONSTRAINT fk_bp_invoice_attachment FOREIGN KEY (invoice_attachment_id) REFERENCES app.attachments(id);

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
  tax_type          TEXT NULL CHECK (tax_type IN ('vat','turnover','pit','social','property','land','other')),
                    -- toifa default_account='6410' (soliq to'lovi) bo'lsa majburiy (ilova tekshiradi) → ledger analytics.tax_type
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
  counterparty_id UUID NULL REFERENCES app.counterparties(id),
                  -- owner_withdrawal: ta'sischi (counterparties.is_founder) — legal_form ≠ sole_proprietor bo'lsa majburiy (ilova), Dt 4890 analitikasi;
                  -- other: account 6310/4010 da majburiy
  account         TEXT NULL CHECK (account IS NULL OR account IN ('9430','9390','6310','4010','4730')),
                  -- faqat reason='other' (Buxgalter/Egasi tanlaydi): out → Dt account / Kt 5010 (standart 9430);
                  -- in → Dt 5010 / Kt account (standart 9390) — 13 §2.18
  employee_id     UUID NULL REFERENCES app.users(id), -- account='4730' (xodim bilan hisob-kitob) da majburiy
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
  CHECK (reason IN ('owner_withdrawal','other') OR counterparty_id IS NULL),
  CHECK (reason = 'other' OR account IS NULL),
  -- reason↔direction juftligi: collection/owner_withdrawal → out, deposit → in, other → ikkalasi
  CHECK ((reason IN ('collection','owner_withdrawal') AND direction = 'out') OR (reason = 'deposit' AND direction = 'in') OR reason = 'other'),
  CHECK (account IS DISTINCT FROM '4730' OR employee_id IS NOT NULL),
  CHECK (account IS NULL OR account NOT IN ('6310','4010') OR counterparty_id IS NOT NULL)
);

-- bank ko'chirmasi importi (POST /bank-settlements/imports, 1CClientBankExchange .txt) — sinxron; natija
-- bank_settlements(source='statement_import', status='draft') qoralamalari, hech narsa avtomatik post qilinmaydi
CREATE TABLE app.bank_statement_imports (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  branch_id          UUID NULL REFERENCES app.branches(id), -- so'rovdagi standart filial
  attachment_id      UUID NOT NULL REFERENCES app.attachments(id), -- attachments.kind='import'
  file_sha256        TEXT NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
  format             TEXT NOT NULL DEFAULT '1c_client_bank_exchange' CHECK (format IN ('1c_client_bank_exchange')),
  account            TEXT NULL,             -- СекцияРасчСчет.РасчСчет
  period_from        DATE NULL,
  period_to          DATE NULL,
  status             TEXT NOT NULL CHECK (status IN ('parsed','failed')),
  rows_total         INT NOT NULL DEFAULT 0,
  drafts_created     INT NOT NULL DEFAULT 0,
  duplicates         INT NOT NULL DEFAULT 0, -- takror qatorlar (bank_ref + doc_date + summa bo'yicha)
  ignored_outgoing   INT NOT NULL DEFAULT 0,
  unmatched_lines    JSONB NOT NULL DEFAULT '[]',
  error_code         TEXT NULL,
  parsed_at          TIMESTAMPTZ NULL,
  created_by         UUID NOT NULL REFERENCES app.users(id),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, file_sha256)            -- BANK_IMPORT_DUPLICATE
);

-- bank tushumi tasdig'i (qaror #42): 5710 (yo'ldagi pul) → 5110 (bank) o'tkazmasi va komissiya,
-- 13-provodka-qoidalari.md §2.18a. Faqat back-office (sync voqeasi yo'q), doc_sequences kodi 'BT'.
CREATE TABLE app.bank_settlements (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  number            TEXT NULL,
  temp_number       TEXT NULL,
  doc_date          DATE NOT NULL, -- bank hisobiga tushgan sana (provodka sanasi)
  status            TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  source            TEXT NOT NULL CHECK (source IN ('manual','statement_import')) DEFAULT 'manual',
  method            TEXT NOT NULL CHECK (method IN ('card','uzqr','click','payme','uzum','collection')),
  settled_from      DATE NOT NULL, -- qamralgan tranzit tushumlar oralig'i
  settled_to        DATE NOT NULL,
  gross_amount      NUMERIC(18,2) NOT NULL CHECK (gross_amount > 0), -- 5710 dan yopiladigan summa
  commission_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (commission_amount >= 0),
                    -- Dt hisobi: card/uzqr → 9430; click/payme/uzum → settings.payment_org_commission_account; collection → 9410
  variance_amount   NUMERIC(18,2) NOT NULL DEFAULT 0, -- faqat collection: <0 inkassa kamomadi (Dt 5910), >0 ortiqcha (Kt 9390)
  net_amount        NUMERIC(18,2) GENERATED ALWAYS AS (gross_amount - commission_amount + variance_amount) STORED, -- Dt 5110
  bank_ref          TEXT NULL, -- bank ko'chirmasi / to'lov topshirig'i raqami
  statement_import_id UUID NULL REFERENCES app.bank_statement_imports(id), -- source='statement_import' da majburiy
  attachment_id     UUID NULL REFERENCES app.attachments(id), -- ko'chirma fayli (attachments.kind='import')
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
  CHECK (settled_from <= settled_to),
  CHECK (commission_amount < gross_amount),
  CHECK (method = 'collection' OR variance_amount = 0),
  CHECK ((source = 'statement_import') = (statement_import_id IS NOT NULL)),
  CHECK (gross_amount - commission_amount + variance_amount > 0)
);
CREATE INDEX idx_bank_settlements_branch_date ON app.bank_settlements (tenant_id, branch_id, doc_date);

-- Terminal settlement'i («сверка итогов», kunni yopish; qaror #71): smena yopilishida POS/agent settlement()
-- chaqiradi (POS yopiq bo'lsa — agent vazifasi card.settlement). Terminal jamlari bizning integrated tranzaksiyalar
-- jami (expected_*) bilan solishtiriladi; farq — status='mismatch' + BO-14 ogohlantirishi. Bank ko'chirmasi
-- (bank_settlements, method='card') shu partiyaga bank_settlement_id orqali bog'lanadi (13 §2.18a). Provodka yo'q.
CREATE TABLE app.card_terminal_settlements (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  branch_id         UUID NOT NULL REFERENCES app.branches(id),
  card_terminal_id  UUID NOT NULL REFERENCES app.card_terminals(id),
  shift_id          UUID NULL REFERENCES app.shifts(id),
  batch_no          TEXT NULL,                     -- terminal partiya raqami
  business_date     DATE NOT NULL,
  settled_at        TIMESTAMPTZ NOT NULL,          -- terminal vaqti
  purchase_count    INT NOT NULL DEFAULT 0 CHECK (purchase_count >= 0),
  purchase_total    NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (purchase_total >= 0),
  refund_count      INT NOT NULL DEFAULT 0 CHECK (refund_count >= 0),
  refund_total      NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (refund_total >= 0),
  net_total         NUMERIC(18,2) GENERATED ALWAYS AS (purchase_total - refund_total) STORED,
  expected_count    INT NOT NULL DEFAULT 0,        -- server: shu terminal partiyasidagi approved purchase soni
  expected_total    NUMERIC(18,2) NOT NULL DEFAULT 0, -- server: Σ approved purchase − Σ approved refund
  variance          NUMERIC(18,2) GENERATED ALWAYS AS (purchase_total - refund_total - expected_total) STORED,
  status            TEXT NOT NULL CHECK (status IN ('matched','mismatch','failed')),
  bank_settlement_id UUID NULL REFERENCES app.bank_settlements(id), -- bank tushumi tasdig'i bilan moslashtirilgach
  terminal_response JSONB NOT NULL DEFAULT '{}',
  client_event_id   UUID NULL,
  device_id         UUID NULL REFERENCES app.devices(id),
  created_by        UUID NULL REFERENCES app.users(id), -- NULL — agent vazifasi (card.settlement)
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, client_event_id),
  CHECK (status <> 'matched' OR (purchase_total - refund_total) = expected_total)
);
CREATE UNIQUE INDEX uq_cts_batch ON app.card_terminal_settlements (card_terminal_id, batch_no) WHERE batch_no IS NOT NULL;
CREATE INDEX idx_cts_terminal_date ON app.card_terminal_settlements (tenant_id, card_terminal_id, business_date);
CREATE INDEX idx_cts_unmatched_bank ON app.card_terminal_settlements (tenant_id, business_date)
  WHERE bank_settlement_id IS NULL AND status <> 'failed';
ALTER TABLE app.card_terminal_transactions ADD CONSTRAINT fk_ctt_settlement
  FOREIGN KEY (settlement_id) REFERENCES app.card_terminal_settlements(id);

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

-- soliq davr hisob-kitobi (13-provodka-qoidalari.md §2.26, §4.3), doc_sequences kodi 'ST'. Faqat back-office.
-- vat_offset: Dt 6410 / Kt 4410 — (tenant, davr) bo'yicha, vat_moves tenant bo'yicha yig'iladi (qaror #31 — 1 tenant = 1 STIR);
-- branch_id = tenantning is_default filiali (server yozadi). turnover_tax: Dt expense_account / Kt 6410 —
-- (filial, davr) bo'yicha, branch_id majburiy (SK 468-modda 2-qism).
CREATE TABLE app.tax_settlements (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  branch_id       UUID NOT NULL REFERENCES app.branches(id),
  number          TEXT NULL,
  temp_number     TEXT NULL,
  doc_date        DATE NOT NULL, -- odatda davr oxirgi kuni (provodka sanasi)
  status          TEXT NOT NULL CHECK (status IN ('draft','posted','cancelled')) DEFAULT 'draft',
  tax_kind        TEXT NOT NULL CHECK (tax_kind IN ('vat_offset','turnover_tax')),
  period          DATE NOT NULL CHECK (extract(day FROM period) = 1),
  base_amount     NUMERIC(18,2) NOT NULL CHECK (base_amount >= 0), -- vat_offset: Σ kiruvchi QQS; turnover_tax: (9020−9040−9050)+9390+8530 (13 §4.3)
  rate            NUMERIC(5,2) NULL CHECK (rate IS NULL OR rate BETWEEN 0 AND 100), -- faqat turnover_tax
  amount          NUMERIC(18,2) NOT NULL CHECK (amount >= 0),
  expense_account TEXT NULL CHECK (expense_account IN ('9430','9820')), -- faqat turnover_tax (settings.turnover_tax_account)
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
  CHECK ((tax_kind = 'turnover_tax') = (rate IS NOT NULL AND expense_account IS NOT NULL))
);
-- bitta (tenant, davr) uchun bitta faol vat_offset; bitta (filial, davr) uchun bitta faol turnover_tax
CREATE UNIQUE INDEX uq_tax_settlements_vat_offset ON app.tax_settlements (tenant_id, period)
  WHERE tax_kind = 'vat_offset' AND status <> 'cancelled';
CREATE UNIQUE INDEX uq_tax_settlements_turnover ON app.tax_settlements (tenant_id, branch_id, period)
  WHERE tax_kind = 'turnover_tax' AND status <> 'cancelled';
```

### 2.7 Registrlar

`stock_moves`, `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves` — **haqiqiy append-only** (3-bo'limda `REVOKE`+trigger bilan mahkamlanadi). `stock_lots`, `avg_costs`, `stock_balances`, `debt_balances` — "balans/ishchi" jadvallar: qiymatlari shu registrlardan hisoblanadi, lekin qatorlari FIFO/AVECO qulfi ostida **UPDATE** qilinadi (aniqlashtirish #2 — 11-model bu jadvallarni "Registrlar" sarlavhasi ostida bersa ham, `stock_lots.qty_left` jismonan mutatsiya qilinadi, `23-backend-arxitekturasi.md` §2.1).

```sql
CREATE TABLE app.stock_moves (
  id            UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id     UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id  UUID NOT NULL REFERENCES app.warehouses(id),
  product_id    UUID NOT NULL REFERENCES app.products(id),
  lot_id        UUID NULL, -- FK pastda (stock_lots yaratilgandan keyin)
  qty           NUMERIC(18,3) NOT NULL, -- ishorali: kirim +, chiqim -
  cost_amount   NUMERIC(18,2) NOT NULL DEFAULT 0,
  doc_type      TEXT NOT NULL,
  doc_id        UUID NOT NULL,
  line_id       UUID NULL,
  reversal_of_id UUID NULL REFERENCES app.stock_moves(id),
  moved_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                -- hujjat biznes vaqti: POS voqeasida effective_created_at (16 §8), back-office hujjatda posted_at;
                -- DEFAULT now() faqat zaxira
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_stock_moves_wh_prod ON app.stock_moves (tenant_id, warehouse_id, product_id, moved_at);
CREATE INDEX idx_stock_moves_doc ON app.stock_moves (tenant_id, doc_type, doc_id);

CREATE TABLE app.stock_lots (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id    UUID NOT NULL REFERENCES app.warehouses(id),
  product_id      UUID NOT NULL REFERENCES app.products(id),
  receipt_line_id UUID NULL REFERENCES app.receipt_lines(id), -- faqat source_doc_type='goods_receipt'
  source_doc_type TEXT NOT NULL CHECK (source_doc_type IN ('goods_receipts','stock_openings','transfers','stock_counts')),
                  -- aniqlashtirish #3; stock_counts — inventarizatsiya ortiqchasi partiyasi (13 §2.11)
  source_doc_id   UUID NOT NULL,
  source_line_id  UUID NOT NULL,
  received_at     TIMESTAMPTZ NOT NULL,
  qty_in          NUMERIC(18,3) NOT NULL CHECK (qty_in >= 0),
  qty_left        NUMERIC(18,3) NOT NULL CHECK (qty_left >= 0),
  unit_cost       NUMERIC(18,4) NOT NULL CHECK (unit_cost >= 0),
  blocked_qty     NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (blocked_qty >= 0 AND blocked_qty <= qty_left),
                  -- qaytarilgan muddati o'tgan tovar (restock=false, qaror #48): sotuvga chiqmaydi; write_offs
                  -- (expired_return) post'ida blocked_qty va qty_left birga kamayadi (13 §2.5)
  expiry_date     DATE NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- FIFO: ORDER BY received_at, id; sotuvga ochiq miqdor — qty_left − blocked_qty (13 §3.1)
CREATE INDEX idx_stock_lots_fifo ON app.stock_lots (tenant_id, warehouse_id, product_id, received_at, id)
  WHERE qty_left > blocked_qty;

ALTER TABLE app.stock_moves ADD CONSTRAINT fk_sm_lot FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);
ALTER TABLE app.supplier_return_lines ADD CONSTRAINT fk_srl_lot FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);
-- transfer_lines'da lot_id ustuni yo'q (lot_allocations JSONB ishlatiladi) — shuning uchun fk_tl_lot yo'q
ALTER TABLE app.write_off_lines       ADD CONSTRAINT fk_wol_lot FOREIGN KEY (lot_id) REFERENCES app.stock_lots(id);

CREATE TABLE app.avg_costs (
  tenant_id    UUID NOT NULL REFERENCES app.tenants(id),
  warehouse_id UUID NOT NULL REFERENCES app.warehouses(id),
  product_id   UUID NOT NULL REFERENCES app.products(id),
  avg_cost     NUMERIC(18,4) NOT NULL DEFAULT 0,
  qty          NUMERIC(18,3) NOT NULL DEFAULT 0,
  total_value  NUMERIC(18,2) NOT NULL DEFAULT 0, -- AVECO qiymat yig'indisi: avg = total_value / qty; qty ≤ 0 → 0 (13 §3.1)
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
-- manfiy qoldiqlarni tezkor topish (offline overselling, `16` §5)
CREATE INDEX idx_stock_balances_negative ON app.stock_balances (tenant_id, warehouse_id, product_id) WHERE qty < 0;

CREATE TABLE app.debt_moves (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  direction       TEXT NOT NULL CHECK (direction IN ('receivable','payable')),
  amount          NUMERIC(18,2) NOT NULL, -- ishorali
  due_date        DATE NULL,
  limit_exceeded  BOOLEAN NOT NULL DEFAULT false, -- offline nasiya limitdan oshgan qator
  doc_type        TEXT NOT NULL,
  doc_id          UUID NOT NULL,
  reversal_of_id  UUID NULL REFERENCES app.debt_moves(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_debt_moves_cp ON app.debt_moves (tenant_id, counterparty_id, direction, created_at);
CREATE INDEX idx_debt_moves_due ON app.debt_moves (tenant_id, due_date) WHERE direction = 'receivable';
CREATE INDEX idx_debt_moves_limit_exceeded ON app.debt_moves (tenant_id) WHERE limit_exceeded;

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
  bank_account_id  UUID NULL, -- MVP: doim NULL — yagona yashirin bank hisobi 5110; ko'p bank hisobi (jadval) — backlog
  shift_id         UUID NULL REFERENCES app.shifts(id),
  amount           NUMERIC(18,2) NOT NULL, -- ishorali
  method           TEXT NOT NULL CHECK (method IN ('cash','card','uzqr','click','payme','uzum','bank')),
  doc_type         TEXT NOT NULL,
  doc_id           UUID NOT NULL,
  reversal_of_id   UUID NULL REFERENCES app.cash_moves(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (method <> 'cash' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL))
);
CREATE INDEX idx_cash_moves_shift ON app.cash_moves (shift_id) WHERE shift_id IS NOT NULL;

CREATE TABLE app.ledger_entries (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  entry_date     DATE NOT NULL,
  branch_id      UUID NULL REFERENCES app.branches(id), -- filial bo'yicha hisobot uchun indeksli ustun
  account_dt     TEXT NOT NULL CHECK (account_dt ~ '^[0-9]{4}$'), -- hisob kodi 13-provodka-qoidalari.md §1 ro'yxatidan (0000, 2910/2920, 5710 …)
  account_kt     TEXT NOT NULL CHECK (account_kt ~ '^[0-9]{4}$'),
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
CREATE INDEX idx_ledger_entries_branch ON app.ledger_entries (tenant_id, branch_id, entry_date);

CREATE TABLE app.vat_moves (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  period         DATE NOT NULL, -- oyning 1-sanasi
  kind           TEXT NOT NULL CHECK (kind IN ('output','input')),
  base_amount    NUMERIC(18,2) NOT NULL,
  vat_amount     NUMERIC(18,2) NOT NULL,
  doc_type       TEXT NOT NULL,
  doc_id         UUID NOT NULL,
  einvoice_id    UUID NULL, -- FK pastda (einvoices yaratilgandan keyin)
  reversal_of_id UUID NULL REFERENCES app.vat_moves(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vat_moves_period ON app.vat_moves (tenant_id, period, kind);
```

**Balans jadvallarining upsert naqshi** (posting xizmati ichida, `23-backend-arxitekturasi.md` §2.1 qulfi ostida):

```sql
-- namuna: posting xizmati ichidagi so'rov, migratsiya emas
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
-- kind='z_report' — smena yopilganda Z-hisobot shu jadvalga yoziladi (sale_id/return_id/receipt_seq hammasi
-- NULL, raqami = shifts.shift_no). kind='debt_settlement' — qarz to'lovida chiqariladigan chek, debt_payment_id
-- orqali bog'lanadi; har doim cash_register_id, shift_id, receipt_seq bilan; bank o'tkazmasi orqali qarz to'lovida
-- chek yaratilmaydi (qaror #67). Lokal ko'prik rejimida FM natijasi POS voqeasining fiscal_result'idan yoziladi
-- (qaror #68); receipt_seq to'qnashuvida server qayta raqamlaydi, qurilma qiymati payload.device_receipt_seq da. Chek
-- matni/payload ikki tilda chiqariladi (o'zbek + ixtiyoriy rus — `products.name_ru`, qaror #29).
-- kind='credit_sale' — nasiya sotuvda "kredit" turidagi chek (QR va fiskal belgisiz, VMQ-943 1-ilova 7-band),
-- faqat tenants.settings.fiscal_policy.credit_sale_receipt='credit_type' bo'lsa yaratiladi.
-- payload.items[] har qatorda: mxik (17 raqam), package_code, katalog o'lchov birligi, marking_codes[] (GS bilan aynan).
-- 48 soatlik blok (qaror #43): shu kassada ofd_acked_at IS NULL bo'lgan eng eski fiskal chek created_at'idan
-- 48 soat o'tsa yangi fiskal chek yaratilmaydi (FISCAL_OFFLINE_48H_BLOCKED) — idx_fiscal_receipts_unacked.
CREATE TABLE app.fiscal_receipts (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  kind             TEXT NOT NULL CHECK (kind IN ('sale','return','z_report','debt_settlement','credit_sale')),
  sale_id          UUID NULL REFERENCES app.sales(id),
  return_id        UUID NULL REFERENCES app.returns(id),
  debt_payment_id  UUID NULL REFERENCES app.debt_payments(id), -- (qaror #30) kind='debt_settlement'da majburiy
  cash_register_id UUID NULL REFERENCES app.cash_registers(id), -- barcha turlarda majburiy (CHECK pastda)
  shift_id         UUID NULL REFERENCES app.shifts(id), -- xuddi shunday
  receipt_seq      INT  NULL, -- qurilma beradi (qaror #12); faqat z_report'da NULL
  fm_terminal_id   TEXT NULL, -- fiskal modul (FM) seriya raqami — FiscalResult.terminal_id
  fm_receipt_seq   BIGINT NULL, -- FM bergan chek raqami (OFD ReceiptSeq); receipt_seq'dan alohida
  fiscal_at        TIMESTAMPTZ NULL, -- FM imzolagan vaqt (FiscalResult.fiscal_datetime)
  payload          JSONB NOT NULL,
  fiscal_sign      TEXT NULL,
  qr_url           TEXT NULL,
  payment_form     TEXT NULL CHECK (payment_form IN ('cash','card','qr','mixed')),
                   -- chek "to'lov shakli" rekviziti: cash; card; uzqr/click/payme/uzum → qr; bir nechta shakl → mixed. z_report'da NULL
  delivery         TEXT NOT NULL DEFAULT 'printed' CHECK (delivery IN ('printed','electronic')),
  delivery_reason  TEXT NULL, -- electronic bo'lsa majburiy (printer nosoz / xaridor so'radi), audit
  sent_at          TIMESTAMPTZ NULL,
  ofd_acked_at     TIMESTAMPTZ NULL, -- OFD tasdig'i olingan vaqt; NULL — 48 soatlik hisoblagichga kiradi
  offline_since    TIMESTAMPTZ NULL,
  status           TEXT NOT NULL CHECK (status IN ('pending','sent','fiscalized','failed')) DEFAULT 'pending',
  attempts         INT NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (delivery = 'printed' OR delivery_reason IS NOT NULL),
  CHECK (kind = 'z_report' OR payment_form IS NOT NULL),
  CHECK (
       (kind IN ('sale','credit_sale') AND sale_id IS NOT NULL AND return_id IS NULL AND debt_payment_id IS NULL AND receipt_seq IS NOT NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)
    OR (kind = 'return'          AND return_id IS NOT NULL AND sale_id IS NULL AND debt_payment_id IS NULL AND receipt_seq IS NOT NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)
    OR (kind = 'z_report'        AND sale_id IS NULL AND return_id IS NULL AND debt_payment_id IS NULL AND receipt_seq IS NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)
    OR (kind = 'debt_settlement' AND debt_payment_id IS NOT NULL AND sale_id IS NULL AND return_id IS NULL AND receipt_seq IS NOT NULL AND cash_register_id IS NOT NULL AND shift_id IS NOT NULL)
  ),
  UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)
);
CREATE UNIQUE INDEX uq_fiscal_z_per_shift ON app.fiscal_receipts (shift_id) WHERE kind = 'z_report';
CREATE INDEX idx_fiscal_receipts_pending ON app.fiscal_receipts (tenant_id) WHERE status IN ('pending','failed');
CREATE INDEX idx_fiscal_receipts_unacked ON app.fiscal_receipts (cash_register_id, created_at)
  WHERE ofd_acked_at IS NULL AND kind <> 'z_report';
CREATE UNIQUE INDEX uq_fiscal_fm_seq ON app.fiscal_receipts (tenant_id, fm_terminal_id, fm_receipt_seq)
  WHERE fm_receipt_seq IS NOT NULL;

CREATE TABLE app.marking_codes (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  code        TEXT NOT NULL, -- DataMatrix
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
-- SalePostingService sale_lines'dan oldin, shu tranzaksiyada INSERT INTO marking_codes ...
-- ON CONFLICT (tenant_id, code) DO UPDATE SET status=..., last_doc_id=... bajaradi
-- (status='pending_verification'; chek OFD tasdig'ini olgach — fiscal_receipts.ofd_acked_at — 'sold', qaror #62,
-- 18 §4.2, 16 §7); FK DEFERRABLE shu tartibni kafolatlaydi.

CREATE TABLE app.einvoices (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  direction       TEXT NOT NULL CHECK (direction IN ('in','out')),
  operator        TEXT NOT NULL CHECK (operator IN ('didox','faktura')),
  operator_doc_id TEXT NULL,
  counterparty_id UUID NOT NULL REFERENCES app.counterparties(id),
  related_doc_type TEXT NULL,
  related_doc_id  UUID NULL,
  status          TEXT NOT NULL CHECK (status IN ('draft','received','signed','sent','accepted','rejected','cancelled')),
  number          TEXT NULL, -- operator/faktura raqami
  doc_date        DATE NULL,
  total_amount    NUMERIC(18,2) NULL,
  vat_amount      NUMERIC(18,2) NULL,
  signed_by       UUID NULL REFERENCES app.users(id),
  risk_flag       TEXT NOT NULL DEFAULT 'unknown' CHECK (risk_flag IN ('green','red','unknown')),
                  -- VM 830 xavf darajasi (Didox `scoring`; Faktura.uz — unknown); unknown — QQS krediti qizil kabi
                  -- to'lovgacha kechiktiriladi (13 §2.8), Buxgalter BO-15'da qo'lda belgilaydi
  factura_type    TEXT NOT NULL DEFAULT 'standard' CHECK (factura_type IN ('standard','additional','corrected')),
  related_einvoice_id UUID NULL REFERENCES app.einvoices(id), -- additional/corrected — asl EHF
  signed_at       TIMESTAMPTZ NULL,
  payload         JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (related_doc_type IS NULL OR related_doc_type IN ('sales','goods_receipts','supplier_returns')),
  CHECK (factura_type = 'standard' OR related_einvoice_id IS NOT NULL)
);
-- 13-provodka-qoidalari.md §2.22 cheklovi: bitta chekka bitta faol chiquvchi faktura
CREATE UNIQUE INDEX uq_einvoice_out_per_doc ON app.einvoices (tenant_id, related_doc_type, related_doc_id)
  WHERE direction = 'out' AND related_doc_id IS NOT NULL AND status <> 'cancelled';
CREATE UNIQUE INDEX uq_einvoice_operator_doc ON app.einvoices (tenant_id, operator, operator_doc_id)
  WHERE operator_doc_id IS NOT NULL;

ALTER TABLE app.vat_moves ADD CONSTRAINT fk_vm_einvoice FOREIGN KEY (einvoice_id) REFERENCES app.einvoices(id);
-- goods_receipts.einvoice_id shu yerda FK bilan bog'lanadi (einvoices jadvali yuqorida yaratilgan):
ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_einvoice FOREIGN KEY (einvoice_id) REFERENCES app.einvoices(id);
CREATE UNIQUE INDEX uq_gr_einvoice_active ON app.goods_receipts (tenant_id, einvoice_id)
  WHERE einvoice_id IS NOT NULL AND status <> 'cancelled';

-- E-ishonchnoma (BO-04 → E-IMZO → operator, 19 §8a). Holatlar: draft → pending_signature → sending → sent →
-- accepted | rejected; sending → failed → sending (qayta imzo/yuborish); draft | pending_signature → cancelled.
-- Yuborish — outbox_jobs(kind='poa_send'), EInvoicePort.send_power_of_attorney.
CREATE TABLE app.powers_of_attorney (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  branch_id        UUID NOT NULL REFERENCES app.branches(id),
  purchase_order_id UUID NULL REFERENCES app.purchase_orders(id),
  supplier_id      UUID NOT NULL REFERENCES app.counterparties(id),
  employee_user_id UUID NOT NULL REFERENCES app.users(id),   -- ishonchli shaxs (odatda Omborchi)
  doc_date         DATE NOT NULL,
  valid_from       DATE NOT NULL,
  valid_to         DATE NOT NULL,
  number           TEXT NULL,                                -- operator bergan raqam
  operator_doc_id  TEXT NULL,
  status           TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_signature','sending','sent',
                     'accepted','rejected','cancelled','failed')),
  last_error       TEXT NULL,
  signed_at        TIMESTAMPTZ NULL,
  sent_at          TIMESTAMPTZ NULL,
  responded_at     TIMESTAMPTZ NULL,
  reject_reason    TEXT NULL,
  created_by       UUID NOT NULL REFERENCES app.users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  version          INT NOT NULL DEFAULT 1,
  CHECK (valid_to >= valid_from)
);
CREATE INDEX idx_poa_po ON app.powers_of_attorney (tenant_id, purchase_order_id);
ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_poa FOREIGN KEY (poa_id) REFERENCES app.powers_of_attorney(id);

-- e-TTN: kiruvchi xaridda EHF bilan birlashtirilgan (einvoice_id); ichki ko'chirishda ("Ombordan omborga")
-- yozuvchi — transfer `post` (transfer_id; qaror #63, 19 §13).
CREATE TABLE app.ettn_documents (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  einvoice_id     UUID NULL REFERENCES app.einvoices(id),
  transfer_id     UUID NULL REFERENCES app.transfers(id),
  transport_type  TEXT NOT NULL CHECK (transport_type IN ('warehouse_to_warehouse','seller_to_buyer','other')),
  direction       TEXT NOT NULL CHECK (direction IN ('in','out')),
  status          TEXT NOT NULL CHECK (status IN ('pending_signature','sending','registered','received','accepted',
                    'rejected','cancelled','failed')),
                  -- chiquvchi: pending_signature → sending → registered → accepted/rejected; sending → failed → sending
                  -- (qayta imzo/yuborish); kiruvchi: received → accepted/rejected; cancelled
  counterparty_id UUID NULL REFERENCES app.counterparties(id), -- kiruvchi: jo'natuvchi; chiquvchi (seller_to_buyer): oluvchi
  receipt_id      UUID NULL REFERENCES app.goods_receipts(id), -- kiruvchi e-TTN bog'langan kirim
  doc_date        DATE NULL,
  payload         JSONB NOT NULL DEFAULT '{}',
  signed_at       TIMESTAMPTZ NULL,
  last_error      TEXT NULL,
  operator_doc_id TEXT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (direction = 'in' OR einvoice_id IS NOT NULL OR transfer_id IS NOT NULL),
  CHECK (transport_type <> 'warehouse_to_warehouse' OR transfer_id IS NOT NULL)
);

CREATE TABLE app.state_reports (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  tax_type           TEXT NOT NULL CHECK (tax_type IN ('vat','turnover')), -- MVP: QQS va aylanma solig'i (05 §1.3 — mol-mulk/yer/JShDS/ijtimoiy Won't)
  period             DATE NOT NULL,
  published_at       TIMESTAMPTZ NULL,
  deadline_at        TIMESTAMPTZ NULL, -- min(published_at + 5 ish kuni, topshirish muddati) (SK 5-modda 7-qism, 81-modda 6-qism)
  file_attachment_id UUID NULL REFERENCES app.attachments(id),
  status             TEXT NOT NULL CHECK (status IN ('uploaded','compared','match','diff_found','correction_sent','confirmed',
                       'auto_accepted')),
                     -- uploaded → compared → match | diff_found → correction_sent | confirmed | auto_accepted
  state_amount         NUMERIC(18,2) NULL,
  our_amount           NUMERIC(18,2) NULL,
  diff_amount          NUMERIC(18,2) NULL,
  compared_at          TIMESTAMPTZ NULL,
  correction_sent_at   TIMESTAMPTZ NULL,
  correction_comment   TEXT NULL, -- my.soliq.uz kabinetida kiritilgan tuzatish izohi (tizim faqat qayd etadi, imzosiz)
  correction_portal_ref TEXT NULL, -- kabinetdagi tuzatish raqami (ixtiyoriy)
  confirmed_at         TIMESTAMPTZ NULL,
  confirmed_by         UUID NULL REFERENCES app.users(id),
  uploaded_by          UUID NOT NULL REFERENCES app.users(id),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Tolerantlik — tenants.settings.vat_diff_tolerance_amount

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
-- Tenant darajasidagi integratsiya hisob ma'lumotlari (CRPT, Click/Payme/Uzum, UzQR, Faktura.uz, E-IMZO) —
-- `21-integratsiyalar.md` kirish qismi #7, `20-api-moliya-admin.md` (integratsiya sozlamalari), `27-backlog.md`.
-- `ciphertext` — KEK orqali konvert-shifrlangan (platform.oauth_clients.client_secret_encrypted bilan bir xil
-- naqsh), API hech qachon qaytarmaydi (faqat yozish/almashtirish, `kind` + `rotated_at` ko'rinadi).
-- RLS: oddiy tenant jadvali — 4.2-bo'limdagi `tenant_isolation` siyosati (0026-revizion) qo'llanadi.
CREATE TABLE app.tenant_secrets (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  branch_id   UUID NULL REFERENCES app.branches(id), -- NULL = butun tenant uchun yagona (filialga xos bo'lmagan)
  cash_register_id UUID NULL REFERENCES app.cash_registers(id), -- uzqr: dinamik QR API kaliti har kassa uchun alohida
  kind        TEXT NOT NULL CHECK (kind IN ('faktura_uz','crpt','click','payme','uzum','uzqr','fiscal_partner','eimzo',
                                    'card_terminal_vendor')), -- card_terminal_vendor — CloudTerminalAdapter (qaror #71)
  ciphertext  BYTEA NOT NULL,
  key_version INT NOT NULL,
  rotated_at  TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (tenant_id, branch_id, cash_register_id, kind),
  CHECK (cash_register_id IS NULL OR kind = 'uzqr')
);

CREATE TABLE app.outbox_jobs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  kind            TEXT NOT NULL CHECK (kind IN ('ofd_send','einvoice_send','einvoice_accept','ettn_send',
                     'ettn_accept','poa_send','marking_verify','marking_accept','marking_supplier_return',
                     'marking_writeoff','state_report_reminder','sms','telegram','ai','report_export','label_pdf',
                     'billing_webhook_reconcile')),
                  -- ofd_send — faqat ERP_FISCAL_PROVIDER=partner_cloud rejimida (lokal ko'prikda chekni agent/FM yuboradi)
  payload         JSONB NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('queued','running','done','retry','failed')) DEFAULT 'queued',
  attempts        INT NOT NULL DEFAULT 0,
  next_run_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_error      TEXT NULL,
  idempotency_key TEXT NOT NULL,
  created_by           UUID NULL REFERENCES app.users(id), -- eksport job'ini faqat yaratuvchi/Egasi ko'radi
  progress_pct         SMALLINT NULL CHECK (progress_pct BETWEEN 0 AND 100),
  result_attachment_id UUID NULL REFERENCES app.attachments(id),
  error_code           TEXT NULL, -- 17-api-umumiy.md xato kodlari katalogidan (masalan EXPORT_JOB_FAILED)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);
-- API holati xaritasi: 'retry' → API'da 'running' sifatida ko'rsatiladi
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

-- sinxron istisnolari (16-offline-sync.md §5): offline narx farqi, arxivlangan tovar, manfiy qoldiq, limitdan
-- oshgan nasiya/tasdiq limiti, qarz to'lovi farqlari, yopilgan davrga kech kelgan voqea va h.k. — axborot, voqea
-- rad etilmaydi; BO-14 "Sinxron istisnolari" (qaror #56)
CREATE TABLE app.sync_exceptions (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  device_id       UUID NULL REFERENCES app.devices(id),
  client_event_id UUID NULL,
  kind            TEXT NOT NULL CHECK (kind IN ('price_mismatch','archived_product','stock_negative',
                    'debt_limit_exceeded_offline','approval_limit_exceeded_offline','receipt_seq_conflict',
                    'debt_overpayment_offline','debt_allocation_mismatch','late_in_closed_period','cost_unknown',
                    'count_late_move','card_result_mismatch','card_orphan_transaction')), -- 16 §5 ro'yxati
  doc_type        TEXT NULL,
  doc_id          UUID NULL,
  details         JSONB NOT NULL DEFAULT '{}',
  reviewed_at     TIMESTAMPTZ NULL,
  reviewed_by     UUID NULL REFERENCES app.users(id),
  review_note     TEXT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (reviewed_at IS NULL OR (reviewed_by IS NOT NULL AND review_note IS NOT NULL))
);
CREATE INDEX idx_sync_exceptions_open ON app.sync_exceptions (tenant_id, created_at) WHERE reviewed_at IS NULL;

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
  status     TEXT NOT NULL CHECK (status IN ('uploaded','validating','validated','committing','committed','failed')) DEFAULT 'uploaded',
  total_rows INT NOT NULL DEFAULT 0,
  ok_rows    INT NOT NULL DEFAULT 0,
  errors     JSONB NOT NULL DEFAULT '[]',
  result     JSONB NOT NULL DEFAULT '{}', -- {"created_doc_ids":[...], "created_product_count":n}
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

-- AI hujjat yozmaydi — tasdiqdan keyin qoralama hujjat (goods_receipts/stock_openings) yoki mahsulot kartochkalari
-- (catalog — created_product_ids) yaratiladi. Qaytarish OCR orqali yaratilmaydi (returns faqat POS sync orqali).
CREATE TABLE app.ai_ocr_jobs (
  id                    UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id             UUID NOT NULL REFERENCES app.tenants(id),
  branch_id             UUID NULL REFERENCES app.branches(id),
  created_by            UUID NOT NULL REFERENCES app.users(id),
  attachment_id         UUID NOT NULL REFERENCES app.attachments(id),
  doc_type_hint         TEXT NOT NULL DEFAULT 'purchase' CHECK (doc_type_hint IN ('purchase','catalog')), -- 20-api-moliya-admin.md #73–75
  status                TEXT NOT NULL DEFAULT 'processing'
                          CHECK (status IN ('processing','done','failed','confirmed','expired')),
  fields                JSONB NULL, -- {header:{supplier_name:{value,confidence},...}, lines:[{...}]}
  low_confidence_fields TEXT[] NOT NULL DEFAULT '{}', -- masalan 'lines[0].product_name'
  error_code            TEXT NULL, -- 'OCR_IMAGE_UNREADABLE', 'AI_PROVIDER_UNAVAILABLE'
  ai_request_id         UUID NULL REFERENCES app.ai_requests(id),
  created_doc_type      TEXT NULL CHECK (created_doc_type IN ('goods_receipts','stock_openings')), -- (#75 javobi)
  created_doc_id        UUID NULL,
  created_product_ids   UUID[] NOT NULL DEFAULT '{}', -- catalog tasdig'ida yaratilgan mahsulotlar
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at           TIMESTAMPTZ NULL,
  confirmed_at          TIMESTAMPTZ NULL,
  expires_at            TIMESTAMPTZ NOT NULL, -- created_at + 7 kun (standart, sozlanadi), keyin 'expired' va fields tozalanadi
  CHECK (status <> 'confirmed' OR ((created_doc_id IS NOT NULL OR cardinality(created_product_ids) > 0)
                                   AND confirmed_at IS NOT NULL)),
  CHECK ((created_doc_type IS NULL) = (created_doc_id IS NULL))
);
CREATE INDEX idx_ai_ocr_jobs_expiry ON app.ai_ocr_jobs (expires_at) WHERE status IN ('processing','done');
ALTER TABLE app.goods_receipts ADD CONSTRAINT fk_gr_ocr_job FOREIGN KEY (ai_ocr_job_id) REFERENCES app.ai_ocr_jobs(id);

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

**Hujjat raqami generatori** (aniqlashtirish #12 — 11-model faqat `K-01-2026-000154` namunasini beradi, to'liq `doc_type` kod jadvali ro'yxatlanmagan):

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

`doc_type` kodlari (aniqlashtirish #12): `K`=sales, `V`=returns, `Z`=purchase_orders, `M`=goods_receipts, `MV`=supplier_returns, `P`=transfers, `I`=stock_counts, `L`=write_offs, `C`=price_changes, `OO`=stock_openings, `OD`=debt_openings, `DP`=debt_payments, `DW`=debt_writeoffs, `SP`=supplier_payments, `E`=expenses, `CM`=cash_movements, **`BX`=ledger_adjustments**, **`BT`=bank_settlements** (qaror #42), **`ST`=tax_settlements**. Ro'yxat — standart (qaror #54), yangi kod — append-only seed.

### 2.10 `updated_at` trigger'larini ommaviy ulash

Barcha jadvallar yaratilgandan so'ng, bitta martalik migratsiya qadami:

```sql
-- 0025 updated_at_triggers
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

Bu blok — bitta martalik (0025-revizion). Undan keyingi revizionlar `updated_at`li yangi jadvallarga trigger'ni aniq yozadi. `0028 store_agent` (2.11-bo'lim, Do'kon agenti umumiy registri) — 2 jadval:

```sql
-- 0028 store_agent
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['onec_agents','onec_agent_tasks'] LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON app.%I FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t);
  END LOOP;
END $$;
```

`0029 onec_integration` (2.11-bo'lim, 1C ga xos jadvallar) — 11 jadval:

```sql
-- 0029 onec_integration
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['onec_bases','onec_settings','onec_branch_bindings','onec_catalog_items',
    'onec_mappings','onec_value_mappings','onec_ref_create_requests','onec_export_batches','onec_export_items',
    'onec_object_refs','onec_reconciliations'] LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON app.%I FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t);
  END LOOP;
END $$;
```

`updated_at`siz (faqat INSERT yoki o'zgarmas qator): `onec_task_results`, `auth.onec_device_authorizations` (0028); `onec_metadata_snapshots`, `onec_export_item_sources`, `onec_events`, `onec_agent_logs` (0029).

### 2.11 1C integratsiyasi (`onec_*`)

Do'kon agenti va 1C integratsiya moduli jadvallari — manba `33-1c-integratsiya.md` §5. Jami **19 jadval**: `app` sxemasida 18 ta (`tenant_id NOT NULL`, oddiy `tenant_isolation` RLS) + `auth.onec_device_authorizations` (RFC 8628 device grant; tenant tasdiqqacha noma'lum, shuning uchun `auth` sxemasida, faqat `SECURITY DEFINER` funksiyalar orqali). Ikki Alembic revizion (6.1-bo'lim, qaror #66):

- **`0028 store_agent` (Bosqich 5)** — Do'kon agenti umumiy registri (nomi 33 bilan moslik uchun `onec_` prefiksli): `onec_agents`, `onec_agent_tasks`, `onec_task_results`, `auth.onec_device_authorizations` + `cash_registers.fiscal_agent_id` FK'i (`fk_cr_fiscal_agent`). Agentni ulash, token, imzoli vazifa navbati, fiskal ko'prik/printer xizmat vazifalari shu revizionga tayanadi; `onec_agent_tasks` ning 1C ga ishora qiluvchi ustunlari (`base_id`, `batch_id`, `item_id`, `ref_create_request_id`, `reconciliation_id`) FK'siz yaratiladi.
- **`0029 onec_integration` (Bosqich 7)** — qolgan 15 ta 1C ga xos jadval (`onec_bases` … `onec_agent_logs`), `onec_forbid_namespace_change` trigger'i va kechiktirilgan FK'lar, jumladan `onec_agent_tasks` ga `fk_oat_base`, `fk_oat_batch`, `fk_oat_item`, `fk_oat_ref_create`, `fk_oat_reconciliation`.

Istisno (1.3-bo'limdan): 1C hujjat vaqti (`onec_export_items.doc_time`, `onec_object_refs.onec_date`) — `TIMESTAMP` (zonasiz, Asia/Tashkent mahalliy vaqti — 1C `Дата` shunday saqlaydi). DDL izohlaridagi `§` havolalari — `33-1c-integratsiya.md` bo'limlari («FK §5.21» — shu bo'lim oxiridagi kechiktirilgan FK bloki).

| Jadval | Maqsad | Saqlash muddati |
|---|---|---|
| `onec_agents` | Ulangan Do'kon agentlari (har PK — bitta), `devices` bilan 1:1, imkoniyatlar (`capabilities`) | Doimiy (revoke — holat) |
| `onec_bases` | Agent ulagan 1C bazalari, qulf №1, onboarding natijasi | Doimiy (arxiv — holat) |
| `onec_settings` | Baza bo'yicha rejim, jadval, avto-tasdiq, siyosatlar | Doimiy |
| `onec_branch_bindings` | Filial → baza yo'naltirish | Doimiy (arxiv) |
| `onec_metadata_snapshots` | 1C metadata nusxasi (profil tekshiruvi) | Oxirgi 5 ta nusxa |
| `onec_catalog_items` | 1C ma'lumotnoma elementlari keshi (moslashtirish ustasi uchun) | Baza faol ekan |
| `onec_mappings` | ERP qatori (UUID) ↔ 1C elementi GUID (ref maps) | Doimiy |
| `onec_value_mappings` | ERP qiymati/kaliti ↔ 1C elementi / sanoq qiymati / hisob (value maps) | Doimiy |
| `onec_ref_create_requests` | 1C'da element yaratish takliflari va tasdig'i | 5 yil |
| `onec_export_batches` | Kun eksporti (baza × sana × revision) | 5 yil (qaror #7) |
| `onec_export_items` | Partiyadagi har 1C obyekti (urinish, holat) | 5 yil (`op_spec` — 90 kun) |
| `onec_export_item_sources` | Item ↔ ERP manba hujjatlari | 5 yil |
| `onec_object_refs` | ERP yozgan har 1C obyektining daftari | 5 yil |
| `onec_agent_tasks` | Imzolangan vazifalar navbati (1C va qurilma xizmati), lease | 5 yil (yozish), 30 kun (o'qish va xizmat) |
| `onec_task_results` | Har urinish natijasi (xom) | 5 yil (yozish), 30 kun (o'qish) |
| `onec_reconciliations` | Solishtirish natijalari (partiya jamlari, drift, qoldiq) | 5 yil |
| `onec_events` | Server voqealar lentasi (BO-23 progress, BO-22 jurnal) | 1 yil |
| `onec_agent_logs` | Agent yuborgan maskalangan loglar | 30 kun |
| `auth.onec_device_authorizations` | RFC 8628 device grant holati | 30 kun |

Mavjud jadvallarga bog'liq qismlar: `devices.kind = 'onec_agent'` va `devices.outbox_*` (2.3), `attachments.kind = 'onec_diagnostics'` (2.6), `signing_keys.purpose` `'onec_task'`/`'agent_update'` (2.1), `oauth_clients` qatori `onec-agent` (5.1). `notification_settings.kind` — CHECK'siz `TEXT`; 1C turlari `onec_export_result`, `onec_problems` (33 §13.3).

**`0028 store_agent` jadvallari** (Bosqich 5):

#### `onec_agents`

Do'kon PK'sidagi har agent; `devices` (`kind='onec_agent'`) bilan 1:1. 1C paroli va agentning maxfiy kaliti saqlanmaydi — faqat ochiq kalit. Holatlar: `active` → `revoked` (yakuniy).

```sql
CREATE TABLE app.onec_agents (
  id                      UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id               UUID NOT NULL REFERENCES app.tenants(id),
  device_id               UUID NOT NULL REFERENCES app.devices(id),
  client_id               TEXT NOT NULL,                 -- 'onec-agent:' || id — private_key_jwt iss/sub
  name                    TEXT NOT NULL,                 -- BO'da ko'rinadigan nom (standart = pc_name)
  pc_name                 TEXT NOT NULL,
  machine_hash            TEXT NOT NULL CHECK (machine_hash ~ '^[0-9a-f]{64}$'), -- SHA-256(MachineGuid|user SID) — agent hisoblaydi
  os_version              TEXT NULL,
  agent_version           TEXT NULL,
  worker_bits             SMALLINT[] NOT NULL DEFAULT '{}' CHECK (worker_bits <@ ARRAY[32,64]::smallint[]),
  platforms               JSONB NOT NULL DEFAULT '[]',   -- [{version:"8.3.25.1374", bits:64, progid:"V83.COMConnector", registered:true}]
  public_jwk              JSONB NOT NULL,                -- {"kty":"OKP","crv":"Ed25519","x":"...","kid":"<thumbprint>"}
  public_key_thumbprint   TEXT NOT NULL,                 -- RFC 7638 JWK thumbprint (base64url)
  status                  TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  update_channel          TEXT NOT NULL DEFAULT 'stable' CHECK (update_channel IN ('stable','pilot')),
  capabilities            JSONB NOT NULL DEFAULT '{}',   -- 34 §14.2 sxemasi; A-01 hello'dan yangilanadi
                                                         -- (vazifa faqat capabilities.<oila>.enabled = true bo'lsa navbatga qo'yiladi)
  paired_by               UUID NOT NULL REFERENCES app.users(id),
  paired_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  paired_ip               INET NULL,
  last_hello_at           TIMESTAMPTZ NULL,
  last_poll_at            TIMESTAMPTZ NULL,
  last_ip                 INET NULL,
  machine_hash_changed_at TIMESTAMPTZ NULL,              -- hello'da boshqa machine_hash kelsa (ogohlantirish)
  offline_notified_at     TIMESTAMPTZ NULL,
  revoked_at              TIMESTAMPTZ NULL,
  revoked_by              UUID NULL REFERENCES app.users(id),
  revoke_reason           TEXT NULL CHECK (revoke_reason IN ('user','uninstall','key_compromised','replaced')),
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  version                 INT NOT NULL DEFAULT 1,
  UNIQUE (client_id),
  UNIQUE (device_id),
  CHECK (client_id = 'onec-agent:' || id::text),
  CHECK (status <> 'revoked' OR (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL))
);
CREATE INDEX idx_onec_agents_tenant_status ON app.onec_agents (tenant_id, status);
-- kassa ↔ agent bog'lanishi (lokal fiskal ko'prik, qaror #66); cash_registers.fiscal_agent_id 0002 da FK'siz
ALTER TABLE app.cash_registers ADD CONSTRAINT fk_cr_fiscal_agent FOREIGN KEY (fiscal_agent_id) REFERENCES app.onec_agents(id);
-- karta terminali ↔ agent (adapter='agent_ecr', qaror #71); card_terminals.agent_id 0010 da FK'siz
ALTER TABLE app.card_terminals ADD CONSTRAINT fk_ct_agent FOREIGN KEY (agent_id) REFERENCES app.onec_agents(id);
```

#### `onec_agent_tasks`

Agent faqat shu jadvaldan vazifa oladi (pull, lease, imzo). Holat mashinasi — 33 §5.15. Xizmat vazifalari (`fiscal.*`, `print.raw`, `scale.plu_upload`, `card.status`, `card.settlement`; `purpose='device_service'`) — 1C bazasiz, payload'lari 34 §14.3. `card.status` — karta terminallari holati va hal qilinmagan `unknown` urinishlar (har 5 daqiqa) → `card_terminals.health_status`/`health_checked_at`, `card_terminal_transactions` holat so'rovi natijasi; `card.settlement` — POS'siz smena yopilishi/kun oxirida terminal settlement'i → `card_terminal_settlements` (`created_by` NULL) (qaror #71); ikkalasi faqat `capabilities.card_terminal.enabled = true` agentga navbatga qo'yiladi. `base_id`, `batch_id`, `item_id`, `ref_create_request_id`, `reconciliation_id` FK'lari — `0029 onec_integration` da (kechiktirilgan FK bloki).

```sql
CREATE TABLE app.onec_agent_tasks (
  id                     UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id              UUID NOT NULL REFERENCES app.tenants(id),
  agent_id               UUID NOT NULL REFERENCES app.onec_agents(id),
  base_id                UUID NULL,   -- NULL: agent darajasidagi vazifa; FK fk_oat_base (0029)
  batch_id               UUID NULL,   -- FK fk_oat_batch (0029)
  item_id                UUID NULL,   -- FK fk_oat_item (0029)
  ref_create_request_id  UUID NULL,   -- FK fk_oat_ref_create (0029)
  reconciliation_id      UUID NULL,   -- FK fk_oat_reconciliation (0029)
  kind                   TEXT NOT NULL CHECK (kind IN ('probe','discover_bases','read_metadata','read_refs',
                           'read_date_prohibition','read_totals','read_stock_balances','preview_object','write_object',
                           'post_object','unpost_object','mark_delete_object','collect_diagnostics',
                           'fiscal.status','fiscal.resend_unsent','fiscal.zreport','print.raw','scale.plu_upload',
                           'card.status','card.settlement')), -- card.* — karta terminali (qaror #71)
  purpose                TEXT NOT NULL CHECK (purpose IN ('onboarding','mapping','export','reconcile','correction',
                           'ref_create','diagnostics','user_test','device_service')),
  is_write               BOOLEAN GENERATED ALWAYS AS
                           (kind IN ('write_object','post_object','unpost_object','mark_delete_object')) STORED,
  priority               SMALLINT NOT NULL DEFAULT 100,  -- kichik = birinchi: user_test/onboarding 10, mapping 30, ref_create 50, export 100, reconcile 150
  payload                JSONB NOT NULL,                 -- §9.5 vazifa turi bo'yicha
  payload_sha256         TEXT NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),  -- SHA-256(JCS(payload))
  status                 TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','leased','done','failed','expired','cancelled')),
  attempt                INT NOT NULL DEFAULT 1 CHECK (attempt >= 1),
  timeout_s              INT NOT NULL CHECK (timeout_s BETWEEN 10 AND 1800),
  not_before             TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at             TIMESTAMPTZ NULL,               -- shu vaqtgacha lease qilinmasa → expired (o'qish vazifalari)
  lease_id               UUID NULL,
  leased_at              TIMESTAMPTZ NULL,
  lease_until            TIMESTAMPTZ NULL,
  heartbeat_at           TIMESTAMPTZ NULL,
  progress               JSONB NULL,                     -- {"stage":"posting","pct":40}
  signing_kid            UUID NULL,                      -- platform.signing_keys.kid (purpose='onec_task')
  signature              TEXT NULL,                      -- compact JWS (§9.4)
  outcome                TEXT NULL CHECK (outcome IN ('done','failed','unknown')),
  error_code             TEXT NULL,
  finished_at            TIMESTAMPTZ NULL,
  created_by             UUID NULL REFERENCES app.users(id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status <> 'leased' OR (lease_id IS NOT NULL AND lease_until IS NOT NULL AND signature IS NOT NULL)),
  CHECK (status NOT IN ('done','failed') OR outcome IS NOT NULL),
  CHECK (base_id IS NOT NULL OR kind IN ('probe','discover_bases','collect_diagnostics',
         'fiscal.status','fiscal.resend_unsent','fiscal.zreport','print.raw','scale.plu_upload',
         'card.status','card.settlement')),
  CHECK ((kind LIKE '%.%') = (purpose = 'device_service')),
  CHECK (kind NOT LIKE '%.%' OR base_id IS NULL),
  CHECK (NOT is_write OR base_id IS NOT NULL)
);
CREATE INDEX idx_onec_tasks_dispatch ON app.onec_agent_tasks (agent_id, priority, not_before) WHERE status = 'queued';
CREATE INDEX idx_onec_tasks_lease ON app.onec_agent_tasks (lease_until) WHERE status = 'leased';
-- bitta bazada bir vaqtda bitta lease (bitta COM sessiya, fayl bazada 1C qulflari)
CREATE UNIQUE INDEX uq_onec_tasks_one_leased_per_base ON app.onec_agent_tasks (base_id)
  WHERE status = 'leased' AND base_id IS NOT NULL;
-- agent darajasidagi vazifadan bir vaqtda bittasi
CREATE UNIQUE INDEX uq_onec_tasks_one_leased_agent_level ON app.onec_agent_tasks (agent_id)
  WHERE status = 'leased' AND base_id IS NULL;
CREATE INDEX idx_onec_tasks_item ON app.onec_agent_tasks (item_id) WHERE item_id IS NOT NULL;
```

#### `onec_task_results`

Har urinishning xom natijasi; ilova faqat `INSERT` qiladi, o'qish natijalari 30 kundan keyin `onec_cleanup` bilan o'chiriladi (shuning uchun 3-bo'limdagi append-only ro'yxatda yo'q).

```sql
CREATE TABLE app.onec_task_results (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  task_id        UUID NOT NULL REFERENCES app.onec_agent_tasks(id),
  lease_id       UUID NOT NULL,
  attempt        INT NOT NULL,
  outcome        TEXT NOT NULL CHECK (outcome IN ('done','failed','unknown')),
  data           JSONB NOT NULL DEFAULT '{}',   -- read_refs/read_metadata katta qismi o'z jadvaliga ko'chiriladi, bu yerda qisqartiriladi
  data_trimmed   BOOLEAN NOT NULL DEFAULT false,
  error          JSONB NULL,                    -- §9.10
  duration_ms    INT NULL CHECK (duration_ms >= 0),
  agent_version  TEXT NULL,
  worker_bits    SMALLINT NULL CHECK (worker_bits IN (32,64)),
  late           BOOLEAN NOT NULL DEFAULT false, -- lease muddati o'tgandan keyin keldi
  received_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (task_id, lease_id)
);
```

#### `auth.onec_device_authorizations`

RFC 8628 device grant holati (agentni ulash, 30 kun saqlanadi). `erp_app`ga hech qanday grant yo'q — kirish faqat 4.5-bo'limdagi `onec_device_auth_*` funksiyalari orqali; RLS yoqilmaydi (boshqa `auth.*` kabi, 6.2 CI istisnosi).

```sql
CREATE TABLE auth.onec_device_authorizations (
  id                     UUID PRIMARY KEY DEFAULT app.uuidv7(),
  device_code_hash       TEXT NOT NULL UNIQUE,      -- SHA-256(device_code); kodning o'zi saqlanmaydi
  user_code              TEXT NOT NULL CHECK (user_code ~ '^[BCDFGHJKLMNPQRSTVWXZ]{8}$'),  -- chiziqchasiz, katta harf
  client_id              TEXT NOT NULL DEFAULT 'onec-agent',
  scope                  TEXT NOT NULL DEFAULT 'onec.agent',
  public_jwk             JSONB NOT NULL,
  public_key_thumbprint  TEXT NOT NULL,
  machine_hash           TEXT NOT NULL,
  pc_name                TEXT NOT NULL,
  os_version             TEXT NULL,
  agent_version          TEXT NULL,
  request_ip             INET NULL,
  status                 TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','denied','consumed','expired')),
  tenant_id              UUID NULL REFERENCES app.tenants(id),
  approved_by            UUID NULL REFERENCES app.users(id),
  approved_at            TIMESTAMPTZ NULL,
  agent_id               UUID NULL,                 -- tasdiqlanganda yaratilgan app.onec_agents.id
  poll_interval_s        INT NOT NULL DEFAULT 5,
  last_poll_at           TIMESTAMPTZ NULL,
  expires_at             TIMESTAMPTZ NOT NULL,      -- created_at + 10 daqiqa
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status NOT IN ('approved','consumed') OR (tenant_id IS NOT NULL AND agent_id IS NOT NULL AND approved_by IS NOT NULL))
);
CREATE UNIQUE INDEX uq_onec_device_auth_user_code_pending ON auth.onec_device_authorizations (user_code) WHERE status = 'pending';
```

**`0029 onec_integration` jadvallari** (Bosqich 7):

#### `onec_bases`

Agent qo'shgan har 1C bazasi; qulf №1 (`write_enabled`). `guid_namespace` — deterministik GUID nomlar fazosi, trigger bilan o'zgarmas. Ulanish satri va parol saqlanmaydi. Holat mashinasi — 33 §5.3.

```sql
CREATE TABLE app.onec_bases (
  id                        UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id                 UUID NOT NULL REFERENCES app.tenants(id),
  agent_id                  UUID NOT NULL REFERENCES app.onec_agents(id),
  local_id                  TEXT NOT NULL,              -- agentdagi baza ID'si (agent beradi, GUID satr)
  name                      TEXT NOT NULL,
  connect_kind              TEXT NOT NULL CHECK (connect_kind IN ('file','server')),
  connect_fingerprint       TEXT NOT NULL CHECK (connect_fingerprint ~ '^[0-9a-f]{64}$'),
                            -- SHA-256(normallashtirilgan "File=..." yoki "Srvr=...;Ref=...", Usr/Pwd'siz,
                            -- kichik harf, disk harfi UNC'ga yechilgan) — agent hisoblaydi (34)
  connect_display           TEXT NOT NULL,              -- maskalangan: '\\SERVER\1c\shop' yoki 'srv1c/shop'
  auth_kind                 TEXT NOT NULL CHECK (auth_kind IN ('password','os')),
  onec_user_name            TEXT NULL,                  -- 1C login nomi (sir emas)
  config_name               TEXT NULL,                  -- Метаданные.Имя
  config_synonym            TEXT NULL,                  -- Метаданные.Синоним
  config_version            TEXT NULL,                  -- Метаданные.Версия
  platform_version          TEXT NULL,
  platform_bits             SMALLINT NULL CHECK (platform_bits IN (32,64)),
  profile_code              TEXT NOT NULL DEFAULT 'unknown'
                            CHECK (profile_code IN ('bp30_uz','ut11_uz','roznica30_uz','uk30_uz','unknown')),
  guid_namespace            UUID NOT NULL,              -- uuid4, o'zgarmas
  write_enabled             BOOLEAN NOT NULL DEFAULT false,  -- qulf №1 (server, BO-22)
  pc_write_enabled          BOOLEAN NOT NULL DEFAULT false,  -- qulf №2 (agent oynasi; hello orqali keladi, faqat ko'rsatish)
  status                    TEXT NOT NULL DEFAULT 'onboarding'
                            CHECK (status IN ('onboarding','ready','error','disabled','archived')),
  checks                    JSONB NOT NULL DEFAULT '[]', -- §2.3 natijalari
  checks_at                 TIMESTAMPTZ NULL,
  date_prohibition          DATE NULL,                  -- oxirgi o'qilgan 1C taqiq sanasi (NULL = yo'q)
  date_prohibition_read_at  TIMESTAMPTZ NULL,
  organization_guid         UUID NULL,                  -- tasdiqlangan onec_mappings(entity='organization') nusxasi
  metadata_hash             TEXT NULL,
  last_ok_at                TIMESTAMPTZ NULL,
  last_error_code           TEXT NULL,
  last_error_at             TIMESTAMPTZ NULL,
  archived_at               TIMESTAMPTZ NULL,
  archived_by               UUID NULL REFERENCES app.users(id),
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  version                   INT NOT NULL DEFAULT 1,
  UNIQUE (agent_id, local_id),
  CHECK (status <> 'archived' OR archived_at IS NOT NULL),
  CHECK (auth_kind = 'os' OR onec_user_name IS NOT NULL),
  CHECK (NOT write_enabled OR status IN ('ready','error'))
);
-- bitta 1C bazasiga tenant ichida faqat bitta faol yozuvchi agent
CREATE UNIQUE INDEX uq_onec_bases_fingerprint_active ON app.onec_bases (tenant_id, connect_fingerprint)
  WHERE status <> 'archived';
CREATE INDEX idx_onec_bases_agent ON app.onec_bases (agent_id) WHERE status <> 'archived';

CREATE OR REPLACE FUNCTION app.onec_forbid_namespace_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.guid_namespace IS DISTINCT FROM OLD.guid_namespace THEN
    RAISE EXCEPTION 'onec_bases.guid_namespace o''zgartirilmaydi' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER trg_onec_bases_namespace_immutable BEFORE UPDATE ON app.onec_bases
  FOR EACH ROW EXECUTE FUNCTION app.onec_forbid_namespace_change();
```

#### `onec_settings`

Baza bo'yicha sozlamalar (1:1), baza yaratilganda standart qiymatlar bilan yoziladi.

```sql
CREATE TABLE app.onec_settings (
  base_id                       UUID PRIMARY KEY REFERENCES app.onec_bases(id),
  tenant_id                     UUID NOT NULL REFERENCES app.tenants(id),
  mode                          TEXT NOT NULL DEFAULT 'full' CHECK (mode IN ('full','sales_only')),
  start_date                    DATE NULL,             -- shu sanadan oldingi ERP hujjatlari hech qachon yuborilmaydi
  orp_grouping                  TEXT NOT NULL DEFAULT 'register_day' CHECK (orp_grouping IN ('register_day','branch_day')),
  same_day_returns              TEXT NOT NULL DEFAULT 'orp_returns_section'
                                CHECK (same_day_returns IN ('orp_returns_section','separate_document')), -- P-07
  card_refund_mode              TEXT NOT NULL DEFAULT 'card_operation'
                                CHECK (card_refund_mode IN ('card_operation','orp_negative_payment')), -- P-08
  schedule_mode                 TEXT NOT NULL DEFAULT 'manual' CHECK (schedule_mode IN ('manual','on_shift_close','at_time')),
  schedule_time                 TIME NULL,             -- Asia/Tashkent
  last_schedule_run_on          DATE NULL,
  readiness_policy              TEXT NOT NULL DEFAULT 'all_shifts_closed'
                                CHECK (readiness_policy IN ('all_shifts_closed','allow_open')),
  auto_approve                  BOOLEAN NOT NULL DEFAULT false,  -- faqat Egasi yoqadi (qaror #40)
  auto_approve_set_by           UUID NULL REFERENCES app.users(id),
  auto_approve_set_at           TIMESTAMPTZ NULL,
  ref_create_policy             TEXT NOT NULL DEFAULT 'ask' CHECK (ref_create_policy IN ('ask','deny')),
  stock_preflight               TEXT NOT NULL DEFAULT 'on_error' CHECK (stock_preflight IN ('always','on_error','off')),
                                -- mode='sales_only' bo'lsa amalda 'always'
  continue_money_on_stock_error BOOLEAN NOT NULL DEFAULT true,
  send_bank_payments            BOOLEAN NOT NULL DEFAULT false, -- bank orqali qarz/yetkazib beruvchi to'lovlari
  send_bank_settlements         BOOLEAN NOT NULL DEFAULT false, -- bank_settlements (5710→5110), qaror #42
  send_shift_variance           BOOLEAN NOT NULL DEFAULT false,
  notify_user_ids               UUID[] NOT NULL DEFAULT '{}',   -- qo'shimcha qabul qiluvchilar (onec.view baribir shart)
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  version                       INT NOT NULL DEFAULT 1,
  CHECK (schedule_mode <> 'at_time' OR schedule_time IS NOT NULL),
  CHECK (NOT auto_approve OR (auto_approve_set_by IS NOT NULL AND auto_approve_set_at IS NOT NULL)),
  CHECK (NOT (auto_approve AND schedule_mode = 'manual'))
);
```

#### `onec_branch_bindings`

Filial → 1C bazasi; bitta filial — bitta faol bog'lanish.

```sql
CREATE TABLE app.onec_branch_bindings (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  branch_id   UUID NOT NULL REFERENCES app.branches(id),
  base_id     UUID NOT NULL REFERENCES app.onec_bases(id),
  bound_from  DATE NOT NULL,              -- shu sanadan boshlab; >= onec_settings.start_date (ilova tekshiradi)
  created_by  UUID NOT NULL REFERENCES app.users(id),
  archived_at TIMESTAMPTZ NULL,
  archived_by UUID NULL REFERENCES app.users(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_onec_bindings_branch_active ON app.onec_branch_bindings (branch_id) WHERE archived_at IS NULL;
CREATE INDEX idx_onec_bindings_base ON app.onec_branch_bindings (base_id) WHERE archived_at IS NULL;
```

#### `onec_metadata_snapshots`

`read_metadata` natijasi (profil va `ObjectSpec` tekshiruvi uchun); oxirgi 5 ta nusxa saqlanadi.

```sql
CREATE TABLE app.onec_metadata_snapshots (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  base_id         UUID NOT NULL REFERENCES app.onec_bases(id),
  config_name     TEXT NOT NULL,
  config_version  TEXT NOT NULL,
  metadata_hash   TEXT NOT NULL CHECK (metadata_hash ~ '^[0-9a-f]{64}$'),
  object_count    INT NOT NULL,
  data            JSONB NOT NULL,          -- §9.5 read_metadata natijasi (objects[])
  task_id         UUID NULL,               -- FK §5.21
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (base_id, metadata_hash)
);
CREATE INDEX idx_onec_meta_base_time ON app.onec_metadata_snapshots (base_id, created_at DESC);
```

#### `onec_catalog_items`

`read_refs` bilan o'qilgan 1C ma'lumotnoma elementlari va sanoq qiymatlari keshi (auto-match va qo'lda tanlash).

```sql
CREATE TABLE app.onec_catalog_items (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  base_id        UUID NOT NULL REFERENCES app.onec_bases(id),
  onec_type      TEXT NOT NULL,          -- 'Справочник.Номенклатура', 'Перечисление.СтавкиНДС', 'ПланСчетов.Хозрасчетный'
  onec_guid      UUID NULL,              -- sanoq qiymatida NULL
  enum_value     TEXT NULL,              -- sanoq qiymati nomi
  code           TEXT NULL,
  name           TEXT NOT NULL,
  full_name      TEXT NULL,
  name_norm      TEXT NOT NULL,          -- §6.13 normallashtirish
  inn            TEXT NULL,              -- ИНН (STIR, 9 raqam)
  pinfl          TEXT NULL,              -- ПИНФЛ (14 raqam) — 1C rekvizit nomi metadata o'qishda tasdiqlanadi (26 #132)
  ikpu           TEXT NULL,              -- ИКПУ/MXIK (17 raqam) — 1C rekvizit nomi metadata o'qishda tasdiqlanadi (26 #132)
  article        TEXT NULL,              -- Артикул
  barcodes       TEXT[] NOT NULL DEFAULT '{}',
  parent_guid    UUID NULL,
  owner_guid     UUID NULL,              -- ДоговорыКонтрагентов.Владелец va h.k.
  is_folder      BOOLEAN NOT NULL DEFAULT false,
  deletion_mark  BOOLEAN NOT NULL DEFAULT false,
  extra          JSONB NOT NULL DEFAULT '{}', -- ТипСклада, ВидДоговора, ВидОплаты hisobi/kontragenti, ЕдиницаИзмерения va h.k.
  read_at        TIMESTAMPTZ NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((onec_guid IS NULL) <> (enum_value IS NULL))
);
CREATE UNIQUE INDEX uq_onec_catalog_items_guid ON app.onec_catalog_items (base_id, onec_type, onec_guid) WHERE onec_guid IS NOT NULL;
CREATE UNIQUE INDEX uq_onec_catalog_items_enum ON app.onec_catalog_items (base_id, onec_type, enum_value) WHERE enum_value IS NOT NULL;
CREATE INDEX idx_onec_catalog_items_name_trgm ON app.onec_catalog_items USING gin (name_norm gin_trgm_ops);
CREATE INDEX idx_onec_catalog_items_inn ON app.onec_catalog_items (base_id, onec_type, inn) WHERE inn IS NOT NULL;
CREATE INDEX idx_onec_catalog_items_ikpu ON app.onec_catalog_items (base_id, ikpu) WHERE ikpu IS NOT NULL;
CREATE INDEX idx_onec_catalog_items_barcodes ON app.onec_catalog_items USING gin (barcodes);
```

#### `onec_mappings`

Ref maps: ERP qatori (UUID) ↔ 1C elementi GUID. Eksport faqat `status='confirmed'` qatorlarni ishlatadi; `entity` → 1C turi — 33 §5.8.

```sql
CREATE TABLE app.onec_mappings (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  base_id            UUID NOT NULL REFERENCES app.onec_bases(id),
  entity             TEXT NOT NULL CHECK (entity IN ('organization','branch','warehouse','cash_register','cash_desk',
                       'product','product_category','counterparty','counterparty_contract','expense_category')),
  erp_id             UUID NOT NULL,      -- tenants.id / branches.id / warehouses.id / cash_registers.id / products.id / ...
  erp_role           TEXT NOT NULL DEFAULT '' CHECK (erp_role IN ('','customer','supplier')), -- faqat counterparty_contract
  onec_type          TEXT NOT NULL,      -- 'Справочник.Номенклатура' (profil beradi)
  onec_guid          UUID NOT NULL,
  onec_presentation  TEXT NULL,
  onec_extra         JSONB NOT NULL DEFAULT '{}', -- expense_category: {"account_guid":"..."}; warehouse: {"warehouse_type":"РозничныйМагазин"}
  status             TEXT NOT NULL CHECK (status IN ('suggested','confirmed')),
  source             TEXT NOT NULL CHECK (source IN ('auto_inn','auto_ikpu','auto_barcode','auto_article','auto_code',
                       'auto_name','auto_fuzzy','manual','created_by_erp')),
  match_quality      TEXT NULL CHECK (match_quality IN ('exact','probable')),
  confidence         NUMERIC(4,3) NULL CHECK (confidence BETWEEN 0 AND 1),
  erp_version        INT NULL,           -- products/counterparties.version bog'langan paytda
  confirmed_by       UUID NULL REFERENCES app.users(id),
  confirmed_at       TIMESTAMPTZ NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (base_id, entity, erp_id, erp_role),
  CHECK (status <> 'confirmed' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)),
  CHECK (entity = 'counterparty_contract' OR erp_role = '')
);
CREATE INDEX idx_onec_mappings_guid ON app.onec_mappings (base_id, onec_guid);  -- bir 1C elementiga bir nechta ERP qatori mumkin
CREATE INDEX idx_onec_mappings_status ON app.onec_mappings (base_id, entity, status);
```

#### `onec_value_mappings`

Value maps: ERP enum qiymati / sozlama kaliti ↔ 1C elementi yoki sanoq qiymati; `erp_value` yopiq lug'ati — 33 §5.9.

```sql
CREATE TABLE app.onec_value_mappings (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  base_id            UUID NOT NULL REFERENCES app.onec_bases(id),
  kind               TEXT NOT NULL CHECK (kind IN ('payment_method','vat_rate','unit','account','cash_flow_item',
                       'retail_customer','retail_customer_contract','bank_account','goods_kind','product_folder','debtor_folder')),
  erp_value          TEXT NOT NULL,      -- quyidagi lug'at
  onec_type          TEXT NOT NULL,
  onec_guid          UUID NULL,
  onec_enum          TEXT NULL,
  onec_presentation  TEXT NULL,
  onec_extra         JSONB NOT NULL DEFAULT '{}', -- payment_method: {"account_code":"5710","acquirer_guid":"..."} (ko'rsatish uchun)
  source             TEXT NOT NULL CHECK (source IN ('auto','manual','created_by_erp')),
  confirmed_by       UUID NULL REFERENCES app.users(id),
  confirmed_at       TIMESTAMPTZ NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (base_id, kind, erp_value),
  CHECK ((onec_guid IS NULL) <> (onec_enum IS NULL))
);
```

#### `onec_ref_create_requests`

1C'da yangi ma'lumotnoma elementi yaratish faqat shu jadval orqali, inson tasdig'i bilan (qaror #40). Holat mashinasi — 33 §5.10.

```sql
CREATE TABLE app.onec_ref_create_requests (
  id                UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id         UUID NOT NULL REFERENCES app.tenants(id),
  base_id           UUID NOT NULL REFERENCES app.onec_bases(id),
  entity            TEXT NOT NULL CHECK (entity IN ('product','counterparty','counterparty_contract','warehouse',
                      'cash_register','cash_desk','branch','expense_category','unit','payment_method','cash_flow_item',
                      'retail_customer')),
  erp_id            TEXT NOT NULL,     -- UUID matni yoki value lug'ati qiymati (unit/payment_method/...)
  erp_role          TEXT NOT NULL DEFAULT '' CHECK (erp_role IN ('','customer','supplier')),
  onec_type         TEXT NOT NULL,
  onec_guid         UUID NOT NULL,     -- uuid5(guid_namespace, 'catalog_{entity}:{erp_key}') — §8.1
  proposed_fields   JSONB NOT NULL,    -- [{name, value(§9.8), label_uz}] — BO'dagi "1C'da yaratiladi" kartasi
  op_spec           JSONB NULL,        -- tasdiqda quriladi
  op_spec_sha256    TEXT NULL,
  status            TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed','approved','sending','created','failed','rejected','superseded')),
  source            TEXT NOT NULL CHECK (source IN ('wizard','batch_preview')),
  batch_id          UUID NULL,         -- qaysi partiya preview'i talab qilgan (FK §5.21)
  requested_by      UUID NULL REFERENCES app.users(id),
  approved_by       UUID NULL REFERENCES app.users(id),
  approved_at       TIMESTAMPTZ NULL,
  rejected_by       UUID NULL REFERENCES app.users(id),
  rejected_at       TIMESTAMPTZ NULL,
  reject_reason     TEXT NULL,
  task_id           UUID NULL,         -- FK §5.21
  attempts          INT NOT NULL DEFAULT 0,
  last_error_code   TEXT NULL,
  last_error        JSONB NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status NOT IN ('approved','sending','created') OR approved_by IS NOT NULL),
  CHECK (status <> 'rejected' OR (rejected_by IS NOT NULL AND reject_reason IS NOT NULL))
);
CREATE UNIQUE INDEX uq_onec_ref_create_open ON app.onec_ref_create_requests (base_id, entity, erp_id, erp_role)
  WHERE status IN ('proposed','approved','sending');
CREATE INDEX idx_onec_ref_create_status ON app.onec_ref_create_requests (base_id, status);
```

#### `onec_export_batches`

Baza × hisob kuni × revision bo'yicha kun eksporti (holat mashinasi — 33 §7.1).

```sql
CREATE TABLE app.onec_export_batches (
  id                     UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id              UUID NOT NULL REFERENCES app.tenants(id),
  base_id                UUID NOT NULL REFERENCES app.onec_bases(id),
  business_date          DATE NOT NULL,           -- ERP doc_date (Toshkent hisob kuni)
  revision               INT NOT NULL DEFAULT 1 CHECK (revision >= 1),
  kind                   TEXT NOT NULL DEFAULT 'regular' CHECK (kind IN ('regular','correction')),
  correction_date        DATE NULL,               -- kind='correction': 1C hujjatlari sanasi (joriy ochiq sana)
  is_current             BOOLEAN NOT NULL DEFAULT true,
  supersedes_batch_id    UUID NULL REFERENCES app.onec_export_batches(id),
  status                 TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','preview','approved','queued',
                           'sending','verifying','done','partial','mismatch','failed','cancelled')),
  trigger                TEXT NOT NULL CHECK (trigger IN ('manual','shift_close','schedule','late_data','correction')),
  mode                   TEXT NOT NULL CHECK (mode IN ('full','sales_only')),          -- qurilgan paytdagi nusxa
  orp_grouping           TEXT NOT NULL CHECK (orp_grouping IN ('register_day','branch_day')),
  branch_ids             UUID[] NOT NULL,         -- qurilgan paytdagi bog'langan filiallar
  readiness              JSONB NOT NULL DEFAULT '{}',  -- §7.3 {checks:[...], evaluated_at}
  blocking_issues        JSONB NOT NULL DEFAULT '[]',  -- [{code, params}] — bo'sh bo'lmasa approve taqiqlanadi
  warnings               JSONB NOT NULL DEFAULT '[]',  -- [{code, params}]
  excluded_devices       JSONB NOT NULL DEFAULT '[]',  -- [{device_id, reason, by, at}] — §7.3 qo'lda istisno
  preview                JSONB NULL,                   -- §7.4
  preview_hash           TEXT NULL CHECK (preview_hash IS NULL OR preview_hash ~ '^[0-9a-f]{64}$'),
  expected_totals        JSONB NOT NULL DEFAULT '{}',  -- §6.11
  actual_totals          JSONB NULL,
  item_counts            JSONB NOT NULL DEFAULT '{}',  -- {"pending":0,"written":3,"failed":1,...}
  needs_resync           BOOLEAN NOT NULL DEFAULT false,
  resync_detected_at     TIMESTAMPTZ NULL,
  created_by             UUID NULL REFERENCES app.users(id),  -- NULL = scheduler
  approved_by            UUID NULL REFERENCES app.users(id),  -- auto: onec_settings.auto_approve_set_by
  approved_at            TIMESTAMPTZ NULL,
  approval_mode          TEXT NULL CHECK (approval_mode IN ('manual','auto')),
  approved_preview_hash  TEXT NULL,
  acknowledged_warnings  TEXT[] NOT NULL DEFAULT '{}',
  queued_at              TIMESTAMPTZ NULL,
  started_at             TIMESTAMPTZ NULL,
  finished_at            TIMESTAMPTZ NULL,
  accepted_by            UUID NULL REFERENCES app.users(id),  -- partial/mismatch qabul qilindi
  accepted_at            TIMESTAMPTZ NULL,
  accept_reason          TEXT NULL,
  cancel_requested_at    TIMESTAMPTZ NULL,
  cancelled_by           UUID NULL REFERENCES app.users(id),
  cancelled_at           TIMESTAMPTZ NULL,
  cancel_reason          TEXT NULL,
  error_code             TEXT NULL,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (base_id, business_date, kind, revision),
  CHECK (kind <> 'correction' OR correction_date IS NOT NULL),
  CHECK (status NOT IN ('approved','queued','sending','verifying','done','partial','mismatch')
         OR (approved_at IS NOT NULL AND approval_mode IS NOT NULL AND approved_preview_hash IS NOT NULL)),
  CHECK (status <> 'cancelled' OR (cancelled_at IS NOT NULL AND cancel_reason IS NOT NULL)),
  CHECK (accepted_at IS NULL OR (status IN ('partial','mismatch') AND accepted_by IS NOT NULL AND accept_reason IS NOT NULL))
);
-- baza bo'yicha bir vaqtda bitta faol (navbatda/yuborilayotgan/tekshirilayotgan) partiya
CREATE UNIQUE INDEX uq_onec_batches_one_active ON app.onec_export_batches (base_id)
  WHERE status IN ('queued','sending','verifying');
-- (baza, sana, tur) bo'yicha bitta joriy revision
CREATE UNIQUE INDEX uq_onec_batches_current ON app.onec_export_batches (base_id, business_date, kind) WHERE is_current;
CREATE INDEX idx_onec_batches_base_date ON app.onec_export_batches (base_id, business_date DESC);
CREATE INDEX idx_onec_batches_open ON app.onec_export_batches (tenant_id, status) WHERE status NOT IN ('done','cancelled');
```

#### `onec_export_items`

Partiyadagi har 1C obyekti — bitta GUID, bitta urinishlar zanjiri (holat mashinasi — 33 §7.5).

```sql
CREATE TABLE app.onec_export_items (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  batch_id           UUID NOT NULL REFERENCES app.onec_export_batches(id),
  base_id            UUID NOT NULL REFERENCES app.onec_bases(id),
  seq                INT NOT NULL CHECK (seq > 0),
  phase              SMALLINT NOT NULL CHECK (phase BETWEEN 10 AND 120),
  kind               TEXT NOT NULL CHECK (kind IN ('retail_sales_report','retail_sales_correction','retail_return',
                       'retail_return_cash_out','retail_return_card_refund','credit_sale','credit_sale_payment',
                       'customer_return','customer_return_refund','debt_payment','goods_receipt','goods_receipt_payment',
                       'supplier_return','supplier_payment','transfer','transfer_loss','write_off','stock_count',
                       'stock_count_loss','stock_count_gain','stock_adjustment','expense','cash_movement',
                       'bank_settlement','shift_variance')),
  action             TEXT NOT NULL CHECK (action IN ('create','update','unchanged','unpost_mark_delete','correction')),
  erp_key            TEXT NOT NULL,           -- §8.1 jadvali
  idempotency_key    TEXT NOT NULL,           -- '{base_id}:{kind}:{erp_key}'
  object_ref_id      UUID NULL,               -- FK §5.21 (avval yozilgan bo'lsa)
  depends_on_item_id UUID NULL REFERENCES app.onec_export_items(id),
  onec_type          TEXT NOT NULL,           -- 'Документ.ОтчетОРозничныхПродажах'
  onec_guid          UUID NOT NULL,
  doc_time           TIMESTAMP NOT NULL,      -- 1C Дата (Toshkent mahalliy, zonasiz)
  title              TEXT NOT NULL,           -- 'ОРП · Kassa-1 · 15.10.2026' (preview qatori)
  content_hash       TEXT NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),   -- §8.2
  op_spec            JSONB NULL,              -- ObjectSpec (§9.6); 90 kundan keyin NULL
  op_spec_sha256     TEXT NOT NULL CHECK (op_spec_sha256 ~ '^[0-9a-f]{64}$'),
  line_count         INT NOT NULL DEFAULT 0,
  expected_amount    NUMERIC(18,2) NOT NULL DEFAULT 0,  -- hujjat summasi (ERP)
  expected_vat       NUMERIC(18,2) NOT NULL DEFAULT 0,
  expected_qty       NUMERIC(18,3) NULL,
  status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','queued','sending','retry_wait',
                       'unknown','written','verified','failed','skipped','mismatch')),
  skip_reason        TEXT NULL CHECK (skip_reason IN ('unchanged','empty','user','dependency','cancelled')),
  attempts           INT NOT NULL DEFAULT 0,
  max_attempts       INT NOT NULL DEFAULT 8,
  next_attempt_at    TIMESTAMPTZ NULL,
  last_task_id       UUID NULL,               -- FK §5.21
  last_error_code    TEXT NULL,
  last_error         JSONB NULL,              -- §9.10 xato obyekti (1C xabarlari bilan)
  result             JSONB NULL,              -- write_object natijasi (§9.5)
  onec_number        TEXT NULL,
  onec_posted        BOOLEAN NULL,
  written_at         TIMESTAMPTZ NULL,
  verified_at        TIMESTAMPTZ NULL,
  skipped_by         UUID NULL REFERENCES app.users(id),
  skipped_at         TIMESTAMPTZ NULL,
  skip_note          TEXT NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (batch_id, seq),
  UNIQUE (batch_id, onec_guid),
  UNIQUE (batch_id, idempotency_key),
  CHECK (status <> 'skipped' OR skip_reason IS NOT NULL),
  CHECK (skip_reason IS DISTINCT FROM 'user' OR (skipped_by IS NOT NULL AND skip_note IS NOT NULL)),
  CHECK (action <> 'unchanged' OR status = 'skipped')
);
CREATE INDEX idx_onec_items_dispatch ON app.onec_export_items (batch_id, phase, seq)
  WHERE status IN ('pending','queued','retry_wait','unknown');
CREATE INDEX idx_onec_items_retry ON app.onec_export_items (next_attempt_at) WHERE status = 'retry_wait';
CREATE INDEX idx_onec_items_guid ON app.onec_export_items (base_id, onec_guid);
```

#### `onec_export_item_sources`

Item ↔ ERP manba hujjatlari (`doc_type` — hujjat jadvali nomi).

```sql
CREATE TABLE app.onec_export_item_sources (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  item_id        UUID NOT NULL REFERENCES app.onec_export_items(id),
  batch_id       UUID NOT NULL REFERENCES app.onec_export_batches(id),
  base_id        UUID NOT NULL REFERENCES app.onec_bases(id),
  doc_type       TEXT NOT NULL CHECK (doc_type IN ('sales','returns','goods_receipts','supplier_returns','transfers',
                   'write_offs','stock_counts','debt_payments','supplier_payments','expenses','cash_movements',
                   'bank_settlements','shifts')),
  doc_id         UUID NOT NULL,
  business_date  DATE NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (item_id, doc_type, doc_id)
);
CREATE INDEX idx_onec_item_sources_doc ON app.onec_export_item_sources (tenant_id, doc_type, doc_id);
```

#### `onec_object_refs`

ERP 1C'da yaratgan (yoki `dedupe` bilan qabul qilgan) har obyektning doimiy daftari; bitta `(base, kind, erp_key)` — bitta 1C obyekti.

```sql
CREATE TABLE app.onec_object_refs (
  id                 UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id          UUID NOT NULL REFERENCES app.tenants(id),
  base_id            UUID NOT NULL REFERENCES app.onec_bases(id),
  kind               TEXT NOT NULL,            -- onec_export_items.kind yoki 'catalog_*' (§8.1)
  erp_key            TEXT NOT NULL,
  onec_type          TEXT NOT NULL,
  onec_guid          UUID NOT NULL,
  origin             TEXT NOT NULL DEFAULT 'created' CHECK (origin IN ('created','adopted')),
                     -- adopted = 1C'da allaqachon bor hujjat dedupe orqali bog'landi (GUID bizniki emas)
  onec_number        TEXT NULL,
  onec_date          TIMESTAMP NULL,           -- 1C mahalliy vaqt
  onec_data_version  TEXT NULL,                -- ВерсияДанных (oxirgi yozish/o'qishdan keyin)
  content_hash       TEXT NULL,                -- oxirgi muvaffaqiyatli yozilgan kontent
  content_snapshot   JSONB NULL,               -- neytral kontent (qatorlar) — tuzatuvchi hujjat farqi uchun (§8.8)
  posted             BOOLEAN NOT NULL DEFAULT false,
  deletion_mark      BOOLEAN NOT NULL DEFAULT false,
  state              TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active','unposted','marked_deleted',
                       'missing_in_1c','changed_in_1c')),
  last_batch_id      UUID NULL REFERENCES app.onec_export_batches(id),
  last_item_id       UUID NULL,                -- FK §5.21
  first_written_at   TIMESTAMPTZ NULL,
  last_written_at    TIMESTAMPTZ NULL,
  last_checked_at    TIMESTAMPTZ NULL,         -- drift tekshiruvi
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (base_id, kind, erp_key),
  UNIQUE (base_id, onec_guid)
);
CREATE INDEX idx_onec_object_refs_drift ON app.onec_object_refs (base_id, last_written_at DESC) WHERE state = 'active';
```

#### `onec_reconciliations`

Solishtirish natijalari: `batch_totals`, `drift`, `stock_balance`, `opening_stock`.

```sql
CREATE TABLE app.onec_reconciliations (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  base_id        UUID NOT NULL REFERENCES app.onec_bases(id),
  batch_id       UUID NULL REFERENCES app.onec_export_batches(id),
  kind           TEXT NOT NULL CHECK (kind IN ('batch_totals','drift','stock_balance','opening_stock')),
  as_of_date     DATE NOT NULL,
  status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','match','mismatch','failed')),
  task_id        UUID NULL REFERENCES app.onec_agent_tasks(id) ON DELETE SET NULL,
  expected       JSONB NOT NULL DEFAULT '{}',
  actual         JSONB NULL,
  diffs          JSONB NOT NULL DEFAULT '[]',   -- [{key, title, erp, onec, diff}]
  diff_count     INT NOT NULL DEFAULT 0,
  diff_amount    NUMERIC(18,2) NULL,
  requested_by   UUID NULL REFERENCES app.users(id),
  finished_at    TIMESTAMPTZ NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_onec_recon_base ON app.onec_reconciliations (base_id, kind, as_of_date DESC);
```

#### `onec_events`

Server voqealar lentasi (BO-23 progress, BO-22 jurnal); `audit_log` o'rnini bosmaydi. Voqea kodlari — 33 §5.19.

```sql
CREATE TABLE app.onec_events (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  base_id        UUID NULL REFERENCES app.onec_bases(id),
  agent_id       UUID NULL REFERENCES app.onec_agents(id),
  batch_id       UUID NULL REFERENCES app.onec_export_batches(id),
  item_id        UUID NULL REFERENCES app.onec_export_items(id),
  task_id        UUID NULL REFERENCES app.onec_agent_tasks(id) ON DELETE SET NULL,
  level          TEXT NOT NULL CHECK (level IN ('info','warning','error')),
  code           TEXT NOT NULL,     -- 'batch.prepared','batch.approved','item.written','item.retry','agent.online', ...
  message_key    TEXT NOT NULL,     -- 'onec.events.item_written'
  params         JSONB NOT NULL DEFAULT '{}',
  actor_user_id  UUID NULL REFERENCES app.users(id),
  at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_onec_events_batch ON app.onec_events (batch_id, at) WHERE batch_id IS NOT NULL;
CREATE INDEX idx_onec_events_base ON app.onec_events (tenant_id, base_id, at DESC);
```

#### `onec_agent_logs`

Agent `POST /onec-agent/logs` (A-06) bilan yuborgan maskalangan log yozuvlari.

```sql
CREATE TABLE app.onec_agent_logs (
  id              UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id       UUID NOT NULL REFERENCES app.tenants(id),
  agent_id        UUID NOT NULL REFERENCES app.onec_agents(id),
  client_log_id   UUID NOT NULL,          -- agent beradi (takror yuborishda dedupe)
  base_id         UUID NULL REFERENCES app.onec_bases(id),
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
```

#### Kechiktirilgan FK

Aylana bog'liqliklar (`onec_agent_tasks` ↔ `onec_reconciliations`, `onec_export_items` ↔ `onec_object_refs` va h.k.) — `0029 onec_integration` revizionida, barcha jadvallar yaratilgandan keyin. O'qish vazifalari 30 kundan keyin `onec_cleanup` bilan o'chiriladi — ularga ishora qiluvchi uzoq yashovchi jadvallarning `task_id` FK'lari `ON DELETE SET NULL`:

```sql
ALTER TABLE app.onec_metadata_snapshots  ADD CONSTRAINT fk_onec_meta_task        FOREIGN KEY (task_id)           REFERENCES app.onec_agent_tasks(id) ON DELETE SET NULL;
ALTER TABLE app.onec_export_items        ADD CONSTRAINT fk_onec_items_object_ref FOREIGN KEY (object_ref_id)     REFERENCES app.onec_object_refs(id);
ALTER TABLE app.onec_export_items        ADD CONSTRAINT fk_onec_items_last_task  FOREIGN KEY (last_task_id)      REFERENCES app.onec_agent_tasks(id);
ALTER TABLE app.onec_object_refs         ADD CONSTRAINT fk_onec_refs_last_item   FOREIGN KEY (last_item_id)      REFERENCES app.onec_export_items(id);
ALTER TABLE app.onec_ref_create_requests ADD CONSTRAINT fk_onec_rcr_task         FOREIGN KEY (task_id)           REFERENCES app.onec_agent_tasks(id);
ALTER TABLE app.onec_ref_create_requests ADD CONSTRAINT fk_onec_rcr_batch        FOREIGN KEY (batch_id)          REFERENCES app.onec_export_batches(id);
-- onec_agent_tasks (0028 da FK'siz yaratilgan) — 1C jadvallariga FK'lar
ALTER TABLE app.onec_agent_tasks         ADD CONSTRAINT fk_oat_base              FOREIGN KEY (base_id)               REFERENCES app.onec_bases(id);
ALTER TABLE app.onec_agent_tasks         ADD CONSTRAINT fk_oat_batch             FOREIGN KEY (batch_id)              REFERENCES app.onec_export_batches(id);
ALTER TABLE app.onec_agent_tasks         ADD CONSTRAINT fk_oat_item              FOREIGN KEY (item_id)               REFERENCES app.onec_export_items(id);
ALTER TABLE app.onec_agent_tasks         ADD CONSTRAINT fk_oat_ref_create        FOREIGN KEY (ref_create_request_id) REFERENCES app.onec_ref_create_requests(id);
ALTER TABLE app.onec_agent_tasks         ADD CONSTRAINT fk_oat_reconciliation    FOREIGN KEY (reconciliation_id)     REFERENCES app.onec_reconciliations(id);
```

RLS uchligi — 4.2-bo'lim, grantlar — 4.4, `updated_at` trigger'lari — 2.10, `SECURITY DEFINER` funksiyalar — 4.5.

---

## 3. Registrlar: append-only mahkamlash

Haqiqiy append-only jadvallar — **faqat** `stock_moves`, `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves`, `audit_log`, `sync_receipts`, `doc_approvals` (tasdiq jurnali), `auth.login_attempts`. Ikki qatlamli himoya: (a) `erp_app`dan `UPDATE`/`DELETE` huquqi **olib tashlanadi**, (b) trigger — kod xatosi yoki boshqa (masalan `erp_migrator`) rol bilan ulanish ham qatorni o'zgartira olmasligi uchun.

`auth.login_attempts` — append-only, lekin saqlash muddati bor (90 kun — standart, sozlanadi, `14-autentifikatsiya-oauth2.md` §19). `erp_app`ning `auth.*`ga umuman huquqi yo'q (4.4); `erp_system`dan `UPDATE` olib tashlanadi, `DELETE` esa faqat saqlash muddati tozalovchisi `app.auth_purge_login_attempts(p_older_than interval)` (4.5) orqali: `app.login_attempts_guard()` trigger'i `UPDATE`ni har doim, `DELETE`ni esa `current_user <> 'erp_system'` bo'lsa rad etadi. `erp_system` — `NOLOGIN`, ya'ni `current_user = 'erp_system'` faqat `SECURITY DEFINER` funksiya ichida bo'ladi; `auth.login_attempts`dan `DELETE` qiladigan yagona funksiya — `auth_purge_login_attempts`. Uni har kuni scheduler job'i chaqiradi (`23-backend-arxitekturasi.md` §4).

`app.forbid_mutation()` — `0001` da. `REVOKE` + trigger har jadval uchun jadval mavjud bo'lgan revizionda qo'llanadi (jadvalni yaratgan revizionda yoki undan keyin): `0015` — beshta registr, `doc_approvals` (0010 da yaratiladi) va `auth.login_attempts` (0003 da yaratiladi; `app.login_attempts_guard()` ham shu yerda); `0022` — `sync_receipts`; `0024` — `audit_log`. `0026`dagi sxema bo'yicha GRANT'lar bu `REVOKE`larni bekor qiladi, shuning uchun `0026` ularni qayta qo'llaydi (4.4-bo'lim).

```sql
CREATE OR REPLACE FUNCTION app.forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'append-only jadval: % operatsiyasi taqiqlangan (jadval: %)', TG_OP, TG_TABLE_NAME
    USING ERRCODE = 'integrity_constraint_violation';
END;
$$;
```

```sql
-- 0015 registers
DO $$
DECLARE
  t TEXT;
  append_only_tables TEXT[] := ARRAY[
    'app.stock_moves', 'app.debt_moves', 'app.cash_moves',
    'app.ledger_entries', 'app.vat_moves', 'app.doc_approvals'
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

-- auth.login_attempts: UPDATE — hech kimga; DELETE — faqat erp_system (SECURITY DEFINER app.auth_purge_login_attempts)
CREATE OR REPLACE FUNCTION app.login_attempts_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' AND current_user = 'erp_system' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'append-only jadval: % operatsiyasi taqiqlangan (jadval: %)', TG_OP, TG_TABLE_NAME
    USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

REVOKE UPDATE ON auth.login_attempts FROM erp_system;
CREATE TRIGGER trg_login_attempts_guard BEFORE UPDATE OR DELETE ON auth.login_attempts
  FOR EACH ROW EXECUTE FUNCTION app.login_attempts_guard();
```

```sql
-- 0022 integration_sync
REVOKE UPDATE, DELETE ON app.sync_receipts FROM erp_app;
CREATE TRIGGER trg_no_update_delete BEFORE UPDATE OR DELETE ON app.sync_receipts
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
```

```sql
-- 0024 audit_periods
REVOKE UPDATE, DELETE ON app.audit_log FROM erp_app;
CREATE TRIGGER trg_no_update_delete BEFORE UPDATE OR DELETE ON app.audit_log
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
```

`stock_lots`/`avg_costs`/`stock_balances`/`debt_balances` — **UPDATE ruxsat etilgan** (balans-keshi, 2.7-bo'limdagi upsert naqshi); ularning yaxlitligi FK + `CHECK (qty_left >= 0)` kabi cheklovlar va posting xizmatining `FOR UPDATE` qulfi bilan ta'minlanadi, DB darajasidagi `REVOKE` emas. `fiscal_receipts`, `marking_codes`, `outbox_jobs`, `recost_jobs`, `import_jobs`, `einvoices`, `ettn_documents`, `state_reports`, `state_report_diffs`, `refresh_tokens`, `sessions`, `otp_challenges`, `approval_requests`, `payment_checkouts`, `card_terminal_transactions`, `card_terminal_settlements`, `ai_ocr_jobs`, `ledger_adjustments` — holat-mashinasi jadvallari, `UPDATE` tabiiy ravishda kerak (status o'tishlari), append-only emas. 1C jadvallaridan `onec_task_results`, `onec_events`, `onec_agent_logs` — ilova faqat `INSERT` qiladi, lekin saqlash muddati tugagach `onec_cleanup` job'i `DELETE` qiladi (2.11-bo'lim jadvali), shuning uchun append-only ro'yxatida emas.

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

`current_setting(..., true)` parametr o'rnatilmagan bo'lsa xato tashlamay `NULL` qaytaradi; `NULLIF(...,'')` bo'sh satrni ham `NULL`ga aylantiradi — natijada kontekstsiz so'rov **hech qanday qator qaytarmaydi** (fail-closed, `15-xavfsizlik-va-audit.md` §3.2).

### 4.2 Siyosat shabloni — barcha oddiy tenant jadvallari

```sql
DO $$
DECLARE
  r RECORD;
  excluded_tables TEXT[] := ARRAY['tenants', 'users', 'memberships']; -- maxsus siyosat, pastda
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

2.11-bo'lim jadvallari — hammasi oddiy `tenant_isolation` (maxsus siyosat yo'q; `auth.onec_device_authorizations` — RLS'siz, 6.2 istisnosi). `0028 store_agent` — 3 jadval:

```sql
-- 0028 store_agent
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['onec_agents','onec_agent_tasks','onec_task_results'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE app.%I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY tenant_isolation ON app.%I USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id())', t);
  END LOOP;
END $$;
```

`0029 onec_integration` — 15 jadval:

```sql
-- 0029 onec_integration
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['onec_bases','onec_settings','onec_branch_bindings','onec_metadata_snapshots',
    'onec_catalog_items','onec_mappings','onec_value_mappings','onec_ref_create_requests','onec_export_batches',
    'onec_export_items','onec_export_item_sources','onec_object_refs',
    'onec_reconciliations','onec_events','onec_agent_logs'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE app.%I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY tenant_isolation ON app.%I USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id())', t);
  END LOOP;
END $$;
```

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

`plans`, `addons`, `units`, `oauth_clients`, `signing_keys`, `label_templates`, `marking_product_groups`, `terms_versions`, `turnover_tax_rates`, `fx_rates`, `card_bin_rules` — `tenant_id`siz, RLS **yoqilmaydi**; o'rniga faqat `SELECT` beriladi (yozish — faqat `erp_migrator`/admin yo'li orqali). `platform_admins` — `erp_app`ga **umuman** grant yo'q (platforma admin BFF alohida, yuqori ishonchli yo'l orqali ishlaydi, `15-xavfsizlik-va-audit.md` §3.4).

```sql
GRANT SELECT ON platform.plans, platform.addons, platform.units,
                platform.oauth_clients, platform.signing_keys, platform.label_templates,
                platform.marking_product_groups, platform.terms_versions, platform.turnover_tax_rates,
                platform.card_bin_rules
  TO erp_app;
-- kurs scheduler'i (erp_app ulanishi) yozadi (qaror #55)
GRANT SELECT, INSERT, UPDATE ON platform.fx_rates TO erp_app;
-- platform.platform_admins — erp_app'ga HECH QANDAY grant yo'q
REVOKE ALL ON platform.platform_admins FROM erp_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO erp_app;

REVOKE ALL ON SCHEMA auth FROM PUBLIC, erp_app;
GRANT ALL ON ALL TABLES IN SCHEMA auth TO erp_system;

-- yuqoridagi ikki sxema-GRANT append-only jadvallardagi REVOKE'larni (3-bo'lim, 0015/0022/0024) bekor qiladi —
-- shuning uchun 0026 ularni darhol qayta qo'llaydi (tartib muhim: GRANT'lardan keyin)
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'app.stock_moves', 'app.debt_moves', 'app.cash_moves', 'app.ledger_entries', 'app.vat_moves',
    'app.audit_log', 'app.sync_receipts', 'app.doc_approvals'
  ] LOOP
    EXECUTE format('REVOKE UPDATE, DELETE ON %s FROM erp_app', t);
  END LOOP;
END $$;
-- auth.login_attempts: DELETE erp_system'da qoladi — uni trigger faqat auth_purge_login_attempts ichida o'tkazadi (3-bo'lim)
REVOKE UPDATE ON auth.login_attempts FROM erp_system;
```

`ON ALL TABLES IN SCHEMA` grantlari faqat ijro paytidagi jadvallarga ta'sir qiladi va keyingi revizionda qayta ishlatilmaydi (ular append-only jadvallardagi `REVOKE UPDATE, DELETE`ni qaytarib bergani uchun `0026` `REVOKE`larni yuqorida qayta qo'llaydi; trigger'lar GRANT'dan ta'sirlanmaydi).

`public.alembic_version` — Alembic o'zi yaratadi (revizion emas). `/health/ready` sxema versiyasini `erp_app` ulanishi bilan o'qiydi (`23-backend-arxitekturasi.md` §8), shuning uchun `alembic/env.py` har `alembic upgrade`dan keyin, `erp_app` roli mavjud bo'lsa, `GRANT SELECT ON public.alembic_version TO erp_app` bajaradi (idempotent; boshqa huquq berilmaydi). `0028 store_agent` va `0029 onec_integration` grantlarni jadval nomi bilan beradi:

```sql
-- 0028 store_agent
GRANT SELECT, INSERT, UPDATE, DELETE ON app.onec_agents, app.onec_agent_tasks, app.onec_task_results TO erp_app;
GRANT ALL ON auth.onec_device_authorizations TO erp_system; -- erp_app'ga hech qanday grant yo'q
```

```sql
-- 0029 onec_integration
GRANT SELECT, INSERT, UPDATE, DELETE ON
  app.onec_bases, app.onec_settings, app.onec_branch_bindings, app.onec_metadata_snapshots,
  app.onec_catalog_items, app.onec_mappings, app.onec_value_mappings, app.onec_ref_create_requests,
  app.onec_export_batches, app.onec_export_items, app.onec_export_item_sources, app.onec_object_refs,
  app.onec_reconciliations, app.onec_events, app.onec_agent_logs
  TO erp_app;
```

### 4.5 `SECURITY DEFINER` funksiyalar

Faqat shu bo'limdagi funksiyalar tenant-kontekstidan **oldin** yoki undan tashqarida ishlaydigan amallarni qamrab oladi (login, scheduler fan-out, billing/to'lov webhook, ochiq havola, 1C agentini ulash va agent tokeni). Barchasi `erp_system` egaligida, `SET search_path` bilan (search_path hijack'dan himoya — chaqiruvchi sessiyaning `search_path`i e'tiborga olinmaydi).

Funksiyani `erp_migrator` yaratadi, keyin `ALTER FUNCTION … OWNER TO erp_system` bilan topshiradi. Superuser bo'lmagan migrator uchun PostgreSQL ikki shart qo'yadi: migrator yangi egasi rolining a'zosi (`GRANT erp_system TO erp_migrator` — 0-bo'lim bootstrap) va yangi ega funksiya sxemasida `CREATE` huquqiga ega. `erp_system`ga `app` sxemasida doimiy `CREATE` berilmaydi — u faqat egalikni topshiruvchi revizion davomida beriladi: `0027` (yadro revizionlarining oxirgisi) birinchi bayonot sifatida `GRANT`, oxirgi bayonot sifatida `REVOKE` bajaradi; `0028`/`0029` ham o'z funksiyalarini xuddi shu juftlik ichida topshiradi.

```sql
-- 0027 boshida
GRANT CREATE ON SCHEMA app TO erp_system;
```

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

-- tenant kontekstisiz kiruvchi so'rovlar uchun (do'kon to'lov webhook'lari, billing
-- javob yo'li, ochiq hisob-varaq havolasi) — xuddi billing_tenant_by_payment naqshi bilan.
CREATE OR REPLACE FUNCTION app.payments_checkout_by_provider_tx(p_provider text, p_provider_tx_id text)
RETURNS TABLE (tenant_id uuid, checkout_ref uuid, status text) LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT tenant_id, checkout_ref, status FROM app.payment_checkouts
  WHERE provider = p_provider AND provider_tx_id = p_provider_tx_id;
$$;

CREATE OR REPLACE FUNCTION app.payments_checkout_by_ref(p_checkout_ref uuid)
RETURNS TABLE (tenant_id uuid, provider text, status text, amount numeric) LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT tenant_id, provider, status, amount FROM app.payment_checkouts WHERE checkout_ref = p_checkout_ref;
$$;

CREATE OR REPLACE FUNCTION app.billing_payment_by_id(p_payment_id uuid)
RETURNS TABLE (tenant_id uuid, status text, amount numeric) LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT tenant_id, status, amount FROM app.billing_payments WHERE id = p_payment_id;
$$;

CREATE OR REPLACE FUNCTION app.public_statement_by_token(p_token_hash text)
RETURNS TABLE (tenant_id uuid, counterparty_id uuid, expires_at timestamptz) LANGUAGE sql SECURITY DEFINER
SET search_path = app, pg_temp AS $$
  SELECT tenant_id, counterparty_id, expires_at FROM app.counterparty_statement_links
  WHERE token_hash = p_token_hash AND revoked_at IS NULL AND expires_at > now();
$$;

-- funksiyalar ichida o'qiladigan app jadvallari (erp_system — BYPASSRLS, lekin jadval grant'i baribir kerak; nomma-nom)
GRANT SELECT ON app.users, app.memberships, app.tenants, app.subscriptions, app.billing_payments,
                app.payment_checkouts, app.counterparty_statement_links
  TO erp_system;

ALTER FUNCTION app.auth_find_user_by_phone(text) OWNER TO erp_system;
ALTER FUNCTION app.auth_list_memberships(uuid) OWNER TO erp_system;
ALTER FUNCTION app.list_active_tenant_ids() OWNER TO erp_system;
ALTER FUNCTION app.billing_tenant_by_payment(text, text) OWNER TO erp_system;
ALTER FUNCTION app.payments_checkout_by_provider_tx(text, text) OWNER TO erp_system;
ALTER FUNCTION app.payments_checkout_by_ref(uuid) OWNER TO erp_system;
ALTER FUNCTION app.billing_payment_by_id(uuid) OWNER TO erp_system;
ALTER FUNCTION app.public_statement_by_token(text) OWNER TO erp_system;

REVOKE ALL ON FUNCTION app.auth_find_user_by_phone(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_list_memberships(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.list_active_tenant_ids() FROM PUBLIC;
REVOKE ALL ON FUNCTION app.billing_tenant_by_payment(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.payments_checkout_by_provider_tx(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.payments_checkout_by_ref(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.billing_payment_by_id(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.public_statement_by_token(text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.auth_find_user_by_phone(text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_list_memberships(uuid) TO erp_app;
GRANT EXECUTE ON FUNCTION app.list_active_tenant_ids() TO erp_app;
GRANT EXECUTE ON FUNCTION app.billing_tenant_by_payment(text, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.payments_checkout_by_provider_tx(text, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.payments_checkout_by_ref(uuid) TO erp_app;
GRANT EXECUTE ON FUNCTION app.billing_payment_by_id(uuid) TO erp_app;
GRANT EXECUTE ON FUNCTION app.public_statement_by_token(text) TO erp_app;
```
Telegram ulash kodi (20-api-moliya-admin.md #66) — DB emas, Redis `tg_link:{code}` (TTL 10 daqiqa).

`14-autentifikatsiya-oauth2.md` §7, §16.1.3, §19 dagi token oqimlari uchun 4 ta `SECURITY DEFINER` funksiya — xuddi shu naqsh bilan (`erp_system` egaligida, `SET search_path = app, auth, pg_temp`), `auth.*` jadvallarni yozadi/o'qiydi. AS yozuvlari to'liq ro'yxati — shu va keyingi blokda (14 §19 bilan aynan); CI ro'yxati (§6.2) hammasini tekshiradi.

```sql
-- Authorization Code — bir martalik iste'mol (atomik): yaroqli bo'lsa used_at qo'yiladi va qator qaytadi,
-- aks holda bo'sh natija (AS: invalid_grant). PKCE tekshiruvi (code_verifier → S256) ilovada.
CREATE OR REPLACE FUNCTION app.auth_consume_code(p_code_hash text)
RETURNS TABLE (client_id uuid, user_id uuid, tenant_id uuid, code_challenge text,
               code_challenge_method text, redirect_uri text, scope text)
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  UPDATE auth.authorization_codes c
     SET used_at = now()
   WHERE c.code_hash = p_code_hash AND c.used_at IS NULL AND c.expires_at > now()
  RETURNING c.client_id, c.user_id, c.tenant_id, c.code_challenge, c.code_challenge_method, c.redirect_uri, c.scope;
$$;

-- Refresh rotatsiyasi (14 §7): outcome —
--   'rotated'      — eski token used_at, yangi token yozildi (p_new_token_hash), sessiya yangi tokenga ko'chdi;
--   'grace_replay' — eski token ≤ 30 s oldin ishlatilgan va vorisi hali ishlatilmagan: hech narsa o'zgarmaydi,
--                    voris id qaytadi (AS javobni single-flight keshidan beradi; 14 §7, standart 30 s);
--   'reuse_revoked'— qayta ishlatish: butun oila va sessiyalar bekor qilinadi (audit: refresh_token_reuse_detected);
--   'invalid'      — topilmadi / muddati o'tgan / bekor qilingan.
-- suspended_at bo'lsa ham 'rotated' qaytadi, `suspended=true` — AS faqat scope=sync.drain beradi (14 §16.4).
-- Yangi token eski tokenning suspended_at va revoked_reason ('subscription') qiymatlarini oladi — lokaut paytida
-- (sync.drain) aylantirilgan token ham to'lovdan keyin auth_suspend_tenant(.., false) bilan tiklanadi.
CREATE OR REPLACE FUNCTION app.auth_rotate_refresh(p_token_hash text, p_new_token_hash text, p_new_expires_at timestamptz)
RETURNS TABLE (outcome text, refresh_token_id uuid, family_id uuid, client_id uuid, user_id uuid,
               tenant_id uuid, device_id uuid, scope text, suspended boolean)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  r   auth.refresh_tokens%ROWTYPE;
  nxt auth.refresh_tokens%ROWTYPE;
  new_id uuid;
BEGIN
  SELECT * INTO r FROM auth.refresh_tokens t WHERE t.token_hash = p_token_hash FOR UPDATE;
  IF NOT FOUND OR r.revoked_at IS NOT NULL OR r.expires_at <= now() THEN
    RETURN QUERY SELECT 'invalid'::text, NULL::uuid, NULL::uuid, NULL::uuid, NULL::uuid, NULL::uuid, NULL::uuid, NULL::text, NULL::boolean;
    RETURN;
  END IF;
  IF r.used_at IS NOT NULL THEN
    SELECT * INTO nxt FROM auth.refresh_tokens t WHERE t.id = r.replaced_by_id;
    IF now() - r.used_at <= interval '30 seconds' AND nxt.id IS NOT NULL AND nxt.used_at IS NULL AND nxt.revoked_at IS NULL THEN
      RETURN QUERY SELECT 'grace_replay'::text, nxt.id, nxt.family_id, nxt.client_id, nxt.user_id, nxt.tenant_id,
                          nxt.device_id, nxt.scope, (nxt.suspended_at IS NOT NULL);
      RETURN;
    END IF;
    UPDATE auth.refresh_tokens t SET revoked_at = now(), revoked_reason = 'reuse_detected'
     WHERE t.family_id = r.family_id AND t.revoked_at IS NULL;
    UPDATE auth.sessions s SET revoked_at = now(), revoked_reason = 'reuse_detected'
     WHERE s.revoked_at IS NULL
       AND s.current_refresh_token_id IN (SELECT t.id FROM auth.refresh_tokens t WHERE t.family_id = r.family_id);
    RETURN QUERY SELECT 'reuse_revoked'::text, r.id, r.family_id, r.client_id, r.user_id, r.tenant_id, r.device_id, r.scope, NULL::boolean;
    RETURN;
  END IF;
  INSERT INTO auth.refresh_tokens (token_hash, family_id, client_id, user_id, tenant_id, device_id, scope,
                                   expires_at, suspended_at, revoked_reason)
  VALUES (p_new_token_hash, r.family_id, r.client_id, r.user_id, r.tenant_id, r.device_id, r.scope,
          p_new_expires_at, r.suspended_at, r.revoked_reason)
  RETURNING id INTO new_id;
  UPDATE auth.refresh_tokens t SET used_at = now(), replaced_by_id = new_id WHERE t.id = r.id;
  UPDATE auth.sessions s SET current_refresh_token_id = new_id, last_seen_at = now()
   WHERE s.current_refresh_token_id = r.id AND s.revoked_at IS NULL;
  RETURN QUERY SELECT 'rotated'::text, new_id, r.family_id, r.client_id, r.user_id, r.tenant_id, r.device_id,
                      r.scope, (r.suspended_at IS NOT NULL);
END;
$$;

-- Tenantning barcha sessiya/refresh tokenlarini to'liq bekor qilish (tenant yopilishi, xavfsizlik hodisasi).
CREATE OR REPLACE FUNCTION app.auth_revoke_tenant(p_tenant_id uuid, p_reason text)
RETURNS void
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  UPDATE auth.refresh_tokens SET revoked_at = now(), revoked_reason = p_reason
   WHERE tenant_id = p_tenant_id AND revoked_at IS NULL;
  UPDATE auth.sessions SET revoked_at = now(), revoked_reason = p_reason
   WHERE tenant_id = p_tenant_id AND revoked_at IS NULL;
$$;

-- Obuna lokauti (14 §16.1.3): p_suspend=true — refresh_tokens.suspended_at=now(), revoked_reason='subscription'
-- (to'liq bekor emas); p_suspend=false — to'lovdan keyin tozalash (§16.1.5): to'xtatilgan token suspended_at
-- bo'yicha topiladi. sessions o'zgarmaydi — kirish Redis sub_status orqali to'xtaydi.
CREATE OR REPLACE FUNCTION app.auth_suspend_tenant(p_tenant_id uuid, p_suspend boolean)
RETURNS void
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  UPDATE auth.refresh_tokens
     SET suspended_at   = CASE WHEN p_suspend THEN now() ELSE NULL END,
         revoked_reason = CASE WHEN p_suspend THEN 'subscription' ELSE NULL END
   WHERE tenant_id = p_tenant_id AND revoked_at IS NULL
     AND (CASE WHEN p_suspend THEN suspended_at IS NULL ELSE suspended_at IS NOT NULL END);
$$;

ALTER FUNCTION app.auth_consume_code(text) OWNER TO erp_system;
ALTER FUNCTION app.auth_rotate_refresh(text, text, timestamptz) OWNER TO erp_system;
ALTER FUNCTION app.auth_revoke_tenant(uuid, text) OWNER TO erp_system;
ALTER FUNCTION app.auth_suspend_tenant(uuid, boolean) OWNER TO erp_system;
REVOKE ALL ON FUNCTION app.auth_consume_code(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_rotate_refresh(text, text, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_revoke_tenant(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_suspend_tenant(uuid, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.auth_consume_code(text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_rotate_refresh(text, text, timestamptz) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_revoke_tenant(uuid, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_suspend_tenant(uuid, boolean) TO erp_app;
```

AS yozuvchi va sessiya funksiyalari (`14-autentifikatsiya-oauth2.md` §1, §2, §4, §7, §12, §16, §18, §19, §20) — 17 ta, naqsh yuqoridagi bilan bir xil; `erp_app` `auth.*` jadvallariga faqat shu bo'limdagi funksiyalar orqali kiradi. `auth_lookup_refresh` va `auth_revoke_refresh_family` — `/oauth/revoke` (RFC 7009) va `/oauth/introspect` (RFC 7662) uchun refresh tokenni xeshi bo'yicha topish/bekor qilish; `auth_purge_login_attempts` — `login_attempts` saqlash muddati (3-bo'lim).

```sql
-- Authorization Code berish (14 §4): TTL standart 60 s.
CREATE OR REPLACE FUNCTION app.auth_issue_code(
  p_code_hash text, p_client_id uuid, p_user_id uuid, p_tenant_id uuid, p_code_challenge text,
  p_redirect_uri text, p_scope text, p_ttl_s int
) RETURNS void
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  INSERT INTO auth.authorization_codes
    (code_hash, client_id, user_id, tenant_id, code_challenge, code_challenge_method, redirect_uri, scope, expires_at)
  VALUES
    (p_code_hash, p_client_id, p_user_id, p_tenant_id, p_code_challenge, 'S256', p_redirect_uri, p_scope,
     now() + make_interval(secs => COALESCE(p_ttl_s, 60)));
$$;

-- Birinchi token juftligi (code almashinuvi yoki login): yangi refresh oilasi; p_with_session=true (BFF mijozlari) —
-- sessions qatori ham (current_refresh_token_id = shu token). Android (public client) — false, session_id = NULL.
CREATE OR REPLACE FUNCTION app.auth_issue_tokens(
  p_user_id uuid, p_tenant_id uuid, p_client_id uuid, p_device_id uuid, p_refresh_token_hash text,
  p_refresh_expires_at timestamptz, p_scope text, p_with_session boolean, p_idle_expires_at timestamptz,
  p_absolute_expires_at timestamptz, p_ip inet, p_user_agent text
) RETURNS TABLE (session_id uuid, refresh_token_id uuid, family_id uuid)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
#variable_conflict use_column
DECLARE
  v_rt  uuid := app.uuidv7();
  v_fam uuid := app.uuidv7();
  v_sid uuid;
BEGIN
  INSERT INTO auth.refresh_tokens (id, token_hash, family_id, client_id, user_id, tenant_id, device_id, scope, expires_at)
  VALUES (v_rt, p_refresh_token_hash, v_fam, p_client_id, p_user_id, p_tenant_id, p_device_id, p_scope, p_refresh_expires_at);
  IF p_with_session THEN
    INSERT INTO auth.sessions (user_id, tenant_id, client_id, device_id, current_refresh_token_id,
                               idle_expires_at, absolute_expires_at, ip, user_agent)
    VALUES (p_user_id, p_tenant_id, p_client_id, p_device_id, v_rt,
            p_idle_expires_at, p_absolute_expires_at, p_ip, p_user_agent)
    RETURNING id INTO v_sid;
  END IF;
  RETURN QUERY SELECT v_sid, v_rt, v_fam;
END;
$$;

-- BFF __Host-sid bo'yicha sessiyani o'qish (Redis keshi bo'sh bo'lganda).
CREATE OR REPLACE FUNCTION app.auth_session_by_id(p_session_id uuid)
RETURNS TABLE (session_id uuid, user_id uuid, tenant_id uuid, client_id uuid, device_id uuid,
               current_refresh_token_id uuid, idle_expires_at timestamptz, absolute_expires_at timestamptz,
               revoked_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT s.id, s.user_id, s.tenant_id, s.client_id, s.device_id, s.current_refresh_token_id,
         s.idle_expires_at, s.absolute_expires_at, s.revoked_at
  FROM auth.sessions s
  WHERE s.id = p_session_id;
$$;

-- Sliding idle: last_seen_at = now(); idle_expires_at absolute_expires_at dan oshmaydi.
CREATE OR REPLACE FUNCTION app.auth_touch_session(p_session_id uuid, p_idle_expires_at timestamptz)
RETURNS void
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  UPDATE auth.sessions s
     SET last_seen_at = now(), idle_expires_at = LEAST(p_idle_expires_at, s.absolute_expires_at)
   WHERE s.id = p_session_id AND s.revoked_at IS NULL;
$$;

-- OTP yaratish (TTL standart 300 s, qaror #54); shu (phone, purpose) dagi oldingi tasdiqlanmagan challenge'lar yopiladi.
CREATE OR REPLACE FUNCTION app.auth_otp_create(
  p_phone text, p_purpose text, p_channel text, p_code_hash text, p_ttl_s int
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  v_id uuid;
BEGIN
  UPDATE auth.otp_challenges o
     SET expires_at = now()
   WHERE o.phone = p_phone AND o.purpose = p_purpose AND o.verified_at IS NULL AND o.expires_at > now();
  INSERT INTO auth.otp_challenges (phone, purpose, channel, code_hash, expires_at)
  VALUES (p_phone, p_purpose, p_channel, p_code_hash, now() + make_interval(secs => COALESCE(p_ttl_s, 300)))
  RETURNING id INTO v_id;
  RETURN v_id;
END;
$$;

-- OTP tekshiruvi: 'ok' | 'invalid' (attempts += 1; challenge topilmasa ham 'invalid') | 'expired' | 'locked' | 'used'.
CREATE OR REPLACE FUNCTION app.auth_otp_verify(p_challenge_id uuid, p_code_hash text)
RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  r auth.otp_challenges%ROWTYPE;
BEGIN
  SELECT * INTO r FROM auth.otp_challenges o WHERE o.id = p_challenge_id FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'invalid';
  END IF;
  IF r.verified_at IS NOT NULL THEN
    RETURN 'used';
  END IF;
  IF r.attempts >= r.max_attempts THEN
    RETURN 'locked';
  END IF;
  IF r.expires_at <= now() THEN
    RETURN 'expired';
  END IF;
  IF r.code_hash = p_code_hash THEN
    UPDATE auth.otp_challenges o SET verified_at = now() WHERE o.id = r.id;
    RETURN 'ok';
  END IF;
  UPDATE auth.otp_challenges o SET attempts = o.attempts + 1 WHERE o.id = r.id;
  RETURN 'invalid';
END;
$$;

-- Login urinishi qaydi (14 §2, qaror #54): muvaffaqiyatda hisoblagich nolga; xatoda +1, 15 daqiqalik oynada
-- kamida 5 ta xato bo'lsa har 5-xatoda progressiv blok 1 → 5 → 15 → 60 daqiqa. Foydalanuvchi topilmasa — NULL'lar.
CREATE OR REPLACE FUNCTION app.auth_record_login(
  p_phone text, p_ip inet, p_success boolean, p_failure_reason text
) RETURNS TABLE (failed_login_count int, locked_until timestamptz)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
#variable_conflict use_column
DECLARE
  v_user   uuid;
  v_fail   int;
  v_recent int;
  v_lock   timestamptz;
BEGIN
  INSERT INTO auth.login_attempts (phone, ip, success, failure_reason)
  VALUES (p_phone, p_ip, p_success, CASE WHEN p_success THEN NULL ELSE p_failure_reason END);

  SELECT u.id INTO v_user FROM app.users u WHERE u.phone = p_phone;
  IF v_user IS NULL THEN
    RETURN QUERY SELECT NULL::int, NULL::timestamptz;
    RETURN;
  END IF;

  IF p_success THEN
    UPDATE auth.user_credentials c
       SET failed_login_count = 0, locked_until = NULL, updated_at = now()
     WHERE c.user_id = v_user;
    RETURN QUERY SELECT 0, NULL::timestamptz;
    RETURN;
  END IF;

  UPDATE auth.user_credentials c
     SET failed_login_count = c.failed_login_count + 1, updated_at = now()
   WHERE c.user_id = v_user
  RETURNING c.failed_login_count, c.locked_until INTO v_fail, v_lock;
  IF NOT FOUND THEN
    RETURN QUERY SELECT NULL::int, NULL::timestamptz;
    RETURN;
  END IF;

  SELECT count(*) INTO v_recent
    FROM auth.login_attempts a
   WHERE a.phone = p_phone AND NOT a.success AND a.created_at > now() - interval '15 minutes';

  IF v_recent >= 5 AND v_fail % 5 = 0 THEN
    v_lock := now() + CASE LEAST(v_fail / 5, 4)
                        WHEN 1 THEN interval '1 minute'
                        WHEN 2 THEN interval '5 minutes'
                        WHEN 3 THEN interval '15 minutes'
                        ELSE interval '60 minutes' END;
    UPDATE auth.user_credentials c SET locked_until = v_lock WHERE c.user_id = v_user;
  END IF;
  RETURN QUERY SELECT v_fail, v_lock;
END;
$$;

-- Parol/PIN o'rnatish (UPSERT): NULL argument — o'sha maydon o'zgarmaydi; berilganda *_updated_at = now(),
-- mos must_change_* = false.
CREATE OR REPLACE FUNCTION app.auth_set_credentials(p_user_id uuid, p_password_hash text, p_pin_hash text)
RETURNS void
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  INSERT INTO auth.user_credentials AS c
    (user_id, password_hash, password_updated_at, pin_hash, pin_updated_at)
  VALUES
    (p_user_id, p_password_hash, CASE WHEN p_password_hash IS NOT NULL THEN now() END,
     p_pin_hash, CASE WHEN p_pin_hash IS NOT NULL THEN now() END)
  ON CONFLICT (user_id) DO UPDATE SET
    password_hash        = COALESCE(p_password_hash, c.password_hash),
    password_updated_at  = CASE WHEN p_password_hash IS NOT NULL THEN now() ELSE c.password_updated_at END,
    must_change_password = CASE WHEN p_password_hash IS NOT NULL THEN false ELSE c.must_change_password END,
    pin_hash             = COALESCE(p_pin_hash, c.pin_hash),
    pin_updated_at       = CASE WHEN p_pin_hash IS NOT NULL THEN now() ELSE c.pin_updated_at END,
    must_change_pin      = CASE WHEN p_pin_hash IS NOT NULL THEN false ELSE c.must_change_pin END,
    updated_at           = now();
$$;

-- Admin tomonidan tiklash: tanlangan hash NULL, must_change_* = true; parol tiklansa foydalanuvchining barcha
-- sessiya/refresh tokenlari bekor qilinadi (revoked_reason='credential_reset').
CREATE OR REPLACE FUNCTION app.auth_reset_credentials(p_user_id uuid, p_reset_password boolean, p_reset_pin boolean)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
BEGIN
  UPDATE auth.user_credentials c
     SET password_hash        = CASE WHEN p_reset_password THEN NULL ELSE c.password_hash END,
         must_change_password = CASE WHEN p_reset_password THEN true ELSE c.must_change_password END,
         pin_hash             = CASE WHEN p_reset_pin THEN NULL ELSE c.pin_hash END,
         must_change_pin      = CASE WHEN p_reset_pin THEN true ELSE c.must_change_pin END,
         updated_at           = now()
   WHERE c.user_id = p_user_id;
  IF p_reset_password THEN
    UPDATE auth.refresh_tokens t SET revoked_at = now(), revoked_reason = 'credential_reset'
     WHERE t.user_id = p_user_id AND t.revoked_at IS NULL;
    UPDATE auth.sessions s SET revoked_at = now(), revoked_reason = 'credential_reset'
     WHERE s.user_id = p_user_id AND s.revoked_at IS NULL;
  END IF;
END;
$$;

-- /auth/pin/verify uchun.
CREATE OR REPLACE FUNCTION app.auth_get_pin_hash(p_user_id uuid)
RETURNS TABLE (pin_hash text, must_change_pin boolean)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT c.pin_hash, c.must_change_pin FROM auth.user_credentials c WHERE c.user_id = p_user_id;
$$;

-- Bitta sessiyani va uning joriy refresh oilasini bekor qilish (logout, admin).
CREATE OR REPLACE FUNCTION app.auth_revoke_session(p_session_id uuid, p_reason text)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  v_rt uuid;
BEGIN
  UPDATE auth.sessions s SET revoked_at = now(), revoked_reason = p_reason
   WHERE s.id = p_session_id AND s.revoked_at IS NULL
  RETURNING s.current_refresh_token_id INTO v_rt;
  IF v_rt IS NOT NULL THEN
    UPDATE auth.refresh_tokens t SET revoked_at = now(), revoked_reason = p_reason
     WHERE t.family_id = (SELECT f.family_id FROM auth.refresh_tokens f WHERE f.id = v_rt)
       AND t.revoked_at IS NULL;
  END IF;
END;
$$;

-- Foydalanuvchining (p_tenant_id berilsa — faqat shu tenantdagi) barcha sessiya/refresh tokenlarini bekor qilish;
-- qaytaradi — bekor qilingan sessiyalar soni.
CREATE OR REPLACE FUNCTION app.auth_revoke_user(p_user_id uuid, p_tenant_id uuid, p_reason text)
RETURNS int
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  v_n int;
BEGIN
  UPDATE auth.refresh_tokens t SET revoked_at = now(), revoked_reason = p_reason
   WHERE t.user_id = p_user_id AND (p_tenant_id IS NULL OR t.tenant_id = p_tenant_id) AND t.revoked_at IS NULL;
  UPDATE auth.sessions s SET revoked_at = now(), revoked_reason = p_reason
   WHERE s.user_id = p_user_id AND (p_tenant_id IS NULL OR s.tenant_id = p_tenant_id) AND s.revoked_at IS NULL;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN v_n;
END;
$$;

-- GET /admin/users/{id}/sessions — faol (bekor qilinmagan, muddati o'tmagan) sessiyalar.
CREATE OR REPLACE FUNCTION app.auth_list_user_sessions(p_user_id uuid, p_tenant_id uuid)
RETURNS TABLE (session_id uuid, client_id uuid, device_id uuid, created_at timestamptz, last_seen_at timestamptz,
               ip inet, user_agent text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT s.id, s.client_id, s.device_id, s.created_at, s.last_seen_at, s.ip, s.user_agent
  FROM auth.sessions s
  WHERE s.user_id = p_user_id AND (p_tenant_id IS NULL OR s.tenant_id = p_tenant_id)
    AND s.revoked_at IS NULL AND s.idle_expires_at > now() AND s.absolute_expires_at > now()
  ORDER BY s.last_seen_at DESC;
$$;

-- OTP Telegram kanali: telefon bo'yicha faol bog'langan chat (eng oxirgi linked_at); topilmasa NULL → SMS.
CREATE OR REPLACE FUNCTION app.auth_telegram_chat_by_phone(p_phone text)
RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT tl.chat_id
  FROM app.users u
  JOIN app.telegram_links tl ON tl.user_id = u.id
  WHERE u.phone = p_phone AND tl.revoked_at IS NULL
  ORDER BY tl.linked_at DESC
  LIMIT 1;
$$;

-- Refresh token metama'lumoti xeshi bo'yicha (tokenning o'zi emas): AS mijoz bog'lanishini, oilaning mutlaq
-- muddatini (sliding refresh, 14 §7) va unga bog'langan BFF sessiyasini tekshiradi (/oauth/introspect, rotatsiyadan oldin).
CREATE OR REPLACE FUNCTION app.auth_lookup_refresh(p_token_hash text)
RETURNS TABLE (refresh_token_id uuid, family_id uuid, client_id uuid, user_id uuid, tenant_id uuid,
               device_id uuid, scope text, issued_at timestamptz, expires_at timestamptz, used_at timestamptz,
               revoked_at timestamptz, suspended_at timestamptz, family_issued_at timestamptz,
               session_id uuid, session_revoked_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT t.id, t.family_id, t.client_id, t.user_id, t.tenant_id, t.device_id, t.scope, t.issued_at,
         t.expires_at, t.used_at, t.revoked_at, t.suspended_at,
         (SELECT min(f.issued_at) FROM auth.refresh_tokens f WHERE f.family_id = t.family_id),
         s.id, s.revoked_at
  FROM auth.refresh_tokens t
  LEFT JOIN LATERAL (
    SELECT se.id, se.revoked_at
    FROM auth.sessions se
    JOIN auth.refresh_tokens f ON f.id = se.current_refresh_token_id
    WHERE f.family_id = t.family_id
    ORDER BY se.created_at
    LIMIT 1
  ) s ON true
  WHERE t.token_hash = p_token_hash;
$$;

-- RFC 7009: berilgan refresh tokenning butun oilasi va unga bog'langan BFF sessiyasi bekor qilinadi.
-- Qaytaradi — sessiya/foydalanuvchi/tenant (AS Redis sid-revoke keshini yangilaydi, 14 §5); token topilmasa bo'sh.
CREATE OR REPLACE FUNCTION app.auth_revoke_refresh_family(p_token_hash text, p_reason text)
RETURNS TABLE (session_id uuid, user_id uuid, tenant_id uuid, family_id uuid)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
#variable_conflict use_column
DECLARE
  r     auth.refresh_tokens%ROWTYPE;
  v_sid uuid;
BEGIN
  SELECT * INTO r FROM auth.refresh_tokens t WHERE t.token_hash = p_token_hash FOR UPDATE;
  IF NOT FOUND THEN
    RETURN;
  END IF;
  SELECT se.id INTO v_sid
    FROM auth.sessions se
   WHERE se.current_refresh_token_id IN (SELECT f.id FROM auth.refresh_tokens f WHERE f.family_id = r.family_id)
   LIMIT 1;
  UPDATE auth.sessions se SET revoked_at = now(), revoked_reason = p_reason
   WHERE se.id = v_sid AND se.revoked_at IS NULL;
  UPDATE auth.refresh_tokens t SET revoked_at = now(), revoked_reason = p_reason
   WHERE t.family_id = r.family_id AND t.revoked_at IS NULL;
  RETURN QUERY SELECT v_sid, r.user_id, r.tenant_id, r.family_id;
END;
$$;

-- login_attempts saqlash muddati (14 §19; 90 kun — standart, sozlanadi): p_older_than dan eski qatorlar o'chiriladi,
-- qaytaradi — o'chirilganlar soni. 15 daqiqalik blok oynasi (auth_record_login) buzilmasligi uchun kamida 1 kun.
-- Yagona chaqiruvchi — scheduler job'i purge_login_attempts (23 §4); trigger DELETE'ni faqat shu yerda o'tkazadi (3-bo'lim).
CREATE OR REPLACE FUNCTION app.auth_purge_login_attempts(p_older_than interval)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  v_n bigint;
BEGIN
  IF p_older_than IS NULL OR p_older_than < interval '1 day' THEN
    RAISE EXCEPTION 'login_attempts retention must be at least 1 day, got %', p_older_than
      USING ERRCODE = 'invalid_parameter_value';
  END IF;
  DELETE FROM auth.login_attempts a WHERE a.created_at < now() - p_older_than;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN v_n;
END;
$$;

-- funksiyalar ichida o'qiladigan qo'shimcha app jadvali
GRANT SELECT ON app.telegram_links TO erp_system;

ALTER FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int) OWNER TO erp_system;
ALTER FUNCTION app.auth_issue_tokens(uuid, uuid, uuid, uuid, text, timestamptz, text, boolean, timestamptz, timestamptz, inet, text) OWNER TO erp_system;
ALTER FUNCTION app.auth_session_by_id(uuid) OWNER TO erp_system;
ALTER FUNCTION app.auth_touch_session(uuid, timestamptz) OWNER TO erp_system;
ALTER FUNCTION app.auth_otp_create(text, text, text, text, int) OWNER TO erp_system;
ALTER FUNCTION app.auth_otp_verify(uuid, text) OWNER TO erp_system;
ALTER FUNCTION app.auth_record_login(text, inet, boolean, text) OWNER TO erp_system;
ALTER FUNCTION app.auth_set_credentials(uuid, text, text) OWNER TO erp_system;
ALTER FUNCTION app.auth_reset_credentials(uuid, boolean, boolean) OWNER TO erp_system;
ALTER FUNCTION app.auth_get_pin_hash(uuid) OWNER TO erp_system;
ALTER FUNCTION app.auth_revoke_session(uuid, text) OWNER TO erp_system;
ALTER FUNCTION app.auth_revoke_user(uuid, uuid, text) OWNER TO erp_system;
ALTER FUNCTION app.auth_list_user_sessions(uuid, uuid) OWNER TO erp_system;
ALTER FUNCTION app.auth_telegram_chat_by_phone(text) OWNER TO erp_system;
ALTER FUNCTION app.auth_lookup_refresh(text) OWNER TO erp_system;
ALTER FUNCTION app.auth_revoke_refresh_family(text, text) OWNER TO erp_system;
ALTER FUNCTION app.auth_purge_login_attempts(interval) OWNER TO erp_system;

REVOKE ALL ON FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_issue_tokens(uuid, uuid, uuid, uuid, text, timestamptz, text, boolean, timestamptz, timestamptz, inet, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_session_by_id(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_touch_session(uuid, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_otp_create(text, text, text, text, int) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_otp_verify(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_record_login(text, inet, boolean, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_set_credentials(uuid, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_reset_credentials(uuid, boolean, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_get_pin_hash(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_revoke_session(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_revoke_user(uuid, uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_list_user_sessions(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_telegram_chat_by_phone(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_lookup_refresh(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_revoke_refresh_family(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.auth_purge_login_attempts(interval) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_issue_tokens(uuid, uuid, uuid, uuid, text, timestamptz, text, boolean, timestamptz, timestamptz, inet, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_session_by_id(uuid) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_touch_session(uuid, timestamptz) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_otp_create(text, text, text, text, int) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_otp_verify(uuid, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_record_login(text, inet, boolean, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_set_credentials(uuid, text, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_reset_credentials(uuid, boolean, boolean) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_get_pin_hash(uuid) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_revoke_session(uuid, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_revoke_user(uuid, uuid, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_list_user_sessions(uuid, uuid) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_telegram_chat_by_phone(text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_lookup_refresh(text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_revoke_refresh_family(text, text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.auth_purge_login_attempts(interval) TO erp_app;
```

```sql
-- 0027 oxirida (egalik topshirilgach)
REVOKE CREATE ON SCHEMA app FROM erp_system;
```

#### Do'kon agenti va 1C integratsiyasi funksiyalari (`0028 store_agent`, `0029 onec_integration`)

7 ta funksiya — agentni ulash (RFC 8628 device grant, `auth.onec_device_authorizations`), agent tokeni (`private_key_jwt`) va SAQ cron fan-out uchun (`33-1c-integratsiya.md` §5.18, §4.4, §9.2). Naqsh yuqoridagi bilan bir xil: `erp_system` egaligida, `SET search_path = app, auth, pg_temp` (`auth`ga tegmaydiganlarida `app, pg_temp`), `erp_app`ga faqat `EXECUTE`. `0028 store_agent` — `onec_device_auth_start/lookup/approve/poll/deny`, `onec_agent_credentials` (6 ta); `0029 onec_integration` — `onec_tenants_due`.

```sql
-- 0028 store_agent
-- AS POST /oauth/device_authorization: yangi pending yozuv (10 daqiqa).
-- user_code to'qnashsa (uq_onec_device_auth_user_code_pending) — ilova yangi kod bilan qayta chaqiradi.
CREATE OR REPLACE FUNCTION app.onec_device_auth_start(
  p_device_code_hash text, p_user_code text, p_public_jwk jsonb, p_thumbprint text,
  p_machine_hash text, p_pc_name text, p_os text, p_agent_version text, p_ip inet
) RETURNS uuid
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  INSERT INTO auth.onec_device_authorizations
    (device_code_hash, user_code, public_jwk, public_key_thumbprint, machine_hash, pc_name,
     os_version, agent_version, request_ip, expires_at)
  VALUES
    (p_device_code_hash, p_user_code, p_public_jwk, p_thumbprint, p_machine_hash, p_pc_name,
     p_os, p_agent_version, p_ip, now() + interval '10 minutes')
  RETURNING id;
$$;

-- W-03: foydalanuvchi kiritgan kod bo'yicha so'rov kartasi. Faqat pending va muddati o'tmagan; aks holda bo'sh.
-- public_jwk/public_key_thumbprint/machine_hash — W-04 shu qiymatlar bilan onec_agents qatorini yaratadi.
CREATE OR REPLACE FUNCTION app.onec_device_auth_lookup(p_user_code text)
RETURNS TABLE (
  id uuid, pc_name text, os_version text, agent_version text, request_ip inet,
  created_at timestamptz, expires_at timestamptz,
  public_jwk jsonb, public_key_thumbprint text, machine_hash text
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT d.id, d.pc_name, d.os_version, d.agent_version, d.request_ip, d.created_at, d.expires_at,
         d.public_jwk, d.public_key_thumbprint, d.machine_hash
  FROM auth.onec_device_authorizations d
  WHERE d.user_code = p_user_code AND d.status = 'pending' AND d.expires_at > now();
$$;

-- W-04: onec_agents/devices shu tranzaksiyada RLS ostida yaratilgandan keyin chaqiriladi.
-- pending → approved. Agent joriy tenant'da bo'lishi va kaliti so'rovdagi kalit bilan bir xil bo'lishi shart.
-- Natija: 'approved' | 'not_found' (kod yo'q yoki agent/kalit mos emas → 404 ONEC_PAIRING_CODE_INVALID) |
-- 'expired' (→ 409 ONEC_PAIRING_CODE_EXPIRED) | 'used' (allaqachon tasdiqlangan/rad etilgan/iste'mol qilingan → 404 ONEC_PAIRING_CODE_INVALID).
CREATE OR REPLACE FUNCTION app.onec_device_auth_approve(
  p_user_code text, p_tenant_id uuid, p_user_id uuid, p_agent_id uuid
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  r auth.onec_device_authorizations%ROWTYPE;
BEGIN
  IF p_tenant_id IS DISTINCT FROM app.current_tenant_id()
     OR p_user_id IS DISTINCT FROM app.current_user_id() THEN
    RAISE EXCEPTION 'onec_device_auth_approve: tenant/foydalanuvchi konteksti mos emas'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  -- user_code faqat pending orasida noyob — pending birinchi, aks holda eng oxirgisi
  SELECT * INTO r FROM auth.onec_device_authorizations d
   WHERE d.user_code = p_user_code
   ORDER BY (d.status = 'pending') DESC, d.created_at DESC
   LIMIT 1
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'not_found';
  END IF;
  IF r.status = 'expired' OR (r.status = 'pending' AND r.expires_at <= now()) THEN
    UPDATE auth.onec_device_authorizations d SET status = 'expired' WHERE d.id = r.id AND d.status = 'pending';
    RETURN 'expired';
  END IF;
  IF r.status <> 'pending' THEN
    RETURN 'used';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM app.onec_agents a
                 WHERE a.id = p_agent_id AND a.tenant_id = p_tenant_id
                   AND a.public_key_thumbprint = r.public_key_thumbprint) THEN
    RETURN 'not_found';
  END IF;

  UPDATE auth.onec_device_authorizations d
     SET status = 'approved', tenant_id = p_tenant_id, approved_by = p_user_id,
         approved_at = now(), agent_id = p_agent_id
   WHERE d.id = r.id;
  RETURN 'approved';
END;
$$;

-- W-04 "Rad etish": pending → denied; agent poll'i 'denied' oladi (AS: access_denied).
-- Natija: 'denied' | 'not_found' | 'expired' | 'used' (approve bilan bir xil xaritalash).
CREATE OR REPLACE FUNCTION app.onec_device_auth_deny(p_user_code text, p_user_id uuid)
RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  r auth.onec_device_authorizations%ROWTYPE;
BEGIN
  IF app.current_tenant_id() IS NULL OR p_user_id IS DISTINCT FROM app.current_user_id() THEN
    RAISE EXCEPTION 'onec_device_auth_deny: tenant/foydalanuvchi konteksti mos emas'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  SELECT * INTO r FROM auth.onec_device_authorizations d
   WHERE d.user_code = p_user_code
   ORDER BY (d.status = 'pending') DESC, d.created_at DESC
   LIMIT 1
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'not_found';
  END IF;
  IF r.status = 'expired' OR (r.status = 'pending' AND r.expires_at <= now()) THEN
    UPDATE auth.onec_device_authorizations d SET status = 'expired' WHERE d.id = r.id AND d.status = 'pending';
    RETURN 'expired';
  END IF;
  IF r.status <> 'pending' THEN
    RETURN 'used';
  END IF;

  UPDATE auth.onec_device_authorizations d
     SET status = 'denied', tenant_id = app.current_tenant_id()
   WHERE d.id = r.id;
  RETURN 'denied';
END;
$$;

-- AS /oauth/token (grant_type=urn:ietf:params:oauth:grant-type:device_code).
-- Bo'sh natija → invalid_grant. slow_down=true → poll_interval_s dan tez so'raldi (holat o'zgarmaydi).
-- approved → consumed bir martalik: shu chaqiruv status='approved' qaytaradi (token beriladi),
-- keyingilari 'consumed' (invalid_grant). Muddati o'tgan pending/approved → 'expired'.
CREATE OR REPLACE FUNCTION app.onec_device_auth_poll(p_device_code_hash text)
RETURNS TABLE (status text, tenant_id uuid, agent_id uuid, slow_down boolean)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
#variable_conflict use_column
DECLARE
  r      auth.onec_device_authorizations%ROWTYPE;
  v_slow boolean;
  v_new  text;
BEGIN
  SELECT * INTO r FROM auth.onec_device_authorizations d
   WHERE d.device_code_hash = p_device_code_hash
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN;
  END IF;

  v_slow := r.last_poll_at IS NOT NULL
            AND now() - r.last_poll_at < make_interval(secs => r.poll_interval_s);

  IF r.status IN ('pending','approved') AND r.expires_at <= now() THEN
    r.status := 'expired';
  END IF;
  v_new := CASE WHEN r.status = 'approved' AND NOT v_slow THEN 'consumed' ELSE r.status END;

  UPDATE auth.onec_device_authorizations d
     SET last_poll_at = now(), status = v_new
   WHERE d.id = r.id;

  RETURN QUERY SELECT r.status, r.tenant_id, r.agent_id, v_slow;
END;
$$;

-- AS /oauth/token (client_credentials + private_key_jwt): client_id = 'onec-agent:{agent_id}' bo'yicha
-- tenant kontekstisiz agent kalitini topish. status='revoked' bo'lsa AS rad etadi.
CREATE OR REPLACE FUNCTION app.onec_agent_credentials(p_client_id text)
RETURNS TABLE (tenant_id uuid, agent_id uuid, device_id uuid, public_jwk jsonb, status text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
  SELECT a.tenant_id, a.id, a.device_id, a.public_jwk, a.status
  FROM app.onec_agents a
  WHERE a.client_id = p_client_id;
$$;

-- 0028: funksiyalar ichida o'qiladigan app jadvali (erp_system — BYPASSRLS, lekin jadval grant'i baribir kerak)
GRANT SELECT ON app.onec_agents TO erp_system;

ALTER FUNCTION app.onec_device_auth_start(text, text, jsonb, text, text, text, text, text, inet) OWNER TO erp_system;
ALTER FUNCTION app.onec_device_auth_lookup(text) OWNER TO erp_system;
ALTER FUNCTION app.onec_device_auth_approve(text, uuid, uuid, uuid) OWNER TO erp_system;
ALTER FUNCTION app.onec_device_auth_deny(text, uuid) OWNER TO erp_system;
ALTER FUNCTION app.onec_device_auth_poll(text) OWNER TO erp_system;
ALTER FUNCTION app.onec_agent_credentials(text) OWNER TO erp_system;

REVOKE ALL ON FUNCTION app.onec_device_auth_start(text, text, jsonb, text, text, text, text, text, inet) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.onec_device_auth_lookup(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.onec_device_auth_approve(text, uuid, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.onec_device_auth_deny(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.onec_device_auth_poll(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.onec_agent_credentials(text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.onec_device_auth_start(text, text, jsonb, text, text, text, text, text, inet) TO erp_app;
GRANT EXECUTE ON FUNCTION app.onec_device_auth_lookup(text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.onec_device_auth_approve(text, uuid, uuid, uuid) TO erp_app;
GRANT EXECUTE ON FUNCTION app.onec_device_auth_deny(text, uuid) TO erp_app;
GRANT EXECUTE ON FUNCTION app.onec_device_auth_poll(text) TO erp_app;
GRANT EXECUTE ON FUNCTION app.onec_agent_credentials(text) TO erp_app;
```

`0029 onec_integration`:

```sql
-- 0029 onec_integration
-- SAQ cron fan-out (33 §4.4): arxivlanmagan 1C bazasi bor tenantlar;
-- 'sweep' — yana queued/leased vazifasi yoki retry_wait itemi borlar.
CREATE OR REPLACE FUNCTION app.onec_tenants_due(p_kind text)
RETURNS SETOF uuid
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
BEGIN
  IF p_kind IS NULL OR p_kind NOT IN ('schedule','sweep','drift','offline','cleanup') THEN
    RAISE EXCEPTION 'onec_tenants_due: noma''lum tur %', p_kind USING ERRCODE = 'invalid_parameter_value';
  END IF;
  RETURN QUERY
    SELECT DISTINCT b.tenant_id
    FROM app.onec_bases b
    WHERE b.status <> 'archived'
      AND (p_kind <> 'sweep'
           OR EXISTS (SELECT 1 FROM app.onec_agent_tasks t
                      WHERE t.tenant_id = b.tenant_id AND t.status IN ('queued','leased'))
           OR EXISTS (SELECT 1 FROM app.onec_export_items i
                      WHERE i.tenant_id = b.tenant_id AND i.status = 'retry_wait'));
END;
$$;

GRANT SELECT ON app.onec_bases, app.onec_agent_tasks, app.onec_export_items TO erp_system;
ALTER FUNCTION app.onec_tenants_due(text) OWNER TO erp_system;
REVOKE ALL ON FUNCTION app.onec_tenants_due(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.onec_tenants_due(text) TO erp_app;
```

---

## 5. Seed data

### 5.1 Global (bir martalik, barcha tenantlar uchun umumiy)

```sql
INSERT INTO platform.units (code, is_fractional) VALUES
  ('pcs', false), ('kg', true), ('l', true), ('m', true), ('box', false);

INSERT INTO platform.plans (code, price_month, price_year, limits) VALUES
  ('standard', 99000.00, 950400.00, -- 950 400 = 99 000 × 12 × 0,8 (−20% yillik chegirma)
   '{"included_cash_registers": 1, "ai_monthly_tokens": 2500000}'::jsonb);
  -- ai_monthly_tokens — standart, sozlanadi (`22-ai-qatlami.md` §5, 26 #54)

INSERT INTO platform.addons (code, name, price_month) VALUES
  ('extra_register', 'Qo''shimcha virtual kassa', 39000.00);

INSERT INTO platform.marking_product_groups (code, name, acceptance_deadline, legal_ref) VALUES
  ('general',         'Umumiy (boshqa markirovkalangan tovarlar)', '3_business_days', 'VM 833 66–67-band'),
  ('water_beverages', 'Suv va ichimliklar',                        '72_hours',        'VM 631'),
  ('medicines',       'Dori vositalari',                           '72_hours',        'VM 149'),
  ('vegetable_oil',   'O''simlik yog''i (pilot)',                  '72_hours',        'VM 23');

-- aylanma solig'i stavkalari (13 §4.3) — stavka o'zgarsa yangi valid_from qatori qo'shiladi
INSERT INTO platform.turnover_tax_rates (code, rate_pct, valid_from) VALUES
  ('retail_city_100k_plus',  4.00, '2026-01-01'),
  ('retail_other',           2.00, '2026-01-01'),
  ('retail_remote_mountain', 1.00, '2026-01-01'),
  ('general',                4.00, '2026-01-01'),
  ('tobacco',                4.00, '2026-01-01'),
  ('sole_proprietor',        1.00, '2026-01-01');

-- kamida bitta standart yorliq shabloni
INSERT INTO platform.label_templates (code, name, width_mm, height_mm, fields) VALUES
  ('58x40_price', '58×40 narx yorlig''i', 58.00, 40.00,
   '{"fields": ["product_name", "price", "barcode"]}'::jsonb);

INSERT INTO platform.oauth_clients (client_id, client_type, name, allowed_grant_types, allowed_scopes, status) VALUES
  ('web-bff',      'confidential', 'Veb BFF (back-office + veb-kassa)', ARRAY['authorization_code','refresh_token'], ARRAY['*','sync','pos'], 'pending_secret'),
  ('admin-bff',    'confidential', 'Platforma admin BFF',               ARRAY['authorization_code','refresh_token'], ARRAY['platform.admin'], 'pending_secret'),
  ('android-pos',  'public',       'Android POS',                       ARRAY['authorization_code','refresh_token'], ARRAY['*','sync','pos'], 'active'),
  ('telegram-bot', 'confidential', 'Telegram bot',                      ARRAY['client_credentials'],                 ARRAY['bot.internal'],   'pending_secret'),
  ('onec-agent',   'public',       'Do''kon agenti (Windows)',               ARRAY['urn:ietf:params:oauth:grant-type:device_code','client_credentials'], ARRAY['onec.agent'], 'active');
-- allowed_scopes: '*' — foydalanuvchi ruxsatlaridan hisoblangan prefikslar; 'sync'/'pos' faqat aniq yozilganda (14 §10) —
-- veb-kassa web-bff orqali /sync/push, /sync/pull chaqiradi.
-- onec-agent: ulash — device code (RFC 8628), keyin client_credentials + private_key_jwt
-- (agentning shaxsiy client_id'si 'onec-agent:{agent_id}', kaliti app.onec_agents.public_jwk; 33-1c-integratsiya.md §9.2).
-- redirect_uris bo'sh, client_secret yo'q.
-- Maxfiy mijozlar 'pending_secret' holatida seed qilinadi; deploy skripti sirni KEK orqali yozib holatni 'active' qiladi
-- (15-xavfsizlik §4.2): UPDATE platform.oauth_clients SET client_secret_encrypted = :enc, status = 'active' WHERE client_id = :id;

-- signing_keys — haqiqiy kalit juftligi deploy skriptida (joserfc) generatsiya qilinadi, DB'ga faqat natija yoziladi:
-- INSERT INTO platform.signing_keys (algorithm, purpose, public_key, private_key_encrypted, status, activated_at)
-- VALUES ('EdDSA', 'access', :pub, :enc_priv, 'active', now());
-- INSERT INTO platform.signing_keys (algorithm, purpose, public_key, private_key_encrypted, status, activated_at)
-- VALUES ('EdDSA', 'license', :pub2, :enc_priv2, 'active', now());
-- 1C integratsiya moduli yoqilgan muhitda (qaror #36–#38) xuddi shu tartibda 'onec_task' va 'agent_update' kalitlari ham yaratiladi.
```

### 5.2 Tenant-provisioning shabloni (har ro'yxatdan o'tishda qo'llaniladi, global emas)

`15-xavfsizlik-va-audit.md` §1.5: `roles`/`role_permissions`/`expense_categories`/`doc_sequences` **tenant-scoped** jadvallar — bular bir martalik global seed emas, balki **har signup tranzaksiyasida** ilova kodi tomonidan quyidagi shablon bo'yicha yaratiladi (aniqlashtirish #13). **Standart filial** — `branches.code='01'`; keyingi filiallar — keyingi bo'sh ikki xonali raqam (API'da ixtiyoriy kiritiladi).

```sql
-- 5 standart rol (parametr :tenant_id)
INSERT INTO app.roles (tenant_id, name, is_system, system_code) VALUES
  (:tenant_id, 'Egasi',      true, 'owner'),
  (:tenant_id, 'Menejer',    true, 'manager'),
  (:tenant_id, 'Kassir',     true, 'cashier'),
  (:tenant_id, 'Omborchi',   true, 'storekeeper'),
  (:tenant_id, 'Buxgalter',  true, 'accountant');

-- standart limitlar (`15` §2.3) — faqat Kassir roliga namuna; to'liq matritsa §2.2'dan ilova kodida yuklanadi
INSERT INTO app.role_permissions (tenant_id, role_id, permission_code, limit_value) VALUES
  (:tenant_id, :cashier_role_id, 'discount.give',    5.00), -- foiz
  (:tenant_id, :cashier_role_id, 'returns.approve',  100000.00), -- so'm
  (:tenant_id, :cashier_role_id, 'cash.withdraw',    50000.00), -- so'm
  (:tenant_id, :cashier_role_id, 'sales.void',       NULL); -- limitsiz, audit bilan
-- (qaror #28) Egasi roli — barcha tenant ruxsatlarining supersetiga ega (sotuv/smena/
-- qaytarish/buxgalteriya ko'rish ham kiradi), limitlar cheksiz; seed yuqoridagi namuna kabi har bir
-- permission_code uchun (:tenant_id, :owner_role_id, <kod>, NULL) qatorlarini `15-xavfsizlik-va-audit.md` §2.1
-- to'liq katalogidan generatsiya qiladi (ilova kodida, `platform.admin`dan tashqari) — to'liq matritsa §2.2'da.

-- standart xarajat toifalari — toifa → hisob xaritasi 13-provodka-qoidalari.md §2.17 (VMQ-54, S1 §407–412);
-- tenant default_account'ni o'zgartira oladi
INSERT INTO app.expense_categories (tenant_id, code, name, default_account, source_ref, is_system) VALUES
  (:tenant_id, 'rent_store',         'Ijara — savdo zali/ombor',        '9410', 'VMQ-54 2.1.2.3',  true),
  (:tenant_id, 'rent_office',        'Ijara — ofis',                    '9420', 'VMQ-54 2.2.8',    true),
  (:tenant_id, 'utilities_store',    'Kommunal — do''kon',              '9410', 'VMQ-54 2.1.2.6',  true),
  (:tenant_id, 'utilities_office',   'Kommunal — ofis',                 '9420', 'VMQ-54 2.2.4',    true),
  (:tenant_id, 'communication',      'Aloqa, internet, telefon',        '9420', 'VMQ-54 2.2.6',    true),
  (:tenant_id, 'transport_delivery', 'Transport — tovar tashish',       '9410', 'VMQ-54 2.1.1',    true),
  (:tenant_id, 'transport_admin',    'Transport — xizmat avtomobili',   '9420', 'VMQ-54 2.2.3',    true),
  (:tenant_id, 'payroll_sales',      'Ish haqi — savdo xodimlari',      '9410', 'VMQ-54 2.1.2.1',  true),
  (:tenant_id, 'payroll_admin',      'Ish haqi — boshqaruv',            '9420', 'VMQ-54 2.2.1',    true),
  (:tenant_id, 'advertising',        'Reklama, marketing',              '9410', 'VMQ-54 2.1.2.8',  true),
  (:tenant_id, 'repair_store',       'Ta''mirlash — savdo',             '9410', 'VMQ-54 2.1.2.3',  true),
  (:tenant_id, 'repair_admin',       'Ta''mirlash — ma''muriy',         '9420', 'VMQ-54 2.2.9',    true),
  (:tenant_id, 'packaging',          'Tara, qadoqlash',                 '9410', 'VMQ-54 2.1.2.10', true),
  (:tenant_id, 'supplies',           'Inventar, xo''jalik buyumlari',   '9410', 'VMQ-54 2.1.2.5',  true),
  (:tenant_id, 'bank_services',      'Bank xizmatlari',                 '9430', 'S1 §410, §412',   true),
  (:tenant_id, 'collection_service', 'Inkassatsiya xizmati',            '9410', 'VMQ-54 2.1.2.18', true),
  (:tenant_id, 'period_taxes',       'Soliq va yig''imlar (davr xarajati)', '9430', 'S1 §275',     true),
  (:tenant_id, 'fines',              'Jarimalar, penyalar',             '9430', 'VMQ-54 2.3.15',   true),
  (:tenant_id, 'audit_consulting',   'Audit, maslahat, o''qitish',      '9430', 'S1 §410',         true),
  (:tenant_id, 'tax_payment',        'Soliq to''lovi (byudjetga)',      '6410', 'S1 §275',         true),
  (:tenant_id, 'other',              'Boshqa',                          '9430', 'S1 §410',         true);

-- standart filial (code='01') va uning ombori — type='store', inventory_account='2920' (13 §1; keyingi
-- omborlar POST /branches yoki PATCH /warehouses orqali, type → inventory_account: store → 2920, stock → 2910)
INSERT INTO app.branches (id, tenant_id, code, name, is_default, settlement_category, activity_type) VALUES
  (:branch_id, :tenant_id, '01', :branch_name, true, :settlement_category, 'retail');
INSERT INTO app.warehouses (tenant_id, branch_id, name, type, inventory_account) VALUES
  (:tenant_id, :branch_id, 'Asosiy ombor', 'store', '2920');

-- doc_sequences — birinchi hujjat yaratilganda ON CONFLICT bilan o'zi paydo bo'ladi (next_doc_number, 2.9-bo'lim),
-- oldindan INSERT shart emas (ixtiyoriy, hisobot uchun 0-qatorlar kerak bo'lsa):
-- INSERT INTO app.doc_sequences (tenant_id, branch_id, doc_type, year, next_value) VALUES (:tenant_id, :branch_id, 'K', :year, 1)
-- ON CONFLICT DO NOTHING;
```

---

## 6. Migratsiya tartibi va CI tekshiruvi

### 6.1 Alembic revizion rejasi

Revizionlardan oldin — DBA bootstrap (0-bo'lim: rollar, parollar, `GRANT erp_system TO erp_migrator`, `search_path`, `erp_migrator` egaligidagi baza); barcha revizionlar `erp_migrator` bilan ishlaydi. Revizionlar zanjiri chiziqli: `0001` → … → `0027` → `0028` → `0029`; `0028 store_agent` ning `down_revision` — `0027` (yadro revizionlarining oxirgisi).

**SQL fayllar shu hujjatdan generatsiya qilinadi** (`backend/scripts/gen_migration_sql.py` → `backend/alembic/sql/NNNN_<nom>.{up,down}.sql`; `--check` rejimi CI'da drift'ni ushlaydi). Har ` ```sql ` bloki revizionga quyidagi tartibda biriktiriladi:
1. Blokning birinchi qatori — marker izoh: `-- NNNN <nom>` (masalan `-- 0015 registers`, `-- 0027 boshida`) — butun blok shu revizionga; `-- DBA bootstrap` — revizion emas (0-bo'lim, `initdb.sh`); `-- namuna` — DDL emas, misol.
2. Markersiz blok — bo'lim sarlavhasi bo'yicha: 0, 1.1–1.4 → `0001`; 2.1–2.9 → har bayonot o'z jadvalining revizioniga (quyidagi jadval; jadvaldan keyin yozilgan kechiktirilgan FK/indeks — FK bog'langan eng kech jadval revizioniga), `app.next_doc_number()` → `0019`; 2.11 → `0028`/`0029`; 4.1–4.4 → `0026`; 4.5 → `0027`; 5 (seed) va 6.2 (CI) — revizion emas.
3. `0028`/`0029` bloklari tegishli bosqichgacha generatsiya qilinmaydi.

| № | Revizion | Mazmuni |
|---|---|---|
| 0001 | `extensions_roles_schemas` | Rollar (faqat migratsiya roli superuser/`CREATEROLE` bo'lsa va rol yo'q bo'lsa; aks holda mavjudligi tekshiriladi — 0-bo'lim), sxemalar, kengaytmalar, `search_path` (xuddi shu shart bilan, 1.1), `app.uuidv7()`, `app.set_updated_at()`, `app.forbid_mutation()` |
| 0002 | `core_tenant_user` | `tenants` (+`legal_form`, `go_live_date`, `accepted_terms_*`), `users`, `branches` (+`code`), `branch_tax_settings`, `warehouses` (+`inventory_account`, standartsiz), `cash_registers` (+`ofd_status`, `fm_state`, `last_unacked_receipt_at`, `fm_receipts_pending`, `tax_registered_at`, `outlet_address_snapshot`, `txkm_contract_ref`, `fiscal_agent_id` — FK 0028 da, `fiscal_local_device_id`), `devices` (`kind` ichida `onec_agent`, qaror #58), `memberships`, `roles`, `role_permissions` |
| 0003 | `auth_schema` | `platform.oauth_clients` (+`status`, `pending_secret` CHECK — auth FK'lari uchun oldin), `auth.*` (6 jadval, `otp_challenges.channel` — qaror #34) + ularning `app.users`/`tenants`/`devices`ga FK'lari, `app.license_tokens`, **`app.user_identities`** (Google OIDC bog'lash, qaror #34) |
| 0004 | `label_templates` | `platform.label_templates`, `platform.marking_product_groups` (qaror #63) |
| 0005 | `valuation_method_history` | `app.valuation_method_history` |
| 0006 | `counterparties` | `counterparties` (+`debt_due_date`, `is_founder`), `debt_doubtful_flags` |
| 0007 | `platform_global` | `platform.plans`, `addons`, `units`, `signing_keys` (`purpose` ichida `onec_task`/`agent_update`), `platform_admins`, `fx_rates` (qaror #55), `terms_versions` (qaror #61), `turnover_tax_rates`, `card_bin_rules` (qaror #71) + `app.subscriptions`, `tenant_addons`, `billing_payments` (davr/kvitansiya ustunlari, +`kind`/`reason`/`actor_user_id`, qaror #56), `tenant_tax_regimes`, `consents` (qaror #61) |
| 0008 | `catalog_pricing` | `product_categories`, `products` (`mxik_code` NULL ruxsat; `name_ru` nullable — qaror #29; `marking_group_code` — qaror #63; `turnover_tax_group`), `product_barcodes`, `product_prices`, `label_print_queue`, `internal_barcode_seq`, `discount_rules`; `products.package_code` uzunlik CHECK |
| 0009 | `counterparty_statement_links` | `app.counterparty_statement_links` (`counterparties`dan keyin) |
| 0010 | `approval_payment_infra` | `approval_requests`, `doc_approvals` (`kind` ichida `card_manual_entry`), `payment_checkouts`, `card_terminals` (qaror #71; `agent_id` FK'siz — `fk_ct_agent` 0028 da) — `docs_sales`dan **oldin**, `sale_payments.checkout_ref` FK uchun |
| 0011 | `docs_sales` | `shifts` (`shift_no`/`variance`, `status` — `open`/`closed`), `sales` (+`is_offline`/`debt_limit_exceeded`), `sale_lines` (chegirma/QQS ustunlari, `settled_amount`), `card_terminal_transactions` (qaror #71; `shifts`dan keyin, `sale_payments`dan oldin; `settlement_id` FK'siz — `fk_ctt_settlement` 0018 da), `sale_payments` (+`due_date`/`checkout_ref`, `card_type`/`card_mask`/`rrn` va UzQR CHECK'lari — qaror #64; `card_entry_mode`/`card_terminal_transaction_id`/`approval_code`/`card_scheme`/`card_type_source`/`manual_reason` va ularning CHECK'lari, `uq_sale_payments_card_tx` — qaror #71) |
| 0012 | `docs_returns` | `returns` (+smena/kassa/qaytarish usuli — `uzqr`/`click`/`payme`/`uzum` bilan; karta qaytarish rekvizitlari `card_entry_mode`/`card_terminal_transaction_id`/`card_type`/`card_mask`/`rrn`/`approval_code`/`card_scheme`/`manual_reason` + `uq_returns_card_tx` — qaror #71), `return_lines` (+QQS/marking, `restock` — qaror #48) |
| 0013 | `docs_purchasing` | `purchase_orders` (+`warehouse_id`), `po_lines` (`price` ixtiyoriy), `goods_receipts` (+`source`/`einvoice_id`/`ai_ocr_job_id`/`ettn_ref`/`poa_id`/`poa_number`/`kind`), `receipt_lines` (+`vat_exemption_code`, `discrepancy_reason`) |
| 0014 | `docs_inventory` | `transfers` (+`sent_at/by`, `received_at/by`), `transfer_lines` (`lot_id` yo'q, `lot_allocations` JSONB), `transfers` (+`transport_mode`/`ettn_ref`/`vehicle_plate`/`driver_name`), `stock_counts` (+`started_at`/`responsible_user_id`), `count_lines` (`counted` NULL, +`snapshot_qty`/`counted_at` — qaror #53), `write_offs` (+`responsible_user_id`/`promo_order_ref`/`source_return_id`), `write_off_lines` (+`expired_return`, `gift_kind`), `stock_openings`, `opening_lines` |
| 0015 | `registers` | `stock_moves`, `stock_lots` (`source_doc_type` ko'plik, +`stock_counts`, `blocked_qty`) (+ `supplier_returns` (+`reason`) / `supplier_return_lines`), `avg_costs` (+`total_value`), `stock_balances`, `debt_moves` (+`limit_exceeded`), `debt_balances`, `cash_moves` (`method` CHECK + bank_account_id izohi), `ledger_entries` (+`branch_id`, hisob kodi formati CHECK), `vat_moves`; append-only `REVOKE`+trigger (3-bo'lim): beshta registr, `app.doc_approvals` (0010 jadvali) va `auth.login_attempts` (0003 jadvali; `app.login_attempts_guard()` — `DELETE` faqat `auth_purge_login_attempts` ichida) |
| 0016 | `ledger_adjustments` | `app.ledger_adjustments` (doc_sequences kodi `BX`, +`analytics`) |
| 0017 | `docs_pricing_debts` | `price_changes`, `price_change_lines` (+`valid_from`), `debt_openings` (+`due_date`), `debt_payments` (`method` to'liq ro'yxat + checkout/promise_date, +`card_type`/`card_mask`/`rrn`/`qr_type`, `receipt_seq`, `unallocated_amount`, bank ↔ kassasiz CHECK; qaror #71 karta ustunlari va `uq_debt_payments_card_tx` — `sale_payments` bilan bir xil), `debt_payment_allocations` (`target_doc_type` CHECK, +`debt_writeoffs`), `debt_writeoffs` (+`reason`, `account_choice` default, `tax_writeoff_basis`), `supplier_payments` (+`cash_register_id`/`shift_id`), `supplier_payment_allocations` (`target_doc_type` CHECK) |
| 0018 | `docs_expenses_cash` | `expense_categories` (+`version`, `code`/`default_account`/`source_ref`), `recurring_expenses`, `attachments` (+`content_type`/`original_name`/`sha256`/`kind` CHECK), `expenses` (+`tax_type`), `cash_movements` (+`counterparty_id`, `account`, `employee_id`, `reason`↔`direction` CHECK), `bank_statement_imports`, `bank_settlements` (qaror #42, `attachments`dan keyin; +`variance_amount`, `statement_import_id`), `card_terminal_settlements` (qaror #71, `bank_settlements`dan keyin) + `fk_ctt_settlement`, `tax_settlements` (kod `ST`; `vat_offset` — (tenant, davr), `turnover_tax` — (filial, davr) bo'yicha yagona); shu revizionda `attachments` mavjud bo'lgach `ALTER TABLE billing_payments ADD CONSTRAINT fk_bp_invoice_attachment ...` |
| 0019 | `doc_sequences` | `doc_sequences`, `app.next_doc_number()`; kod ro'yxatiga `BX`=ledger_adjustments, `BT`=bank_settlements, `ST`=tax_settlements |
| 0020 | `fiscal_marking_edocs` | `fiscal_receipts` (`kind` + `debt_settlement`/`credit_sale`, `debt_payment_id`, `fm_terminal_id`/`fm_receipt_seq`/`fiscal_at`/`ofd_acked_at`, `payment_form`, `delivery`; qaror #30, #43, #45), `marking_codes`, `einvoices` (status CHECK + summalar + `uq_einvoice_out_per_doc`, `risk_flag` + `unknown`, `factura_type`/`related_einvoice_id`), `powers_of_attorney` (`einvoices` dan keyin), `ettn_documents` (+`transfer_id`/`transport_type`/`direction`/`counterparty_id`/`receipt_id`/`doc_date`/`payload`/`signed_at`/`last_error`, `status` CHECK `failed` bilan — qaror #63), `state_reports` (+solishtirish ustunlari, `confirmed`, `correction_comment`/`correction_portal_ref`/`confirmed_at`/`confirmed_by`), `state_report_diffs`; shu revizionda `einvoices`/`marking_codes`/`powers_of_attorney` mavjud bo'lgach `fk_gr_einvoice`, `fk_vm_einvoice`, `fk_sl_marking`, `fk_gr_poa` |
| 0021 | `ai_ocr_jobs` | `app.ai_requests` (`ai_ocr_jobs.ai_request_id` FK uchun oldin), `app.ai_ocr_jobs` (`doc_type_hint` — `purchase`/`catalog`, `created_product_ids`) + `fk_gr_ocr_job` (`goods_receipts.ai_ocr_job_id` → `ai_ocr_jobs.id`) |
| 0022 | `integration_sync` | `app.tenant_secrets` (integratsiya hisob ma'lumotlari, +`cash_register_id` — UzQR kaliti); `outbox_jobs` (17 qiymatli `kind` ro'yxati — `poa_send`, `marking_supplier_return`, `marking_writeoff`, `billing_webhook_reconcile` bilan; job-progress ustunlari), `sync_receipts`, `sync_exceptions` (qaror #56; `kind` CHECK — 16 §5 ro'yxati, +`card_result_mismatch`/`card_orphan_transaction` — qaror #71), `idempotency_keys`, `recost_jobs`, `import_jobs` (holatlar + `result`); `sync_receipts` append-only `REVOKE`+trigger (3-bo'lim) |
| 0023 | `notifications_ai` | `telegram_links`, `notification_settings`, `notifications_log`, `ai_training_samples`, `ai_feedback`, `tenant_glossary` |
| 0024 | `audit_periods` | `audit_log`, `period_closings`; `audit_log` append-only `REVOKE`+trigger (3-bo'lim) |
| 0025 | `updated_at_triggers` | 2.10-bo'limdagi `DO` bloki (jumladan `card_terminals`, `card_terminal_transactions`, `card_terminal_settlements`, `platform.card_bin_rules`) |
| 0026 | `rls_policies` | 4.2–4.4-bo'limlardagi `DO` bloki + maxsus siyosatlar + GRANT/REVOKE (+`platform.label_templates`/`marking_product_groups`/`terms_versions`/`turnover_tax_rates`/`card_bin_rules` SELECT, `platform.fx_rates` SELECT/INSERT/UPDATE); sxema-GRANT'lardan keyin append-only `REVOKE`lar qayta qo'llanadi, `auth.login_attempts` uchun `erp_system`dan `UPDATE` (4.4) |
| 0027 | `security_definer_functions` | 4.5-bo'limdagi 4 funksiya + `auth_consume_code`/`auth_rotate_refresh`/`auth_revoke_tenant`/`auth_suspend_tenant` + (`payments_checkout_by_provider_tx`, `payments_checkout_by_ref`, `billing_payment_by_id`, `public_statement_by_token`) + 17 ta AS yozuvchi/sessiya funksiyasi (`auth_issue_code` … `auth_telegram_chat_by_phone`, `auth_lookup_refresh`, `auth_revoke_refresh_family`, `auth_purge_login_attempts`) — jami 29; ular o'qiydigan `app` jadvallariga `erp_system` uchun nomma-nom `GRANT SELECT`; boshida `GRANT CREATE ON SCHEMA app TO erp_system`, oxirida `REVOKE` (egalik topshirish uchun vaqtincha, 4.5) |
| 0028 | `store_agent` | Do'kon agenti umumiy registri (2.11-bo'lim, qaror #66): `app.onec_agents` (+`capabilities`), `app.onec_agent_tasks` (1C ustunlari FK'siz; fiskal/printer/tarozi/karta terminali xizmat vazifalari — `card.status`, `card.settlement` (qaror #71), `purpose='device_service'`), `app.onec_task_results`, `auth.onec_device_authorizations`; `fk_cr_fiscal_agent` (`cash_registers.fiscal_agent_id` → `onec_agents`), `fk_ct_agent` (`card_terminals.agent_id` → `onec_agents`, qaror #71); `updated_at` trigger'lari (2.10, 2 jadval); RLS uchligi (4.2, 3 jadval); grantlar (4.4); 6 ta `SECURITY DEFINER` funksiya (`onec_device_auth_start/lookup/approve/poll/deny`, `onec_agent_credentials`; 4.5). `0002`/`0007` dagi `devices`, `signing_keys`, `cash_registers` ga bog'liq. Bosqich 5 |
| 0029 | `onec_integration` | 1C integratsiyasi (2.11-bo'lim, `33-1c-integratsiya.md` §5): 15 ta `app.onec_*` jadval (FK tartibida: `onec_bases` → `onec_settings`, `onec_branch_bindings`, `onec_metadata_snapshots`, `onec_catalog_items`, `onec_mappings`, `onec_value_mappings`, `onec_ref_create_requests` → `onec_export_batches` → `onec_export_items` → `onec_export_item_sources`, `onec_object_refs` → `onec_reconciliations`, `onec_events`, `onec_agent_logs`); `onec_forbid_namespace_change` trigger'i; kechiktirilgan FK'lar, jumladan `onec_agent_tasks` ga `fk_oat_base`, `fk_oat_batch`, `fk_oat_item`, `fk_oat_ref_create`, `fk_oat_reconciliation`; `updated_at` trigger'lari (2.10, 11 jadval); RLS uchligi (4.2, 15 jadval); grantlar (4.4); `onec_tenants_due` (4.5). `onec_metadata_snapshots`/`onec_reconciliations`/`onec_events` `task_id` FK'lari `ON DELETE SET NULL` (o'qish vazifalari 30 kunda tozalanadi). `0018` dagi `attachments`ga bog'liq. Bosqich 7 |

Seed (5-bo'lim) — **Alembic revizion emas** (`23-backend-arxitekturasi.md` §11: "bazani versiyalash bilan aralashtirmaslik uchun"), `migrate` konteyneridan keyin alohida `python -m scripts.seed global` bosqichi (`erp_migrator` ulanishi bilan — `platform.*` jadvallariga faqat u yozadi, 4.4), faqat 5.1 (global) qismini ishga tushiradi (idempotent, `ON CONFLICT DO NOTHING`); 5.2 (tenant-provisioning) — har signup'da ilova kodi tomonidan.

> Diqqat: yuqoridagi tartib 2-bo'limning **o'qish tartibidan** farq qiladi (masalan `supplier_returns`/`supplier_return_lines` 2-bo'limda purchasing ostida ko'rsatilgan, lekin `stock_lots`ga FK'i borligi sababli 0015-revizionda, registrlardan keyin yaratiladi). Bu — FK bog'liqligini hal qilish uchun zarur qayta tartiblash, 11-model mazmuniga ta'sir qilmaydi.

### 6.2 CI tekshiruvi — RLS'siz jadvallar

```sql
WITH exempt AS (
  SELECT unnest(ARRAY[
    'platform.plans', 'platform.addons', 'platform.units',
    'platform.oauth_clients', 'platform.signing_keys', 'platform.platform_admins',
    'platform.label_templates', 'platform.fx_rates', 'platform.terms_versions',
    'platform.marking_product_groups', 'platform.turnover_tax_rates', 'platform.card_bin_rules',
    'auth.user_credentials', 'auth.otp_challenges', 'auth.login_attempts',
    'auth.authorization_codes', 'auth.refresh_tokens', 'auth.sessions',
    'auth.onec_device_authorizations', -- 1C agent device grant: tenant tasdiqqacha noma'lum, faqat SECURITY DEFINER orqali
    'app.user_identities'
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

Qo'shimcha, `auth`-sxema istisnosini tasdiqlovchi tekshiruv (`15-xavfsizlik-va-audit.md` §3.3):

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
                     'auth_revoke_tenant','auth_suspend_tenant',
                     'payments_checkout_by_provider_tx','payments_checkout_by_ref',
                     'billing_payment_by_id','public_statement_by_token',
                     'auth_issue_code','auth_issue_tokens','auth_session_by_id','auth_touch_session',
                     'auth_otp_create','auth_otp_verify','auth_record_login','auth_set_credentials',
                     'auth_reset_credentials','auth_get_pin_hash','auth_revoke_session','auth_revoke_user',
                     'auth_list_user_sessions','auth_telegram_chat_by_phone',
                     'auth_lookup_refresh','auth_revoke_refresh_family','auth_purge_login_attempts',
                     'onec_device_auth_start','onec_device_auth_lookup',
                     'onec_device_auth_approve','onec_device_auth_deny','onec_device_auth_poll',
                     'onec_agent_credentials','onec_tenants_due');
-- 36 qator qaytishi shart (0027 — 29, 0028 — 6, 0029 — 1); kamroq bo'lsa CI qizil.
-- 0028 qo'llanmagan muhitda — 29, 0029 qo'llanmagan muhitda — 35.
```

---

## 7. 11 bilan aniqlashtirishlar

`11-malumotlar-modeli.md` jadval/ustun nomlari saqlangan holda DDL uchun qabul qilingan aniq qarorlar:

1. **UUID generatsiyasi**: ilova tomonida (offline-first talabi, §1.2), DB `DEFAULT app.uuidv7()` — faqat zaxira.
2. **`stock_lots`/`avg_costs`/`stock_balances`/`debt_balances`ning append-only emasligi**: 11 §7 ularni "Registrlar (append-only)" sarlavhasi ostida bersa ham, bular jismoniy mutatsiya qilinadigan balans-keshlari; haqiqiy append-only — `stock_moves`/`debt_moves`/`cash_moves`/`ledger_entries`/`vat_moves` (3-bo'lim).
3. **`stock_lots.receipt_line_id`ning umumlashtirilishi**: 11 faqat `receipt_line_id`ni ko'rsatadi, lekin `stock_openings`/`transfers` ham yangi partiya yaratadi (goods_receipt'siz). Shuning uchun `receipt_line_id` (faqat kirim uchun, nullable) ustiga `source_doc_type`/`source_doc_id`/`source_line_id` polimorfik ustunlari qo'shildi.
4. **Sxema taqsimoti** (`app`/`auth`/`platform`): 11'da umuman yo'q — bu hujjat tomonidan kiritildi, `15-xavfsizlik-va-audit.md` §3.3, `14-autentifikatsiya-oauth2.md` §19 dagi RLS istisnolari mantiqiga mos ravishda.
5. **Hisob-kitob ustunlarining aniq `NUMERIC` kategoriyasi**: 11 faqat uchta umumiy kategoriya beradi (pul/miqdor/narx-tannarx); har bir aniq ustun (masalan `sale_lines.price` → narx 18,4; `sale_lines.line_total` → pul 18,2; `sale_lines.cost_amount` → pul 18,2, chunki bu qatorning **jami** tannarxi, birlik tannarxi emas) shu uchta toifaga ushbu hujjat tomonidan taqsimlangan.
6. **`role_permissions.limit_value` birligi**: 11 aniqlashtirmaydi (foiz yoki summa) — bu hujjat yagona `NUMERIC(18,4)` ustunni tanladi, ma'no `permission_code` konvensiyasi orqali aniqlanadi (masalan `discount.give` = foiz, `cash.withdraw` = so'm); alohida `limit_unit` ustuni **qo'shilmadi** (ilova darajasida kod-konstanta sifatida saqlanadi).
7. **`discount_rules.value`**: xuddi shunday, `kind='percent'` bo'lsa foiz, aks holda summa — bitta `NUMERIC(18,4)` ustun.
8. **`products.vat_rate`**: 01 "12/0/imtiyoz kodi" deydi — bitta ustunda son va kod aralashishi mumkin emas, shuning uchun `vat_rate NUMERIC(5,2) NULL` + `vat_exemption_code TEXT NULL` ikkiga ajratildi (`CHECK` — kamida bittasi to'ldirilgan bo'lishi shart).
9. **`goods_receipts.paid_immediately`**: 11'da yo'q, lekin `13-provodka-qoidalari.md` §2.6/§2.8 ikki xil provodka yo'li (nasiyaga / darhol to'langan) borligini aytadi — bu bayroq shu tanlovni saqlash uchun qo'shildi.
10. **`sales.total_amount`**: 11'da yo'q, tezkor o'qish/hisobot uchun hisoblangan ustun sifatida qo'shildi (qatorlar yig'indisidan posting vaqtida to'ldiriladi, manba emas).
11. **`debt_payment_allocations`/`supplier_payment_allocations`**: 11 faqat "`allocations` (qaysi qarzni yopdi)" deydi, alohida jadval nomini bermaydi — polimorfik `target_doc_type`/`target_doc_id` naqshi bilan modellashtirildi (registrlardagi `doc_type`/`doc_id` naqshiga mos).
12. **`doc_sequences.doc_type` kodlari**: 11 faqat `K-01-2026-000154` namunasini beradi, to'liq kod jadvalini bermaydi — 2.9-bo'limdagi ro'yxat — standart (qaror #54), yangi kod append-only seed.
13. **Global seed vs tenant-provisioning**: 01 `roles`/`role_permissions`/`expense_categories`/`doc_sequences`ni "seed" sifatida tilga oladi, lekin bu jadvallar `tenant_id NOT NULL` — demak **global** bir martalik seed emas, balki `15-xavfsizlik-va-audit.md` §1.5'dagi tenant-provisioning tranzaksiyasining bir qismi (5.2-bo'lim shu farqni aniq ajratadi).
14. **`marking_codes` ↔ `sale_lines.marking_code` FK**: 11'da bu bog'lanish aniq FK sifatida ko'rsatilmagan — `(tenant_id, code)` composite UNIQUE + `DEFERRABLE` FK qo'shildi (chek va kod bir xil tranzaksiyada, lekin ikkisining yozilish tartibi ilova mantiqiga bog'liq bo'lishi mumkin, shuning uchun kechiktirilgan tekshiruv).
15. **`shifts`ning umumiy hujjat sarlavhasidan mustasnoligi**: 11 §11 (raqamlash) shiftlarga `number` berilishini aytmaydi — shuning uchun `shifts` boshqa hujjatlardan farqli, `number`/`temp_number`siz maxsus sarlavha oldi.
16. **`branch_tax_settings`/`tenant_tax_regimes.created_by`**: 11'da yo'q, audit izlanishi uchun qo'shildi (boshqa barcha hujjat/ma'lumotnoma yozuvlarida bor konvensiyaga moslashtirildi).
17. **Hisob kodlari**: `ledger_entries`/`ledger_adjustments`dagi `account_dt`/`account_kt` — 4 raqamli `TEXT` (`CHECK ~ '^[0-9]{4}$'`); ruxsat etilgan kodlar ro'yxati (texnik `0000` bilan) — `13-provodka-qoidalari.md` §1, ilova konstantasi. Alohida hisoblar rejasi jadvali yo'q.
18. **Inventarizatsiya qatorlari** jadvali nomi — `count_lines` (qaror #53 dagi "stock_count_lines" shu jadval).

---

## Yakuniy eslatma

Bu hujjat — `11-malumotlar-modeli.md`ning DDL proyeksiyasi. Buxgalteriya hisob raqamlari (`account_dt`/`account_kt` qiymatlari) BHMS №21 rasmiy matni bo'yicha `13-provodka-qoidalari.md` §1 da belgilangan — bu hujjat ularni 4 raqamli `TEXT` sifatida saqlaydi, ruxsat etilgan ro'yxatni ilova konstantasi tekshiradi.

