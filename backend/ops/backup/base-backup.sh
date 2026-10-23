#!/usr/bin/env bash
# Daily full base backup (15 §7.1: "to'liq bazaviy backup kuniga 1 marta") + retention.
#
#   - wal-g backup-push without a data directory = remote backup over the replication
#     protocol (BASE_BACKUP), so it works against UzCloud DBaaS without shell access;
#   - the first backup of each month is marked permanent: the >= 5-year archive (qaror #51,
#     O'RQ-404 29-modda); permanent backups are never removed by `delete retain`;
#   - operational retention: the newest BACKUP_RETAIN_FULL full backups (default 30 = 30 days).
#
# Env: lib.sh walg_preflight/pg_preflight, BACKUP_RETAIN_FULL (default 30),
#      BACKUP_MARK_MONTHLY (default 1; 0 = never mark permanent, e.g. on staging).
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

walg_preflight
pg_preflight
retain="${BACKUP_RETAIN_FULL:-30}"
[[ "$retain" =~ ^[0-9]+$ && "$retain" -ge 7 ]] || die "BACKUP_RETAIN_FULL >= 7 bo'lishi shart (hozir: $retain)"

started=$(date +%s)
log "base backup boshlandi (remote, $PGHOST)"
wal-g backup-push
latest=$(wal-g backup-list 2> /dev/null | awk 'NR > 1 && $1 ~ /^base_/ { name = $1 } END { print name }')
[[ -n "$latest" ]] || die "backup-list bo'sh — backup yozilmadi"
log "backup tayyor: $latest ($(($(date +%s) - started)) s)"

if [[ "${BACKUP_MARK_MONTHLY:-1}" == "1" && "$(date -u +%d)" == "01" ]]; then
  wal-g backup-mark "$latest"
  log "oylik arxiv: $latest permanent (>= 5 yil, qaror #51)"
fi

wal-g delete retain FULL "$retain" --confirm
log "retention: oxirgi $retain ta to'liq backup qoldi (permanent'lar daxlsiz)"
