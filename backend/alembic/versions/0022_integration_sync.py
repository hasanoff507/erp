"""0022 integration_sync (12-db-sxema.md §6.1).

SQL: alembic/sql/0022_integration_sync.{up,down}.sql — generated from the spec.
"""

from __future__ import annotations

from app.core.db.migrations import run_sql_file

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    run_sql_file(revision, "up")


def downgrade() -> None:
    run_sql_file(revision, "down")
