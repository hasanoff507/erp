"""0027b debts_finance (12-db-sxema.md §6.1) — Bosqich 4, append-only.

SQL: alembic/sql/0027b_debts_finance.{up,down}.sql — generated from the spec (blocks marked ``-- 0027b``).
"""

from __future__ import annotations

from app.core.db.migrations import run_sql_file

revision: str = "0027b"
down_revision: str | None = "0027a"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    run_sql_file(revision, "up")


def downgrade() -> None:
    run_sql_file(revision, "down")
