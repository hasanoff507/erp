-- 0003 auth_schema — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

DROP TABLE IF EXISTS app.license_tokens CASCADE;
DROP TABLE IF EXISTS app.user_identities CASCADE;
DROP TABLE IF EXISTS auth.sessions CASCADE;
DROP TABLE IF EXISTS auth.refresh_tokens CASCADE;
DROP TABLE IF EXISTS auth.authorization_codes CASCADE;
DROP TABLE IF EXISTS auth.login_attempts CASCADE;
DROP TABLE IF EXISTS auth.otp_challenges CASCADE;
DROP TABLE IF EXISTS auth.user_credentials CASCADE;
DROP TABLE IF EXISTS platform.oauth_clients CASCADE;
