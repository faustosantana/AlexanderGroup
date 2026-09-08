#!/usr/bin/env bash
# Dump / dry-run / apply / QA product-type corrections on staging or production.
set -euo pipefail
TARGET="${1:?staging|production}"
MODE="${2:-dry}"  # dump|dry|apply|qa|flow
case "$TARGET" in
  staging) CT=doralex-enterprise-staging-odoo; DB=doralex_ent_staging ;;
  production) CT=doralex-production-odoo; DB=doralex_prod ;;
  *) echo "target must be staging or production" >&2; exit 2 ;;
esac
ROOT="$(cd "$(dirname "$0")" && pwd)"
EV="${PRODUCT_TYPE_EVIDENCE:-$ROOT/../../docs/enterprise_conversion/evidence/alexander_product_type_audit_20260908}"
PAYLOAD="${PRODUCT_TYPE_PAYLOAD_LOCAL:-$EV/product_type_apply_payload.json}"

run_shell() {
  local src="$1"
  local extra="${2:-}"
  local name
  name="$(basename "$src")"
  scp -q "$src" "doralex-server:/tmp/${name}"
  ssh doralex-server "docker cp /tmp/${name} ${CT}:/tmp/${name} && docker exec -u 100:101 \
    ${extra} \
    ${CT} bash -lc 'python3 /usr/bin/odoo shell --database=${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/${name}'"
}

case "$MODE" in
  dump)
    run_shell "$ROOT/dump_product_type_catalog.py" "-e PRODUCT_TYPE_DUMP=/tmp/product_type_dump.json"
    ssh doralex-server "docker cp ${CT}:/tmp/product_type_dump.json /tmp/product_type_dump_${TARGET}.json"
    scp -q "doralex-server:/tmp/product_type_dump_${TARGET}.json" "${EV}/product_type_dump_${TARGET}.json"
    ;;
  dry)
    scp -q "$PAYLOAD" "doralex-server:/tmp/product_type_apply_payload.json"
    ssh doralex-server "docker cp /tmp/product_type_apply_payload.json ${CT}:/tmp/product_type_apply_payload.json"
    run_shell "$ROOT/apply_product_type.py" "-e PRODUCT_TYPE_DRY=1 -e PRODUCT_TYPE_PAYLOAD=/tmp/product_type_apply_payload.json"
    ;;
  apply)
    scp -q "$PAYLOAD" "doralex-server:/tmp/product_type_apply_payload.json"
    ssh doralex-server "docker cp /tmp/product_type_apply_payload.json ${CT}:/tmp/product_type_apply_payload.json"
    scp -q "$ROOT/apply_product_type.py" "doralex-server:/tmp/apply_product_type.py"
    ssh doralex-server "docker cp /tmp/apply_product_type.py ${CT}:/tmp/apply_product_type.py && docker exec -u 100:101 \
      -e PRODUCT_TYPE_DRY=0 \
      -e PRODUCT_TYPE_PAYLOAD=/tmp/product_type_apply_payload.json \
      ${CT} bash -lc 'python3 /usr/bin/odoo shell --database=${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" --no-http < /tmp/apply_product_type.py'"
    ;;
  qa)
    run_shell "$ROOT/qa_product_type.py"
    ;;
  flow)
    run_shell "$ROOT/staging_type_flow_qa.py"
    ;;
  *)
    echo "mode must be dump|dry|apply|qa|flow" >&2
    exit 2
    ;;
esac
