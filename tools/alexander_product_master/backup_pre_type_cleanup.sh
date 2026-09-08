#!/usr/bin/env bash
# Create pre_alexander_product_type_cleanup_<timestamp> on the server.
# Includes DB dump listing validation (pg_restore -l). Does not restore.
set -euo pipefail
STAMP="${1:-$(date +%Y%m%d_%H%M%S)}"
NAME="pre_alexander_product_type_cleanup_${STAMP}"
ssh doralex-server bash -s -- "$NAME" <<'EOS'
set -euo pipefail
NAME="$1"
ROOT="/opt/odoo-backups/${NAME}"
mkdir -p "$ROOT"/{db,filestore,addons,config}
docker exec doralex-production-db pg_dump -U odoo -Fc doralex_prod > "$ROOT/db/doralex_prod.dump"
docker exec doralex-production-db pg_restore -l /dev/stdin < "$ROOT/db/doralex_prod.dump" > "$ROOT/db/pg_restore.list"
test -s "$ROOT/db/pg_restore.list"
echo "PRE_PRODUCT_TYPE_BACKUP=PASS"
echo "ROOT=$ROOT"
wc -l "$ROOT/db/pg_restore.list"
EOS
