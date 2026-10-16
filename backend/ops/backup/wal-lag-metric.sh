#!/usr/bin/env bash
# WAL archive lag for Prometheus (25 §5 alert "WAL arxivi kechikishi > 5 daqiqa — RPO buzilishi").
# Writes erp_wal_archive_lag_seconds to a node_exporter textfile-collector file:
#   0                      — the newest archived segment is the one before the current segment
#                            (everything except the segment being written is archived);
#   age of newest segment  — otherwise (the archive is behind);
#   -1                     — nothing archived at all (alert on < 0 too).
# Env: lib.sh pg_preflight, WAL_LIST_REMOTE (rclone path of the WAL-G wal_005/ folder, e.g.
#      uzcloud:erp-pg-backup/prod/wal_005), TEXTFILE_DIR (node_exporter textfile directory).
# Cron: every minute.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

pg_preflight
require_cmd rclone
require_env WAL_LIST_REMOTE TEXTFILE_DIR

# segment preceding the current insert position (pg_lsn - numeric needs PostgreSQL >= 14)
previous=$(psql -X -v ON_ERROR_STOP=1 -Atq \
  -c "SELECT pg_walfile_name(pg_current_wal_lsn() - 16777216::numeric)")
# newest archived segment as "<unix mtime> <24-hex name>"; names sort chronologically
newest=$(
  rclone lsf --files-only --format "tp" --separator " " --time-format unix "$WAL_LIST_REMOTE" \
    | awk '{ n = substr($2, 1, 24); if (n ~ /^[0-9A-F]+$/ && length(n) == 24 && n > best) { best = n; t = $1 } }
           END { if (best != "") print t, best }'
)

now=$(date +%s)
lag=-1
if [[ -n "$newest" ]]; then
  read -r mtime name <<< "$newest"
  if [[ "$name" > "$previous" || "$name" == "$previous" ]]; then
    lag=0
  else
    lag=$((now - mtime))
  fi
fi

tmp=$(mktemp "$TEXTFILE_DIR/.erp_wal.XXXXXX")
{
  echo "# HELP erp_wal_archive_lag_seconds Age of the newest archived WAL segment while the archive is behind (0 caught up, -1 empty)."
  echo "# TYPE erp_wal_archive_lag_seconds gauge"
  echo "erp_wal_archive_lag_seconds $lag"
  echo "# HELP erp_wal_archive_lag_checked_timestamp_seconds Unix time of the last successful lag check."
  echo "# TYPE erp_wal_archive_lag_checked_timestamp_seconds gauge"
  echo "erp_wal_archive_lag_checked_timestamp_seconds $now"
} > "$tmp"
chmod 644 "$tmp"
mv "$tmp" "$TEXTFILE_DIR/erp_wal.prom"
