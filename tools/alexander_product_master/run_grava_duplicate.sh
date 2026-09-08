#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:?staging|production}"
MODE="${2:-apply}"
case "$TARGET" in
  staging) CT=doralex-enterprise-staging-odoo; DB=doralex_ent_staging ;;
  production) CT=doralex-production-odoo; DB=doralex_prod ;;
  *) echo "target must be staging or production" >&2; exit 2 ;;
esac
ROOT="$(cd "$(dirname "$0")" && pwd)"
DRY=0
if [[ "$MODE" == "dry" ]]; then DRY=1; fi
scp -q "$ROOT/apply_grava_duplicate.py" "doralex-server:/tmp/apply_grava_duplicate.py"
ssh doralex-server "docker cp /tmp/apply_grava_duplicate.py ${CT}:/tmp/apply_grava_duplicate.py && docker exec -u 100:101 \
  -e GRAVA_DUP_DRY=${DRY} \
  ${CT} bash -lc 'python3 /usr/bin/odoo shell --database=${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/apply_grava_duplicate.py'"
