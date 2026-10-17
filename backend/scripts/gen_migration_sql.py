"""Generate ``alembic/sql/NNNN_<name>.{up,down}.sql`` from 12-db-sxema.md.

The DDL in the spec is the authority: every ``up`` statement is copied verbatim
from a ```sql block of 12. Each block is routed by the rule in 12 §6.1:

1. a marker on the block's first line — ``-- NNNN <name>`` (that revision),
   ``-- DBA bootstrap`` (not a revision) or ``-- namuna`` (an example, not DDL);
2. otherwise the numbered section heading above the block (``SECTION_ROUTES``);
   in the table sections (2.1–2.9) each statement follows its table
   (``TABLES`` mirrors the 12 §6.1 plan).

Revision 0027a (web_pos, Bosqich 3) is append-only: its blocks carry the marker
``-- 0027a web_pos`` (up) or ``-- 0027a down`` (verbatim down statements — ALTER/DROP
COLUMN, previous function bodies — that cannot be derived). Revisions 0028
(store_agent, Bosqich 5) and 0029 (onec_integration, Bosqich 7) are not generated
yet. Other ``down`` scripts are derived from what ``up`` creates.

    uv run python scripts/gen_migration_sql.py          # write files
    uv run python scripts/gen_migration_sql.py --check  # exit 1 on drift
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ddl_from_spec import SPEC_FILE, Statement, statements

OUT_DIR = Path(__file__).resolve().parents[1] / "alembic" / "sql"

REVISIONS: dict[str, str] = {
    "0001": "extensions_roles_schemas",
    "0002": "core_tenant_user",
    "0003": "auth_schema",
    "0004": "label_templates",
    "0005": "valuation_method_history",
    "0006": "counterparties",
    "0007": "platform_global",
    "0008": "catalog_pricing",
    "0009": "counterparty_statement_links",
    "0010": "approval_payment_infra",
    "0011": "docs_sales",
    "0012": "docs_returns",
    "0013": "docs_purchasing",
    "0014": "docs_inventory",
    "0015": "registers",
    "0016": "ledger_adjustments",
    "0017": "docs_pricing_debts",
    "0018": "docs_expenses_cash",
    "0019": "doc_sequences",
    "0020": "fiscal_marking_edocs",
    "0021": "ai_ocr_jobs",
    "0022": "integration_sync",
    "0023": "notifications_ai",
    "0024": "audit_periods",
    "0025": "updated_at_triggers",
    "0026": "rls_policies",
    "0027": "security_definer_functions",
    "0027a": "web_pos",  # Bosqich 3 — append-only (27 B3: device-bound login, POS deltas)
}
LATER_REVISIONS = frozenset({"0028", "0029"})  # Bosqich 5 / 7

TABLES_ROUTE = "tables"
SKIP = "skip"
DEFERRED = "deferred"

# 12 §6.1 rule 2 — numbered section → revision (unmarked blocks only)
SECTION_ROUTES: dict[str, str] = {
    "0": "0001",  # role check DO block (the bootstrap block carries "-- DBA bootstrap")
    "1.1": "0001",
    "1.2": "0001",
    "1.4": "0001",
    **dict.fromkeys(("2.1", "2.2", "2.3", "2.4", "2.5", "2.5a", "2.6", "2.7", "2.8", "2.9"), TABLES_ROUTE),
    "2.11": DEFERRED,
    "3": "0001",  # app.forbid_mutation(); the per-revision blocks are marked
    "4.1": "0026",
    "4.2": "0026",
    "4.3": "0026",
    "4.4": "0026",
    "4.5": "0027",
    "5.1": SKIP,
    "5.2": SKIP,
    "6.2": SKIP,
}

# 12 §6.1 — table -> revision
TABLES: dict[str, list[str]] = {
    "0002": [
        "app.tenants",
        "app.users",
        "app.branches",
        "app.branch_tax_settings",
        "app.warehouses",
        "app.cash_registers",
        "app.devices",
        "app.memberships",
        "app.roles",
        "app.role_permissions",
    ],
    "0003": [
        "platform.oauth_clients",
        "auth.user_credentials",
        "auth.otp_challenges",
        "auth.login_attempts",
        "auth.authorization_codes",
        "auth.refresh_tokens",
        "auth.sessions",
        "app.license_tokens",
        "app.user_identities",
    ],
    "0004": ["platform.label_templates", "platform.marking_product_groups"],
    "0005": ["app.valuation_method_history"],
    "0006": ["app.counterparties", "app.debt_doubtful_flags"],
    "0007": [
        "platform.plans",
        "platform.addons",
        "platform.units",
        "platform.signing_keys",
        "platform.platform_admins",
        "platform.fx_rates",
        "platform.terms_versions",
        "platform.turnover_tax_rates",
        "platform.card_bin_rules",
        "app.subscriptions",
        "app.tenant_addons",
        "app.billing_payments",
        "app.tenant_tax_regimes",
        "app.consents",
    ],
    "0008": [
        "app.product_categories",
        "app.products",
        "app.product_barcodes",
        "app.product_prices",
        "app.label_print_queue",
        "app.internal_barcode_seq",
        "app.discount_rules",
    ],
    "0009": ["app.counterparty_statement_links"],
    "0010": ["app.approval_requests", "app.doc_approvals", "app.payment_checkouts", "app.card_terminals"],
    "0011": [
        "app.shifts",
        "app.sales",
        "app.sale_lines",
        "app.card_terminal_transactions",
        "app.sale_payments",
    ],
    "0012": ["app.returns", "app.return_lines"],
    "0013": ["app.purchase_orders", "app.po_lines", "app.goods_receipts", "app.receipt_lines"],
    "0014": [
        "app.transfers",
        "app.transfer_lines",
        "app.stock_counts",
        "app.count_lines",
        "app.write_offs",
        "app.write_off_lines",
        "app.stock_openings",
        "app.opening_lines",
    ],
    "0015": [
        "app.stock_moves",
        "app.stock_lots",
        "app.supplier_returns",
        "app.supplier_return_lines",
        "app.avg_costs",
        "app.stock_balances",
        "app.debt_moves",
        "app.debt_balances",
        "app.cash_moves",
        "app.ledger_entries",
        "app.vat_moves",
    ],
    "0016": ["app.ledger_adjustments"],
    "0017": [
        "app.price_changes",
        "app.price_change_lines",
        "app.debt_openings",
        "app.debt_payments",
        "app.debt_payment_allocations",
        "app.debt_writeoffs",
        "app.supplier_payments",
        "app.supplier_payment_allocations",
    ],
    "0018": [
        "app.expense_categories",
        "app.recurring_expenses",
        "app.attachments",
        "app.expenses",
        "app.cash_movements",
        "app.bank_statement_imports",
        "app.bank_settlements",
        "app.card_terminal_settlements",
        "app.tax_settlements",
    ],
    "0019": ["app.doc_sequences"],
    "0020": [
        "app.fiscal_receipts",
        "app.marking_codes",
        "app.einvoices",
        "app.powers_of_attorney",
        "app.ettn_documents",
        "app.state_reports",
        "app.state_report_diffs",
    ],
    "0021": ["app.ai_requests", "app.ai_ocr_jobs"],
    "0022": [
        "app.tenant_secrets",
        "app.outbox_jobs",
        "app.sync_receipts",
        "app.sync_exceptions",
        "app.idempotency_keys",
        "app.recost_jobs",
        "app.import_jobs",
    ],
    "0023": [
        "app.telegram_links",
        "app.notification_settings",
        "app.notifications_log",
        "app.ai_training_samples",
        "app.ai_feedback",
        "app.tenant_glossary",
    ],
    "0024": ["app.audit_log", "app.period_closings"],
}
TABLE_REV = {t: rev for rev, ts in TABLES.items() for t in ts}

# functions written inside the table sections (2.x)
FUNCTION_REV = {"app.next_doc_number": "0019"}


def _marker_route(marker: str) -> str:
    if marker.endswith(" down"):
        if marker[: -len(" down")] in REVISIONS:
            return marker
        raise SystemExit(f"unknown down marker '-- {marker}' in 12-db-sxema.md")
    if marker in ("DBA bootstrap", "namuna"):
        return SKIP
    if marker in REVISIONS:
        return marker
    if marker in LATER_REVISIONS:
        return DEFERRED
    raise SystemExit(f"unknown block marker '-- {marker}' in 12-db-sxema.md")


def route(st: Statement, last_table_rev: str) -> str:
    """Revision of one statement (12 §6.1 routing rule)."""
    if st.marker is not None:
        return _marker_route(st.marker)
    section = SECTION_ROUTES.get(st.section)
    if section is None:
        raise SystemExit(
            f"spec line {st.line}: §{st.section} has no default revision — mark the block (12 §6.1)"
        )
    if section != TABLES_ROUTE:
        return section
    if st.kind == "function":
        if st.target not in FUNCTION_REV:
            raise SystemExit(f"spec line {st.line}: function {st.target} has no revision")
        return FUNCTION_REV[st.target]
    if st.target in TABLE_REV:
        # a deferred FK/index written right after the table it depends on
        # (e.g. fk_bp_invoice_attachment after attachments) goes with that table
        return max(TABLE_REV[st.target], last_table_rev)
    raise SystemExit(f"unrouted statement at spec line {st.line}: {st.kind} {st.target}")


_TRIGGER = re.compile(r"CREATE TRIGGER (\w+)\s+(?:BEFORE|AFTER)[\w\s,]*?\sON\s+([\w.]+)", re.I)
_DO_TRIGGER = re.compile(r"CREATE TRIGGER (\w+)\s+(?:BEFORE|AFTER)[\w\s,]*?\sON\s+%s", re.I)
_DO_ARRAY = re.compile(r"ARRAY\s*\[([^\]]*)\]", re.S)
_GRANT_SELECT_SYSTEM = re.compile(r"GRANT SELECT ON (.+?)\s+TO erp_system\s*;", re.I | re.S)


def _triggers(st: Statement) -> list[tuple[str, str]]:
    """``(trigger, table)`` pairs created by a statement (plain or a FOREACH DO block)."""
    if st.kind == "trigger":
        m = _TRIGGER.search(st.sql)
        return [(m.group(1), m.group(2))] if m else []
    if st.kind == "do":
        named = _DO_TRIGGER.search(st.sql)
        arr = _DO_ARRAY.search(st.sql)
        if named and arr:
            tables = re.findall(r"'([\w.]+)'", arr.group(1))
            return [(named.group(1), t) for t in tables]
    return []


def _qualified_index(sql: str, table: str) -> str:
    m = re.search(r"INDEX (?:IF NOT EXISTS )?(\w+)", sql, re.I)
    assert m is not None
    return f"{table.split('.')[0]}.{m.group(1)}"


def build() -> dict[str, tuple[str, str]]:
    up: dict[str, list[str]] = defaultdict(list)
    tables_in: dict[str, list[str]] = defaultdict(list)
    functions_in: dict[str, list[str]] = defaultdict(list)
    foreign_constraints: dict[str, list[tuple[str, str]]] = defaultdict(list)
    foreign_indexes: dict[str, list[str]] = defaultdict(list)
    foreign_triggers: dict[str, list[tuple[str, str]]] = defaultdict(list)
    system_grants: dict[str, list[str]] = defaultdict(list)
    explicit_down: dict[str, list[str]] = defaultdict(list)

    last_table_rev = "0000"
    for st in statements():
        if st.kind == "table" and st.target in TABLE_REV:
            last_table_rev = TABLE_REV[st.target]
        rev = route(st, last_table_rev)
        if rev in (SKIP, DEFERRED):
            continue
        if rev.endswith(" down"):
            explicit_down[rev[: -len(" down")]].append(st.sql + "\n")
            continue
        up[rev].append(st.sql + "\n")
        if st.kind == "table":
            tables_in[rev].append(st.target)
        elif st.kind == "function":
            functions_in[rev].append(st.target)
        elif st.kind == "alter" and TABLE_REV.get(st.target) != rev:
            for name in re.findall(r"ADD CONSTRAINT (\w+)", st.sql):
                foreign_constraints[rev].append((st.target, name))
        elif st.kind == "index" and TABLE_REV.get(st.target) != rev:
            foreign_indexes[rev].append(_qualified_index(st.sql, st.target))
        for trigger, table in _triggers(st):
            if TABLE_REV.get(table, rev) != rev:
                foreign_triggers[rev].append((trigger, table))
        system_grants[rev].extend(" ".join(g.split()) for g in _GRANT_SELECT_SYSTEM.findall(st.sql))

    out: dict[str, tuple[str, str]] = {}
    for rev, name in REVISIONS.items():
        header = (
            f"-- {rev} {name} — generated from spec/kod-uchun/12-db-sxema.md by "
            "scripts/gen_migration_sql.py; do not edit by hand.\n\n"
        )
        down = _down(
            rev,
            tables_in[rev],
            functions_in[rev],
            foreign_constraints[rev],
            foreign_indexes[rev],
            foreign_triggers[rev],
            system_grants[rev],
        )
        if explicit_down[rev]:  # append-only revisions: derived drops first, then the hand-written
            # down statements (they restore the previous function bodies the derived drops removed)
            down = (down + "\n" if down else "") + "\n".join(explicit_down[rev])
        out[rev] = (header + "\n".join(up[rev]), header + down)
    return out


def _down(
    rev: str,
    tables: list[str],
    functions: list[str],
    constraints: list[tuple[str, str]],
    indexes: list[str],
    triggers: list[tuple[str, str]],
    system_grants: list[str],
) -> str:
    parts: list[str] = []
    if rev == "0001":
        return (
            "DROP SCHEMA IF EXISTS app CASCADE;\nDROP SCHEMA IF EXISTS auth CASCADE;\n"
            "DROP SCHEMA IF EXISTS platform CASCADE;\nDROP EXTENSION IF EXISTS pg_trgm;\n"
            "DROP EXTENSION IF EXISTS pgcrypto;\n"
            "-- roles (erp_migrator/erp_app/erp_system) are cluster-wide and are kept.\n"
        )
    if rev == "0025":
        return _DROP_UPDATED_AT_TRIGGERS
    if rev == "0026":
        parts.append(_DROP_RLS)
    for objects in system_grants:  # object lists come from the spec's GRANT statements
        parts.append(f"REVOKE SELECT ON {objects} FROM erp_system;\n")  # noqa: S608
    for trigger, table in triggers:
        parts.append(f"DROP TRIGGER IF EXISTS {trigger} ON {table};\n")
    for idx in reversed(indexes):
        parts.append(f"DROP INDEX IF EXISTS {idx};\n")
    for table, name in reversed(constraints):
        parts.append(f"ALTER TABLE IF EXISTS {table} DROP CONSTRAINT IF EXISTS {name};\n")
    for t in reversed(tables):
        parts.append(f"DROP TABLE IF EXISTS {t} CASCADE;\n")
    for f in reversed(functions):
        parts.append(f"DROP FUNCTION IF EXISTS {f} CASCADE;\n")
    return "".join(parts)


_DROP_UPDATED_AT_TRIGGERS = """\
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
"""

_DROP_RLS = """\
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
"""


def main() -> int:
    check = "--check" in sys.argv
    if not SPEC_FILE.exists():
        print(f"spec not found: {SPEC_FILE}", file=sys.stderr)
        return 2
    drift = False
    expected: set[str] = set()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for rev, (up_sql, down_sql) in build().items():
        name = REVISIONS[rev]
        for suffix, content in (("up", up_sql), ("down", down_sql)):
            path = OUT_DIR / f"{rev}_{name}.{suffix}.sql"
            expected.add(path.name)
            if check:
                if not path.exists() or path.read_text(encoding="utf-8") != content:
                    print(f"drift: {path.name}")
                    drift = True
            else:
                path.write_text(content, encoding="utf-8", newline="\n")
    stray = sorted(p.name for p in OUT_DIR.glob("*.sql") if p.name not in expected)
    if stray:
        print("not generated from the spec: " + ", ".join(stray))
        drift = True
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
