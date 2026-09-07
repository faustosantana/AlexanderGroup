#!/usr/bin/env bash
# Apply product master payload on staging or production via Odoo ORM.
set -euo pipefail
TARGET="${1:?staging|production}"
MODE="${2:-apply}"  # apply|dry
case "$TARGET" in
  staging) CT=doralex-enterprise-staging-odoo; DB=doralex_ent_staging ;;
  production) CT=doralex-production-odoo; DB=doralex_prod ;;
  *) echo "target must be staging or production" >&2; exit 2 ;;
esac
ROOT="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="${PRODUCT_MASTER_PAYLOAD_LOCAL:-$ROOT/../../docs/enterprise_conversion/evidence/alexander_product_master_20260907/product_master_payload.json}"
DRY=0
if [[ "$MODE" == "dry" ]]; then DRY=1; fi
scp -q "$PAYLOAD" "doralex-server:/tmp/product_master_payload.json"
scp -q "$ROOT/apply_odoo.py" "doralex-server:/tmp/apply_odoo.py"
ssh doralex-server "docker cp /tmp/product_master_payload.json ${CT}:/tmp/product_master_payload.json && docker cp /tmp/apply_odoo.py ${CT}:/tmp/apply_odoo.py && docker exec -u 100:101 \
  -e PRODUCT_MASTER_PAYLOAD=/tmp/product_master_payload.json \
  -e PRODUCT_MASTER_DRY=${DRY} \
  -e PRODUCT_MASTER_TRUST_IDS=0 \
  -e PRODUCT_MASTER_BATCH=ALEXANDER_PRODUCT_MASTER_20260907 \
  ${CT} bash -lc 'python3 /usr/bin/odoo shell --database=${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/apply_odoo.py'"
