#!/usr/bin/env bash
# Verifica que justech_alexander_reports 19.0.3.8.5 y 58 QWeb sigan en staging.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

load_env enterprise-staging
expected_qweb="${EXPECTED_QWEB:-58}"
expected_ver="${EXPECTED_REPORTS_VERSION:-19.0.3.8.5}"

row="$(docker exec doralex-enterprise-staging-db \
  bash -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT (SELECT latest_version FROM ir_module_module WHERE name='\''justech_alexander_reports'\'' AND state='\''installed'\''), (SELECT COUNT(*) FROM ir_ui_view WHERE key LIKE '\''justech_alexander%'\'');"')"
row="$(echo "$row" | tr -d '[:space:]')"
ver="${row%%|*}"
qweb="${row##*|}"
log "justech_alexander_reports=${ver} qweb=${qweb}"
if [ "$ver" != "$expected_ver" ] || [ "$qweb" != "$expected_qweb" ]; then
  err "REPORTS_DRIFT version=${ver} (expected ${expected_ver}) qweb=${qweb} (expected ${expected_qweb})"
  exit 3
fi
log "DORALEX_REPORTS_PRESERVED = YES"
