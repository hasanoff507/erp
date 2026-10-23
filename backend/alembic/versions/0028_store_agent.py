"""0028 store_agent (12-db-sxema.md §2.11, §6.1) — Bosqich 5: Do'kon agenti registry.

SQL: alembic/sql/0028_store_agent.{up,down}.sql — generated from the spec
(blocks marked ``-- 0028 store_agent``).
"""

from __future__ import annotations

from app.core.db.migrations import run_sql_file

revision: str = "0028"
down_revision: str | None = "0027b"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    run_sql_file(revision, "up")


def downgrade() -> None:
    run_sql_file(revision, "down")
