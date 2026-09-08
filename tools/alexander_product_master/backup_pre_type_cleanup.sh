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
docker exec -u postgres doralex-production-db bash -lc 'pg_dump -U doralex_prod -d doralex_prod -Fc -f /var/lib/postgresql/doralex_prod.dump'
docker cp doralex-production-db:/var/lib/postgresql/doralex_prod.dump "$ROOT/db/doralex_prod.dump"
docker exec -u postgres doralex-production-db pg_restore -l /var/lib/postgresql/doralex_prod.dump > "$ROOT/db/pg_restore.list"
docker exec -u postgres doralex-production-db rm -f /var/lib/postgresql/doralex_prod.dump
test -s "$ROOT/db/pg_restore.list"
test -s "$ROOT/db/doralex_prod.dump"
echo "PRE_PRODUCT_TYPE_BACKUP=PASS"
echo "ROOT=$ROOT"
wc -l "$ROOT/db/pg_restore.list"
EOS
