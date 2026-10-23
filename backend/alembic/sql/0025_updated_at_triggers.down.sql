-- 0025 updated_at_triggers — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT tg.tgname, c.relname, n.nspname
    FROM pg_trigger tg
    JOIN pg_class c ON c.oid = tg.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE tg.tgname = 'trg_set_updated_at' AND n.nspname IN ('app', 'platform')
  LOOP
    EXECUTE format('DROP TRIGGER %I ON %I.%I', r.tgname, r.nspname, r.relname);
  END LOOP;
END $$;
