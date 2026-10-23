-- 0026 rls_policies — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE OR REPLACE FUNCTION app.current_tenant_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;

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
