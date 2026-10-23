-- 0027a web_pos — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- 0027a web_pos
ALTER TABLE auth.authorization_codes ADD COLUMN device_id UUID NULL REFERENCES app.devices(id);

ALTER TABLE auth.user_credentials ADD COLUMN pin_local_hash TEXT NULL;

-- 0027a web_pos
ALTER TABLE app.memberships ADD COLUMN pin_reset_at TIMESTAMPTZ NULL;

GRANT UPDATE (pin_reset_at) ON app.memberships TO erp_system;

-- 0027a web_pos
CREATE OR REPLACE FUNCTION app.touch_product_on_barcode_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE app.products SET updated_at = now()
   WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.product_id ELSE NEW.product_id END;
  IF TG_OP = 'UPDATE' AND OLD.product_id <> NEW.product_id THEN
    UPDATE app.products SET updated_at = now() WHERE id = OLD.product_id;
  END IF;
  RETURN NULL;
END;
$$;

CREATE TRIGGER trg_product_barcodes_touch_product AFTER INSERT OR UPDATE OR DELETE ON app.product_barcodes
  FOR EACH ROW EXECUTE FUNCTION app.touch_product_on_barcode_change();

-- 0027a web_pos
ALTER TABLE app.sync_exceptions DROP CONSTRAINT sync_exceptions_kind_check;

ALTER TABLE app.sync_exceptions ADD CONSTRAINT sync_exceptions_kind_check CHECK (kind IN ('price_mismatch','archived_product','stock_negative',
    'debt_limit_exceeded_offline','approval_limit_exceeded_offline','receipt_seq_conflict',
    'debt_overpayment_offline','debt_allocation_mismatch','late_in_closed_period','cost_unknown',
    'count_late_move','card_result_mismatch','card_orphan_transaction',
    'actor_unverified','late_in_closed_shift'));

-- 0027a web_pos
GRANT CREATE ON SCHEMA app TO erp_system;

DROP FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int);

-- Authorization Code berish (14 §4, §7.2): TTL standart 60 s; p_device_id — qurilmaga bog'langan login (NULL — yo'q).
CREATE OR REPLACE FUNCTION app.auth_issue_code(
  p_code_hash text, p_client_id uuid, p_user_id uuid, p_tenant_id uuid, p_code_challenge text,
  p_redirect_uri text, p_scope text, p_ttl_s int, p_device_id uuid
) RETURNS void
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  INSERT INTO auth.authorization_codes
    (code_hash, client_id, user_id, tenant_id, code_challenge, code_challenge_method, redirect_uri, scope,
     expires_at, device_id)
  VALUES
    (p_code_hash, p_client_id, p_user_id, p_tenant_id, p_code_challenge, 'S256', p_redirect_uri, p_scope,
     now() + make_interval(secs => COALESCE(p_ttl_s, 60)), p_device_id);
$$;

DROP FUNCTION app.auth_consume_code(text);

-- Authorization Code — bir martalik iste'mol (atomik), device_id bilan (14 §7.2).
CREATE OR REPLACE FUNCTION app.auth_consume_code(p_code_hash text)
RETURNS TABLE (client_id uuid, user_id uuid, tenant_id uuid, code_challenge text,
               code_challenge_method text, redirect_uri text, scope text, device_id uuid)
LANGUAGE sql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  UPDATE auth.authorization_codes c
     SET used_at = now()
   WHERE c.code_hash = p_code_hash AND c.used_at IS NULL AND c.expires_at > now()
  RETURNING c.client_id, c.user_id, c.tenant_id, c.code_challenge, c.code_challenge_method, c.redirect_uri,
            c.scope, c.device_id;
$$;

-- Parol/PIN o'rnatish (UPSERT): NULL argument — o'sha maydon o'zgarmaydi; berilganda *_updated_at = now(),
-- mos must_change_* = false; yangi PIN eski lokal verifikatorni o'chiradi (ilova yangisini
-- auth_set_pin_local_hash bilan yozadi).
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
    pin_local_hash       = CASE WHEN p_pin_hash IS NOT NULL THEN NULL ELSE c.pin_local_hash END,
    pin_updated_at       = CASE WHEN p_pin_hash IS NOT NULL THEN now() ELSE c.pin_updated_at END,
    must_change_pin      = CASE WHEN p_pin_hash IS NOT NULL THEN false ELSE c.must_change_pin END,
    updated_at           = now();
  -- yangi PIN barcha tenant-lokal bekor qilish belgilarini yechadi (16 §9) — vaqt solishtirilmaydi
  UPDATE app.memberships m SET pin_reset_at = NULL
   WHERE p_pin_hash IS NOT NULL AND m.user_id = p_user_id AND m.pin_reset_at IS NOT NULL;
$$;

-- Admin tomonidan tiklash: tanlangan hash NULL (PIN bilan birga lokal verifikator ham), must_change_* = true;
-- parol tiklansa foydalanuvchining barcha sessiya/refresh tokenlari bekor qilinadi (revoked_reason='credential_reset').
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
         pin_local_hash       = CASE WHEN p_reset_pin THEN NULL ELSE c.pin_local_hash END,
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

-- Lokal PIN verifikatorini yozish (14 §13): faqat joriy pin_hash ilova tekshirgan/yaratgan qiymat bilan bir xil
-- bo'lsa (oraliqda PIN almashtirilgan yoki bekor qilingan bo'lsa — false, hech narsa yozilmaydi).
CREATE OR REPLACE FUNCTION app.auth_set_pin_local_hash(p_user_id uuid, p_pin_hash text, p_pin_local_hash text)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
BEGIN
  UPDATE auth.user_credentials c
     SET pin_local_hash = p_pin_local_hash, updated_at = now()
   WHERE c.user_id = p_user_id AND c.pin_hash IS NOT NULL AND c.pin_hash = p_pin_hash
     AND NOT c.must_change_pin;
  RETURN FOUND;
END;
$$;

-- /auth/pin/verify va server tomonidagi PIN tekshiruvi (14 §4.3). Faqat joriy tenant (app.current_tenant_id(),
-- tenant_transaction) a'zosi uchun javob beradi — boshqa tenant foydalanuvchisi uchun bo'sh natija.
CREATE OR REPLACE FUNCTION app.auth_pin_state(p_user_id uuid)
RETURNS TABLE (pin_hash text, pin_local_hash text, must_change_pin boolean, pin_updated_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT c.pin_hash, c.pin_local_hash, c.must_change_pin, c.pin_updated_at
  FROM auth.user_credentials c
  JOIN app.memberships m ON m.user_id = c.user_id AND m.tenant_id = app.current_tenant_id()
  WHERE c.user_id = p_user_id;
$$;

-- permissions pull scope'i (16 §1, §3.2): berilgan foydalanuvchilarning lokal verifikatori (argon2 pin_hash emas).
-- Faqat joriy tenant (app.current_tenant_id()) a'zolari qaytadi.
CREATE OR REPLACE FUNCTION app.auth_staff_pin_states(p_user_ids uuid[])
RETURNS TABLE (user_id uuid, pin_set boolean, pin_local_hash text, must_change_pin boolean,
               pin_updated_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT c.user_id, c.pin_hash IS NOT NULL, c.pin_local_hash, c.must_change_pin, c.pin_updated_at
  FROM auth.user_credentials c
  JOIN app.memberships m ON m.user_id = c.user_id AND m.tenant_id = app.current_tenant_id()
  WHERE c.user_id = ANY (p_user_ids);
$$;

-- RS zaxirasi (14 §5): Redis ishlamaganda sid'siz access tokenning `fam` oilasi tirikmi — oilada bekor
-- qilinmagan token qolmagan (yoki oila yo'q) bo'lsa true.
CREATE OR REPLACE FUNCTION app.auth_family_revoked(p_family_id uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT NOT EXISTS (
    SELECT 1 FROM auth.refresh_tokens t WHERE t.family_id = p_family_id AND t.revoked_at IS NULL
  );
$$;

-- Sessiyaning joriy refresh oilasi (bitta sessiyani bekor qilishda `fam` belgisi uchun, 14 §5).
CREATE OR REPLACE FUNCTION app.auth_session_family(p_session_id uuid)
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT f.family_id
  FROM auth.sessions s JOIN auth.refresh_tokens f ON f.id = s.current_refresh_token_id
  WHERE s.id = p_session_id;
$$;

-- Qurilma bekor qilinganda (16 §9, 14 §7): unga bog'langan barcha sessiya va refresh tokenlar bekor qilinadi;
-- qaytaradi — bekor qilingan sessiyalar va oilalar (Redis sid/fam belgilari uchun).
CREATE OR REPLACE FUNCTION app.auth_revoke_device(p_device_id uuid, p_reason text)
RETURNS TABLE (session_ids uuid[], family_ids uuid[])
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
DECLARE
  v_sids uuid[];
  v_fams uuid[];
BEGIN
  WITH s AS (
    UPDATE auth.sessions se SET revoked_at = now(), revoked_reason = p_reason
     WHERE se.device_id = p_device_id AND se.revoked_at IS NULL
    RETURNING se.id
  ) SELECT COALESCE(array_agg(s.id), '{}') INTO v_sids FROM s;
  WITH t AS (
    UPDATE auth.refresh_tokens rt SET revoked_at = now(), revoked_reason = p_reason
     WHERE rt.device_id = p_device_id AND rt.revoked_at IS NULL
    RETURNING rt.family_id
  ) SELECT COALESCE(array_agg(DISTINCT t.family_id), '{}') INTO v_fams FROM t;
  RETURN QUERY SELECT v_sids, v_fams;
END;
$$;

-- Foydalanuvchining p_tenant_id dan boshqa tenantda faol a'zoligi bormi (16 §9: PIN global yoki tenant-lokal
-- bekor qilinadi — bir tenant boshqa tenant bilan umumiy kredensialga tegmaydi).
CREATE OR REPLACE FUNCTION app.auth_member_elsewhere(p_user_id uuid, p_tenant_id uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = app, auth, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1 FROM app.memberships m
    WHERE m.user_id = p_user_id AND m.tenant_id <> p_tenant_id AND m.status = 'active'
  );
$$;

ALTER FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int, uuid) OWNER TO erp_system;

ALTER FUNCTION app.auth_consume_code(text) OWNER TO erp_system;

ALTER FUNCTION app.auth_set_pin_local_hash(uuid, text, text) OWNER TO erp_system;

ALTER FUNCTION app.auth_pin_state(uuid) OWNER TO erp_system;

ALTER FUNCTION app.auth_staff_pin_states(uuid[]) OWNER TO erp_system;

ALTER FUNCTION app.auth_family_revoked(uuid) OWNER TO erp_system;

ALTER FUNCTION app.auth_session_family(uuid) OWNER TO erp_system;

ALTER FUNCTION app.auth_revoke_device(uuid, text) OWNER TO erp_system;

ALTER FUNCTION app.auth_member_elsewhere(uuid, uuid) OWNER TO erp_system;

REVOKE ALL ON FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int, uuid) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_consume_code(text) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_set_pin_local_hash(uuid, text, text) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_pin_state(uuid) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_staff_pin_states(uuid[]) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_family_revoked(uuid) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_session_family(uuid) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_revoke_device(uuid, text) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_member_elsewhere(uuid, uuid) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int, uuid) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_consume_code(text) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_set_pin_local_hash(uuid, text, text) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_pin_state(uuid) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_staff_pin_states(uuid[]) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_family_revoked(uuid) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_session_family(uuid) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_revoke_device(uuid, text) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_member_elsewhere(uuid, uuid) TO erp_app;

REVOKE CREATE ON SCHEMA app FROM erp_system;
