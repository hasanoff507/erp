#!/usr/bin/env bash
# Off-provider copy (qaror #65, 15 §7.1): copy the WAL-G repository from UzCloud S3 to a bucket
# at a second provider. Objects are already libsodium-encrypted by WAL-G, so the second
# provider only ever sees ciphertext. `copy` (not `sync`): deletions at UzCloud never reach
# the copy — retention there is the bucket's own lifecycle/object-lock rule (5 years).
#
# Remotes are defined purely by env (rclone RCLONE_CONFIG_<NAME>_* convention), e.g.
#   RCLONE_CONFIG_UZCLOUD_TYPE=s3 RCLONE_CONFIG_UZCLOUD_PROVIDER=Other
#   RCLONE_CONFIG_UZCLOUD_ENDPOINT=... RCLONE_CONFIG_UZCLOUD_ACCESS_KEY_ID=... (+ _SECRET_ACCESS_KEY)
#   RCLONE_CONFIG_OFFSITE_TYPE=s3 ... (second provider)
# Env: OFFSITE_SRC (e.g. uzcloud:erp-pg-backup/prod), OFFSITE_DST (e.g. offsite:erp-pg-copy/prod),
#      OFFSITE_BWLIMIT (optional, e.g. 20M).
set -euo pipefail
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_cmd rclone
require_env OFFSITE_SRC OFFSITE_DST
[[ "$OFFSITE_SRC" != "$OFFSITE_DST" ]] || die "OFFSITE_SRC va OFFSITE_DST bir xil"

args=(--checksum --immutable --transfers 8 --retries 5 --low-level-retries 20 --stats-one-line --stats 0)
if [[ -n "${OFFSITE_BWLIMIT:-}" ]]; then
  args+=(--bwlimit "$OFFSITE_BWLIMIT")
fi

started=$(date +%s)
log "off-provider nusxa: $OFFSITE_SRC -> $OFFSITE_DST"
rclone copy "${args[@]}" "$OFFSITE_SRC" "$OFFSITE_DST"
# every source object must exist (same size/hash) at the destination
rclone check --one-way --checksum "$OFFSITE_SRC" "$OFFSITE_DST"
log "off-provider nusxa tayyor ($(($(date +%s) - started)) s)"
