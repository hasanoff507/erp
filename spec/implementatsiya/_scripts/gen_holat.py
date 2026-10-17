#!/usr/bin/env python3
"""spec/implementatsiya/00-holat.md generatori.

Manbalar (faqat o'qiladi):
  spec/kod-uchun/27-backlog.md            — bosqichlar, vazifalar, hikoyalar, "Tayyor ta'rifi"
  spec/kod-uchun/30-izchillik-matritsasi.md — US → ekran / API / jadval
  spec/kod-uchun/31-qabul-testlari.md     — QT-* ID'lari va US bog'lanishi
  spec/kod-uchun/14, 17, 18, 19, 20, 33   — endpoint kataloglari
  spec/kod-uchun/12-db-sxema.md           — jadvallar (CREATE TABLE) va revizionlar
  spec/kod-uchun/07-ekran-tafsilotlari.md — ekranlar
  spec/kod-uchun/26-ochiq-savollar-reestri.md — Jadval B (tashqi javoblar)
  backend/, web/                          — avtomatik dalil: route, test nomi, jadval ishlatilishi

Ishga tushirish (repo ildizidan, faqat stdlib):
  python spec/implementatsiya/_scripts/gen_holat.py            # 00-holat.md ni qayta yozadi
  python spec/implementatsiya/_scripts/gen_holat.py --check    # o'zgarish bo'lsa exit 1
  python spec/implementatsiya/_scripts/gen_holat.py --pytest   # dalil uchun `uv run pytest --collect-only -q` ham ishlatadi

Holatni qo'lda o'zgartirish: 00-holat.md dagi qatorning "Holat" va "Dalil" ustunini tahrirlang
— qayta generatsiyada saqlanadi (avtomatik ✅ topilmasa). Doimiy qo'lda holatlar — MANUAL lug'atida.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "spec" / "kod-uchun"
OUT = ROOT / "spec" / "implementatsiya" / "00-holat.md"
BACKEND = ROOT / "backend"
WEB = ROOT / "web"

DONE, PART, TODO, BLOCKED, LATER = "✅", "🟡", "⬜", "⛔", "⏭"
STATUSES = [DONE, PART, TODO, BLOCKED, LATER]
STAGES = ["0", "1", "2", "3", "4", "5", "6", "7", "K"]  # K — "MVP'dan keyin"
STAGE_NAME = {"K": "MVP'dan keyin"}
DASH = "–"
ELL = "…"


def read(name: str) -> str:
    return (SPEC / name).read_text(encoding="utf-8")


def clean(s: str, n: int = 160, code: bool = False) -> str:
    s = re.sub(r"\*\*", "", s) if code else re.sub(r"\*\*|`", "", s)
    s = re.sub(r"\s+", " ", s).strip().replace("|", "/")
    if len(s) > n:
        s = s[: n - 1].rstrip() + ELL
    if s.count("`") % 2:
        s += "`"
    return s


def split_row(line: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", line.strip())
    return [p.strip().replace("\\|", "|") for p in parts[1:-1]]


# ---------------------------------------------------------------- 27 backlog
@dataclass
class Stage:
    key: str
    title: str
    goal: str = ""
    tasks: list[str] = field(default_factory=list)
    stories_text: str = ""
    dod: str = ""


def parse_backlog() -> dict[str, Stage]:
    text = read("27-backlog.md")
    stages: dict[str, Stage] = {}
    blocks = re.split(r"^## ", text, flags=re.M)
    for b in blocks:
        head, _, body = b.partition("\n")
        m = re.match(r"Bosqich (\d+): (.+)", head)
        if m:
            st = Stage(m.group(1), m.group(2).strip())
            st.tasks = [ln[6:].strip() for ln in body.splitlines() if ln.startswith("- [ ] ")]
            g = re.search(r"^\*\*Maqsad:\*\* (.+)$", body, re.M)
            st.goal = g.group(1) if g else ""
            h = re.search(r"^\*\*Hikoyalar:\*\* (.+)$", body, re.M)
            st.stories_text = h.group(1) if h else ""
            d = re.search(r"^\*\*Tayyor ta'rifi:\*\* (.+)$", body, re.M)
            st.dod = d.group(1) if d else ""
            stages[st.key] = st
        elif head.startswith("MVP'dan keyin"):
            st = Stage("K", "MVP'dan keyin")
            st.tasks = [re.sub(r"^\d+\.\s+", "", ln).strip() for ln in body.splitlines() if re.match(r"^\d+\.\s", ln)]
            st.stories_text = " ".join(st.tasks)
            stages["K"] = st
    return stages


US_RE = re.compile(r"US-M(\d\d)-(\d\d)(?:\s*[…]\s*(?:US-M\d\d-)?-?(\d\d))?")


def expand_us(text: str) -> list[str]:
    out: list[str] = []
    for m in US_RE.finditer(text):
        mod, a, b = m.group(1), int(m.group(2)), m.group(3)
        rng = range(a, int(b) + 1) if b else [a]
        for i in rng:
            u = f"US-M{mod}-{i:02d}"
            if u not in out:
                out.append(u)
    # "US-M19-01…18" va "-14, -15" kabi qisqa yozuvlar 27 da yo'q; bor bo'lsa yuqoridagi yetarli
    return out


QT_RE = re.compile(r"(QT-[A-Z0-9]+(?:-[A-Z0-9]+)*)((?:\s*[…]\s*\d\d)?)((?:/\d\d)*)")


def expand_qt(text: str) -> list[str]:
    out: list[str] = []
    for m in QT_RE.finditer(text):
        tok, rng, slashes = m.group(1), m.group(2), m.group(3)
        if not re.search(r"-\d\d$", tok):
            continue
        prefix, last = tok.rsplit("-", 1)
        ids = [int(last)]
        if rng.strip():
            end = int(re.search(r"\d\d", rng).group(0))
            ids = list(range(int(last), end + 1))
        for s in re.findall(r"\d\d", slashes):
            ids.append(int(s))
        for i in ids:
            q = f"{prefix}-{i:02d}"
            if q not in out:
                out.append(q)
    return out


# ---------------------------------------------------------------- 30 matrix
@dataclass
class UsRow:
    id: str
    name: str
    mvp: str
    screens: str
    api: str
    tables: str
    stage: str


def parse_matrix() -> dict[str, UsRow]:
    rows: dict[str, UsRow] = {}
    for ln in read("30-izchillik-matritsasi.md").splitlines():
        if re.match(r"^\| US-M\d\d-\d\d \|", ln):
            c = split_row(ln)
            if len(c) >= 10:
                rows[c[0]] = UsRow(c[0], c[1], c[2], c[4], c[5], c[6], c[9])
    return rows


# ---------------------------------------------------------------- 31 QT
@dataclass
class Qt:
    id: str
    us: list[str]
    kind: str
    text: str
    section: str


def parse_qt() -> dict[str, Qt]:
    out: dict[str, Qt] = {}
    section = ""
    for ln in read("31-qabul-testlari.md").splitlines():
        if ln.startswith("#"):
            section = ln.lstrip("# ").strip()
        m = re.match(r"^\| (QT-[A-Z0-9-]+) \|", ln)
        if not m or m.group(1) in out:
            continue
        c = split_row(ln)
        us = expand_us(c[1]) if len(c) > 3 and "US-M" in c[1] else []
        kind = c[2] if us else c[1]
        out[m.group(1)] = Qt(m.group(1), us, clean(kind, 40), clean(c[-1], 150), section)
    return out


# ---------------------------------------------------------------- endpoints
@dataclass
class Ep:
    id: str  # 18#12, 20#55a, 19#31, 14#5, 17#1, 33W-01
    label: str
    paths: list[str]
    events: list[str]
    src: str
    module: str = ""
    alias: str = ""  # 14 §20: "14:/auth/license" — raqam o'zgarsa ham barqaror kalit (override/MANUAL)


def norm_path(p: str) -> str:
    p = p.strip().strip("`").split("?")[0].rstrip(".,;:)")
    p = re.sub(r"^https?://[^/]+", "", p)
    p = re.sub(r"^/api/v1(?=/)", "", p)
    p = re.sub(r"\{[^}]*\}", "{}", p)
    p = p.rstrip("/") or "/"
    return p.lower()


PATH_TOK = re.compile(r"(?<![\w.])(…?/[A-Za-z0-9_\-.{}/*:]+)")


def paths_in(text: str) -> list[str]:
    """Absolute paths plus relative ones (`/{id}/post`, `/post`) resolved against the last absolute path."""
    out: list[str] = []
    last_abs = ""
    for raw in PATH_TOK.findall(text):
        raw = raw.rstrip(".,;:")
        if raw.startswith("…/"):
            seg = raw[2:].split("/")[0]
            if last_abs and f"/{seg}" in last_abs:
                p = last_abs[: last_abs.index(f"/{seg}")] + raw[1:]
            else:
                continue
        elif raw.startswith("/{") or re.fullmatch(r"/(post|cancel|approve|reject|confirm|compare|archive|unflag|send|receive|validate|commit|retry|diffs|correction|unblock)", raw):
            if not last_abs:
                continue
            base = re.sub(r"/\{[^}]*\}.*$", "", last_abs)
            p = base + raw if raw.startswith("/{") else base + "/{}" + raw
        else:
            p = raw
            if re.match(r"^/(api/v1/)?[a-z]", p) or p.startswith("/.well-known"):
                last_abs = p
        n = norm_path(p)
        if len(n) > 1 and n not in out:
            out.append(n)
    return out


def bare_res(text: str) -> set[str]:
    """Backtick ichidagi slash'siz resurs nomlari: `debt-doubtful-flags` → /debt-doubtful-flags."""
    return {"/" + m for m in re.findall(r"`([a-z]+(?:-[a-z]+)+)`", text)}


def ep_resource(p: str) -> str:
    segs = [s for s in p.split("/") if s]
    if not segs:
        return p
    generic = {"reports", "billing", "tenant", "notifications", "ai", "auth", "oauth", "platform", "admin", "sync", "payments", ".well-known", "v1"}
    if segs[0] in generic and len(segs) > 1:
        return "/" + "/".join(segs[:2])
    return "/" + segs[0]


EVENT_RE = re.compile(r"event `([a-z_]+\.[a-z_]+)`")


def parse_endpoints() -> list[Ep]:
    eps: list[Ep] = []
    # 17 — health/metrics (17 §1 jadvali, 23 §8)
    for i, (lbl, p) in enumerate(
        [("GET /health/live", "/health/live"), ("GET /health/ready", "/health/ready"), ("GET /metrics", "/metrics"), ("GET /health (live aliasi, 27 B0)", "/health")], 1
    ):
        eps.append(Ep(f"17#{i}", lbl, [p], [], "17 §1, 23 §8"))

    # 14 — §20 (+ §18.1 platforma, §18.2 /admin/users, §9 switch-tenant)
    t14 = read("14-autentifikatsiya-oauth2.md")
    s20 = t14.split("## 20. API endpoint ro'yxati", 1)[1].split("\n## ", 1)[0]
    n = 0
    for ln in s20.splitlines():
        if not ln.startswith("| `"):
            continue
        c = split_row(ln)
        ep_txt, method = c[0], c[1]
        if ep_txt.startswith("`/platform") or ep_txt.startswith("`/admin/users") or "onec-agent" in ep_txt:
            continue  # quyida §18.1/§18.2 dan, agent — 33 A/W
        n += 1
        ps = paths_in(ep_txt.replace("`GET /billing/plan`, `/subscription`, `/addons`, `/payments`", "/billing/plan /billing/subscription /billing/addons /billing/payments"))
        lbl = ep_txt if re.match(r"`(GET|POST|PUT|PATCH|DELETE)\b", ep_txt) else f"{method} {ep_txt}"
        eps.append(Ep(f"14#{n}", clean(lbl, 90), ps, [], "14 §20", alias=f"14:{ps[0]}" if ps else ""))
    s181 = t14.split("### 18.1", 1)[1].split("### 18.2", 1)[0]
    k = 0
    for ln in s181.splitlines():
        if ln.startswith("| `") and ("/platform" in ln):
            k += 1
            c = split_row(ln)
            eps.append(Ep(f"14§18.1#{k}", clean(c[0], 90), paths_in(c[0]), [], "14 §18.1"))
    s182 = t14.split("### 18.2", 1)[1].split("\n## ", 1)[0]
    k = 0
    for ln in s182.splitlines():
        if ln.startswith("|") and "/admin/users" in ln:
            c = split_row(ln)
            for mm in re.finditer(r"`((?:GET|POST|PATCH|PUT|DELETE) /admin/users[^`]*)`", c[-1]):
                k += 1
                eps.append(Ep(f"14§18.2#{k}", clean(mm.group(1) + " — " + c[0], 90), paths_in(mm.group(1)), [], "14 §18.2"))
    if not any("/bff/switch-tenant" in e.paths for e in eps):  # 14 §20 da hali yo'q bo'lsa — §9 dan
        eps.append(Ep("14§9#1", "POST /bff/switch-tenant (tenant almashtirish)", ["/bff/switch-tenant"], [], "14 §9", alias="14:/bff/switch-tenant"))

    # 18 — §1 indeks
    t18 = read("18-api-kassa.md").split("## 1. Endpoint / voqea indeksi", 1)[1].split("\n## ", 1)[0]
    for ln in t18.splitlines():
        m = re.match(r"^\| (\d+|—) \|", ln)
        if not m:
            continue
        c = split_row(ln)
        num = c[0] if c[0] != "—" else "L"
        evs = EVENT_RE.findall(c[1])
        eps.append(Ep(f"18#{num}", clean(c[1], 90), paths_in(c[1]), evs, f"18 §{c[3]}", "M01"))

    # 19 — har "### " sarlavhasi bitta katalog qatori (rasmiy raqam yo'q — tartib bo'yicha)
    t19 = read("19-api-ombor.md")
    body19 = t19.split("\n## 1. ", 1)[1]
    body19 = "## 1. " + body19.split("\n## Ishlatilgan xato kodlari", 1)[0]
    n = 0
    sec = ""
    chunks = re.split(r"^(##+ .*)$", body19, flags=re.M)
    for i in range(1, len(chunks), 2):
        h, content = chunks[i], chunks[i + 1]
        if h.startswith("## "):
            sec = re.match(r"## ([\w.]+)", h).group(1).rstrip(".")
            continue
        if not h.startswith("### "):
            continue
        ps = paths_in(" ".join(re.findall(r"`([^`]*)`", h)))
        if not ps:
            ps = paths_in(" ".join(re.findall(r"`([^`]*)`", content[:800])))[:2]
        if not ps:
            continue
        n += 1
        eps.append(Ep(f"19#{n}", clean(h[4:], 90), ps, [], f"19 §{sec}"))

    # 20 — "Endpoint indeksi"
    t20 = read("20-api-moliya-admin.md").split("## Endpoint indeksi", 1)[1].split("\n## ", 1)[0]
    for ln in t20.splitlines():
        m = re.match(r"^\| (\d+[a-z]?) \|", ln)
        if not m:
            continue
        c = split_row(ln)
        eps.append(Ep(f"20#{c[0]}", clean(c[1] + " — " + c[3], 90), paths_in(c[1]), [], "20 indeks", c[2]))

    # 33 — W-01…W-55 (§10) va A-01…A-10 (§9.3)
    for ln in read("33-1c-integratsiya.md").splitlines():
        m = re.match(r"^\| (W-\d\d) \| (.+?) \| (.+?) \|", ln)
        if m:
            eps.append(Ep(f"33{m.group(1)}", clean(f"{m.group(2)} — {m.group(3)}", 90), paths_in(m.group(2)), [], "33 §10", "M19"))
    for i, nm in enumerate(["hello", "bases", "poll", "heartbeat", "result", "logs", "diagnostics", "task-keys", "update-manifest", "unpair"], 1):
        eps.append(Ep(f"33A-{i:02d}", f"/onec-agent/{nm} (A-{i:02d})", [f"/onec-agent/{nm}"], [], "33 §9.3", "M19"))
    return eps


# ---------------------------------------------------------------- 12 tables
@dataclass
class Table:
    fq: str
    rev: str
    in_db: bool = False  # backend/alembic/sql da bor


def parse_tables() -> list[Table]:
    text = read("12-db-sxema.md")
    rev_of: dict[str, str] = {}
    sql_dir = BACKEND / "alembic" / "sql"
    if sql_dir.exists():
        for f in sorted(sql_dir.glob("*.up.sql")):
            for m in re.finditer(r"CREATE TABLE (?:IF NOT EXISTS )?([a-z_]+\.[a-z_0-9]+)", f.read_text(encoding="utf-8")):
                rev_of.setdefault(m.group(1), f.name[:4])
    # 12 §6.1: 0028 store_agent qatori — undagi jadvallar; §2.11 ning qolganlari — 0029
    row0028 = re.search(r"^\| 0028 \|.*$", text, re.M)
    names0028 = set(re.findall(r"`((?:app|auth)\.[a-z_]+)`", row0028.group(0))) if row0028 else set()
    out: list[Table] = []
    for m in re.finditer(r"CREATE TABLE (?:IF NOT EXISTS )?([a-z_]+\.[a-z_0-9]+)", text):
        fq = m.group(1)
        if fq in [t.fq for t in out]:
            continue
        rev = rev_of.get(fq) or ("0028" if fq in names0028 else "0029" if ".onec_" in fq else "")
        out.append(Table(fq, rev, fq in rev_of))
    return out


# ---------------------------------------------------------------- screens (07)
def parse_screens() -> dict[str, str]:
    out: dict[str, str] = {}
    for ln in read("07-ekran-tafsilotlari.md").splitlines():
        m = re.match(r"^## ((?:POS|BO|ADM)-\d\d|UX-INSTALL) — (.+)$", ln)
        if m:
            out[m.group(1)] = clean(m.group(2), 80)
    return out


SCREEN_RE = re.compile(r"\b((?:POS|BO|ADM)-\d\d|UX-INSTALL)\b")

# ---------------------------------------------------------------- evidence from code
@dataclass
class Code:
    routes: dict[str, str]  # norm path -> file
    test_text: str
    test_files: dict[str, str]  # file -> text
    app_text: str
    pytest_ids: list[str]


def scan_code(use_pytest: bool) -> Code:
    routes: dict[str, str] = {}
    app_text = ""
    # spec'dan DDL/kod generatsiya qiluvchi skriptlar jadval ishlatilishiga dalil emas
    gen_scripts = {"gen_migration_sql.py", "ddl_from_spec.py", "gen_error_codes.py", "export_openapi.py"}
    for f in list((BACKEND / "app").rglob("*.py")) + list((BACKEND / "scripts").rglob("*.py")):
        t = f.read_text(encoding="utf-8")
        if f.name not in gen_scripts:
            app_text += t
        prefix = ""
        pm = re.search(r'APIRouter\(prefix="([^"]+)"', t)
        if pm:
            prefix = pm.group(1)
        for m in re.finditer(r'@(?:router|api_router)\.(?:get|post|put|patch|delete)\(\s*"([^"]*)"', t):
            p = m.group(1)
            full = (prefix + p) if prefix and not p.startswith(prefix) else p
            routes[norm_path(full)] = str(f.relative_to(ROOT)).replace("\\", "/")
    test_files: dict[str, str] = {}
    skip = {"node_modules", ".venv", "dist", ".turbo", "__pycache__", ".git", "playwright-report", "test-results", "coverage"}
    test_re = re.compile(r"(\.py$|\.(test|spec)\.(ts|tsx|js)$)")
    for base in (BACKEND / "tests", WEB):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in filenames:
                if test_re.search(fn) and (base != WEB or not fn.endswith(".py")):
                    f = Path(dirpath) / fn
                    test_files[str(f.relative_to(ROOT)).replace("\\", "/")] = f.read_text(encoding="utf-8")
    ids: list[str] = []
    if use_pytest:
        try:
            r = subprocess.run(["uv", "run", "pytest", "--collect-only", "-q"], cwd=BACKEND, capture_output=True, text=True, timeout=600)
            ids = [ln for ln in r.stdout.splitlines() if "::" in ln]
        except Exception as exc:  # noqa: BLE001
            print(f"pytest collect ishlamadi: {exc}", file=sys.stderr)
    return Code(routes, "\n".join(test_files.values()), test_files, app_text, ids)


def qt_evidence(qt: str, code: Code) -> str:
    key = qt.lower().replace("-", "_")
    for f, t in code.test_files.items():
        if re.search(rf"\b(?:test_)?{re.escape(key)}(?:_|\b)", t) or qt in t:
            m = re.search(rf"def (test_{re.escape(key)}\w*)", t)
            return f"`{f}`" + (f" :: `{m.group(1)}`" if m else "")
    return ""


def route_evidence(ep: Ep, code: Code) -> tuple[str, str]:
    hits = [p for p in ep.paths if p in code.routes]
    if not hits or len(hits) < len([p for p in ep.paths if "*" not in p]):
        if not hits:
            return "", ""
    files = sorted({code.routes[p] for p in hits})
    def pat(p: str) -> str:
        # `{}` — test ichidagi qiymat yoki f-string o'rni (`{p['id']}` ichida qo'shtirnoq bo'lishi mumkin)
        parts = re.split(r"(\{\})", p)
        return "".join(r"(?:\{[^}\n]*\}|[^\"'`\s/{])+" if x == "{}" else re.escape(x) for x in parts) + r"(?![\w/-])"

    def loose(p: str, t: str) -> bool:
        # prefiks o'zgaruvchida: `API = "/api/v1/import-jobs"` + f"{API}/{job_id}/commit"
        segs = [x for x in p.split("/") if x]
        if len(segs) < 3 or segs[-1] == "{}" or "{}" not in segs:
            return False
        return f"/{segs[0]}" in t and re.search(r"\}/" + re.escape(segs[-1]) + r"(?![\w/-])", t) is not None

    tfiles = sorted({f for f, t in code.test_files.items() if any(re.search(pat(p), t) or loose(p, t) for p in hits)})
    tested = bool(tfiles)
    full = len(hits) == len(ep.paths)
    st = DONE if (tested and full) else PART
    ev = "kod: " + ", ".join(f"`{f}`" for f in files)
    ev += ("; test: " + ", ".join(f"`{f}`" for f in tfiles[:3])) if tfiles else "; test yo'q"
    if not full:
        ev += f"; yo'q: {', '.join(p for p in ep.paths if p not in hits)}"
    return st, ev


def table_evidence(t: Table, code: Code) -> tuple[str, str]:
    if not t.in_db:
        return TODO, f"DDL migratsiyasi ({t.rev or '—'}) hali yo'q"
    in_app = t.fq in code.app_text
    tf = sorted(f for f, txt in code.test_files.items() if t.fq in txt)
    if in_app and tf:
        return DONE, f"DDL {t.rev}; kod va test: {', '.join(f'`{f}`' for f in tf[:2])}"
    return PART, f"DDL {t.rev} bor" + ("; ilova kodi bor, test yo'q" if in_app else "; modul kodi/testi yo'q")


# ---------------------------------------------------------------- manual knowledge
# Bosqich 0 — kod va testlar bilan qo'lda tekshirilgan holat (2026-10-16, commit e06e9cc).
MANUAL: dict[str, tuple[str, str]] = {
    # ---- Bosqich 0 (2026-10-17: G-02…G-12 yopildi; tashqi bandlar — ⛔)
    "B0-T01": (DONE, "`backend/app/core/` (context, db/rls, errors, idempotency, `telemetry.py`, `body_limit.py`), `backend/alembic/` 0001–0027, `backend/app/workers/` (SAQ), `backend/docker-compose.yml`, `.github/workflows/backend.yml`; test: `test_rls.py`, `test_health_and_idempotency.py`, `test_seed_and_worker.py`, `test_migrations.py`; telemetriya (G-08): `tests/unit/test_telemetry.py`, `tests/integration/test_metrics.py`"),
    "B0-T02": (DONE, "`backend/app/modules/auth/` (Authlib AS, BFF, JWKS EdDSA, refresh oilasi; jonli access tokenlarni `jti`/`fam`/`sid` Redis belgilari bilan bekor qilish — G-04; `POST /bff/switch-tenant` — G-07; AS login sahifasi BO-01 ga moslandi — G-06); test: `test_oauth.py`, `test_auth_gate_fixes.py`, `test_auth_revocation_and_switch.py`, `tests/unit/test_login_page.py`"),
    "B0-T03": (DONE, "`web/` Turborepo: `apps/shell`, `@shared/api` (orval, `src/generated/`), `@shared/ui` (shadcn), `@shared/state`, `@shared/i18n` (uz/ru), PWA (`vite-plugin-pwa`, `apps/shell/vite.config.ts`); test: vitest 347 + Playwright 53 (`apps/shell/e2e/*.spec.ts`)"),
    "B0-T04": (DONE, "global seed `backend/scripts/seed.py`, provisioning `app/modules/access/application/provisioning.py`, ruxsatlar `access/domain/permissions.py`, xarajat toifalari `expenses/domain/categories.py`, hisoblar rejasi `accounting/domain/chart_of_accounts.py`; test: `test_seed_and_worker.py::test_global_seed_values_and_rerun`, `::test_demo_tenant_provisioning`, `tests/unit/test_permissions.py`, `tests/unit/test_chart_of_accounts.py` (13 §1 bilan to'liq solishtirish — G-10). Rol limitlari NULL — 26 #179"),
    "B0-T05": (DONE, "`alembic/sql/0002`, `0007`; test: `test_migrations.py::test_devices_kind_accepts_onec_agent_qaror_58c`, `::test_signing_keys_purpose_qaror_58c`"),
    "B0-T06": (DONE, "`research_notes/ochiq-savollar/spike-datamatrix.md`; test: `tests/unit/test_spike_datamatrix.py` (16), vektorlar `tests/fixtures/datamatrix/vectors.json`; bwip-js server zahirasi kerak emas"),
    "B0-T07": (DONE, "Manrope (`@fontsource-variable/manrope`) + self-hosted Noto Sans zaxirasi (`@fontsource-variable/noto-sans`, `apps/shell/src/noto-sans-fallback.css`, `unicode-range` faqat ʻ ʼ Ққ Ғғ Ҳҳ, PWA precache — G-02, asoschi qarori 26 #141); test: `apps/shell/e2e/font-glyphs.spec.ts` (400/700/800, tofu/tizim shrifti yo'q)"),
    "B0-T08": (DONE, "mypy --strict, ruff, pip-audit, gitleaks, shellcheck (`.github/workflows/backend.yml`), ESLint pul qoidasi (`shared/config/eslint-config/rules/no-money-arithmetic.js` + test), `pnpm audit --audit-level=high` (`web.yml`), `.env.example` (test `test_env_example_lists_every_setting`), CSP nonce + statik xost sha256 zaxirasi (`apps/shell/csp.ts`, `csp-hashes.ts`, build guard; test `csp.test.ts`, `csp-hashes.test.ts`, `e2e/csp-nonce.spec.ts` — G-05), `get-nonce` pnpm katalogida (G-03)"),
    "B0-T09": (BLOCKED, "repo qismi bajarildi (G-09): envelope shifrlash `backend/app/core/secrets.py` (test `test_auth_units.py::test_envelope_roundtrip_binding_and_rotation`), `.sops.yaml` (age), WAL-G zaxira/PITR/offsite/staging-restore skriptlari `backend/ops/backup/*.sh` + `RUNBOOK-backup-restore.md`, test `tests/unit/test_ops_backup.py`; tashqi (asoschi): UzCloud avto-to'lov + billing ogohlantirishi, DBaaS replikatsiya roli, S3 bucket'lar (UzCloud + ikkinchi provayder), age/WAL-G kalitlari — runbook ⛔ bo'limi"),
    "B0-T10": (DONE, "`backend/app/modules/ai/privacy/masking.py` (o'chirib bo'lmaydi), rozilik darvozasi `ai/application/ports.py`; test: `tests/unit/test_ai_masking.py`, `tests/integration/test_ai_pii.py`"),
    "B0-T11": (BLOCKED, "asoschi — G-01"),
    "B0-T12": (BLOCKED, "#130 dan keyin; `letter_tracker` — asoschi — G-01"),
    "B0-T13": (BLOCKED, "asoschi + buxgalter — G-01 (`tests/unit/test_chart_of_accounts.py` kod ↔ 13 mosligini tekshiradi; buxgalter tasdig'i tashqi)"),
    "B0-T14": (BLOCKED, "asoschi — G-01"),
    "B0-T15": (BLOCKED, "asoschi — G-01"),
    "B0-T16": (BLOCKED, "kod qismi bajarildi (G-11): OWASP ZAP baseline + API DAST — `.github/workflows/dast.yml`, qoidalar `backend/ops/zap/rules.tsv` (test `tests/unit/test_ops_backup.py`); tashqi: ichki OAuth/to'lov/fiskal tekshiruv ro'yxati va Celion/ONESEC taklifi — asoschi"),
    "B0-T17": (BLOCKED, "asoschi — G-01 (bot/support havolalari runtime-config'da tayyor: `telegramBot`, `supportTelegram`, `supportPhone`, `supportUrl`)"),
    "B0-T18": (BLOCKED, "asoschi — G-01"),
    "B0-T19": (BLOCKED, "asoschi + yurist — G-01"),
    "B0-DoD-01": (DONE, "`backend/app/core/health.py` (`/health`, `/health/live`, `/health/ready`); test: `test_health_and_idempotency.py::test_health_ready_gates_on_postgres_schema_and_redis`, `test_core_misc.py::test_health_liveness_without_dependencies`; RLS — `tests/integration/test_rls.py`"),
    "B0-DoD-02": (DONE, "`research_notes/ochiq-savollar/spike-datamatrix.md`, `spike-font.md` (Noto zaxirasi qabul qilindi — `08` §2)"),
    "B0-DoD-03": (DONE, "`tests/unit/test_ai_masking.py` (31 holat)"),
    "B0-DoD-04": (DONE, "`tests/integration/test_oauth.py` — haqiqiy PostgreSQL 16 + Redis (testcontainers yoki CI servislari, `tests/conftest.py`)"),
    "B0-DoD-05": (DONE, "BO-01 `web/apps/shell/src/pages/login/`, layout `src/app/ui/layout/`, klient `web/packages/shared/api/src/generated/`; test: `e2e/login.spec.ts`, `e2e/session.spec.ts`, `instance.test.ts`"),
    "B0-DoD-06": (BLOCKED, "asoschi — G-01"),
    "B0-DoD-07": (BLOCKED, "asoschi — G-01"),
    "B0-DoD-08": (DONE, "`test_rls.py::test_qt_rls_01…08`, `test_oauth.py::test_qt_oauth_01…07`, `test_ai_pii.py`/`test_ai_masking.py::test_qt_ai_pii_01_*`"),
    "B0-DoD-09": (DONE, "`.github/workflows/backend.yml` (mypy --strict, pip-audit, gitleaks), `web.yml` (`pnpm audit --audit-level=high`)"),
    "B0-DoD-10": (DONE, "`tests/integration/test_migrations.py` (qaror #58 c)"),
    "B0-DoD-11": (BLOCKED, "protsedura tayyor: `backend/ops/backup/staging-restore.sh`, `verify-restore.sql`, `RUNBOOK-backup-restore.md` (staging restore bo'limi); bajarish UzCloud hisobi, bucket'lar va kalitlardan keyin — asoschi (G-09)"),
    # ekranlar
    "B0-SCR-BO-01": (DONE, "`web/apps/shell/src/pages/login/` + AS sahifasi `backend/app/modules/auth/api/login_page.py` (BO-01 maketi va 07 ga moslandi: aria-invalid, 'Parolni unutdim?', ro'yxatdan o'tish havolasi, logo — G-06); test: `e2e/login.spec.ts`, `e2e/session.spec.ts`, `tests/unit/test_login_page.py::test_bo01_fields_and_links`, `::test_error_marks_fields_invalid_without_revealing_which`"),
    "B4-SCR-BO-02": (PART, "maket-skelet `web/packages/pages/reports/src/pages/dashboard/` (qiymatlar '—'), test `model.test.ts`; `GET /reports/dashboard` yo'q"),
    "B5-SCR-BO-02": (PART, "skelet bor (B4 qatoriga qarang)"),
    # endpointlar (14 §20 — yo'l bo'yicha kalit)
    "B0-EP-14:/oauth/revoke": (DONE, "kod: `auth/api/oauth.py`, `auth/application/revocation.py` (refresh → oila + jonli access tokenlar, access → `jti`); test: `test_oauth.py::test_revoke_and_introspect`, `test_auth_revocation_and_switch.py::test_oauth_revoke_refresh_kills_live_access_token_of_its_family`, `::test_oauth_revoke_access_token_by_jti_keeps_the_family`, `::test_oauth_revoke_reuse_detection_kills_every_access_token_of_the_family`"),
    "B0-EP-14:/oauth/authorize": (DONE, "kod: `auth/api/oauth.py`, `auth/api/login_page.py`; test: `test_oauth.py`, `tests/unit/test_login_page.py` (BO-01 ko'rinishi — G-06)"),
    "B0-EP-14:/bff/switch-tenant": (DONE, "kod: `auth/api/bff.py`, `auth/application/bff.py` (14 §9); veb: `@shared/state` session `switchTenantFx`; test: `test_auth_revocation_and_switch.py::test_bff_switch_tenant_repoints_the_cookie`, `::test_bff_switch_tenant_refusals_keep_the_session`, `::test_bff_switch_tenant_needs_a_cookie_session`, `session.test.ts`"),
    "B0-EP-14:/auth/sessions/revoke-all": (DONE, "kod: `auth/api/bff.py`; test: `test_auth_revocation_and_switch.py::test_auth_revoke_all_ends_every_session_in_every_tenant` (G-12), `web/packages/shared/state/src/session/session.test.ts`"),
    "B0-EP-17#3": (DONE, "kod: `backend/app/core/telemetry.py` (`GET /metrics`, Prometheus, bearer token, `ERP_METRICS_ENABLED`; OTel/Sentry config bilan — G-08); test: `tests/integration/test_metrics.py::test_metrics_report_requests_pool_and_queue_depth`, `tests/unit/test_telemetry.py`"),
    # ---- Bosqich 1 (2026-10-17: Opus tekshiruvi — xavfsizlik/spec/veb, qabul agenti, tuzatishlar)
    "B1-T01": (DONE, "`auth/api/signup.py`, `auth/application/signup.py` (`business_type` → filial `activity_type` va birinchi `branch_tax_settings`, Toshkent sanasi), `auth/infrastructure/signup_repository.py`, `access/application/provisioning.py`, `branches/application/services.py`, `billing/application/trial.py`; test: `test_signup_flow.py::test_qt_m17_01_sms_code_then_trial_and_full_provisioning`, `::test_signup_is_one_transaction`, `::test_qt_m17_08_terms_required_current_and_consent_recorded`, `::test_signup_business_type_other_reaches_the_branch_and_its_tax_setting`, `::test_signup_rate_limited_per_ip_and_cross_origin_refused`"),
    "B1-T02": (DONE, "`branches/api/tenant.py`, `branches/application/tenant_settings.py`, `branches/api/branches.py` (`settlement_category`, standart `city_100k_plus`); test: `test_tenant_settings_api.py`, `test_branches_api.py::test_qt_m14_03/04/05_*`, `e2e/store-settings.spec.ts`, `e2e/branches.spec.ts`"),
    "B1-T03": (DONE, "`web/packages/pages/billing/src/pages/install/`, `features/install-guide/`, `apps/shell/src/features/ios-install-gate/` (`@shared/lib/platform`), ochiq route `createPublicRoutes`; test: `e2e/install.spec.ts`, `install-guide/model/model.test.ts`"),
    "B1-T04": (DONE, "`auth/application/admin_users.py::create` (mavjud hisob — `invited`, qabul qilinguncha kirish yo'q), provisioning, `branches/application/branches.py`; test: `test_admin_users_invite.py::test_qt_m13_04_invite_sends_one_time_code_never_a_secret`, `::test_invite_of_an_existing_account_waits_for_acceptance`, `test_branches_api.py::test_qt_m14_02_*`"),
    "B1-T05": (DONE, "`auth/api/admin_users.py` (PATCH `status`/`role_ids`/`branch_ids`, reset-pin/password — boshqa tenantdagi hisobda rad, Egasi nishoniga faqat Egasi), `auth/application/admin_users.py`; veb BO-11 `pages/settings/src/pages/users/`; test: `test_admin_users_update.py`, `test_admin_users_credentials.py`, `test_admin_users_sessions.py`, `test_admin_users_invite.py`, `e2e/staff.spec.ts`"),
    "B1-T06": (DONE, "`catalog/` (tovar, shtrix-kod, MXIK, toifa, birlik), `pricing/` (narx, narx tarixi `set_by_name`, `GET /products` `current_price`, narx o'zgarishlari); test: `test_catalog_products.py`, `test_catalog_mxik.py`, `test_pricing_price_changes.py`, `test_pricing_current_price.py`, `tests/unit/test_catalog_barcodes.py`, `tests/unit/test_pricing_resolution.py`, `e2e/catalog.spec.ts`, `e2e/prices.spec.ts`"),
    "B1-T07": (DONE, "`imports/` (yuklash → tekshirish/xatolar → tasdiqlash; xlsx zip/o'lcham/qator chegaralari, 413 `FILE_TOO_LARGE`); test: `test_import_jobs.py::test_us_m04_04_csv_upload_validate_commit`, `::test_upload_limits_and_file_checks`, `::test_commit_rechecks_catalog_and_rls`, `tests/unit/test_import_parsing.py::test_xlsx_far_cell_fails_fast`, `::test_zip_bomb_ratio_and_unpacked_size_are_refused_before_parsing`, `e2e/product-import.spec.ts`. Boshlang'ich qoldiq importi — B2 (27 B2 `stock_openings`), qarzlar — B4"),
    "B1-T08": (DONE, "`auth/application/otp.py`, `integrations/otp/infrastructure/{telegram,eskiz,fakes}.py` (Telegram birinchi, Eskiz test rejimi, staging/prod'da fake taqiqlangan); test: `test_otp_flow.py::test_telegram_is_the_first_channel_when_linked`, `::test_telegram_failure_falls_back_to_sms`, `::test_qt_m17_06_no_channel_delivers_503`, `::test_eskiz_test_mode_sends_only_the_allowed_text`, `::test_refused_requests_do_not_spend_the_sms_budget`, `test_otp_service.py`"),
    "B1-T09": (DONE, "`workers/cron.py` (03:30 Toshkent), `workers/jobs/system.py` (tenant fan-out, `ERP_IDEMPOTENCY_RETENTION_DAYS`); test: `test_purge_idempotency.py`"),
    "B1-T10": (DONE, "`backend/pyproject.toml` `[tool.importlinter]` (5 shartnoma), CI `.github/workflows/backend.yml` (`lint-imports`); har modulda `application/ports.py` + `wiring.py`; `lint-imports`: 5 kept, 0 broken"),
    "B1-T11": (DONE, "`auth/application/google.py`, `auth/infrastructure/google_oidc.py` (JWKS faqat noma'lum `kid`da, 60 s), `/auth/google/{start,callback}` (sozlanmagan bo'lsa → `/login?error=google_auth_failed`, IP limit); veb `googleEnabled` runtime-config; test: `test_google_login.py` (`test_qt_m17_02_*`), `tests/unit/test_auth_units.py`, `e2e/signup.spec.ts`"),
    "B1-DoD-01": (DONE, "`test_signup_flow.py::test_qt_nfr_signup_01_otp_verify_signup_session_under_two_minutes` (~1 s), `test_import_jobs.py::test_qt_nfr_signup_01_catalog_import_500_products_xlsx` (~1.3 s, < 120 s); server vaqti — brauzer e2e vaqti kuzatiladi, blok emas (31). \"Birinchi sotuv\" qismi — B3"),
    "B1-DoD-02": (DONE, "telefon+parol (OTP bilan ro'yxatdan o'tgach): `test_signup_flow.py::test_signup_owner_can_log_in_with_phone_and_password`; OTP tiklash: `test_credentials_flow.py::test_recovery_end_to_end_*`; Google: `test_google_login.py`"),
    "B1-DoD-03": (DONE, "barcha B1 QT nomli testlar bilan (pastdagi QT qatorlari); QT-M09-09 ning posting'dagi qayta tekshiruvi — B3 (sotuv kerak, 19 §4)"),
    "B1-US-M17-01": (DONE, "B1-T01, T08, T11 ga qarang; veb BO-21 `pages/billing/src/pages/onboarding/`; test: `e2e/signup.spec.ts`, `test_signup_flow.py`"),
    "B1-US-M13-01": (DONE, "`test_access_roles.py::test_qt_m13_01_role_grants_its_permissions`, `test_admin_users_invite.py::test_qt_m13_01_cashier_role_gives_cashier_permissions`"),
    "B1-US-M13-02": (DONE, "`test_access_roles.py::test_qt_m13_02_two_roles_union_and_most_generous_limit`, `test_admin_users_invite.py::test_qt_m13_02_two_roles_give_the_union_and_the_higher_right_wins`"),
    "B1-US-M13-03": (DONE, "`access/api/roles.py`, `access/application/roles.py` (limitlar rolga, Egasi — 31 QT-M13-03 tuzatildi); test: `test_access_roles.py::test_qt_m13_03_limit_change_takes_effect_immediately`, `::test_put_permissions_validation`"),
    "B1-US-M13-04": (DONE, "`test_admin_users_invite.py::test_qt_m13_04_*`, `::test_us_m13_04_staff_sees_only_assigned_branches`, `::test_invite_of_an_existing_account_waits_for_acceptance`; veb `/invite` (`credential-set`, `invite_accepted`), `e2e/credentials.spec.ts`"),
    "B1-US-M13-05": (DONE, "`test_admin_users_update.py::test_qt_m13_05_block_revokes_now_and_unblock_restores_login`, `::test_qt_m13_09_*`"),
    "B1-US-M13-06": (DONE, "`test_admin_users_credentials.py::test_qt_m13_06_reset_password_kills_sessions_and_sends_admin_reset_code`, `::test_qt_m13_06_reset_pin_forces_a_new_pin_and_keeps_sessions`; o'zi tiklash: `test_credentials_flow.py::test_recovery_end_to_end_*`; `e2e/credentials.spec.ts`. POS-01 da majburiy yangi PIN — B3"),
    "B1-US-M13-07": (DONE, "`test_admin_users_sessions.py::test_qt_m13_07_revoking_one_session_leaves_the_other`, `::test_revoke_sessions_ends_every_session_and_device_token`"),
    "B1-US-M14-03": (DONE, "`test_branches_api.py::test_qt_m14_02_*` (haqiqiy tenant kabi \"Kassa 1\" bilan — `ADDON_REQUIRED`), `::test_cash_register_patch_fiscal_pair_and_archive`"),
    "B1-US-M14-04": (DONE, "`test_branches_api.py::test_qt_m14_03/04/05_*`, `::test_patch_branch_upserts_current_month_and_keeps_history`, `tests/unit/test_branches_domain.py::test_qt_m14_05_*`, `settings/src/pages/branches/model/model.test.ts`"),
    "B1-US-M09-01": (DONE, "`test_pricing_price_changes.py::test_qt_m09_01_manager_updates_price_old_one_goes_to_history`, `tests/unit/test_pricing_resolution.py::test_qt_m09_01_*`, `e2e/prices.spec.ts`"),
    "B1-US-M09-05": (DONE, "`catalog/domain/barcodes.py`, `ProductService.generate_internal_barcode`; test: `test_catalog_products.py::test_qt_m09_05_internal_barcode_generation`, `tests/unit/test_catalog_barcodes.py`. Yorliqda chop — B6 (US-M09-04)"),
    "B1-US-M04-04": (DONE, "qo'lda: `POST /products` (`test_catalog_products.py::test_product_crud_version_archive`); import: `test_import_jobs.py::test_us_m04_04_*`, `e2e/product-import.spec.ts`. Boshlang'ich qoldiq — B2 (27 B2), AI-03 — B6"),
    "B1-SCR-BO-01": (DONE, "`apps/shell/src/pages/login/` (Google — `googleEnabled`, `/recover`, `/invite`, shartlar havolalari `GET /auth/terms` dan), AS sahifasi `auth/api/login_page.py`; test: `tests/unit/test_otp_units.py::test_login_page_has_google_and_code_entry_points_uz_ru`, `e2e/login.spec.ts`, `e2e/signup.spec.ts`. \"Ma'lumotlarimni yuklab olish\" — B6 (`/billing/export-my-data`)"),
    "B1-SCR-BO-05": (DONE, "B1 qismi: `pages/catalog/src/pages/prices/` (barcha sahifalardagi qoralamalar, doira almashtirishda tasdiq); test: `prices/model/*.test.ts`, `e2e/prices.spec.ts`. Katta o'zgarish tasdig'i (US-M09-02) — B6; Tannarx/Ustama — B2"),
    "B1-SCR-BO-11": (DONE, "`pages/settings/src/pages/users/` (xodimlar — `invited` holati, rollar — ruxsatlar uz/ru i18n, sessiyalar); test: `users/model/model.test.ts`, `shared/i18n/src/permissions.test.ts`, `e2e/staff.spec.ts`"),
    "B1-SCR-BO-12": (DONE, "B1 qismi: `pages/settings/src/pages/branches/`; test: `branches/model/model.test.ts`, `e2e/branches.spec.ts`. Konsolidatsiya (US-M14-01) — B4; karta terminallari — B3/B5"),
    "B1-SCR-BO-14": (DONE, "B1 qismi: `pages/settings/src/pages/tenant/` (yuridik shakl, siyosatlar, soliq rejimi, AI rozilik; yashirin tabdagi xato → tabga o'tish + banner); test: `tenant/model/model.test.ts`, `e2e/store-settings.spec.ts`. Integratsiya kalitlari (20 #40d/e) — B5"),
    "B1-SCR-BO-18": (DONE, "B1 qismi — ichki shtrix-kod yaratish: `pages/catalog/src/pages/products/ui/editor/Barcodes.tsx`; test: `e2e/catalog.spec.ts` (QT-M09-05/08), `test_catalog_products.py::test_qt_m09_05_internal_barcode_generation`. Yorliq navbati/chop — B6 (US-M09-04), tarozi PLU — B3 (US-M09-06)"),
    "B1-SCR-BO-21": (DONE, "`pages/billing/src/pages/onboarding/` (①② ro'yxatdan o'tish, ③a Excel/qo'lda, ⑤, ⑥ `<InstallGuide embedded/>`); test: `e2e/signup.spec.ts`, `onboarding` model testlari. ③b — B2, ④ — B4, ③ foto (AI-03) — B6"),
    "B1-TBL-app.tenant_tax_regimes": (DONE, "DDL 0007; kod `branches/infrastructure/tenant.py`; test `test_tenant_settings_api.py::test_tax_regime_from_next_month_only` (API orqali)"),
    "B1-TBL-app.internal_barcode_seq": (DONE, "DDL 0008; kod `catalog/infrastructure/repositories.py` (`lock_internal_seq`/`set_internal_seq`); test `test_catalog_products.py::test_qt_m09_05_internal_barcode_generation` (band qiymatni o'tkazib yuboradi)"),
    "B1-TBL-app.price_change_lines": (DONE, "DDL 0017; kod `pricing/infrastructure/repositories.py`; test `test_pricing_price_changes.py::test_qt_m09_01_manager_updates_price_old_one_goes_to_history` (`lines[0].old_price/new_price`)"),
    "B1-TBL-app.import_jobs": (DONE, "DDL 0022; kod `imports/infrastructure/repositories.py`; test `test_import_jobs.py::test_us_m04_04_csv_upload_validate_commit`, `::test_all_rows_invalid_fails_and_job_requires_tenant`"),
    "B1-TBL-app.doc_sequences": (DONE, "DDL 0019; kod `core/doc_numbers.py` (`app.next_doc_number`, birinchi hujjatda yaratiladi — 12 §5.2, 14 §20); test `test_pricing_price_changes.py::test_qt_m09_01_*` (`C-01-2026-000001` → `…000002`), `test_import_jobs.py::test_us_m04_04_*`"),
    "B1-SCR-UX-INSTALL": (DONE, "B1-T03 ga qarang; analitika `install_guide_viewed`/`pwa_installed`, PWA precache `apps/shell/vite.config.ts`; test: `e2e/install.spec.ts`"),
    # ---- Bosqich 2 (2026-10-17/18; 3 Opus tekshiruvchi → qabul agenti → tuzatishlar)
    "B2-T01": (DONE, "posting toolkit: `accounting/application/posting.py` (`LedgerPoster`: hisob rejasi/Dt≠Kt/summa tekshiruvi, `vat_moves`, storno — Dt/Kt almashadi, QQS manfiy, `reversal_of_id`, ochiq davr sanasi; `PERIOD_CLOSED`), `inventory/application/stock.py` (`StockService.lock` — `stock_balances` qatorlari tartibli `FOR UPDATE`, `receive`/`issue`/`reverse_*`, cost-line analitika shartnomasi), `debts/application/register.py`; har hujjat bitta `tenant_transaction`da; test: `tests/unit/test_accounting_entries.py`, `test_accounting_ledger.py` (storno, PERIOD_CLOSED), `test_inventory_concurrency.py`, `test_debt_register.py`"),
    "B2-T02": (DONE, "`purchasing/` (goods receipts: nasiya `Kt 6010` + `debt_moves`, darhol bank `Kt 5110`, tekin `Kt 8530`, QQS/aylanma rejimi, qizil/`unknown` faktura — 4410 `vat_credit='deferred'`, avans `Kt 4310`), `debts/` (kontragentlar CRUD, STIR qidiruv, qarz balansi); test: `test_goods_receipts.py` (QT-M04-01, QT-M07-02/03/04/07/08/09, §2.6a/§2.7/§2.8/§2.16/§4.3), `test_counterparties.py`, `test_purchase_orders.py`, `tests/unit/test_purchasing_posting.py`. Kassadan naqd to'lov — B4 (`supplier_payments`)"),
    "B2-T03": (DONE, "`inventory/domain/costing.py` (FIFO lot qiymati, AVECO `total_value`), `application/stock.py`, `application/recost.py` (`recost_jobs`, SAQ `inventory_recost` + 15 daqiqalik sweep, `/recost-jobs` API), qoldiq API (`/stock-balances|lots|moves`); test: `test_inventory_costing.py` (QT-M04-05/06/09/10), `test_recost_jobs.py` (QT-M04-11, yopilgan davr tuzatishi), `tests/unit/test_costing.py`, `test_inventory_stock_api.py` (QT-PERM-08/09)"),
    "B2-T04": (DONE, "`inventory/application/transfers.py` (2970 jo'natish/qabul, kamomad 5910, `TRANSFER_COST_PENDING`), `stock_counts.py` (X-02 `expected`, 4730/5910, ortiqcha 9390 `last_purchase_cost`da), `warehouses.inventory_account`; test: `test_transfers.py` (QT-M06-01…03/05/06), `test_stock_counts.py` (QT-M05-01…04/06/07). Offline `transfer.*`/`stock_count.line_recorded` — voqea nomlari va payload validatorlari `inventory/domain/*`da, `/sync/push` — B3"),
    "B2-T05": (DONE, "`ettn_documents` qoralamasi (`pending_signature`, `warehouse_to_warehouse`) transfer `post`ida; `ERP_EINVOICE_PROVIDER=fake` — `outbox_jobs(kind='ettn_send')` → `integrations/einvoice/application/ettn_outbox.py` (`FakeEInvoiceAdapter` → `registered`, `transfers.ettn_ref`, backoff 1 daq×2 cap 1 soat, 24 urinish, qulf tartibi transfer → outbox → ettn); test: `test_transfers.py::test_qt_m06_07_*`, `::test_qt_m06_08_*`, `test_ettn_outbox.py`, `tests/unit/test_ettn_lock_order.py`. Real operator va E-IMZO — B5"),
    "B2-T06": (DONE, "`purchasing/application/supplier_returns.py` (13 §2.20: `Dt 6010 / Kt inv_acct`, AVECO 3a/3b, 2-qator QQS — qo'shimcha e-faktura bilan B5; 12 oy → `reverse_sale_required`); test: `test_supplier_returns.py::test_qt_m07_06_*` va 3a/3b raqamli testlari"),
    "B2-T07": (DONE, "`inventory/application/write_offs.py` (13 §2.12: 9430/4730/9410, sovg'a QQS `Dt 9430 / Kt 6410` bozor qiymatidan + `vat_moves`, limit → `approval_requests` 202 + `over_limit_action`; partiya `expiry_date`), faqat online REST (sync voqeasi yo'q); test: `test_write_offs.py::test_qt_m04_08_*` va §2.12 matritsasi"),
    "B2-T08": (DONE, "`inventory/application/openings.py` (`Dt inv_acct / Kt 0000`, `entry_date = go_live_date − 1`, QQSsiz), `imports` `kind=opening_stock` (filial doirasi tekshiruvi); `go_live_date` ro'yxatdan o'tishda yoziladi; test: `test_stock_openings.py::test_qt_m04_04_*`, `test_import_jobs.py`"),
    "B2-T09": (DONE, "`stock_lots.blocked_qty` (`block`, `from_blocked`, bekor qilishda tiklanadi), AVECO `total_value` (eski qiymat − COGS, kirimni bekor qilish himoyasi), pending tannarx keyingi kirimda qoplanadi + recost, FIFO↔AVECO bir martalik almashtirish (`valuation.py`); test: `test_inventory_costing.py`, `test_inventory_valuation.py`, `test_write_offs.py`, `test_recost_jobs.py`"),
    "B2-T10": (DONE, "`notifications/application/outbox.py` (`outbox_jobs(kind='telegram')`, dedupe kaliti) — `expiry_soon`, `low_stock` (kunlik cron), `over_limit_action` (hisobdan chiqarish limiti); yuboruvchi worker yo'q (B4); test: `test_inventory_notifications.py::test_qt_m04_07_*`, `::test_qt_m04_02_*`, `test_write_offs.py` (202 yo'li)"),
    "B2-T11": (DONE, "`web/packages/pages/warehouse` BO-03 «Ko'chirishlar» tabi (holat, kechikkan, e-TTN ustuni, post/jo'natish/qabul/bekor) + «Qoldiq» ostidagi qisqa blok; `transfer_overdue_hours` sozlamasi; test: `features/transfers/model/*.test.ts`, `e2e/warehouse-transfers.spec.ts`, `test_transfers.py::test_qt_m06_05_*`"),
    "B2-DoD-01": (DONE, "raqamli testlar: §2.6 `test_qt_m07_03_*` (1 000 000,00 + 120 000,00), §2.6a/§2.7/§2.8/§2.16/§4.3 (`test_goods_receipts.py`), §2.9–§2.10 `test_qt_m06_01/02/03_*`, §2.11 `test_qt_m05_03_*`/`test_qt_m05_06_*` (16 000,00), §2.12 `test_qt_m04_08_*` + matritsa, §2.20 `test_supplier_returns.py` (3a/3b), §2.21 `test_qt_m04_04_*`, §3 `test_qt_m04_05_*` (980 000,00 / 270 000,00), `test_qt_m04_06_*` (8 333,3333 / 1 000 000,00 / 250 000,00), `test_qt_m04_09/10/11_*`, almashtirish `test_inventory_valuation.py`, X-02 `test_qt_m05_07_*`, `tests/unit/test_costing.py::test_x02_expected_count_qty`"),
    "B2-DoD-02": (DONE, "tekshiruv tuzatishlari (ACC-01/02/03/04/06/15, ACC-08) bilan raqamli testlar yangilandi: `test_inventory_costing.py` (AVECO kirim bekor qilish, FIFO partiya qoldig'i 33,34), `test_purchasing_posting.py` (qizil faktura 1 120 000,00), `test_transfers.py` (`TRANSFER_COST_PENDING`), `test_stock_counts.py` (bekor qilingan kirim partiyasi — 16 000,00)"),
    "B2-US-M04-01": (DONE, "`test_goods_receipts.py::test_qt_m04_01_*`, `test_inventory_costing.py::test_qt_m04_01_*`, `test_recost_jobs.py::test_qt_m04_11_*`; BO-03 — `e2e/warehouse-stock.spec.ts`"),
    "B2-US-M04-05": (DONE, "`test_qt_m04_05/06/09/10_*`, `test_inventory_valuation.py` (PATCH qoidalari, almashtirish); BO-14 — `e2e/valuation.spec.ts`"),
    "B2-US-M04-06": (DONE, "`test_inventory_notifications.py::test_qt_m04_07_*`, `test_write_offs.py::test_qt_m04_08_*`; BO-03 muddati yaqin partiyalar — `e2e/warehouse-stock.spec.ts`"),
    "B2-US-M05-01": (DONE, "`test_stock_counts.py::test_qt_m05_01_*`; BO-03 back-office sanash — `e2e/warehouse-counts.spec.ts` (POS-10 skaneri — B3)"),
    "B2-US-M05-02": (DONE, "`test_stock_counts.py::test_qt_m05_02_*`, `::test_qt_m05_07_*`; `e2e/warehouse-counts.spec.ts`"),
    "B2-US-M05-03": (DONE, "`test_stock_counts.py::test_qt_m05_03_*`, `::test_qt_m05_04_*`, `::test_qt_m05_06_*`"),
    "B2-US-M06-01": (DONE, "`test_transfers.py::test_qt_m06_01_*`, `::test_qt_m06_06_*`, `::test_qt_m06_07_*`, `::test_qt_m06_08_*`; `e2e/warehouse-transfers.spec.ts`"),
    "B2-US-M06-02": (DONE, "`test_transfers.py::test_qt_m06_02_*`, `::test_qt_m06_03_*`; `e2e/warehouse-transfers.spec.ts`"),
    "B2-US-M06-03": (DONE, "`test_transfers.py::test_qt_m06_05_*` (`is_overdue`, `transfer_overdue_hours`); BO-03 «Ko'chirishlar» — `e2e/warehouse-transfers.spec.ts`"),
    "B2-US-M07-01": (DONE, "`test_purchase_orders.py::test_qt_m07_01_*`; BO-04 — `e2e/purchases.spec.ts`"),
    "B2-US-M07-02": (DONE, "`test_goods_receipts.py::test_qt_m07_02_*`, `::test_qt_m07_07_*`, `::test_qt_m07_08_*`; `e2e/purchases.spec.ts`"),
    "B2-US-M07-05": (DONE, "`test_supplier_returns.py::test_qt_m07_06_*`; `e2e/purchases.spec.ts`"),
    "B2-US-M11-01": (DONE, "xarid qismi: kirim/qaytarish/ko'chirish/inventarizatsiya/hisobdan chiqarish/boshlang'ich qoldiq — avtomatik ikki tomonlama provodka; `test_accounting_ledger.py::test_qt_m11_01_*`, BO-08 `e2e/journal.spec.ts`. Sotuv qismi (2.1–2.4) — B3"),
    "B2-US-M04-04": (DONE, "qoldiq qismi: `test_stock_openings.py::test_qt_m04_04_*`, `test_import_jobs.py` (`opening_stock`); BO-21 ③b — `e2e/opening-stock.spec.ts`"),
    "B2-EP-19#33": (DONE, "kod: `backend/app/modules/purchasing/api/goods_receipts.py`; test: `test_goods_receipts.py` (bekor qilish storno, `LOT_ALREADY_CONSUMED`, PO qayta ochiladi)"),
    "B2-EP-19#56": (DONE, "kod: `backend/app/modules/inventory/api/transfers.py`; test: `test_transfers.py` (`act(..., 'post')` — QT-M06-07/08)"),
    "B2-EP-19#57": (DONE, "kod: `backend/app/modules/inventory/api/transfers.py`; test: `test_transfers.py` (`act(..., 'send')` — QT-M06-01, `ETTN_REQUIRED`)"),
    "B2-EP-19#58": (DONE, "kod: `backend/app/modules/inventory/api/transfers.py`; test: `test_transfers.py` (`act(..., 'receive')` — QT-M06-02/03, `TRANSFER_COST_PENDING`)"),
    "B2-EP-19#60": (DONE, "kod: `backend/app/modules/inventory/api/transfers.py`; test: `test_transfers.py` (har holatdan bekor qilish, `ETTN_CANCEL_IN_OPERATOR`)"),
    "B2-EP-19#62": (DONE, "kod: `backend/app/modules/inventory/api/stock_counts.py`; test: `test_stock_counts.py` (QT-M05-01, `BARCODE_NOT_IN_CATALOG`)"),
    "B2-EP-19#63": (DONE, "kod: `backend/app/modules/inventory/api/stock_counts.py`; test: `test_stock_counts.py`"),
    "B2-EP-19#64": (DONE, "kod: `backend/app/modules/inventory/api/stock_counts.py`; test: `test_stock_counts.py` (QT-M05-04)"),
    "B2-EP-19#65": (DONE, "kod: `backend/app/modules/inventory/api/stock_counts.py`; test: `test_stock_counts.py` (QT-M05-02/03/06/07, `COUNT_LINES_INCOMPLETE`)"),
    "B2-EP-19#66": (DONE, "kod: `backend/app/modules/inventory/api/stock_counts.py`; test: `test_stock_counts.py` (aralash qatorli storno)"),
    "B2-EP-19#69": (DONE, "kod: `backend/app/modules/inventory/api/write_offs.py`; test: `test_write_offs.py` (QT-M04-08, 202 tasdiq yo'li)"),
    "B2-EP-19#70": (DONE, "kod: `backend/app/modules/inventory/api/write_offs.py`; test: `test_write_offs.py` (storno + QQS manfiy, `expired_return` bloklangan qoldiq tiklanadi)"),
    "B2-TBL-app.po_lines": (DONE, "DDL 0013; kod: `purchasing/infrastructure/repositories.py`; test (API orqali): `test_purchase_orders.py` (qatorlarni almashtirish, `received_lines`)"),
    "B2-TBL-app.supplier_return_lines": (DONE, "DDL 0015; kod: `purchasing/infrastructure/receipts_sql.py`; test (API orqali): `test_supplier_returns.py` (QQS ulushi, qoldiq qaytarilishi)"),
    "B2-TBL-app.transfer_lines": (DONE, "DDL 0014; kod: `inventory/infrastructure/transfers_sql.py` (`lot_allocations`, `unit_cost`); test (API orqali): `test_transfers.py`"),
    "B2-TBL-app.opening_lines": (DONE, "DDL 0014; kod: `inventory/infrastructure/docs_sql.py`; test (API orqali): `test_stock_openings.py`, `test_import_jobs.py`"),
    "B2-SCR-BO-03": (DONE, "B2 qismi: `pages/warehouse/src/pages/stock` — «Qoldiq» (KPI, kam qoldiq/muddat banneri, jadval, ko'chirishlar qisqa bloki), «Ko'chirishlar», «Inventarizatsiyalar», hisobdan chiqarish dialogi (online); test: model testlari, `e2e/warehouse-stock|transfers|counts.spec.ts`. «Barchasi» konsolidatsiya va eksport — B4; e-TTN imzolash — B5; POS-10 — B3"),
    "B2-SCR-BO-04": (DONE, "B2 qismi: `pages/warehouse/src/pages/purchases` — xaridnomalar, kirimlar (PO'dan, farq sababi, o'tkazish), qaytarish, yetkazib beruvchilar (STIR qidiruv, qarz balansi); test: model testlari, `e2e/purchases.spec.ts`. To'lov / «Men qarzdorman» — B4, e-ishonchnoma — B5, AI-03 — B6"),
    "B2-SCR-BO-08": (DONE, "B2 qismi: `pages/finance/src/pages/journal` — provodkalar jurnali (filtrlar, Dt=Kt oboroti), «Qayta hisoblash navbati» (qayta urinish); test: `journal/model/model.test.ts`, `e2e/journal.spec.ts`. Davr yopish, tuzatuvchi yozuv, eksport, hisob qoldiqlari — B4/B5"),
    "B2-SCR-BO-14": (DONE, "B2 qismi: `pages/settings` tenant — baholash usuli (FIFO/AVECO, keyingi yildan, tasdiq dialogi), recost holat qatori; test: tenant model testlari, `e2e/valuation.spec.ts`"),
    "B2-SCR-BO-21": (DONE, "B2 qismi: ③b «Boshlang'ich qoldiq» — Excel/CSV import (`opening_stock`) va qo'lda kiritish (`pages/billing/src/features/opening-stock`); test: `opening-stock/model/model.test.ts`, `e2e/opening-stock.spec.ts`"),
}

# Endpoint → bosqich: matn bo'yicha topilmaganlar yoki spec matni noaniq bo'lganlar (manba ko'rsatilgan).
EP_STAGE_OVERRIDE: dict[str, tuple[str, str]] = {
    # 14 §20 — qator raqami spec tahririda siljiydi, shuning uchun yo'l bo'yicha kalit (`14:<yo'l>`)
    "14:/oauth/device_authorization": ("5", "27 B5: `/oauth/device_authorization`"),
    "14:/auth/signup": ("1", "27 B1: `POST /auth/signup`"),
    "14:/auth/otp/request": ("1", "27 B1: Telegram OTP real (`/auth/otp/*`)"),
    "14:/auth/otp/verify": ("1", "27 B1: Telegram OTP real (`/auth/otp/*`)"),
    "14:/auth/credentials": ("1", "27 B1: taklif/tiklash kodi bilan kredensial o'rnatish (US-M13-04/06, 14 §4.2)"),
    "14:/auth/terms": ("1", "27 B1: Foydalanish shartlari aksepti"),
    "14:/auth/google/start": ("1", "27 B1: Google bilan kirish (§2.2)"),
    "14:/auth/google/callback": ("1", "27 B1: Google bilan kirish (§2.2)"),
    "14:/auth/google/token": ("K", "Android native Google Sign-In — Android POS MVP'dan keyin (28)"),
    "14:/auth/pin/verify": ("3", "Kassir PIN — Bosqich 3 (qurilmaga bog'langan login, 14 §4.3/§7)"),
    "14:/auth/license": ("6", "offline litsenziya tokeni — 27 B6"),
    "14:/bff/switch-tenant": ("0", "14 §9 — Bosqich 0 poydevori (BFF)"),
    "14:/.well-known/oauth-authorization-server": ("0", "27 B0: imzolash kaliti/JWKS, AS metadata"),
    "14:/.well-known/jwks.json": ("0", "27 B0: imzolash kaliti/JWKS"),
    "14:/billing/webhooks/{}": ("6", "billing webhook — 27 B6 (US-M17-02)"),
    "18#L": ("5", "agent lokal API `/v1/card/*` — 27 B5"),
    "17#3": ("0", "23 §8 / §1 skelet (`telemetry.py`)"),
    "14§9#1": ("0", "14 §9 — Bosqich 0 poydevori (BFF)"),
    "18#8": ("3", "27 B3: qayta chop etish auditi"),
    "18#33": ("3", "fiskal chek (`FakeFiscalAdapter`) — 27 B3; infratuzilma/admin (30 §3-E)"),
    "18#34": ("3", "fiskal retry (BO-14) — 27 B3; infratuzilma/admin"),
    "19#7": ("1", "katalog (M09) — 27 B1"),
    "19#8": ("1", "katalog (M09) — 27 B1"),
    "19#9": ("1", "katalog (M09) — 27 B1"),
    "19#10": ("1", "katalog (M09) — 27 B1"),
    "19#11": ("1", "birliklar — katalog, 27 B1"),
    "19#27": ("2", "ombor registrlari — 27 B2"),
    "19#28": ("2", "ombor registrlari — 27 B2"),
    "19#76": ("3", "tarozi shtrix-kod formati (US-M09-06, B3), kam qoldiq chegarasi — B4"),
    "19#77": ("5", "27 B5: MVP'da PLU CSV eksport"),
    "19#78": ("2", "27 B2: qayta hisoblash ishi"),
    "19#79": ("2", "27 B2: qayta hisoblash ishi"),
    "19#80": ("2", "27 B2: qayta hisoblash ishi"),
    "20#29": ("1", "US-M13-03 (30 §2b, 20 #27–29)"),
    "20#37": ("1", "US-M14-03 (30 §2b)"),
    "20#37a": ("1", "US-M14-03 (30 §2b)"),
    "20#40c": ("1", "do'kon sozlamalari BO-14 — 27 B1"),
    "20#40d": ("5", "integratsiya kalitlari (Faktura.uz, CRPT) — 27 B5"),
    "20#40e": ("5", "integratsiya kalitlari — 27 B5"),
    "20#40f": ("3", "sinxron istisnolari (BO-14) — 27 B3 offline"),
    "20#40g": ("3", "sinxron istisnolari (BO-14) — 27 B3 offline"),
    "20#45": ("4", "M15 xarajatlar — 27 B4"),
    "20#46": ("4", "M15 xarajatlar — 27 B4"),
    "20#47": ("4", "M15 xarajatlar — 27 B4"),
    "20#57": ("6", "obuna — 27 B6 (US-M17-02)"),
    "20#58": ("6", "obuna — 27 B6 (US-M17-02)"),
    "20#59": ("6", "obuna — 27 B6"),
    "20#60": ("6", "obuna — 27 B6"),
    "20#62": ("6", "obuna — 27 B6 (US-M17-02)"),
    "20#63": ("6", "billing webhook — 27 B6"),
    "20#64": ("6", "billing webhook — 27 B6"),
    "20#65": ("6", "obuna — 27 B6"),
    "20#71": ("4", "M18 bildirishnomalar — 27 B4"),
    "20#76": ("6", "AI-05 — 27 B6 (US-M10-02)"),
    "20#79": ("6", "AI limiti — 27 B6"),
    # matn bo'yicha topilgan, lekin 27 dagi bosqich mazmuni boshqacha bo'lganlar
    "20#73": ("6", "AI-03 — 27 B6 (US-M04-04 (3)-yo'l)"),
    "20#74": ("6", "AI-03 — 27 B6"),
    "20#75": ("6", "AI-03 — 27 B6"),
    "19#71": ("2", "27 B2: `stock_openings` (US-M04-04 qoldiq qismi)"),
    "19#72": ("2", "27 B2: `stock_openings`"),
    "19#73": ("2", "27 B2: `stock_openings`"),
    "19#26": ("2", "qoldiq registri — 27 B2 (US-M04-01); `low_stock` filtri — B4"),
    "19#39": ("2", "27 B2: yetkazib beruvchilar (M07)"),
    "19#40": ("2", "27 B2: yetkazib beruvchilar (M07)"),
    "19#41": ("2", "27 B2: yetkazib beruvchilar (M07)"),
    "19#42": ("2", "27 B2: yetkazib beruvchilar (M07)"),
    "19#43": ("2", "27 B2: yetkazib beruvchilar (M07)"),
    "19#44": ("2", "27 B2: yetkazib beruvchilar (STIR qidiruv)"),
    "18#17": ("2", "kontragentlar CRUD — 27 B2 (yetkazib beruvchilar); mijoz qismi — B4"),
    "18#21": ("4", "qarz to'lovi — 27 B4 (US-M08-04); karta natijasi maydoni — B3"),
    "18#37": ("5", "dinamik UzQR/Click/Payme checkout — 30 US-M01-05 (5 — dinamik, 26 #49)"),
    "18#38": ("5", "dinamik UzQR — 30 US-M01-05"),
    "18#39": ("5", "dinamik UzQR — 30 US-M01-05"),
    "19#88": ("5", "27 B5: e-TTN EDO operatori orqali (B2 da faqat qoralama, `FakeEInvoiceAdapter`)"),
    "19#89": ("5", "27 B5: e-TTN + E-IMZO"),
    "19#90": ("5", "27 B5: e-TTN"),
    "19#91": ("5", "27 B5: e-TTN"),
    "20#40a": ("1", "27 B1: do'kon sozlamalari (BO-14, BO-21)"),
    "20#40b": ("1", "27 B1: do'kon sozlamalari (`tenants.legal_form`)"),
}

# Jadval → bosqich: matn bo'yicha topilgani 27 mazmuniga zid bo'lganlar.
TBL_STAGE_OVERRIDE: dict[str, tuple[str, str]] = {
    "app.ai_ocr_jobs": ("6", "AI-03 — 27 B6"),
    "app.ai_requests": ("6", "AI — 27 B6"),
    "app.stock_openings": ("2", "27 B2: `stock_openings`"),
    "app.opening_lines": ("2", "27 B2: `stock_openings`"),
    "app.products": ("1", "27 B1: M09 tovarlar"),
    "app.einvoices": ("5", "27 B5: e-faktura (B2 dagi `factura_type` — faqat ustun)"),
    "app.tax_settlements": ("4", "27 B4: `tax_settlements`"),
    "app.product_categories": ("1", "27 B1: M09 katalog"),
    "app.counterparties": ("2", "27 B2: yetkazib beruvchilar (M07); mijozlar — B4"),
    "app.debt_doubtful_flags": ("4", "27 B4: `debt-doubtful-flags`"),
    "app.bank_statement_imports": ("4", "27 B4: bank ko'chirmasi importi"),
    "app.recost_jobs": ("2", "27 B2: qayta hisoblash ishi"),
    "app.consents": ("1", "US-M17-01 — `POST /tenant/consents` (qaror #61)"),
    "app.tenant_tax_regimes": ("1", "27 B1: do'kon sozlamalari (soliq rejimi)"),
    "platform.terms_versions": ("1", "27 B1: Foydalanish shartlari aksepti"),
    "app.tenant_addons": ("6", "27 B6: tarif limitlari, qo'shimcha kassa"),
    "platform.marking_product_groups": ("5", "27 B5: markirovka (qaror #63)"),
    "app.ai_training_samples": ("6", "AI — 27 B6 (22 ichki quvur)"),
    "app.ai_feedback": ("6", "AI — 27 B6 (22 ichki quvur)"),
    "app.tenant_glossary": ("6", "AI — 27 B6 (22 ichki quvur)"),
}

# QT → bosqich: US qoidasi noto'g'ri bosqich beradiganlar.
QT_STAGE_OVERRIDE: dict[str, tuple[str, str]] = {
    "QT-M04-04": ("2", "boshlang'ich qoldiq (`stock-openings`) — 27 B2"),
}

# QT → bosqich: 31 dagi US ustuni yoki 27 dagi aniq havola bo'lmaganlar (kross-kesma bloklar).
QT_STAGE_RULES: list[tuple[str, str, str]] = [
    (r"QT-RLS-", "0", "27 B0 Tayyor ta'rifi; endpoint darajasi — 31 §1.1 jadvali"),
    (r"QT-OAUTH-", "0", "27 B0 Tayyor ta'rifi"),
    (r"QT-AI-PII-01$", "0", "27 B0 Tayyor ta'rifi"),
    (r"QT-IDEMP-", "3", "31 §1.2 — `cash-movements`/`sync/push` ustida (B3)"),
    (r"QT-SEQ-", "3", "31 §1.3 — smena/chek (B3)"),
    (r"QT-OFFLINE48-", "3", "27 B3 Tayyor (QT-OFFLINE48); -05 — B5"),
    (r"QT-SUB-", "6", "31 §1.5 — obuna lokauti (27 B6)"),
    (r"QT-PERM-0[89]$", "2", "31 §1.7 — filial doirasi `stock-balances` (B2)"),
    (r"QT-PERM-", "3", "31 §1.7 — chegirma/qaytarish/pul olish limitlari (B3)"),
    (r"QT-AI-", "6", "27 B6 — AI-01/03/05/06"),
    (r"QT-NFR-0[12]$", "3", "POS tezligi (B3)"),
    (r"QT-NFR-0[34]$", "3", "API p95 — sotuv posting (B3)"),
    (r"QT-NFR-(05|13)$", "6", "AI chat (B6)"),
    (r"QT-NFR-06$", "3", "48 soat (B3)"),
    (r"QT-NFR-07$", "5", "markirovka qabul muddati (B5)"),
    (r"QT-NFR-08$", "6", "davlat hisoboti 5 ish kuni (B6)"),
    (r"QT-NFR-(09|10|11|12)$", "3", "sync sig'imi (B3)"),
    (r"QT-NFR-1[45]$", "7", "31 §4 — Bosqich 7"),
    (r"QT-M19-", "7", "31 M19 — Bosqich 7"),
]

# Istalgan band → boshqa bosqich (spec mexanik biriktirishi noto'g'ri yoki band qismi keyingi bosqichga tegishli).
# Kalit — generatsiya qilingan ID (yoki 14 §20 uchun `B<n>-EP-14:<yo'l>`); qiymat — (yangi bosqich, sabab).
STAGE_MOVE: dict[str, tuple[str, str]] = {
    "B0-TBL-app.license_tokens": ("6", "yozish/o'qish yo'li — `GET /auth/license` offline litsenziya tokeni (27 B6, 14 §17); B0 da faqat DDL"),
    "B0-TBL-app.tenant_secrets": ("5", "yozish yo'li — integratsiya kalitlari `20` #40d/#40e (Faktura.uz, CRPT, UzQR — 27 B5); B0 da DDL va envelope shifrlash (`core/secrets.py`), B1 da BO-14 faqat holatini o'qiydi"),
    "B2-TBL-app.supplier_payments": ("4", "yetkazib beruvchiga to'lov (US-M07-04, 19 §11) — 27 B4; B2 vazifa matnida faqat «kassadan naqd to'lov — Bosqich 4» deb tilga olingan"),
    "B2-SCR-POS-08": ("3", "veb-kassa (POS) ekrani — 27 B3 (M01 kassa va POS qobig'i); B2 da faqat backend kontrakti: `/goods-receipts` (19 §8, online)"),
    "B2-SCR-POS-09": ("3", "veb-kassa (POS) ekrani — 27 B3; B2 da backend `/transfers` va offline voqea nomlari (`transfer.sent`/`transfer.received`, sync — B3)"),
    "B2-SCR-POS-10": ("3", "veb-kassa (POS) skaneri — 27 B3 (`stock_count.line_recorded` sync bilan); B2 da `/stock-counts` va BO-03 back-office sanash"),
    "B1-SCR-POS-01": ("3", "27 B3: M01 kassa, smena ochish va POS-01 (iOS ko'rsatmasi bilan) — Bosqich 3 da quriladi; B1 ulushi (US-M13-06 tiklash) `/recover` sahifasida, BO-01 qatorida"),
}

BLOCKED_TASKS = {
    "B5-T05": "26 #172–#174 — vendor shartnomasi",
    "B6-T11": "26 #45 — Eskiz shartnomasi (#130 dan keyin)",
    "B6-T12": "26 #127 — yurist (imzolangan oferta)",
}

GAPS = [
    ("G-01", "Asoschining tashqi vazifalari", "yuridik shaxs va xat imzolovchi (26 #130); Xat 1–10 ni yuborish va `letter_tracker` (26 #71); buxgalter bilan `13` ni tekshirish; reyestr arizasi (26 #25/#42) va fiskal hamkor muzokarasi (26 #109/#168/#169), Eskiz (26 #45); karta terminali hamkorlari (26 #172–#176); pentest taklifi; qo'llab-quvvatlash kanali; 15–20 do'kon suhbati va 5–10 pilot; yurist (oferta, rozilik, runbook — 26 #127/#126)", "B0-T11…T15, T17…T19, B0-DoD-06/07", "⛔ asoschi"),
    ("G-02", "Noto Sans subset zaxirasi (ʻ ʼ, Ққ Ғғ Ҳҳ)", "✅ `@fontsource-variable/noto-sans` (ʻ ʼ — `latin`, Ққ Ғғ Ҳҳ — `cyrillic-ext`), `apps/shell/src/noto-sans-fallback.css` (`unicode-range` faqat 8 belgi), stek `preset.ts`, PWA precache; `KNOWN_MANROPE_GAPS` olib tashlandi — `e2e/font-glyphs.spec.ts`; `08` §2, 26 #141", "B0-T07", "✅ yopildi"),
    ("G-03", "`get-nonce` pnpm katalogida", "✅ `pnpm-workspace.yaml` katalogi, `apps/shell/package.json` → `catalog:`", "B0-T08", "✅ yopildi"),
    ("G-04", "`/oauth/revoke` — jonli access tokenlar", "✅ access tokenda `fam` claim; Redis belgilari `auth:jti_revoked`/`auth:fam_revoked`/`auth:sid_revoked` (bitta MGET, TTL = access muddati); refresh revoke, reuse aniqlash, qurilma revoke — oila bilan; `test_auth_revocation_and_switch.py`; `14` §5", "B0-T02, B0-EP-14#6", "✅ yopildi"),
    ("G-05", "CSP `sha256-…` zaxirasi", "✅ `ERP_CSP_MODE=hash` build: Radix scroll-lock `<style>` sha256 ro'yxati (`apps/shell/csp-hashes.ts`), `dist/_headers`, build guard (ruxsatsiz inline skript/stil — build xatosi); `csp-hashes.test.ts`, `e2e/csp-nonce.spec.ts`; `24` §4.4", "B0-T08", "✅ yopildi"),
    ("G-06", "AS login sahifasi ko'rinishi", "✅ BO-01 maketi va 07 bilan tekshirildi va tuzatildi (aria-invalid/aria-describedby, 'Parolni unutdim?', telefon maxlength/placeholder, logo, ro'yxatdan o'tish havolasi, tenant select `required`); skriptsiz, hash CSP; `tests/unit/test_login_page.py`", "B0-T02, B0-EP-14#3, B0-SCR-BO-01", "✅ yopildi"),
    ("G-07", "`POST /bff/switch-tenant` (14 §9)", "✅ route + `14` §9 shartnoma va §20 qatori; eski `sid`/oila bekor, cookie yangi sessiyaga; veb `@shared/state` `switchTenantFx`, `/bff` proksi; testlar `test_bff_switch_tenant_*`", "B0-EP-14#29", "✅ yopildi"),
    ("G-08", "Telemetriya: `/metrics`, OpenTelemetry, Sentry", "✅ `app/core/telemetry.py`: Prometheus (`/metrics`, bearer token, route-shablon label), OTel (FastAPI/SQLAlchemy/httpx + SAQ job span'lari, OTLP), Sentry (PII'siz, token scrub) — hammasi sozlama bilan; worker metrikalari; `test_telemetry.py`, `test_metrics.py`. Keyingi modullar metrikalari (posting, outbox, AI, fiskal, 1C) — o'z bosqichlarida", "B0-EP-17#3, B0-T01", "✅ yopildi"),
    ("G-09", "Sirlar va zaxira infratuzilmasi", "repo qismi ✅: `.sops.yaml` (age), WAL-G `backend/ops/backup/*.sh` (bazaviy zaxira, WAL qabul, offsite rclone, PITR, staging restore, lag metrikasi, cron/systemd), `RUNBOOK-backup-restore.md`, `test_ops_backup.py`, CI shellcheck. ⛔ asoschi: UzCloud avto-to'lov + billing ogohlantirishi, DBaaS replikatsiya roli/`pg_switch_wal`, S3 bucket'lar (UzCloud + ikkinchi provayder, object lock), age va `WALG_LIBSODIUM_KEY` kalitlari, **staging restore bir marta** (qaror #65)", "B0-T09, B0-DoD-11", "⛔ tashqi (repo qismi ✅)"),
    ("G-10", "Hisoblar rejasi konstantasiga test", "✅ `tests/unit/test_chart_of_accounts.py` — 13 §1 jadvalini parse qilib kod/nom/tur, takrorsizlik, 4 xonali kod, 13 §2+ dagi har hisob mavjudligi (30 kod), 6710 ishlatilmasligi; konstanta 13 ga to'liq mos", "B0-T04", "✅ yopildi"),
    ("G-11", "Pentest tayyorgarligi — DAST", "kod ✅: `.github/workflows/dast.yml` (ZAP baseline + passiv API skan, High/FAIL → job xatosi), `backend/ops/zap/rules.tsv`. ⛔ asoschi: ichki OAuth/to'lov/fiskal tekshiruv ro'yxati, Celion/ONESEC taklifi", "B0-T16", "⛔ tashqi (CI qismi ✅)"),
    ("G-12", "`POST /auth/sessions/revoke-all` — backend testi", "✅ `test_auth_revocation_and_switch.py::test_auth_revoke_all_ends_every_session_in_every_tenant` (2 tenant, brauzer + Android; CSRF/Bearer rad; cookie tozalanadi; access tokenlar 401)", "B0-EP-14#19", "✅ yopildi"),
    ("G-13", "Endpoint katalogida B0 ga tegishli qolganlar", "`/oauth/device_authorization` — B5, `/auth/pin/verify` — B3, `/auth/license` va `app.license_tokens` — B6, `/auth/google/token` — MVP'dan keyin (Android), `app.tenant_secrets` yozish yo'li — B5", "—", "ma'lumot"),
]

# Bosqich 1 tekshiruvi (2026-10-17, Opus: xavfsizlik / spec / veb → qabul agenti): keyingi bosqichga o'tkazilgan topilmalar.
DEFERRED = [
    ("SEC-08", "Redis ishlamayotganda `sid`siz (Android/Bearer) token uchun bekor qilish DB zaxirasiz (fail-open ≤ 15 daq)", "3", "B1 da faqat BFF tokenlari (hammasida `sid`); qurilma/Android login bilan — oila bo'yicha DB zaxirasi"),
    ("SEC-09", "Bitta sessiyani bekor qilish Android access tokenini (`fam`, `sid`siz) darhol o'chirmaydi", "3", "B3 qurilma login — `mark_revoked(sids, families)`"),
    ("SEC-12", "MXIK qidiruvi: foydalanuvchi bo'yicha limit, javob hajmi chegarasi (SSRF yo'q; 3 urinish — 19 §161 talabi)", "6", "umumiy mustahkamlash — pilot oldidan"),
    ("CORR-06", "QT-M09-09: aksiya narxini sotuv posting'ida server qayta tekshirishi", "3", "sotuv posting'i B3 da (19 §4 ga yozildi); narx aniqlash qismi B1 da testlangan"),
    ("WEB-12", "Topbar qo'ng'iroq/qidiruv va tasdiqlar soni belgisi", "3/4", "tasdiqlar (BO-16) — B3, bildirishnomalar (M18) — B4"),
    ("WEB-15", "BO-05 «Tannarx» va «Ustama %» ustunlari", "2", "tannarx (`stock_lots`/`avg_costs`) B2 da"),
    ("—", "Qurilmani bekor qilish (`branches/infrastructure/devices.py`) so'nggi foydalanuvchilarning PIN'ini global tiklaydi (SEC-01 ga o'xshash ko'p-tenant masalasi)", "3", "PIN login va qurilma bog'lash — B3; tenant-lokal PIN talqini bilan birga"),
    ("—", "Taklifni qayta yuborish amali yo'q (ikki tenant bir telefonni taklif qilsa, oxirgi kod amal qiladi)", "1+", "UX takomillashtirish — asoschi ustuvorligi bo'yicha"),
]

# Bosqich 2 tekshiruvi (2026-10-18, Opus: buxgalteriya / xavfsizlik / veb → qabul agentlari): keyingi bosqichga.
DEFERRED_B2 = [
    ("ACC-07", "Kirim qatori summasi 4 kasrli birlik narxdan qayta hisoblanadi — katta miqdorda EHF qator summasi/QQS tiyingacha mos kelmasligi mumkin", "5", "`from-einvoice` bilan qator `net_amount`/`vat_amount` asosiy qilib qabul qilinadi"),
    ("ACC-09", "`moved_at = posted_at`, `entry_date = doc_date`: o'tgan sanali kirim davr oxiridagi qoldiq hisobotida ko'rinmaydi", "5", "davr yopish tayyorligi: GL `inv_acct` ↔ Σ `stock_balances.value` tekshiruvi va `doc_date` bo'yicha qoldiq hisoboti"),
    ("WEB-10", "Qoldiq qatorlari uchun mahsulot kartalari alohida so'raladi (veb qismida cheklov va navbat qo'yildi)", "4", "`/stock-balances` ga birlik/kategoriya/shtrix-kod/markirovka maydonlari — `GET /reports/stock` bilan"),
    ("—", "BO-03 «Barchasi» (konsolidatsiya), eksport", "4", "`/reports/stock`, eksport ishlari — M12"),
    ("—", "e-TTN imzolash, qo'lda ro'yxatga olish, qabul tomonda tasdiqlash", "5", "E-IMZO va real operator (19 §20)"),
]

FOUNDER = [
    ("26 #179", "Rol limitlarining standart qiymatlari (Menejer — `discount.give` %, `cash.withdraw`, `stock.writeoff`; Kassir — `debts.create`; Omborchi — `stock.writeoff`)", "⛔ kutilmoqda", "seed va provisioning'da `limit_value = NULL` (limitsiz); Egasi BO-11 da o'zi qo'yadi; qaror kelganda faqat `app/modules/access/domain/permissions.py` o'zgaradi (migratsiyasiz)"),
    ("Agent porti", "Do'kon agenti lokal API porti — ruxsat ro'yxati, standart `47110`", "✅ qabul qilingan", "CSP `connect-src` deploy konfiguratsiyasidagi port ro'yxatidan generatsiya qilinadi (24 §CSP, 21 §16). Hozir kodda bitta port: `web/apps/shell/csp.ts` (`agentPort = 47110`, test `csp.test.ts`), `shared/lib/src/runtime-config`; ro'yxatga kengaytirish — agent bilan (B5)"),
    ("braces audit", "`pnpm audit` dagi `braces` topilmasini e'tiborsiz qoldirish", "✅ qabul qilingan", "`web/pnpm-workspace.yaml` (audit ignore, sababi izohda: build-vaqt zanjiri, foydalanuvchi kiritmasi yo'q); tailwindcss/micromatch `braces`dan voz kechganda olib tashlanadi"),
    ("Noto subset", "Manrope'da yo'q gliflar uchun self-hosted Noto Sans subset zaxirasi", "✅ qabul qilingan", "bajarildi — G-02 (`08` §2, 26 #141)"),
    ("B2 QQS krediti", "E-fakturasiz qo'lda kiritilgan kirimda QQS krediti post paytida ochiladi (SK 266 — kredit ro'yxatdan o'tgan EHF bilan)", "⛔ kutilmoqda", "hozir: einvoice_id yo'q kirim yashil kabi; ehtiyotkor variant — `unknown` kabi kechiktirish (`purchasing/domain/receipts.py`, B5 `from-einvoice` bilan qayta ko'rish)"),
    ("B2 qizil faktura", "Qizil/`unknown` fakturada 6010 to'liq (QQS bilan), 4410 `vat_credit='deferred'`, faqat `vat_moves` to'lovgacha kechiktiriladi", "✅ qabul qilingan (13 §2.8 tuzatildi)", "`purchasing/domain/receipts.py`; B4 to'lov / B5 `green` faqat `vat_moves` yozadi"),
    ("B2 naqd kirim", "`paid_immediately=true` faqat bank (`Kt 5110`); kassadan naqd — B4 `supplier_payments`", "✅ qabul qilingan (27, 13 §2.8)", "kassa smenasi (B3) kerak"),
    ("B2 orqa sana", "Back-office hujjatlarida `moved_at = posted_at` — o'tgan sanali kirim recost qo'zg'atmaydi, usul o'tkazilgan kundagi bo'yicha", "⛔ tasdiqlash kerak", "13 §3.1/§3.3; davr yopish tekshiruvi — B5 (ACC-09)"),
    ("B2 12 oy qaytarish", "Asl kirimdan 12 oy o'tgan qaytarish rad etiladi (`reverse_sale_required`) — teskari realizatsiya alohida oqim", "⛔ tasdiqlash kerak", "`purchasing/application/supplier_returns.py`"),
    ("B2 ko'chirish muddati", "`settings.transfer_overdue_hours` standart 48 soat (QT-M06-05 «tenant sozlamasi» kaliti spec'da yo'q edi)", "⛔ tasdiqlash kerak", "`branches/domain/tenant_settings.py`; 11/20 ga qo'shildi"),
    ("B2 go_live_date", "`tenants.go_live_date` = ro'yxatdan o'tgan kun (boshlang'ich qoldiq `go_live_date − 1`)", "⛔ tasdiqlash kerak", "`auth/infrastructure/signup_repository.py`; ilgari hech qayerda yozilmas edi"),
    ("Karta `unknown`", "Noma'lum karta natijasini menejer rekvizitsiz yopadi", "✅ qabul qilingan", "menejer faqat tasdiqlaydi, hech narsa yozmaydi (`resolved_by='manager'`), rekvizitlar NULL (qaror #71, 21 §9.2) — B3 vazifasi"),
]


# ---------------------------------------------------------------- 26 Jadval B
def parse_table_b() -> list[list[str]]:
    t = read("26-ochiq-savollar-reestri.md").split("## Jadval B", 1)[1].split("\n## ", 1)[0]
    rows = []
    for ln in t.splitlines():
        if re.match(r"^\| \d+ \|", ln):
            rows.append(split_row(ln))
    return rows


# ---------------------------------------------------------------- assembly
@dataclass
class Item:
    id: str
    kind: str  # T DoD US EP SCR TBL QT
    stage: str
    text: str
    source: str
    status: str = TODO
    evidence: str = ""
    alias: str = ""  # MANUAL uchun barqaror kalit (14 §20 — yo'l bo'yicha)


def stage_label(s: str) -> str:
    return STAGE_NAME.get(s, f"Bosqich {s}")


def load_previous() -> dict[str, tuple[str, str]]:
    prev: dict[str, tuple[str, str]] = {}
    if not OUT.exists():
        return prev
    for ln in OUT.read_text(encoding="utf-8").splitlines():
        if ln.startswith("| B") or ln.startswith("| BK"):
            c = split_row(ln)
            if len(c) >= 5 and re.match(r"^B[0-7K]-", c[0]) and c[1] in STATUSES:
                prev[c[0]] = (c[1], c[4])
    return prev


def build(use_pytest: bool) -> str:
    stages = parse_backlog()
    matrix = parse_matrix()
    qts = parse_qt()
    eps = parse_endpoints()
    tables = parse_tables()
    screens = parse_screens()
    code = scan_code(use_pytest)
    prev = load_previous()

    # hikoyalar → bosqich(lar)
    stage_us: dict[str, list[str]] = {s: expand_us(stages[s].stories_text) for s in STAGES if s in stages}
    first_stage_of_us: dict[str, str] = {}
    for s in STAGES:
        for u in stage_us.get(s, []):
            first_stage_of_us.setdefault(u, s)

    task_corpus = {s: " ".join(stages[s].tasks) + " " + stages[s].dod for s in STAGES if s in stages}
    us_corpus = {s: " ".join((matrix[u].api + " " + matrix[u].screens + " " + matrix[u].tables) for u in stage_us.get(s, []) if u in matrix) for s in STAGES}

    items: list[Item] = []

    # vazifalar va "Tayyor ta'rifi"
    for s in STAGES:
        st = stages.get(s)
        if not st:
            continue
        pre = "BK" if s == "K" else f"B{s}"
        for i, t in enumerate(st.tasks, 1 if s != "K" else 0):
            items.append(Item(f"{pre}-T{i:02d}", "T", s, clean(t, 260, code=True), "27"))
        if st.dod:
            parts, buf, depth = [], "", 0
            for ch in st.dod:
                depth += (ch == "(") - (ch == ")")
                if ch == ";" and depth == 0:
                    parts.append(buf.strip())
                    buf = ""
                else:
                    buf += ch
            parts = [p for p in parts + [buf.strip()] if p]
            for i, p in enumerate(parts, 1):
                items.append(Item(f"{pre}-DoD-{i:02d}", "DoD", s, clean(p, 260, code=True), "27 Tayyor ta'rifi"))
        for u in stage_us.get(s, []):
            name = matrix[u].name if u in matrix else "?"
            items.append(Item(f"{pre}-{u.replace('US-', 'US-')}", "US", s, clean(f"{u} — {name}", 160), f"27 Hikoyalar; 30 ({matrix[u].mvp if u in matrix else '?'})"))

    # endpointlar → bosqich
    def corpus_paths(txt: str) -> list[str]:
        return paths_in(txt)

    tpaths = {s: corpus_paths(task_corpus.get(s, "")) for s in STAGES}
    upaths = {s: corpus_paths(us_corpus.get(s, "")) for s in STAGES}
    idx_order: dict[str, list[str]] = {}
    for e in eps:
        f, _, num = e.id.partition("#")
        idx_order.setdefault(f, []).append(num)

    def refs_in(txt: str) -> set[str]:
        out: set[str] = set()
        for m in re.finditer(r"\b(18|20)(?:-api-[a-z-]+\.md`?)?\s*(?:§[\w.]+,?\s*)?#(\d+[a-z]?)(?:\s*[–…-]\s*#?(\d+[a-z]?))?", txt):
            f, a, b = m.group(1), m.group(2), m.group(3)
            order = idx_order.get(f, [])
            if b and a in order and b in order:
                for x in order[order.index(a) : order.index(b) + 1]:
                    out.add(f"{f}#{x}")
            else:
                out.add(f"{f}#{a}")
        for m in re.finditer(r"\b([WA])-(\d\d)(?:\s*…\s*[WA]-(\d\d))?", txt):
            a, b = int(m.group(2)), int(m.group(3) or m.group(2))
            for x in range(a, b + 1):
                out.add(f"33{m.group(1)}-{x:02d}")
        return out

    trefs = {s: refs_in(task_corpus.get(s, "")) for s in STAGES}
    urefs = {s: refs_in(us_corpus.get(s, "")) for s in STAGES}

    def match_level(e: Ep, s: str) -> int:
        tp, up = tpaths[s], upaths[s]
        tc = task_corpus.get(s, "")
        uc = us_corpus.get(s, "")
        if any(p in tp for p in e.paths) or any(f"`{ev}`" in tc for ev in e.events):
            return 1
        if any(g.endswith("*") and any(p.startswith(g.rstrip("*")) for p in e.paths) for g in tp):
            return 2
        if any(p in up for p in e.paths) or any(f"`{ev}`" in uc for ev in e.events):
            return 3
        if e.id in trefs[s]:
            return 4
        if e.id in urefs[s]:
            return 5
        res = {ep_resource(p) for p in e.paths if not p.startswith("/onec")}
        if res & ({ep_resource(x) for x in tp} | bare_res(tc)):
            return 6
        if res & ({ep_resource(x) for x in up} | bare_res(uc)):
            return 7
        return 99

    unassigned: list[str] = []
    for e in eps:
        why = ""
        ov = EP_STAGE_OVERRIDE.get(e.id) or EP_STAGE_OVERRIDE.get(e.alias)
        if ov:
            s, why = ov
        else:
            best = min(((match_level(e, s), STAGES.index(s), s) for s in STAGES), default=(99, 0, ""))
            if best[0] == 99:
                # 33: 27 B5 vazifasida sanalmagan W/A — Bosqich 7
                if e.id.startswith("33"):
                    s, why = "7", "27 B7: W-06, W-09…W-55, A-02"
                else:
                    unassigned.append(e.id)
                    continue
            else:
                s = best[2]
                why = {1: "27 vazifa matni", 2: "27 vazifa matni (`/*`)", 3: "30 (US API)", 4: "27 (katalog raqami)", 5: "30 (katalog raqami)", 6: "27 (resurs)", 7: "30 (resurs)"}[best[0]]
        pre = "BK" if s == "K" else f"B{s}"
        items.append(Item(f"{pre}-EP-{e.id}", "EP", s, e.label, f"{e.src}; {why}"))
        items[-1].evidence = ""
        items[-1]._ep = e  # type: ignore[attr-defined]
        if e.alias:
            items[-1].alias = f"{pre}-EP-{e.alias}"

    # ekranlar — har bosqichda (vazifa matni + hikoyalar)
    for s in STAGES:
        found: list[str] = []
        for m in SCREEN_RE.findall(task_corpus.get(s, "")):
            if m not in found:
                found.append(m)
        for u in stage_us.get(s, []):
            if u in matrix:
                for m in SCREEN_RE.findall(matrix[u].screens):
                    if m not in found:
                        found.append(m)
        if s == "1" and "/install" in task_corpus.get(s, "") and "UX-INSTALL" not in found:
            found.append("UX-INSTALL")
        pre = "BK" if s == "K" else f"B{s}"
        for scr in sorted(found, key=lambda x: (x.split("-")[0], x)):
            items.append(Item(f"{pre}-SCR-{scr}", "SCR", s, f"{scr} — {screens.get(scr, '?')}", "07; 27/30"))
    # BO-01 — B0 (login sahifasi, 27 B0 Tayyor ta'rifi)
    items.append(Item("B0-SCR-BO-01", "SCR", "0", f"BO-01 — {screens.get('BO-01', '')}", "27 B0 Tayyor ta'rifi (login sahifasi)"))

    # jadvallar → bosqich (birinchi tilga olingan bosqich; 0028 → B5, 0029 → B7)
    names = [t.fq for t in tables]
    bare_count: dict[str, int] = {}
    for fq in names:
        bare_count[fq.split(".")[1]] = bare_count.get(fq.split(".")[1], 0) + 1

    def mentions(fq: str, txt: str) -> bool:
        sch, nm = fq.split(".")
        if re.search(rf"\b{re.escape(fq)}\b", txt):
            return True
        if bare_count[nm] == 1 and re.search(rf"`{re.escape(nm)}(?:[`.(]| \()", txt):
            return True
        return False

    for t in tables:
        if t.fq in TBL_STAGE_OVERRIDE:
            s, why = TBL_STAGE_OVERRIDE[t.fq]
        elif t.rev == "0028":
            s, why = "5", "12 §6.1 — 0028 store_agent (27 B5)"
        elif t.rev == "0029":
            s, why = "7", "12 §6.1 — 0029 onec_integration (27 B7)"
        else:
            cand = [(STAGES.index(s), 1, s) for s in STAGES if mentions(t.fq, task_corpus.get(s, ""))]
            cand += [(STAGES.index(s), 2, s) for s in STAGES if mentions(t.fq, us_corpus.get(s, ""))]
            if cand:
                best = min(cand)
                s, why = best[2], ("27 vazifa matni" if best[1] == 1 else "30 (US jadvallari)")
            else:
                s, why = "0", "infratuzilma — 12 §6.1 revizioni Bosqich 0 da"
        pre = "BK" if s == "K" else f"B{s}"
        it = Item(f"{pre}-TBL-{t.fq}", "TBL", s, f"`{t.fq}` (revizion {t.rev or '—'})", f"12; {why}")
        it._tbl = t  # type: ignore[attr-defined]
        items.append(it)

    # QT → bosqich
    explicit: dict[str, str] = {}
    for s in STAGES:
        for q in expand_qt(task_corpus.get(s, "")):
            explicit.setdefault(q, s)
    for q in qts.values():
        why = ""
        if q.id in QT_STAGE_OVERRIDE:
            s, why = QT_STAGE_OVERRIDE[q.id]
        elif q.id in explicit:
            s, why = explicit[q.id], "27 (aniq havola)"
        elif q.us:
            ss = [first_stage_of_us[u] for u in q.us if u in first_stage_of_us]
            if ss:
                s = min(ss, key=STAGES.index)
                why = f"31 US ({', '.join(q.us)})"
            else:
                s, why = "K", "US MVP'dan keyin"
        else:
            s = ""
            for pat, st_, w in QT_STAGE_RULES:
                if re.match(pat, q.id):
                    s, why = st_, w
                    break
            if not s:
                unassigned.append(q.id)
                continue
        pre = "BK" if s == "K" else f"B{s}"
        it = Item(f"{pre}-{q.id}", "QT", s, clean(f"{q.id} ({q.kind}) — {q.text}", 170), f"31; {why}")
        items.append(it)

    # ---- boshqa bosqichga ko'chirilganlar (sabab "Manba" ustunida)
    for it in items:
        mv = STAGE_MOVE.get(it.id) or (STAGE_MOVE.get(it.alias) if it.alias else None)
        if mv:
            new_s, why = mv
            pre = "BK" if new_s == "K" else f"B{new_s}"
            old_id = it.id
            it.id = pre + it.id[it.id.index("-"):]
            if it.alias:
                it.alias = pre + it.alias[it.alias.index("-"):]
            it.stage = new_s
            it.source = f"{it.source}; ko'chirildi {old_id.split('-')[0]} → {pre}: {why}"
            it._moved = True  # type: ignore[attr-defined]
    # ko'chirilgan band shu bosqichda allaqachon bo'lsa — bittasi qoladi (sabab qo'shiladi)
    seen: dict[str, Item] = {}
    merged: list[Item] = []
    for it in items:
        if it.id in seen:
            keep = seen[it.id]
            moved = it if getattr(it, "_moved", False) else keep
            other = keep if moved is it else it
            other.source = moved.source
            if moved is keep:
                merged[merged.index(keep)] = other
                seen[it.id] = other
            continue
        seen[it.id] = it
        merged.append(it)
    items[:] = merged

    # ---- holatlar
    for it in items:
        st, ev = TODO, ""
        if it.kind == "QT":
            e = qt_evidence(it.id.split("-", 1)[1], code)
            if e:
                st, ev = DONE, "test: " + e
        elif it.kind == "EP":
            st2, ev2 = route_evidence(it._ep, code)  # type: ignore[attr-defined]
            if st2:
                st, ev = st2, ev2
        elif it.kind == "TBL":
            st, ev = table_evidence(it._tbl, code)  # type: ignore[attr-defined]
        mkey = it.id if it.id in MANUAL else (it.alias if it.alias in MANUAL else "")
        if mkey:
            st, ev = MANUAL[mkey]
        elif it.id in BLOCKED_TASKS and st == TODO:
            st, ev = BLOCKED, BLOCKED_TASKS[it.id]
        if it.stage == "K" and st == TODO:
            st = LATER
        if st in (TODO, LATER) and it.id in prev and prev[it.id][0] not in (TODO,) and not mkey:
            st, ev = prev[it.id]
        it.status, it.evidence = st, ev

    return render(stages, items, unassigned, eps, tables, qts, matrix, screens, code)


# ---------------------------------------------------------------- rendering
KIND_TITLE = [
    ("T", "Vazifalar (27)"),
    ("DoD", "Tayyor ta'rifi (27)"),
    ("US", "Hikoyalar (27 → 30)"),
    ("EP", "Endpointlar (14/17/18/19/20/33)"),
    ("SCR", "Ekranlar (06/07)"),
    ("TBL", "Jadvallar / migratsiyalar (12)"),
    ("QT", "Qabul testlari (31)"),
]


def render(stages, items, unassigned, eps, tables, qts, matrix, screens, code) -> str:
    L: list[str] = []
    w = L.append
    w("# Implementatsiya holati — yagona kuzatuv hujjati")
    w("")
    w("**Maqsad:** spec'dagi (`spec/kod-uchun/`) har bir bosqich bandini — vazifa, hikoya, endpoint, ekran, jadval, qabul testi — kod va test bilan solishtirib, ish siklini (keyingi nima, nima qolgan) shu yerdan boshqarish. · "
      "**Kim uchun:** asoschi, Claude va kod yozayotgan agentlar. · "
      "**Bog'liq fayllar:** `27-backlog.md`, `30-izchillik-matritsasi.md`, `31-qabul-testlari.md`, `12`, `14`, `17`–`20`, `33`, `06`/`07`, `26`. · "
      "**Holat:** joriy, generatsiya qilingan — qo'lda tahrir faqat \"Holat\"/\"Dalil\" ustunlarida.")
    w("")
    w("## Qanday yangilanadi")
    w("")
    w("| Belgi | Ma'nosi |")
    w("|---|---|")
    w(f"| {DONE} bajarildi | kod **va** test bor (dalil ustunida fayl/test nomi) |")
    w(f"| {PART} qisman | kod bor, lekin test yo'q yoki band to'liq emas (nima qolgani dalilda) |")
    w(f"| {TODO} qilinmagan | kod yo'q |")
    w(f"| {BLOCKED} tashqi javob kutmoqda | band tashqi javob/qarorsiz bajarilmaydi (26 Jadval B, asoschi) |")
    w(f"| {LATER} MVP'dan keyin | `27` \"MVP'dan keyin\" bo'limi |")
    w("")
    w(f"**Qoida: band faqat kod va test ikkalasi mavjud bo'lsagina {DONE} bo'ladi.** Test bor-yo'qligi — repo'dagi test fayllari (pytest/vitest/Playwright); \"yashil\" ekanini CI tasdiqlaydi.")
    w("")
    w("- **ID sxemasi:** `B<bosqich>-<tur>-<manba>` — `B1-T03` (27 dagi 3-vazifa), `B1-DoD-02` (Tayyor ta'rifining 2-bandi), `B1-US-M13-04`, `B1-EP-20#28` (20 indeksi #28), `B1-EP-19#31` (19 dagi 31-endpoint sarlavhasi, tartib bo'yicha), `B0-EP-14#6` (14 §20 dagi 6-qator), `B1-EP-14§18.2#2`, `B0-EP-17#1`, `B5-EP-33W-01`, `B3-SCR-POS-02`, `B3-TBL-app.sales`, `B0-QT-RLS-01`; `BK-…` — MVP'dan keyin.")
    w("- **Bosqichga biriktirish** mexanik: vazifa/hikoya — `27`; endpoint — `27` vazifa matnidagi yo'l → `30` dagi US API ustuni → katalog raqami → resurs nomi (eng aniq moslik, keyin eng erta bosqich; \"Manba\" ustunida ko'rsatilgan); ekran — bosqich vazifasi va hikoyalarining ekranlari (bir ekran bir necha bosqichda bo'lishi mumkin — har bosqich o'z qismini quradi); jadval — birinchi tilga olingan bosqich (0028 → B5, 0029 → B7, tilga olinmagani → B0 infratuzilma); QT — `27` dagi aniq havola → `31` US ustuni → kross-kesma qoidalar (`_scripts/gen_holat.py` `QT_STAGE_RULES`).")
    w("- **Jadval qatori:** ✅ = DDL migratsiyada + ilova kodida ishlatiladi + testda bor; 🟡 = DDL bor, modul kodi/testi hali yo'q.")
    w("- **Qayta generatsiya:** `python spec/implementatsiya/_scripts/gen_holat.py` (repo ildizidan; `--check` — CI uchun, `--pytest` — dalilga `pytest --collect-only` qo'shadi). Skript route'larni, test nomlarini (`test_qt_…`) va jadval ishlatilishini o'zi topadi; qo'lda qo'yilgan holat/dalil (shu fayldagi) avtomatik ✅ topilmaguncha saqlanadi. Bosqich 0 va 1 ning qo'lda tekshirilgan holatlari — skriptdagi `MANUAL`; boshqa bosqichga ko'chirilganlar — `STAGE_MOVE` (sabab \"Manba\" ustunida).")
    w("- **Ish sikli:** bosqich boshida shu bosqich bo'limidagi ⬜ qatorlar — ish ro'yxati; band tugaganda kod+test bilan ✅ va dalil; bosqich \"Tayyor ta'rifi\" (`DoD`) qatorlarining hammasi ✅ bo'lganda keyingi bosqichga o'tiladi (27).")
    w("")

    # yig'ma
    w("## Yig'ma (bosqich × holat)")
    w("")
    w("| Bosqich | " + " | ".join(STATUSES) + " | Jami | Vazifa | DoD | US | EP | Ekran | Jadval | QT |")
    w("|---|" + "---|" * (len(STATUSES) + 8))
    tot = {s: 0 for s in STATUSES}
    for s in STAGES:
        its = [i for i in items if i.stage == s]
        if not its:
            continue
        cnt = {x: sum(1 for i in its if i.status == x) for x in STATUSES}
        for x in STATUSES:
            tot[x] += cnt[x]
        kinds = [sum(1 for i in its if i.kind == k) for k, _ in KIND_TITLE]
        w(f"| [{stage_label(s)}](#{anchor(s, stages)}) | " + " | ".join(str(cnt[x]) for x in STATUSES) + f" | {len(its)} | " + " | ".join(map(str, kinds)) + " |")
    kinds_all = [sum(1 for i in items if i.kind == k) for k, _ in KIND_TITLE]
    w("| **Jami** | " + " | ".join(f"**{tot[x]}**" for x in STATUSES) + f" | **{len(items)}** | " + " | ".join(f"**{k}**" for k in kinds_all) + " |")
    w("")
    n_us = len({i.id.split("-", 1)[1] for i in items if i.kind == "US"})
    w(f"Manba qamrovi: {len(matrix)} US (30) → {n_us} tasi bosqich ro'yxatlarida; {len(eps)} endpoint katalog qatori (17: 4, 14: {sum(1 for e in eps if e.id.startswith('14'))}, 18: {sum(1 for e in eps if e.id.startswith('18'))}, 19: {sum(1 for e in eps if e.id.startswith('19'))}, 20: {sum(1 for e in eps if e.id.startswith('20'))}, 33: {sum(1 for e in eps if e.id.startswith('33'))}); "
      f"{len(screens)} ekran (07, UX-INSTALL bilan); {len(tables)} jadval (12); {len(qts)} QT (31). Biriktirilmagan: {', '.join(unassigned) if unassigned else 'yo`q'}.".replace("yo`q", "yo'q"))
    w("")

    # Bosqich 0 dan qolganlar
    w("## Bosqich 0 dan qolganlar")
    w("")
    w("Bosqich 0 kodi `e06e9cc` commit'ida; G-02…G-12 Bosqich 1 bilan birga yopildi (2026-10-17). Qolgani — asoschining tashqi ishlari (⛔).")
    w("")
    w("| # | Bo'shliq | Tafsilot | Qatorlar | Kim / turi |")
    w("|---|---|---|---|---|")
    for g in GAPS:
        w(f"| {g[0]} | {g[1]} | {g[2]} | {g[3]} | {g[4]} |")
    w("")
    rest = [i for i in items if i.stage == "0" and i.status != DONE]
    w(f"Bosqich 0 ning ✅ bo'lmagan barcha qatorlari ({len(rest)}): " + ", ".join(f"`{i.id}` {i.status}" for i in rest) + ".")
    w("")

    # keyingi bosqichga o'tkazilgan topilmalar
    w("## Bosqich 1 tekshiruvi: keyingi bosqichlarga o'tkazilgan topilmalar")
    w("")
    w("Bosqich 1 + B0 bo'shliqlari 3 ta Opus tekshiruvchidan (xavfsizlik, spec, veb — 39 topilma) va Opus qabul agentidan o'tdi: 30 qabul qilindi va tuzatildi (kod yoki spec), 3 rad etildi, quyidagilar — keyingi bosqichga.")
    w("")
    w("| Topilma | Tafsilot | Bosqich | Sabab |")
    w("|---|---|---|---|")
    for d in DEFERRED:
        w(f"| {d[0]} | {d[1]} | {d[2]} | {d[3]} |")
    w("")

    w("## Bosqich 2 tekshiruvi: keyingi bosqichlarga o'tkazilgan topilmalar")
    w("")
    w("Bosqich 2 3 ta Opus tekshiruvchidan (buxgalteriya to'g'riligi — 17, xavfsizlik/RLS/parallellik — 10, veb 07/08 — 22 topilma; qabul agenti WEB-23 ni qo'shdi) va Opus qabul agentlaridan o'tdi: 50 topilmadan 45 tasi qabul qilindi va tuzatildi (kod va/yoki spec), 3 tasi rad etildi (ACC-11, ACC-14, WEB-14 — spec aniqlashtirildi), quyidagilar — keyingi bosqichga (ACC-07, ACC-09, WEB-10 backend qismi).")
    w("")
    w("| Topilma | Tafsilot | Bosqich | Sabab |")
    w("|---|---|---|---|")
    for d in DEFERRED_B2:
        w(f"| {d[0]} | {d[1]} | {d[2]} | {d[3]} |")
    w("")

    # Asoschi qarorlari
    w("## Asoschi qarorlari")
    w("")
    w("| Band | Qaror mavzusi | Holat | Kodga ta'siri |")
    w("|---|---|---|---|")
    for f in FOUNDER:
        w(f"| {f[0]} | {f[1]} | {f[2]} | {f[3]} |")
    w("")

    # Tashqi bog'liqliklar
    w("## Tashqi bog'liqliklar (26 Jadval B)")
    w("")
    w("Real adapterni bloklaydigan bandlar va ungacha ishlatiladigan vaqtinchalik standart / fake. Manba — `26-ochiq-savollar-reestri.md` Jadval B (generatsiya qilingan); xatlar `27` \"Tashqi bog'liqliklar\" jadvalida.")
    w("")
    w("| 26 # | Savol | Kim | Vaqtinchalik standart / fake | Bloklaydigan bosqich |")
    w("|---|---|---|---|---|")
    for r in parse_table_b():
        w(f"| {r[0]} | {clean(r[2], 150)} | {clean(r[3], 60)} | {clean(r[5], 200)} | {clean(r[6], 90)} |")
    w("")

    # bosqichlar
    for s in STAGES:
        st = stages.get(s)
        if not st:
            continue
        its = [i for i in items if i.stage == s]
        w(f"## {stage_label(s)}" + (f": {st.title}" if s != "K" else ""))
        w("")
        if st.goal:
            w(f"**Maqsad (27):** {clean(st.goal, 400)}")
            w("")
        cnt = {x: sum(1 for i in its if i.status == x) for x in STATUSES}
        w("Holat: " + " · ".join(f"{x} {cnt[x]}" for x in STATUSES) + f" · jami {len(its)}")
        w("")
        for k, title in KIND_TITLE:
            sub = [i for i in its if i.kind == k]
            if not sub:
                continue
            w(f"### {stage_label(s)} — {title}")
            w("")
            w("| ID | Holat | Band | Manba | Dalil |")
            w("|---|---|---|---|---|")
            for i in sub:
                w(f"| {i.id} | {i.status} | {i.text} | {i.source} | {i.evidence} |")
            w("")
    w("## Manbalar")
    w("")
    w("- `spec/kod-uchun/27-backlog.md`, `30-izchillik-matritsasi.md`, `31-qabul-testlari.md`, `12-db-sxema.md` §6.1, `14` §9/§18/§20, `17` §1, `18` §1, `19`, `20` \"Endpoint indeksi\", `33` §9.3/§10, `07`, `26` Jadval B.")
    w("- Kod: `backend/` (pytest — 462 test), `web/` (vitest — 347, Playwright — 53), B0 commit `e06e9cc` + Bosqich 1 ishchi daraxti (2026-10-17).")
    w("- Generator: `spec/implementatsiya/_scripts/gen_holat.py`.")
    w("")
    return "\n".join(L)


def anchor(s: str, stages) -> str:
    title = stage_label(s) + (f": {stages[s].title}" if s != "K" else "")
    a = title.lower()
    a = re.sub(r"[^\w\s-]", "", a)
    return re.sub(r"\s", "-", a)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--pytest", action="store_true")
    a = ap.parse_args()
    text = build(a.pytest)
    if a.check:
        old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if old != text:
            print("00-holat.md eskirgan — generatorni ishga tushiring", file=sys.stderr)
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"yozildi: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
