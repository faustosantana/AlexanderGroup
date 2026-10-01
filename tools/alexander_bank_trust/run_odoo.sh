#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:?staging|production}"
SCRIPT="${2:?script path}"
case "$TARGET" in
  staging) CT=doralex-enterprise-staging-odoo; DB=doralex_ent_staging ;;
  production) CT=doralex-production-odoo; DB=doralex_prod ;;
  *) echo "target must be staging or production" >&2; exit 2 ;;
esac
NAME="$(basename "$SCRIPT")"
scp -q "$SCRIPT" "doralex-server:/tmp/${NAME}"
ssh doralex-server "docker cp /tmp/${NAME} ${CT}:/tmp/${NAME} && \
  docker exec -u 100:101 ${CT} bash -lc \
  'python3 /usr/bin/odoo shell --database=${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/${NAME}'"
