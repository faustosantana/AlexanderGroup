#!/usr/bin/env bash
# Run an odoo-shell script on enterprise-staging. Never Prod.
set -euo pipefail
SRC="${1:?script path}"
NAME="$(basename "$SRC")"
scp "$SRC" "doralex-server:/tmp/${NAME}"
ssh doralex-server "docker cp /tmp/${NAME} doralex-enterprise-staging-odoo:/tmp/${NAME} && docker exec -u 100:101 ${QA_ENV:+} doralex-enterprise-staging-odoo bash -lc 'export QA_COMPANY_IDS=\"${QA_COMPANY_IDS:-}\"; python3 /usr/bin/odoo shell --database=doralex_ent_staging --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/${NAME}'"
