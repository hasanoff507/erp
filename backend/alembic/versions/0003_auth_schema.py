"""0003 auth_schema (12-db-sxema.md §6.1).

SQL: alembic/sql/0003_auth_schema.{up,down}.sql — generated from the spec.
"""

from __future__ import annotations

from app.core.db.migrations import run_sql_file

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    run_sql_file(revision, "up")


def downgrade() -> None:
    run_sql_file(revision, "down")
