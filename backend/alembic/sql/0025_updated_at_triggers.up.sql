-- 0025 updated_at_triggers — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

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
