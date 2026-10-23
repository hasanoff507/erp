#!/usr/bin/env bash
# Shared helpers for the backup scripts (15 §7, qaror #51/#65). Sourced, never executed.
# All inputs come from the environment; secrets are decrypted by SOPS/age at deploy time into
# the file named by ERP_BACKUP_ENV_FILE (never committed) — see ../RUNBOOK-backup-restore.md.

set -euo pipefail

if [[ -n "${ERP_BACKUP_ENV_FILE:-}" ]]; then
  if [[ ! -r "$ERP_BACKUP_ENV_FILE" ]]; then
    echo "ERP_BACKUP_ENV_FILE=$ERP_BACKUP_ENV_FILE o'qib bo'lmadi" >&2
    exit 64
  fi
  set -a
  # shellcheck source=/dev/null
  . "$ERP_BACKUP_ENV_FILE"
  set +a
fi

log() {
  printf '%s [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${0##*/}" "$*" >&2
}

die() {
  log "XATO: $*"
  exit 1
}

# require_env NAME... — fail fast (exit 64) when a required variable is empty
require_env() {
  local name missing=()
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      missing+=("$name")
    fi
  done
  if ((${#missing[@]} > 0)); then
    log "XATO: muhit o'zgaruvchilari berilmagan: ${missing[*]}"
    exit 64
  fi
}

require_cmd() {
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" > /dev/null 2>&1 || die "'$cmd' topilmadi (PATH)"
  done
}

# WAL-G settings every script needs: storage (UzCloud S3), client-side encryption, source DB
walg_preflight() {
  require_cmd wal-g
  require_env WALG_S3_PREFIX AWS_ENDPOINT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY WALG_LIBSODIUM_KEY
  export AWS_S3_FORCE_PATH_STYLE="${AWS_S3_FORCE_PATH_STYLE:-true}"
  export AWS_REGION="${AWS_REGION:-us-east-1}"
  export WALG_LIBSODIUM_KEY_TRANSFORM="${WALG_LIBSODIUM_KEY_TRANSFORM:-hex}"
  export WALG_COMPRESSION_METHOD="${WALG_COMPRESSION_METHOD:-zstd}"
}

# pg_preflight — libpq connection to the source database (backup role with REPLICATION)
pg_preflight() {
  require_cmd psql
  require_env PGHOST PGUSER
  export PGPORT="${PGPORT:-5432}"
  export PGDATABASE="${PGDATABASE:-postgres}"
  export PGSSLMODE="${PGSSLMODE:-require}"
}
