#!/usr/bin/env bash
# Run an NCF script on staging or production. Copies helpers to /tmp first.
set -euo pipefail
TARGET="${1:?staging|production}"
SCRIPT="${2:?script path}"
shift 2
case "$TARGET" in
  staging) CT=doralex-enterprise-staging-odoo; DB=doralex_ent_staging ;;
  production) CT=doralex-production-odoo; DB=doralex_prod ;;
  *) echo "target must be staging or production" >&2; exit 2 ;;
esac
ROOT="$(cd "$(dirname "$0")" && pwd)"
NAME="$(basename "$SCRIPT")"
scp -q "$ROOT/authorized.py" "$ROOT/gates.py" "$SCRIPT" "doralex-server:/tmp/"
ssh doralex-server "docker cp /tmp/authorized.py ${CT}:/tmp/authorized.py && \
  docker cp /tmp/gates.py ${CT}:/tmp/gates.py && \
  docker cp /tmp/${NAME} ${CT}:/tmp/${NAME} && \
  docker exec -u 100:101 $* ${CT} bash -lc \
  'python3 /usr/bin/odoo shell --database=${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/${NAME}'"
