#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:?staging|production}"
MODE="${2:-inspect}"  # inspect|dump|qa
case "$TARGET" in
  staging) CT=doralex-enterprise-staging-odoo; DB=doralex_ent_staging ;;
  production) CT=doralex-production-odoo; DB=doralex_prod ;;
  *) echo "target must be staging or production" >&2; exit 2 ;;
esac
ROOT="$(cd "$(dirname "$0")" && pwd)"

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
  inspect) run_shell "$ROOT/inspect_price_engine.py" ;;
  dump)
    run_shell "$ROOT/dump_product_prices.py" "-e PRODUCT_PRICE_DUMP=/tmp/product_price_dump.json"
    ssh doralex-server "docker cp ${CT}:/tmp/product_price_dump.json /tmp/product_price_dump_${TARGET}.json"
    mkdir -p "$ROOT/../../docs/enterprise_conversion/evidence/alexander_product_price_audit_20260908"
    scp -q "doralex-server:/tmp/product_price_dump_${TARGET}.json" \
      "$ROOT/../../docs/enterprise_conversion/evidence/alexander_product_price_audit_20260908/product_price_dump_${TARGET}.json"
    ;;
  qa) run_shell "$ROOT/qa_quotation_price.py" ;;
  *) echo "mode must be inspect|dump|qa" >&2; exit 2 ;;
esac
