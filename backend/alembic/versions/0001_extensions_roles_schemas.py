"""0001 extensions_roles_schemas (12-db-sxema.md §6.1).

SQL: alembic/sql/0001_extensions_roles_schemas.{up,down}.sql — generated from the spec.
"""

from __future__ import annotations

from app.core.db.migrations import run_sql_file

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    run_sql_file(revision, "up")


def downgrade() -> None:
    run_sql_file(revision, "down")
