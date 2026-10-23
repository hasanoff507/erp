#!/usr/bin/env bash
# Continuous WAL archive (RPO <= 5 min, qaror #51): stream WAL from the DBaaS primary over the
# replication protocol and upload every segment, encrypted, to UzCloud S3. Long-running —
# run under systemd (erp-wal-receive.service, Restart=always). wal-switch.sh closes a segment
# at least every 4 minutes so a quiet database still meets the RPO.
#
# Env: lib.sh walg_preflight/pg_preflight + WALG_SLOTNAME (physical slot, default walg_erp).
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

walg_preflight
pg_preflight
export WALG_SLOTNAME="${WALG_SLOTNAME:-walg_erp}"

log "wal-receive boshlandi: slot=$WALG_SLOTNAME host=$PGHOST prefix=$WALG_S3_PREFIX"
exec wal-g wal-receive
