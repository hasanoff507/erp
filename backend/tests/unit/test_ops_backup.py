"""Backup/restore ops skeleton (qaror #51/#65, 15 §7): scripts, runbook, SOPS rules, ZAP rules."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
OPS = BACKEND / "ops"
BACKUP = OPS / "backup"
RUNBOOK = OPS / "RUNBOOK-backup-restore.md"
SCRIPTS = (
    "lib.sh",
    "wal-receive.sh",
    "wal-switch.sh",
    "base-backup.sh",
    "offsite-copy.sh",
    "pitr-restore.sh",
    "staging-restore.sh",
    "wal-lag-metric.sh",
)
# shapes of real credentials that must never land in ops files (placeholders are fine)
_SECRET_SHAPES = re.compile(
    r"AGE-SECRET-KEY-1|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:password)\s*=\s*\S"
)


@pytest.mark.parametrize("name", SCRIPTS)
def test_script_is_strict_bash_without_secrets(name: str) -> None:
    text = (BACKUP / name).read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash\n")
    assert re.search(r"^set -euo pipefail$", text, re.MULTILINE)
    assert "\r" not in text
    assert not _SECRET_SHAPES.search(text)


def test_runbook_references_every_ops_file() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    for name in (*SCRIPTS, "verify-restore.sql", "erp-backup.cron", "erp-wal-receive.service"):
        assert f"backend/ops/backup/{name}" in runbook, name
        assert (BACKUP / name).is_file(), name
    # founder-only external steps are clearly marked; the restore log of qaror #51 is named
    assert runbook.count("⛔ **tashqi**") >= 6
    assert "docs/ops/restore-log.md" in runbook
    for anchor in ("RPO", "RTO", "PITR", "staging", "age", "SOPS"):
        assert anchor in runbook


def test_cron_and_systemd_point_at_the_scripts() -> None:
    cron = (BACKUP / "erp-backup.cron").read_text(encoding="utf-8")
    for name in ("wal-switch.sh", "wal-lag-metric.sh", "base-backup.sh", "offsite-copy.sh"):
        assert f"/opt/erp/backend/ops/backup/{name}" in cron
    unit = (BACKUP / "erp-wal-receive.service").read_text(encoding="utf-8")
    assert "ExecStart=/opt/erp/backend/ops/backup/wal-receive.sh" in unit
    assert "Restart=always" in unit


def test_sops_rules_parse_and_cover_every_environment() -> None:
    config = yaml.safe_load((REPO / ".sops.yaml").read_text(encoding="utf-8"))
    rules = config["creation_rules"]
    paths = [rule["path_regex"] for rule in rules]
    for target in (
        "deploy/secrets/prod.enc.yaml",
        "deploy/secrets/staging.enc.yaml",
        "deploy/secrets/backup-prod.enc.env",
        "deploy/secrets/backup-staging.enc.env",
    ):
        assert sum(bool(re.search(p, target)) for p in paths) == 1, target
    assert not any(re.search(p, "backend/.env.example") for p in paths)
    for rule in rules:
        recipients = [r.strip() for r in rule["age"].split(",")]
        assert len(recipients) == 2, "deploy key + founder break-glass key"
        assert all(r.startswith("age1") for r in recipients)
        assert "kms" not in rule and "pgp" not in rule  # age only (qaror #65)


def test_zap_rules_are_well_formed() -> None:
    lines = (OPS / "zap" / "rules.tsv").read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    for line in lines:
        rule_id, action, comment = line.split("\t")
        assert rule_id.isdigit() and rule_id not in seen
        assert action in {"IGNORE", "WARN", "FAIL"}
        assert comment.startswith("(") and comment.endswith(")") and len(comment) > 10
        seen.add(rule_id)
    # session-cookie invariants of 15 §8 fail the scan
    assert {"10010", "10011", "10054"} <= {
        line.split("\t")[0] for line in lines if line.split("\t")[1] == "FAIL"
    }
