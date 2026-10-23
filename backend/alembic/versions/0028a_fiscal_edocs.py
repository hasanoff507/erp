"""0028a fiscal_edocs (12-db-sxema.md §6.1) — Bosqich 5, append-only.

SQL: alembic/sql/0028a_fiscal_edocs.{up,down}.sql — generated from the spec (blocks marked ``-- 0028a``).
"""

from __future__ import annotations

from app.core.db.migrations import run_sql_file

revision: str = "0028a"
down_revision: str | None = "0028"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    run_sql_file(revision, "up")


def downgrade() -> None:
    run_sql_file(revision, "down")
