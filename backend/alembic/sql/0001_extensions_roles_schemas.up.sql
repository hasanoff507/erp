-- 0001 extensions_roles_schemas — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

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

CREATE SCHEMA IF NOT EXISTS app;

CREATE SCHEMA IF NOT EXISTS auth;

CREATE SCHEMA IF NOT EXISTS platform;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- gen_random_bytes/gen_random_uuid — uuidv7() va parol-siz tasodifiy qiymatlar uchun
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- mahsulot/kontragent nomi bo'yicha qidiruv indeksi (11-model §1)

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

CREATE OR REPLACE FUNCTION app.set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION app.forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'append-only jadval: % operatsiyasi taqiqlangan (jadval: %)', TG_OP, TG_TABLE_NAME
    USING ERRCODE = 'integrity_constraint_violation';
END;
$$;
