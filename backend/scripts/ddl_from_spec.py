"""Split the SQL in spec/kod-uchun/12-db-sxema.md into top-level statements.

Used by ``gen_migration_sql.py`` to build ``alembic/sql/*.sql`` (whose ``--check``
mode is the spec-drift test). Statements are returned verbatim (comments kept)
together with the spec line they start on, the object they act on, the numbered
section heading they sit under and the block marker (12 §6.1), so routing never
depends on line numbers.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db.sql_script import split_sql

SPEC_FILE = Path(__file__).resolve().parents[2] / "spec" / "kod-uchun" / "12-db-sxema.md"

# "## 0. Rollar", "### 2.5a Tasdiqlash", "### 4.5 `SECURITY DEFINER`" → "0", "2.5a", "4.5"
_HEADING = re.compile(r"^#{2,4}\s+(\d+(?:\.\d+)?[a-z]?)\.?\s")
# first line of a block: "-- 0015 registers", "-- 0027a down", "-- DBA bootstrap", "-- namuna: ..."
_MARKER = re.compile(r"^--\s*(\d{4}[a-z]?(?: down)?\b|DBA bootstrap|namuna\b)")


@dataclass(frozen=True)
class SqlBlock:
    line: int  # 1-based line of the first SQL line
    body: str
    section: str  # number of the nearest numbered heading above the block
    marker: str | None  # "0015", "DBA bootstrap", "namuna" or None


@dataclass(frozen=True)
class Statement:
    line: int
    sql: str
    kind: str
    target: str
    section: str = ""
    marker: str | None = None


def sql_blocks(text: str) -> list[SqlBlock]:
    blocks: list[SqlBlock] = []
    lines = text.splitlines()
    section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        heading = _HEADING.match(line)
        if heading:
            section = heading.group(1)
        if line.startswith("```"):
            fence_is_sql = line.startswith("```sql")
            start = i + 2  # 1-based number of the first body line
            body: list[str] = []
            i += 1
            while not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            if fence_is_sql:
                first = next((b.strip() for b in body if b.strip()), "")
                m = _MARKER.match(first)
                blocks.append(SqlBlock(start, "\n".join(body), section, m.group(1) if m else None))
        i += 1
    return blocks


def _strip_comments(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("table", re.compile(r"CREATE TABLE (?:IF NOT EXISTS )?([\w.]+)", re.I)),
    ("index", re.compile(r"CREATE (?:UNIQUE )?INDEX (?:IF NOT EXISTS )?\w+ ON (?:ONLY )?([\w.]+)", re.I)),
    ("alter", re.compile(r"ALTER TABLE (?:ONLY )?([\w.]+)", re.I)),
    ("function", re.compile(r"CREATE (?:OR REPLACE )?FUNCTION ([\w.]+)", re.I)),
    ("alter_function", re.compile(r"ALTER FUNCTION ([\w.]+)", re.I)),
    (
        "trigger",
        re.compile(r"CREATE (?:CONSTRAINT )?TRIGGER \w+\s+(?:BEFORE|AFTER)[\w\s,]*? ON ([\w.]+)", re.I),
    ),
    ("comment", re.compile(r"COMMENT ON (?:TABLE|COLUMN|FUNCTION) ([\w.]+)", re.I)),
    ("policy", re.compile(r"CREATE POLICY \w+ ON ([\w.]+)", re.I)),
    ("schema", re.compile(r"CREATE SCHEMA", re.I)),
    ("role", re.compile(r"CREATE ROLE (\w+)", re.I)),
    ("do", re.compile(r"DO \$\$", re.I)),
]


def classify(sql: str) -> tuple[str, str]:
    body = _strip_comments(sql).strip()
    for kind, pat in _PATTERNS:
        m = pat.match(body) if kind != "trigger" else pat.search(body)
        if m and (kind == "trigger" or m.start() == 0):
            return kind, (m.group(1) if m.groups() else "")
    first = body.split(None, 2)
    return (" ".join(first[:2]).lower() if first else "?"), ""


def statements(spec_file: Path = SPEC_FILE) -> list[Statement]:
    text = spec_file.read_text(encoding="utf-8")
    result: list[Statement] = []
    for block in sql_blocks(text):
        for line, sql in split_sql(block.body, block.line):
            kind, target = classify(sql)
            if kind == "comment" and target.count(".") == 2:
                target = target.rsplit(".", 1)[0]
            result.append(Statement(line, sql, kind, target, block.section, block.marker))
    return result


if __name__ == "__main__":
    for st in statements():
        print(f"{st.line:5d} §{st.section:5s} {st.marker or '':14s} {st.kind:14s} {st.target}")
