#!/usr/bin/env bash
# READ-ONLY odoo-shell runner. Never Prod.
set -euo pipefail
SRC="${1:?script path}"
TARGET="${2:-staging}"
NAME="$(basename "$SRC")"

case "$TARGET" in
  staging)
    CT=doralex-enterprise-staging-odoo
    DB=doralex_ent_staging
    ;;
  dev)
    CT=doralex-dev-odoo
    DB=doralex_dev
    ;;
  *)
    echo "Target must be staging or dev (never prod)" >&2
    exit 2
    ;;
esac

scp "$SRC" "doralex-server:/tmp/${NAME}"
ssh doralex-server "docker cp /tmp/${NAME} ${CT}:/tmp/${NAME} && docker exec -u 100:101 ${CT} bash -lc 'python3 /usr/bin/odoo shell --database=${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/${NAME}'"
