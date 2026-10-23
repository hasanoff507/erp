"""Export the backend OpenAPI schema; in CI, fail if the committed client schema drifted (23 §7.1).

The app is built through its factory without starting it (no DB/Redis), the same
way ``web/scripts/api-gen.mjs`` (``pnpm api:export``) does.

    uv run python scripts/export_openapi.py                 # print to stdout
    uv run python scripts/export_openapi.py -o PATH         # write PATH
    uv run python scripts/export_openapi.py --check PATH    # exit 1 if PATH differs (semantically)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SCHEMA = ROOT.parent / "web" / "packages" / "shared" / "api" / "openapi.json"


def build_schema() -> dict[str, Any]:
    from app.core.config import Settings
    from app.main import create_app

    # ignore a developer's local .env so the export is deterministic
    schema: dict[str, Any] = create_app(Settings(_env_file=None)).openapi()
    return schema


def _diff_paths(expected: Any, actual: Any, path: str = "$") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        out: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                out.append(f"+ {path}.{key}")
            elif key not in actual:
                out.append(f"- {path}.{key}")
            else:
                out.extend(_diff_paths(expected[key], actual[key], f"{path}.{key}"))
        return out
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        out = []
        for i, (e, a) in enumerate(zip(expected, actual, strict=True)):
            out.extend(_diff_paths(e, a, f"{path}[{i}]"))
        return out
    return [] if expected == actual else [f"~ {path}"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-o", "--output", type=Path, help="write the schema to this file")
    group.add_argument(
        "--check",
        type=Path,
        nargs="?",
        const=DEFAULT_SCHEMA,
        help=f"compare with a committed schema (default: {DEFAULT_SCHEMA})",
    )
    args = parser.parse_args(argv)

    schema = build_schema()
    if args.check is not None:
        committed = json.loads(args.check.read_text(encoding="utf-8"))
        if committed == schema:
            print(f"OpenAPI schema matches {args.check}")
            return 0
        diff = _diff_paths(committed, schema)
        print(f"OpenAPI schema drift vs {args.check} ({len(diff)} differences):", file=sys.stderr)
        for line in diff[:50]:
            print(f"  {line}", file=sys.stderr)
        print(
            "Regenerate: cd web && pnpm api:export (then commit openapi.json + generated client)",
            file=sys.stderr,
        )
        return 1

    text = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
