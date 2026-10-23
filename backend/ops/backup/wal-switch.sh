#!/usr/bin/env bash
# Close the current WAL segment so wal-receive uploads it (RPO <= 5 min on a quiet database).
# pg_switch_wal() is a no-op when nothing was written since the last switch. The backup role
# needs: GRANT EXECUTE ON FUNCTION pg_switch_wal() TO <backup role>. Cron: every 4 minutes.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

pg_preflight
psql -X -v ON_ERROR_STOP=1 -Atq -c "SELECT pg_switch_wal()" > /dev/null
