#!/usr/bin/env bash
# Run a read-only (or already-reviewed) odoo-shell script on production.
set -euo pipefail
SRC="${1:?script path}"
NAME="$(basename "$SRC")"
scp "$SRC" "doralex-server:/tmp/${NAME}"
ssh doralex-server "docker cp /tmp/${NAME} doralex-production-odoo:/tmp/${NAME} && docker exec -u 100:101 doralex-production-odoo bash -lc 'python3 /usr/bin/odoo shell --database=doralex_prod --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/${NAME}'"
