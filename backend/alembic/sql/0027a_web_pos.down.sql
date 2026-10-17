-- 0027a web_pos — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

DROP TRIGGER IF EXISTS trg_product_barcodes_touch_product ON app.product_barcodes;
ALTER TABLE IF EXISTS app.sync_exceptions DROP CONSTRAINT IF EXISTS sync_exceptions_kind_check;
DROP FUNCTION IF EXISTS app.auth_member_elsewhere CASCADE;
DROP FUNCTION IF EXISTS app.auth_revoke_device CASCADE;
DROP FUNCTION IF EXISTS app.auth_session_family CASCADE;
DROP FUNCTION IF EXISTS app.auth_family_revoked CASCADE;
DROP FUNCTION IF EXISTS app.auth_staff_pin_states CASCADE;
DROP FUNCTION IF EXISTS app.auth_pin_state CASCADE;
DROP FUNCTION IF EXISTS app.auth_set_pin_local_hash CASCADE;
DROP FUNCTION IF EXISTS app.auth_reset_credentials CASCADE;
DROP FUNCTION IF EXISTS app.auth_set_credentials CASCADE;
DROP FUNCTION IF EXISTS app.auth_consume_code CASCADE;
DROP FUNCTION IF EXISTS app.auth_issue_code CASCADE;
DROP FUNCTION IF EXISTS app.touch_product_on_barcode_change CASCADE;

-- 0027a down
ALTER TABLE auth.authorization_codes DROP COLUMN IF EXISTS device_id;

ALTER TABLE auth.user_credentials DROP COLUMN IF EXISTS pin_local_hash;

-- 0027a down
REVOKE UPDATE (pin_reset_at) ON app.memberships FROM erp_system;

ALTER TABLE app.memberships DROP COLUMN IF EXISTS pin_reset_at;

-- 0027a down
DELETE FROM app.sync_exceptions WHERE kind IN ('actor_unverified','late_in_closed_shift');

ALTER TABLE app.sync_exceptions DROP CONSTRAINT IF EXISTS sync_exceptions_kind_check;

ALTER TABLE app.sync_exceptions ADD CONSTRAINT sync_exceptions_kind_check CHECK (kind IN ('price_mismatch','archived_product','stock_negative',
    'debt_limit_exceeded_offline','approval_limit_exceeded_offline','receipt_seq_conflict',
    'debt_overpayment_offline','debt_allocation_mismatch','late_in_closed_period','cost_unknown',
    'count_late_move','card_result_mismatch','card_orphan_transaction'));

-- 0027a down
GRANT CREATE ON SCHEMA app TO erp_system;

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

ALTER FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int) OWNER TO erp_system;

ALTER FUNCTION app.auth_consume_code(text) OWNER TO erp_system;

ALTER FUNCTION app.auth_set_credentials(uuid, text, text) OWNER TO erp_system;

ALTER FUNCTION app.auth_reset_credentials(uuid, boolean, boolean) OWNER TO erp_system;

REVOKE ALL ON FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_consume_code(text) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_set_credentials(uuid, text, text) FROM PUBLIC;

REVOKE ALL ON FUNCTION app.auth_reset_credentials(uuid, boolean, boolean) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.auth_issue_code(text, uuid, uuid, uuid, text, text, text, int) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_consume_code(text) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_set_credentials(uuid, text, text) TO erp_app;

GRANT EXECUTE ON FUNCTION app.auth_reset_credentials(uuid, boolean, boolean) TO erp_app;

REVOKE CREATE ON SCHEMA app FROM erp_system;
