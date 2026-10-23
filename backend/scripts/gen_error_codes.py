"""Generate ``app/core/error_codes.py`` from the catalog in 17-api-umumiy.md §15.

17 §15 is the single source of error codes (32 §2.6); the Python enum is never
edited by hand.

    uv run python scripts/gen_error_codes.py          # write
    uv run python scripts/gen_error_codes.py --check  # exit 1 on drift
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT.parent / "spec" / "kod-uchun" / "17-api-umumiy.md"
OUT = ROOT / "app" / "core" / "error_codes.py"

_ROW = re.compile(
    r"^\|\s*(?P<domain>[^|]+?)\s*\|\s*`(?P<code>[A-Z0-9_]+)`\s*\|\s*(?P<http>[^|]+?)\s*\|\s*`(?P<key>[^`]+)`"
)


def parse(text: str) -> list[tuple[str, str, int | None, str]]:
    section = text.split("## 15. Xato kodlari katalogi", 1)[1].split("### 15.1", 1)[0]
    rows: list[tuple[str, str, int | None, str]] = []
    seen: set[str] = set()
    for line in section.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        code = m.group("code")
        if code in seen:
            raise SystemExit(f"duplicate code in 17 §15: {code}")
        seen.add(code)
        http = re.match(r"(\d{3})", m.group("http"))
        rows.append((m.group("domain"), code, int(http.group(1)) if http else None, m.group("key")))
    return rows


def render(rows: list[tuple[str, str, int | None, str]]) -> str:
    out = [
        '"""Error code catalog — GENERATED from spec/kod-uchun/17-api-umumiy.md §15.',
        "",
        "Do not edit by hand: run ``uv run python scripts/gen_error_codes.py``.",
        "``http_status`` is None for codes that never appear as an HTTP error",
        "(1C item/task results); 200/202 codes travel in ``warnings[]``.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "from enum import StrEnum",
        "from typing import Final",
        "",
        "",
        "class ErrorCode(StrEnum):",
    ]
    out += [f'    {code} = "{code}"' for _, code, _, _ in rows]
    out += [
        "",
        "",
        "@dataclass(frozen=True, slots=True)",
        "class ErrorSpec:",
        "    domain: str",
        "    http_status: int | None",
        "    message_key: str",
        "",
        "",
        "ERROR_SPECS: Final[dict[ErrorCode, ErrorSpec]] = {",
    ]
    for domain, code, http, key in rows:
        out.append(f'    ErrorCode.{code}: ErrorSpec("{domain}", {http}, "{key}"),')
    out += ["}", ""]
    return "\n".join(out)


def main() -> int:
    rows = parse(SPEC.read_text(encoding="utf-8"))
    content = render(rows)
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != content:
            print("drift: app/core/error_codes.py differs from 17 §15")
            return 1
        return 0
    OUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"{len(rows)} codes -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
