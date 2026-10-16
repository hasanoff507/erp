#!/usr/bin/env bash
# Quarterly full restore drill on staging (qaror #51, 15 §7.2): PITR-restore the production
# backup on the staging host, run verify-restore.sql, measure the time and print one row for
# docs/ops/restore-log.md (appended to RESTORE_LOG when it is set). Exit code != 0 on failure
# or when the measured time breaks the RTO (<= 4 h) — that is an incident (15 §7.2, §10).
#
# Env: everything pitr-restore.sh needs (pointed at the PRODUCTION repository with READ-ONLY
#      storage credentials), RESTORE_OPERATOR (who ran it), RESTORE_LOG (optional path),
#      RESTORE_DBNAME (default erp), RTO_LIMIT_S (default 14400).
set -euo pipefail
here="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_env PGDATA_RESTORE RESTORE_OPERATOR
port="${RESTORE_PORT:-5433}"
rto_limit="${RTO_LIMIT_S:-14400}"
psql_bin="${PG_BINDIR:+$PG_BINDIR/}psql"
target="${RECOVERY_TARGET_TIME:-WAL oxiri}"
day=$(date -u +%Y-%m-%d)
started=$(date +%s)
result="muvaffaqiyatli"
note=""

if ! RESTORE_START=1 RESTORE_PORT="$port" "$here/pitr-restore.sh"; then
  result="muvaffaqiyatsiz"
  note="pitr-restore.sh xato bilan tugadi"
elif ! "$psql_bin" -X -v ON_ERROR_STOP=1 -h localhost -p "$port" -d "${RESTORE_DBNAME:-erp}" \
  -f "$here/verify-restore.sql"; then
  result="muvaffaqiyatsiz"
  note="verify-restore.sql tekshiruvi o'tmadi"
fi
elapsed=$(($(date +%s) - started))
if [[ "$result" == "muvaffaqiyatli" ]] && ((elapsed > rto_limit)); then
  result="muvaffaqiyatsiz (RTO oshdi)"
  note="o'lchangan vaqt ${elapsed}s > ${rto_limit}s — insident (15 §10)"
fi

row="| $day | ${RESTORE_BACKUP:-LATEST} | $target | $((elapsed / 60)) daq | $result | $RESTORE_OPERATOR | ${note:-—} |"
echo "$row"
if [[ -n "${RESTORE_LOG:-}" ]]; then
  echo "$row" >> "$RESTORE_LOG"
  log "natija $RESTORE_LOG ga yozildi"
fi
[[ "$result" == "muvaffaqiyatli" ]]
