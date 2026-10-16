#!/usr/bin/env bash
# Point-in-time restore (qaror #51: RPO <= 5 min, RTO <= 4 h) into an EMPTY data directory on a
# host with PostgreSQL 16 binaries and wal-g. Never points at the production data directory.
#
#   1. wal-g backup-fetch  — base backup (RESTORE_BACKUP, default LATEST; use the newest base
#                            backup that finished BEFORE the target time);
#   2. recovery settings   — restore_command = wal-g wal-fetch, optional recovery_target_time,
#                            recovery_target_action = promote, archive_mode = off (a restored
#                            cluster must never push WAL into the production repository);
#   3. RESTORE_START=1     — start with pg_ctl (the postmaster inherits this env, so
#                            restore_command sees the WAL-G variables) and wait until the
#                            cluster leaves recovery.
#
# Env: lib.sh walg_preflight, PGDATA_RESTORE (empty dir), RESTORE_BACKUP (default LATEST),
#      RECOVERY_TARGET_TIME (optional, e.g. "2026-10-17 10:30:00+05"), RESTORE_PORT (default 5433),
#      PG_BINDIR (optional, dir with pg_ctl/psql), RESTORE_START (default 1),
#      RESTORE_WAIT_S (default 14400).
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

walg_preflight
require_env PGDATA_RESTORE
backup="${RESTORE_BACKUP:-LATEST}"
port="${RESTORE_PORT:-5433}"
wait_s="${RESTORE_WAIT_S:-14400}"
pg_ctl="${PG_BINDIR:+$PG_BINDIR/}pg_ctl"
psql_bin="${PG_BINDIR:+$PG_BINDIR/}psql"
target_time="${RECOVERY_TARGET_TIME:-}"

[[ "$port" =~ ^[0-9]+$ ]] || die "RESTORE_PORT raqam bo'lishi shart"
[[ "$target_time" != *"'"* ]] || die "RECOVERY_TARGET_TIME ichida apostrof bo'lmasin"
mkdir -p "$PGDATA_RESTORE"
if [[ -n "$(ls -A "$PGDATA_RESTORE")" ]]; then
  die "$PGDATA_RESTORE bo'sh emas — tiklash faqat bo'sh katalogga"
fi
chmod 700 "$PGDATA_RESTORE"

started=$(date +%s)
log "backup-fetch: $backup -> $PGDATA_RESTORE"
wal-g backup-fetch "$PGDATA_RESTORE" "$backup"

{
  echo "# --- erp pitr-restore.sh $(date -u +%Y-%m-%dT%H:%M:%SZ) ---"
  echo "restore_command = 'wal-g wal-fetch %f %p'"
  echo "recovery_target_action = 'promote'"
  echo "recovery_target_timeline = 'latest'"
  if [[ -n "$target_time" ]]; then
    echo "recovery_target_time = '$target_time'"
    echo "recovery_target_inclusive = true"
  fi
  echo "archive_mode = 'off'"
  echo "port = $port"
  echo "listen_addresses = 'localhost'"
} >> "$PGDATA_RESTORE/postgresql.auto.conf"
touch "$PGDATA_RESTORE/recovery.signal"
# a remote (BASE_BACKUP) copy of a managed server may carry provider-specific settings:
# they are overridden above; review postgresql.conf before exposing the cluster
rm -f "$PGDATA_RESTORE/postmaster.pid"
log "recovery sozlandi (target=${target_time:-WAL oxirigacha}, port=$port)"

if [[ "${RESTORE_START:-1}" != "1" ]]; then
  log "RESTORE_START=0: klaster ishga tushirilmadi; qo'lda: $pg_ctl -D $PGDATA_RESTORE start"
  exit 0
fi

"$pg_ctl" -D "$PGDATA_RESTORE" -l "$PGDATA_RESTORE/restore.log" -w -t 120 start
deadline=$((started + wait_s))
until [[ "$("$psql_bin" -X -Atq -h localhost -p "$port" -d postgres -c 'SELECT pg_is_in_recovery()')" == "f" ]]; do
  (($(date +%s) < deadline)) || die "recovery ${wait_s}s ichida tugamadi — $PGDATA_RESTORE/restore.log"
  sleep 10
done
elapsed=$(($(date +%s) - started))
log "tiklandi va promote qilindi: ${elapsed}s (RTO maqsadi <= 14400s)"
echo "RESTORE_ELAPSED_S=$elapsed"
