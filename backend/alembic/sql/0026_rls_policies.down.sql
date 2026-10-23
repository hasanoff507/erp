-- 0026 rls_policies — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT schemaname, tablename, policyname FROM pg_policies WHERE schemaname = 'app' LOOP
    EXECUTE format('DROP POLICY %I ON %I.%I', r.policyname, r.schemaname, r.tablename);
  END LOOP;
  FOR r IN
    SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'app' AND c.relkind = 'r' AND c.relrowsecurity
  LOOP
    EXECUTE format('ALTER TABLE %I.%I NO FORCE ROW LEVEL SECURITY', r.nspname, r.relname);
    EXECUTE format('ALTER TABLE %I.%I DISABLE ROW LEVEL SECURITY', r.nspname, r.relname);
  END LOOP;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA app FROM erp_app;
REVOKE ALL ON ALL TABLES IN SCHEMA platform FROM erp_app;
REVOKE ALL ON ALL TABLES IN SCHEMA auth FROM erp_system;
DROP FUNCTION IF EXISTS app.current_user_id CASCADE;
DROP FUNCTION IF EXISTS app.current_tenant_id CASCADE;
