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
PAYLOAD="${PHASE2_PAYLOAD_LOCAL:-$ROOT/../../docs/enterprise_conversion/evidence/alexander_product_master_phase2_20260908/phase2_apply_payload.json}"
DRY=0
if [[ "$MODE" == "dry" ]]; then DRY=1; fi
scp -q "$PAYLOAD" "doralex-server:/tmp/phase2_apply_payload.json"
scp -q "$ROOT/phase2_apply.py" "doralex-server:/tmp/phase2_apply.py"
ssh doralex-server "docker cp /tmp/phase2_apply_payload.json ${CT}:/tmp/phase2_apply_payload.json && docker cp /tmp/phase2_apply.py ${CT}:/tmp/phase2_apply.py && docker exec -u 100:101 \
  -e PHASE2_PAYLOAD=/tmp/phase2_apply_payload.json \
  -e PHASE2_DRY=${DRY} \
  ${CT} bash -lc 'python3 /usr/bin/odoo shell --database=${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/phase2_apply.py'"
