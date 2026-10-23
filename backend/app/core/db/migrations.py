"""Helpers for the SQL-file based Alembic revisions (alembic/sql/*.sql)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from alembic import op
from app.core.db.sql_script import split_sql

SQL_DIR = Path(__file__).resolve().parents[3] / "alembic" / "sql"


def run_sql_file(revision: str, direction: Literal["up", "down"]) -> None:
    matches = sorted(SQL_DIR.glob(f"{revision}_*.{direction}.sql"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected one {revision}_*.{direction}.sql in {SQL_DIR}, found {len(matches)}"
        )
    path = matches[0]
    bind = op.get_bind()
    for line, statement in split_sql(path.read_text(encoding="utf-8")):
        try:
            bind.exec_driver_sql(statement)
        except Exception as exc:
            exc.add_note(f"{path.name}:{line}")
            raise
