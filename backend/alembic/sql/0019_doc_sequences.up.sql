-- 0019 doc_sequences — generated from spec/kod-uchun/12-db-sxema.md by scripts/gen_migration_sql.py; do not edit by hand.

CREATE TABLE app.doc_sequences (
  tenant_id  UUID NOT NULL REFERENCES app.tenants(id),
  branch_id  UUID NOT NULL REFERENCES app.branches(id),
  doc_type   TEXT NOT NULL,
  year       INT NOT NULL,
  next_value BIGINT NOT NULL DEFAULT 1,
  PRIMARY KEY (tenant_id, branch_id, doc_type, year)
);

CREATE OR REPLACE FUNCTION app.next_doc_number(
  p_tenant_id uuid, p_branch_id uuid, p_branch_code text, p_doc_type text, p_year int
) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE v_next bigint;
BEGIN
  INSERT INTO app.doc_sequences (tenant_id, branch_id, doc_type, year, next_value)
  VALUES (p_tenant_id, p_branch_id, p_doc_type, p_year, 2)
  ON CONFLICT (tenant_id, branch_id, doc_type, year)
  DO UPDATE SET next_value = app.doc_sequences.next_value + 1
  RETURNING next_value - 1 INTO v_next;
  RETURN format('%s-%s-%s-%s', p_doc_type, p_branch_code, p_year, lpad(v_next::text, 6, '0'));
END;
$$;
