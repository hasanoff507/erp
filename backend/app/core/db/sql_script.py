"""Split a SQL script into top-level statements (quotes, dollar quotes, comments aware)."""

from __future__ import annotations

import re

_DOLLAR = re.compile(r"\$[A-Za-z_]*\$")


def split_sql(script: str, first_line: int = 1) -> list[tuple[int, str]]:
    """Return ``(line, statement)`` pairs; comment-only chunks are dropped."""
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    line = first_line
    stmt_line: int | None = None
    dollar: str | None = None
    in_quote = False
    i, n = 0, len(script)
    while i < n:
        ch = script[i]
        if dollar is not None:
            if script.startswith(dollar, i):
                buf.append(dollar)
                i += len(dollar)
                dollar = None
                continue
        elif in_quote:
            if ch == "'":
                in_quote = False
        elif script.startswith("--", i):
            end = script.find("\n", i)
            end = n if end == -1 else end
            buf.append(script[i:end])
            i = end
            continue
        elif ch == "'":
            in_quote = True
        elif ch == "$":
            m = _DOLLAR.match(script, i)
            if m:
                dollar = m.group(0)
                if stmt_line is None:
                    stmt_line = line
                buf.append(dollar)
                i += len(dollar)
                continue
        elif ch == ";":
            buf.append(";")
            if stmt_line is not None:
                out.append((stmt_line, "".join(buf).strip()))
            buf, stmt_line = [], None
            i += 1
            continue
        if ch == "\n":
            line += 1
        elif not ch.isspace() and stmt_line is None:
            stmt_line = line
        buf.append(ch)
        i += 1
    if stmt_line is not None and "".join(buf).strip():
        out.append((stmt_line, "".join(buf).strip()))
    return out
