"""0027a web_pos (12-db-sxema.md §6.1) — Bosqich 3, append-only.

SQL: alembic/sql/0027a_web_pos.{up,down}.sql — generated from the spec (blocks marked ``-- 0027a``).
"""

from __future__ import annotations

from app.core.db.migrations import run_sql_file

revision: str = "0027a"
down_revision: str | None = "0027"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    run_sql_file(revision, "up")


def downgrade() -> None:
    run_sql_file(revision, "down")
