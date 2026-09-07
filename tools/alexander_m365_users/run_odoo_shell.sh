#!/usr/bin/env bash
# Copia un script al contenedor Odoo (staging o prod) y lo ejecuta en shell.
set -euo pipefail
TARGET="${1:?staging|production}"
SRC="${2:?script path}"
NAME="$(basename "$SRC")"
case "$TARGET" in
  staging)
    CT=doralex-enterprise-staging-odoo
    DB=doralex_ent_staging
    ;;
  production)
    CT=doralex-production-odoo
    DB=doralex_prod
    ;;
  *)
    echo "target must be staging or production" >&2
    exit 2
    ;;
esac
ROOT="$(cd "$(dirname "$0")" && pwd)"
scp -q "$SRC" "doralex-server:/tmp/${NAME}"
scp -q "$ROOT/catalog.py" "doralex-server:/tmp/catalog.py"
ssh doralex-server "docker cp /tmp/${NAME} ${CT}:/tmp/${NAME} && docker cp /tmp/catalog.py ${CT}:/tmp/catalog.py && docker exec -u 100:101 -e ODOO_USER_APPLY=\"${ODOO_USER_APPLY:-}\" -e ODOO_TEMP_PASSWORD=\"${ODOO_TEMP_PASSWORD:-}\" -e ODOO_QA_LIVE_DOCS=\"${ODOO_QA_LIVE_DOCS:-}\" ${CT} bash -lc 'python3 /usr/bin/odoo shell --database=${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/${NAME}'"
