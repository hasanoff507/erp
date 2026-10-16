-- Restore verification (15 §7.2): run with `psql -X -v ON_ERROR_STOP=1 -f verify-restore.sql` as a
-- superuser of the RESTORED cluster (RLS does not apply to it). Any failed check RAISEs → exit != 0.
\pset footer off

-- 1. The cluster left recovery (promoted) and is writable.
DO $$
BEGIN
  IF pg_is_in_recovery() THEN
    RAISE EXCEPTION 'klaster hali recovery holatida';
  END IF;
END $$;

-- 2. Schema version (compare with `alembic heads` of the deployed release).
SELECT version_num AS alembic_version FROM public.alembic_version;

-- 3. Core tables exist; tenants is never empty in production.
DO $$
DECLARE
  n bigint;
BEGIN
  SELECT count(*) INTO n FROM app.tenants;
  IF n = 0 THEN
    RAISE EXCEPTION 'app.tenants bo''sh — tiklash noto''g''ri';
  END IF;
END $$;

SELECT 'tenants' AS jadval, count(*) AS qatorlar FROM app.tenants
UNION ALL SELECT 'users', count(*) FROM app.users
UNION ALL SELECT 'products', count(*) FROM app.products
UNION ALL SELECT 'sales', count(*) FROM app.sales
UNION ALL SELECT 'stock_lots', count(*) FROM app.stock_lots
UNION ALL SELECT 'ledger_entries', count(*) FROM app.ledger_entries
UNION ALL SELECT 'audit_log', count(*) FROM app.audit_log;

-- 4. Freshness: the newest write must be close to the recovery target (RPO <= 5 min).
--    Compare with RECOVERY_TARGET_TIME and record the gap in docs/ops/restore-log.md.
SELECT 'audit_log' AS manba, max(created_at) AS oxirgi_yozuv FROM app.audit_log
UNION ALL SELECT 'ledger_entries', max(created_at) FROM app.ledger_entries
UNION ALL SELECT 'sales', max(created_at) FROM app.sales;

-- 5. Ledger integrity: a storno mirrors its original (same amount, Dt/Kt swapped; 13 §5.2).
DO $$
DECLARE
  bad bigint;
BEGIN
  SELECT count(*) INTO bad
  FROM app.ledger_entries r
  JOIN app.ledger_entries o ON o.id = r.reversal_of_id
  WHERE r.amount <> o.amount OR r.account_dt <> o.account_kt OR r.account_kt <> o.account_dt;
  IF bad > 0 THEN
    RAISE EXCEPTION 'storno juftliklari mos emas: % ta', bad;
  END IF;
END $$;

-- 6. Physical integrity of every valid B-tree index of the application schemas (amcheck).
CREATE EXTENSION IF NOT EXISTS amcheck;
DO $$
DECLARE
  idx regclass;
  checked int := 0;
BEGIN
  FOR idx IN
    SELECT c.oid::regclass
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_am am ON am.oid = c.relam
    WHERE n.nspname IN ('app', 'auth', 'platform') AND am.amname = 'btree' AND i.indisvalid
  LOOP
    PERFORM bt_index_check(idx);
    checked := checked + 1;
  END LOOP;
  RAISE NOTICE 'amcheck: % ta indeks tekshirildi', checked;
END $$;

SELECT 'verify-restore: OK' AS natija;
