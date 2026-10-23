-- 0027 security_definer_functions — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

-- 0027 boshida
GRANT CREATE ON SCHEMA app TO erp_system;

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

-- 0027 oxirida (egalik topshirilgach)
REVOKE CREATE ON SCHEMA app FROM erp_system;
